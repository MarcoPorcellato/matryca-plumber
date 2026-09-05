"""Narrow ports for Plumber-owned, session-bound graph identity reads."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..session_read_models import GraphIdentityResponse, GraphSourceIdentity


class OgGraphIdentityPort(Protocol):
    """Internal source boundary implemented by the OG Parser adapter."""

    def identify_og_graph(self, graph_root: Path, page_title: str) -> GraphSourceIdentity:
        """Return normalized, content-free identity for one explicitly selected OG page."""
        ...


class GraphSessionReadPort(Protocol):
    """Consumer boundary for the current identity-only Plumber session slice."""

    def identify(self, *, session_id: str, graph_id: str) -> GraphIdentityResponse:
        """Return identity only when the caller presents the active graph binding."""
        ...


__all__ = ["GraphSessionReadPort", "OgGraphIdentityPort"]
