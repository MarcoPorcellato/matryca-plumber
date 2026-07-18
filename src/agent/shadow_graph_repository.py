"""Shadow-backed ``GraphReadPort`` adapter (v2 PR-C2 / #255)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loguru import logger

from ..graph.path_sandbox import resolved_graph_root
from ..rag.matryca_hooks import get_page_spatial_context
from ..shadow.config import shadow_db_enabled
from ..shadow.connection import open_shadow_db
from ..shadow.health import ShadowHealthState, resolve_shadow_health
from ..shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid
from .graph_tool_helpers import parse_optional_json_query
from .page_input_normalizer import format_resolution_notes_footer, normalize_page_ref_or_raw

_HEADING_BULLET = re.compile(r"^(\s*)-\s+(.*)$")


def _parse_subtree_query(
    graph_path: str,
    query: str,
) -> tuple[str, str, str, list[str]]:
    from .alias_state import resolve_pipe_target
    from .page_input_normalizer import normalize_pipe_page_target

    normalized_query, page_notes = normalize_pipe_page_target(graph_path, query)
    resolved_query = resolve_pipe_target(graph_path, normalized_query)
    opts: dict[str, Any] = {}
    page_ref = resolved_query
    block_uuid = ""
    if resolved_query.strip().startswith("{"):
        opts = parse_optional_json_query(resolved_query)
        raw_page = str(opts.get("page", "")).strip()
        page_norm = normalize_page_ref_or_raw(graph_path, raw_page) if raw_page else None
        page_ref = page_norm.canonical_title if page_norm else ""
        if page_norm:
            page_notes.extend(page_norm.resolution_notes)
        block_uuid = str(opts.get("block_uuid", opts.get("uuid", ""))).strip()
    else:
        parts = [p.strip() for p in resolved_query.split("|", 1)]
        if len(parts) == 2:
            page_ref, block_uuid = parts[0], parts[1]
    heading_filter = str(opts.get("heading", "")).strip() if opts else ""
    return page_ref, block_uuid, heading_filter, page_notes


def _subtree_not_found_message(page_ref: str, block_uuid: str) -> str:
    return (
        f"Block `{block_uuid}` not found on page `{page_ref}`. "
        "Confirm the UUID matches an `id::` line on that page."
    )


def _apply_heading_filter(excerpt: str, heading_filter: str) -> str:
    if not heading_filter:
        return excerpt
    heading_needle = heading_filter.lstrip("#").strip().lower()
    lines = excerpt.splitlines(keepends=True)
    filtered: list[str] = []
    include = False
    heading_indent: int | None = None
    for line in lines:
        stripped_line = line.rstrip("\n")
        match = _HEADING_BULLET.match(stripped_line)
        if match:
            indent = len(match.group(1))
            text_part = match.group(2).strip()
            if not include:
                if text_part.lstrip("#").strip().lower() == heading_needle:
                    include = True
                    heading_indent = indent
                    filtered = [line]
                continue
            if heading_indent is not None and indent > heading_indent:
                filtered.append(line)
            else:
                break
        elif include:
            filtered.append(line)
    return "".join(filtered) if filtered else excerpt


def _format_subtree_envelope(
    page_ref: str,
    block_uuid: str,
    excerpt: str,
    page_notes: list[str],
) -> str:
    body = (
        "# Subtree excerpt\n\n"
        f"- **Page:** [[{page_ref}]]\n"
        f"- **Block UUID:** `{block_uuid}`\n\n"
        f"```markdown\n{excerpt.rstrip()}\n```\n"
    )
    return body + format_resolution_notes_footer(page_notes)


class ShadowGraphRepository:
    """Read subtree excerpts from shadow CTE; spatial reads stay on Markdown."""

    def __init__(self) -> None:
        from .markdown_graph_repository import MarkdownGraphRepository

        self._markdown = MarkdownGraphRepository()

    def read_subtree_markdown(self, graph_root: Path, query: str) -> str:
        root = resolved_graph_root(graph_root)
        if not shadow_db_enabled() or resolve_shadow_health(root) != ShadowHealthState.READY:
            return self._markdown.read_subtree_markdown(graph_root, query)

        try:
            page_ref, block_uuid, heading_filter, page_notes = _parse_subtree_query(
                str(root),
                query,
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if not page_ref or not block_uuid:
            msg = (
                "Invalid subtree query. Use `Page Title|block-uuid` or JSON "
                '`{"page":"...","block_uuid":"...","heading":"optional"}`.'
            )
            raise ValueError(msg)

        try:
            conn = open_shadow_db(root)
            try:
                result = query_subtree_by_block_uuid(conn, block_uuid)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — shadow backend failure → markdown fallback
            logger.exception("Shadow subtree read failed; falling back to MarkdownGraphRepository")
            return self._markdown.read_subtree_markdown(graph_root, query)

        if result.status == SubtreeStatus.NOT_FOUND:
            msg = _subtree_not_found_message(page_ref, block_uuid)
            return msg + format_resolution_notes_footer(page_notes)

        if result.status == SubtreeStatus.INCONSISTENT:
            logger.warning(
                "Shadow subtree inconsistent for {} on {}; falling back to Markdown",
                block_uuid,
                page_ref,
            )
            return self._markdown.read_subtree_markdown(graph_root, query)

        excerpt = _apply_heading_filter(result.excerpt_markdown, heading_filter)
        return _format_subtree_envelope(page_ref, block_uuid, excerpt, page_notes)

    async def read_page_spatial_markdown(self, graph_root: Path, title: str) -> str:
        return await get_page_spatial_context(title, str(graph_root))


def shadow_read_port_ready(graph_root: Path | str) -> bool:
    """True when shadow subtree reads may use the CTE adapter."""
    if not shadow_db_enabled():
        return False
    root = resolved_graph_root(graph_root)
    return resolve_shadow_health(root) == ShadowHealthState.READY


__all__ = [
    "ShadowGraphRepository",
    "shadow_read_port_ready",
]
