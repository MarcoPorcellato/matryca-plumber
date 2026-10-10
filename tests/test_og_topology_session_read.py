"""Behavior specification for the bounded OG topology session slice."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from logseq_matryca_parser import LogosParser
from logseq_matryca_parser.graph import LogseqGraph
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from pydantic import ValidationError
from src.agent import og_parser_topology_adapter as adapter
from src.agent import og_topology_snapshot as snapshot
from src.graph.session_read_models import GraphSessionReadError
from src.graph.session_topology_models import (
    GraphTopologyNode,
    GraphTopologyResult,
    OgTopologySourceSnapshot,
)


def _write_page(root: Path, relative_path: str, markdown: str) -> None:
    page_path = root / relative_path
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text(markdown, encoding="utf-8")


def test_og_topology_uses_one_complete_parser_snapshot_without_content_leakage(
    tmp_path: Path,
) -> None:
    """Breaks if topology reopens source files or exposes Parser or Markdown values."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    _write_page(
        tmp_path,
        "pages/Alpha.md",
        "- alpha [[Beta]]\n"
        "  id:: 11111111-1111-1111-1111-111111111111\n"
        "  - child ((22222222-2222-2222-2222-222222222222))\n"
        "    id:: 33333333-3333-3333-3333-333333333333\n",
    )
    _write_page(
        tmp_path,
        "pages/Beta.md",
        "- beta\n  id:: 22222222-2222-2222-2222-222222222222\n",
    )

    binding = create_og_topology_session_reader(tmp_path)
    response = binding.reader.topology_snapshot(
        session_id=binding.session.id,
        graph_id=binding.session.graph_id,
    )

    assert response.contract_id == "plumber.graph.topology/v1"
    assert response.operation == "graph.topology.snapshot.complete"
    assert response.source_revision == binding.session.source_revision
    assert response.result.complete is True
    assert len(response.result.nodes) == 5
    assert [node.ordinal for node in response.result.nodes if node.parent_id is None] == [0, 1]
    assert response.result.edges
    rendered = response.model_dump_json()
    assert "Alpha" not in rendered
    assert "Beta" not in rendered
    assert "alpha" not in rendered
    assert "pages/" not in rendered
    assert "11111111-1111-1111-1111-111111111111" not in rendered


def test_topology_values_reject_noncanonical_parentage_before_service_delivery() -> None:
    """Breaks if a future adapter can pass a partial or out-of-order topology to consumers."""
    from src.graph.session_topology_models import (
        GraphTopologyNode,
        GraphTopologyProvenance,
        GraphTopologyResult,
    )

    with pytest.raises(ValidationError, match="canonical preorder"):
        GraphTopologyResult(
            topology_id="topology-alpha",
            nodes=(
                GraphTopologyNode(
                    id="block-alpha", kind="block", parent_id="page-alpha", ordinal=0
                ),
                GraphTopologyNode(id="page-alpha", kind="page", parent_id=None, ordinal=0),
            ),
            edges=(),
            provenance=GraphTopologyProvenance(source_revision="revision-alpha"),
        )


def test_topology_values_reject_reference_to_undeclared_node() -> None:
    """Breaks if a response can claim a structural reference outside its complete node set."""
    from src.graph.session_topology_models import (
        GraphTopologyNode,
        GraphTopologyProvenance,
        GraphTopologyReference,
        GraphTopologyResult,
    )

    with pytest.raises(ValidationError, match="declared topology nodes"):
        GraphTopologyResult(
            topology_id="topology-alpha",
            nodes=(GraphTopologyNode(id="page-alpha", kind="page", parent_id=None, ordinal=0),),
            edges=(GraphTopologyReference(source_id="page-alpha", target_id="node-missing"),),
            provenance=GraphTopologyProvenance(source_revision="revision-alpha"),
        )


def test_topology_values_reject_noncanonical_reference_order() -> None:
    """Breaks if the service can expose a nondeterministic complete topology order."""
    from src.graph.session_topology_models import (
        GraphTopologyNode,
        GraphTopologyProvenance,
        GraphTopologyReference,
        GraphTopologyResult,
    )

    with pytest.raises(ValidationError, match="canonical lexical order"):
        GraphTopologyResult(
            topology_id="topology-alpha",
            nodes=(
                GraphTopologyNode(id="page-alpha", kind="page", parent_id=None, ordinal=0),
                GraphTopologyNode(id="page-beta", kind="page", parent_id=None, ordinal=1),
            ),
            edges=(
                GraphTopologyReference(source_id="page-beta", target_id="page-alpha"),
                GraphTopologyReference(source_id="page-alpha", target_id="page-beta"),
            ),
            provenance=GraphTopologyProvenance(source_revision="revision-alpha"),
        )


