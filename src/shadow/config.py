"""Environment-driven configuration for the Shadow DB read cache (v2 Phase 3)."""

from __future__ import annotations

from ..utils.env_parse import env_bool, env_int_clamped

_SHADOW_BUSY_TIMEOUT_MS_MIN = 0
_SHADOW_BUSY_TIMEOUT_MS_MAX = 60_000
_SHADOW_BUSY_TIMEOUT_MS_DEFAULT = 5_000

_SHADOW_WRITER_LOCK_TIMEOUT_S_MIN = 1
_SHADOW_WRITER_LOCK_TIMEOUT_S_MAX = 300
_SHADOW_WRITER_LOCK_TIMEOUT_S_DEFAULT = 10

_SHADOW_REBUILD_LOCK_TIMEOUT_S_MIN = 1
_SHADOW_REBUILD_LOCK_TIMEOUT_S_MAX = 600
_SHADOW_REBUILD_LOCK_TIMEOUT_S_DEFAULT = 120


def shadow_db_enabled() -> bool:
    """Return whether the Shadow DB subsystem is enabled (opt-in alpha).

    When false or unset, callers must not create, sync, or read ``shadow.sqlite``.
    """
    return env_bool("MATRYCA_SHADOW_DB_ENABLED", default=False)


def shadow_quarantine_enabled() -> bool:
    """Return whether over-budget pages are quarantined instead of failing the rebuild.

    Nested inside ``MATRYCA_SHADOW_DB_ENABLED``: it has no effect while the Shadow DB
    itself is off, so it cannot change behaviour for a default install. Defaults to
    true because the strict alternative makes one pathological page disable the read
    cache for an entire graph. Set it false to restore the pre-quarantine behaviour
    where any over-budget page aborts the whole rebuild.
    """
    return env_bool("MATRYCA_SHADOW_QUARANTINE_ENABLED", default=True)


def shadow_db_busy_timeout_ms() -> int:
    """SQLite ``busy_timeout`` for shadow connections (0 disables waiting)."""
    return env_int_clamped(
        "MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS",
        _SHADOW_BUSY_TIMEOUT_MS_DEFAULT,
        minimum=_SHADOW_BUSY_TIMEOUT_MS_MIN,
        maximum=_SHADOW_BUSY_TIMEOUT_MS_MAX,
    )


def shadow_writer_lock_timeout_s() -> float:
    """Maximum wait for incremental shadow writer flock (post-write / watchdog)."""
    return float(
        env_int_clamped(
            "MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S",
            _SHADOW_WRITER_LOCK_TIMEOUT_S_DEFAULT,
            minimum=_SHADOW_WRITER_LOCK_TIMEOUT_S_MIN,
            maximum=_SHADOW_WRITER_LOCK_TIMEOUT_S_MAX,
        )
    )


def shadow_rebuild_lock_timeout_s() -> float:
    """Maximum wait for full rebuild flock (daemon bootstrap; may scan large vaults)."""
    return float(
        env_int_clamped(
            "MATRYCA_SHADOW_REBUILD_LOCK_TIMEOUT_S",
            _SHADOW_REBUILD_LOCK_TIMEOUT_S_DEFAULT,
            minimum=_SHADOW_REBUILD_LOCK_TIMEOUT_S_MIN,
            maximum=_SHADOW_REBUILD_LOCK_TIMEOUT_S_MAX,
        )
    )


__all__ = [
    "shadow_db_busy_timeout_ms",
    "shadow_db_enabled",
    "shadow_quarantine_enabled",
    "shadow_rebuild_lock_timeout_s",
    "shadow_writer_lock_timeout_s",
]
