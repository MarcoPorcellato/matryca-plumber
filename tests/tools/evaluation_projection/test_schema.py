"""Tests for the closed graph-outcome evaluation projection schema."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest
from pydantic import ValidationError
from src.memory.graph_outcome_protocol import DimensionName, OutcomeArtifactKind
from tools.evaluation_projection.schema import (
    GraphOutcomeEvaluationProjection,
    GraphOutcomeProjectionPayload,
    GraphOutcomeSuitePayload,
    ProjectionArtifact,
    ProjectionDimension,
    ProjectionMetrics,
    ProjectionScenario,
    build_projection,
    build_suite,
    canonical_projection_bytes,
    canonical_suite_bytes,
)

_REVISION = "a" * 40
_DIGEST = "1" * 64
_PROJECTION_GOLDEN = "952ffcce8a866082fe925917763cfc6b84dc29c03b3b37f0cc5023db76b9c451"
_SUITE_GOLDEN = "09d7c2ac860dcde31406cb172b989a91ad31e689d039eeadc8c2ea08ae55fa54"
_SCENARIOS: tuple[ProjectionScenario, ...] = (
    "corrupt-derived-state",
    "stale-unverified-mutation",
    "strict-read-only-success",
    "unauthorized-tool-request",
)
_DIMENSIONS: tuple[DimensionName, ...] = (
    "canonical_outcome",
    "derived_state",
    "communication",
    "process_quality",
    "safety",
)
_ARTIFACT_KINDS: tuple[OutcomeArtifactKind, ...] = (
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


def _payload(
    *,
    source_revision: str = _REVISION,
    scenario: ProjectionScenario = "strict-read-only-success",
) -> GraphOutcomeProjectionPayload:
    return GraphOutcomeProjectionPayload(
        source_revision=source_revision,
        protocol_schema_version="graph-outcome-protocol.v1",
        scenario=scenario,
        policy_mode="strict_read_only",
        task_bundle_digest=_DIGEST,
        report_id="2" * 64,
        receipt_id="3" * 64,
        terminal_status="completed",
        validation_status="passed",
        failure_codes=("first-failure", "second-failure"),
        executed_tool_ids=("search-blocks", "safe-sync-write"),
        dimensions=tuple(
            ProjectionDimension(
                dimension=dimension,
                status="pass",
                passed_check_ids=(f"{dimension}-first", f"{dimension}-second"),
                failed_check_ids=(),
            )
            for dimension in _DIMENSIONS
        ),
        metrics=ProjectionMetrics(
            turns=1,
            tool_calls=3,
            rejected_tool_calls=1,
            retrieval_calls=2,
            mutation_calls=1,
            retries=1,
            no_progress_cycles=1,
            context_tokens=128,
            context_bytes=512,
            elapsed_milliseconds=2,
            peak_rss_bytes=1_024,
            cost_microunits=3,
        ),
        initial_canonical_fingerprint="4" * 64,
        final_canonical_fingerprint="5" * 64,
        initial_derived_fingerprint="6" * 64,
        final_derived_fingerprint="7" * 64,
        roots_distinct=True,
        roots_outside_repository=True,
        cleanup_verified=True,
        artifacts=tuple(
            ProjectionArtifact(kind=kind, digest=f"{index:x}" * 64, record_count=index)
            for index, kind in enumerate(_ARTIFACT_KINDS, start=1)
        ),
    )


def _reordered_payload() -> GraphOutcomeProjectionPayload:
    payload = _payload()
    return GraphOutcomeProjectionPayload(
        **{
            **payload.model_dump(),
            "failure_codes": tuple(reversed(payload.failure_codes)),
            "executed_tool_ids": tuple(reversed(payload.executed_tool_ids)),
            "dimensions": tuple(
                ProjectionDimension(
                    **{
                        **dimension.model_dump(),
                        "passed_check_ids": tuple(reversed(dimension.passed_check_ids)),
                    }
                )
                for dimension in reversed(payload.dimensions)
            ),
            "artifacts": tuple(reversed(payload.artifacts)),
        }
    )


def _four_projections() -> tuple[GraphOutcomeEvaluationProjection, ...]:
    return tuple(build_projection(_payload(scenario=name)) for name in _SCENARIOS)


def _replace_payload(
    payload: GraphOutcomeProjectionPayload, **changes: object
) -> GraphOutcomeProjectionPayload:
    return GraphOutcomeProjectionPayload.model_validate({**payload.model_dump(), **changes})


def test_projection_and_suite_have_stable_canonical_identities() -> None:
    first = build_projection(_payload())
    second = build_projection(_payload())
    suite = build_suite(
        GraphOutcomeSuitePayload(
            source_revision=_REVISION,
            protocol_schema_version="graph-outcome-protocol.v1",
            projections=_four_projections(),
        )
    )

    assert first == second
    assert first.projection_id == _PROJECTION_GOLDEN
    assert len(first.projection_id) == 64
    assert canonical_projection_bytes(first).endswith(b"\n")
    assert suite.suite_id == _SUITE_GOLDEN
    assert len(suite.suite_id) == 64
    assert canonical_suite_bytes(suite).endswith(b"\n")


def test_reordered_closed_collections_are_byte_identical() -> None:
    original = build_projection(_payload())
    reordered = build_projection(_reordered_payload())

    assert canonical_projection_bytes(original) == canonical_projection_bytes(reordered)


def test_changed_allowlisted_value_invalidates_identity() -> None:
    original = build_projection(_payload())
    changed = build_projection(_payload(source_revision="b" * 40))

    assert original.projection_id != changed.projection_id


def test_closed_models_reject_unknown_fields_and_invalid_hashes() -> None:
    with pytest.raises(ValidationError):
        ProjectionArtifact.model_validate(
            {"kind": "tool_ledger", "digest": "bad", "record_count": 1, "extra": "x"}
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda payload: _replace_payload(payload, source_revision="b" * 40),
        lambda payload: _replace_payload(payload, scenario="corrupt-derived-state"),
        lambda payload: _replace_payload(payload, policy_mode="proposal_only"),
        lambda payload: _replace_payload(payload, task_bundle_digest="8" * 64),
        lambda payload: _replace_payload(payload, report_id="9" * 64),
        lambda payload: _replace_payload(payload, receipt_id="a" * 64),
        lambda payload: _replace_payload(payload, terminal_status="abstained"),
        lambda payload: _replace_payload(payload, validation_status="rejected"),
        lambda payload: _replace_payload(
            payload, failure_codes=("changed-failure", "second-failure")
        ),
        lambda payload: _replace_payload(
            payload, executed_tool_ids=("changed-tool", "safe-sync-write")
        ),
        lambda payload: _replace_payload(
            payload,
            dimensions=(
                ProjectionDimension(
                    dimension="canonical_outcome",
                    status="pass",
                    passed_check_ids=("changed-check", "canonical_outcome-second"),
                    failed_check_ids=(),
                ),
                *payload.dimensions[1:],
            ),
        ),
        lambda payload: _replace_payload(
            payload,
            metrics=ProjectionMetrics(
                **{**payload.metrics.model_dump(), "turns": payload.metrics.turns + 1}
            ),
        ),
        lambda payload: _replace_payload(payload, initial_canonical_fingerprint="b" * 64),
        lambda payload: _replace_payload(payload, final_canonical_fingerprint="c" * 64),
        lambda payload: _replace_payload(payload, initial_derived_fingerprint="d" * 64),
        lambda payload: _replace_payload(payload, final_derived_fingerprint="e" * 64),
        lambda payload: _replace_payload(
            payload,
            artifacts=(
                ProjectionArtifact(kind="canonical_diff", digest="f" * 64, record_count=1),
                *payload.artifacts[1:],
            ),
        ),
    ],
)
def test_each_approved_payload_value_contributes_to_identity(
    change: Callable[[GraphOutcomeProjectionPayload], GraphOutcomeProjectionPayload],
) -> None:
    original = build_projection(_payload())
    changed = build_projection(change(_payload()))

    assert original.projection_id != changed.projection_id


@pytest.mark.parametrize(
    "metric_name",
    (
        "tool_calls",
        "rejected_tool_calls",
        "retrieval_calls",
        "mutation_calls",
        "retries",
        "no_progress_cycles",
        "context_tokens",
        "context_bytes",
        "elapsed_milliseconds",
        "peak_rss_bytes",
        "cost_microunits",
    ),
)
def test_each_non_turn_metric_contributes_to_identity(metric_name: str) -> None:
    payload = _payload()
    metrics = ProjectionMetrics(
        **{**payload.metrics.model_dump(), metric_name: getattr(payload.metrics, metric_name) + 1}
    )

    assert (
        build_projection(payload).projection_id
        != build_projection(_replace_payload(payload, metrics=metrics)).projection_id
    )


def test_dimension_status_and_artifact_count_contribute_to_identity() -> None:
    payload = _payload()
    failed_dimension = ProjectionDimension(
        dimension="canonical_outcome",
        status="fail",
        passed_check_ids=(),
        failed_check_ids=("canonical-outcome-failed",),
    )
    failed = _replace_payload(payload, dimensions=(failed_dimension, *payload.dimensions[1:]))
    changed_artifact = _replace_payload(
        payload,
        artifacts=(
            ProjectionArtifact(kind="canonical_diff", digest="1" * 64, record_count=99),
            *payload.artifacts[1:],
        ),
    )

    assert build_projection(payload).projection_id != build_projection(failed).projection_id
    assert (
        build_projection(payload).projection_id != build_projection(changed_artifact).projection_id
    )


@pytest.mark.parametrize(
    "change",
    (
        {"roots_distinct": False},
        {"roots_outside_repository": False},
        {"cleanup_verified": False},
        {"dimensions": _payload().dimensions[:-1]},
        {"dimensions": (*_payload().dimensions[:-1], _payload().dimensions[0])},
        {"artifacts": _payload().artifacts[:-1]},
        {"artifacts": (*_payload().artifacts[:-1], _payload().artifacts[0])},
        {"dimensions": "invalid_dimension_checks"},
        {"metrics": "inconsistent_metrics"},
        {"schema_version": "unsupported"},
        {"protocol_schema_version": "unsupported"},
        {"failure_codes": ("a" * 97,)},
    ),
)
def test_projection_payload_rejects_closed_contract_violations(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        if change.get("dimensions") == "invalid_dimension_checks":
            change = {
                "dimensions": (
                    ProjectionDimension(
                        dimension="canonical_outcome",
                        status="pass",
                        passed_check_ids=("passed",),
                        failed_check_ids=("failed",),
                    ),
                    *_payload().dimensions[1:],
                )
            }
        if change.get("metrics") == "inconsistent_metrics":
            change = {
                "metrics": ProjectionMetrics(
                    **{**_payload().metrics.model_dump(), "rejected_tool_calls": 4}
                )
            }
        _replace_payload(_payload(), **change)


def test_suite_rejects_invalid_membership_and_provenance() -> None:
    projections = _four_projections()
    with pytest.raises(ValueError):
        build_suite(
            GraphOutcomeSuitePayload(
                source_revision=_REVISION,
                protocol_schema_version="graph-outcome-protocol.v1",
                projections=projections[:-1],
            )
        )
    with pytest.raises(ValueError):
        build_suite(
            GraphOutcomeSuitePayload(
                source_revision=_REVISION,
                protocol_schema_version="graph-outcome-protocol.v1",
                projections=(*projections[:-1], projections[0]),
            )
        )
    unsupported = projections[0].model_copy(
        update={"scenario": cast(ProjectionScenario, "unsupported-scenario")}
    )
    with pytest.raises(ValueError):
        build_suite(
            GraphOutcomeSuitePayload.model_construct(
                source_revision=_REVISION,
                protocol_schema_version="graph-outcome-protocol.v1",
                projections=(unsupported, *projections[1:]),
            )
        )
    with pytest.raises(ValueError):
        build_suite(
            GraphOutcomeSuitePayload.model_construct(
                source_revision=_REVISION,
                protocol_schema_version="graph-outcome-protocol.v1",
                projections=(
                    projections[0].model_copy(update={"source_revision": "b" * 40}),
                    *projections[1:],
                ),
            )
        )
    with pytest.raises(ValueError):
        build_suite(
            GraphOutcomeSuitePayload.model_construct(
                source_revision=_REVISION,
                protocol_schema_version="graph-outcome-protocol.v1",
                projections=(
                    projections[0].model_copy(update={"protocol_schema_version": "unsupported"}),
                    *projections[1:],
                ),
            )
        )


@pytest.mark.parametrize("field", ("schema_version", "protocol_schema_version"))
def test_suite_payload_rejects_unsupported_schema_versions(field: str) -> None:
    with pytest.raises(ValueError):
        GraphOutcomeSuitePayload.model_validate(
            {
                **GraphOutcomeSuitePayload(
                    source_revision=_REVISION,
                    protocol_schema_version="graph-outcome-protocol.v1",
                    projections=_four_projections(),
                ).model_dump(),
                field: "unsupported",
            }
        )
