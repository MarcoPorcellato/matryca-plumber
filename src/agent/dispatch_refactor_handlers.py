"""``refactor_blocks`` handlers — one function per ``RefactorBlocksAction`` (issue #59 slice)."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from ..graph.flashcards import append_logseq_flashcards_under_block
from ..graph.reparent_blocks import refactor_logseq_blocks as run_reparent_logseq_blocks
from ..graph.split_large_blocks import refactor_large_blocks as run_refactor_large_blocks
from ..utils.json_repair import loads_repaired_json
from .alias_state import resolve_pipe_target, resolve_target
from .dispatch_mutate_handlers import mutate_error
from .graph_tool_helpers import (
    RefactorBlocksAction,
    graph_missing_dict,
    graph_path_from_env,
    parse_optional_json_query,
)
from .page_input_normalizer import normalize_page_ref_or_raw, normalize_pipe_page_target


async def handle_refactor_split_large(
    graph_path: str,
    resolved_uuid: str,
    refactor_opts: dict[str, Any],
    refactor_notes: list[str],
) -> dict[str, Any]:
    dry_run = bool(refactor_opts.get("dry_run", True))
    page_ref = resolved_uuid.strip() or None
    if page_ref:
        page_norm = normalize_page_ref_or_raw(graph_path, page_ref)
        page_ref = page_norm.canonical_title
        refactor_notes.extend(page_norm.resolution_notes)
    min_chars = max(50, int(refactor_opts.get("min_chars", 400)))
    max_blocks = max(1, min(int(refactor_opts.get("max_blocks", 25)), 100))
    git_snap: dict[str, object] = (
        {"skipped": True, "reason": "dry_run"}
        if dry_run
        else {
            "committed": True,
            "skipped": False,
            "reason": "post-write robot commits via hooks",
        }
    )

    def _split() -> dict[str, Any]:
        return run_refactor_large_blocks(
            graph_path,
            page_ref=page_ref,
            min_chars=min_chars,
            max_blocks=max_blocks,
            dry_run=dry_run,
        ).as_dict()

    split_out = await asyncio.to_thread(_split)
    split_out["git_snapshot"] = git_snap
    if refactor_notes:
        split_out["warnings"] = refactor_notes
    return split_out


async def handle_refactor_reparent(
    graph_path: str,
    resolved_uuid: str,
    refactor_opts: dict[str, Any],
    payload: str,
    refactor_notes: list[str],
) -> dict[str, Any]:
    dry_run = bool(refactor_opts.get("dry_run", True))
    reparent_page = resolved_uuid.strip()
    if reparent_page:
        page_norm = normalize_page_ref_or_raw(graph_path, reparent_page)
        reparent_page = page_norm.canonical_title
        refactor_notes.extend(page_norm.resolution_notes)
    if not reparent_page:
        return {"ok": False, "error": "For reparent, `target_uuid` must be the page title."}
    groups_raw = refactor_opts.get("groups")
    if groups_raw is None and payload.strip().startswith("["):
        groups_raw = loads_repaired_json(payload)
    if not isinstance(groups_raw, list):
        return {
            "ok": False,
            "error": "For reparent, `payload` must be a JSON array of reparent groups.",
        }
    groups = cast(list[dict[str, Any]], groups_raw)
    reparent_git: dict[str, object] = (
        {"skipped": True, "reason": "dry_run"}
        if dry_run
        else {
            "committed": True,
            "skipped": False,
            "reason": "post-write robot commits via hooks",
        }
    )

    def _reparent() -> dict[str, Any]:
        return run_reparent_logseq_blocks(
            graph_path,
            reparent_page,
            groups,
            dry_run=dry_run,
        ).as_dict()

    reparent_out = await asyncio.to_thread(_reparent)
    reparent_out["git_snapshot"] = reparent_git
    if refactor_notes:
        reparent_out["warnings"] = refactor_notes
    return reparent_out


async def handle_refactor_generate_flashcards(
    graph_path: str,
    resolved_uuid: str,
    refactor_opts: dict[str, Any],
    refactor_notes: list[str],
) -> dict[str, Any]:
    dry_run = bool(refactor_opts.get("dry_run", True))
    flash_parts = [p.strip() for p in resolved_uuid.split("|", 1)]
    if len(flash_parts) != 2 or not flash_parts[0] or not flash_parts[1]:
        return {
            "ok": False,
            "error": (
                "For generate_flashcards, `target_uuid` must be `Page Title|source-block-uuid`."
            ),
        }
    page_ref, source_uuid = flash_parts[0], flash_parts[1]
    page_norm = normalize_page_ref_or_raw(graph_path, page_ref)
    page_ref = page_norm.canonical_title
    refactor_notes.extend(page_norm.resolution_notes)
    max_cards = max(1, min(int(refactor_opts.get("max_cards", 30)), 200))

    def _flash() -> dict[str, Any]:
        return append_logseq_flashcards_under_block(
            graph_path,
            page_ref,
            source_uuid,
            max_cards=max_cards,
            dry_run=dry_run,
        ).as_dict()

    flash_out = await asyncio.to_thread(_flash)
    if refactor_notes:
        flash_out["warnings"] = refactor_notes
    return flash_out


async def dispatch_refactor_target(
    action: RefactorBlocksAction,
    target_uuid: str,
    payload: str = "",
) -> dict[str, Any]:
    """Route ``refactor_blocks`` by ``action`` (headless on-disk rewrites)."""
    graph_path = graph_path_from_env()
    if not graph_path:
        return graph_missing_dict()

    refactor_opts = parse_optional_json_query(payload)
    refactor_notes: list[str] = []
    try:
        resolved_uuid = target_uuid
        if "|" in target_uuid:
            normalized_target, refactor_notes = normalize_pipe_page_target(
                graph_path,
                target_uuid,
            )
            resolved_uuid = resolve_pipe_target(graph_path, normalized_target)
        elif target_uuid.strip():
            page_norm = normalize_page_ref_or_raw(graph_path, target_uuid)
            refactor_notes.extend(page_norm.resolution_notes)
            resolved_uuid = resolve_target(graph_path, page_norm.canonical_title)
    except ValueError as exc:
        return mutate_error(str(exc))

    if action == "split_large":
        return await handle_refactor_split_large(
            graph_path,
            resolved_uuid,
            refactor_opts,
            refactor_notes,
        )
    if action == "reparent":
        return await handle_refactor_reparent(
            graph_path,
            resolved_uuid,
            refactor_opts,
            payload,
            refactor_notes,
        )
    return await handle_refactor_generate_flashcards(
        graph_path,
        resolved_uuid,
        refactor_opts,
        refactor_notes,
    )


__all__ = [
    "dispatch_refactor_target",
    "handle_refactor_generate_flashcards",
    "handle_refactor_reparent",
    "handle_refactor_split_large",
]
