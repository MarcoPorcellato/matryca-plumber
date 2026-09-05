"""Behavior specification for the internal OG identity-only session slice."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.og_session_read_composition import create_og_graph_session_reader
from src.graph.ports.session_read import GraphSessionReadPort, OgGraphIdentityPort
from src.graph.session_read_models import (
    GraphReadCapability,
    GraphSession,
    GraphSessionReadError,
    GraphSessionState,
    GraphSourceIdentity,
)
from src.graph.session_read_service import GraphSessionReadService


class _FixedOgIdentitySource(OgGraphIdentityPort):
    def identify_og_graph(self, graph_root: Path, page_title: str) -> GraphSourceIdentity:
        assert graph_root == Path("selected-og-root")
        assert page_title == "Selected page"
        return GraphSourceIdentity(graph_id="graph-alpha", source_revision="revision-alpha")


def test_consumer_receives_only_plumber_owned_identity_response() -> None:
    """Breaks if Parser data crosses GraphSessionReadPort's public boundary."""
    session = GraphSession.from_source(
        session_id="session-alpha",
        source=_FixedOgIdentitySource().identify_og_graph(
            Path("selected-og-root"), "Selected page"
        ),
    )
    reader: GraphSessionReadPort = GraphSessionReadService(session)

    response = reader.identify(session_id="session-alpha", graph_id="graph-alpha")

    assert response.contract_id == "plumber.graph.read/v1"
    assert response.operation == "graph.identify"
    assert response.result.graph_id == "graph-alpha"
    assert response.source_revision == "revision-alpha"
    assert response.model_dump() == {
        "contract_id": "plumber.graph.read/v1",
        "schema_version": 1,
        "session_id": "session-alpha",
        "graph_id": "graph-alpha",
        "source_revision": "revision-alpha",
        "operation": "graph.identify",
        "outcome": "pass",
        "reason": "og-parser-identity",
        "result": {"graph_id": "graph-alpha"},
    }


def test_composition_binds_consumer_reader_to_parser_normalized_identity() -> None:
    """Breaks if composition skips the injected source or exposes a different graph binding."""
    binding = create_og_graph_session_reader(
        Path("selected-og-root"),
        "Selected page",
        identity_source=_FixedOgIdentitySource(),
    )
    reader: GraphSessionReadPort = binding.reader

    response = reader.identify(session_id=binding.session.id, graph_id="graph-alpha")

    assert binding.session.graph_id == "graph-alpha"
    assert response.result.graph_id == "graph-alpha"


def test_identity_rejects_foreign_graph_binding() -> None:
    """Breaks if a session can serve an identity for another graph."""
    session = GraphSession.from_source(
        session_id="session-alpha",
        source=GraphSourceIdentity(graph_id="graph-alpha", source_revision="revision-alpha"),
    )

    with pytest.raises(GraphSessionReadError, match="foreign graph binding"):
        GraphSessionReadService(session).identify(session_id="session-alpha", graph_id="graph-beta")


def test_identity_rejects_closed_session() -> None:
    """Breaks if a closed session continues to serve a graph identity."""
    session = GraphSession(
        id="session-alpha",
        graph_id="graph-alpha",
        source_revision="revision-alpha",
        capabilities=frozenset({GraphReadCapability.GRAPH_IDENTIFY}),
        state=GraphSessionState.CLOSED,
    )

    with pytest.raises(GraphSessionReadError, match="session is not active"):
        GraphSessionReadService(session).identify(
            session_id="session-alpha", graph_id="graph-alpha"
        )
