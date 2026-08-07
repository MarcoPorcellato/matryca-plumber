"""Restrict optional config and log paths to the graph root or user home."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _graph_root_candidate() -> Path | None:
    raw = os.environ.get("LOGSEQ_GRAPH_PATH", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve(strict=False)


def _allowed_roots(*, graph_root: Path | None = None) -> list[Path]:
    roots: list[Path] = [Path.home().resolve(), Path(tempfile.gettempdir()).resolve()]
    if graph_root is not None:
        roots.insert(0, graph_root.resolve(strict=False))
    else:
        candidate = _graph_root_candidate()
        if candidate is not None:
            roots.insert(0, candidate)
    repo = Path(__file__).resolve().parents[2]
    if repo.is_dir():
        roots.append(repo.resolve(strict=False))
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def is_path_under_allowed_roots(path: Path, *, graph_root: Path | None = None) -> bool:
    """Return whether ``path`` resolves under graph root, repo, home, or temp."""
    resolved = path.expanduser().resolve(strict=False)
    for root in _allowed_roots(graph_root=graph_root):
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def resolve_optional_path_under_allowed_roots(
    raw: str,
    *,
    graph_root: Path | None = None,
    must_exist: bool = False,
) -> Path | None:
    """Resolve ``raw`` when it lies under allowed roots; otherwise return ``None``."""
    cleaned = raw.strip()
    if not cleaned:
        return None
    path = Path(cleaned).expanduser()
    if not is_path_under_allowed_roots(path, graph_root=graph_root):
        return None
    resolved = path.resolve(strict=False)
    if must_exist and not resolved.exists():
        return None
    return resolved


_DEFAULT_OPS_LOG = Path("logs") / "matryca_plumber_ops.log"
_DEFAULT_LOGURU_LOG = Path("logs") / "matryca_plumber.log"


def resolve_plumber_log_path(raw: str | None = None) -> Path:
    """Resolve ops/log paths under allowed roots; fall back to repo ``logs/``."""
    if raw is None:
        raw = os.environ.get("MATRYCA_PLUMBER_LOG_PATH", "").strip()
    if raw:
        allowed = resolve_optional_path_under_allowed_roots(raw)
        if allowed is not None:
            return _read_only_safe_log_path(allowed)
    if _DEFAULT_OPS_LOG.is_absolute():
        return _DEFAULT_OPS_LOG
    return _read_only_safe_log_path(Path(__file__).resolve().parents[2] / _DEFAULT_OPS_LOG)


def _read_only_safe_log_path(path: Path) -> Path:
    """Redirect a graph-local log target to this graph's external runtime cache."""
    graph_root = _graph_root_candidate()
    if graph_root is None:
        return path

    from ..graph.safety.write_policy import GraphReadOnlyError, RuntimeWritePolicy

    policy = RuntimeWritePolicy.from_env(graph_root)
    if not policy.read_only:
        return path
    try:
        return policy.ensure_write_allowed(path, operation="create_log_path")
    except GraphReadOnlyError as exc:
        if exc.reason != "graph_root_mutation_blocked":
            raise

    from ..shadow.cache_location import resolve_shadow_cache_location

    location = resolve_shadow_cache_location(policy.graph_root)
    external_path = location.shadow_dir.parent / "logs" / path.name
    return policy.ensure_write_allowed(external_path, operation="create_log_path")


def graph_config_allowed_roots() -> list[Path]:
    """Roots permitted for ``LOGSEQ_GRAPH_PATH`` updates via UI or ``.env`` writes."""
    roots: list[Path] = [
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
    ]
    repo = Path(__file__).resolve().parents[2]
    if repo.is_dir():
        roots.append(repo.resolve(strict=False))
    candidate = _graph_root_candidate()
    if candidate is not None:
        roots.append(candidate)
    extra = os.environ.get("MATRYCA_ALLOWED_GRAPH_ROOTS", "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            cleaned = part.strip()
            if cleaned:
                roots.append(Path(cleaned).expanduser().resolve(strict=False))
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def assert_graph_path_allowed_for_config(path: Path) -> None:
    """Raise ``ValueError`` when ``path`` is outside :func:`graph_config_allowed_roots`."""
    resolved = path.expanduser().resolve(strict=False)
    for root in graph_config_allowed_roots():
        try:
            resolved.relative_to(root)
            return
        except ValueError:
            continue
    msg = (
        "LOGSEQ_GRAPH_PATH must lie under your home directory, the Matryca repo, "
        "the current graph path, or a path listed in MATRYCA_ALLOWED_GRAPH_ROOTS"
    )
    raise ValueError(msg)


def ensure_plumber_log_directories() -> tuple[Path, Path]:
    """Create parent directories for ops JSONL and Loguru log files (idempotent)."""
    ops_path = resolve_plumber_log_path()
    loguru_path = resolve_loguru_log_path()
    ops_path.parent.mkdir(parents=True, exist_ok=True)
    loguru_path.parent.mkdir(parents=True, exist_ok=True)
    return ops_path, loguru_path


def resolve_loguru_log_path(raw: str | None = None) -> Path:
    """Resolve Loguru log paths under allowed roots; fall back to repo ``logs/``."""
    if raw is None:
        raw = os.environ.get("MATRYCA_LOGURU_LOG_PATH", "").strip()
    if raw:
        allowed = resolve_optional_path_under_allowed_roots(raw)
        if allowed is not None:
            return _read_only_safe_log_path(allowed)
    if _DEFAULT_LOGURU_LOG.is_absolute():
        return _DEFAULT_LOGURU_LOG
    return _read_only_safe_log_path(Path(__file__).resolve().parents[2] / _DEFAULT_LOGURU_LOG)


__all__ = [
    "assert_graph_path_allowed_for_config",
    "ensure_plumber_log_directories",
    "graph_config_allowed_roots",
    "is_path_under_allowed_roots",
    "resolve_loguru_log_path",
    "resolve_optional_path_under_allowed_roots",
    "resolve_plumber_log_path",
]
