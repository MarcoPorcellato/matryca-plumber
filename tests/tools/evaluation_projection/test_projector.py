"""Tests for the fail-closed canonical outcome-evidence projector."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import cast

import pytest
from src.memory.benchmark_protocol import BenchmarkRunReport
from src.memory.graph_outcome_harness import EpisodeRun, run_default_scenarios
from src.memory.graph_outcome_protocol import (
    canonical_episode_report_bytes,
    canonical_outcome_receipt_bytes,
    canonical_task_bundle_bytes,
)
from tools.evaluation_projection.projector import (
    ProjectionEvidenceError,
    project_episode,
    project_suite,
)

_REVISION = "b" * 40
_SCENARIOS = {
    "corrupt-derived-state",
    "stale-unverified-mutation",
    "strict-read-only-success",
    "unauthorized-tool-request",
}


def _episodes() -> tuple[EpisodeRun, ...]:
    return run_default_scenarios().episodes


def test_default_episodes_project_without_changing_canonical_evidence() -> None:
    episodes = _episodes()
    before = tuple(
        (
            canonical_task_bundle_bytes(run.task),
            canonical_episode_report_bytes(run.report),
            canonical_outcome_receipt_bytes(run.receipt),
        )
        for run in episodes
    )

    suite = project_suite(episodes, source_revision=_REVISION)

    after = tuple(
        (
            canonical_task_bundle_bytes(run.task),
            canonical_episode_report_bytes(run.report),
            canonical_outcome_receipt_bytes(run.receipt),
        )
        for run in episodes
    )
    assert before == after
    assert tuple(item.scenario for item in suite.projections) == tuple(sorted(_SCENARIOS))


def test_default_projection_preserves_typed_evidence_fields() -> None:
    for run in _episodes():
        projection = project_episode(run, source_revision=_REVISION)

        assert projection.policy_mode == run.task.policy_mode
        assert projection.task_bundle_digest == run.task.task_bundle_id
        assert projection.report_id == run.report.report_id
        assert projection.receipt_id == run.receipt.receipt_id
        assert projection.terminal_status == run.report.status
        assert projection.executed_tool_ids == run.executed_tool_ids
        assert projection.initial_canonical_fingerprint == run.initial_canonical_fingerprint
        assert projection.final_canonical_fingerprint == run.final_canonical_fingerprint
        assert projection.initial_derived_fingerprint == run.initial_derived_fingerprint
        assert projection.final_derived_fingerprint == run.final_derived_fingerprint
        assert projection.roots_distinct is run.roots_distinct
        assert projection.roots_outside_repository is run.roots_outside_repository
        assert projection.cleanup_verified is run.cleanup_verified
        assert tuple(item.model_dump() for item in projection.dimensions) == tuple(
            {
                "dimension": item.dimension,
                "status": item.status,
                "passed_check_ids": item.passed_check_ids,
                "failed_check_ids": item.failed_check_ids,
            }
            for item in run.report.dimensions
        )
        assert projection.metrics.model_dump() == run.report.metrics.model_dump()
        assert tuple(item.model_dump() for item in projection.artifacts) == tuple(
            item.model_dump() for item in run.receipt.artifacts
        )
        if run.scenario == "unauthorized-tool-request":
            assert projection.validation_status == "rejected"
            assert projection.failure_codes == ("tool_not_allowed_by_task",)
        else:
            assert projection.validation_status == "passed"
            assert projection.failure_codes == ()


@dataclass(frozen=True, slots=True)
class _EpisodeRunSubclass(EpisodeRun):
    """Adversarial exact-type escape attempt."""


def _subclass_episode() -> EpisodeRun:
    run = _episodes()[0]
    return _EpisodeRunSubclass(
        scenario=run.scenario,
        task=run.task,
        report=run.report,
        receipt=run.receipt,
        receipt_bytes=run.receipt_bytes,
        validation_token=run.validation_token,
        validation_error=run.validation_error,
        initial_canonical_fingerprint=run.initial_canonical_fingerprint,
        final_canonical_fingerprint=run.final_canonical_fingerprint,
        initial_derived_fingerprint=run.initial_derived_fingerprint,
        final_derived_fingerprint=run.final_derived_fingerprint,
        roots_distinct=run.roots_distinct,
        roots_outside_repository=run.roots_outside_repository,
        cleanup_verified=run.cleanup_verified,
        executed_tool_ids=run.executed_tool_ids,
        failure_codes=run.failure_codes,
    )


@pytest.mark.parametrize(
    "value",
    (
        {"scenario": "strict-read-only-success"},
        BenchmarkRunReport.model_construct(),
        _subclass_episode(),
    ),
)
def test_project_episode_rejects_non_exact_episode_run_before_field_access(value: object) -> None:
    with pytest.raises(ProjectionEvidenceError, match="^episode_type_unsupported$"):
        project_episode(cast(EpisodeRun, value), source_revision=_REVISION)


@pytest.mark.parametrize(
    ("run", "code"),
    (
        (
            lambda run: replace(run, validation_token="0" * 64),
            "validation_replay_mismatch",
        ),
        (
            lambda run: replace(run, validation_error="wrong", failure_codes=("wrong",)),
            "validation_replay_mismatch",
        ),
        (
            lambda run: replace(
                run, receipt=run.receipt.model_copy(update={"report_id": "0" * 64})
            ),
            "receipt_report_mismatch",
        ),
        (
            lambda run: replace(
                run, receipt=run.receipt.model_copy(update={"task_bundle_digest": "0" * 64})
            ),
            "receipt_task_mismatch",
        ),
        (lambda run: replace(run, receipt_bytes=b"changed"), "receipt_bytes_mismatch"),
        (lambda run: replace(run, scenario="corrupt-derived-state"), "scenario_mismatch"),
        (lambda run: replace(run, roots_distinct=False), "episode_isolation_unproven"),
        (lambda run: replace(run, cleanup_verified=False), "episode_cleanup_unproven"),
    ),
)
def test_project_episode_rejects_mismatched_evidence(
    run: Callable[[EpisodeRun], EpisodeRun], code: str
) -> None:
    changed = run(next(item for item in _episodes() if item.scenario == "strict-read-only-success"))

    with pytest.raises(ProjectionEvidenceError, match=rf"^{code}$"):
        project_episode(changed, source_revision=_REVISION)


@pytest.mark.parametrize("source_revision", ("", "A" * 40, "a" * 39))
def test_project_episode_rejects_invalid_source_revision(source_revision: str) -> None:
    with pytest.raises(ProjectionEvidenceError, match="^source_revision_invalid$"):
        project_episode(_episodes()[0], source_revision=source_revision)


def test_project_episode_rejects_non_string_source_revision() -> None:
    with pytest.raises(ProjectionEvidenceError, match="^source_revision_invalid$"):
        project_episode(_episodes()[0], source_revision=cast(str, 7))
