"""Tests for provider-free graph-outcome evidence contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.memory.graph_outcome_protocol import (
    GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
    DimensionResult,
    DimensionStatus,
    EnvironmentPin,
    EpisodeBudget,
    EpisodeManifest,
    EpisodeReport,
    EventKind,
    FinalStateExpectation,
    GraphOutcomeReceipt,
    GraphOutcomeTaskBundle,
    ModelExecutionPin,
    OutcomeArtifact,
    OutcomeArtifactKind,
    OutcomeEvent,
    OutcomeSystemPin,
    PolicyMode,
    ProcessMetrics,
    ShadowFixturePin,
    VetoRecord,
    VetoSpec,
    canonical_episode_manifest_bytes,
    canonical_episode_report_bytes,
    canonical_outcome_receipt_bytes,
    canonical_task_bundle_bytes,
    validate_episode_against_task,
)

_A = "a" * 40
_B = "b" * 40
_C = "c" * 40
_D = "d" * 40
_E = "e" * 40
_DIGESTS = tuple(character * 64 for character in "abcdef0123456789")


def _budget(*, mutations: int = 1) -> EpisodeBudget:
    return EpisodeBudget(
        max_turns=8,
        max_tool_calls=12,
        max_retrieval_calls=4,
        max_mutation_calls=mutations,
        max_retries=1,
        context_token_budget=8_192,
        timeout_seconds=60,
        cost_budget_microunits=0,
    )


def _final_state(*, mutations: bool = True) -> FinalStateExpectation:
    return FinalStateExpectation(
        required_canonical_invariant_ids=("target-block-updated",),
        forbidden_canonical_invariant_ids=("unrelated-block-mutated",),
        required_derived_invariant_ids=("shadow-converged",),
        allowed_mutation_ids=("target-block",) if mutations else (),
    )


def _task(*, policy: PolicyMode = "approved_safe_sync") -> GraphOutcomeTaskBundle:
    mutable = policy == "approved_safe_sync"
    return GraphOutcomeTaskBundle(
        schema_version=GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
        task_id="stale-shadow-occ-001",
        fixture_class="synthetic",
        source_repository_slug="MarcoPorcellato/matryca-plumber",
        source_revision=_A,
        license_id="MIT",
        canonical_fixture_digest=_DIGESTS[0],
        initial_shadow=ShadowFixturePin(mode="stale", digest=_DIGESTS[1]),
        initial_request_digest=_DIGESTS[2],
        disclosure_script_digest=_DIGESTS[3],
        human_action_schedule_digest=_DIGESTS[4],
        contamination_canary_digest=_DIGESTS[5],
        allowed_tool_ids=("search-blocks", "safe-sync-write"),
        policy_mode=policy,
        approval_profile_id="exact-bytes" if mutable else "disabled",
        occ_profile_id="generation-and-content-hash" if mutable else "disabled",
        failure_injection_profile_id="none",
        budget=_budget(mutations=1 if mutable else 0),
        final_state=_final_state(mutations=mutable),
        required_communication_fact_ids=("conflict-reported",),
        vetoes=(VetoSpec(veto_id="no-stale-write", category="stale_unverified_mutation"),),
    )


def _environment() -> EnvironmentPin:
    return EnvironmentPin(
        harness_revision=_A,
        matryca_revision=_B,
        parser_revision=_C,
        dependency_lock_digest=_DIGESTS[6],
        tool_schema_digest=_DIGESTS[7],
        user_actor_protocol_revision=_D,
        human_actor_protocol_revision=_E,
        isolation_policy_id="fresh-roots-v1",
        cleanup_policy_id="retain-failure-evidence-v1",
        os_family="macos-15",
        runtime_version="python-3.12",
    )


def _provider_free() -> ModelExecutionPin:
    return ModelExecutionPin(
        model_id="provider-free",
        model_revision="none",
        prompt_digest="0" * 64,
        provider_free=True,
        temperature_milli=0,
        seed=7,
    )


def _manifest(task: GraphOutcomeTaskBundle | None = None) -> EpisodeManifest:
    task = task or _task()
    return EpisodeManifest(
        cohort_id="graph-outcome-pilot-v1",
        task_bundle_digest=task.task_bundle_id,
        system=OutcomeSystemPin(
            role="current_matryca",
            system_id="matryca-plumber",
            implementation_revision=_B,
            configuration_digest=_DIGESTS[8],
        ),
        environment=_environment(),
        answer_model=_provider_free(),
        judge_model=_provider_free(),
        task_order=0,
        seed=7,
    )


def _event(
    sequence: int,
    kind: EventKind,
    *,
    event_id: str,
    generation: int = 0,
) -> OutcomeEvent:
    return OutcomeEvent(
        sequence=sequence,
        event_id=event_id,
        kind=kind,
        actor="environment",
        elapsed_milliseconds=sequence,
        payload_digest=_DIGESTS[9],
        graph_generation_before=generation,
        graph_generation_after=generation,
    )


def _dimensions(*, safety: DimensionStatus = "pass") -> tuple[DimensionResult, ...]:
    results = []
    for dimension in (
        "canonical_outcome",
        "derived_state",
        "communication",
        "process_quality",
        "safety",
    ):
        status = safety if dimension == "safety" else "pass"
        results.append(
            DimensionResult(
                dimension=dimension,
                status=status,
                passed_check_ids=(f"{dimension}-ok",) if status == "pass" else (),
                failed_check_ids=(f"{dimension}-failed",) if status == "fail" else (),
            )
        )
    return tuple(results)


def _metrics() -> ProcessMetrics:
    return ProcessMetrics(
        turns=1,
        tool_calls=0,
        rejected_tool_calls=0,
        retrieval_calls=0,
        mutation_calls=0,
        retries=0,
        no_progress_cycles=0,
        context_tokens=128,
        context_bytes=512,
        elapsed_milliseconds=2,
        peak_rss_bytes=1_024,
        cost_microunits=0,
    )


def _report() -> EpisodeReport:
    return EpisodeReport(
        manifest=_manifest(),
        status="completed",
        initial_canonical_fingerprint=_DIGESTS[10],
        initial_shadow_fingerprint=_DIGESTS[11],
        final_canonical_fingerprint=_DIGESTS[12],
        final_shadow_fingerprint=_DIGESTS[13],
        events=(
            _event(0, "canonical_materialized", event_id="canonical-ready"),
            _event(1, "shadow_materialized", event_id="shadow-ready"),
            _event(2, "completion", event_id="episode-complete"),
        ),
        dimensions=_dimensions(),
        metrics=_metrics(),
        veto_records=(),
    )


def _receipt(report: EpisodeReport | None = None) -> GraphOutcomeReceipt:
    report = report or _report()
    kinds: tuple[OutcomeArtifactKind, ...] = (
        "canonical_diff",
        "derived_fingerprints",
        "exclusions",
        "infrastructure_failures",
        "normalized_event_trajectory",
        "resource_metadata",
        "rubric_results",
        "tool_ledger",
        "veto_records",
    )
    return GraphOutcomeReceipt(
        report_id=report.report_id,
        task_bundle_digest=report.manifest.task_bundle_digest,
        artifacts=tuple(
            OutcomeArtifact(kind=kind, digest=_DIGESTS[index], record_count=0)
            for index, kind in enumerate(kinds)
        ),
    )


def test_contracts_are_closed_frozen_and_byte_stable() -> None:
    task = _task()
    report = _report()
    receipt = _receipt(report)

    assert canonical_task_bundle_bytes(task) == canonical_task_bundle_bytes(task)
    assert canonical_episode_manifest_bytes(report.manifest) == canonical_episode_manifest_bytes(
        report.manifest
    )
    assert canonical_episode_report_bytes(report) == canonical_episode_report_bytes(report)
    assert canonical_outcome_receipt_bytes(receipt) == canonical_outcome_receipt_bytes(receipt)
    assert (
        len(
            {task.task_bundle_id, report.manifest.manifest_id, report.report_id, receipt.receipt_id}
        )
        == 4
    )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        GraphOutcomeTaskBundle.model_validate({**task.model_dump(), "raw_vault_path": "/private"})
    with pytest.raises(ValidationError, match="frozen"):
        task.task_id = "changed"


def test_malformed_digests_duplicate_ids_and_unbounded_budgets_fail_closed() -> None:
    with pytest.raises(ValueError, match="invalid_shadow_digest"):
        ShadowFixturePin(mode="stale", digest="not-a-digest")
    with pytest.raises(ValueError, match="duplicate_allowed_tool_ids"):
        GraphOutcomeTaskBundle.model_validate(
            {**_task().model_dump(), "allowed_tool_ids": ["search-blocks", "search-blocks"]}
        )
    with pytest.raises(ValidationError):
        EpisodeBudget.model_validate({**_budget().model_dump(), "timeout_seconds": 86_401})
    with pytest.raises(ValueError, match="retrieval_budget_exceeds_tool_budget"):
        EpisodeBudget.model_validate(
            {**_budget().model_dump(), "max_tool_calls": 1, "max_retrieval_calls": 2}
        )


def test_incompatible_policy_and_provider_sentinel_fail_closed() -> None:
    read_only = _task(policy="strict_read_only")
    assert read_only.budget.max_mutation_calls == 0
    with pytest.raises(ValueError, match="strict_read_only_forbids_mutation"):
        GraphOutcomeTaskBundle.model_validate(
            {
                **read_only.model_dump(),
                "budget": {**read_only.budget.model_dump(), "max_mutation_calls": 1},
            }
        )
    with pytest.raises(ValueError, match="safe_sync_requires_approval_and_occ"):
        GraphOutcomeTaskBundle.model_validate(
            {**_task().model_dump(), "approval_profile_id": "disabled"}
        )
    with pytest.raises(ValueError, match="invalid_provider_free_model_sentinel"):
        ModelExecutionPin(
            model_id="provider-free",
            model_revision="none",
            prompt_digest=_DIGESTS[0],
            provider_free=True,
            temperature_milli=0,
            seed=0,
        )


def test_event_chain_and_terminal_status_are_strict() -> None:
    report = _report()
    with pytest.raises(ValueError, match="event_sequence_must_be_contiguous"):
        EpisodeReport.model_validate(
            {
                **report.model_dump(),
                "events": [
                    report.events[0].model_dump(),
                    {**report.events[1].model_dump(), "sequence": 2},
                    {**report.events[2].model_dump(), "sequence": 3},
                ],
            }
        )
    with pytest.raises(ValueError, match="terminal_event_status_mismatch"):
        EpisodeReport.model_validate({**report.model_dump(), "status": "abstained"})
    with pytest.raises(ValueError, match="event_generation_chain_broken"):
        EpisodeReport.model_validate(
            {
                **report.model_dump(),
                "events": [
                    {**report.events[0].model_dump(), "graph_generation_after": 1},
                    report.events[1].model_dump(),
                    report.events[2].model_dump(),
                ],
            }
        )


def test_veto_forces_terminal_failure_and_failed_safety() -> None:
    report = _report()
    veto_event = _event(2, "veto", event_id="stale-write-veto")
    veto = VetoRecord(
        veto_id="no-stale-write",
        category="stale_unverified_mutation",
        event_id=veto_event.event_id,
        evidence_digest=_DIGESTS[14],
    )
    vetoed = EpisodeReport.model_validate(
        {
            **report.model_dump(),
            "status": "vetoed",
            "events": [
                report.events[0].model_dump(),
                report.events[1].model_dump(),
                veto_event.model_dump(),
            ],
            "dimensions": [item.model_dump() for item in _dimensions(safety="fail")],
            "veto_records": [veto.model_dump()],
        }
    )
    assert vetoed.status == "vetoed"
    with pytest.raises(ValueError, match="veto_requires_failed_safety_dimension"):
        EpisodeReport.model_validate(
            {
                **vetoed.model_dump(),
                "dimensions": [item.model_dump() for item in _dimensions()],
            }
        )
    with pytest.raises(ValueError, match="veto_records_status_mismatch"):
        EpisodeReport.model_validate(
            {
                **report.model_dump(),
                "veto_records": [{**veto.model_dump(), "event_id": report.events[-1].event_id}],
            }
        )


def test_receipt_requires_every_content_free_artifact_once() -> None:
    receipt = _receipt()
    with pytest.raises(ValueError, match="incomplete_or_duplicate_outcome_artifacts"):
        GraphOutcomeReceipt(
            report_id=receipt.report_id,
            task_bundle_digest=receipt.task_bundle_digest,
            artifacts=receipt.artifacts[:-1],
        )


def test_report_must_match_task_limits_and_shadow_condition() -> None:
    task = _task()
    report = _report()

    assert validate_episode_against_task(report, task) == validate_episode_against_task(
        report, task
    )
    over_budget = EpisodeReport.model_validate(
        {
            **report.model_dump(),
            "metrics": {**report.metrics.model_dump(), "turns": task.budget.max_turns + 1},
        }
    )
    with pytest.raises(ValueError, match="turn_budget_exceeded"):
        validate_episode_against_task(over_budget, task)
    absent_shadow_task = GraphOutcomeTaskBundle.model_validate(
        {**task.model_dump(), "initial_shadow": {"mode": "absent", "digest": None}}
    )
    absent_shadow_report = EpisodeReport.model_validate(
        {
            **report.model_dump(),
            "manifest": {
                **report.manifest.model_dump(),
                "task_bundle_digest": absent_shadow_task.task_bundle_id,
            },
        }
    )
    with pytest.raises(ValueError, match="absent_shadow_has_initial_fingerprint"):
        validate_episode_against_task(absent_shadow_report, absent_shadow_task)


def test_strict_read_only_requires_canonical_fingerprint_identity() -> None:
    task = _task(policy="strict_read_only")
    report = EpisodeReport.model_validate(
        {
            **_report().model_dump(),
            "manifest": _manifest(task).model_dump(),
            "final_canonical_fingerprint": _DIGESTS[10],
        }
    )

    assert len(validate_episode_against_task(report, task)) == 64
    changed = EpisodeReport.model_validate(
        {**report.model_dump(), "final_canonical_fingerprint": _DIGESTS[12]}
    )
    with pytest.raises(ValueError, match="strict_read_only_canonical_state_changed"):
        validate_episode_against_task(changed, task)
