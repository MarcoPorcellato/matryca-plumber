"""Plumber-owned values for the identity-only graph session read slice."""

from __future__ import annotations

import re
from enum import StrEnum
from math import isfinite
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator

CONTRACT_ID: Final[Literal["plumber.graph.read/v1"]] = "plumber.graph.read/v1"
SCHEMA_VERSION: Final[Literal[1]] = 1
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class GraphSessionReadError(ValueError):
    """Raised when an identity-only graph session request fails closed."""


class GraphReadCapability(StrEnum):
    """Capabilities implemented by this narrow runtime slice."""

    GRAPH_IDENTIFY = "graph.identify"


class GraphSessionState(StrEnum):
    """Lifecycle states that may be exposed by an identity-only session."""

    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class _OpaqueIdentityModel(BaseModel):
    """Validate content-free identifiers shared by session-facing values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*")
    @classmethod
    def _validate_opaque_ids(cls, value: object) -> object:
        if isinstance(value, str) and (len(value) > 128 or not _OPAQUE_ID.fullmatch(value)):
            raise ValueError("must be a bounded opaque identifier")
        return value


class GraphSourceIdentity(_OpaqueIdentityModel):
    """Adapter-normalized identity; never carries a Parser model or graph content."""

    graph_id: str
    source_revision: str


class GraphSession(_OpaqueIdentityModel):
    """One Plumber-owned OG session bound to a graph identity and source revision."""

    contract_id: Literal["plumber.graph.read/v1"] = CONTRACT_ID
    schema_version: Literal[1] = SCHEMA_VERSION
    id: str
    graph_id: str
    source_revision: str
    mode: Literal["og"] = "og"
    capabilities: frozenset[GraphReadCapability]
    state: GraphSessionState = GraphSessionState.ACTIVE
    expires_at_monotonic: float | None = None

    @field_validator("expires_at_monotonic")
    @classmethod
    def _validate_expiry(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(value):
            raise ValueError("must be a finite monotonic deadline")
        return value

    @classmethod
    def from_source(
        cls,
        *,
        session_id: str,
        source: GraphSourceIdentity,
        expires_at_monotonic: float | None = None,
    ) -> GraphSession:
        """Create the only session shape admitted by the OG identity slice."""
        return cls(
            id=session_id,
            graph_id=source.graph_id,
            source_revision=source.source_revision,
            capabilities=frozenset({GraphReadCapability.GRAPH_IDENTIFY}),
            expires_at_monotonic=expires_at_monotonic,
        )


class GraphIdentityResult(_OpaqueIdentityModel):
    """Content-free result for ``graph.identify``."""

    graph_id: str


class GraphIdentityResponse(_OpaqueIdentityModel):
    """Plumber-owned response vocabulary for the internal identity-only reader."""

    contract_id: Literal["plumber.graph.read/v1"] = CONTRACT_ID
    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    graph_id: str
    source_revision: str
    operation: Literal["graph.identify"] = "graph.identify"
    outcome: Literal["pass"] = "pass"
    reason: Literal["og-parser-identity"] = "og-parser-identity"
    result: GraphIdentityResult


__all__ = [
    "CONTRACT_ID",
    "SCHEMA_VERSION",
    "GraphIdentityResponse",
    "GraphIdentityResult",
    "GraphReadCapability",
    "GraphSession",
    "GraphSessionReadError",
    "GraphSessionState",
    "GraphSourceIdentity",
]
