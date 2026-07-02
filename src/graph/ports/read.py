"""Read-side port for GraphRepository (v2 Phase 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GraphReadPort(Protocol):
    """Narrow read contract for Markdown (v1) and shadow (v2-alpha) backends."""

    def read_subtree_markdown(self, graph_root: Path, query: str) -> str:
        """Return Markdown excerpt for a block subtree query."""
        ...

    async def read_page_spatial_markdown(self, graph_root: Path, title: str) -> str:
        """Return spatial parser context for a page title."""
        ...
