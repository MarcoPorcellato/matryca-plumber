"""FTS5 markdown formatter and ``search_graph(bm25)`` routing (v2 PR-B / #250)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from loguru import logger

from ..graph.path_sandbox import resolved_graph_root
from ..rag.local_query import format_keyword_query_markdown
from .config import shadow_db_enabled
from .connection import open_shadow_db_query_only
from .freshness import (
    ShadowFreshnessError,
    ShadowFreshnessReason,
    ensure_shadow_page_fresh,
)
from .fts_validation import (
    _FTS_VALIDATION_PREFIX,
    MAX_FTS_MATCH_QUERY_CHARS,
    FtsQueryValidationError,
    check_fts_query_length_bounded,
    validate_fts_match_query,
)
from .health import ShadowHealthState, resolve_shadow_health
from .query import BlockHit, search_blocks_fts


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
    conn = open_shadow_db_query_only(root)
    try:
        try:
            hits = search_blocks_fts(conn, keyword, limit=limit)
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if any(
                fragment in msg
                for fragment in (
                    "syntax",
                    "no such column",
                    "unknown special query",
                )
            ):
                raise FtsQueryValidationError(
                    f"{_FTS_VALIDATION_PREFIX}: {keyword!r} is not valid FTS5 syntax."
                ) from exc
            raise
        page_rows = _page_rows_for_hits(conn, hits)
        if not hits:
            raise ShadowFreshnessError(ShadowFreshnessReason.EMPTY_RESULT_UNPROVEN)
        for page_id in page_rows:
            ensure_shadow_page_fresh(conn, root, page_id=page_id)
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
        except ShadowFreshnessError as exc:
            logger.bind(reason=exc.reason.value).info(
                "Shadow FTS freshness unproven; falling back to generational BM25"
            )
            fallback = format_keyword_query_markdown(root, keyword, limit=limit, mode="bm25")
            return f"{fallback.rstrip()}\n\n- **Shadow fallback:** `{exc.reason.value}`\n"
        except Exception:  # noqa: BLE001 — shadow backend failure → v1 fallback
            logger.exception("Shadow FTS search failed; falling back to generational BM25")
    return format_keyword_query_markdown(root, keyword, limit=limit, mode="bm25")


__all__ = [
    "FtsQueryValidationError",
    "MAX_FTS_MATCH_QUERY_CHARS",
    "check_fts_query_length_bounded",
    "format_shadow_fts_markdown",
    "resolve_bm25_search_markdown",
    "validate_fts_match_query",
]
