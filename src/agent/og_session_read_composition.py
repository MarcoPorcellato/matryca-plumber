"""Composition root for the internal OG identity-only graph session reader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from ..graph.ports.session_read import GraphSessionReadPort, OgGraphIdentityPort
from ..graph.session_read_models import GraphSession
from ..graph.session_read_service import GraphSessionReadService
from .og_parser_identity_adapter import ParserOgIdentityAdapter


@dataclass(frozen=True, slots=True)
class OgGraphSessionReader:
    """One consumer-ready reader plus its explicit active session descriptor."""

    session: GraphSession
    reader: GraphSessionReadPort


def create_og_graph_session_reader(
    graph_root: Path,
    page_title: str,
    *,
    identity_source: OgGraphIdentityPort | None = None,
) -> OgGraphSessionReader:
    """Bind one explicit OG source to an identity-only Plumber session."""
    source = identity_source or ParserOgIdentityAdapter()
    identity = source.identify_og_graph(graph_root, page_title)
    session = GraphSession.from_source(session_id=uuid4().hex, source=identity)
    return OgGraphSessionReader(session=session, reader=GraphSessionReadService(session))


__all__ = ["OgGraphSessionReader", "create_og_graph_session_reader"]
