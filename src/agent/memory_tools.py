"""MCP memory tools: persist user facts into the in-graph identity config page."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

from ..daemon.ast_cache import get_graph_ast_cache
from ..daemon.config_layer import (
    CONSTRAINTS_HEADING,
    TELOS_HEADING,
    WRITE_PAGE_TITLE,
    find_constraints_heading_node,
    refresh_identity_config,
    resolve_identity_config_path,
)
from ..graph.graph_path_validate import validate_logseq_graph_path
from ..graph.path_sandbox import read_graph_file_text
from .graph_dispatch import _headless_append_child
from .graph_tool_helpers import graph_missing_text, graph_path_from_env
from .routing_hint import routing_hint_for_write_outline

_CONFIG_PAGE_SKELETON = f"""- # {TELOS_HEADING}

- # {CONSTRAINTS_HEADING}

"""


def _require_graph_root() -> Path:
    raw = graph_path_from_env()
    if not raw:
        msg = graph_missing_text()
        raise ValueError(msg)
    return validate_logseq_graph_path(raw)


def _ensure_config_page(graph_root: Path) -> Path:
    """Create ``pages/matryca-config.md`` with base headings when missing.

    Uses an exclusive create (``O_CREAT | O_EXCL``) so two concurrent
    ``store_fact`` calls racing on a missing config page can't clobber
    each other's write with the skeleton — the loser simply sees
    ``FileExistsError`` and reads back whatever the winner wrote.
    """
    path = resolve_identity_config_path(graph_root, for_write=True)
    if path.is_file():
        content = read_graph_file_text(path, graph_root, encoding="utf-8")
        if content.strip():
            return path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        pass
    else:
        try:
            os.write(fd, _CONFIG_PAGE_SKELETON.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
    get_graph_ast_cache(graph_root).apply_file_event(path, "modified")
    refresh_identity_config(graph_root, path)
    return path


async def dispatch_store_fact(fact: str) -> dict[str, Any]:
    """Append ``fact`` under ``- # AI Constraints`` on ``pages/matryca-config.md``."""
    cleaned = fact.strip()
    if not cleaned:
        msg = "fact must be a non-empty string"
        raise ValueError(msg)

    graph_root = _require_graph_root()
    config_path = _ensure_config_page(graph_root)
    cache = get_graph_ast_cache(graph_root)
    cache.bootstrap()

    located = find_constraints_heading_node(graph_root)
    if located is None:
        cache.apply_file_event(config_path, "modified")
        located = find_constraints_heading_node(graph_root)
    if located is None:
        msg = (
            f"Could not find '- # {CONSTRAINTS_HEADING}' on page {WRITE_PAGE_TITLE}; "
            "check pages/matryca-config.md structure"
        )
        raise ValueError(msg)

    _page, constraints_node = located
    parent_uuid = constraints_node.uuid
    if not parent_uuid:
        msg = "AI Constraints heading has no block UUID in the graph index"
        raise ValueError(msg)

    new_uuid = _headless_append_child(
        graph_root,
        parent_uuid,
        cleaned,
        properties={"stored::": "matryca-plumber"},
    )

    cache.apply_file_event(config_path, "modified")
    refresh_identity_config(graph_root, config_path)

    logger.bind(page=WRITE_PAGE_TITLE, block_uuid=new_uuid).info("store_fact persisted preference")
    return {
        "ok": True,
        "page": WRITE_PAGE_TITLE,
        "path": str(config_path.relative_to(graph_root)),
        "block_uuid": new_uuid,
        "fact": cleaned,
        "routing_hint": routing_hint_for_write_outline(),
    }


__all__ = ["dispatch_store_fact"]
