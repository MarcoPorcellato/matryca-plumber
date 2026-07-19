"""FTS5 query helpers for ``shadow.sqlite`` (v2 Phase 2; not wired to dispatch yet)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

# ASCII hyphen + common Unicode dash code points (en/em/figure dashes).
_HYPHEN_DASH_CLASS = "-\u2010\u2011\u2012\u2013\u2014"
_FTS_RESERVED_TOKENS = frozenset({"OR", "AND", "NOT", "NEAR"})
_NATURAL_COMPOUND_TOKEN = re.compile(rf"^[A-Za-z0-9][A-Za-z0-9{_HYPHEN_DASH_CLASS}]*[A-Za-z0-9]$")


@dataclass(frozen=True, slots=True)
class BlockHit:
    """One FTS5 match from the shadow read cache."""

    block_uuid: str
    content: str
    page_id: int
    rank: float


def _quote_natural_hyphenated_token(token: str) -> str:
    """Quote a bare token that FTS5 would parse as boolean NOT chains."""
    prefix = ""
    suffix = ""
    core = token
    while core.startswith("("):
        prefix += "("
        core = core[1:]
    while core.endswith(")"):
        suffix = ")" + suffix
        core = core[:-1]
    if not core or core.upper() in _FTS_RESERVED_TOKENS:
        return token
    if core.startswith("-") or "*" in core:
        return token
    if not any(ch in _HYPHEN_DASH_CLASS for ch in core):
        return token
    if not _NATURAL_COMPOUND_TOKEN.match(core):
        return token
    escaped = core.replace('"', '""')
    return f'{prefix}"{escaped}"{suffix}'


def prepare_fts_user_query(query: str) -> str:
    """Prepare user keyword input for safe FTS5 ``MATCH`` binding.

    Natural compound tokens such as ``state-of-the-art`` are wrapped as phrase
    literals so FTS5 does not interpret interior hyphens as ``NOT``. Explicit
    quoted spans, boolean operators, prefix terms (``*``), and leading ``-``
    negation are left unchanged.
    """
    q = query.strip()
    if not q:
        return q
    parts: list[str] = []
    i = 0
    n = len(q)
    while i < n:
        while i < n and q[i].isspace():
            i += 1
        if i >= n:
            break
        if q[i] == '"':
            j = i + 1
            while j < n and q[j] != '"':
                j += 1
            end = j + 1 if j < n else n
            parts.append(q[i:end])
            i = end
        else:
            j = i
            while j < n and not q[j].isspace():
                j += 1
            parts.append(_quote_natural_hyphenated_token(q[i:j]))
            i = j
    return " ".join(parts)


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
    stripped = query.strip()
    if not stripped:
        return []
    from .fts_format import check_fts_query_length_bounded

    check_fts_query_length_bounded(stripped)
    q = prepare_fts_user_query(query)
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
    "prepare_fts_user_query",
    "search_blocks_fts",
]
