"""Shared async dispatch for MCP mega-tools and the agent-native CLI."""

from __future__ import annotations

import asyncio
import uuid as uuid_module
from pathlib import Path
from typing import Any

from logseq_matryca_parser.agent_writer import _insertion_line_after_node
from logseq_matryca_parser.graph import LogseqGraph
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from loguru import logger

from ..config import MatrycaWikiConfig
from ..daemon.ast_cache import get_graph_ast_cache
from ..graph.markdown_blocks import (
    OCCConflictError,
    OCCSnapshot,
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    canonical_line_suffix,
    graph_safe_page_path,
    read_file_mtime_ns,
    strip_line_endings,
)
from ..graph.page_write_lock import page_rmw_lock
from ..graph.path_sandbox import (
    assert_path_within_graph,
    read_graph_file_text,
)
from .alias_state import resolve_target
from .dispatch_lint_handlers import dispatch_lint_target
from .dispatch_mutate_handlers import dispatch_mutate_target
from .dispatch_read_handlers import dispatch_read_target
from .dispatch_refactor_handlers import dispatch_refactor_target
from .dispatch_search_handlers import dispatch_search_target
from .graph_tool_helpers import (
    MutateGraphAction,
    ReadGraphTarget,
    RefactorBlocksAction,
    RunLinterName,
    SearchGraphMethod,
)
from .page_input_normalizer import normalize_page_ref
from .routing_hint import (
    routing_hint_for_entity_alias_preflight,
    routing_hint_for_write_outline,
)


def _cached_graph(graph_root: Path) -> LogseqGraph:
    return get_graph_ast_cache(graph_root).get_graph()


def _resolve_graph_node(graph: LogseqGraph, block_uuid: str) -> LogseqNode | None:
    """Resolve a block UUID against parser registry keys and on-disk ``id::`` values."""
    node = graph.get_node_by_uuid(block_uuid)
    if node is not None:
        return node
    return graph.get_node_by_embed_ref(block_uuid)


def _persistable_node_uuid(node: LogseqNode) -> str:
    source_uuid = getattr(node, "source_uuid", None)
    if isinstance(source_uuid, str) and source_uuid.strip():
        return source_uuid.strip()
    return str(node.uuid)


def _logseq_page_for_title(graph: LogseqGraph, page_title: str) -> LogseqPage | None:
    page = graph.pages.get(page_title)
    if page is not None:
        return page
    fold = page_title.casefold()
    for key, candidate in graph.pages.items():
        title = getattr(candidate, "title", key)
        if key.casefold() == fold or str(title).casefold() == fold:
            return candidate
    return None


def _fallback_page_bottom_parent_uuid(graph: LogseqGraph, page_title: str) -> str | None:
    """Return the last top-level block UUID on ``page_title`` for safe page-bottom append."""
    page = _logseq_page_for_title(graph, page_title)
    if page is None:
        return None
    roots = getattr(page, "root_nodes", None) or []
    if not roots:
        return None
    return _persistable_node_uuid(roots[-1])


_SAFE_APPEND_WARNING = "Block ID invalid. Performed a safe append to the page instead."
_EMPTY_PAGE_APPEND_NOTE = "Page has no outline blocks; appending at end of file."


def _coerce_write_target(target: object) -> str:
    """Coerce LLM-hallucinated targets (``0``, ``True``, etc.) to a safe string."""
    if target is None:
        return ""
    if isinstance(target, bool):
        return str(target).lower()
    return str(target).strip()


def _write_target_fallback(
    graph: LogseqGraph,
    page_title: str,
    warnings: list[str],
) -> tuple[str | None, str | None, list[str]]:
    """Return either a parent UUID or an empty-page append target."""
    parent = _fallback_page_bottom_parent_uuid(graph, page_title)
    if parent is not None:
        return parent, None, warnings
    warnings.append(_EMPTY_PAGE_APPEND_NOTE)
    return None, page_title, warnings


