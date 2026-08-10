"""Closed, content-free contracts for reproducible benchmark evidence.

The contracts deliberately validate run provenance and opaque result artifacts;
they do not download suites, invoke models, or retain prompts, answers, vault
content, credentials, paths, or raw outputs.  A comparison is admissible only
when its runs share the same evaluation context and contain the prespecified
Matryca controls plus two reproducible external open-system controls.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence_models import EvidenceContractError

BENCHMARK_PROTOCOL_SCHEMA_VERSION = "benchmark-protocol.v1"
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

SuiteName = Literal["beam", "locomo", "longmemeval", "longmemeval-v2", "memoryagentbench"]
EvidenceClass = Literal[
    "independently_reproduced",
    "not_comparable",
    "synthetic_design_evidence",
    "upstream_reported_not_rerun",
]
EvaluationLayer = Literal["end_to_end_answer", "retrieval"]
SystemRole = Literal[
    "external_open_system",
    "matryca_candidate_feature",
    "matryca_without_semantic_memory",
]
RunStatus = Literal["completed", "excluded", "failed"]
ArtifactKind = Literal["exclusions", "failed_runs", "item_results", "run_metadata"]


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


class DatasetPin(_ClosedModel):
    """One legally attributable public-suite revision without local content."""

    suite: SuiteName
    dataset_id: str
    repository_slug: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    dataset_revision: str
    license_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")

    @model_validator(mode="after")
    def _validate_identifiers(self) -> DatasetPin:
        object.__setattr__(self, "dataset_id", _identifier(self.dataset_id, field="dataset_id"))
        object.__setattr__(
            self,
            "dataset_revision",
            _git_revision(self.dataset_revision, field="dataset_revision"),
        )
        return self


class ModelPin(_ClosedModel):
    """Pinned evaluator model or the explicit provider-free sentinel."""

    model_id: str
    model_revision: str
    prompt_digest: str
    temperature_milli: int = Field(ge=0, le=2_000)
    seed: int = Field(ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def _validate_pins(self) -> ModelPin:
        object.__setattr__(self, "model_id", _identifier(self.model_id, field="model_id"))
        object.__setattr__(
            self,
            "model_revision",
            _identifier(self.model_revision, field="model_revision"),
        )
        object.__setattr__(
            self,
            "prompt_digest",
            _sha256(self.prompt_digest, field="prompt_digest"),
        )
        return self


class EvaluationBudget(_ClosedModel):
    """Comparable retrieval and context limits for every system in a cohort."""

    context_token_budget: int = Field(ge=1, le=10_000_000)
    retrieval_call_budget: int = Field(ge=0, le=10_000)
    top_k: int = Field(ge=1, le=1_000)
    timeout_seconds: int = Field(ge=1, le=86_400)


class RuntimePin(_ClosedModel):
    """Content-free hardware and dependency provenance for one run."""

    harness_revision: str
    matryca_revision: str
    dependency_lock_digest: str
    hardware_class: str
    os_family: str
    runtime_version: str
    concurrency: int = Field(ge=1, le=10_000)
    cache_state: Literal["cold", "primed", "warm"]
    failure_policy_id: str
    retry_policy_id: str

    @model_validator(mode="after")
    def _validate_pins(self) -> RuntimePin:
        object.__setattr__(
            self,
            "harness_revision",
            _git_revision(self.harness_revision, field="harness_revision"),
        )
        object.__setattr__(
            self,
            "matryca_revision",
            _git_revision(self.matryca_revision, field="matryca_revision"),
        )
        object.__setattr__(
            self,
            "dependency_lock_digest",
            _sha256(self.dependency_lock_digest, field="dependency_lock_digest"),
        )
        object.__setattr__(
            self,
            "hardware_class",
            _identifier(self.hardware_class, field="hardware_class"),
        )
        object.__setattr__(self, "os_family", _identifier(self.os_family, field="os_family"))
        object.__setattr__(
            self,
            "runtime_version",
            _identifier(self.runtime_version, field="runtime_version"),
        )
        object.__setattr__(
            self,
            "failure_policy_id",
            _identifier(self.failure_policy_id, field="failure_policy_id"),
        )
        object.__setattr__(
            self,
            "retry_policy_id",
            _identifier(self.retry_policy_id, field="retry_policy_id"),
        )
        return self


class SystemPin(_ClosedModel):
    """A reproducible system/control identity without configuration content."""

    role: SystemRole
    system_id: str
    implementation_revision: str
    configuration_digest: str
    open_source: bool

    @model_validator(mode="after")
    def _validate_system(self) -> SystemPin:
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
        if self.role == "external_open_system" and not self.open_source:
            raise EvidenceContractError("external_system_must_be_open_source")
        if self.role != "external_open_system" and self.system_id != "matryca-plumber":
            raise EvidenceContractError("matryca_control_must_use_matryca_id")
        return self


class OpaqueArtifact(_ClosedModel):
    """Digest-pinned, retained result material stored outside the contract."""

    kind: ArtifactKind
    digest: str
    record_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_digest(self) -> OpaqueArtifact:
        object.__setattr__(self, "digest", _sha256(self.digest, field=f"{self.kind}_digest"))
        return self


class BenchmarkRunManifest(_ClosedModel):
    """Closed run manifest for one evaluation layer and one tested system."""

    schema_version: str = BENCHMARK_PROTOCOL_SCHEMA_VERSION
    cohort_id: str
    dataset: DatasetPin
    evaluation_layer: EvaluationLayer
    system: SystemPin
    answer_model: ModelPin | None
    judge_model: ModelPin | None
    budget: EvaluationBudget
    runtime: RuntimePin
    evidence_class: EvidenceClass

    @model_validator(mode="after")
    def _validate_manifest(self) -> BenchmarkRunManifest:
        if self.schema_version != BENCHMARK_PROTOCOL_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_benchmark_protocol_schema")
        object.__setattr__(self, "cohort_id", _identifier(self.cohort_id, field="cohort_id"))
        if self.evaluation_layer == "retrieval":
            if self.answer_model is not None or self.judge_model is not None:
                raise EvidenceContractError("retrieval_run_cannot_pin_answer_or_judge")
        elif self.answer_model is None or self.judge_model is None:
            raise EvidenceContractError("end_to_end_run_requires_answer_and_judge")
        return self

    @property
    def manifest_id(self) -> str:
        return hashlib.sha256(canonical_manifest_bytes(self)).hexdigest()


class BenchmarkRunReport(_ClosedModel):
    """Run outcome that retains all result categories as opaque artifacts."""

    manifest: BenchmarkRunManifest
    status: RunStatus
    artifacts: tuple[OpaqueArtifact, ...]

    @model_validator(mode="after")
    def _validate_report(self) -> BenchmarkRunReport:
        artifacts = tuple(self.artifacts)
        expected = {"exclusions", "failed_runs", "item_results", "run_metadata"}
        if {artifact.kind for artifact in artifacts} != expected or len(artifacts) != len(expected):
            raise EvidenceContractError("incomplete_or_duplicate_run_artifacts")
        object.__setattr__(self, "artifacts", tuple(sorted(artifacts, key=lambda item: item.kind)))
        if self.status == "completed" and any(
            artifact.record_count > 0 for artifact in artifacts if artifact.kind == "failed_runs"
        ):
            raise EvidenceContractError("completed_run_cannot_have_failed_items")
        return self

    @property
    def report_id(self) -> str:
        return hashlib.sha256(canonical_report_bytes(self)).hexdigest()


def canonical_manifest_bytes(manifest: BenchmarkRunManifest) -> bytes:
    """Serialize a manifest deterministically without raw benchmark content."""
    return json.dumps(
        manifest.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_report_bytes(report: BenchmarkRunReport) -> bytes:
    """Serialize a retained-artifact report deterministically."""
    return json.dumps(
        report.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def validate_comparative_cohort(reports: tuple[BenchmarkRunReport, ...]) -> str:
    """Return a cohort fingerprint only for a like-for-like four-system baseline.

    The validator does not score systems.  It proves only that a resulting
    comparison has the required controls and compatible measurement context.
    """
    if len(reports) != 4:
        raise EvidenceContractError("comparative_cohort_requires_exactly_four_runs")
    manifests = tuple(report.manifest for report in reports)
    if any(manifest.evidence_class != "independently_reproduced" for manifest in manifests):
        raise EvidenceContractError("comparative_cohort_requires_reproduced_evidence")
    if any(report.status != "completed" for report in reports):
        raise EvidenceContractError("comparative_cohort_requires_completed_runs")
    if len({manifest.cohort_id for manifest in manifests}) != 1:
        raise EvidenceContractError("comparative_cohort_id_mismatch")
    if len({manifest.evaluation_layer for manifest in manifests}) != 1:
        raise EvidenceContractError("comparative_cohort_mixes_evaluation_layers")
    reference = manifests[0]
    comparison_key = (
        reference.dataset,
        reference.answer_model,
        reference.judge_model,
        reference.budget,
        reference.runtime,
    )
    if any(
        (
            manifest.dataset,
            manifest.answer_model,
            manifest.judge_model,
            manifest.budget,
            manifest.runtime,
        )
        != comparison_key
        for manifest in manifests[1:]
    ):
        raise EvidenceContractError("comparative_cohort_context_mismatch")
    roles = [manifest.system.role for manifest in manifests]
    if roles.count("matryca_without_semantic_memory") != 1:
        raise EvidenceContractError("missing_matryca_no_memory_control")
    if roles.count("matryca_candidate_feature") != 1:
        raise EvidenceContractError("missing_matryca_candidate_control")
    external_ids = {
        manifest.system.system_id
        for manifest in manifests
        if manifest.system.role == "external_open_system"
    }
    if len(external_ids) < 2:
        raise EvidenceContractError("comparative_cohort_requires_two_external_systems")
    return hashlib.sha256(
        json.dumps(
            {
                "manifest_ids": sorted(manifest.manifest_id for manifest in manifests),
                "report_ids": sorted(report.report_id for report in reports),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "ArtifactKind",
    "BENCHMARK_PROTOCOL_SCHEMA_VERSION",
    "BenchmarkRunManifest",
    "BenchmarkRunReport",
    "DatasetPin",
    "EvaluationBudget",
    "EvaluationLayer",
    "EvidenceClass",
    "ModelPin",
    "OpaqueArtifact",
    "RunStatus",
    "RuntimePin",
    "SuiteName",
    "SystemPin",
    "SystemRole",
    "canonical_manifest_bytes",
    "canonical_report_bytes",
    "validate_comparative_cohort",
]
