"""``run_linter`` handlers — one function per ``RunLinterName`` (issue #59 slice)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from loguru import logger

from ..config import MatrycaWikiConfig
from ..graph.block_ref_lint import lint_block_refs_in_graph
from ..graph.tag_unify import lint_unify_logseq_tags as core_lint_unify_logseq_tags
from ..graph.wiki_lint import format_wiki_lint_report, lint_wiki_prefixed_pages
from .graph_tool_helpers import (
    RunLinterName,
    graph_missing_dict,
    graph_missing_text,
    graph_path_from_env,
)

LintHandler = Callable[[MatrycaWikiConfig, str], Awaitable[str | dict[str, Any]]]


async def handle_lint_unify_tags(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
) -> dict[str, Any]:
    def _tags() -> dict[str, Any]:
        raw = core_lint_unify_logseq_tags(graph_path, dry_run=True).as_dict()
        return cast(dict[str, Any], raw)

    return await asyncio.to_thread(_tags)


async def handle_lint_block_refs(_wiki_config: MatrycaWikiConfig, graph_path: str) -> str:
    from .graph_dispatch import _cached_graph

    def _refs() -> str:
        root = Path(graph_path).expanduser().resolve()
        result = lint_block_refs_in_graph(root, graph=_cached_graph(root))
        logger.bind(
            pages=result.pages_scanned,
            issues=len(result.broken),
        ).info("run_linter(block_refs) completed")
        return result.format_report()

    return await asyncio.to_thread(_refs)


async def handle_lint_full_wiki_scan(
    wiki_config: MatrycaWikiConfig,
    graph_path: str,
) -> str:
    def _wiki() -> str:
        findings = lint_wiki_prefixed_pages(graph_path, wiki_config)
        return format_wiki_lint_report(findings, prefix=wiki_config.wiki_file_prefix)

    wiki_report: str = await asyncio.to_thread(_wiki)
    logger.bind(graph=graph_path).info("run_linter(full_wiki_scan) completed")
    return wiki_report


_LINT_HANDLERS: dict[RunLinterName, LintHandler] = {
    "unify_tags": handle_lint_unify_tags,
    "block_refs": handle_lint_block_refs,
    "full_wiki_scan": handle_lint_full_wiki_scan,
}


async def dispatch_lint_target(
    wiki_config: MatrycaWikiConfig,
    linter_name: RunLinterName,
) -> str | dict[str, Any]:
    """Route ``run_linter`` by ``linter_name``."""
    graph_path = graph_path_from_env()
    if not graph_path:
        if linter_name == "unify_tags":
            return graph_missing_dict()
        return graph_missing_text()

    handler = _LINT_HANDLERS[linter_name]
    return await handler(wiki_config, graph_path)


__all__ = [
    "dispatch_lint_target",
    "handle_lint_block_refs",
    "handle_lint_full_wiki_scan",
    "handle_lint_unify_tags",
]
