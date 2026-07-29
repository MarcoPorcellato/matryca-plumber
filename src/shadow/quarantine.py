"""Per-page quarantine for the Shadow read cache (v2.0).

A page whose bounded parse cannot complete within the budget is *parked* rather than
allowed to abort the whole rebuild. Quarantine is deliberately a separate table from
``pages``: an entry here means the page is **absent** from the cache, so every existing
``pages`` query, FTS trigger, and subtree CTE keeps its exact prior meaning and reads
for that page route to Markdown, which stays authoritative.

Rows are content-free. Only the graph-relative file path — already stored in
``pages.file_path`` — plus size and timing counters are persisted. No page title, no
absolute path, no block identifier, no content hash.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

QuarantineReason = Literal["parse_timeout", "parse_error"]

_VALID_REASONS: frozenset[str] = frozenset({"parse_timeout", "parse_error"})


def normalize_quarantine_reason(raw: str | None) -> QuarantineReason:
    """Map an arbitrary parse-failure category onto the closed reason vocabulary."""
    text = (raw or "").strip().lower()
    if text == "timeout":
        return "parse_timeout"
    if text in _VALID_REASONS:
        return text  # type: ignore[return-value]
    return "parse_error"


def record_quarantined_page(
    connection: sqlite3.Connection,
    file_path: str,
    *,
    reason: QuarantineReason,
    byte_count: int,
    line_count: int,
    now: str,
) -> None:
    """Park a page, or record another failed attempt if it is already quarantined."""
    connection.execute(
        """
        INSERT INTO quarantined_pages (
            file_path, reason, byte_count, line_count,
            attempt_count, first_quarantined_at, last_attempt_at
        )
        VALUES (?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            reason = excluded.reason,
            byte_count = excluded.byte_count,
            line_count = excluded.line_count,
            attempt_count = quarantined_pages.attempt_count + 1,
            last_attempt_at = excluded.last_attempt_at
        """,
        (file_path, reason, max(0, byte_count), max(0, line_count), now, now),
    )


def clear_quarantined_page(connection: sqlite3.Connection, file_path: str) -> None:
    """Release a page from quarantine after it parses successfully again."""
    connection.execute("DELETE FROM quarantined_pages WHERE file_path = ?", (file_path,))


def is_page_quarantined(connection: sqlite3.Connection, file_path: str) -> bool:
    """Return whether reads for this page must fall back to Markdown."""
    row = connection.execute(
        "SELECT 1 FROM quarantined_pages WHERE file_path = ? LIMIT 1", (file_path,)
    ).fetchone()
    return row is not None


def quarantined_page_count(connection: sqlite3.Connection) -> int:
    """Return how many pages are currently parked outside the cache."""
    row = connection.execute("SELECT COUNT(*) FROM quarantined_pages").fetchone()
    return int(row[0]) if row else 0


def quarantined_file_paths(connection: sqlite3.Connection) -> list[str]:
    """Return the graph-relative paths of every quarantined page, sorted."""
    rows = connection.execute(
        "SELECT file_path FROM quarantined_pages ORDER BY file_path"
    ).fetchall()
    return [str(row[0]) for row in rows]


__all__ = [
    "QuarantineReason",
    "clear_quarantined_page",
    "is_page_quarantined",
    "normalize_quarantine_reason",
    "quarantined_file_paths",
    "quarantined_page_count",
    "record_quarantined_page",
]
