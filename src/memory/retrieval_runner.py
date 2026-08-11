"""Local-only retrieval execution bridge for benchmark evidence.

The runner accepts already-loaded evidence or synthetic fixtures.  It never
loads a suite, calls a provider, reads a vault, infers an answer, or selects a
retrieval implementation.  A caller must explicitly choose the empty
no-memory retriever or provide a typed candidate seam.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .benchmark_protocol import (
    ArtifactKind,
    BenchmarkRunManifest,
    BenchmarkRunReport,
    OpaqueArtifact,
    SystemPin,
)
from .evidence_models import EvidenceContractError

RETRIEVAL_RUNNER_SCHEMA_VERSION = "retrieval-runner.v1"
_ARTIFACT_FILES: dict[ArtifactKind, str] = {
    "exclusions": "exclusions.jsonl",
    "failed_runs": "failed_runs.jsonl",
    "item_results": "item_results.jsonl",
    "run_metadata": "run_metadata.jsonl",
}


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetrievalItem(_ClosedModel):
    """One caller-supplied query and its opaque relevance references."""

    item_id: str = Field(min_length=1, max_length=512)
    query: str = Field(min_length=1, max_length=65_536)
    relevant_ids: tuple[str, ...] = ()
    excluded_reason: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _validate_ids(self) -> RetrievalItem:
        if len(set(self.relevant_ids)) != len(self.relevant_ids):
            raise EvidenceContractError("duplicate_relevant_id")
        if self.excluded_reason is not None and self.relevant_ids:
            raise EvidenceContractError("excluded_item_cannot_have_relevance")
        return self


class RetrievalInputEvidence(_ClosedModel):
    """Immutable, caller-supplied input evidence; not a result or a loader."""

    input_provenance_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[RetrievalItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_items(self) -> RetrievalInputEvidence:
        ids = [item.item_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise EvidenceContractError("duplicate_retrieval_item_id")
        return self


class RetrievedCandidate(_ClosedModel):
    """One opaque candidate returned by an explicitly configured seam."""

    candidate_id: str = Field(min_length=1, max_length=512)
    rank: int = Field(ge=1)


class ItemResult(_ClosedModel):
    item_id: str
    retrieved_ids: tuple[str, ...]
    relevant_ids: tuple[str, ...]
    hit_count: int = Field(ge=0)


class ExclusionRecord(_ClosedModel):
    item_id: str
    reason: str


class FailureRecord(_ClosedModel):
    item_id: str
    classification: Literal["timeout", "retrieval_failure"]


class RetrievalCandidateSeam(Protocol):
    """Explicit provider-neutral seam; callers own the implementation."""

    system: SystemPin

    def retrieve(self, item: RetrievalItem, *, top_k: int) -> Sequence[RetrievedCandidate]: ...


class NoMemoryRetriever:
    """Explicit empty-context baseline; it never inspects or retrieves input."""

    def __init__(self, *, system: SystemPin) -> None:
        self.system = system

    def retrieve(self, item: RetrievalItem, *, top_k: int) -> tuple[RetrievedCandidate, ...]:
        del item, top_k
        return ()


def run_retrieval(
    manifest: BenchmarkRunManifest,
    evidence: RetrievalInputEvidence,
    *,
    run_root: Path,
    retriever: RetrievalCandidateSeam,
) -> BenchmarkRunReport:
    """Replay caller-supplied evidence into a digest-bound retrieval report."""
    if manifest.evaluation_layer != "retrieval":
        raise EvidenceContractError("retrieval_runner_requires_retrieval_manifest")
    if evidence.input_provenance_digest != manifest.input_provenance_digest:
        raise EvidenceContractError("input_provenance_digest_mismatch")
    root = _validated_run_root(run_root)
    if not callable(getattr(retriever, "retrieve", None)):
        raise EvidenceContractError("invalid_retrieval_candidate_seam")
    if getattr(retriever, "system", None) != manifest.system:
        raise EvidenceContractError("retrieval_seam_system_mismatch")

    results: list[ItemResult] = []
    exclusions: list[ExclusionRecord] = []
    failures: list[FailureRecord] = []
    for item in sorted(evidence.items, key=lambda value: value.item_id):
        if item.excluded_reason is not None:
            exclusions.append(ExclusionRecord(item_id=item.item_id, reason=item.excluded_reason))
            continue
        try:
            candidates = retriever.retrieve(item, top_k=manifest.budget.top_k)
        except TimeoutError:
            failures.append(FailureRecord(item_id=item.item_id, classification="timeout"))
            continue
        except EvidenceContractError:
            raise
        except Exception:
            failures.append(FailureRecord(item_id=item.item_id, classification="retrieval_failure"))
            continue
        _validate_result_order(candidates, top_k=manifest.budget.top_k)
        retrieved_ids = tuple(candidate.candidate_id for candidate in candidates)
        results.append(
            ItemResult(
                item_id=item.item_id,
                retrieved_ids=retrieved_ids,
                relevant_ids=tuple(sorted(item.relevant_ids)),
                hit_count=len(set(retrieved_ids) & set(item.relevant_ids)),
            )
        )

    status: Literal["completed", "failed"] = "failed" if failures else "completed"
    metadata = {
        "artifact_schema_version": RETRIEVAL_RUNNER_SCHEMA_VERSION,
        "evidence_item_count": len(evidence.items),
        "input_provenance_digest": evidence.input_provenance_digest,
        "manifest_id": manifest.manifest_id,
        "retrieval_mode": "no_memory_empty_context"
        if isinstance(retriever, NoMemoryRetriever)
        else "explicit_candidate_seam",
        "status": status,
    }
    payloads = {
        "exclusions": _lines(exclusions),
        "failed_runs": _lines(failures),
        "item_results": _lines(results),
        "run_metadata": _lines((metadata,)),
    }
    artifacts = tuple(
        OpaqueArtifact(
            kind=kind,
            digest=_write_artifact(root, filename, payloads[kind]),
            record_count=_record_count(payloads[kind]),
        )
        for kind, filename in _ARTIFACT_FILES.items()
    )
    return BenchmarkRunReport(manifest=manifest, status=status, artifacts=artifacts)


def _validate_result_order(candidates: Sequence[RetrievedCandidate], *, top_k: int) -> None:
    if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence):
        raise EvidenceContractError("retrieval_result_not_sequence")
    if any(not isinstance(candidate, RetrievedCandidate) for candidate in candidates):
        raise EvidenceContractError("invalid_retrieval_candidate")
    if len(candidates) > top_k:
        raise EvidenceContractError("retrieval_result_exceeds_top_k")
    ranks = tuple(candidate.rank for candidate in candidates)
    if ranks != tuple(range(1, len(candidates) + 1)):
        raise EvidenceContractError("invalid_result_ordering")
    ids = tuple(candidate.candidate_id for candidate in candidates)
    if len(set(ids)) != len(ids):
        raise EvidenceContractError("duplicate_retrieval_candidate")


def _validated_run_root(run_root: Path) -> Path:
    if not isinstance(run_root, Path) or not run_root.is_dir() or run_root.is_symlink():
        raise EvidenceContractError("invalid_supplied_run_root")
    root = run_root.resolve()
    if not root.is_dir():
        raise EvidenceContractError("invalid_supplied_run_root")
    return root


def _lines(records: Iterable[object]) -> bytes:
    values = [
        record.model_dump(mode="json") if isinstance(record, BaseModel) else record
        for record in records
    ]
    return b"".join(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
        for value in values
    )


def _record_count(payload: bytes) -> int:
    return payload.count(b"\n")


def _write_artifact(root: Path, filename: str, payload: bytes) -> str:
    path = root / filename
    if path.is_symlink() or path.resolve().parent != root:
        raise EvidenceContractError("artifact_path_outside_run_root")
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "ExclusionRecord",
    "FailureRecord",
    "ItemResult",
    "NoMemoryRetriever",
    "RetrievedCandidate",
    "RetrievalCandidateSeam",
    "RetrievalInputEvidence",
    "RetrievalItem",
    "run_retrieval",
]
