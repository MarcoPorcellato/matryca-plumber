"""Private Parser 1.9 adapter for one bounded, complete OG topology snapshot."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from logseq_matryca_parser.graph import LogseqGraph, SnapshotPage
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage

from ..graph.ports.session_read import OgGraphTopologyPort
from ..graph.session_read_models import GraphSessionReadError
from ..graph.session_topology_models import (
    GraphTopologyNode,
    GraphTopologyProvenance,
    GraphTopologyReference,
    GraphTopologyResult,
    OgTopologySourceSnapshot,
)
from .og_parser_identity_adapter import _OgSnapshotReadError, _opaque_digest
from .og_topology_snapshot import MAX_CAPTURE_BYTES as MAX_OG_TOPOLOGY_SNAPSHOT_BYTES
from .og_topology_snapshot import MAX_CAPTURE_FILE_BYTES as MAX_OG_TOPOLOGY_SNAPSHOT_PAGE_BYTES
from .og_topology_snapshot import MAX_CAPTURE_FILES as MAX_OG_TOPOLOGY_SNAPSHOT_PAGES
from .og_topology_snapshot import (
    _admit_og_topology_root,
    capture_og_topology,
    verify_og_topology_capture,
)

MAX_OG_TOPOLOGY_NODES = 1024
MAX_OG_TOPOLOGY_EDGES = 4096
MAX_OG_TOPOLOGY_BLOCK_DEPTH = 64


def _opaque_topology_token(*parts: str) -> str:
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"topology-{digest}"


def _append_node(
    *,
    nodes: list[GraphTopologyNode],
    node_ids: dict[str, str],
    source_revision: str,
    parser_node: LogseqNode,
    parent_id: str,
    ordinal: int,
    seen_ids: set[str],
    projected_blocks: list[LogseqNode],
) -> None:
    """Consume one subtree lazily, retaining only a bounded DFS stack."""
    stack: list[tuple[Iterator[tuple[int, LogseqNode]], str, int]] = [
        (iter(enumerate((parser_node,), start=ordinal)), parent_id, 1)
    ]
    while stack:
        children, parent, depth = stack[-1]
        try:
            child_ordinal, child = next(children)
        except StopIteration:
            stack.pop()
            continue
        if depth > MAX_OG_TOPOLOGY_BLOCK_DEPTH or len(nodes) >= MAX_OG_TOPOLOGY_NODES:
            raise _OgSnapshotReadError("bounds_exceeded", "OG topology node/depth limit exceeded")
        node_id = _opaque_topology_token(source_revision, "block", child.uuid)
        if not child.uuid or child.uuid in node_ids or node_id in seen_ids:
            raise _OgSnapshotReadError("source_rejected", "OG topology node identity rejected")
        node_ids[child.uuid] = node_id
        seen_ids.add(node_id)
        nodes.append(
            GraphTopologyNode(id=node_id, kind="block", parent_id=parent, ordinal=child_ordinal)
        )
        projected_blocks.append(child)
        if child.children:
            if depth >= MAX_OG_TOPOLOGY_BLOCK_DEPTH:
                raise _OgSnapshotReadError("bounds_exceeded", "OG topology block depth exceeded")
            stack.append((iter(enumerate(child.children)), node_id, depth + 1))


def _logical_page_path(page: LogseqPage, root: Path) -> str:
    if not page.source_path:
        raise _OgSnapshotReadError("source_rejected", "OG topology page source rejected")
    path = Path(page.source_path)
    if not path.is_absolute() or ".." in path.parts:
        raise _OgSnapshotReadError("source_rejected", "OG topology page source rejected")
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise _OgSnapshotReadError("source_rejected", "OG topology page source rejected") from exc


def _canonical_pages(
    graph: LogseqGraph, *, root: Path, logical_paths: tuple[str, ...]
) -> tuple[tuple[str, LogseqPage], ...]:
    """Require exact physical-page coverage, without absolute-path/title identity fallback."""
    if len(logical_paths) > MAX_OG_TOPOLOGY_SNAPSHOT_PAGES:
        raise _OgSnapshotReadError("bounds_exceeded", "OG topology page limit exceeded")
    expected = set(logical_paths)
    if len(expected) != len(logical_paths):
        raise _OgSnapshotReadError("source_rejected", "OG topology capture mapping rejected")
    mapped: dict[str, LogseqPage] = {}
    titles: set[str] = set()
    for page in graph.iter_canonical_pages():
        logical_path = _logical_page_path(page, root)
        title = page.title.strip().casefold()
        if logical_path not in expected or logical_path in mapped or not title or title in titles:
            raise _OgSnapshotReadError("source_rejected", "OG topology page mapping rejected")
        mapped[logical_path] = page
        titles.add(title)
    if mapped.keys() != expected:
        raise _OgSnapshotReadError("source_rejected", "OG topology incomplete page mapping")
    return tuple(
        (logical_path, mapped[logical_path])
        for logical_path in sorted(expected, key=lambda value: value.encode("utf-8"))
    )


def _project_references(
    graph: LogseqGraph,
    *,
    root: Path,
    pages: tuple[tuple[str, LogseqPage], ...],
    page_ids: dict[str, str],
    node_ids: dict[str, str],
    blocks: list[LogseqNode],
) -> tuple[GraphTopologyReference, ...]:
    """Resolve references only against the already complete, bounded physical projection."""
    declared_pages = dict(pages)
    edges: set[tuple[str, str]] = set()

    def _add_edge(source_id: str, target_id: str) -> None:
        key = (source_id, target_id)
        if key not in edges:
            if len(edges) >= MAX_OG_TOPOLOGY_EDGES:
                raise _OgSnapshotReadError("bounds_exceeded", "OG topology edge limit exceeded")
            edges.add(key)

    for block in blocks:
        source_id = node_ids[block.uuid]
        for reference in block.wikilinks:
            target_page = graph.get_page(reference)
            if target_page is None:
                raise _OgSnapshotReadError("source_rejected", "OG topology reference rejected")
            logical_path = _logical_page_path(target_page, root)
            declared = declared_pages.get(logical_path)
            if declared is None or declared.title != target_page.title:
                raise _OgSnapshotReadError("source_rejected", "OG topology reference rejected")
            _add_edge(source_id, page_ids[logical_path])
        for reference in block.block_refs:
            target_block = graph.get_node_by_embed_ref(reference)
            if target_block is None or target_block.uuid not in node_ids:
                raise _OgSnapshotReadError("source_rejected", "OG topology reference rejected")
            _add_edge(source_id, node_ids[target_block.uuid])
    return tuple(
        GraphTopologyReference(source_id=source_id, target_id=target_id)
        for source_id, target_id in sorted(edges)
    )


def _project_topology(
    graph: LogseqGraph,
    source_revision: str,
    *,
    root: Path,
    logical_paths: tuple[str, ...],
) -> GraphTopologyResult:
    """Project captured logical identities with bounded, iterative preorder and references."""
    pages = _canonical_pages(graph, root=root, logical_paths=logical_paths)
    page_ids = {
        logical_path: _opaque_topology_token(source_revision, "page", logical_path)
        for logical_path, _ in pages
    }
    nodes: list[GraphTopologyNode] = []
    node_ids: dict[str, str] = {}
    seen_ids: set[str] = set()
    projected_blocks: list[LogseqNode] = []
    for page_ordinal, (logical_path, page) in enumerate(pages):
        if len(nodes) >= MAX_OG_TOPOLOGY_NODES:
            raise _OgSnapshotReadError("bounds_exceeded", "OG topology node limit exceeded")
        page_id = page_ids[logical_path]
        if page_id in seen_ids:
            raise _OgSnapshotReadError("source_rejected", "OG topology node identity rejected")
        seen_ids.add(page_id)
        nodes.append(
            GraphTopologyNode(id=page_id, kind="page", parent_id=None, ordinal=page_ordinal)
        )
        for child_ordinal, child in enumerate(page.root_nodes):
            _append_node(
                nodes=nodes,
                node_ids=node_ids,
                source_revision=source_revision,
                parser_node=child,
                parent_id=page_id,
                ordinal=child_ordinal,
                seen_ids=seen_ids,
                projected_blocks=projected_blocks,
            )
    ordered_edges = _project_references(
        graph,
        root=root,
        pages=pages,
        page_ids=page_ids,
        node_ids=node_ids,
        blocks=projected_blocks,
    )
    return GraphTopologyResult(
        topology_id=_opaque_topology_token(source_revision, "graph"),
        nodes=tuple(nodes),
        edges=ordered_edges,
        provenance=GraphTopologyProvenance(source_revision=source_revision),
    )


class ParserOgTopologyAdapter(OgGraphTopologyPort):
    """Build a complete topology only from Plumber-captured bytes and Parser's public API."""

    def snapshot_og_graph(self, graph_root: Path) -> OgTopologySourceSnapshot:
        root = _admit_og_topology_root(graph_root)
        capture = capture_og_topology(root)
        snapshot_pages = tuple(
            SnapshotPage(logical_path=page.logical_path, text=page.content.decode("utf-8"))
            for page in capture.pages
        )
        source_revision = capture.source_revision
        try:
            graph = LogseqGraph.from_snapshot_pages(
                root,
                snapshot_pages,
                strict_refs=True,
                strict_title_collisions=True,
            )
            topology = _project_topology(
                graph,
                source_revision,
                root=root,
                logical_paths=tuple(page.logical_path for page in capture.pages),
            )
        except GraphSessionReadError:
            raise
        except Exception as exc:
            raise _OgSnapshotReadError("source_rejected", "OG Parser topology read failed") from exc
        verify_og_topology_capture(root, capture)
        return OgTopologySourceSnapshot(
            graph_id=_opaque_digest(str(root)),
            source_revision=source_revision,
            topology=topology,
        )


__all__ = [
    "MAX_OG_TOPOLOGY_EDGES",
    "MAX_OG_TOPOLOGY_NODES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_BYTES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_PAGE_BYTES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_PAGES",
    "ParserOgTopologyAdapter",
]
