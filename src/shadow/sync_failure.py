"""Durable, content-free invalidation for failed Shadow synchronization."""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from .cache_location import ShadowCacheLocationError, resolve_shadow_cache_location
from .runtime_state import (
    clear_shadow_generation_invalid,
    is_shadow_generation_invalid,
    mark_shadow_generation_invalid,
)

SHADOW_SYNC_FAILURE_REASON = "incremental_sync_failed"
_FAILURE_MARKER_FILENAME = "shadow.sync-invalid"


def _marker_path(graph_root: Path | str) -> Path:
    location = resolve_shadow_cache_location(graph_root)
    return location.shadow_dir / _FAILURE_MARKER_FILENAME


def mark_shadow_sync_failed(graph_root: Path | str) -> None:
    """Latch failure in memory and best-effort persist it outside SQLite."""
    mark_shadow_generation_invalid(graph_root)
    try:
        location = resolve_shadow_cache_location(graph_root)
        location.ensure_directory()
        marker = location.shadow_dir / _FAILURE_MARKER_FILENAME
        if marker.is_symlink():
            raise ShadowCacheLocationError("sync_failure_marker_symlink")
        flags = os.O_CREAT | os.O_TRUNC | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(marker, flags, 0o600)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, 0o600)
            os.write(descriptor, SHADOW_SYNC_FAILURE_REASON.encode("ascii"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError, ShadowCacheLocationError):
        logger.warning("Failed to persist the content-free Shadow sync-failure marker")


def clear_shadow_sync_failed(graph_root: Path | str) -> bool:
    """Clear durable and in-process invalidation after full reconciliation."""
    try:
        marker = _marker_path(graph_root)
        marker.unlink(missing_ok=True)
    except (OSError, RuntimeError, ShadowCacheLocationError):
        logger.warning("Failed to clear the content-free Shadow sync-failure marker")
        return False
    clear_shadow_generation_invalid(graph_root)
    return True


def is_shadow_sync_failed(graph_root: Path | str) -> bool:
    """Return whether this process or the durable marker invalidates reads."""
    if is_shadow_generation_invalid(graph_root):
        return True
    try:
        marker = _marker_path(graph_root)
    except (OSError, RuntimeError, ShadowCacheLocationError):
        return False
    return marker.is_symlink() or marker.exists()


__all__ = [
    "SHADOW_SYNC_FAILURE_REASON",
    "clear_shadow_sync_failed",
    "is_shadow_sync_failed",
    "mark_shadow_sync_failed",
]
