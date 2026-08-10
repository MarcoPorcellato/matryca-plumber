"""External, graph-scoped location for the immutable P0 evidence archive.

This resolver intentionally does not import or initialize Shadow DB.  It shares
the established cache-root policy while keeping evidence storage a separate,
append-only component that remains usable in strict read-only graph mode.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root
from ..graph.safety.write_policy import GraphReadOnlyError, RuntimeWritePolicy

_APP_CACHE_DIRNAME = "matryca-plumber"
_GRAPH_CACHE_DIRNAME = "graphs"
_GRAPH_ID_VERSION = "v1"
_ARCHIVE_DIRNAME = "evidence"
_EVENTS_FILENAME = "events.jsonl"
_WRITER_LOCK_FILENAME = "events.writer.flock"


class EvidenceArchiveLocationError(ValueError):
    """A content-free failure to resolve a safe external evidence location."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Evidence archive location unavailable ({reason})")


@dataclass(frozen=True, slots=True)
class EvidenceArchiveLocation:
    """Canonical external archive paths owned by one graph."""

    graph_root: Path
    cache_root: Path
    graph_id: str
    archive_dir: Path
    events_path: Path
    writer_lock_path: Path

    def ensure_directory(self) -> Path:
        """Create only the private evidence directory after containment checks."""
        directories = (
            self.cache_root,
            self.cache_root / _GRAPH_CACHE_DIRNAME,
            self.archive_dir.parent,
            self.archive_dir,
        )
        for directory in directories:
            resolved = directory.resolve(strict=False)
            if resolved != self.cache_root and not resolved.is_relative_to(self.cache_root):
                raise EvidenceArchiveLocationError("archive_directory_escape")
            if directory.is_symlink():
                raise EvidenceArchiveLocationError("archive_directory_symlink")
            resolved.mkdir(mode=0o700, exist_ok=True)
            if os.name == "posix":
                try:
                    resolved.chmod(0o700)
                except OSError as exc:
                    raise EvidenceArchiveLocationError("archive_directory_permissions") from exc
        return self.archive_dir


def resolve_evidence_archive_location(
    graph_root: Path | str,
    *,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
) -> EvidenceArchiveLocation:
    """Resolve an external archive location without creating a file or Shadow DB."""
    source = os.environ if env is None else env
    platform_value = sys.platform if platform_name is None else platform_name
    home_value = Path.home() if home is None else Path(home)
    root = resolved_graph_root(graph_root)
    candidate = _cache_root(source, platform_name=platform_value, home=home_value)
    if not candidate.is_absolute():
        raise EvidenceArchiveLocationError("cache_root_not_absolute")
    if candidate.is_symlink():
        raise EvidenceArchiveLocationError("cache_root_symlink")
    try:
        policy = RuntimeWritePolicy(graph_root=root, cache_path=candidate)
        policy.ensure_write_allowed(candidate, operation="resolve_evidence_archive")
    except GraphReadOnlyError as exc:
        raise EvidenceArchiveLocationError(exc.reason) from exc
    cache_root = policy.cache_path
    if cache_root is None:  # pragma: no cover - constructor input guarantees it
        raise EvidenceArchiveLocationError("cache_root_missing")

    graph_id = _canonical_graph_identity(root, platform_name=platform_value)
    archive_dir = (cache_root / _GRAPH_CACHE_DIRNAME / graph_id / _ARCHIVE_DIRNAME).resolve(
        strict=False
    )
    if not archive_dir.is_relative_to(cache_root):
        raise EvidenceArchiveLocationError("archive_directory_escape")
    if archive_dir.is_symlink():
        raise EvidenceArchiveLocationError("archive_directory_symlink")
    events_path = archive_dir / _EVENTS_FILENAME
    writer_lock_path = archive_dir / _WRITER_LOCK_FILENAME
    if events_path.is_symlink():
        raise EvidenceArchiveLocationError("events_path_symlink")
    if writer_lock_path.is_symlink():
        raise EvidenceArchiveLocationError("writer_lock_symlink")
    return EvidenceArchiveLocation(
        graph_root=root,
        cache_root=cache_root,
        graph_id=graph_id,
        archive_dir=archive_dir,
        events_path=events_path,
        writer_lock_path=writer_lock_path,
    )


def _cache_root(env: Mapping[str, str], *, platform_name: str, home: Path) -> Path:
    override = (env.get("MATRYCA_CACHE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    if platform_name == "darwin":
        return home.expanduser() / "Library" / "Caches" / _APP_CACHE_DIRNAME
    if platform_name == "win32":
        local_app_data = (env.get("LOCALAPPDATA") or "").strip()
        base = Path(local_app_data) if local_app_data else home.expanduser() / "AppData" / "Local"
        return base / _APP_CACHE_DIRNAME / "Cache"
    xdg_cache = (env.get("XDG_CACHE_HOME") or "").strip()
    base = Path(xdg_cache) if xdg_cache else home.expanduser() / ".cache"
    return base / _APP_CACHE_DIRNAME


def _canonical_graph_identity(graph_root: Path, *, platform_name: str) -> str:
    canonical = str(graph_root)
    if platform_name == "win32":
        canonical = os.path.normcase(canonical).casefold()
    digest = hashlib.sha256(canonical.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"{_GRAPH_ID_VERSION}-{digest[:32]}"


__all__ = [
    "EvidenceArchiveLocation",
    "EvidenceArchiveLocationError",
    "resolve_evidence_archive_location",
]
