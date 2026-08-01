"""Cross-process exclusive flock for JSON checkpoint files."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ..utils.platform_lock import cross_process_sidecar_lock
from .safety.write_policy import GraphReadOnlyError, guard_graph_mutation


def flock_sidecar_path(target: Path) -> Path:
    """Return a sidecar lock path adjacent to ``target``."""
    return target.parent / f".{target.name}.flock"


@contextmanager
def cross_process_json_flock(target: Path) -> Iterator[None]:
    """Hold an exclusive flock for one JSON read/write critical section."""
    lock_path = flock_sidecar_path(target)
    depth_key = str(lock_path.expanduser().resolve(strict=False))
    with cross_process_sidecar_lock(
        lock_path,
        depth_key=depth_key,
        unavailable_label="JSON sidecar lock",
    ):
        yield


@contextmanager
def cross_process_json_read_flock(target: Path, *, graph_root: Path) -> Iterator[None]:
    """Lock a JSON read without creating a graph-local sidecar in read-only mode."""
    lock_path = flock_sidecar_path(target)
    try:
        guard_graph_mutation(graph_root, lock_path, operation="acquire_json_read_lock")
    except GraphReadOnlyError:
        yield
        return
    with cross_process_json_flock(target):
        yield


__all__ = ["cross_process_json_flock", "cross_process_json_read_flock", "flock_sidecar_path"]
