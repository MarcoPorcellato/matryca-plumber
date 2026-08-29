"""Fail-closed projection of canonical graph-outcome episode evidence."""

from __future__ import annotations

import re
from typing import Literal, cast

from src.memory.evidence_models import EvidenceContractError
from src.memory.graph_outcome_harness import EpisodeRun
from src.memory.graph_outcome_protocol import (
    GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
    canonical_outcome_receipt_bytes,
    validate_episode_against_task,
)

from tools.evaluation_projection.schema import (
    GraphOutcomeEvaluationProjection,
    GraphOutcomeEvaluationSuite,
    GraphOutcomeProjectionPayload,
    GraphOutcomeSuitePayload,
    ProjectionArtifact,
    ProjectionDimension,
    ProjectionMetrics,
    build_projection,
    build_suite,
)

_REVISION = re.compile(r"^[0-9a-f]{40}$")


class ProjectionEvidenceError(ValueError):
    """Stable content-free evidence-rejection code."""


def _require_source_revision(source_revision: str) -> None:
    if not isinstance(source_revision, str) or not _REVISION.fullmatch(source_revision):
        raise ProjectionEvidenceError("source_revision_invalid")


def _validation_status(run: EpisodeRun) -> Literal["passed", "rejected"]:
    try:
        replayed_token = validate_episode_against_task(run.report, run.task)
    except EvidenceContractError as exc:
        code = str(exc)
        if (
            run.validation_token is not None
            or run.validation_error != code
            or run.failure_codes != (code,)
        ):
            raise ProjectionEvidenceError("validation_replay_mismatch") from None
        return "rejected"
    if (
        run.validation_token != replayed_token
        or run.validation_error is not None
        or run.failure_codes
    ):
        raise ProjectionEvidenceError("validation_replay_mismatch")
    return "passed"


def _require_receipt_identity(run: EpisodeRun) -> None:
    if run.receipt.report_id != run.report.report_id:
        raise ProjectionEvidenceError("receipt_report_mismatch")
    if run.receipt.task_bundle_digest != run.task.task_bundle_id:
        raise ProjectionEvidenceError("receipt_task_mismatch")
    if canonical_outcome_receipt_bytes(run.receipt) != run.receipt_bytes:
        raise ProjectionEvidenceError("receipt_bytes_mismatch")


def project_episode(run: EpisodeRun, *, source_revision: str) -> GraphOutcomeEvaluationProjection:
    """Project one exact canonical episode only after evidence replay."""
    if type(run) is not EpisodeRun:
        raise ProjectionEvidenceError("episode_type_unsupported")
    _require_source_revision(source_revision)
    validation_status = _validation_status(run)
    _require_receipt_identity(run)
    if run.scenario != run.task.task_id:
        raise ProjectionEvidenceError("scenario_mismatch")
    if not run.roots_distinct or not run.roots_outside_repository:
        raise ProjectionEvidenceError("episode_isolation_unproven")
    if not run.cleanup_verified:
        raise ProjectionEvidenceError("episode_cleanup_unproven")

    return build_projection(
        GraphOutcomeProjectionPayload(
            source_revision=source_revision,
            protocol_schema_version=cast(
                Literal["graph-outcome-protocol.v1"],
                GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
            ),
            scenario=run.scenario,
            policy_mode=run.task.policy_mode,
            task_bundle_digest=run.task.task_bundle_id,
            report_id=run.report.report_id,
            receipt_id=run.receipt.receipt_id,
            terminal_status=run.report.status,
            validation_status=validation_status,
            failure_codes=run.failure_codes,
            executed_tool_ids=run.executed_tool_ids,
            dimensions=tuple(
                ProjectionDimension(
                    dimension=item.dimension,
                    status=item.status,
                    passed_check_ids=item.passed_check_ids,
                    failed_check_ids=item.failed_check_ids,
                )
                for item in run.report.dimensions
            ),
            metrics=ProjectionMetrics(
                turns=run.report.metrics.turns,
                tool_calls=run.report.metrics.tool_calls,
                rejected_tool_calls=run.report.metrics.rejected_tool_calls,
                retrieval_calls=run.report.metrics.retrieval_calls,
                mutation_calls=run.report.metrics.mutation_calls,
                retries=run.report.metrics.retries,
                no_progress_cycles=run.report.metrics.no_progress_cycles,
                context_tokens=run.report.metrics.context_tokens,
                context_bytes=run.report.metrics.context_bytes,
                elapsed_milliseconds=run.report.metrics.elapsed_milliseconds,
                peak_rss_bytes=run.report.metrics.peak_rss_bytes,
                cost_microunits=run.report.metrics.cost_microunits,
            ),
            initial_canonical_fingerprint=run.initial_canonical_fingerprint,
            final_canonical_fingerprint=run.final_canonical_fingerprint,
            initial_derived_fingerprint=run.initial_derived_fingerprint,
            final_derived_fingerprint=run.final_derived_fingerprint,
            roots_distinct=True,
            roots_outside_repository=True,
            cleanup_verified=True,
            artifacts=tuple(
                ProjectionArtifact(
                    kind=item.kind,
                    digest=item.digest,
                    record_count=item.record_count,
                )
                for item in run.receipt.artifacts
            ),
        )
    )


def project_suite(
    episodes: tuple[EpisodeRun, ...], *, source_revision: str
) -> GraphOutcomeEvaluationSuite:
    """Project exactly the closed default scenario suite."""
    projections = tuple(project_episode(run, source_revision=source_revision) for run in episodes)
    return build_suite(
        GraphOutcomeSuitePayload(
            source_revision=source_revision,
            protocol_schema_version=cast(
                Literal["graph-outcome-protocol.v1"],
                GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
            ),
            projections=projections,
        )
    )


__all__ = ["ProjectionEvidenceError", "project_episode", "project_suite"]
