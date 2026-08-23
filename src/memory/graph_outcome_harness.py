"""Provider-free, synthetic graph-outcome harness.

This module is deliberately an in-process test seam.  It creates two fresh
temporary roots, writes deterministic synthetic bytes, runs a finite scripted
sequence, and retains only content-free protocol evidence after cleanup.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from .evidence_models import EvidenceContractError
from .graph_outcome_protocol import (
    GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
    DimensionName,
    DimensionResult,
    EnvironmentPin,
    EpisodeBudget,
    EpisodeManifest,
    EpisodeReport,
    FinalStateExpectation,
    GraphOutcomeReceipt,
    GraphOutcomeTaskBundle,
    ModelExecutionPin,
    OutcomeArtifact,
    OutcomeArtifactKind,
    OutcomeEvent,
    OutcomeSystemPin,
    ProcessMetrics,
    ShadowFixturePin,
    VetoRecord,
    VetoSpec,
    canonical_outcome_receipt_bytes,
    validate_episode_against_task,
)

ScenarioName = Literal[
    "corrupt-derived-state",
    "strict-read-only-success",
    "unauthorized-tool-request",
    "stale-unverified-mutation",
]
OperationKind = Literal["read", "mutate"]

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
_REVISION = "a" * 40
_CANONICAL_BYTES = b"- synthetic graph outcome page\n  - target block\n"
_DERIVED_BYTES = b'{"generation":0,"state":"synthetic"}\n'
_CORRUPT_DERIVED_BYTES = b'{"generation":"invalid","state":\n'
_CANONICAL_NAME = Path("canonical.md")
_DERIVED_NAME = Path("derived/state.json")


@dataclass(frozen=True, slots=True)
class ScriptedToolRequest:
    """One deterministic tool request in a synthetic episode script."""

    tool_id: str
    operation: OperationKind
    stale_unverified: bool = False

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.tool_id):
            raise ValueError("invalid_tool_id")
        if self.operation == "read" and self.stale_unverified:
            raise ValueError("stale_marker_requires_mutation")


@dataclass(frozen=True, slots=True)
class ScriptedScenario:
    """Finite scenario declaration used as the harness extension seam."""

    name: ScenarioName
    steps: tuple[ScriptedToolRequest, ...]


@dataclass(frozen=True, slots=True)
class EpisodeRun:
    """Content-free result retained after both temporary roots are removed."""

    scenario: ScenarioName
    task: GraphOutcomeTaskBundle
    report: EpisodeReport
    receipt: GraphOutcomeReceipt
    receipt_bytes: bytes
    validation_token: str | None
    validation_error: str | None
    initial_canonical_fingerprint: str
    final_canonical_fingerprint: str
    initial_derived_fingerprint: str
    final_derived_fingerprint: str
    roots_distinct: bool
    roots_outside_repository: bool
    cleanup_verified: bool
    executed_tool_ids: tuple[str, ...]
    failure_codes: tuple[str, ...]

    @property
    def validation_succeeded(self) -> bool:
        """Whether the existing protocol validator accepted this report."""
        return self.validation_error is None


@dataclass(frozen=True, slots=True)
class ResetIsolationProof:
    """Proof that two episodes receive fresh roots and do not share state."""

    first: EpisodeRun
    second: EpisodeRun
    distinct_episode_roots: bool
    no_content_leak: bool
    cleanup_verified: bool


@dataclass(frozen=True, slots=True)
class DefaultHarnessRun:
    """The bounded default scenario set and its two-episode reset proof."""

    episodes: tuple[EpisodeRun, ...]
    reset_isolation: ResetIsolationProof


STRICT_READ_ONLY_SUCCESS = ScriptedScenario(
    name="strict-read-only-success",
    steps=(ScriptedToolRequest(tool_id="search-blocks", operation="read"),),
)
UNAUTHORIZED_TOOL_REQUEST = ScriptedScenario(
    name="unauthorized-tool-request",
    steps=(ScriptedToolRequest(tool_id="foreign-tool", operation="read"),),
)
STALE_UNVERIFIED_MUTATION = ScriptedScenario(
    name="stale-unverified-mutation",
    steps=(
        ScriptedToolRequest(
            tool_id="safe-sync-write",
            operation="mutate",
            stale_unverified=True,
        ),
    ),
)
CORRUPT_DERIVED_STATE = ScriptedScenario(
    name="corrupt-derived-state",
    steps=(ScriptedToolRequest(tool_id="search-blocks", operation="read"),),
)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _scenario_digest_payload(scenario: ScriptedScenario) -> dict[str, object]:
    return {
        "scenario": scenario.name,
        "steps": tuple(
            {
                "tool_id": step.tool_id,
                "operation": step.operation,
                "stale_unverified": step.stale_unverified,
            }
            for step in scenario.steps
        ),
    }


def _fingerprint_root(root: Path) -> str:
    """Return a content-free digest of deterministic relative file metadata."""
    records = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _bytes_digest(path.read_bytes()),
            "size": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return _digest(records)


def _assert_owned_roots(canonical_root: Path, derived_root: Path) -> bool:
    """Reject repository/vault roots and prove the two roots are distinct."""
    repository_root = Path(__file__).parent.parent.parent.resolve()
    canonical = canonical_root.resolve()
    derived = derived_root.resolve()
    if canonical == derived:
        raise RuntimeError("episode_roots_must_be_distinct")
    if canonical == repository_root or canonical.is_relative_to(repository_root):
        raise RuntimeError("canonical_root_inside_repository")
    if derived == repository_root or derived.is_relative_to(repository_root):
        raise RuntimeError("derived_root_inside_repository")
    return True


def _materialize(
    canonical_root: Path,
    derived_root: Path,
    *,
    derived_bytes: bytes = _DERIVED_BYTES,
) -> tuple[str, str]:
    """Materialize the only synthetic bytes used by an episode."""
    canonical_path = canonical_root / _CANONICAL_NAME
    derived_path = derived_root / _DERIVED_NAME
    derived_path.parent.mkdir()
    canonical_path.write_bytes(_CANONICAL_BYTES)
    derived_path.write_bytes(derived_bytes)
    return _fingerprint_root(canonical_root), _fingerprint_root(derived_root)


def _provider_free_model() -> ModelExecutionPin:
    return ModelExecutionPin(
        model_id="provider-free",
        model_revision="none",
        prompt_digest="0" * 64,
        provider_free=True,
        temperature_milli=0,
        seed=7,
    )


def _task(
    scenario: ScriptedScenario,
    canonical_fingerprint: str,
    derived_fingerprint: str,
) -> GraphOutcomeTaskBundle:
    mutable = scenario.name == "stale-unverified-mutation"
    corrupt_derived_state = scenario.name == "corrupt-derived-state"
    allowed_tools = ("search-blocks", "safe-sync-write") if mutable else ("search-blocks",)
    return GraphOutcomeTaskBundle(
        schema_version=GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
        task_id=scenario.name,
        fixture_class="synthetic",
        source_repository_slug="synthetic/graph-outcome",
        source_revision=_REVISION,
        license_id="MIT",
        canonical_fixture_digest=canonical_fingerprint,
        initial_shadow=ShadowFixturePin(
            mode="stale" if mutable else "corrupt" if corrupt_derived_state else "fresh",
            digest=derived_fingerprint,
        ),
        initial_request_digest=_digest(_scenario_digest_payload(scenario)),
        disclosure_script_digest=_digest("synthetic-disclosure-v1"),
        human_action_schedule_digest=None,
        contamination_canary_digest=_digest("synthetic-contamination-canary-v1"),
        allowed_tool_ids=allowed_tools,
        policy_mode="approved_safe_sync" if mutable else "strict_read_only",
        approval_profile_id="exact-bytes" if mutable else "disabled",
        occ_profile_id="generation-and-content-hash" if mutable else "disabled",
        failure_injection_profile_id=(
            "corrupt-derived-state-v1" if corrupt_derived_state else "none"
        ),
        budget=EpisodeBudget(
            max_turns=4,
            max_tool_calls=4,
            max_retrieval_calls=4,
            max_mutation_calls=1 if mutable else 0,
            max_retries=0,
            context_token_budget=1_024,
            timeout_seconds=30,
            cost_budget_microunits=0,
        ),
        final_state=FinalStateExpectation(
            required_canonical_invariant_ids=("target-block-present",),
            forbidden_canonical_invariant_ids=("unrelated-block-mutated",),
            required_derived_invariant_ids=("derived-state-isolated",),
            allowed_mutation_ids=("target-block",) if mutable else (),
        ),
        required_communication_fact_ids=("outcome-reported",),
        vetoes=(VetoSpec(veto_id="no-stale-write", category="stale_unverified_mutation"),)
        if mutable
        else (),
    )


def _environment() -> EnvironmentPin:
    return EnvironmentPin(
        harness_revision=_REVISION,
        matryca_revision=_REVISION,
        parser_revision=_REVISION,
        dependency_lock_digest=_digest("synthetic-dependencies-v1"),
        tool_schema_digest=_digest("synthetic-tool-schema-v1"),
        user_actor_protocol_revision=_REVISION,
        human_actor_protocol_revision=_REVISION,
        isolation_policy_id="temporary-roots-only-v1",
        cleanup_policy_id="content-free-failure-metadata-v1",
        os_family="synthetic-os",
        runtime_version="python-3.12",
    )


def _manifest(task: GraphOutcomeTaskBundle, *, task_order: int) -> EpisodeManifest:
    return EpisodeManifest(
        cohort_id="graph-outcome-synthetic-v1",
        task_bundle_digest=task.task_bundle_id,
        system=OutcomeSystemPin(
            role="current_matryca",
            system_id="matryca-plumber",
            implementation_revision=_REVISION,
            configuration_digest=_digest("synthetic-configuration-v1"),
        ),
        environment=_environment(),
        answer_model=_provider_free_model(),
        judge_model=_provider_free_model(),
        task_order=task_order,
        seed=7,
    )


def _event(
    sequence: int,
    event_id: str,
    kind: Literal[
        "canonical_materialized",
        "shadow_materialized",
        "tool_call",
        "tool_result",
        "completion",
        "abstention",
        "veto",
    ],
    payload: object,
    *,
    tool_id: str | None = None,
    argument_digest: str | None = None,
    policy_decision: Literal["not_applicable", "allowed", "rejected"] = "not_applicable",
    success: bool | None = None,
) -> OutcomeEvent:
    return OutcomeEvent(
        sequence=sequence,
        event_id=event_id,
        kind=kind,
        actor="tool" if kind in {"tool_call", "tool_result"} else "environment",
        elapsed_milliseconds=sequence,
        payload_digest=_digest(payload),
        tool_id=tool_id,
        argument_digest=argument_digest,
        policy_decision=policy_decision,
        success=success,
        graph_generation_before=0,
        graph_generation_after=0,
    )


def _dimensions(
    *, process_failed: bool = False, safety_failed: bool = False
) -> tuple[DimensionResult, ...]:
    dimensions: tuple[DimensionName, ...] = (
        "canonical_outcome",
        "derived_state",
        "communication",
        "process_quality",
        "safety",
    )
    results: list[DimensionResult] = []
    for dimension in dimensions:
        failed = (
            (f"{dimension}-failed",)
            if (
                (dimension == "process_quality" and process_failed)
                or (dimension == "safety" and safety_failed)
            )
            else ()
        )
        results.append(
            DimensionResult(
                dimension=dimension,
                status="fail" if failed else "pass",
                passed_check_ids=() if failed else (f"{dimension}-ok",),
                failed_check_ids=failed,
            )
        )
    return tuple(results)


def _report(
    task: GraphOutcomeTaskBundle,
    scenario: ScriptedScenario,
    canonical_fingerprint: str,
    derived_fingerprint: str,
) -> tuple[EpisodeReport, tuple[str, ...]]:
    events: list[OutcomeEvent] = [
        _event(0, "canonical-materialized", "canonical_materialized", {"root": "canonical"}),
        _event(1, "shadow-materialized", "shadow_materialized", {"root": "derived"}),
    ]
    executed: list[str] = []
    rejected = 0
    retrieval_calls = 0
    mutation_calls = 0
    veto_records: tuple[VetoRecord, ...] = ()
    process_failed = False
    safety_failed = False
    status: Literal["completed", "abstained", "vetoed"] = "completed"

    for index, request in enumerate(scenario.steps, start=2):
        argument_digest = _digest(
            {
                "operation": request.operation,
                "stale_unverified": request.stale_unverified,
            }
        )
        allowed = request.tool_id in task.allowed_tool_ids
        if not allowed:
            policy_decision: Literal["allowed", "rejected"] = "rejected"
            rejected += 1
            process_failed = True
            status = "abstained"
        elif request.stale_unverified:
            policy_decision = "rejected"
            rejected += 1
            status = "vetoed"
            safety_failed = True
            veto_event_id = "stale-write-veto"
            veto_records = (
                VetoRecord(
                    veto_id="no-stale-write",
                    category="stale_unverified_mutation",
                    event_id=veto_event_id,
                    evidence_digest=_digest({"event": veto_event_id, "tool": request.tool_id}),
                ),
            )
        elif scenario.name == "corrupt-derived-state":
            policy_decision = "rejected"
            rejected += 1
            status = "abstained"
        else:
            policy_decision = "allowed"
            executed.append(request.tool_id)
            if request.operation == "read":
                retrieval_calls += 1
            else:
                mutation_calls += 1

        events.append(
            _event(
                index,
                f"tool-request-{index}",
                "tool_call",
                {"operation": request.operation, "executed": request.tool_id in executed},
                tool_id=request.tool_id,
                argument_digest=argument_digest,
                policy_decision=policy_decision,
            )
        )
        if status == "vetoed":
            events.append(
                _event(
                    index + 1,
                    "stale-write-veto",
                    "veto",
                    {"category": "stale_unverified_mutation"},
                )
            )
            break
        if not allowed:
            events.append(
                _event(
                    index + 1,
                    "unauthorized-abstention",
                    "abstention",
                    {"reason": "tool-not-allowed"},
                )
            )
            break
        if status == "abstained":
            events.append(
                _event(
                    index + 1,
                    "corrupt-derived-state-no-serve",
                    "abstention",
                    {"reason": "derived-state-corrupt"},
                )
            )
            break
        events.append(
            _event(
                index + 1,
                f"tool-result-{index}",
                "tool_result",
                {"success": True},
                tool_id=request.tool_id,
                success=True,
            )
        )

    if status == "completed":
        events.append(_event(len(events), "episode-complete", "completion", {"status": status}))

    report = EpisodeReport(
        manifest=_manifest(task, task_order=0),
        status=status,
        initial_canonical_fingerprint=canonical_fingerprint,
        initial_shadow_fingerprint=derived_fingerprint,
        final_canonical_fingerprint=canonical_fingerprint,
        final_shadow_fingerprint=derived_fingerprint,
        events=tuple(events),
        dimensions=_dimensions(process_failed=process_failed, safety_failed=safety_failed),
        metrics=ProcessMetrics(
            turns=1,
            tool_calls=len([event for event in events if event.kind == "tool_call"]),
            rejected_tool_calls=rejected,
            retrieval_calls=retrieval_calls,
            mutation_calls=mutation_calls,
            retries=0,
            no_progress_cycles=0,
            context_tokens=128,
            context_bytes=512,
            elapsed_milliseconds=events[-1].elapsed_milliseconds,
            peak_rss_bytes=0,
            cost_microunits=0,
        ),
        veto_records=veto_records,
    )
    return report, tuple(executed)


def _receipt(
    report: EpisodeReport,
    task: GraphOutcomeTaskBundle,
    failure_codes: tuple[str, ...],
) -> GraphOutcomeReceipt:
    artifact_inputs: tuple[tuple[OutcomeArtifactKind, object, int], ...] = (
        (
            "canonical_diff",
            {
                "initial": report.initial_canonical_fingerprint,
                "final": report.final_canonical_fingerprint,
            },
            1,
        ),
        (
            "derived_fingerprints",
            {
                "initial": report.initial_shadow_fingerprint,
                "final": report.final_shadow_fingerprint,
            },
            1,
        ),
        ("exclusions", (), 0),
        ("infrastructure_failures", failure_codes, len(failure_codes)),
        (
            "normalized_event_trajectory",
            tuple(event.model_dump(mode="json") for event in report.events),
            len(report.events),
        ),
        ("resource_metadata", report.metrics.model_dump(mode="json"), 1),
        (
            "rubric_results",
            tuple(item.model_dump(mode="json") for item in report.dimensions),
            len(report.dimensions),
        ),
        (
            "tool_ledger",
            tuple(
                event.model_dump(mode="json")
                for event in report.events
                if event.kind == "tool_call"
            ),
            len([event for event in report.events if event.kind == "tool_call"]),
        ),
        (
            "veto_records",
            tuple(item.model_dump(mode="json") for item in report.veto_records),
            len(report.veto_records),
        ),
    )
    return GraphOutcomeReceipt(
        report_id=report.report_id,
        task_bundle_digest=task.task_bundle_id,
        artifacts=tuple(
            OutcomeArtifact(kind=kind, digest=_digest(value), record_count=count)
            for kind, value, count in artifact_inputs
        ),
    )


def _run_episode(
    scenario: ScriptedScenario,
    root_pairs: list[tuple[Path, Path]] | None = None,
) -> EpisodeRun:
    canonical_path = Path()
    derived_path = Path()
    roots_distinct = False
    roots_outside_repository = False
    with (
        TemporaryDirectory(prefix="matryca-graph-outcome-canonical-") as canonical_name,
        TemporaryDirectory(prefix="matryca-graph-outcome-derived-") as derived_name,
    ):
        canonical_path = Path(canonical_name)
        derived_path = Path(derived_name)
        roots_distinct = _assert_owned_roots(canonical_path, derived_path)
        roots_outside_repository = True
        if root_pairs is not None:
            root_pairs.append((canonical_path, derived_path))
        initial_canonical, initial_derived = _materialize(
            canonical_path,
            derived_path,
            derived_bytes=(
                _CORRUPT_DERIVED_BYTES
                if scenario.name == "corrupt-derived-state"
                else _DERIVED_BYTES
            ),
        )
        task = _task(scenario, initial_canonical, initial_derived)
        report, executed_tool_ids = _report(
            task,
            scenario,
            initial_canonical,
            initial_derived,
        )
        validation_token: str | None = None
        validation_error: str | None = None
        try:
            validation_token = validate_episode_against_task(report, task)
        except EvidenceContractError as exc:
            validation_error = str(exc)
        failure_codes = (validation_error,) if validation_error is not None else ()
        receipt = _receipt(report, task, failure_codes)
        final_canonical = _fingerprint_root(canonical_path)
        final_derived = _fingerprint_root(derived_path)
        receipt_bytes = canonical_outcome_receipt_bytes(receipt)
    return EpisodeRun(
        scenario=scenario.name,
        task=task,
        report=report,
        receipt=receipt,
        receipt_bytes=receipt_bytes,
        validation_token=validation_token,
        validation_error=validation_error,
        initial_canonical_fingerprint=initial_canonical,
        final_canonical_fingerprint=final_canonical,
        initial_derived_fingerprint=initial_derived,
        final_derived_fingerprint=final_derived,
        roots_distinct=roots_distinct,
        roots_outside_repository=roots_outside_repository,
        cleanup_verified=not canonical_path.exists() and not derived_path.exists(),
        executed_tool_ids=executed_tool_ids,
        failure_codes=failure_codes,
    )


def run_episode(scenario: ScriptedScenario) -> EpisodeRun:
    """Run one explicit deterministic scenario in fresh temporary roots."""
    return _run_episode(scenario)


def run_reset_isolation_proof() -> ResetIsolationProof:
    """Run two fresh episodes and retain only their content-free comparison."""
    root_pairs: list[tuple[Path, Path]] = []
    first = _run_episode(STRICT_READ_ONLY_SUCCESS, root_pairs)
    second = _run_episode(STRICT_READ_ONLY_SUCCESS, root_pairs)
    distinct_episode_roots = (
        len(root_pairs) == 2
        and root_pairs[0][0] != root_pairs[1][0]
        and root_pairs[0][1] != root_pairs[1][1]
    )
    no_content_leak = (
        first.initial_canonical_fingerprint == second.initial_canonical_fingerprint
        and first.initial_derived_fingerprint == second.initial_derived_fingerprint
        and first.validation_succeeded
        and second.validation_succeeded
    )
    return ResetIsolationProof(
        first=first,
        second=second,
        distinct_episode_roots=distinct_episode_roots,
        no_content_leak=no_content_leak,
        cleanup_verified=first.cleanup_verified and second.cleanup_verified,
    )


def run_policy_transition_reset_proof() -> ResetIsolationProof:
    """Prove that a vetoed stale write cannot contaminate a later read-only episode."""
    root_pairs: list[tuple[Path, Path]] = []
    first = _run_episode(STALE_UNVERIFIED_MUTATION, root_pairs)
    second = _run_episode(STRICT_READ_ONLY_SUCCESS, root_pairs)
    distinct_episode_roots = (
        len(root_pairs) == 2
        and root_pairs[0][0] != root_pairs[1][0]
        and root_pairs[0][1] != root_pairs[1][1]
    )
    no_content_leak = (
        first.initial_canonical_fingerprint == second.initial_canonical_fingerprint
        and first.initial_derived_fingerprint == second.initial_derived_fingerprint
        and first.final_canonical_fingerprint == second.initial_canonical_fingerprint
        and first.final_derived_fingerprint == second.initial_derived_fingerprint
        and first.validation_succeeded
        and second.validation_succeeded
    )
    return ResetIsolationProof(
        first=first,
        second=second,
        distinct_episode_roots=distinct_episode_roots,
        no_content_leak=no_content_leak,
        cleanup_verified=first.cleanup_verified and second.cleanup_verified,
    )


def run_corrupt_state_reset_proof() -> ResetIsolationProof:
    """Prove a corrupt derived state cannot contaminate a later read-only episode."""
    root_pairs: list[tuple[Path, Path]] = []
    first = _run_episode(CORRUPT_DERIVED_STATE, root_pairs)
    second = _run_episode(STRICT_READ_ONLY_SUCCESS, root_pairs)
    distinct_episode_roots = (
        len(root_pairs) == 2
        and root_pairs[0][0] != root_pairs[1][0]
        and root_pairs[0][1] != root_pairs[1][1]
    )
    no_content_leak = (
        first.initial_canonical_fingerprint == second.initial_canonical_fingerprint
        and first.initial_derived_fingerprint != second.initial_derived_fingerprint
        and first.final_canonical_fingerprint == second.initial_canonical_fingerprint
        and second.validation_succeeded
    )
    return ResetIsolationProof(
        first=first,
        second=second,
        distinct_episode_roots=distinct_episode_roots,
        no_content_leak=no_content_leak,
        cleanup_verified=first.cleanup_verified and second.cleanup_verified,
    )


def run_default_scenarios() -> DefaultHarnessRun:
    """Run the bounded default scenarios and reset-isolation proof."""
    return DefaultHarnessRun(
        episodes=tuple(
            run_episode(scenario)
            for scenario in (
                STRICT_READ_ONLY_SUCCESS,
                UNAUTHORIZED_TOOL_REQUEST,
                STALE_UNVERIFIED_MUTATION,
                CORRUPT_DERIVED_STATE,
            )
        ),
        reset_isolation=run_reset_isolation_proof(),
    )


__all__ = [
    "DefaultHarnessRun",
    "EpisodeRun",
    "ResetIsolationProof",
    "CORRUPT_DERIVED_STATE",
    "STALE_UNVERIFIED_MUTATION",
    "STRICT_READ_ONLY_SUCCESS",
    "ScriptedScenario",
    "ScriptedToolRequest",
    "UNAUTHORIZED_TOOL_REQUEST",
    "run_default_scenarios",
    "run_corrupt_state_reset_proof",
    "run_episode",
    "run_policy_transition_reset_proof",
    "run_reset_isolation_proof",
]
