"""Private Parser 1.9 adapter for one bounded, complete OG topology snapshot."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from logseq_matryca_parser.graph import LogseqGraph, SnapshotPage
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage

from ..graph.path_sandbox import resolved_graph_root
from ..graph.ports.session_read import OgGraphTopologyPort
from ..graph.session_read_models import GraphSessionReadError
from ..graph.session_topology_models import (
    GraphTopologyNode,
    GraphTopologyProvenance,
    GraphTopologyReference,
    GraphTopologyResult,
    OgTopologySourceSnapshot,
)
from .og_parser_identity_adapter import _opaque_digest, _read_bounded_snapshot

MAX_OG_TOPOLOGY_SNAPSHOT_PAGES = 1024
MAX_OG_TOPOLOGY_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_OG_TOPOLOGY_SNAPSHOT_PAGE_BYTES = 1024 * 1024
MAX_OG_TOPOLOGY_NODES = 1024
MAX_OG_TOPOLOGY_EDGES = 4096


def _opaque_topology_token(*parts: str) -> str:
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"topology-{digest}"


def _regular_markdown_paths(root: Path) -> tuple[tuple[str, Path], ...]:
    """Discover only regular ``pages/`` and ``journals/`` Markdown candidates."""
    candidates: list[tuple[str, Path]] = []
    try:
        for directory_name in ("pages", "journals"):
            directory = root / directory_name
            try:
                directory_metadata = directory.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(directory_metadata.st_mode) or not stat.S_ISDIR(
                directory_metadata.st_mode
            ):
                raise GraphSessionReadError("OG topology source rejected")
            for path in directory.rglob("*.md"):
                if stat.S_ISREG(path.lstat().st_mode):
                    candidates.append((path.relative_to(root).as_posix(), path))
    except OSError as exc:
        raise GraphSessionReadError("OG topology discovery rejected") from exc
    candidates.sort(key=lambda item: item[0])
    if len(candidates) > MAX_OG_TOPOLOGY_SNAPSHOT_PAGES:
        raise GraphSessionReadError("OG topology page limit exceeded")
    return tuple(candidates)


def _capture_snapshot_pages(root: Path) -> tuple[tuple[SnapshotPage, ...], str]:
    """Capture one bounded source set before Parser performs any graph construction."""
    captured: list[SnapshotPage] = []
    revision = hashlib.sha256()
    total_bytes = 0
    for logical_path, path in _regular_markdown_paths(root):
        snapshot = _read_bounded_snapshot(path, max_bytes=MAX_OG_TOPOLOGY_SNAPSHOT_PAGE_BYTES)
        total_bytes += len(snapshot)
        if total_bytes > MAX_OG_TOPOLOGY_SNAPSHOT_BYTES:
            raise GraphSessionReadError("OG topology byte limit exceeded")
        try:
            text = snapshot.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GraphSessionReadError("OG topology decoding rejected") from exc
        logical_bytes = logical_path.encode("utf-8")
        revision.update(len(logical_bytes).to_bytes(4, "big"))
        revision.update(logical_bytes)
        revision.update(len(snapshot).to_bytes(8, "big"))
        revision.update(snapshot)
        captured.append(SnapshotPage(logical_path=logical_path, text=text))
    return tuple(captured), revision.hexdigest()


def _append_node(
    *,
    nodes: list[GraphTopologyNode],
    node_ids: dict[str, str],
    source_revision: str,
    parser_node: LogseqNode,
    parent_id: str,
    ordinal: int,
) -> None:
    node_id = _opaque_topology_token(source_revision, "block", parser_node.uuid)
    node_ids[parser_node.uuid] = node_id
    nodes.append(GraphTopologyNode(id=node_id, kind="block", parent_id=parent_id, ordinal=ordinal))
    for child_ordinal, child in enumerate(parser_node.children):
        _append_node(
            nodes=nodes,
            node_ids=node_ids,
            source_revision=source_revision,
            parser_node=child,
            parent_id=node_id,
            ordinal=child_ordinal,
        )


def _canonical_pages(graph: LogseqGraph) -> tuple[LogseqPage, ...]:
    """Use Parser's in-memory snapshot graph but select a deterministic page order."""
    return tuple(sorted(graph.iter_canonical_pages(), key=lambda page: page.source_path or ""))


def _project_topology(graph: LogseqGraph, source_revision: str) -> GraphTopologyResult:
    """Project Parser-owned values into bounded Plumber-owned opaque topology values."""
    pages = _canonical_pages(graph)
    page_ids = {
        page.title: _opaque_topology_token(source_revision, "page", page.source_path or page.title)
        for page in pages
    }
    nodes: list[GraphTopologyNode] = []
    node_ids: dict[str, str] = {}
    for page_ordinal, page in enumerate(pages):
        page_id = page_ids[page.title]
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
            )
    if len(nodes) > MAX_OG_TOPOLOGY_NODES:
        raise GraphSessionReadError("OG topology node limit exceeded")

    edges: set[tuple[str, str]] = set()

    def add_page_reference(source_id: str, reference: str) -> None:
        target = graph.get_page(reference)
        if target is not None and target.title in page_ids:
            edges.add((source_id, page_ids[target.title]))

    def add_block_references(source_id: str, parser_node: LogseqNode) -> None:
        for reference in parser_node.wikilinks:
            add_page_reference(source_id, reference)
        for reference in parser_node.block_refs:
            target = graph.get_node_by_embed_ref(reference)
            if target is not None and target.uuid in node_ids:
                edges.add((source_id, node_ids[target.uuid]))
        for child in parser_node.children:
            child_id = node_ids[child.uuid]
            add_block_references(child_id, child)

    for page in pages:
        page_id = page_ids[page.title]
        for child in page.root_nodes:
            add_block_references(node_ids[child.uuid], child)

    if len(edges) > MAX_OG_TOPOLOGY_EDGES:
        raise GraphSessionReadError("OG topology edge limit exceeded")
    ordered_edges = tuple(
        GraphTopologyReference(source_id=source_id, target_id=target_id)
        for source_id, target_id in sorted(edges)
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
        root = resolved_graph_root(graph_root)
        if not root.is_dir():
            raise GraphSessionReadError("OG graph root unavailable")
        snapshot_pages, source_revision = _capture_snapshot_pages(root)
        try:
            graph = LogseqGraph.from_snapshot_pages(
                root,
                snapshot_pages,
                strict_refs=True,
                strict_title_collisions=True,
            )
        except Exception as exc:
            raise GraphSessionReadError("OG Parser topology read failed") from exc
        return OgTopologySourceSnapshot(
            graph_id=_opaque_digest(str(root)),
            source_revision=source_revision,
            topology=_project_topology(graph, source_revision),
        )


__all__ = [
    "MAX_OG_TOPOLOGY_EDGES",
    "MAX_OG_TOPOLOGY_NODES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_BYTES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_PAGE_BYTES",
    "MAX_OG_TOPOLOGY_SNAPSHOT_PAGES",
    "ParserOgTopologyAdapter",
]
