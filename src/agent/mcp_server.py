"""Agent-facing MCP server scaffolding (headless graph tools)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from ..config import MatrycaWikiConfig
from .graph_dispatch import (
    dispatch_lint,
    dispatch_mutate,
    dispatch_read,
    dispatch_refactor,
    dispatch_search,
)
from .graph_tool_helpers import (
    MutateGraphAction,
    ReadGraphTarget,
    RefactorBlocksAction,
    RunLinterName,
    SearchGraphMethod,
)
from .ingestion import dispatch_ingest_document
from .mcp_telemetry import mcp_tool_info, mcp_tool_session
from .mcp_tool_guard import guard_mcp_tool
from .memory_tools import dispatch_store_fact
from .outline_models import (
    Domain,
    EntityType,
    OutlineNode,
    PageType,
    outline_block_count,
)
from .tana_import import dispatch_tana_import


@dataclass(frozen=True, slots=True)
class AppContext:
    """Dependencies available for the MCP server lifetime."""

    wiki_config: MatrycaWikiConfig


def register_mcp_tools(mcp: FastMCP) -> None:
    """Register consolidated MCP tools on the FastMCP application.

    Tools: ``read_graph_data``, ``search_graph``, ``mutate_graph``, ``refactor_blocks``,
    ``run_linter``, ``store_fact``, ``ingest_document``, ``import_tana`` — each routes by a
    ``typing.Literal`` discriminator (where applicable) to
    existing graph/RAG helpers (see module-level docstrings on each handler).

    Args:
        mcp: The application instance created in :mod:`src.main`.
    """

    def safe_tool(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """Register an MCP tool wrapped with :func:`guard_mcp_tool`."""

        def decorator(fn: Any) -> Any:
            return mcp.tool(*args, **kwargs)(guard_mcp_tool(fn))

        return decorator

    @safe_tool()
    async def read_graph_data(
        ctx: Context[ServerSession, AppContext],
        target_type: ReadGraphTarget,
        query: str = "",
    ) -> str:
        """Unified read plane: pages, L1 memory, block excerpts, structural hops, dashboards.

        Pick ``target_type`` first, then set ``query`` exactly as below (ignored where noted).

        **``target_type=page``** — ``query`` = Logseq **page title** (e.g. ``My Project``),
        not a file path.
        Returns spatial-parser Markdown: block tree, ``synthetic_id``, ``source_uuid``, ``uuid``.
        Use before edits; pair with ``mutate_graph`` only when you have a parent block UUID.

        **``target_type=memory``** — ``query`` ignored. Loads L1 fast-context Markdown
        (``MATRYCA_L1_PATH``, ``memory_path`` in ``matryca-wiki.yml``, or ``matryca-l1/*.md``).

        **``target_type=block_ast``** — ``query`` = ``Page Title|block-uuid`` (pipe-separated).
        Raw on-disk bullet subtree for that ``id::`` block (headless; no Logseq HTTP API).

        **``target_type=subtree``** — ``query`` = ``Page Title|block-uuid`` or JSON with
        ``page``, ``block_uuid``, optional ``heading`` to narrow nested bullets
        (token-saving reads).

        **``target_type=structural_hops``** — ``query`` = comma-separated seed page titles,
        or JSON ``{"seeds":"A, B", "max_depth": 3, "max_per_level": 40}``. BFS over wikilinks,
        shared tags, and light ``type::`` / ``domain::`` rings (no vectors).

        **``target_type=bootstrap_status``** — ``query`` ignored. Phase 1 semaphore JSON
        (``bootstrap_complete``, progress, ``soft_gate_active``). Call before the Master Index
        Soft Gate.

        **``target_type=dashboard``** — ``query`` ignored. Matryca dashboard Markdown:
        page counts, ``id::`` tally, block-ref health under ``pages/``.

        **``target_type=xray_page``** — ``query`` = Logseq **page title**. Ultra-dense
        ``[n]`` outline (X-Ray mode); persists alias→UUID map to ``.matryca_xray_state.json`` at
        the graph root. Use ``[n]`` in ``target`` / ``target_uuid`` on later mutations.

        **Requires:** ``LOGSEQ_GRAPH_PATH`` for every target except ``memory`` (still recommended).

        TIER-2 SOFT GATE: Before first wiki read/search, call ``target_type=bootstrap_status``
        then ``target_type=page`` ``query="Matryca Master Index"``. If missing or Phase 1
        incomplete, pause and present 3 fallback options to the operator for authorization:
        (A) Local Daemon — recommended, run ``matryca plumber start``;
        (B) Blind Search — proceed without index, less precise;
        (C) Cloud Indexing — agent scans vault now, high token cost.
        Wait for explicit user choice before B or C. Do not guess page titles.
        """
        wiki_config = ctx.request_context.lifespan_context.wiki_config
        if target_type == "dashboard":
            await mcp_tool_info(
                ctx,
                "Rendering Matryca dashboard: scanning pages/ and block-reference health…",
            )
            async with mcp_tool_session(ctx):
                dashboard_md: str = await dispatch_read(wiki_config, target_type, query)
            await mcp_tool_info(ctx, "Dashboard render complete.")
            return dashboard_md
        return await dispatch_read(wiki_config, target_type, query)

    @safe_tool()
    async def search_graph(
        ctx: Context[ServerSession, AppContext],
        method: SearchGraphMethod,
        query: str = "",
    ) -> str | dict[str, Any]:
        """Lexical and structural discovery on the on-disk graph (no vector DB).

        **``method=bm25``** — ``query`` = natural-language keywords (e.g. ``redis cache``), or JSON
        ``{"keyword":"...", "limit":15}``. Ranks ``pages/**/*.md`` by Okapi BM25.

        **``method=semantic``** — Hybrid search over dual block embeddings (content +
        applicability). Requires ``MATRYCA_DUAL_EMBEDDING_ENABLED=true`` and daemon indexing.
        ``query`` = natural language or JSON ``{"query":"...", "limit":15}``.

        **``method=regex``** — ``query`` = Python regex pattern (line scan in ``pages/``), or JSON
        ``{"pattern":"TODO|LATER", "limit":50}``.

        **``method=unlinked_mentions``** — ``query`` empty or JSON
        ``{"max_hits_per_file":80, "max_titles":500}``. Plain-text mentions of existing titles.

        **``method=journal_tasks``** — ``query`` = days to scan (default ``7``), or JSON
        ``{"days":14}``. Open ``TODO`` / ``LATER`` / ``WAITING`` in ``journals/`` plus review MD.

        **``method=resolve_entity``** — ``query`` = page title or ``alias::`` name. Resolves
        collisions, lists existing aliases, and reports whether a new entity page is safe to create.

        PREREQUISITE: Check ``bootstrap_status`` and scan ``[[Matryca Master Index]]`` via
        ``read_graph_data(page)`` first. If index unavailable, pause and present fallback options
        (Local Daemon, Blind Search, Cloud Indexing) to the operator for authorization before
        blind ``bm25`` discovery.
        """
        if method == "bm25":
            await mcp_tool_info(
                ctx,
                "Building in-memory BM25 index over pages/ "
                "(first run or cache miss may take a moment)…",
            )
            async with mcp_tool_session(ctx):
                result_md = await dispatch_search(method, query)
            await mcp_tool_info(ctx, "Local page query complete.")
            return result_md
        if method == "semantic":
            await mcp_tool_info(
                ctx,
                "Embedding query and scoring dual block vectors (content + applicability)…",
            )
            async with mcp_tool_session(ctx):
                result_md = await dispatch_search(method, query)
            await mcp_tool_info(ctx, "Semantic block search complete.")
            return result_md
        return await dispatch_search(method, query)

    @safe_tool()
    async def mutate_graph(
        ctx: Context[ServerSession, AppContext],
        action: MutateGraphAction,
        target: str,
        payload: str,
    ) -> dict[str, Any]:
        """Create or patch durable graph content via headless on-disk writes.

        **``action=write_outline``** — ``target`` = parent **block UUID**, X-Ray ``[n]``,
        or ``Page Title|block-uuid`` / ``Page Title|[n]`` (v1.9.7+ safe append on invalid block).
        ``payload`` = JSON outline tree (``text``, optional ``properties`` / schema fields,
        nested ``children``) matching ``OutlineNode``. Response may include ``warnings``.

        **``action=edit_property``** — ``target`` = ``Page Title|block-uuid``.
        ``payload`` = JSON: ``search``, ``replacement``, optional ``dry_run`` (default true),
        ``use_regex``, ``replace_all``, ``case_sensitive``. Surgical ``key::`` line edits only.

        **``action=append_journal``** — ``target`` ignored (use ``""``).
        ``payload`` = Markdown to append to today's ``journals/YYYY_MM_DD.md``, or JSON
        ``{"markdown_body":"...", "dry_run":true}``.

        **``action=inject_query``** — ``target`` = parent block UUID (or ``[n]`` alias).
        ``payload`` = JSON with inner EDN in ``query_edn`` and/or ``query_preset``
        (``open_markers``, ``pages_tagged``) plus optional ``tag``, ``dry_run`` (default true).

        **``action=generate_moc``** — ``target`` = namespace stem (e.g. ``Project/Sub``).
        ``payload`` = optional JSON ``{"output_page_title":"MOC Project", "dry_run":true}``.
        Writes a Map-of-Content index page listing every page under that namespace.
        """
        _ = ctx
        return await dispatch_mutate(action, target, payload)

    @safe_tool()
    async def refactor_blocks(
        ctx: Context[ServerSession, AppContext],
        action: RefactorBlocksAction,
        target_uuid: str,
        payload: str = "",
    ) -> dict[str, Any]:
        """AST-heavy block restructuring on disk (indent-only; preserves ``id::`` where possible).

        **``action=split_large``** — ``target_uuid`` = page title (optional; empty = all pages).
        ``payload`` = optional JSON ``{"min_chars":400, "max_blocks":25, "dry_run":true}``.

        **``action=reparent``** — ``target_uuid`` = page title. ``payload`` = JSON array of groups
        (same shape as legacy ``refactor_logseq_blocks`` ``groups`` argument).

        **``action=generate_flashcards``** — ``target_uuid`` = ``Page Title|source-block-uuid``.
        ``payload`` = optional JSON ``{"max_cards":30, "dry_run":true}``.
        """
        _ = ctx
        return await dispatch_refactor(action, target_uuid, payload)

    @safe_tool()
    async def run_linter(
        ctx: Context[ServerSession, AppContext],
        linter_name: RunLinterName,
    ) -> str | dict[str, Any]:
        """Vault hygiene scans (read-only or dry-run by default).

        **``linter_name=unify_tags``** — Preview-only tag clustering (``dry_run=true``).
        Cluster ``#tag`` spellings vault-wide; apply only after explicit operator consent.

        **``linter_name=block_refs``** — Markdown report: ``((uuid))`` vs graph-wide node index.

        **``linter_name=full_wiki_scan``** — Lint wiki-prefixed pages per ``matryca-wiki.yml``
        (``type::``, stale knowledge, credentials, wikilinks).
        """
        wiki_config = ctx.request_context.lifespan_context.wiki_config
        if linter_name == "full_wiki_scan":
            await mcp_tool_info(
                ctx,
                "Scanning wiki-prefixed pages under pages/ for lint findings…",
            )
            async with mcp_tool_session(ctx):
                wiki_report = await dispatch_lint(wiki_config, linter_name)
            await mcp_tool_info(ctx, "Wiki lint scan complete.")
            return wiki_report
        return await dispatch_lint(wiki_config, linter_name)

    @safe_tool()
    async def store_fact(
        ctx: Context[ServerSession, AppContext],
        fact: str,
    ) -> dict[str, Any]:
        """Persist a user preference, rule, or fact across sessions.

        Appends ``fact`` as a bullet under ``- # AI Constraints`` on ``pages/matryca-config.md``
        (created with Telos/Constraints headings when missing). Use this tool to permanently
        remember operator preferences for future MCP and daemon LLM runs.
        """
        _ = ctx
        return await dispatch_store_fact(fact)

    @safe_tool()
    async def ingest_document(
        ctx: Context[ServerSession, AppContext],
        source_name: str,
        raw_text: str,
    ) -> dict[str, Any]:
        """Atomically ingest external markdown into the Logseq graph.

        Parses ``raw_text`` via a temporary OS file (never under ``pages/``), assigns fresh
        block UUIDs, appends a section to the ingest destination page (daily ``Ingest/YYYY-MM-DD``
        or ``MATRYCA_INGEST_PAGE``), and updates ``LOG`` / ``GLOSSARY`` ledgers with OCC-safe
        writes and optional robot git commits.
        """
        _ = ctx
        return await dispatch_ingest_document(source_name, raw_text)

    @safe_tool()
    async def import_tana(
        ctx: Context[ServerSession, AppContext],
        export_path: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Import a Tana workspace JSON export into the Logseq graph.

        Streams ``docs[]`` via ``ijson``, builds hybrid placement plans, resolves wikilinks
        against in-flight pages and ``MasterCatalog``, then writes entity pages and journals
        with ``tana-id`` idempotency. When ``dry_run`` is true (default), returns the JSON
        report without touching disk.
        """
        _ = ctx
        return await dispatch_tana_import(export_path, dry_run=dry_run)


__all__ = [
    "AppContext",
    "Domain",
    "EntityType",
    "OutlineNode",
    "PageType",
    "MutateGraphAction",
    "ReadGraphTarget",
    "RefactorBlocksAction",
    "RunLinterName",
    "SearchGraphMethod",
    "outline_block_count",
    "register_mcp_tools",
]
