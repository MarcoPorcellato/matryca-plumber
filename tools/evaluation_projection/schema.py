"""Closed, deterministic graph-outcome evaluation projection models."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.memory.graph_outcome_protocol import (
    DimensionName,
    DimensionStatus,
    OutcomeArtifactKind,
    PolicyMode,
    TerminalStatus,
)

from tools.evaluation_projection.privacy import assert_projection_private

PROJECTION_SCHEMA_VERSION = "matryca-graph-outcome-evaluation-projection.v1"
SUITE_SCHEMA_VERSION = "matryca-graph-outcome-evaluation-projection-suite.v1"
ProjectionScenario = Literal[
    "corrupt-derived-state",
    "stale-unverified-mutation",
    "strict-read-only-success",
    "unauthorized-tool-request",
]
ClosedIdentifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,95}$")]

_REQUIRED_DIMENSIONS = frozenset(
    {"canonical_outcome", "derived_state", "communication", "process_quality", "safety"}
)
_REQUIRED_ARTIFACT_KINDS = frozenset(
    {
        "canonical_diff",
        "derived_fingerprints",
        "exclusions",
        "infrastructure_failures",
        "normalized_event_trajectory",
        "resource_metadata",
        "rubric_results",
        "tool_ledger",
        "veto_records",
    }
)
_REQUIRED_SCENARIOS = frozenset(
    {
        "corrupt-derived-state",
        "stale-unverified-mutation",
        "strict-read-only-success",
        "unauthorized-tool-request",
    }
)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _normalized_identifiers(values: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate_{field}")
    return tuple(sorted(values))


class ProjectionDimension(_ClosedModel):
    dimension: DimensionName
    status: DimensionStatus
    passed_check_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    failed_check_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)

    @model_validator(mode="after")
    def _normalize_and_validate_checks(self) -> ProjectionDimension:
        for field in ("passed_check_ids", "failed_check_ids"):
            object.__setattr__(
                self, field, _normalized_identifiers(getattr(self, field), field=field)
            )
        if set(self.passed_check_ids) & set(self.failed_check_ids):
            raise ValueError("rubric_check_in_both_outcomes")
        if self.status == "pass" and self.failed_check_ids:
            raise ValueError("passing_dimension_has_failed_checks")
        if self.status == "fail" and not self.failed_check_ids:
            raise ValueError("failed_dimension_requires_failed_check")
        if self.status == "not_applicable" and (self.passed_check_ids or self.failed_check_ids):
            raise ValueError("not_applicable_dimension_has_checks")
        return self


class ProjectionMetrics(_ClosedModel):
    turns: int = Field(ge=0, le=1_000)
    tool_calls: int = Field(ge=0, le=10_000)
    rejected_tool_calls: int = Field(ge=0, le=10_000)
    retrieval_calls: int = Field(ge=0, le=10_000)
    mutation_calls: int = Field(ge=0, le=1_000)
    retries: int = Field(ge=0, le=100)
    no_progress_cycles: int = Field(ge=0, le=1_000)
    context_tokens: int = Field(ge=0, le=10_000_000)
    context_bytes: int = Field(ge=0, le=10**10)
    elapsed_milliseconds: int = Field(ge=0, le=86_400_000)
    peak_rss_bytes: int = Field(ge=0, le=10**13)
    cost_microunits: int = Field(ge=0, le=10**12)

    @model_validator(mode="after")
    def _validate_counts(self) -> ProjectionMetrics:
        if self.rejected_tool_calls > self.tool_calls:
            raise ValueError("rejected_calls_exceed_tool_calls")
        if self.retrieval_calls > self.tool_calls or self.mutation_calls > self.tool_calls:
            raise ValueError("specialized_calls_exceed_tool_calls")
        return self


class ProjectionArtifact(_ClosedModel):
    kind: OutcomeArtifactKind
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_count: int = Field(ge=0, le=10_000_000)


class GraphOutcomeProjectionPayload(_ClosedModel):
    schema_version: Literal["matryca-graph-outcome-evaluation-projection.v1"] = (
        "matryca-graph-outcome-evaluation-projection.v1"
    )
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_schema_version: Literal["graph-outcome-protocol.v1"]
    scenario: ProjectionScenario
    policy_mode: PolicyMode
    task_bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_status: TerminalStatus
    validation_status: Literal["passed", "rejected"]
    failure_codes: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    executed_tool_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    dimensions: tuple[ProjectionDimension, ...] = Field(min_length=5, max_length=5)
    metrics: ProjectionMetrics
    initial_canonical_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_canonical_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_derived_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_derived_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    roots_distinct: Literal[True]
    roots_outside_repository: Literal[True]
    cleanup_verified: Literal[True]
    artifacts: tuple[ProjectionArtifact, ...] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def _normalize_and_validate_collections(self) -> GraphOutcomeProjectionPayload:
        for field in ("failure_codes", "executed_tool_ids"):
            object.__setattr__(
                self, field, _normalized_identifiers(getattr(self, field), field=field)
            )
        if self.validation_status == "passed" and self.failure_codes:
            raise ValueError("passed_validation_has_failure_codes")
        if self.validation_status == "rejected" and len(self.failure_codes) != 1:
            raise ValueError("rejected_validation_requires_one_failure_code")
        dimensions = tuple(sorted(self.dimensions, key=lambda item: item.dimension))
        if {item.dimension for item in dimensions} != _REQUIRED_DIMENSIONS or len(
            dimensions
        ) != len(_REQUIRED_DIMENSIONS):
            raise ValueError("incomplete_or_duplicate_outcome_dimensions")
        object.__setattr__(self, "dimensions", dimensions)
        artifacts = tuple(sorted(self.artifacts, key=lambda item: item.kind))
        if {item.kind for item in artifacts} != _REQUIRED_ARTIFACT_KINDS or len(artifacts) != len(
            _REQUIRED_ARTIFACT_KINDS
        ):
            raise ValueError("incomplete_or_duplicate_outcome_artifacts")
        object.__setattr__(self, "artifacts", artifacts)
        return self


class GraphOutcomeEvaluationProjection(GraphOutcomeProjectionPayload):
    projection_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class GraphOutcomeSuitePayload(_ClosedModel):
    schema_version: Literal["matryca-graph-outcome-evaluation-projection-suite.v1"] = (
        "matryca-graph-outcome-evaluation-projection-suite.v1"
    )
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_schema_version: Literal["graph-outcome-protocol.v1"]
    projections: tuple[GraphOutcomeEvaluationProjection, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def _normalize_and_validate_projections(self) -> GraphOutcomeSuitePayload:
        projections = tuple(sorted(self.projections, key=lambda item: item.scenario))
        if {item.scenario for item in projections} != _REQUIRED_SCENARIOS or len(
            projections
        ) != len(_REQUIRED_SCENARIOS):
            raise ValueError("incomplete_or_duplicate_projection_scenarios")
        if any(item.source_revision != self.source_revision for item in projections):
            raise ValueError("mixed_projection_source_revision")
        if any(
            item.protocol_schema_version != self.protocol_schema_version for item in projections
        ):
            raise ValueError("mixed_projection_protocol_schema_version")
        object.__setattr__(self, "projections", projections)
        return self


class GraphOutcomeEvaluationSuite(GraphOutcomeSuitePayload):
    suite_id: str = Field(pattern=r"^[0-9a-f]{64}$")


def _canonical_bytes(value: BaseModel, *, exclude: set[str] | None = None) -> bytes:
    payload = value.model_dump(mode="json", exclude=exclude)
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def canonical_projection_bytes(value: GraphOutcomeEvaluationProjection) -> bytes:
    """Serialize a final projection with its deterministic document newline."""
    return _canonical_bytes(value) + b"\n"


def canonical_suite_bytes(value: GraphOutcomeEvaluationSuite) -> bytes:
    """Serialize a final suite with its deterministic document newline."""
    return _canonical_bytes(value) + b"\n"


def build_projection(payload: GraphOutcomeProjectionPayload) -> GraphOutcomeEvaluationProjection:
    """Return the normalized closed projection and its payload-derived identity."""
    normalized = GraphOutcomeProjectionPayload.model_validate(payload.model_dump())
    assert_projection_private(normalized.model_dump(mode="json"))
    projection_id = hashlib.sha256(_canonical_bytes(normalized)).hexdigest()
    return GraphOutcomeEvaluationProjection(**normalized.model_dump(), projection_id=projection_id)


def build_suite(payload: GraphOutcomeSuitePayload) -> GraphOutcomeEvaluationSuite:
    """Return the normalized closed four-scenario suite and its identity."""
    normalized = GraphOutcomeSuitePayload.model_validate(payload.model_dump())
    assert_projection_private(normalized.model_dump(mode="json"))
    suite_id = hashlib.sha256(_canonical_bytes(normalized)).hexdigest()
    return GraphOutcomeEvaluationSuite(**normalized.model_dump(), suite_id=suite_id)


__all__ = [
    "ClosedIdentifier",
    "GraphOutcomeEvaluationProjection",
    "GraphOutcomeEvaluationSuite",
    "GraphOutcomeProjectionPayload",
    "GraphOutcomeSuitePayload",
    "PROJECTION_SCHEMA_VERSION",
    "ProjectionArtifact",
    "ProjectionDimension",
    "ProjectionMetrics",
    "ProjectionScenario",
    "SUITE_SCHEMA_VERSION",
    "build_projection",
    "build_suite",
    "canonical_projection_bytes",
    "canonical_suite_bytes",
]
