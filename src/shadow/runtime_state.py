"""In-process Shadow DB coordination (rebuild locks, deferrals)."""

from __future__ import annotations

import threading
from collections import defaultdict
from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root

_rebuild_locks: dict[str, threading.Lock] = {}
_bootstrapping_roots: set[str] = set()
_deferred_sync_paths: dict[str, set[str]] = defaultdict(set)
_state_lock = threading.Lock()


def graph_root_key(graph_root: Path | str) -> str:
    return str(resolved_graph_root(graph_root))


def rebuild_lock_for(graph_root: Path | str) -> threading.Lock:
    key = graph_root_key(graph_root)
    with _state_lock:
        return _rebuild_locks.setdefault(key, threading.Lock())


def is_shadow_bootstrapping(graph_root: Path | str) -> bool:
    return graph_root_key(graph_root) in _bootstrapping_roots


def mark_bootstrapping(graph_root: Path | str) -> None:
    with _state_lock:
        _bootstrapping_roots.add(graph_root_key(graph_root))


def clear_bootstrapping(graph_root: Path | str) -> None:
    with _state_lock:
        _bootstrapping_roots.discard(graph_root_key(graph_root))


def defer_sync_path(graph_root: Path | str, rel_path: str) -> None:
    with _state_lock:
        _deferred_sync_paths[graph_root_key(graph_root)].add(rel_path)


def pop_deferred_sync_paths(graph_root: Path | str) -> list[str]:
    with _state_lock:
        key = graph_root_key(graph_root)
        paths = sorted(_deferred_sync_paths.pop(key, set()))
        return paths


def reset_shadow_runtime_state_for_tests() -> None:
    with _state_lock:
        _rebuild_locks.clear()
        _bootstrapping_roots.clear()
        _deferred_sync_paths.clear()


__all__ = [
    "clear_bootstrapping",
    "defer_sync_path",
    "graph_root_key",
    "is_shadow_bootstrapping",
    "mark_bootstrapping",
    "pop_deferred_sync_paths",
    "rebuild_lock_for",
    "reset_shadow_runtime_state_for_tests",
]
