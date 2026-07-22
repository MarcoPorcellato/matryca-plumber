"""Atomic ``LogseqGraph`` construction backed by bounded page parsing.

This adapter turns a successful isolated Stack-Machine page parse into the
same graph-native page shape produced by ``StackMachineParser.parse_page_file``.
It also centralizes the parser package's currently-private graph-index helpers,
so the cache integration has one compatibility boundary to audit.

Failure values contain only a content hash and coarse measurements.  They
intentionally never expose the source path or Markdown body.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from logseq_matryca_parser.graph import (
    LogseqGraph,
    _build_backlink_registry,
    _build_lower_title_map,
    _build_node_registry_from_pages,
    _enrich_pages_index,
)
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from logseq_matryca_parser.logseq_markdown import detect_tab_size_from_markdown
from logseq_matryca_parser.logseq_paths import (
    derive_page_title_from_source_path,
)

from .bounded_page_parse import (
    BoundedParseResult,
    parse_page_text_bounded,
)
from .path_sandbox import assert_path_within_graph, read_graph_file_text


@dataclass(frozen=True, slots=True)
class BoundedGraphParseFailure:
    """Content-free result for a failed bounded file parse.

    ``source_path`` and page text are deliberately absent: callers may record
    this value in operational diagnostics without disclosing vault content.
    """

    content_hash: str
    byte_count: int
    line_count: int
    timed_out: bool
    elapsed_s: float
    error: str


@dataclass(frozen=True, slots=True)
class BoundedGraphPageResult:
    """Either a graph-native page or a content-free parse failure."""

    page: LogseqPage | None = field(default=None, repr=False)
    failure: BoundedGraphParseFailure | None = None

    @property
    def ok(self) -> bool:
        """Whether a page was parsed and hydrated successfully."""
        return self.page is not None and self.failure is None


def _apply_source_path(nodes: list[LogseqNode], source_path: str) -> list[LogseqNode]:
    """Recursively attach the owning file path, matching parser behavior."""
    return [
        node.model_copy(
            update={
                "source_path": source_path,
                "children": _apply_source_path(node.children, source_path),
            }
        )
        for node in nodes
    ]


def _failure_from_bounded_result(result: BoundedParseResult) -> BoundedGraphPageResult:
    """Project the worker result to the content-free cache-facing error type."""
    return BoundedGraphPageResult(
        failure=BoundedGraphParseFailure(
            content_hash=result.content_hash,
            byte_count=result.byte_count,
            line_count=result.line_count,
            timed_out=result.timed_out,
            elapsed_s=result.elapsed_s,
            error=result.error or "parse_error",
        )
    )


def _read_failure() -> BoundedGraphPageResult:
    """Return a path-free read failure when a source file cannot be opened."""
    return BoundedGraphPageResult(
        failure=BoundedGraphParseFailure(
            content_hash="",
            byte_count=0,
            line_count=0,
            timed_out=False,
            elapsed_s=0.0,
            error="read_error",
        )
    )


def parse_graph_page_bounded(
    source_path: Path,
    graph_root: Path,
    *,
    timeout_s: float | None = None,
) -> BoundedGraphPageResult:
    """Read and bounded-parse one graph Markdown file in Stack-Machine mode.

    On success the returned page has the same source metadata as
    ``StackMachineParser.parse_page_file``.  On timeout or parser/read error,
    the failure is safe to log and has no path or body field.
    """
    root = graph_root.expanduser().resolve(strict=False)
    try:
        resolved = assert_path_within_graph(source_path, root)
        text = read_graph_file_text(resolved, root, encoding="utf-8-sig")
        stat = resolved.stat()
    except OSError:
        return _read_failure()

    page_title = derive_page_title_from_source_path(resolved)
    detected_tab = detect_tab_size_from_markdown(text)
    parsed = parse_page_text_bounded(
        text,
        mode="stack",
        page_title=page_title,
        tab_size=detected_tab,
        timeout_s=timeout_s,
    )
    if not parsed.ok or not isinstance(parsed.page, LogseqPage):
        return _failure_from_bounded_result(parsed)

    source_path_text = str(resolved)
    page = parsed.page
    assert isinstance(page, LogseqPage)
    created_at = page.created_at if page.created_at is not None else int(os.path.getctime(resolved))
    updated_at = page.updated_at if page.updated_at is not None else int(stat.st_mtime)
    return BoundedGraphPageResult(
        page=page.model_copy(
            update={
                "source_path": source_path_text,
                "graph_root": str(root),
                "created_at": created_at,
                "updated_at": updated_at,
                "tab_size": detected_tab,
                "root_nodes": _apply_source_path(page.root_nodes, source_path_text),
            }
        )
    )


def build_graph_from_bounded_pages(
    graph_root: Path,
    pages: Iterable[LogseqPage],
) -> LogseqGraph:
    """Build a fully indexed graph from parsed pages without mutating inputs.

    The private helper imports are intentionally centralized in this module;
    they reproduce ``LogseqGraph.load_directory`` index construction exactly.
    """
    indexed_pages: dict[str, LogseqPage] = {}
    for page in pages:
        indexed_pages[page.title] = page
    _enrich_pages_index(indexed_pages)
    return LogseqGraph(
        graph_path=graph_root.expanduser().resolve(strict=False),
        pages=indexed_pages,
        node_registry=_build_node_registry_from_pages(indexed_pages),
        backlink_registry=_build_backlink_registry(indexed_pages),
        lower_title_map=_build_lower_title_map(indexed_pages),
    )


def replace_graph_page_by_source_path(
    graph: LogseqGraph,
    source_path: Path,
    replacement: LogseqPage | None,
) -> LogseqGraph:
    """Return a new complete graph with one source path replaced or removed.

    ``graph`` and its index registries are never mutated.  Alias keys are
    eliminated by iterating canonical pages before rebuilding all indexes.
    """
    resolved = source_path.expanduser().resolve(strict=False)
    kept: list[LogseqPage] = []
    for page in graph.iter_canonical_pages():
        page_source = page.source_path
        if page_source and Path(page_source).resolve(strict=False) == resolved:
            continue
        kept.append(page)
    if replacement is not None:
        kept.append(replacement)
    return build_graph_from_bounded_pages(graph.graph_path, kept)


__all__ = [
    "BoundedGraphPageResult",
    "BoundedGraphParseFailure",
    "build_graph_from_bounded_pages",
    "parse_graph_page_bounded",
    "replace_graph_page_by_source_path",
]
