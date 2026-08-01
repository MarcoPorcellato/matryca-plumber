"""Resolve the v2 RC Shadow DB cache outside the authoritative Logseq graph."""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from ..graph.safety.write_policy import GraphReadOnlyError, RuntimeWritePolicy

_APP_CACHE_DIRNAME = "matryca-plumber"
_GRAPH_CACHE_DIRNAME = "graphs"
_GRAPH_ID_VERSION = "v1"
_SHADOW_DIRNAME = "shadow"
_SHADOW_DB_FILENAME = "shadow.sqlite"
_SHADOW_WRITER_LOCK_FILENAME = "shadow.writer.flock"
_LEGACY_CACHE_DIRNAME = ".matryca_semantic_cache"


class ShadowCacheLocationError(ValueError):
    """A content-free failure to resolve a safe external Shadow cache location."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Shadow cache location unavailable ({reason})")


@dataclass(frozen=True, slots=True)
class ShadowCacheLocation:
    """Canonical external paths owned by one graph's Shadow runtime."""

    graph_root: Path
    cache_root: Path
    graph_id: str
    shadow_dir: Path
    database_path: Path
    writer_lock_path: Path

    @property
    def shadow_db_wal_path(self) -> Path:
        """SQLite WAL sidecar path for this graph's Shadow DB."""

        return self.database_path.with_name(f"{self.database_path.name}-wal")

    @property
    def shadow_db_shm_path(self) -> Path:
        """SQLite SHM sidecar path for this graph's Shadow DB."""

        return self.database_path.with_name(f"{self.database_path.name}-shm")

    def ensure_directory(self) -> Path:
        """Create the private Shadow directory after revalidating containment."""
        directories = (
            self.cache_root,
            self.cache_root / _GRAPH_CACHE_DIRNAME,
            self.shadow_dir.parent,
            self.shadow_dir,
        )
        for directory in directories:
            resolved = directory.resolve(strict=False)
            if resolved != self.cache_root and not resolved.is_relative_to(self.cache_root):
                raise ShadowCacheLocationError("shadow_directory_escape")
            resolved.mkdir(mode=0o700, exist_ok=True)
            if os.name == "posix":
                try:
                    resolved.chmod(0o700)
                except OSError as exc:
                    raise ShadowCacheLocationError("shadow_directory_permissions") from exc
        return self.shadow_dir


def _canonical_graph_identity(graph_root: Path, *, platform_name: str) -> str:
    canonical = str(graph_root)
    if platform_name == "win32":
        canonical = os.path.normcase(canonical).casefold()
    digest = hashlib.sha256(canonical.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"{_GRAPH_ID_VERSION}-{digest[:32]}"


def _default_cache_root(
    env: Mapping[str, str],
    *,
    platform_name: str,
    home: Path,
) -> Path:
    if platform_name == "darwin":
        return home / "Library" / "Caches" / _APP_CACHE_DIRNAME
    if platform_name == "win32":
        local_app_data = (env.get("LOCALAPPDATA") or "").strip()
        base = Path(local_app_data) if local_app_data else home / "AppData" / "Local"
        return base / _APP_CACHE_DIRNAME / "Cache"
    xdg_cache = (env.get("XDG_CACHE_HOME") or "").strip()
    base = Path(xdg_cache) if xdg_cache else home / ".cache"
    return base / _APP_CACHE_DIRNAME


def resolve_shadow_cache_location(
    graph_root: Path | str,
    *,
    env: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
) -> ShadowCacheLocation:
    """Resolve safe, deterministic external paths without creating any file."""
    source = os.environ if env is None else env
    platform_value = sys.platform if platform_name is None else platform_name
    home_value = Path.home() if home is None else Path(home)
    root = resolved_graph_root(graph_root)

    override = (source.get("MATRYCA_CACHE_PATH") or "").strip()
    candidate = (
        Path(override).expanduser()
        if override
        else _default_cache_root(
            source,
            platform_name=platform_value,
            home=home_value.expanduser(),
        )
    )
    if not candidate.is_absolute():
        raise ShadowCacheLocationError("cache_root_not_absolute")
    if candidate.is_symlink():
        raise ShadowCacheLocationError("cache_root_symlink")

    try:
        policy = RuntimeWritePolicy(graph_root=root, cache_path=candidate)
    except GraphReadOnlyError as exc:
        raise ShadowCacheLocationError(exc.reason) from exc
    cache_root = policy.cache_path
    if cache_root is None:  # pragma: no cover - constructor input guarantees a path
        raise ShadowCacheLocationError("cache_root_missing")

    graph_id = _canonical_graph_identity(root, platform_name=platform_value)
    shadow_dir = (cache_root / _GRAPH_CACHE_DIRNAME / graph_id / _SHADOW_DIRNAME).resolve(
        strict=False
    )
    if not shadow_dir.is_relative_to(cache_root):
        raise ShadowCacheLocationError("shadow_directory_escape")

    database_candidate = shadow_dir / _SHADOW_DB_FILENAME
    if database_candidate.is_symlink():
        raise ShadowCacheLocationError("database_symlink")
    wal_candidate = database_candidate.with_name(f"{database_candidate.name}-wal")
    if wal_candidate.is_symlink():
        raise ShadowCacheLocationError("wal_symlink")
    shm_candidate = database_candidate.with_name(f"{database_candidate.name}-shm")
    if shm_candidate.is_symlink():
        raise ShadowCacheLocationError("shm_symlink")
    writer_lock_candidate = shadow_dir / _SHADOW_WRITER_LOCK_FILENAME
    if writer_lock_candidate.is_symlink():
        raise ShadowCacheLocationError("writer_lock_symlink")

    return ShadowCacheLocation(
        graph_root=root,
        cache_root=cache_root,
        graph_id=graph_id,
        shadow_dir=shadow_dir,
        database_path=database_candidate,
        writer_lock_path=writer_lock_candidate,
    )


def legacy_graph_local_shadow_db_path(graph_root: Path | str) -> Path:
    """Return the published-beta path for detection only; never migrate it in place."""
    root = resolved_graph_root(graph_root)
    return assert_path_within_graph(
        root / _LEGACY_CACHE_DIRNAME / _SHADOW_DB_FILENAME,
        root,
    )


__all__ = [
    "ShadowCacheLocation",
    "ShadowCacheLocationError",
    "legacy_graph_local_shadow_db_path",
    "resolve_shadow_cache_location",
]
