"""Cross-process advisory lock for all Matryca shadow.sqlite writers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..graph.path_sandbox import PathTraversalSecurityError, resolved_graph_root
from ..utils.platform_lock import cross_process_sidecar_lock
from .cache_location import (
    ShadowCacheLocationError,
    resolve_shadow_cache_location,
)
from .config import shadow_rebuild_lock_timeout_s, shadow_writer_lock_timeout_s


def _writer_lock_depth_key(lock_path: Path) -> str:
    """Thread-local reentrancy key scoped to the resolved lock path."""
    return str(lock_path.expanduser().resolve(strict=False))


def shadow_writer_lock_path(graph_root: Path | str) -> Path:
    """Return the typed sidecar flock path for this graph's shadow cache."""
    root = resolved_graph_root(graph_root)
    try:
        location = resolve_shadow_cache_location(root)
    except ShadowCacheLocationError as exc:
        raise PathTraversalSecurityError(str(exc)) from exc
    return location.writer_lock_path


@contextmanager
def shadow_writer_lock(graph_root: Path | str) -> Iterator[None]:
    """Serialize incremental sync/delete writers for one graph root."""
    lock_path = shadow_writer_lock_path(graph_root)
    with cross_process_sidecar_lock(
        lock_path,
        depth_key=_writer_lock_depth_key(lock_path),
        unavailable_label="shadow writer lock",
        max_wait_s=shadow_writer_lock_timeout_s(),
    ):
        yield


@contextmanager
def shadow_rebuild_lock(graph_root: Path | str) -> Iterator[None]:
    """Serialize full rebuild writers (longer default timeout than incremental)."""
    lock_path = shadow_writer_lock_path(graph_root)
    with cross_process_sidecar_lock(
        lock_path,
        depth_key=_writer_lock_depth_key(lock_path),
        unavailable_label="shadow rebuild lock",
        max_wait_s=shadow_rebuild_lock_timeout_s(),
    ):
        yield


__all__ = [
    "shadow_rebuild_lock",
    "shadow_writer_lock",
    "shadow_writer_lock_path",
]
