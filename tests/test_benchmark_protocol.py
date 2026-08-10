"""Tests for closed, reproducible cross-system benchmark contracts."""

from __future__ import annotations

import pytest
from src.memory.benchmark_protocol import (
    BENCHMARK_PROTOCOL_SCHEMA_VERSION,
    BenchmarkRunManifest,
    BenchmarkRunReport,
    DatasetPin,
    EvaluationBudget,
    EvaluationLayer,
    ModelPin,
    OpaqueArtifact,
    RuntimePin,
    SystemPin,
    SystemRole,
    canonical_manifest_bytes,
    canonical_report_bytes,
    validate_comparative_cohort,
)
from src.memory.evidence_models import EvidenceContractError

_A = "a" * 40
_B = "b" * 40
_C = "c" * 40
_D = "d" * 40
_E = "e" * 40
_F = "f" * 40
_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_DIGEST_D = "d" * 64
_DIGEST_E = "e" * 64


def _runtime() -> RuntimePin:
    return RuntimePin(
        harness_revision=_A,
        matryca_revision=_B,
        dependency_lock_digest=_DIGEST_A,
        hardware_class="apple-m4-max-64gb",
        os_family="macos-15",
        runtime_version="python-3.12",
        concurrency=1,
        cache_state="cold",
        failure_policy_id="retain-all-terminal-outcomes",
        retry_policy_id="no-retry",
    )


def _manifest(
    role: SystemRole,
    system_id: str,
    *,
    layer: EvaluationLayer = "retrieval",
) -> BenchmarkRunManifest:
    return BenchmarkRunManifest(
        schema_version=BENCHMARK_PROTOCOL_SCHEMA_VERSION,
        cohort_id="locomo-retrieval-baseline-v1",
        dataset=DatasetPin(
            suite="locomo",
            dataset_id="locomo-v1",
            repository_slug="snap-research/locomo",
            dataset_revision=_C,
            license_id="CC-BY-4.0",
        ),
        evaluation_layer=layer,
        system=SystemPin(
            role=role,
            system_id=system_id,
            implementation_revision=_D if system_id == "matryca-plumber" else _E,
            configuration_digest=_DIGEST_B,
            open_source=True,
        ),
        answer_model=None,
        judge_model=None,
        budget=EvaluationBudget(
            context_token_budget=8_192,
            retrieval_call_budget=4,
            top_k=8,
            timeout_seconds=60,
        ),
        runtime=_runtime(),
        evidence_class="independently_reproduced",
    )


def _report(role: SystemRole, system_id: str) -> BenchmarkRunReport:
    return BenchmarkRunReport(
        manifest=_manifest(role, system_id),
        status="completed",
        artifacts=(
            OpaqueArtifact(kind="item_results", digest=_DIGEST_A, record_count=24),
            OpaqueArtifact(kind="run_metadata", digest=_DIGEST_B, record_count=1),
            OpaqueArtifact(kind="exclusions", digest=_DIGEST_C, record_count=0),
            OpaqueArtifact(kind="failed_runs", digest=_DIGEST_D, record_count=0),
        ),
    )


def test_manifest_and_report_are_closed_and_byte_stable() -> None:
    report = _report("matryca_without_semantic_memory", "matryca-plumber")

    assert canonical_manifest_bytes(report.manifest) == canonical_manifest_bytes(report.manifest)
    assert canonical_report_bytes(report) == canonical_report_bytes(report)
    assert len(report.manifest.manifest_id) == 64
    assert len(report.report_id) == 64
    with pytest.raises(ValueError):
        BenchmarkRunManifest.model_validate(
            {**report.manifest.model_dump(), "raw_prompt": "unsafe"}
        )


def test_retrieval_and_end_to_end_layers_cannot_be_conflated() -> None:
    retrieval = _manifest("matryca_candidate_feature", "matryca-plumber")

    with pytest.raises(ValueError, match="retrieval_run_cannot_pin_answer_or_judge"):
        BenchmarkRunManifest.model_validate(
            {**retrieval.model_dump(), "answer_model": _model().model_dump()}
        )
    with pytest.raises(ValueError, match="end_to_end_run_requires_answer_and_judge"):
        BenchmarkRunManifest.model_validate(
            {**retrieval.model_dump(), "evaluation_layer": "end_to_end_answer"}
        )


def _model() -> ModelPin:
    return ModelPin(
        model_id="local-judge",
        model_revision="v1",
        prompt_digest=_DIGEST_E,
        temperature_milli=0,
        seed=7,
    )


def test_report_requires_all_retained_result_categories() -> None:
    report = _report("matryca_candidate_feature", "matryca-plumber")

    with pytest.raises(ValueError, match="incomplete_or_duplicate_run_artifacts"):
        BenchmarkRunReport(
            manifest=report.manifest,
            status="completed",
            artifacts=report.artifacts[:-1],
        )
    failed = OpaqueArtifact(kind="failed_runs", digest=_DIGEST_D, record_count=1)
    without_failed = tuple(item for item in report.artifacts if item.kind != "failed_runs")
    with pytest.raises(ValueError, match="completed_run_cannot_have_failed_items"):
        BenchmarkRunReport(
            manifest=report.manifest,
            status="completed",
            artifacts=(*without_failed, failed),
        )


def test_comparative_cohort_requires_matryca_controls_and_two_open_systems() -> None:
    reports = (
        _report("matryca_without_semantic_memory", "matryca-plumber"),
        _report("matryca_candidate_feature", "matryca-plumber"),
        _report("external_open_system", "mem0"),
        _report("external_open_system", "graphiti"),
    )

    assert validate_comparative_cohort(reports) == validate_comparative_cohort(reports)
    duplicated_external = (*reports[:-1], _report("external_open_system", "mem0"))
    with pytest.raises(
        EvidenceContractError,
        match="comparative_cohort_requires_two_external_systems",
    ):
        validate_comparative_cohort(duplicated_external)


def test_comparative_cohort_rejects_context_or_layer_mismatch() -> None:
    reports = list(
        (
            _report("matryca_without_semantic_memory", "matryca-plumber"),
            _report("matryca_candidate_feature", "matryca-plumber"),
            _report("external_open_system", "mem0"),
            _report("external_open_system", "graphiti"),
        )
    )
    reports[-1] = BenchmarkRunReport(
        manifest=BenchmarkRunManifest.model_validate(
            {
                **reports[-1].manifest.model_dump(),
                "budget": {**reports[-1].manifest.budget.model_dump(), "top_k": 9},
            }
        ),
        status=reports[-1].status,
        artifacts=reports[-1].artifacts,
    )

    with pytest.raises(EvidenceContractError, match="comparative_cohort_context_mismatch"):
        validate_comparative_cohort(tuple(reports))

    reports[-1] = BenchmarkRunReport(
        manifest=BenchmarkRunManifest.model_validate(
            {
                **reports[-1].manifest.model_dump(),
                "budget": reports[0].manifest.budget.model_dump(),
                "runtime": {
                    **reports[-1].manifest.runtime.model_dump(),
                    "cache_state": "warm",
                    "retry_policy_id": "one-bounded-retry",
                },
            }
        ),
        status=reports[-1].status,
        artifacts=reports[-1].artifacts,
    )
    with pytest.raises(EvidenceContractError, match="comparative_cohort_context_mismatch"):
        validate_comparative_cohort(tuple(reports))
    with pytest.raises(ValueError, match="external_system_must_be_open_source"):
        SystemPin(
            role="external_open_system",
            system_id="closed-memory",
            implementation_revision=_F,
            configuration_digest=_DIGEST_A,
            open_source=False,
        )
