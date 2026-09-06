"""Composition root for one internal, complete OG topology session."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..graph.ports.session_read import GraphSessionReadPort, OgGraphTopologyPort
from ..graph.session_read_models import (
    GraphReadCapability,
    GraphSession,
    GraphSourceIdentity,
    GraphTopologyCapability,
)
from ..graph.session_read_service import GraphSessionReadService
from .og_parser_topology_adapter import ParserOgTopologyAdapter


@dataclass(frozen=True, slots=True)
class OgGraphTopologySessionReader:
    """One consumer-ready reader plus its explicit active topology session descriptor."""

    session: GraphSession
    reader: GraphSessionReadPort


def create_og_topology_session_reader(
    graph_root: Path,
    *,
    topology_source: OgGraphTopologyPort | None = None,
) -> OgGraphTopologySessionReader:
    """Bind one Parser-built, graph-wide OG snapshot to a Plumber-owned session."""
    source = topology_source or ParserOgTopologyAdapter()
    snapshot = source.snapshot_og_graph(graph_root)
    session = GraphSession.from_source(
        session_id=uuid4().hex,
        source=GraphSourceIdentity(
            graph_id=snapshot.graph_id,
            source_revision=snapshot.source_revision,
        ),
        capabilities=frozenset(
            {
                GraphReadCapability.GRAPH_IDENTIFY,
                GraphTopologyCapability.GRAPH_TOPOLOGY_SNAPSHOT_COMPLETE,
            }
        ),
    )
    return OgGraphTopologySessionReader(
        session=session,
        reader=GraphSessionReadService(session, topology=snapshot.topology),
    )


__all__ = ["OgGraphTopologySessionReader", "create_og_topology_session_reader"]
