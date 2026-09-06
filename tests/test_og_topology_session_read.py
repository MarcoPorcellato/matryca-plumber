"""Behavior specification for the bounded OG topology session slice."""

from __future__ import annotations

from pathlib import Path

import pytest
from logseq_matryca_parser import LogosParser
from pydantic import ValidationError
from src.graph.session_read_models import GraphSessionReadError


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
