"""Plumber-owned, content-free values for one complete OG topology snapshot."""

from __future__ import annotations

import re
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .session_read_models import CONTRACT_ID, SCHEMA_VERSION

TOPOLOGY_CONTRACT_ID: Final[Literal["plumber.graph.topology/v1"]] = "plumber.graph.topology/v1"
TOPOLOGY_SCHEMA_VERSION: Final[Literal[1]] = 1
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _validate_opaque_id(value: str) -> str:
    if len(value) > 128 or not _OPAQUE_ID.fullmatch(value):
        raise ValueError("must be a bounded opaque identifier")
    return value


class _TopologyModel(BaseModel):
    """Reject undeclared fields from every topology boundary value."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GraphTopologyNode(_TopologyModel):
    """One opaque, content-free page or block position in canonical preorder."""

    id: str
    kind: Literal["page", "block"]
    parent_id: str | None
    ordinal: int = Field(ge=0)

    @field_validator("id", "parent_id")
    @classmethod
    def _validate_ids(cls, value: str | None) -> str | None:
        return _validate_opaque_id(value) if value is not None else None


class GraphTopologyReference(_TopologyModel):
    """One declared, non-containment structural reference."""

    source_id: str
    target_id: str
    kind: Literal["reference"] = "reference"

    @field_validator("source_id", "target_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_opaque_id(value)


class GraphTopologyProvenance(_TopologyModel):
    """Bind a topology result to the exact Plumber graph-read source revision."""

    kind: Literal["derived-structural"] = "derived-structural"
    source_contract_id: Literal["plumber.graph.read/v1"] = CONTRACT_ID
    source_schema_version: Literal[1] = SCHEMA_VERSION
    source_revision: str

    @field_validator("source_revision")
    @classmethod
    def _validate_source_revision(cls, value: str) -> str:
        return _validate_opaque_id(value)


class GraphTopologyResult(_TopologyModel):
    """Complete, bounded topology with no Markdown, path, title, or native ID fields."""

    topology_id: str
    complete: Literal[True] = True
    nodes: tuple[GraphTopologyNode, ...] = Field(max_length=1024)
    edges: tuple[GraphTopologyReference, ...] = Field(max_length=4096)
    provenance: GraphTopologyProvenance

    @field_validator("topology_id")
    @classmethod
    def _validate_topology_id(cls, value: str) -> str:
        return _validate_opaque_id(value)

    @model_validator(mode="after")
    def _validate_canonical_preorder(self) -> GraphTopologyResult:
        """Reject non-complete structural values before any consumer service receives them."""
        seen: dict[str, GraphTopologyNode] = {}
        next_ordinal: dict[str | None, int] = {}
        for node in self.nodes:
            if node.id in seen:
                raise ValueError("topology node identifiers must be unique")
            if node.kind == "page" and node.parent_id is not None:
                raise ValueError("topology page nodes must be roots")
            if node.kind == "block" and node.parent_id is None:
                raise ValueError("topology block nodes require a parent")
            if node.parent_id is not None and node.parent_id not in seen:
                raise ValueError("topology nodes must use canonical preorder")
            expected = next_ordinal.get(node.parent_id, 0)
            if node.ordinal != expected:
                raise ValueError("topology sibling ordinals must be contiguous")
            next_ordinal[node.parent_id] = expected + 1
            seen[node.id] = node
        for edge in self.edges:
            if edge.source_id not in seen or edge.target_id not in seen:
                raise ValueError("topology references must target declared topology nodes")
        edge_keys = tuple((edge.kind, edge.source_id, edge.target_id) for edge in self.edges)
        if edge_keys != tuple(sorted(set(edge_keys))):
            raise ValueError("topology references must use canonical lexical order")
        return self


class GraphTopologyResponse(_TopologyModel):
    """Plumber-owned successful response for one active, bound topology session."""

    contract_id: Literal["plumber.graph.topology/v1"] = TOPOLOGY_CONTRACT_ID
    schema_version: Literal[1] = TOPOLOGY_SCHEMA_VERSION
    session_id: str
    graph_id: str
    source_revision: str
    operation: Literal["graph.topology.snapshot.complete"] = "graph.topology.snapshot.complete"
    outcome: Literal["pass"] = "pass"
    reason: Literal["og-parser-snapshot"] = "og-parser-snapshot"
    result: GraphTopologyResult

    @field_validator("session_id", "graph_id", "source_revision")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_opaque_id(value)


class OgTopologySourceSnapshot(_TopologyModel):
    """Internal adapter result, normalized before any consumer-facing service receives it."""

    graph_id: str
    source_revision: str
    topology: GraphTopologyResult

    @field_validator("graph_id", "source_revision")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        return _validate_opaque_id(value)


__all__ = [
    "GraphTopologyNode",
    "GraphTopologyProvenance",
    "GraphTopologyReference",
    "GraphTopologyResponse",
    "GraphTopologyResult",
    "OgTopologySourceSnapshot",
    "TOPOLOGY_CONTRACT_ID",
    "TOPOLOGY_SCHEMA_VERSION",
]
