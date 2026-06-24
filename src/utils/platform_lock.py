"""Shared cross-process ``fcntl.flock`` sidecar locking (NB + backoff + degradation)."""

from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from loguru import logger

from ..graph.io_retry import (
    IO_RETRY_ATTEMPTS,
    IO_RETRY_INITIAL_DELAY_S,
    IO_RETRY_MAX_DELAY_S,
    PageLockUnavailableError,
)

_fcntl: Any
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows and other non-Unix platforms
    _fcntl = None

_flock_depth_local = threading.local()


def flock_degradation_allowed() -> bool:
    """Return whether flock failures may fall back to in-process-only coordination."""
    raw = os.environ.get("MATRYCA_ALLOW_FLOCK_DEGRADATION", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def flock_depths() -> dict[str, int]:
    """Per-thread reentrancy depth keyed by caller-supplied lock identity."""
    depths = getattr(_flock_depth_local, "depths", None)
    if depths is None:
        depths = {}
        _flock_depth_local.depths = depths
    return depths


def clear_flock_depths() -> None:
    """Reset thread-local flock depth tracking (tests)."""
    if hasattr(_flock_depth_local, "depths"):
        del _flock_depth_local.depths


def acquire_exclusive_flock(
    fd: int,
    lock_path: Path,
    *,
    unavailable_label: str = "sidecar lock",
) -> bool:
    """Acquire exclusive flock with exponential backoff.

    Returns:
        True when the OS flock is held on ``fd``.
        False when flock is unsupported and degradation is allowed.
    """
    if _fcntl is None:
        return False

    delay = IO_RETRY_INITIAL_DELAY_S
    for attempt in range(IO_RETRY_ATTEMPTS):
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if attempt >= IO_RETRY_ATTEMPTS - 1:
                logger.warning(
                    "{} sidecar contended after {} NB retries; blocking until free: {}",
                    unavailable_label,
                    IO_RETRY_ATTEMPTS - 1,
                    lock_path,
                )
                try:
                    _fcntl.flock(fd, _fcntl.LOCK_EX)
                    return True
                except OSError as exc:
                    if not flock_degradation_allowed():
                        raise PageLockUnavailableError(
                            f"Could not acquire {unavailable_label} for {lock_path}: {exc}",
                        ) from exc
                    logger.info(
                        "[LOCK FILE SYSTEM DEGRADATION] Shared process lock not supported by "
                        "filesystem ({}), falling back to in-process coordination for {}.",
                        exc,
                        lock_path,
                    )
                    return False
            time.sleep(min(IO_RETRY_MAX_DELAY_S, delay))
            delay = min(IO_RETRY_MAX_DELAY_S, delay * 2)
        except OSError as exc:
            if not flock_degradation_allowed():
                raise PageLockUnavailableError(
                    f"Cross-process {unavailable_label} unavailable for {lock_path}: {exc}",
                ) from exc
            logger.info(
                "[LOCK FILE SYSTEM DEGRADATION] Shared process lock not supported by "
                "filesystem ({}), falling back to in-process coordination for {}.",
                exc,
                lock_path,
            )
            return False
    return False


def probe_exclusive_flock(
    lock_path: Path,
    *,
    unavailable_label: str = "sidecar lock",
) -> None:
    """Verify a sidecar flock can be acquired (single NB attempt, no hold)."""
    if _fcntl is None:
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PageLockUnavailableError(
                f"Could not probe cross-process {unavailable_label} for {lock_path}",
            ) from exc
        except OSError as exc:
            if not flock_degradation_allowed():
                raise PageLockUnavailableError(
                    f"Cross-process {unavailable_label} unavailable for {lock_path}: {exc}",
                ) from exc
            return
        with suppress(OSError):
            _fcntl.flock(fd, _fcntl.LOCK_UN)
    finally:
        os.close(fd)


@contextmanager
def cross_process_sidecar_lock(
    lock_path: Path,
    *,
    depth_key: str,
    unavailable_label: str = "sidecar lock",
) -> Iterator[None]:
    """Hold an exclusive cross-process flock on ``lock_path`` with reentrancy depth tracking."""
    depths = flock_depths()
    nested = depths.get(depth_key, 0)
    if nested > 0:
        depths[depth_key] = nested + 1
        try:
            yield
        finally:
            depths[depth_key] -= 1
        return

    if _fcntl is None:
        depths[depth_key] = 1
        try:
            yield
        finally:
            depths.pop(depth_key, None)
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        acquired = acquire_exclusive_flock(
            fd,
            lock_path,
            unavailable_label=unavailable_label,
        )
        if not acquired and not flock_degradation_allowed():
            raise PageLockUnavailableError(
                f"Could not acquire cross-process {unavailable_label} for {lock_path}",
            )
        if not acquired:
            depths[depth_key] = 1
            try:
                yield
            finally:
                depths.pop(depth_key, None)
            return
        depths[depth_key] = 1
        try:
            yield
        finally:
            depths.pop(depth_key, None)
            with suppress(OSError):
                _fcntl.flock(fd, _fcntl.LOCK_UN)
    finally:
        os.close(fd)


def flock_available() -> bool:
    """Return whether OS-level ``fcntl.flock`` is available on this platform."""
    return _fcntl is not None and sys.platform != "win32"


__all__ = [
    "acquire_exclusive_flock",
    "flock_available",
    "clear_flock_depths",
    "cross_process_sidecar_lock",
    "flock_degradation_allowed",
    "flock_depths",
    "probe_exclusive_flock",
]
