"""Semantic macro: bundle page + block context for LLM agents (#16)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ..graph.path_sandbox import graph_safe_page_path
from ..rag.matryca_hooks import get_page_spatial_context
from .graph_tool_helpers import (
    graph_missing_dict,
    graph_path_from_env,
    read_subtree_markdown,
)


async def _load_subtree_context(root: str, raw: str) -> dict[str, Any]:
    """Handle a ``Page Title|block-uuid`` pipe query."""
    page_part, block_part = [p.strip() for p in raw.split("|", 1)]
    if not page_part or not block_part:
        return {"ok": False, "error": "Invalid `Page Title|block-uuid` query."}
    try:
        subtree_md = await asyncio.to_thread(read_subtree_markdown, root, raw)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "mode": "subtree",
        "page": page_part,
        "block_uuid": block_part,
        "markdown": subtree_md,
    }


async def load_agent_context(
    query: str,
    *,
    graph_path: str | None = None,
) -> dict[str, Any]:
    """High-level context bundle from a page title or ``Page|uuid`` pipe target."""
    root = (graph_path or graph_path_from_env()).strip()
    if not root:
        return graph_missing_dict()

    raw = query.strip()
    if not raw:
        return {
            "ok": False,
            "error": "Set query to a page title or `Page Title|block-uuid` for subtree focus.",
        }

    if "|" in raw:
        return await _load_subtree_context(root, raw)

    try:
        page_md = await get_page_spatial_context(raw, root)
    except FileNotFoundError:
        return {"ok": False, "error": f"Page not found: {raw!r}"}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    def _relative_path() -> str | None:
        graph_root = Path(root).expanduser().resolve(strict=False)
        try:
            page_path = graph_safe_page_path(graph_root, raw)
        except ValueError:
            return None
        if not page_path.is_file():
            return None
        return page_path.relative_to(graph_root).as_posix()

    rel = await asyncio.to_thread(_relative_path)

    return {
        "ok": True,
        "mode": "page",
        "page": raw,
        "relative_path": rel,
        "markdown": page_md,
    }


def format_context_load_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["format_context_load_json", "load_agent_context"]
