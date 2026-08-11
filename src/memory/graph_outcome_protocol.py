"""Provider-free contracts for resettable graph-outcome evaluation.

The protocol binds public or synthetic fixtures, isolated execution policy,
ordered content-free events, independent outcome dimensions, safety vetoes,
and retained artifacts. It validates evidence only: importing or constructing
these values never reads a graph, creates a Shadow database, invokes a model,
or writes benchmark output.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence_models import EvidenceContractError

GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION = "graph-outcome-protocol.v1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

FixtureClass = Literal["public", "synthetic"]
ShadowInitialMode = Literal["absent", "fresh", "stale", "corrupt", "version_mismatched"]
PolicyMode = Literal["strict_read_only", "proposal_only", "approved_safe_sync"]
SystemRole = Literal["no_memory", "current_matryca", "candidate_matryca", "external_system"]
ActorKind = Literal["user", "human", "agent", "tool", "environment"]
EventKind = Literal[
    "canonical_materialized",
    "shadow_materialized",
    "user_message",
    "human_action",
    "agent_message",
    "tool_call",
    "tool_result",
    "environment_event",
    "completion",
    "abstention",
    "veto",
    "exhausted",
    "infrastructure_failure",
    "agent_failure",
    "excluded",
]
PolicyDecision = Literal["not_applicable", "allowed", "rejected"]
TerminalStatus = Literal[
    "completed",
    "abstained",
    "vetoed",
    "exhausted",
    "infrastructure_failure",
    "agent_failure",
    "excluded",
]
DimensionName = Literal[
    "canonical_outcome",
    "derived_state",
    "communication",
    "process_quality",
    "safety",
]
DimensionStatus = Literal["pass", "fail", "not_applicable"]
VetoCategory = Literal[
    "approval_mismatch",
    "fabricated_success",
    "hidden_failure",
    "lost_concurrent_edit",
    "path_escape",
    "privacy_egress",
    "silent_conflict",
    "stale_unverified_mutation",
    "strict_read_only_write",
    "unauthorized_write",
    "unrelated_mutation",
]
OutcomeArtifactKind = Literal[
    "canonical_diff",
    "derived_fingerprints",
    "exclusions",
    "infrastructure_failures",
    "normalized_event_trajectory",
    "resource_metadata",
    "rubric_results",
    "tool_ledger",
    "veto_records",
]

_TERMINAL_EVENT_BY_STATUS: dict[TerminalStatus, EventKind] = {
    "completed": "completion",
    "abstained": "abstention",
    "vetoed": "veto",
    "exhausted": "exhausted",
    "infrastructure_failure": "infrastructure_failure",
    "agent_failure": "agent_failure",
    "excluded": "excluded",
}
_ACTOR_BY_EVENT: dict[EventKind, ActorKind] = {
    "canonical_materialized": "environment",
    "shadow_materialized": "environment",
    "user_message": "user",
    "human_action": "human",
    "agent_message": "agent",
    "tool_call": "tool",
    "tool_result": "tool",
    "environment_event": "environment",
    "completion": "environment",
    "abstention": "environment",
    "veto": "environment",
    "exhausted": "environment",
    "infrastructure_failure": "environment",
    "agent_failure": "environment",
    "excluded": "environment",
}
_REQUIRED_DIMENSIONS = {
    "canonical_outcome",
    "derived_state",
    "communication",
    "process_quality",
    "safety",
}
_REQUIRED_ARTIFACTS = {
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


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _identifier(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _git_revision(value: str, *, field: str) -> str:
    normalized = value.strip().lower()
    if not _GIT_REVISION.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _sha256(value: str, *, field: str) -> str:
    normalized = value.strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _unique_identifiers(values: tuple[str, ...], *, field: str) -> tuple[str, ...]:
    normalized = tuple(_identifier(value, field=field) for value in values)
    if len(normalized) != len(set(normalized)):
        raise EvidenceContractError(f"duplicate_{field}")
    return tuple(sorted(normalized))


class EpisodeBudget(_ClosedModel):
    """Hard finite bounds for one graph-world episode."""

    max_turns: int = Field(ge=1, le=1_000)
    max_tool_calls: int = Field(ge=0, le=10_000)
    max_retrieval_calls: int = Field(ge=0, le=10_000)
    max_mutation_calls: int = Field(ge=0, le=1_000)
    max_retries: int = Field(ge=0, le=100)
    context_token_budget: int = Field(ge=1, le=10_000_000)
    timeout_seconds: int = Field(ge=1, le=86_400)
    cost_budget_microunits: int = Field(ge=0, le=10**12)

    @model_validator(mode="after")
    def _validate_call_bounds(self) -> EpisodeBudget:
        if self.max_retrieval_calls > self.max_tool_calls:
            raise EvidenceContractError("retrieval_budget_exceeds_tool_budget")
        if self.max_mutation_calls > self.max_tool_calls:
            raise EvidenceContractError("mutation_budget_exceeds_tool_budget")
        return self


class ShadowFixturePin(_ClosedModel):
    """Initial derived-state condition without making Shadow authoritative."""

    mode: ShadowInitialMode
    digest: str | None

    @model_validator(mode="after")
    def _validate_mode(self) -> ShadowFixturePin:
        if self.mode == "absent":
            if self.digest is not None:
                raise EvidenceContractError("absent_shadow_cannot_have_digest")
        elif self.digest is None:
            raise EvidenceContractError("materialized_shadow_requires_digest")
        else:
            object.__setattr__(self, "digest", _sha256(self.digest, field="shadow_digest"))
        return self


class FinalStateExpectation(_ClosedModel):
    """Content-free identifiers for independently graded world invariants."""

    required_canonical_invariant_ids: tuple[str, ...]
    forbidden_canonical_invariant_ids: tuple[str, ...]
    required_derived_invariant_ids: tuple[str, ...]
    allowed_mutation_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_invariants(self) -> FinalStateExpectation:
        for field in (
            "required_canonical_invariant_ids",
            "forbidden_canonical_invariant_ids",
            "required_derived_invariant_ids",
            "allowed_mutation_ids",
        ):
            object.__setattr__(
                self,
                field,
                _unique_identifiers(getattr(self, field), field=field),
            )
        if set(self.required_canonical_invariant_ids) & set(self.forbidden_canonical_invariant_ids):
            raise EvidenceContractError("canonical_invariant_contradiction")
        return self


class VetoSpec(_ClosedModel):
    """One zero-tolerance safety condition declared before execution."""

    veto_id: str
    category: VetoCategory

    @model_validator(mode="after")
    def _validate_id(self) -> VetoSpec:
        object.__setattr__(self, "veto_id", _identifier(self.veto_id, field="veto_id"))
        return self


class GraphOutcomeTaskBundle(_ClosedModel):
    """Immutable public or synthetic graph-world task declaration."""

    schema_version: str = GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION
    task_id: str
    fixture_class: FixtureClass
    source_repository_slug: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    source_revision: str
    license_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    canonical_fixture_digest: str
    initial_shadow: ShadowFixturePin
    initial_request_digest: str
    disclosure_script_digest: str
    human_action_schedule_digest: str | None
    contamination_canary_digest: str
    allowed_tool_ids: tuple[str, ...]
    policy_mode: PolicyMode
    approval_profile_id: str
    occ_profile_id: str
    failure_injection_profile_id: str
    budget: EpisodeBudget
    final_state: FinalStateExpectation
    required_communication_fact_ids: tuple[str, ...]
    vetoes: tuple[VetoSpec, ...]

    @model_validator(mode="after")
    def _validate_task(self) -> GraphOutcomeTaskBundle:
        if self.schema_version != GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_graph_outcome_protocol_schema")
        object.__setattr__(self, "task_id", _identifier(self.task_id, field="task_id"))
        object.__setattr__(
            self, "source_revision", _git_revision(self.source_revision, field="source_revision")
        )
        for field in (
            "canonical_fixture_digest",
            "initial_request_digest",
            "disclosure_script_digest",
            "contamination_canary_digest",
        ):
            object.__setattr__(self, field, _sha256(getattr(self, field), field=field))
        if self.human_action_schedule_digest is not None:
            object.__setattr__(
                self,
                "human_action_schedule_digest",
                _sha256(
                    self.human_action_schedule_digest,
                    field="human_action_schedule_digest",
                ),
            )
        for field in ("approval_profile_id", "occ_profile_id", "failure_injection_profile_id"):
            object.__setattr__(self, field, _identifier(getattr(self, field), field=field))
        object.__setattr__(
            self,
            "allowed_tool_ids",
            _unique_identifiers(self.allowed_tool_ids, field="allowed_tool_ids"),
        )
        object.__setattr__(
            self,
            "required_communication_fact_ids",
            _unique_identifiers(
                self.required_communication_fact_ids,
                field="required_communication_fact_ids",
            ),
        )
        vetoes = tuple(sorted(self.vetoes, key=lambda item: item.veto_id))
        if len(vetoes) != len({item.veto_id for item in vetoes}):
            raise EvidenceContractError("duplicate_veto_id")
        object.__setattr__(self, "vetoes", vetoes)
        if self.policy_mode == "strict_read_only":
            if self.budget.max_mutation_calls != 0 or self.final_state.allowed_mutation_ids:
                raise EvidenceContractError("strict_read_only_forbids_mutation")
            if self.approval_profile_id != "disabled":
                raise EvidenceContractError("strict_read_only_requires_disabled_approval")
        elif self.policy_mode == "proposal_only":
            if self.budget.max_mutation_calls != 0:
                raise EvidenceContractError("proposal_only_forbids_commit_calls")
        elif self.approval_profile_id == "disabled" or self.occ_profile_id == "disabled":
            raise EvidenceContractError("safe_sync_requires_approval_and_occ")
        return self

    @property
    def task_bundle_id(self) -> str:
        return hashlib.sha256(canonical_task_bundle_bytes(self)).hexdigest()


class EnvironmentPin(_ClosedModel):
    """Exact isolated harness and tool-boundary provenance."""

    harness_revision: str
    matryca_revision: str
    parser_revision: str
    dependency_lock_digest: str
    tool_schema_digest: str
    user_actor_protocol_revision: str
    human_actor_protocol_revision: str
    isolation_policy_id: str
    cleanup_policy_id: str
    os_family: str
    runtime_version: str

    @model_validator(mode="after")
    def _validate_pins(self) -> EnvironmentPin:
        for field in (
            "harness_revision",
            "matryca_revision",
            "parser_revision",
            "user_actor_protocol_revision",
            "human_actor_protocol_revision",
        ):
            object.__setattr__(self, field, _git_revision(getattr(self, field), field=field))
        for field in ("dependency_lock_digest", "tool_schema_digest"):
            object.__setattr__(self, field, _sha256(getattr(self, field), field=field))
        for field in ("isolation_policy_id", "cleanup_policy_id", "os_family", "runtime_version"):
            object.__setattr__(self, field, _identifier(getattr(self, field), field=field))
        return self


class ModelExecutionPin(_ClosedModel):
    """A model pin or the explicit provider-free sentinel."""

    model_id: str
    model_revision: str
    prompt_digest: str
    provider_free: bool
    temperature_milli: int = Field(ge=0, le=2_000)
    seed: int = Field(ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _validate_model(self) -> ModelExecutionPin:
        object.__setattr__(self, "model_id", _identifier(self.model_id, field="model_id"))
        object.__setattr__(
            self,
            "model_revision",
            _identifier(self.model_revision, field="model_revision"),
        )
        object.__setattr__(
            self, "prompt_digest", _sha256(self.prompt_digest, field="prompt_digest")
        )
        if self.provider_free and (
            self.model_id != "provider-free"
            or self.model_revision != "none"
            or self.prompt_digest != "0" * 64
            or self.temperature_milli != 0
        ):
            raise EvidenceContractError("invalid_provider_free_model_sentinel")
        if not self.provider_free and self.model_id == "provider-free":
            raise EvidenceContractError("provider_free_sentinel_requires_provider_free")
        return self


class OutcomeSystemPin(_ClosedModel):
    """Comparable tested-system identity without runtime configuration content."""

    role: SystemRole
    system_id: str
    implementation_revision: str
    configuration_digest: str

    @model_validator(mode="after")
    def _validate_system(self) -> OutcomeSystemPin:
        object.__setattr__(self, "system_id", _identifier(self.system_id, field="system_id"))
        object.__setattr__(
            self,
            "implementation_revision",
            _git_revision(self.implementation_revision, field="implementation_revision"),
        )
        object.__setattr__(
            self,
            "configuration_digest",
            _sha256(self.configuration_digest, field="configuration_digest"),
        )
        if self.role != "external_system" and self.system_id != "matryca-plumber":
            raise EvidenceContractError("matryca_arm_must_use_matryca_id")
        return self


class EpisodeManifest(_ClosedModel):
    """One exact task/system/environment execution binding."""

    schema_version: str = GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION
    cohort_id: str
    task_bundle_digest: str
    system: OutcomeSystemPin
    environment: EnvironmentPin
    answer_model: ModelExecutionPin
    judge_model: ModelExecutionPin
    task_order: int = Field(ge=0, le=10_000_000)
    seed: int = Field(ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _validate_manifest(self) -> EpisodeManifest:
        if self.schema_version != GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_graph_outcome_protocol_schema")
        object.__setattr__(self, "cohort_id", _identifier(self.cohort_id, field="cohort_id"))
        object.__setattr__(
            self,
            "task_bundle_digest",
            _sha256(self.task_bundle_digest, field="task_bundle_digest"),
        )
        return self

    @property
    def manifest_id(self) -> str:
        return hashlib.sha256(canonical_episode_manifest_bytes(self)).hexdigest()


class OutcomeEvent(_ClosedModel):
    """One ordered, content-free episode event."""

    sequence: int = Field(ge=0, le=10_000_000)
    event_id: str
    kind: EventKind
    actor: ActorKind
    elapsed_milliseconds: int = Field(ge=0, le=86_400_000)
    payload_digest: str
    tool_id: str | None = None
    argument_digest: str | None = None
    policy_decision: PolicyDecision = "not_applicable"
    success: bool | None = None
    graph_generation_before: int = Field(ge=0, le=2**63 - 1)
    graph_generation_after: int = Field(ge=0, le=2**63 - 1)

    @model_validator(mode="after")
    def _validate_event(self) -> OutcomeEvent:
        object.__setattr__(self, "event_id", _identifier(self.event_id, field="event_id"))
        object.__setattr__(
            self, "payload_digest", _sha256(self.payload_digest, field="payload_digest")
        )
        if self.graph_generation_after < self.graph_generation_before:
            raise EvidenceContractError("graph_generation_regressed")
        if self.actor != _ACTOR_BY_EVENT[self.kind]:
            raise EvidenceContractError("event_actor_mismatch")
        if self.kind in {"tool_call", "tool_result"}:
            if self.actor != "tool" or self.tool_id is None:
                raise EvidenceContractError("tool_event_requires_tool_actor_and_id")
            object.__setattr__(self, "tool_id", _identifier(self.tool_id, field="tool_id"))
            if self.kind == "tool_call":
                if self.argument_digest is None or self.policy_decision == "not_applicable":
                    raise EvidenceContractError("tool_call_requires_arguments_and_policy")
                if self.success is not None:
                    raise EvidenceContractError("tool_call_cannot_have_result")
                object.__setattr__(
                    self,
                    "argument_digest",
                    _sha256(self.argument_digest, field="argument_digest"),
                )
            else:
                if self.success is None:
                    raise EvidenceContractError("tool_result_requires_success")
                if self.argument_digest is not None or self.policy_decision != "not_applicable":
                    raise EvidenceContractError("tool_result_cannot_repeat_call_fields")
        elif (
            self.tool_id is not None
            or self.argument_digest is not None
            or self.policy_decision != "not_applicable"
            or self.success is not None
        ):
            raise EvidenceContractError("non_tool_event_has_tool_fields")
        return self


class ProcessMetrics(_ClosedModel):
    """Bounded content-free mechanism and resource measurements."""

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
    def _validate_counts(self) -> ProcessMetrics:
        if self.rejected_tool_calls > self.tool_calls:
            raise EvidenceContractError("rejected_calls_exceed_tool_calls")
        if self.retrieval_calls > self.tool_calls or self.mutation_calls > self.tool_calls:
            raise EvidenceContractError("specialized_calls_exceed_tool_calls")
        return self


class DimensionResult(_ClosedModel):
    """Independent final-state, communication, process, or safety grade."""

    dimension: DimensionName
    status: DimensionStatus
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _validate_checks(self) -> DimensionResult:
        for field in ("passed_check_ids", "failed_check_ids"):
            object.__setattr__(
                self,
                field,
                _unique_identifiers(getattr(self, field), field=field),
            )
        if set(self.passed_check_ids) & set(self.failed_check_ids):
            raise EvidenceContractError("rubric_check_in_both_outcomes")
        if self.status == "pass" and self.failed_check_ids:
            raise EvidenceContractError("passing_dimension_has_failed_checks")
        if self.status == "fail" and not self.failed_check_ids:
            raise EvidenceContractError("failed_dimension_requires_failed_check")
        if self.status == "not_applicable" and (self.passed_check_ids or self.failed_check_ids):
            raise EvidenceContractError("not_applicable_dimension_has_checks")
        return self


class VetoRecord(_ClosedModel):
    """Content-free proof that one declared zero-tolerance condition fired."""

    veto_id: str
    category: VetoCategory
    event_id: str
    evidence_digest: str

    @model_validator(mode="after")
    def _validate_record(self) -> VetoRecord:
        object.__setattr__(self, "veto_id", _identifier(self.veto_id, field="veto_id"))
        object.__setattr__(self, "event_id", _identifier(self.event_id, field="event_id"))
        object.__setattr__(
            self,
            "evidence_digest",
            _sha256(self.evidence_digest, field="veto_evidence_digest"),
        )
        return self


class EpisodeReport(_ClosedModel):
    """Terminal graph-outcome report with ordered-chain integrity."""

    manifest: EpisodeManifest
    status: TerminalStatus
    initial_canonical_fingerprint: str
    initial_shadow_fingerprint: str | None
    final_canonical_fingerprint: str
    final_shadow_fingerprint: str | None
    events: tuple[OutcomeEvent, ...]
    dimensions: tuple[DimensionResult, ...]
    metrics: ProcessMetrics
    veto_records: tuple[VetoRecord, ...]

    @model_validator(mode="after")
    def _validate_report(self) -> EpisodeReport:
        for field in ("initial_canonical_fingerprint", "final_canonical_fingerprint"):
            object.__setattr__(self, field, _sha256(getattr(self, field), field=field))
        for field in ("initial_shadow_fingerprint", "final_shadow_fingerprint"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _sha256(value, field=field))

        events = tuple(self.events)
        if len(events) < 3:
            raise EvidenceContractError("episode_requires_materialization_and_terminal_events")
        if [event.sequence for event in events] != list(range(len(events))):
            raise EvidenceContractError("event_sequence_must_be_contiguous")
        if len(events) != len({event.event_id for event in events}):
            raise EvidenceContractError("duplicate_event_id")
        if events[0].kind != "canonical_materialized" or events[1].kind != "shadow_materialized":
            raise EvidenceContractError("episode_must_begin_with_materialization")
        if events[-1].kind != _TERMINAL_EVENT_BY_STATUS[self.status]:
            raise EvidenceContractError("terminal_event_status_mismatch")
        for previous, current in zip(events, events[1:], strict=False):
            if current.elapsed_milliseconds < previous.elapsed_milliseconds:
                raise EvidenceContractError("event_time_regressed")
            if current.graph_generation_before != previous.graph_generation_after:
                raise EvidenceContractError("event_generation_chain_broken")
        object.__setattr__(self, "events", events)

        dimensions = tuple(sorted(self.dimensions, key=lambda item: item.dimension))
        if {item.dimension for item in dimensions} != _REQUIRED_DIMENSIONS or len(
            dimensions
        ) != len(_REQUIRED_DIMENSIONS):
            raise EvidenceContractError("incomplete_or_duplicate_outcome_dimensions")
        object.__setattr__(self, "dimensions", dimensions)

        veto_records = tuple(sorted(self.veto_records, key=lambda item: item.veto_id))
        if len(veto_records) != len({item.veto_id for item in veto_records}):
            raise EvidenceContractError("duplicate_veto_record")
        event_ids = {event.event_id for event in events}
        if any(record.event_id not in event_ids for record in veto_records):
            raise EvidenceContractError("veto_references_unknown_event")
        if bool(veto_records) != (self.status == "vetoed"):
            raise EvidenceContractError("veto_records_status_mismatch")
        safety = next(item for item in dimensions if item.dimension == "safety")
        if self.status == "vetoed" and safety.status != "fail":
            raise EvidenceContractError("veto_requires_failed_safety_dimension")
        if self.status == "completed" and any(item.status != "pass" for item in dimensions):
            raise EvidenceContractError("completed_episode_requires_all_dimensions_pass")
        object.__setattr__(self, "veto_records", veto_records)
        return self

    @property
    def report_id(self) -> str:
        return hashlib.sha256(canonical_episode_report_bytes(self)).hexdigest()


class OutcomeArtifact(_ClosedModel):
    """Digest-pinned retained material stored outside the public receipt."""

    kind: OutcomeArtifactKind
    digest: str
    record_count: int = Field(ge=0, le=10_000_000)

    @model_validator(mode="after")
    def _validate_digest(self) -> OutcomeArtifact:
        object.__setattr__(self, "digest", _sha256(self.digest, field=f"{self.kind}_digest"))
        return self


class GraphOutcomeReceipt(_ClosedModel):
    """Content-free retained-evidence receipt for one terminal report."""

    schema_version: str = GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION
    report_id: str
    task_bundle_digest: str
    artifacts: tuple[OutcomeArtifact, ...]

    @model_validator(mode="after")
    def _validate_receipt(self) -> GraphOutcomeReceipt:
        if self.schema_version != GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_graph_outcome_protocol_schema")
        object.__setattr__(self, "report_id", _sha256(self.report_id, field="report_id"))
        object.__setattr__(
            self,
            "task_bundle_digest",
            _sha256(self.task_bundle_digest, field="task_bundle_digest"),
        )
        artifacts = tuple(sorted(self.artifacts, key=lambda item: item.kind))
        if {item.kind for item in artifacts} != _REQUIRED_ARTIFACTS or len(artifacts) != len(
            _REQUIRED_ARTIFACTS
        ):
            raise EvidenceContractError("incomplete_or_duplicate_outcome_artifacts")
        object.__setattr__(self, "artifacts", artifacts)
        return self

    @property
    def receipt_id(self) -> str:
        return hashlib.sha256(canonical_outcome_receipt_bytes(self)).hexdigest()


def _canonical_bytes(value: BaseModel) -> bytes:
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_task_bundle_bytes(bundle: GraphOutcomeTaskBundle) -> bytes:
    """Serialize a task bundle deterministically without fixture content."""
    return _canonical_bytes(bundle)


def canonical_episode_manifest_bytes(manifest: EpisodeManifest) -> bytes:
    """Serialize an execution binding deterministically."""
    return _canonical_bytes(manifest)


def canonical_episode_report_bytes(report: EpisodeReport) -> bytes:
    """Serialize a terminal report deterministically."""
    return _canonical_bytes(report)


def canonical_outcome_receipt_bytes(receipt: GraphOutcomeReceipt) -> bytes:
    """Serialize a content-free retained-evidence receipt deterministically."""
    return _canonical_bytes(receipt)


def validate_episode_against_task(
    report: EpisodeReport,
    task: GraphOutcomeTaskBundle,
) -> str:
    """Bind a terminal report to its task and enforce cross-contract limits."""
    if report.manifest.task_bundle_digest != task.task_bundle_id:
        raise EvidenceContractError("episode_task_bundle_mismatch")

    metrics = report.metrics
    budget = task.budget
    bounded_values = (
        (metrics.turns, budget.max_turns, "turn_budget_exceeded"),
        (metrics.tool_calls, budget.max_tool_calls, "tool_budget_exceeded"),
        (
            metrics.retrieval_calls,
            budget.max_retrieval_calls,
            "retrieval_budget_exceeded",
        ),
        (metrics.mutation_calls, budget.max_mutation_calls, "mutation_budget_exceeded"),
        (metrics.retries, budget.max_retries, "retry_budget_exceeded"),
        (
            metrics.context_tokens,
            budget.context_token_budget,
            "context_budget_exceeded",
        ),
        (
            metrics.elapsed_milliseconds,
            budget.timeout_seconds * 1_000,
            "timeout_budget_exceeded",
        ),
        (
            metrics.cost_microunits,
            budget.cost_budget_microunits,
            "cost_budget_exceeded",
        ),
    )
    for observed, maximum, error in bounded_values:
        if observed > maximum:
            raise EvidenceContractError(error)

    tool_calls = tuple(event for event in report.events if event.kind == "tool_call")
    if len(tool_calls) != metrics.tool_calls:
        raise EvidenceContractError("tool_event_count_mismatch")
    if sum(event.policy_decision == "rejected" for event in tool_calls) != (
        metrics.rejected_tool_calls
    ):
        raise EvidenceContractError("rejected_tool_event_count_mismatch")
    if any(event.tool_id not in task.allowed_tool_ids for event in tool_calls):
        raise EvidenceContractError("tool_not_allowed_by_task")

    if task.initial_shadow.mode == "absent":
        if report.initial_shadow_fingerprint is not None:
            raise EvidenceContractError("absent_shadow_has_initial_fingerprint")
    elif report.initial_shadow_fingerprint is None:
        raise EvidenceContractError("materialized_shadow_missing_initial_fingerprint")

    declared_vetoes = {(item.veto_id, item.category) for item in task.vetoes}
    if any(
        (record.veto_id, record.category) not in declared_vetoes for record in report.veto_records
    ):
        raise EvidenceContractError("episode_uses_undeclared_veto")

    if task.policy_mode == "strict_read_only":
        if report.initial_canonical_fingerprint != report.final_canonical_fingerprint:
            raise EvidenceContractError("strict_read_only_canonical_state_changed")
        if metrics.mutation_calls != 0:
            raise EvidenceContractError("strict_read_only_recorded_mutation")

    return hashlib.sha256(
        json.dumps(
            {
                "report_id": report.report_id,
                "task_bundle_id": task.task_bundle_id,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ActorKind",
    "DimensionName",
    "DimensionResult",
    "DimensionStatus",
    "EnvironmentPin",
    "EpisodeBudget",
    "EpisodeManifest",
    "EpisodeReport",
    "EventKind",
    "FinalStateExpectation",
    "FixtureClass",
    "GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION",
    "GraphOutcomeReceipt",
    "GraphOutcomeTaskBundle",
    "ModelExecutionPin",
    "OutcomeArtifact",
    "OutcomeArtifactKind",
    "OutcomeEvent",
    "OutcomeSystemPin",
    "PolicyDecision",
    "PolicyMode",
    "ProcessMetrics",
    "ShadowFixturePin",
    "ShadowInitialMode",
    "SystemRole",
    "TerminalStatus",
    "VetoCategory",
    "VetoRecord",
    "VetoSpec",
    "canonical_episode_manifest_bytes",
    "canonical_episode_report_bytes",
    "canonical_outcome_receipt_bytes",
    "canonical_task_bundle_bytes",
    "validate_episode_against_task",
]
