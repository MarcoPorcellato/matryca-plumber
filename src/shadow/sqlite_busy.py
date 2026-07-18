"""SQLite contention helpers for shadow.sqlite writers."""

from __future__ import annotations

import sqlite3


def is_sqlite_locked_error(exc: BaseException) -> bool:
    """Return whether ``exc`` indicates transient writer contention."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).casefold()
    return "database is locked" in message or "database is busy" in message


def is_sqlite_corruption_error(exc: BaseException) -> bool:
    """Return whether ``exc`` indicates schema or file corruption (not contention)."""
    if isinstance(exc, sqlite3.DatabaseError) and not isinstance(exc, sqlite3.OperationalError):
        return True
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).casefold()
    if is_sqlite_locked_error(exc):
        return False
    return any(
        token in message
        for token in (
            "malformed",
            "corrupt",
            "no such table",
            "no such column",
            "schema",
        )
    )


def format_sqlite_busy_error(graph_root: str, *, waited_ms: int) -> str:
    """Bounded diagnostic when shadow.sqlite stays busy past ``busy_timeout``."""
    return f"shadow.sqlite busy after {waited_ms}ms for {graph_root}"


__all__ = [
    "format_sqlite_busy_error",
    "is_sqlite_corruption_error",
    "is_sqlite_locked_error",
]
