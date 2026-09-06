"""Application service for the identity-only ``plumber.graph.read/v1`` slice."""

from __future__ import annotations

from collections.abc import Callable
from time import monotonic

from .ports.session_read import GraphSessionReadPort
from .session_read_models import (
    GraphIdentityResponse,
    GraphIdentityResult,
    GraphReadCapability,
    GraphSession,
    GraphSessionReadError,
    GraphSessionState,
    GraphTopologyCapability,
)
from .session_topology_models import (
    GraphTopologyResponse,
    GraphTopologyResult,
)


class GraphSessionReadService(GraphSessionReadPort):
    """Serve one active, bound graph identity without selecting a source or transport."""

    def __init__(
        self,
        session: GraphSession,
        *,
        clock: Callable[[], float] = monotonic,
        topology: GraphTopologyResult | None = None,
    ) -> None:
        self._session = session
        self._clock = clock
        self._state = session.state
        self._topology = topology

    def close(self) -> None:
        """Close an active session once; a terminal session stays terminal."""
        if self._state is GraphSessionState.ACTIVE:
            self._state = GraphSessionState.CLOSED

    def identify(self, *, session_id: str, graph_id: str) -> GraphIdentityResponse:
        """Return a content-free identity response or reject an invalid session binding."""
        if session_id != self._session.id:
            raise GraphSessionReadError("session binding rejected")
        self._require_active_session()
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

    def topology_snapshot(self, *, session_id: str, graph_id: str) -> GraphTopologyResponse:
        """Return one complete, content-free topology or reject an invalid session binding."""
        if session_id != self._session.id:
            raise GraphSessionReadError("session binding rejected")
        self._require_active_session()
        if graph_id != self._session.graph_id:
            raise GraphSessionReadError("foreign graph binding rejected")
        if (
            GraphTopologyCapability.GRAPH_TOPOLOGY_SNAPSHOT_COMPLETE
            not in self._session.capabilities
            or self._topology is None
        ):
            raise GraphSessionReadError("graph topology capability unavailable")
        return GraphTopologyResponse(
            session_id=self._session.id,
            graph_id=self._session.graph_id,
            source_revision=self._session.source_revision,
            result=self._topology,
        )

    def _require_active_session(self) -> None:
        if self._state is GraphSessionState.CLOSED:
            raise GraphSessionReadError("session is closed")
        if self._state is GraphSessionState.EXPIRED:
            raise GraphSessionReadError("session expired")
        if self._state is not GraphSessionState.ACTIVE:
            raise GraphSessionReadError("session is not active")
        deadline = self._session.expires_at_monotonic
        if deadline is not None and self._clock() >= deadline:
            self._state = GraphSessionState.EXPIRED
            raise GraphSessionReadError("session expired")


__all__ = ["GraphSessionReadService"]
