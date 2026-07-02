"""``search_graph`` handlers — one function per ``SearchGraphMethod`` (issue #59 slice)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from ..graph.journal_task_scan import (
    format_journal_task_review_markdown,
    scan_journal_tasks,
)
from ..graph.unlinked_mentions import resolve_unlinked_mentions as scan_unlinked_mentions
from ..rag.local_query import format_keyword_query_markdown
from .graph_tool_helpers import (
    SearchGraphMethod,
    bounded_int_from_options,
    format_regex_search_markdown,
    graph_missing_dict,
    graph_missing_text,
    graph_path_from_env,
    parse_optional_json_query,
)

SearchHandler = Callable[[str, str], Awaitable[str | dict[str, Any]]]


async def handle_search_bm25(graph_path: str, query: str) -> str:
    bm_opts = parse_optional_json_query(query)
    keyword = str(bm_opts.get("keyword", query)).strip()
    if not keyword:
        return "For `method=bm25`, set `query` to search keywords or JSON with `keyword`."
    limit_raw = bounded_int_from_options(
        bm_opts,
        "limit",
        default=15,
        minimum=1,
        maximum=100,
    )
    if isinstance(limit_raw, str):
        return limit_raw
    limit = limit_raw
    return await asyncio.to_thread(
        format_keyword_query_markdown,
        graph_path,
        keyword,
        limit=limit,
        mode="bm25",
    )


async def handle_search_semantic(graph_path: str, query: str) -> str:
    sem_opts = parse_optional_json_query(query)
    sem_query = str(sem_opts.get("query", sem_opts.get("keyword", query))).strip()
    if not sem_query:
        return (
            "For `method=semantic`, set `query` to natural language or JSON "
            'with `"query": "..."`. Requires MATRYCA_DUAL_EMBEDDING_ENABLED=true '
            "and daemon-indexed block vectors."
        )
    sem_limit_raw = bounded_int_from_options(
        sem_opts,
        "limit",
        default=15,
        minimum=1,
        maximum=100,
    )
    if isinstance(sem_limit_raw, str):
        return sem_limit_raw
    sem_limit = sem_limit_raw

    def _run_semantic() -> str:
        from ..semantic.embedding import get_openai_embedding_client
        from ..semantic.search import format_semantic_search_markdown

        client = get_openai_embedding_client()
        return format_semantic_search_markdown(
            graph_path,
            sem_query,
            embedding_client=client,
            limit=sem_limit,
        )

    return await asyncio.to_thread(_run_semantic)


async def handle_search_regex(graph_path: str, query: str) -> str:
    rx_opts = parse_optional_json_query(query)
    pattern = str(rx_opts.get("pattern", query)).strip()
    if not pattern:
        return "For `method=regex`, set `query` to a regex pattern or JSON with `pattern`."
    rx_limit_raw = bounded_int_from_options(
        rx_opts,
        "limit",
        default=50,
        minimum=1,
        maximum=200,
    )
    if isinstance(rx_limit_raw, str):
        return rx_limit_raw
    rx_limit = rx_limit_raw
    return await asyncio.to_thread(
        format_regex_search_markdown,
        graph_path,
        pattern,
        limit=rx_limit,
    )


async def handle_search_unlinked_mentions(graph_path: str, query: str) -> str | dict[str, Any]:
    um_opts = parse_optional_json_query(query)
    max_hits_raw = bounded_int_from_options(
        um_opts,
        "max_hits_per_file",
        default=80,
        minimum=1,
        maximum=500,
    )
    if isinstance(max_hits_raw, str):
        return max_hits_raw
    max_hits = max_hits_raw
    max_titles_raw = bounded_int_from_options(
        um_opts,
        "max_titles",
        default=500,
        minimum=1,
        maximum=2000,
    )
    if isinstance(max_titles_raw, str):
        return max_titles_raw
    max_titles = max_titles_raw

    def _unlinked() -> dict[str, Any]:
        return scan_unlinked_mentions(
            graph_path,
            max_hits_per_file=max_hits,
            max_titles=max_titles,
        )

    return await asyncio.to_thread(_unlinked)


async def handle_search_resolve_entity(graph_path: str, query: str) -> str | dict[str, object]:
    candidate = query.strip()
    if not candidate:
        return "For `method=resolve_entity`, set `query` to a page title or `alias::` name."

    def _resolve_entity() -> dict[str, object]:
        from ..graph.generational_cache import cached_build_alias_index

        root = Path(graph_path).expanduser().resolve(strict=False)
        idx = cached_build_alias_index(root)
        return idx.resolve(candidate).as_dict()

    return await asyncio.to_thread(_resolve_entity)


async def handle_search_journal_tasks(graph_path: str, query: str) -> str | dict[str, Any]:
    j_opts = parse_optional_json_query(query)
    days_default_raw = j_opts.get("days", query.strip() or 7)
    days_raw = bounded_int_from_options(
        {"days": days_default_raw},
        "days",
        default=7,
        minimum=1,
        maximum=90,
    )
    if isinstance(days_raw, str):
        return days_raw
    days = days_raw

    def _journal() -> dict[str, Any]:
        report = scan_journal_tasks(graph_path, days=days)
        md = format_journal_task_review_markdown(report)
        rows = [
            {
                "source_iso_date": it.source_iso_date,
                "source_relpath": it.source_relpath,
                "marker": it.marker,
                "headline": it.headline,
                "scheduled": it.scheduled,
                "deadline": it.deadline,
                "block_text": it.block_text,
            }
            for it in report.items
        ]
        return {
            "ok": True,
            "days_scanned": report.days_scanned,
            "files_scanned": report.files_scanned,
            "open_item_count": len(report.items),
            "notes": report.notes,
            "items": rows,
            "task_review_markdown": md,
        }

    return await asyncio.to_thread(_journal)


_SEARCH_HANDLERS: dict[SearchGraphMethod, SearchHandler] = {
    "bm25": handle_search_bm25,
    "semantic": handle_search_semantic,
    "regex": handle_search_regex,
    "unlinked_mentions": handle_search_unlinked_mentions,
    "resolve_entity": handle_search_resolve_entity,
    "journal_tasks": handle_search_journal_tasks,
}


async def dispatch_search_target(
    method: SearchGraphMethod,
    query: str = "",
) -> str | dict[str, Any]:
    """Route ``search_graph`` by ``method``."""
    graph_path = graph_path_from_env()
    if not graph_path:
        if method == "journal_tasks":
            return {
                "ok": False,
                "error": graph_missing_text(),
                "items": [],
                "task_review_markdown": "",
            }
        if method == "resolve_entity":
            return graph_missing_dict()
        return graph_missing_text()

    handler = _SEARCH_HANDLERS[method]
    return await handler(graph_path, query)


__all__ = [
    "dispatch_search_target",
    "handle_search_bm25",
    "handle_search_journal_tasks",
    "handle_search_regex",
    "handle_search_resolve_entity",
    "handle_search_semantic",
    "handle_search_unlinked_mentions",
]
