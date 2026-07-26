"""``mutate_graph`` handlers — one function per ``MutateGraphAction`` (issue #59 slice)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from loguru import logger

from ..graph.advanced_query_block import (
    resolve_advanced_query_preset,
    wrap_logseq_advanced_query,
)
from ..graph.journal_task_scan import append_journal_markdown_section
from ..graph.markdown_blocks import OCCConflictError, graph_safe_page_path, read_file_mtime_ns
from ..graph.moc_page import write_moc_page
from ..graph.path_sandbox import PathTraversalSecurityError
from ..graph.property_line_edit import edit_block_property_lines
from .alias_state import resolve_pipe_target
from .graph_tool_helpers import (
    MutateGraphAction,
    graph_missing_dict,
    graph_path_from_env,
    parse_json_object,
)
from .page_input_normalizer import normalize_pipe_page_target
from .quality_gate import advanced_query_security_violations, markdown_append_bounds_violations
from .routing_hint import routing_hint_for_write_outline

MutateHandler = Callable[[str | None, str, str], Awaitable[dict[str, Any]]]


def mutate_error(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


async def handle_mutate_write_outline(
    graph_path: str | None,
    target: str,
    payload: str,
) -> dict[str, Any]:
    if not graph_path:
        return graph_missing_dict()
    outline = parse_json_object(payload, field_name="payload")
    from .graph_dispatch import _run_write_outline

    try:
        return await _run_write_outline(graph_path, target, outline)
    except ValueError as exc:
        return mutate_error(str(exc))
    except OSError as exc:
        return mutate_error(str(exc))
    except OCCConflictError as exc:
        return mutate_error(str(exc))


async def handle_mutate_edit_property(
    graph_path: str | None,
    target: str,
    payload: str,
) -> dict[str, Any]:
    if not graph_path:
        return {
            **graph_missing_dict(),
            "dry_run": True,
            "match_count": 0,
            "previews": [],
            "previous_size_bytes": 0,
            "current_size_bytes": 0,
            "lines_changed": 0,
        }
    try:
        normalized_target, page_notes = normalize_pipe_page_target(graph_path, target)
        pipe_target = resolve_pipe_target(graph_path, normalized_target)
    except ValueError as exc:
        return mutate_error(str(exc))
    target_parts = [p.strip() for p in pipe_target.split("|", 1)]
    if len(target_parts) != 2 or not target_parts[0] or not target_parts[1]:
        return {
            "ok": False,
            "error": "For edit_property, `target` must be `Page Title|block-uuid`.",
        }
    page_ref, block_uuid = target_parts[0], target_parts[1]
    prop_opts = parse_json_object(payload, field_name="payload")
    search = str(prop_opts.get("search", ""))
    replacement = str(prop_opts.get("replacement", ""))
    if not search:
        return {"ok": False, "error": "payload must include non-empty `search`."}

    try:
        page_path = graph_safe_page_path(graph_path, page_ref)
    except PathTraversalSecurityError as exc:
        return {"ok": False, "code": "security_violation", "error": str(exc)}
    except ValueError as exc:
        return mutate_error(str(exc))
    baseline_mtime = read_file_mtime_ns(page_path) if page_path.is_file() else None

    def _edit() -> dict[str, object]:
        return edit_block_property_lines(
            graph_path,
            page_ref,
            block_uuid,
            search,
            replacement,
            dry_run=bool(prop_opts.get("dry_run", True)),
            use_regex=bool(prop_opts.get("use_regex", False)),
            replace_all=bool(prop_opts.get("replace_all", False)),
            case_sensitive=bool(prop_opts.get("case_sensitive", True)),
            baseline_mtime=baseline_mtime,
        ).as_dict()

    edit_out = cast(dict[str, Any], await asyncio.to_thread(_edit))
    if page_notes:
        edit_out["warnings"] = page_notes
        for note in page_notes:
            logger.warning(note)
    return edit_out


async def handle_mutate_append_journal(
    graph_path: str | None,
    _target: str,
    payload: str,
) -> dict[str, Any]:
    if not graph_path:
        return graph_missing_dict()
    body = payload
    dry_run = True
    if payload.strip().startswith("{"):
        journal_opts = parse_json_object(payload, field_name="payload")
        body = str(journal_opts.get("markdown_body", ""))
        dry_run = bool(journal_opts.get("dry_run", True))
    bounds = markdown_append_bounds_violations(body)
    if bounds:
        return {
            "ok": False,
            "code": "payload_too_large",
            "error": "; ".join(bounds),
        }
    return await asyncio.to_thread(
        append_journal_markdown_section,
        graph_path,
        body,
        dry_run=dry_run,
    )


async def handle_mutate_inject_query(
    graph_path: str | None,
    target: str,
    payload: str,
) -> dict[str, Any]:
    from .graph_dispatch import (
        _headless_append_child,
        _occ_snapshot_for_block,
        _resolve_write_parent_target,
    )

    if not graph_path:
        return graph_missing_dict()

    try:
        parent_block, empty_page_title, inject_warnings = await asyncio.to_thread(
            _resolve_write_parent_target,
            graph_path,
            target,
        )
    except ValueError as exc:
        return mutate_error(str(exc))
    if empty_page_title:
        inject_warnings = [
            *inject_warnings,
            "inject_query requires a parent block; empty-page fallback is not supported.",
        ]
        return {
            "ok": False,
            "error": (
                f"Page `{empty_page_title}` has no outline blocks. "
                "Run `read_graph_data` / `xray_page` first, then pass a valid parent UUID or `[n]`."
            ),
            "warnings": inject_warnings,
        }
    if not parent_block:
        return mutate_error("Could not resolve parent block for inject_query.")
    inject_opts = parse_json_object(payload, field_name="payload")
    query_preset = inject_opts.get("query_preset")
    tag = inject_opts.get("tag")
    query_edn = str(inject_opts.get("query_edn", ""))
    dry_run = bool(inject_opts.get("dry_run", True))

    inner: str
    if query_preset and str(query_preset).strip():
        try:
            inner = resolve_advanced_query_preset(str(query_preset).strip(), tag=tag)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
    elif query_edn.strip():
        inner = query_edn.strip()
    else:
        return {
            "ok": False,
            "error": "payload must include `query_preset` or non-empty `query_edn`.",
        }

    sec = advanced_query_security_violations(inner)
    if sec:
        return {"ok": False, "error": "; ".join(sec)}

    try:
        markdown = wrap_logseq_advanced_query(inner)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if dry_run:
        dry_out: dict[str, Any] = {
            "ok": True,
            "dry_run": True,
            "markdown": markdown,
            "uuid": None,
            "routing_hint": routing_hint_for_write_outline(),
        }
        if inject_warnings:
            dry_out["warnings"] = inject_warnings
        return dry_out

    occ = _occ_snapshot_for_block(graph_path, parent_block)
    try:
        new_uuid = await asyncio.to_thread(
            _headless_append_child,
            graph_path,
            parent_block,
            markdown,
            occ=occ,
        )
    except (ValueError, OSError, OCCConflictError) as exc:
        return mutate_error(str(exc))

    inject_out: dict[str, Any] = {
        "ok": True,
        "dry_run": False,
        "uuid": new_uuid,
        "markdown": markdown,
        "routing_hint": routing_hint_for_write_outline(),
    }
    if inject_warnings:
        inject_out["warnings"] = inject_warnings
        for note in inject_warnings:
            logger.warning(note)
    return inject_out


async def handle_mutate_generate_moc(
    graph_path: str | None,
    target: str,
    payload: str,
) -> dict[str, Any]:
    if not graph_path:
        return graph_missing_dict()
    namespace = target.strip()
    if not namespace:
        return mutate_error("generate_moc requires `target` = namespace stem (e.g. `Project/Sub`).")
    moc_opts = parse_json_object(payload, field_name="payload") if payload.strip() else {}
    output_page_title = moc_opts.get("output_page_title")
    dry_run = bool(moc_opts.get("dry_run", True))
    return await asyncio.to_thread(
        write_moc_page,
        graph_path,
        namespace,
        output_page_title=str(output_page_title) if output_page_title else None,
        dry_run=dry_run,
    )


_MUTATE_HANDLERS: dict[MutateGraphAction, MutateHandler] = {
    "write_outline": handle_mutate_write_outline,
    "edit_property": handle_mutate_edit_property,
    "append_journal": handle_mutate_append_journal,
    "inject_query": handle_mutate_inject_query,
    "generate_moc": handle_mutate_generate_moc,
}


async def dispatch_mutate_target(
    action: MutateGraphAction,
    target: str,
    payload: str,
) -> dict[str, Any]:
    """Route ``mutate_graph`` by ``action`` (headless on-disk writes)."""
    graph_path = graph_path_from_env()
    handler = _MUTATE_HANDLERS[action]
    return await handler(graph_path, target, payload)


__all__ = [
    "dispatch_mutate_target",
    "handle_mutate_append_journal",
    "handle_mutate_edit_property",
    "handle_mutate_generate_moc",
    "handle_mutate_inject_query",
    "handle_mutate_write_outline",
    "mutate_error",
]