def _resolve_write_parent_target(
    graph_path: str | Path,
    target: object,
) -> tuple[str | None, str | None, list[str]]:
    """Resolve write parent UUID, with page-bottom or empty-file fallback when possible."""
    warnings: list[str] = []
    graph_root = Path(graph_path).expanduser().resolve()
    graph = _cached_graph(graph_root)
    raw = _coerce_write_target(target)
    if not raw:
        msg = "`target` must be the parent block UUID or `Page Title|block-uuid`."
        raise ValueError(msg)

    page_title: str | None = None
    block_ref = raw

    if "|" in raw:
        page_part, block_part = [segment.strip() for segment in raw.split("|", 1)]
        if not page_part or not block_part:
            msg = "For `Page Title|block-uuid`, both page title and block reference are required."
            raise ValueError(msg)
        try:
            page_norm = normalize_page_ref(graph_path, page_part)
        except ValueError:
            raise
        if page_norm is None:
            msg = f"Page not found: {page_part!r}"
            raise ValueError(msg)
        page_title = page_norm.canonical_title
        warnings.extend(page_norm.resolution_notes)
        block_ref = block_part

    try:
        resolved_block = resolve_target(graph_path, block_ref)
    except ValueError:
        if page_title is not None:
            warnings.append(_SAFE_APPEND_WARNING)
            logger.warning(
                "write target alias miss on page {}: {}",
                page_title,
                block_ref,
            )
            return _write_target_fallback(graph, page_title, warnings)
        raise

    node = _resolve_graph_node(graph, resolved_block.strip())
    if node is not None:
        return _persistable_node_uuid(node), None, warnings

    if page_title is not None:
        warnings.append(_SAFE_APPEND_WARNING)
        logger.warning(
            "write target block miss on page {}: {}",
            page_title,
            resolved_block,
        )
        return _write_target_fallback(graph, page_title, warnings)

    msg = f"No node registered for uuid={resolved_block}"
    raise ValueError(msg)


def _property_lines(properties: dict[str, str], block_uuid: str) -> list[str]:
    lines: list[str] = []
    for key, value in properties.items():
        prop_key = key if key.endswith("::") else f"{key}::"
        lines.append(f"{prop_key} {value}")
    if not any(line.strip().startswith("id::") for line in lines):
        lines.append(f"id:: {block_uuid}")
    return lines


def _resolve_chain_parent_uuid(
    graph_path: str | Path,
    parent_uuid: str,
    block_text: str,
    written_id: str,
) -> str:
    """Return a parent key the parser registry accepts for the next append."""
    graph_root = Path(graph_path).expanduser().resolve()
    graph: LogseqGraph | None = None
    for attempt in range(2):
        graph = _cached_graph(graph_root)
        by_id = graph.get_node_by_embed_ref(written_id)
        if by_id is not None:
            return written_id
        if attempt == 0:
            continue

    if graph is not None:
        parent = _resolve_graph_node(graph, parent_uuid)
        if parent is not None:
            for child in reversed(parent.children):
                if child.clean_text.strip() != block_text.strip():
                    continue
                source_uuid = getattr(child, "source_uuid", None)
                if isinstance(source_uuid, str) and source_uuid.strip():
                    return source_uuid.strip()
                return str(child.uuid)

    msg = (
        f"New block id::{written_id} was not indexed after write; "
        "cannot chain nested outline children."
    )
    raise ValueError(msg)


def _occ_snapshot_for_block(graph_path: str | Path, block_uuid: str) -> OCCSnapshot | None:
    """Phase-1 OCC snapshot for the page file hosting ``block_uuid``."""
    graph_root = Path(graph_path).expanduser().resolve()
    graph = _cached_graph(graph_root)
    node = _resolve_graph_node(graph, block_uuid)
    if node is None or not node.source_path:
        return None
    return OCCSnapshot.capture(node.source_path)


