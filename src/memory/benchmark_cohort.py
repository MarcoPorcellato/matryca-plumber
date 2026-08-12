"""Provider-free assembly of privacy-safe comparative benchmark receipts.

This module never executes a benchmark.  It turns already completed, closed
``BenchmarkRunReport`` values into a deterministic receipt only after checking
that every opaque artifact has a matching, content-free retention attestation.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .benchmark_protocol import (
    ArtifactKind,
    BenchmarkRunReport,
    DatasetPin,
    validate_comparative_cohort,
)
from .evidence_models import EvidenceContractError

COHORT_RECEIPT_SCHEMA_VERSION = "benchmark-cohort-receipt.v1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RetentionClass = Literal["public_benchmark_only"]


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _identifier(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _sha256(value: str, *, field: str) -> str:
    normalized = value.strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


class CorpusRetentionAttestation(_ClosedModel):
    """Content-free proof that an exact public corpus revision remains retained."""

    dataset: DatasetPin
    corpus_digest: str
    record_count: int = Field(ge=1)
    retention_policy_id: str
    retention_class: RetentionClass = "public_benchmark_only"

    @model_validator(mode="after")
    def _validate_attestation(self) -> CorpusRetentionAttestation:
        object.__setattr__(
            self,
            "corpus_digest",
            _sha256(self.corpus_digest, field="corpus_digest"),
        )
        object.__setattr__(
            self,
            "retention_policy_id",
            _identifier(self.retention_policy_id, field="retention_policy_id"),
        )
        return self


class RetainedArtifactAttestation(_ClosedModel):
    """Content-free proof that one required run artifact remains retained."""

    report_id: str
    kind: ArtifactKind
    digest: str
    record_count: int = Field(ge=0)
    retention_policy_id: str
    retention_class: RetentionClass = "public_benchmark_only"

    @model_validator(mode="after")
    def _validate_attestation(self) -> RetainedArtifactAttestation:
        object.__setattr__(self, "report_id", _sha256(self.report_id, field="report_id"))
        object.__setattr__(self, "digest", _sha256(self.digest, field=f"{self.kind}_digest"))
        object.__setattr__(
            self,
            "retention_policy_id",
            _identifier(self.retention_policy_id, field="retention_policy_id"),
        )
        return self


class ComparativeCohortReceipt(_ClosedModel):
    """Public, deterministic receipt for a retained like-for-like cohort."""

    schema_version: str = COHORT_RECEIPT_SCHEMA_VERSION
    cohort_id: str
    cohort_fingerprint: str
    corpus: CorpusRetentionAttestation
    retention_policy_id: str
    report_ids: tuple[str, ...]
    artifact_retention_digest: str

    @model_validator(mode="after")
    def _validate_receipt(self) -> ComparativeCohortReceipt:
        if self.schema_version != COHORT_RECEIPT_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_cohort_receipt_schema")
        object.__setattr__(self, "cohort_id", _identifier(self.cohort_id, field="cohort_id"))
        object.__setattr__(
            self,
            "cohort_fingerprint",
            _sha256(self.cohort_fingerprint, field="cohort_fingerprint"),
        )
        object.__setattr__(
            self,
            "retention_policy_id",
            _identifier(self.retention_policy_id, field="retention_policy_id"),
        )
        report_ids = tuple(_sha256(value, field="report_id") for value in self.report_ids)
        if len(report_ids) != 4 or len(set(report_ids)) != len(report_ids):
            raise EvidenceContractError("invalid_cohort_report_ids")
        object.__setattr__(self, "report_ids", tuple(sorted(report_ids)))
        object.__setattr__(
            self,
            "artifact_retention_digest",
            _sha256(self.artifact_retention_digest, field="artifact_retention_digest"),
        )
        if self.corpus.retention_policy_id != self.retention_policy_id:
            raise EvidenceContractError("cohort_retention_policy_mismatch")
        return self

    @property
    def receipt_id(self) -> str:
        return hashlib.sha256(canonical_cohort_receipt_bytes(self)).hexdigest()


def canonical_cohort_receipt_bytes(receipt: ComparativeCohortReceipt) -> bytes:
    """Return the stable content-addressed representation of a public receipt."""

    return json.dumps(
        receipt.model_dump(mode="json"),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def assemble_comparative_cohort_receipt(
    reports: tuple[BenchmarkRunReport, ...],
    corpus: CorpusRetentionAttestation,
    artifacts: tuple[RetainedArtifactAttestation, ...],
) -> ComparativeCohortReceipt:
    """Assemble a receipt after closed control, source, and retention checks.

    No artifact bytes, paths, prompts, answers, credentials, or system calls are
    accepted.  The caller retains raw public benchmark material elsewhere and
    supplies only exact content-free attestations here.
    """

    cohort_fingerprint = validate_comparative_cohort(reports)
    manifests = tuple(report.manifest for report in reports)
    cohort_id = manifests[0].cohort_id
    if corpus.dataset != manifests[0].dataset:
        raise EvidenceContractError("cohort_corpus_dataset_mismatch")

    expected = {
        (report.report_id, artifact.kind): (artifact.digest, artifact.record_count)
        for report in reports
        for artifact in report.artifacts
    }
    if len(expected) != sum(len(report.artifacts) for report in reports):
        raise EvidenceContractError("cohort_report_id_duplicate")
    supplied = {(item.report_id, item.kind): (item.digest, item.record_count) for item in artifacts}
    if len(supplied) != len(artifacts) or set(supplied) != set(expected):
        raise EvidenceContractError("incomplete_or_duplicate_retention_attestations")
    if supplied != expected:
        raise EvidenceContractError("retained_artifact_mismatch")

    policy_ids = {corpus.retention_policy_id, *(item.retention_policy_id for item in artifacts)}
    if len(policy_ids) != 1:
        raise EvidenceContractError("cohort_retention_policy_mismatch")
    retention_payload = [
        {
            "digest": item.digest,
            "kind": item.kind,
            "record_count": item.record_count,
            "report_id": item.report_id,
        }
        for item in sorted(artifacts, key=lambda item: (item.report_id, item.kind))
    ]
    retention_digest = hashlib.sha256(
        json.dumps(
            retention_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ComparativeCohortReceipt(
        cohort_id=cohort_id,
        cohort_fingerprint=cohort_fingerprint,
        corpus=corpus,
        retention_policy_id=corpus.retention_policy_id,
        report_ids=tuple(report.report_id for report in reports),
        artifact_retention_digest=retention_digest,
    )


__all__ = [
    "COHORT_RECEIPT_SCHEMA_VERSION",
    "ComparativeCohortReceipt",
    "CorpusRetentionAttestation",
    "RetainedArtifactAttestation",
    "assemble_comparative_cohort_receipt",
    "canonical_cohort_receipt_bytes",
]
