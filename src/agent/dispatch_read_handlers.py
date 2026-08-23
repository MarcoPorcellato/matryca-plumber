"""``read_graph_data`` handlers — one function per ``ReadGraphTarget`` (issue #59 slice)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

from loguru import logger

from ..config import MatrycaWikiConfig
from ..graph.bootstrap_status import format_bootstrap_status_markdown
from ..graph.dashboard import build_dashboard_markdown
from ..graph.journal_read import read_journal_day_markdown
from ..graph.link_tag_hop import format_hop_report_markdown
from ..rag.matryca_hooks import get_page_spatial_context
from ..shadow.state_api import resolve_shadow_db_state_for_api
from .graph_tool_helpers import (
    ReadGraphTarget,
    bounded_int_from_options,
    graph_missing_text,
    graph_path_from_env,
    parse_optional_json_query,
    read_block_ast_markdown,
    read_xray_page_markdown,
)
from .l1_memory import read_l1_memory_async
from .llm_context_payload import cap_llm_payload_chars
from .markdown_graph_repository import get_graph_read_port
from .page_input_normalizer import format_resolution_notes_footer, normalize_page_ref_or_raw
from .routing_hint import append_read_page_routing_hint

ReadHandler = Callable[[MatrycaWikiConfig, str, str], Awaitable[str]]


async def handle_read_memory(wiki_config: MatrycaWikiConfig, _graph_path: str, _query: str) -> str:
    _labels, body = await read_l1_memory_async(wiki_config)
    if not _labels:
        return (
            "No L1 memory loaded. Set **MATRYCA_L1_PATH**, or **memory_path** in "
            "**matryca-wiki.yml**, or create **matryca-l1/*.md** next to your graph. "
            "See `SYSTEM_PROMPT.md` for L1 vs L2 routing."
        )
    logger.bind(files=len(_labels)).info("read_graph_data(memory) loaded L1 context")
    return cap_llm_payload_chars(body)


async def handle_read_page(_wiki_config: MatrycaWikiConfig, graph_path: str, query: str) -> str:
    page_name = query.strip()
    if not page_name:
        return "For `target_type=page`, set `query` to the Logseq page title."
    try:
        page_norm = normalize_page_ref_or_raw(graph_path, page_name)
    except ValueError as exc:
        return str(exc)
    try:
        markdown = await get_page_spatial_context(page_norm.canonical_title, graph_path)
    except FileNotFoundError as exc:
        logger.bind(page=page_name, graph=graph_path).info("read_graph_data page miss: {}", exc)
        return "Page not found, you can create it."
    except ImportError as exc:
        logger.error("read_graph_data parser missing: {}", exc)
        return f"Spatial parser is not available (install `logseq-matryca-parser`). Detail: {exc}"
    except OSError as exc:
        logger.bind(page=page_name).exception("read_graph_data OS error")
        return f"Could not read the page file from disk: {exc}"
    body = append_read_page_routing_hint(cap_llm_payload_chars(markdown))
    return body + format_resolution_notes_footer(page_norm.resolution_notes)


async def handle_read_journal_day(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
    query: str,
) -> str:
    """Read one dated journal through the Markdown authority, never through Shadow."""
    return await asyncio.to_thread(read_journal_day_markdown, graph_path, query)


async def handle_read_xray_page(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
    query: str,
) -> str:
    page_name = query.strip()
    if not page_name:
        return "For `target_type=xray_page`, set `query` to the Logseq page title."
    try:
        page_norm = normalize_page_ref_or_raw(graph_path, page_name)
    except ValueError as exc:
        return str(exc)
    try:
        xray_md = await asyncio.to_thread(
            read_xray_page_markdown,
            graph_path,
            page_norm.canonical_title,
        )
    except FileNotFoundError:
        return "Page not found, you can create it."
    except ImportError as exc:
        logger.error("read_graph_data xray_page parser missing: {}", exc)
        return f"Spatial parser is not available (install `logseq-matryca-parser`). Detail: {exc}"
    except OSError as exc:
        logger.bind(page=page_name).exception("read_graph_data xray_page OS error")
        return f"Could not read the page file from disk: {exc}"
    body = cap_llm_payload_chars(xray_md)
    return body + format_resolution_notes_footer(page_norm.resolution_notes)


async def handle_read_block_ast(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
    query: str,
) -> str:
    block_query = query.strip()
    if not block_query:
        return (
            "For `target_type=block_ast`, set `query` to `Page Title|block-uuid` "
            "or `Page Title|[n]` after `xray_page`."
        )
    try:
        block_md = await asyncio.to_thread(read_block_ast_markdown, graph_path, block_query)
    except ValueError as exc:
        return str(exc)
    return cap_llm_payload_chars(block_md)


async def handle_read_subtree(_wiki_config: MatrycaWikiConfig, graph_path: str, query: str) -> str:
    from pathlib import Path

    subtree_query = query.strip()
    if not subtree_query:
        return (
            "For `target_type=subtree`, set `query` to `Page Title|block-uuid` "
            'or JSON `{"page":"...","block_uuid":"...","heading":"optional"}`.'
        )
    port = get_graph_read_port(Path(graph_path))
    try:
        subtree_md = await asyncio.to_thread(
            port.read_subtree_markdown,
            Path(graph_path),
            subtree_query,
        )
    except ValueError as exc:
        return str(exc)
    return cap_llm_payload_chars(subtree_md)


async def handle_read_structural_hops(
    wiki_config: MatrycaWikiConfig,
    graph_path: str,
    query: str,
) -> str:
    hop_opts = parse_optional_json_query(query)
    seeds_raw = str(hop_opts.get("seeds", query)).strip()
    seed_list = [s.strip() for s in seeds_raw.split(",") if s.strip()]
    if not seed_list:
        return (
            "For `target_type=structural_hops`, provide seed page titles in `query` "
            "(comma-separated) or JSON with `seeds`."
        )
    depth = wiki_config.max_depth
    if hop_opts.get("max_depth") is not None:
        depth_raw = bounded_int_from_options(
            hop_opts,
            "max_depth",
            default=depth,
            minimum=1,
            maximum=10,
        )
        if isinstance(depth_raw, str):
            return depth_raw
        depth = depth_raw
    per = wiki_config.structural_hop_max_per_level
    if hop_opts.get("max_per_level") is not None:
        per_raw = bounded_int_from_options(
            hop_opts,
            "max_per_level",
            default=per,
            minimum=1,
            maximum=500,
        )
        if isinstance(per_raw, str):
            return per_raw
        per = per_raw

    def _hops() -> str:
        return format_hop_report_markdown(
            graph_path,
            seed_list,
            max_depth=depth,
            max_per_level=per,
        )

    return cap_llm_payload_chars(await asyncio.to_thread(_hops))


async def handle_read_bootstrap_status(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
    _query: str,
) -> str:
    status_md = await asyncio.to_thread(format_bootstrap_status_markdown, graph_path)
    logger.bind(graph=graph_path).info("read_graph_data(bootstrap_status) completed")
    return cap_llm_payload_chars(status_md)


async def handle_read_shadow_status(
    _wiki_config: MatrycaWikiConfig,
    graph_path: str,
    _query: str,
) -> str:
    """Return the versioned, content-free Shadow read profile without cache initialization."""
    snapshot = await asyncio.to_thread(resolve_shadow_db_state_for_api, graph_path)
    logger.bind(state=snapshot.state).info("read_graph_data(shadow_status) completed")
    return json.dumps(snapshot.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)


async def handle_read_dashboard(
    wiki_config: MatrycaWikiConfig,
    graph_path: str,
    _query: str,
) -> str:
    dashboard_md = await asyncio.to_thread(
        build_dashboard_markdown,
        graph_path,
        wiki_config,
    )
    logger.bind(graph=graph_path).info("read_graph_data(dashboard) completed")
    return cap_llm_payload_chars(dashboard_md)


_READ_HANDLERS: dict[ReadGraphTarget, ReadHandler] = {
    "memory": handle_read_memory,
    "page": handle_read_page,
    "journal_day": handle_read_journal_day,
    "xray_page": handle_read_xray_page,
    "block_ast": handle_read_block_ast,
    "subtree": handle_read_subtree,
    "structural_hops": handle_read_structural_hops,
    "bootstrap_status": handle_read_bootstrap_status,
    "shadow_status": handle_read_shadow_status,
    "dashboard": handle_read_dashboard,
}


async def dispatch_read_target(
    wiki_config: MatrycaWikiConfig,
    target_type: ReadGraphTarget,
    query: str = "",
) -> str:
    """Route ``read_graph_data`` by ``target_type``."""
    handler = _READ_HANDLERS.get(target_type, handle_read_dashboard)
    if target_type == "memory":
        return await handler(wiki_config, "", query)

    graph_path = graph_path_from_env()
    if not graph_path:
        logger.warning("read_graph_data(%s) but LOGSEQ_GRAPH_PATH unset", target_type)
        return graph_missing_text()

    return await handler(wiki_config, graph_path, query)


__all__ = [
    "dispatch_read_target",
    "handle_read_bootstrap_status",
    "handle_read_block_ast",
    "handle_read_dashboard",
    "handle_read_memory",
    "handle_read_journal_day",
    "handle_read_page",
    "handle_read_shadow_status",
    "handle_read_structural_hops",
    "handle_read_subtree",
    "handle_read_xray_page",
]
