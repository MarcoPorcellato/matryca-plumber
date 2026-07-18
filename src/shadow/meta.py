"""``shadow_meta`` key contract for Shadow DB health and reconciliation (v2 PR-0)."""

from __future__ import annotations

import sqlite3

from .schema import SHADOW_SCHEMA_VERSION

META_SCHEMA_VERSION = "schema_version"
META_GENERATION = "generation"
META_LAST_FULL_SYNC_AT = "last_full_sync_at"
META_LAST_FULL_SYNC_COMPLETED = "last_full_sync_completed"
META_SOURCE_PAGE_COUNT = "source_page_count"
META_INDEXED_PAGE_COUNT = "indexed_page_count"
META_LAST_SYNC_ERROR = "last_sync_error"
META_LAST_INCREMENTAL_SYNC_AT = "last_incremental_sync_at"

REQUIRED_META_KEYS: tuple[str, ...] = (
    META_SCHEMA_VERSION,
    META_GENERATION,
    META_LAST_FULL_SYNC_AT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_SOURCE_PAGE_COUNT,
    META_INDEXED_PAGE_COUNT,
    META_LAST_SYNC_ERROR,
    META_LAST_INCREMENTAL_SYNC_AT,
)


def get_meta(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute(
        "SELECT value FROM shadow_meta WHERE key = ?",
        (key,),
    ).fetchone()
    return None if row is None else str(row[0])


def set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO shadow_meta (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def ensure_meta_defaults(connection: sqlite3.Connection) -> None:
    """Ensure required keys exist (empty string when unset)."""
    for key in REQUIRED_META_KEYS:
        connection.execute(
            "INSERT OR IGNORE INTO shadow_meta (key, value) VALUES (?, ?)",
            (key, ""),
        )
    set_meta(connection, META_SCHEMA_VERSION, str(SHADOW_SCHEMA_VERSION))


def read_meta_map(connection: sqlite3.Connection) -> dict[str, str]:
    ensure_meta_defaults(connection)
    rows = connection.execute("SELECT key, value FROM shadow_meta").fetchall()
    return {str(key): str(value) for key, value in rows}


def current_generation(connection: sqlite3.Connection) -> int:
    raw = get_meta(connection, META_GENERATION)
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0


def bump_generation(connection: sqlite3.Connection) -> int:
    generation = current_generation(connection) + 1
    set_meta(connection, META_GENERATION, str(generation))
    return generation


__all__ = [
    "META_GENERATION",
    "META_INDEXED_PAGE_COUNT",
    "META_LAST_FULL_SYNC_AT",
    "META_LAST_FULL_SYNC_COMPLETED",
    "META_LAST_INCREMENTAL_SYNC_AT",
    "META_LAST_SYNC_ERROR",
    "META_SCHEMA_VERSION",
    "META_SOURCE_PAGE_COUNT",
    "REQUIRED_META_KEYS",
    "bump_generation",
    "current_generation",
    "ensure_meta_defaults",
    "get_meta",
    "read_meta_map",
    "set_meta",
]