def test_og_topology_rejects_symlinked_source_directory(tmp_path: Path) -> None:
    """Breaks if the graph-wide capture can traverse outside its selected OG root."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    outside = tmp_path / "outside"
    outside.mkdir()
    _write_page(outside, "Secret.md", "- must not become graph input\n")
    (tmp_path / "pages").symlink_to(outside, target_is_directory=True)

    with pytest.raises(GraphSessionReadError, match="source rejected"):
        create_og_topology_session_reader(tmp_path)


def test_og_topology_rejects_unresolved_block_reference(tmp_path: Path) -> None:
    """Breaks if an incomplete graph can be projected as a complete topology."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    _write_page(
        tmp_path,
        "pages/Alpha.md",
        "- unresolved ((11111111-1111-1111-1111-111111111111))\n",
    )

    with pytest.raises(GraphSessionReadError, match="OG Parser topology read failed"):
        create_og_topology_session_reader(tmp_path)


def test_og_topology_rejects_title_collision(tmp_path: Path) -> None:
    """Breaks if one canonical page identity can hide a second physical source page."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    _write_page(tmp_path, "pages/Alpha.md", "title:: Same\n- alpha\n")
    _write_page(tmp_path, "pages/Beta.md", "title:: Same\n- beta\n")

    with pytest.raises(GraphSessionReadError, match="OG Parser topology read failed"):
        create_og_topology_session_reader(tmp_path)


def test_og_topology_does_not_promote_parser_tags_or_refs_to_structural_edges(
    tmp_path: Path,
) -> None:
    """Breaks if Parser convenience fields infer topology semantics beyond explicit references."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    _write_page(tmp_path, "pages/Alpha.md", "- tagged #Beta\n")
    _write_page(tmp_path, "pages/Beta.md", "- beta\n")

    binding = create_og_topology_session_reader(tmp_path)
    response = binding.reader.topology_snapshot(
        session_id=binding.session.id,
        graph_id=binding.session.graph_id,
    )

    assert response.result.edges == ()


