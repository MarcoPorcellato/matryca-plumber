"""FTS5 markdown formatter and ``search_graph(bm25)`` routing (v2 PR-B / #250)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from ..graph.path_sandbox import resolved_graph_root
from ..rag.local_query import format_keyword_query_markdown
from .config import shadow_db_enabled
from .connection import open_shadow_db
from .health import ShadowHealthState, resolve_shadow_health
from .query import BlockHit, search_blocks_fts

_FTS_VALIDATION_PREFIX = "Invalid FTS query for `method=bm25`"

# FTS5 reports an unrecognised bareword column filter (e.g. the ``-of`` / ``-the``
# fragments of ``state-of-the-art``, which it reads as NOT operators against a
# ``of``/``the`` column) as ``OperationalError: no such column: <name>``. This is
# neither an FTS5 *syntax* error nor a shadow backend failure, so it must not reach
# the generational fallback — the query is recoverable as a literal phrase.
_FTS_COLUMN_FILTER_MARKER = "no such column"


class FtsQueryValidationError(ValueError):
    """User-supplied keyword is not a valid FTS5 ``MATCH`` expression."""


def _as_fts_phrase(keyword: str) -> str:
    """Wrap ``keyword`` as a single FTS5 quoted phrase, escaping embedded quotes."""
    return '"' + keyword.strip().replace('"', '""') + '"'


def _search_blocks_fts_recovering(
    connection: sqlite3.Connection,
    keyword: str,
    *,
    limit: int,
) -> list[BlockHit]:
    """Run the FTS5 ``MATCH`` for ``keyword``, recovering misparsed bareword input.

    A user keyword such as ``state-of-the-art`` is a valid search intent but not a
    valid FTS5 expression: FTS5 reads the hyphenated fragments as column filters and
    raises ``no such column: of``. Rather than let that surface as a backend failure
    (which would silently fall back to generational BM25), retry the raw keyword as a
    quoted phrase so it matches the indexed content literally. Genuine syntax errors
    (e.g. a stray apostrophe) still raise :class:`FtsQueryValidationError`, and other
    ``OperationalError``\\ s (missing table, locked database) propagate unchanged.
    """
    try:
        return search_blocks_fts(connection, keyword, limit=limit)
    except sqlite3.OperationalError as exc:
        message = str(exc).lower()
        if "syntax" in message:
            raise FtsQueryValidationError(
                f"{_FTS_VALIDATION_PREFIX}: {keyword!r} is not valid FTS5 syntax."
            ) from exc
        if _FTS_COLUMN_FILTER_MARKER in message:
            try:
                return search_blocks_fts(connection, _as_fts_phrase(keyword), limit=limit)
            except sqlite3.OperationalError as retry_exc:
                raise FtsQueryValidationError(
                    f"{_FTS_VALIDATION_PREFIX}: {keyword!r} is not valid FTS5 syntax."
                ) from retry_exc
        raise


def validate_fts_match_query(keyword: str) -> None:
    """Reject obviously invalid FTS5 query syntax before hitting SQLite."""
    q = keyword.strip()
    if not q:
        raise FtsQueryValidationError(
            f"{_FTS_VALIDATION_PREFIX}: query is empty after trimming whitespace."
        )
    if q.count('"') % 2 != 0:
        raise FtsQueryValidationError(
            f"{_FTS_VALIDATION_PREFIX}: unbalanced double quotes in {q!r}."
        )


def _page_rows_for_hits(
    connection: sqlite3.Connection,
    hits: list[BlockHit],
) -> dict[int, tuple[str, str]]:
    page_ids = {hit.page_id for hit in hits}
    out: dict[int, tuple[str, str]] = {}
    for page_id in page_ids:
        row = connection.execute(
            "SELECT title, file_path FROM pages WHERE page_id = ?",
            (page_id,),
        ).fetchone()
        if row is not None:
            out[page_id] = (str(row[0]), str(row[1]))
    return out


def format_shadow_fts_markdown(
    graph_root: Path | str,
    keyword: str,
    *,
    limit: int = 15,
) -> str:
    """Format shadow FTS block hits using the BM25 search_graph markdown envelope."""
    validate_fts_match_query(keyword)
    root = resolved_graph_root(graph_root)
    conn = open_shadow_db(root)
    try:
        hits = _search_blocks_fts_recovering(conn, keyword, limit=limit)
        page_rows = _page_rows_for_hits(conn, hits)
    finally:
        conn.close()

    lines = [
        "# Local page query",
        "",
        f"- **Graph:** `{root}`",
        f"- **Query:** `{keyword.strip()}`",
        "- **Mode:** `bm25`",
        "",
        f"- **Matches:** {len(hits)}",
        "",
        "## Ranked pages (BM25)",
        "",
    ]
    if not hits:
        lines.append("_No lexical overlap in `pages/**/*.md`._")
        lines.append("")
        return "\n".join(lines)

    for hit in hits:
        title, rel = page_rows.get(hit.page_id, ("?", "?"))
        lines.append(f"- `{rel}` ({title}) — block `{hit.block_uuid}` — **{hit.rank:.4f}**")
        snippet = (hit.content or "").strip().replace("\n", " ")
        if snippet:
            lines.append(f"  > {snippet[:240]}")
    lines.append("")
    return "\n".join(lines)


def resolve_bm25_search_markdown(
    graph_root: Path | str,
    keyword: str,
    *,
    limit: int = 15,
) -> str:
    """Route to shadow FTS when enabled and ``ready``; else generational BM25.

    Validation errors from FTS syntax are returned to the caller (no BM25 fallback).
    Backend failures while shadow is ``ready`` fall back to generational BM25.
    """
    root = resolved_graph_root(graph_root)
    if shadow_db_enabled() and resolve_shadow_health(root) == ShadowHealthState.READY:
        try:
            return format_shadow_fts_markdown(root, keyword, limit=limit)
        except FtsQueryValidationError:
            raise
        except Exception:  # noqa: BLE001 — shadow backend failure → v1 fallback
            logger.exception("Shadow FTS search failed; falling back to generational BM25")
    return format_keyword_query_markdown(root, keyword, limit=limit, mode="bm25")


__all__ = [
    "FtsQueryValidationError",
    "format_shadow_fts_markdown",
    "resolve_bm25_search_markdown",
    "validate_fts_match_query",
]
