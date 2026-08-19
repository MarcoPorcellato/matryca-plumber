"""Focused tests for the provider-free graph-outcome harness."""

from __future__ import annotations

from pathlib import Path

from src.memory.graph_outcome_harness import (
    STALE_UNVERIFIED_MUTATION,
    STRICT_READ_ONLY_SUCCESS,
    UNAUTHORIZED_TOOL_REQUEST,
    ScriptedScenario,
    ScriptedToolRequest,
    run_default_scenarios,
    run_episode,
    run_reset_isolation_proof,
)


def test_fresh_roots_and_receipt_are_deterministic() -> None:
    first = run_episode(STRICT_READ_ONLY_SUCCESS)
    second = run_episode(STRICT_READ_ONLY_SUCCESS)

    assert first.initial_canonical_fingerprint == second.initial_canonical_fingerprint
    assert first.initial_derived_fingerprint == second.initial_derived_fingerprint
    assert first.report == second.report
    assert first.receipt == second.receipt
    assert first.receipt_bytes == second.receipt_bytes


def test_roots_are_distinct_outside_repository_and_cleaned_up() -> None:
    result = run_episode(STRICT_READ_ONLY_SUCCESS)

    assert result.roots_distinct
    assert result.roots_outside_repository
    assert result.cleanup_verified


def test_strict_read_only_preserves_identity_and_records_no_mutation() -> None:
    result = run_episode(STRICT_READ_ONLY_SUCCESS)

    assert result.validation_succeeded
    assert result.report.status == "completed"
    assert result.initial_canonical_fingerprint == result.final_canonical_fingerprint
    assert result.initial_derived_fingerprint == result.final_derived_fingerprint
    assert result.report.metrics.mutation_calls == 0
    assert result.executed_tool_ids == ("search-blocks",)


def test_unauthorized_tool_is_rejected_without_execution() -> None:
    result = run_episode(UNAUTHORIZED_TOOL_REQUEST)

    assert not result.validation_succeeded
    assert result.validation_error == "tool_not_allowed_by_task"
    assert result.executed_tool_ids == ()
    assert result.report.status == "abstained"
    tool_call = next(event for event in result.report.events if event.kind == "tool_call")
    assert tool_call.policy_decision == "rejected"
    assert not any(event.kind == "tool_result" for event in result.report.events)


def test_stale_mutation_emits_declared_veto_and_terminal_failure() -> None:
    result = run_episode(STALE_UNVERIFIED_MUTATION)

    assert result.validation_succeeded
    assert result.report.status == "vetoed"
    assert result.report.events[-1].kind == "veto"
    assert result.report.veto_records[0].category == "stale_unverified_mutation"
    assert result.report.veto_records[0].veto_id == "no-stale-write"
    assert result.executed_tool_ids == ()
    assert result.report.metrics.mutation_calls == 0


def test_reset_isolation_proof_has_fresh_roots_and_no_content_leak() -> None:
    proof = run_reset_isolation_proof()

    assert proof.distinct_episode_roots
    assert proof.no_content_leak
    assert proof.cleanup_verified
    assert proof.first.receipt_bytes == proof.second.receipt_bytes


def test_receipt_has_no_paths_or_synthetic_content() -> None:
    result = run_episode(STRICT_READ_ONLY_SUCCESS)
    receipt = result.receipt_bytes.decode("ascii")
    repository = str(Path(__file__).resolve().parents[1])

    assert repository not in receipt
    assert "canonical.md" not in receipt
    assert "synthetic graph outcome page" not in receipt
    assert "/private/" not in receipt
    assert "artifacts" in receipt


def test_default_run_contains_required_scenarios() -> None:
    result = run_default_scenarios()

    assert tuple(item.scenario for item in result.episodes) == (
        "strict-read-only-success",
        "unauthorized-tool-request",
        "stale-unverified-mutation",
    )
    assert result.reset_isolation.no_content_leak


def test_scripted_scenario_seam_is_explicit_and_bounded() -> None:
    scenario = ScriptedScenario(
        name="strict-read-only-success",
        steps=(ScriptedToolRequest(tool_id="search-blocks", operation="read"),),
    )

    result = run_episode(scenario)

    assert result.validation_succeeded
    assert result.report.report_id
