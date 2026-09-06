"""Narrow ports for Plumber-owned, session-bound graph identity reads."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..session_read_models import GraphIdentityResponse, GraphSourceIdentity
from ..session_topology_models import GraphTopologyResponse, OgTopologySourceSnapshot


class OgGraphIdentityPort(Protocol):
    """Internal source boundary implemented by the OG Parser adapter."""

    def identify_og_graph(self, graph_root: Path, page_title: str) -> GraphSourceIdentity:
        """Return normalized, content-free identity for one explicitly selected OG page."""
        ...


class OgGraphTopologyPort(Protocol):
    """Internal source boundary implemented by Plumber's OG Parser topology adapter."""

    def snapshot_og_graph(self, graph_root: Path) -> OgTopologySourceSnapshot:
        """Return one complete content-free topology bound to a Plumber-captured source revision."""
        ...


class GraphSessionReadPort(Protocol):
    """Consumer boundary for the current identity-only Plumber session slice."""

    def identify(self, *, session_id: str, graph_id: str) -> GraphIdentityResponse:
        """Return identity only when the caller presents the active graph binding."""
        ...

    def topology_snapshot(self, *, session_id: str, graph_id: str) -> GraphTopologyResponse:
        """Return complete structural topology only for an active, bound OG snapshot session."""
        ...

    def close(self) -> None:
        """Close this Plumber-owned session; repeated close calls are harmless."""
        ...


__all__ = ["GraphSessionReadPort", "OgGraphIdentityPort", "OgGraphTopologyPort"]
