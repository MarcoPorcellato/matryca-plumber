"""FTS5 query helpers for ``shadow.sqlite`` (v2 Phase 2; not wired to dispatch yet)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BlockHit:
    """One FTS5 match from the shadow read cache."""

    block_uuid: str
    content: str
    page_id: int
    rank: float


def search_blocks_fts(
    connection: sqlite3.Connection,
    query: str,
    *,
    limit: int = 20,
) -> list[BlockHit]:
    """Return blocks matching ``query`` via FTS5 ``MATCH``, ordered by BM25 rank.

    ``query`` is passed as a bound parameter to ``blocks_fts MATCH ?``. Callers
    should supply FTS5 query syntax (plain tokens are fine for simple search).
    Empty / whitespace-only queries return an empty list.
    """
    q = query.strip()
    if not q:
        return []
    capped = max(1, min(int(limit), 500))
    rows = connection.execute(
        """
        SELECT b.block_uuid, b.content, b.page_id, bm25(blocks_fts) AS rank
        FROM blocks_fts
        JOIN blocks AS b ON b.rowid = blocks_fts.rowid
        WHERE blocks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (q, capped),
    ).fetchall()
    return [
        BlockHit(
            block_uuid=str(row[0]),
            content=str(row[1]),
            page_id=int(row[2]),
            rank=float(row[3]),
        )
        for row in rows
    ]


__all__ = [
    "BlockHit",
    "search_blocks_fts",
]