def _headless_append_child(
    graph_path: str | Path,
    parent_uuid: str,
    content: str,
    *,
    properties: dict[str, str] | None = None,
    occ: OCCSnapshot | None = None,
) -> str:
    """Append a child block on disk under ``parent_uuid``; return the new block UUID."""
    graph_root = Path(graph_path).expanduser().resolve()
    new_uuid = str(uuid_module.uuid4())
    graph = _cached_graph(graph_root)
    parent = _resolve_graph_node(graph, parent_uuid)
    if parent is None:
        msg = f"No node registered for uuid={parent_uuid}"
        raise ValueError(msg)
    source_path = parent.source_path
    if not source_path:
        msg = f"Node uuid={parent_uuid} has no source_path"
        raise ValueError(msg)

    props = _property_lines(dict(properties or {}), new_uuid)
    content_lines = content.splitlines()
    head = content_lines[0] if content_lines else ""
    tail = content_lines[1:]

    page_path = Path(source_path)
    if occ is None:
        occ = OCCSnapshot.capture(page_path)
    elif occ.drifted():
        raise OCCConflictError(
            page_path,
            baseline_mtime=occ.baseline_mtime,
            current_mtime=read_file_mtime_ns(page_path),
        )

    with page_rmw_lock(source_path):
        if occ is not None and occ.drifted():
            raise OCCConflictError(
                page_path,
                baseline_mtime=occ.baseline_mtime,
                current_mtime=read_file_mtime_ns(page_path),
            )
        graph = _cached_graph(graph_root)
        parent = _resolve_graph_node(graph, parent_uuid)
        if parent is None:
            msg = f"No node registered for uuid={parent_uuid}"
            raise ValueError(msg)
        parent_uuid_resolved = parent.uuid

        target_node = graph.get_node_by_uuid(parent_uuid_resolved)
        if target_node is None:
            msg = f"No node registered for uuid={parent_uuid_resolved}"
            raise ValueError(msg)
        insert_after_line = _insertion_line_after_node(target_node)
        child_level = target_node.indent_level + 1
        bullet_indent = " " * (child_level * graph.tab_size)
        body_indent = " " * ((child_level + 1) * graph.tab_size)
        path = Path(target_node.source_path or source_path)
        safe_path = assert_path_within_graph(path, graph_root)
        raw_text = read_graph_file_text(safe_path, graph_root)
        file_lines = raw_text.splitlines(keepends=True)
        insert_index = insert_after_line

        new_lines = [f"{bullet_indent}- {strip_line_endings(head)}\n"]
        new_lines.extend(f"{body_indent}{strip_line_endings(line)}\n" for line in tail)
        new_lines.extend(f"{body_indent}{line}\n" for line in props)

        for offset, line in enumerate(new_lines):
            file_lines.insert(insert_index + offset, line)

        updated = "".join(strip_line_endings(ln) + canonical_line_suffix(ln) for ln in file_lines)
        baseline_mtime = occ.baseline_mtime if occ is not None else read_file_mtime_ns(path)
        commit_summary = f"appended block under parent {parent_uuid}"
        if baseline_mtime is None or not atomic_write_bytes_if_unchanged(
            path,
            updated.encode("utf-8"),
            graph_root=graph_root,
            baseline_mtime=baseline_mtime,
            robot_commit_summary=commit_summary,
        ):
            raise OCCConflictError(
                path,
                baseline_mtime=baseline_mtime or 0,
                current_mtime=read_file_mtime_ns(path),
            )
        if occ is not None:
            occ.refresh_after_own_write()

    return new_uuid


def _headless_write_outline(
    graph_path: str,
    parent_block_uuid: str,
    outline: dict[str, Any],
) -> dict[str, Any]:
    """Depth-first headless outline write using the parser's atomic splice engine."""
    from .outline_models import OutlineNode, outline_block_count, validate_outline_for_write

    root = validate_outline_for_write(outline)

    graph_root = Path(graph_path).expanduser().resolve()
    graph = _cached_graph(graph_root)
    parent_node = _resolve_graph_node(graph, parent_block_uuid)
    occ: OCCSnapshot | None = None
    if parent_node is not None and parent_node.source_path:
        occ = OCCSnapshot.capture(parent_node.source_path)

    created_ids: list[str] = []

    def walk(node: OutlineNode, parent_uuid: str) -> None:
        new_uuid = _headless_append_child(
            graph_path,
            parent_uuid,
            node.text,
            properties=dict(node.properties),
            occ=occ,
        )
        created_ids.append(new_uuid)
        chain_parent = _resolve_chain_parent_uuid(
            graph_path,
            parent_uuid,
            node.text,
            new_uuid,
        )
        for child in node.children:
            walk(child, chain_parent)

    walk(root, parent_block_uuid)
    logger.bind(
        blocks=len(created_ids),
        root_parent=parent_block_uuid,
    ).info("Applied headless Logseq outline with parent-chained UUIDs")
    join_hint = routing_hint_for_write_outline()
    if root.properties.get("type::") == "entity":
        join_hint = f"{join_hint}\n{routing_hint_for_entity_alias_preflight()}"
    return {
        "ok": True,
        "uuids": created_ids,
        "routing_hint": join_hint,
        "outline_block_count": outline_block_count(outline),
        "git_snapshot": {
            "committed": True,
            "skipped": False,
            "reason": "post-write robot commits via hooks",
        },
    }


