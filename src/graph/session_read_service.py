"""Application service for the identity-only ``plumber.graph.read/v1`` slice."""

from __future__ import annotations

from .ports.session_read import GraphSessionReadPort
from .session_read_models import (
    GraphIdentityResponse,
    GraphIdentityResult,
    GraphReadCapability,
    GraphSession,
    GraphSessionReadError,
    GraphSessionState,
)


class GraphSessionReadService(GraphSessionReadPort):
    """Serve one active, bound graph identity without selecting a source or transport."""

    def __init__(self, session: GraphSession) -> None:
        self._session = session

    def identify(self, *, session_id: str, graph_id: str) -> GraphIdentityResponse:
        """Return a content-free identity response or reject an invalid session binding."""
        if session_id != self._session.id:
            raise GraphSessionReadError("session binding rejected")
        if self._session.state is not GraphSessionState.ACTIVE:
            raise GraphSessionReadError("session is not active")
        if graph_id != self._session.graph_id:
            raise GraphSessionReadError("foreign graph binding rejected")
        if GraphReadCapability.GRAPH_IDENTIFY not in self._session.capabilities:
            raise GraphSessionReadError("graph.identify capability unavailable")
        return GraphIdentityResponse(
            session_id=self._session.id,
            graph_id=self._session.graph_id,
            source_revision=self._session.source_revision,
            result=GraphIdentityResult(graph_id=self._session.graph_id),
        )


__all__ = ["GraphSessionReadService"]
