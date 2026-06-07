"""In-memory ``LogseqGraph`` cache with per-file delta reload."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Literal, cast

from logseq_matryca_parser.graph import LogseqGraph
from logseq_matryca_parser.logos_core import LogseqNode
from loguru import logger

FileEventKind = Literal["created", "modified", "deleted"]

_cache_lock = threading.Lock()
_caches: dict[str, GraphAstCache] = {}


def count_graph_markdown_files(graph_root: Path) -> int:
    """Count ``pages/`` and ``journals/`` Markdown files for bootstrap telemetry."""
    root = graph_root.expanduser().resolve(strict=False)
    total = 0
    for subdir in ("pages", "journals"):
        base = root / subdir
        if base.is_dir():
            total += sum(1 for _ in base.rglob("*.md"))
    return total


class GraphAstCache:
    """Thread-safe in-memory graph index for MCP and daemon reads."""

    def __init__(self, graph_root: Path) -> None:
        self.graph_root = graph_root.expanduser().resolve(strict=False)
        self._lock = threading.RLock()
        self._graph: LogseqGraph | None = None

    def bootstrap(self) -> LogseqGraph:
        """Full vault load on first access (idempotent, thread-safe)."""
        with self._lock:
            if self._graph is None:
                markdown_files = count_graph_markdown_files(self.graph_root)
                logger.bind(
                    graph=str(self.graph_root),
                    markdown_files=markdown_files,
                    phase="start",
                ).info("AST cache bootstrap started")
                started = time.perf_counter()
                self._graph = LogseqGraph.load_directory(self.graph_root)
                elapsed_s = round(time.perf_counter() - started, 3)
                page_count = len(self._graph.pages)
                logger.bind(
                    graph=str(self.graph_root),
                    markdown_files=markdown_files,
                    pages_indexed=page_count,
                    duration_s=elapsed_s,
                    phase="complete",
                ).info("AST cache bootstrap complete")
            return self._graph

    def get_graph(self) -> LogseqGraph:
        """Return the cached graph, bootstrapping on first access."""
        return self.bootstrap()

    def apply_file_event(self, path: Path, kind: FileEventKind) -> None:
        """Apply a filesystem delta to the in-memory index."""
        resolved = path.expanduser().resolve(strict=False)
        with self._lock:
            graph = self.bootstrap()
            if kind == "deleted" or not resolved.is_file():
                logger.bind(path=str(resolved), kind=kind).debug(
                    "AST cache full reload after delete or missing file",
                )
                self._graph = LogseqGraph.load_directory(self.graph_root)
                return
            try:
                graph.invalidate_and_reload_page(resolved)
            except Exception as exc:  # noqa: BLE001 - parser edge cases
                logger.warning(
                    "AST cache page reload failed for {} ({}); full reload",
                    resolved,
                    exc,
                )
                self._graph = LogseqGraph.load_directory(self.graph_root)

    def get_block_by_uuid(self, block_uuid: str) -> LogseqNode | None:
        """Resolve a block by registry UUID or on-disk ``id::`` embed ref."""
        graph = self.get_graph()
        node = graph.get_node_by_uuid(block_uuid)
        if node is not None:
            return node
        return graph.get_node_by_embed_ref(block_uuid)

    def get_blocks_by_tag(self, tag: str) -> list[LogseqNode]:
        """Return nodes tagged with ``tag`` (without leading ``#``)."""
        normalized = tag.lstrip("#").strip()
        if not normalized:
            return []
        return cast(list[LogseqNode], self.get_graph().get_nodes_by_tag(normalized))


def get_graph_ast_cache(graph_root: str | Path) -> GraphAstCache:
    """Process singleton keyed by resolved graph root path."""
    key = str(Path(graph_root).expanduser().resolve(strict=False))
    with _cache_lock:
        cache = _caches.get(key)
        if cache is None:
            cache = GraphAstCache(Path(key))
            _caches[key] = cache
        return cache


def clear_graph_ast_cache() -> None:
    """Drop all caches (tests)."""
    with _cache_lock:
        _caches.clear()


__all__ = [
    "FileEventKind",
    "GraphAstCache",
    "clear_graph_ast_cache",
    "count_graph_markdown_files",
    "get_graph_ast_cache",
]