def _headless_write_outline_empty_page(
    graph_path: str | Path,
    page_title: str,
    outline: dict[str, Any],
) -> dict[str, Any]:
    """Append an outline to an empty or blockless page file (safe fallback path)."""
    from .outline_models import OutlineNode, outline_block_count, validate_outline_for_write

    root = validate_outline_for_write(outline)
    graph_root = Path(graph_path).expanduser().resolve()
    page_path = graph_safe_page_path(graph_root, page_title)
    graph = _cached_graph(graph_root)
    tab_size = graph.tab_size
    created_ids: list[str] = []

    def emit_node(node: OutlineNode, indent_level: int, out_lines: list[str]) -> None:
        new_uuid = str(uuid_module.uuid4())
        created_ids.append(new_uuid)
        bullet_indent = " " * (indent_level * tab_size)
        body_indent = " " * ((indent_level + 1) * tab_size)
        content_lines = node.text.splitlines()
        head = content_lines[0] if content_lines else ""
        out_lines.append(f"{bullet_indent}- {strip_line_endings(head)}\n")
        for extra in content_lines[1:]:
            out_lines.append(f"{body_indent}{strip_line_endings(extra)}\n")
        for prop in _property_lines(dict(node.properties), new_uuid):
            out_lines.append(f"{body_indent}{prop}\n")
        for child in node.children:
            emit_node(child, indent_level + 1, out_lines)

    block_lines: list[str] = []
    emit_node(root, 0, block_lines)

    with page_rmw_lock(page_path):
        occ: OCCSnapshot | None = OCCSnapshot.capture(page_path) if page_path.is_file() else None
        if occ is not None and occ.drifted():
            raise OCCConflictError(
                page_path,
                baseline_mtime=occ.baseline_mtime,
                current_mtime=read_file_mtime_ns(page_path),
            )
        prev = read_graph_file_text(page_path, graph_root) if page_path.is_file() else ""
        section = "".join(
            strip_line_endings(line) + canonical_line_suffix(line) for line in block_lines
        )
        new_text = prev.rstrip("\n") + ("\n\n" if prev.strip() else "") + section
        baseline_mtime = occ.baseline_mtime if occ is not None else None
        if page_path.is_file():
            if baseline_mtime is None or not atomic_write_bytes_if_unchanged(
                page_path,
                new_text.encode("utf-8"),
                graph_root=graph_root,
                baseline_mtime=baseline_mtime,
                robot_commit_summary=f"appended outline to empty page {page_title}",
            ):
                raise OCCConflictError(
                    page_path,
                    baseline_mtime=baseline_mtime or 0,
                    current_mtime=read_file_mtime_ns(page_path),
                )
            if occ is not None:
                occ.refresh_after_own_write()
        else:
            page_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(
                page_path,
                new_text.encode("utf-8"),
                graph_root=graph_root,
                robot_commit_summary=f"created page outline {page_title}",
            )

    join_hint = routing_hint_for_write_outline()
    if root.properties.get("type::") == "entity":
        join_hint = f"{join_hint}\n{routing_hint_for_entity_alias_preflight()}"
    return {
        "ok": True,
        "uuids": created_ids,
        "routing_hint": join_hint,
        "outline_block_count": outline_block_count(outline),
        "git_snapshot": {
            "committed": True,
            "skipped": False,
            "reason": "post-write robot commits via hooks",
        },
    }


async def _run_write_outline(
    graph_path: str,
    target: object,
    outline: dict[str, Any],
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _run_write_outline_sync,
        graph_path,
        target,
        outline,
    )


def _run_write_outline_sync(
    graph_path: str,
    target: object,
    outline: dict[str, Any],
) -> dict[str, Any]:
    """Resolve parent and write in one thread (avoid resolve/write TOCTOU)."""
    parent_uuid, empty_page_title, write_warnings = _resolve_write_parent_target(
        graph_path,
        target,
    )
    if empty_page_title:
        result = _headless_write_outline_empty_page(
            graph_path,
            empty_page_title,
            outline,
        )
    else:
        result = _headless_write_outline(
            graph_path,
            parent_uuid or "",
            outline,
        )
    if write_warnings:
        result["warnings"] = write_warnings
        for note in write_warnings:
            logger.warning(note)
    return result


async def dispatch_read(
    wiki_config: MatrycaWikiConfig,
    target_type: ReadGraphTarget,
    query: str = "",
) -> str:
    """Route ``read_graph_data`` by ``target_type``."""
    return await dispatch_read_target(wiki_config, target_type, query)


async def dispatch_search(
    method: SearchGraphMethod,
    query: str = "",
) -> str | dict[str, Any]:
    """Route ``search_graph`` by ``method``."""
    return await dispatch_search_target(method, query)


async def dispatch_mutate(
    action: MutateGraphAction,
    target: str,
    payload: str,
) -> dict[str, Any]:
    """Route ``mutate_graph`` by ``action`` (headless on-disk writes)."""
    return await dispatch_mutate_target(action, target, payload)


async def dispatch_refactor(
    action: RefactorBlocksAction,
    target_uuid: str,
    payload: str = "",
) -> dict[str, Any]:
    """Route ``refactor_blocks`` by ``action`` (headless on-disk rewrites)."""
    return await dispatch_refactor_target(action, target_uuid, payload)


async def dispatch_lint(
    wiki_config: MatrycaWikiConfig,
    linter_name: RunLinterName,
) -> str | dict[str, Any]:
    """Route ``run_linter`` by ``linter_name``."""
    return await dispatch_lint_target(wiki_config, linter_name)


__all__ = [
    "dispatch_lint",
    "dispatch_mutate",
    "dispatch_read",
    "dispatch_refactor",
    "dispatch_search",
]
