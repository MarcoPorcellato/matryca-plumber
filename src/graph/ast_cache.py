"""In-memory ``LogseqGraph`` cache with per-file delta reload."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Literal, cast

from logseq_matryca_parser.graph import LogseqGraph
from logseq_matryca_parser.logos_core import LogseqNode
from logseq_matryca_parser.logseq_paths import discover_graph_files
from loguru import logger

from .bounded_ast_graph import (
    BoundedGraphParseFailure,
    build_graph_from_bounded_pages,
    parse_graph_page_bounded,
    replace_graph_page_by_source_path,
)
from .bounded_page_parse import reset_bounded_page_parse_worker_for_tests

FileEventKind = Literal["created", "modified", "deleted"]

_cache_lock = threading.Lock()
_caches: dict[str, GraphAstCache] = {}


class GraphAstParseError(RuntimeError):
    """A bounded page parse failed without exposing its path or content."""

    def __init__(self, failure: BoundedGraphParseFailure) -> None:
        self.failure = failure
        super().__init__(
            "AST page parse failed "
            f"(error={failure.error}, content_hash={failure.content_hash}, "
            f"bytes={failure.byte_count}, lines={failure.line_count}, "
            f"mode=stack)"
        )


def count_graph_markdown_files(graph_root: Path) -> int:
    """Count sovereign Markdown files under ``pages/`` and ``journals/`` (parser exclusions)."""
    root = graph_root.expanduser().resolve(strict=False)
    return len(discover_graph_files(root))


class GraphAstCache:
    """Thread-safe in-memory graph index for MCP and daemon reads."""

    def __init__(self, graph_root: Path) -> None:
        self.graph_root = graph_root.expanduser().resolve(strict=False)
        self._lock = threading.RLock()
        self._graph: LogseqGraph | None = None

    def bootstrap(self) -> LogseqGraph:
        """Build and atomically publish a complete bounded-parsed graph."""
        with self._lock:
            if self._graph is None:
                markdown_paths = discover_graph_files(self.graph_root)
                markdown_files = len(markdown_paths)
                logger.bind(
                    graph=str(self.graph_root),
                    markdown_files=markdown_files,
                    phase="start",
                ).info("AST cache bootstrap started")
                started = time.perf_counter()
                pages = []
                for path in markdown_paths:
                    result = parse_graph_page_bounded(path, self.graph_root)
                    if result.page is None or result.failure is not None:
                        failure = result.failure or BoundedGraphParseFailure(
                            content_hash="",
                            byte_count=0,
                            line_count=0,
                            timed_out=False,
                            elapsed_s=0.0,
                            error="parse_error",
                        )
                        raise GraphAstParseError(failure)
                    pages.append(result.page)
                staged = build_graph_from_bounded_pages(self.graph_root, pages)
                self._graph = staged
                elapsed_s = round(time.perf_counter() - started, 3)
                page_count = len(staged.pages)
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
        """Atomically apply a bounded filesystem delta to the in-memory index."""
        resolved = path.expanduser().resolve(strict=False)
        with self._lock:
            graph = self.bootstrap()
            if kind == "deleted" or not resolved.is_file():
                self._graph = replace_graph_page_by_source_path(graph, resolved, None)
                return
            result = parse_graph_page_bounded(resolved, self.graph_root)
            if result.page is None or result.failure is not None:
                failure = result.failure
                logger.bind(
                    content_hash=failure.content_hash if failure else "",
                    byte_count=failure.byte_count if failure else 0,
                    line_count=failure.line_count if failure else 0,
                    mode="stack",
                    error=failure.error if failure else "parse_error",
                ).warning("AST cache page reload rejected; preserving last complete graph")
                return
            try:
                staged = replace_graph_page_by_source_path(graph, resolved, result.page)
            except Exception as exc:  # noqa: BLE001 - parser compatibility boundary
                logger.bind(error=type(exc).__name__).warning(
                    "AST cache page reindex failed; preserving last complete graph"
                )
                return
            self._graph = staged

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


_ast_write_bridge_registered = False
_ast_bridge_lock = threading.Lock()


def _ensure_ast_page_written_bridge() -> None:
    """Register AST delta refresh on the graph-local post-write port (once)."""
    global _ast_write_bridge_registered
    with _ast_bridge_lock:
        if _ast_write_bridge_registered:
            return
        from .post_write import PageWrittenEvent, register_page_written_handler

        def _on_ast_refresh(event: PageWrittenEvent) -> None:
            if event.path.suffix.lower() != ".md":
                return
            try:
                get_graph_ast_cache(event.graph_root).apply_file_event(event.path, "modified")
            except Exception:  # noqa: BLE001
                logger.exception("AST cache refresh failed after write to {}", event.path)

        register_page_written_handler(_on_ast_refresh)
        _ast_write_bridge_registered = True


def get_graph_ast_cache(graph_root: str | Path) -> GraphAstCache:
    """Process singleton keyed by resolved graph root path."""
    _ensure_ast_page_written_bridge()
    key = str(Path(graph_root).expanduser().resolve(strict=False))
    with _cache_lock:
        cache = _caches.get(key)
        if cache is None:
            cache = GraphAstCache(Path(key))
            _caches[key] = cache
        return cache


def clear_graph_ast_cache() -> None:
    """Drop all caches (tests)."""
    global _ast_write_bridge_registered
    with _cache_lock:
        _caches.clear()
    with _ast_bridge_lock:
        _ast_write_bridge_registered = False
    reset_bounded_page_parse_worker_for_tests()


__all__ = [
    "FileEventKind",
    "GraphAstCache",
    "GraphAstParseError",
    "clear_graph_ast_cache",
    "count_graph_markdown_files",
    "get_graph_ast_cache",
]
