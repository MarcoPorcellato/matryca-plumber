"""Bounded source-identity checks for requested Shadow page rows."""

from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path

from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root


class ShadowFreshnessReason(StrEnum):
    PAGE_UNTRACKED = "page_untracked"
    SOURCE_MISSING = "source_missing"
    SOURCE_CHANGED = "source_changed"
    EMPTY_RESULT_UNPROVEN = "empty_result_unproven"


class ShadowFreshnessError(RuntimeError):
    """Content-free signal that authoritative Markdown fallback is required."""

    def __init__(self, reason: ShadowFreshnessReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def ensure_shadow_page_fresh(
    connection: sqlite3.Connection,
    graph_root: Path | str,
    *,
    page_id: int | None = None,
    title: str | None = None,
) -> None:
    """Validate one requested row using stored size and nanosecond mtime."""
    if page_id is not None:
        row = connection.execute(
            "SELECT file_path, file_mtime_ns, file_size FROM pages WHERE page_id = ?",
            (page_id,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT file_path, file_mtime_ns, file_size FROM pages WHERE title = ?",
            ((title or "").strip(),),
        ).fetchone()
    if row is None:
        raise ShadowFreshnessError(ShadowFreshnessReason.PAGE_UNTRACKED)

    root = resolved_graph_root(graph_root)
    path = assert_path_within_graph(root / str(row[0]), root)
    try:
        current = path.stat()
    except OSError as exc:
        raise ShadowFreshnessError(ShadowFreshnessReason.SOURCE_MISSING) from exc
    if current.st_mtime_ns != int(row[1]) or current.st_size != int(row[2]):
        raise ShadowFreshnessError(ShadowFreshnessReason.SOURCE_CHANGED)


__all__ = [
    "ShadowFreshnessError",
    "ShadowFreshnessReason",
    "ensure_shadow_page_fresh",
]
