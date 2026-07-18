"""Markdown-backed ``GraphReadPort`` adapter (v2 Phase 1)."""

from __future__ import annotations

from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root
from ..graph.ports.read import GraphReadPort
from ..rag.matryca_hooks import get_page_spatial_context
from .graph_tool_helpers import read_subtree_markdown
from .shadow_graph_repository import ShadowGraphRepository, shadow_read_port_ready


class MarkdownGraphRepository:
    """Delegates read operations to existing graph helpers (default v1 backend)."""

    def read_subtree_markdown(self, graph_root: Path, query: str) -> str:
        return read_subtree_markdown(str(graph_root), query)

    async def read_page_spatial_markdown(self, graph_root: Path, title: str) -> str:
        return await get_page_spatial_context(title, str(graph_root))


def get_graph_read_port(graph_root: Path | None = None) -> GraphReadPort:
    """Return the active read port for ``graph_root`` (shadow when healthy, else Markdown)."""
    if graph_root is not None and shadow_read_port_ready(graph_root):
        return ShadowGraphRepository()
    if graph_root is not None:
        _ = resolved_graph_root(graph_root)
    return MarkdownGraphRepository()


__all__ = [
    "MarkdownGraphRepository",
    "get_graph_read_port",
]