def test_og_topology_excludes_aggregate_page_property_refs(tmp_path: Path) -> None:
    """Page ``refs`` merges properties and block fields, so it has no v1 edge meaning."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    property_markdown = "related:: [[Beta]]\n- alpha\n"
    assert LogosParser().parse(property_markdown).refs == ["Beta"]
    _write_page(tmp_path, "pages/Alpha.md", property_markdown)
    _write_page(tmp_path, "pages/Beta.md", "- beta\n")

    binding = create_og_topology_session_reader(tmp_path)
    response = binding.reader.topology_snapshot(
        session_id=binding.session.id,
        graph_id=binding.session.graph_id,
    )

    assert response.result.edges == ()


@pytest.mark.parametrize("explicit_ids", [False, True])
def test_topology_relocation_preserves_result_and_revision(
    tmp_path: Path, explicit_ids: bool
) -> None:
    """Generated and explicit Parser IDs must remain portable without rewriting block tokens."""
    markdown = "- root [[Beta]]\n"
    if explicit_ids:
        markdown += "  id:: 11111111-1111-1111-1111-111111111111\n"
    markdown += "  - child\n"
    roots = (tmp_path / "first", tmp_path / "second")
    for root in roots:
        _write_page(root, "pages/Alpha.md", markdown)
        _write_page(root, "pages/Beta.md", "- beta\n")
    first = adapter.ParserOgTopologyAdapter().snapshot_og_graph(roots[0])
    repeated = adapter.ParserOgTopologyAdapter().snapshot_og_graph(roots[0])
    relocated = adapter.ParserOgTopologyAdapter().snapshot_og_graph(roots[1])

    def _block_ids(value: OgTopologySourceSnapshot) -> list[str]:
        return [node.id for node in value.topology.nodes if node.kind == "block"]

    assert _block_ids(first) == _block_ids(repeated) == _block_ids(relocated)
    assert first.source_revision == repeated.source_revision == relocated.source_revision
    assert first.graph_id == repeated.graph_id != relocated.graph_id
    assert first.topology == repeated.topology == relocated.topology
    goldens = [
        hashlib.sha256(
            json.dumps(
                value.topology.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        for value in (first, repeated, relocated)
    ]
    assert len(set(goldens)) == 1


def test_topology_uses_utf8_logical_order_and_complete_preorder(tmp_path: Path) -> None:
    """Canonical order follows logical paths and exhausts each subtree before its sibling."""
    logical_paths = ("pages/B.md", "pages/a.md", "pages/sub/x.md", "pages/subA.md")
    for logical_path in reversed(logical_paths):
        _write_page(
            tmp_path, logical_path, "- root\n  - first\n    - grandchild\n  - second\n- next\n"
        )
    snapshot = adapter.ParserOgTopologyAdapter().snapshot_og_graph(tmp_path)
    expected_pages = [
        adapter._opaque_topology_token(snapshot.source_revision, "page", logical_path)
        for logical_path in sorted(logical_paths, key=lambda value: value.encode("utf-8"))
    ]
    page_nodes = [node for node in snapshot.topology.nodes if node.kind == "page"]
    assert [node.id for node in page_nodes] == expected_pages
    assert [node.ordinal for node in page_nodes] == list(range(4))
    for offset in range(0, len(snapshot.topology.nodes), 6):
        (
            page,
            root,
            first,
            grandchild,
            second,
            next_root,
        ) = snapshot.topology.nodes[offset : offset + 6]
        assert root.parent_id == next_root.parent_id == page.id
        assert first.parent_id == second.parent_id == root.id
        assert grandchild.parent_id == first.id
        assert (
            root.ordinal,
            first.ordinal,
            grandchild.ordinal,
            second.ordinal,
            next_root.ordinal,
        ) == (0, 0, 0, 1, 1)


@pytest.mark.parametrize("mapping", ["missing", "extra", "duplicate"])
def test_topology_rejects_missing_extra_and_duplicate_page_mappings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mapping: str
) -> None:
    """An unchanged captured file set must map bijectively to all physical Parser pages."""
    _write_page(tmp_path, "pages/Alpha.md", "- alpha\n")
    _write_page(tmp_path, "pages/Beta.md", "- unreferenced\n")
    before = {path.name: path.read_bytes() for path in (tmp_path / "pages").iterdir()}
    original_pages = LogseqGraph.iter_canonical_pages

    def _altered_pages(graph: LogseqGraph) -> Iterator[LogseqPage]:
        pages = tuple(original_pages(graph))
        if mapping == "missing":
            yield from (page for page in pages if page.title != "Beta")
        else:
            yield from pages
            yield LogseqPage(
                title="Injected",
                raw_content="",
                source_path=str(
                    tmp_path / "pages" / ("Uncaptured.md" if mapping == "extra" else "Alpha.md")
                ),
            )

    monkeypatch.setattr(LogseqGraph, "iter_canonical_pages", _altered_pages)
    failure: Exception | None = None
    try:
        adapter.ParserOgTopologyAdapter().snapshot_og_graph(tmp_path)
    except (GraphSessionReadError, ValidationError) as caught:
        failure = caught
    assert {path.name: path.read_bytes() for path in (tmp_path / "pages").iterdir()} == before
    assert isinstance(failure, GraphSessionReadError), (
        "projection omitted/admitted an uncaptured page or leaked a raw validation error"
    )
    assert getattr(failure, "code", None) == "source_rejected"


class _ProjectionGraph:
    """Synthetic Parser-owned values isolate the projector from Parser allocation behavior."""

    def __init__(self, page: LogseqPage, blocks: list[LogseqNode]) -> None:
        self.page = page
        self.blocks = {block.uuid: block for block in blocks}
        self.reference_lookups = 0

    def iter_canonical_pages(self) -> Iterator[LogseqPage]:
        yield self.page

    def get_page(self, title: str) -> LogseqPage | None:
        return self.page if title == self.page.title else None

    def get_node_by_embed_ref(self, reference: str) -> LogseqNode | None:
        self.reference_lookups += 1
        return self.blocks.get(reference)


def _project(graph: _ProjectionGraph, root: Path) -> GraphTopologyResult:
    """Project synthetic Parser values against the exact admitted logical source manifest."""
    return adapter._project_topology(
        cast(LogseqGraph, graph),
        "revision-synthetic",
        root=root,
        logical_paths=("pages/Synthetic.md",),
    )


def _bounded_projection_fixture(root: Path, resource: str, excess: bool) -> _ProjectionGraph:
    if resource == "nodes":
        count = 1025 if excess else 1023
        blocks = [
            LogseqNode(uuid=f"block-{index}", content="", indent_level=0) for index in range(count)
        ]
        roots = blocks
    elif resource == "references":
        count = 66 if excess else 64
        identifiers = [f"block-{index}" for index in range(count)]
        blocks = [
            LogseqNode(uuid=identifier, content="", indent_level=0, block_refs=list(identifiers))
            for identifier in identifiers
        ]
        roots = blocks
    else:
        depth = 1100 if resource == "recursion" else 65 if excess else 64
        blocks = []
        child: LogseqNode | None = None
        for index in reversed(range(depth)):
            child = LogseqNode(uuid=f"block-{index}", content="", indent_level=0).model_copy(
                update={"children": [] if child is None else [child]}
            )
            blocks.append(child)
        assert child is not None
        roots = [child]
    page = LogseqPage(
        title="Synthetic",
        raw_content="",
        source_path=str(root / "pages/Synthetic.md"),
        root_nodes=roots,
    )
    return _ProjectionGraph(page, blocks)


@pytest.mark.parametrize("resource", ["nodes", "references", "depth", "recursion"])
def test_topology_rejects_projection_bounds_before_excess_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resource: str
) -> None:
    """The first excess node/reference/depth rejects before unbounded append or recursion."""
    graph = _bounded_projection_fixture(tmp_path, resource, True)
    node_allocations = 0
    original_node = GraphTopologyNode

    def _counted_node(*args: Any, **kwargs: Any) -> Any:
        nonlocal node_allocations
        node_allocations += 1
        return original_node(*args, **kwargs)

    monkeypatch.setattr(adapter, "GraphTopologyNode", _counted_node)
    failure: Exception | None = None
    try:
        _project(graph, tmp_path)
    except (GraphSessionReadError, RecursionError) as caught:
        failure = caught
    assert node_allocations <= (65 if resource in {"depth", "recursion"} else 1024)
    assert graph.reference_lookups <= 4097
    assert isinstance(failure, GraphSessionReadError), (
        "bound failure escaped or topology was complete"
    )
    assert getattr(failure, "code", None) == "bounds_exceeded"


@pytest.mark.parametrize("resource", ["nodes", "references", "depth"])
def test_topology_accepts_inclusive_projection_bounds(tmp_path: Path, resource: str) -> None:
    """Inclusive ceilings do not silently become off-by-one source refusals."""
    graph = _bounded_projection_fixture(tmp_path, resource, False)
    result = _project(graph, tmp_path)
    assert result.complete is True
    if resource == "nodes":
        assert len(result.nodes) == 1024
    elif resource == "references":
        assert len(result.edges) == 4096
    else:
        assert len(result.nodes) == 65


@pytest.mark.parametrize(
    ("root_kind", "entry"),
    [
        ("symlink_parent", "adapter"),
        ("symlink_parent", "composition"),
        ("expansion", "adapter"),
        ("expansion", "composition"),
    ],
)
def test_topology_rejects_root_interpretation_divergence_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_kind: str, entry: str
) -> None:
    """Neither adapter nor composition may label lexical bytes with another root identity."""
    from src.agent.og_topology_session_composition import create_og_topology_session_reader

    lexical = tmp_path / ("lexical" if root_kind == "symlink_parent" else "~") / "graph"
    physical = tmp_path / "physical/graph"
    _write_page(lexical, "pages/Selected.md", "- lexical\n")
    _write_page(physical, "pages/Selected.md", "- physical\n")
    if root_kind == "symlink_parent":
        target = tmp_path / "physical/sub"
        target.mkdir()
        link = tmp_path / "lexical/link"
        link.symlink_to(target, target_is_directory=True)
        selected = link / ".." / "graph"
    else:
        monkeypatch.chdir(tmp_path)
        selected = Path("~/graph")
        original_expanduser = Path.expanduser

        def _synthetic_expansion(path: Path) -> Path:
            return physical if path == selected else original_expanduser(path)

        monkeypatch.setattr(Path, "expanduser", _synthetic_expansion)
    original_page = snapshot._capture_page
    page_reads = 0

    def _record_page(*args: Any, **kwargs: Any) -> Any:
        nonlocal page_reads
        page_reads += 1
        return original_page(*args, **kwargs)

    monkeypatch.setattr(snapshot, "_capture_page", _record_page)
    failure: GraphSessionReadError | None = None
    try:
        if entry == "adapter":
            adapter.ParserOgTopologyAdapter().snapshot_og_graph(selected)
        else:
            create_og_topology_session_reader(selected)
    except GraphSessionReadError as caught:
        failure = caught
    assert failure is not None, "topology accepted divergent root interpretations"
    assert getattr(failure, "code", None) == "source_rejected"
    assert page_reads == 0, "ambiguous root reached Markdown capture"
    assert str(tmp_path) not in str(failure)
