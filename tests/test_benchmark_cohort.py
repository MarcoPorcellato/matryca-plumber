"""Tests for provider-free comparative cohort receipt assembly."""

from __future__ import annotations

import pytest
from src.memory.benchmark_cohort import (
    ComparativeCohortReceipt,
    CorpusRetentionAttestation,
    RetainedArtifactAttestation,
    assemble_comparative_cohort_receipt,
    canonical_cohort_receipt_bytes,
)
from src.memory.benchmark_protocol import (
    BenchmarkRunManifest,
    BenchmarkRunReport,
    DatasetPin,
    EvaluationBudget,
    OpaqueArtifact,
    RuntimePin,
    SystemPin,
    SystemRole,
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
_CORPUS_DIGEST = "f" * 64


def _dataset() -> DatasetPin:
    return DatasetPin(
        suite="locomo",
        dataset_id="locomo-v1",
        repository_slug="snap-research/locomo",
        dataset_revision=_C,
        license_id="CC-BY-4.0",
    )


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


def _report(role: SystemRole, system_id: str) -> BenchmarkRunReport:
    return BenchmarkRunReport(
        manifest=BenchmarkRunManifest(
            cohort_id="locomo-retrieval-baseline-v1",
            dataset=_dataset(),
            evaluation_layer="retrieval",
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
        ),
        status="completed",
        artifacts=(
            OpaqueArtifact(kind="item_results", digest=_DIGEST_A, record_count=24),
            OpaqueArtifact(kind="run_metadata", digest=_DIGEST_B, record_count=1),
            OpaqueArtifact(kind="exclusions", digest=_DIGEST_C, record_count=0),
            OpaqueArtifact(kind="failed_runs", digest=_DIGEST_D, record_count=0),
        ),
    )


def _reports() -> tuple[BenchmarkRunReport, ...]:
    return (
        _report("matryca_without_semantic_memory", "matryca-plumber"),
        _report("matryca_candidate_feature", "matryca-plumber"),
        _report("external_open_system", "mem0"),
        _report("external_open_system", "graphiti"),
    )


def _corpus() -> CorpusRetentionAttestation:
    return CorpusRetentionAttestation(
        dataset=_dataset(),
        corpus_digest=_CORPUS_DIGEST,
        record_count=250,
        retention_policy_id="public-benchmark-retention-v1",
    )


def _artifacts(reports: tuple[BenchmarkRunReport, ...]) -> tuple[RetainedArtifactAttestation, ...]:
    return tuple(
        RetainedArtifactAttestation(
            report_id=report.report_id,
            kind=artifact.kind,
            digest=artifact.digest,
            record_count=artifact.record_count,
            retention_policy_id="public-benchmark-retention-v1",
        )
        for report in reports
        for artifact in report.artifacts
    )


def test_receipt_is_deterministic_closed_and_content_free() -> None:
    reports = _reports()
    receipt = assemble_comparative_cohort_receipt(reports, _corpus(), _artifacts(reports))
    reordered = assemble_comparative_cohort_receipt(
        tuple(reversed(reports)), _corpus(), tuple(reversed(_artifacts(reports)))
    )

    assert receipt == reordered
    assert receipt.receipt_id == reordered.receipt_id
    assert canonical_cohort_receipt_bytes(receipt) == canonical_cohort_receipt_bytes(reordered)
    assert receipt.report_ids == tuple(sorted(report.report_id for report in reports))
    assert "path" not in canonical_cohort_receipt_bytes(receipt).decode("ascii")
    with pytest.raises(ValueError):
        ComparativeCohortReceipt.model_validate({**receipt.model_dump(), "raw_prompt": "unsafe"})
    with pytest.raises(ValueError, match="invalid_cohort_report_ids"):
        ComparativeCohortReceipt.model_validate(
            {**receipt.model_dump(), "report_ids": [*receipt.report_ids, _DIGEST_D]}
        )


def test_receipt_rejects_missing_duplicate_and_mismatched_attestations() -> None:
    reports = _reports()
    artifacts = _artifacts(reports)

    with pytest.raises(
        EvidenceContractError, match="incomplete_or_duplicate_retention_attestations"
    ):
        assemble_comparative_cohort_receipt(reports, _corpus(), artifacts[:-1])
    with pytest.raises(
        EvidenceContractError, match="incomplete_or_duplicate_retention_attestations"
    ):
        assemble_comparative_cohort_receipt(reports, _corpus(), (*artifacts, artifacts[0]))

    mismatched = RetainedArtifactAttestation(
        report_id=artifacts[0].report_id,
        kind=artifacts[0].kind,
        digest=_CORPUS_DIGEST,
        record_count=artifacts[0].record_count,
        retention_policy_id=artifacts[0].retention_policy_id,
    )
    with pytest.raises(EvidenceContractError, match="retained_artifact_mismatch"):
        assemble_comparative_cohort_receipt(reports, _corpus(), (mismatched, *artifacts[1:]))


def test_receipt_rejects_dataset_and_retention_policy_mismatches() -> None:
    reports = _reports()
    wrong_corpus = CorpusRetentionAttestation(
        dataset=DatasetPin(
            suite="longmemeval",
            dataset_id="longmemeval-v1",
            repository_slug="x/y",
            dataset_revision=_F,
            license_id="MIT",
        ),
        corpus_digest=_CORPUS_DIGEST,
        record_count=250,
        retention_policy_id="public-benchmark-retention-v1",
    )
    with pytest.raises(EvidenceContractError, match="cohort_corpus_dataset_mismatch"):
        assemble_comparative_cohort_receipt(reports, wrong_corpus, _artifacts(reports))

    changed = list(_artifacts(reports))
    changed[-1] = RetainedArtifactAttestation(
        report_id=changed[-1].report_id,
        kind=changed[-1].kind,
        digest=changed[-1].digest,
        record_count=changed[-1].record_count,
        retention_policy_id="another-policy",
    )
    with pytest.raises(EvidenceContractError, match="cohort_retention_policy_mismatch"):
        assemble_comparative_cohort_receipt(reports, _corpus(), tuple(changed))


def test_receipt_preserves_comparative_and_completed_run_gates() -> None:
    reports = _reports()
    incomplete = reports[:-1]

    with pytest.raises(
        EvidenceContractError, match="comparative_cohort_requires_exactly_four_runs"
    ):
        assemble_comparative_cohort_receipt(incomplete, _corpus(), _artifacts(incomplete))

    expanded = (*reports, _report("external_open_system", "zep"))
    with pytest.raises(
        EvidenceContractError, match="comparative_cohort_requires_exactly_four_runs"
    ):
        assemble_comparative_cohort_receipt(expanded, _corpus(), _artifacts(expanded))

    failed = BenchmarkRunReport(
        manifest=reports[-1].manifest,
        status="failed",
        artifacts=reports[-1].artifacts,
    )
    modified = (*reports[:-1], failed)
    with pytest.raises(EvidenceContractError, match="comparative_cohort_requires_completed_runs"):
        assemble_comparative_cohort_receipt(modified, _corpus(), _artifacts(modified))


def test_receipt_rejects_non_reproduced_evidence() -> None:
    reports = list(_reports())
    reports[-1] = BenchmarkRunReport(
        manifest=BenchmarkRunManifest.model_validate(
            {**reports[-1].manifest.model_dump(), "evidence_class": "upstream_reported_not_rerun"}
        ),
        status=reports[-1].status,
        artifacts=reports[-1].artifacts,
    )
    non_reproduced = tuple(reports)

    with pytest.raises(
        EvidenceContractError, match="comparative_cohort_requires_reproduced_evidence"
    ):
        assemble_comparative_cohort_receipt(
            non_reproduced,
            _corpus(),
            _artifacts(non_reproduced),
        )
