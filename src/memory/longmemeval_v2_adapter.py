"""Local-only LongMemEval-V2 input and provenance evidence adapter.

This module intentionally accepts only caller-supplied JSONL files. It does
not claim to implement the benchmark, download upstream data, resolve media,
invoke models, read vaults, or write results. The selected records are the
smallest typed envelope needed to preserve question, haystack, and linkage.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .evidence_models import EvidenceContractError

_MAX_RECORDS = 100_000
_MAX_RECORD_BYTES = 1_048_576
_MAX_TURNS = 10_000
_MAX_LINKS = 10_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HF_REVISION = re.compile(r"^[0-9a-f]{40}$")
_LICENSE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]{0,127}$")


class _DuplicateJsonKeyError(ValueError):
    """Raised when JSON would otherwise silently overwrite a member."""


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LongMemEvalV2Turn(_ClosedModel):
    """One selected trajectory turn; ordering is source-defined."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=65_536)


class LongMemEvalV2Question(_ClosedModel):
    """Minimal selected question record from a caller-provided JSONL file."""

    question_id: str = Field(min_length=1, max_length=512)
    question: str = Field(min_length=1, max_length=65_536)


class LongMemEvalV2Trajectory(_ClosedModel):
    """Minimal selected haystack trajectory from a caller-provided JSONL file."""

    trajectory_id: str = Field(min_length=1, max_length=512)
    turns: tuple[LongMemEvalV2Turn, ...] = Field(min_length=1, max_length=_MAX_TURNS)


class LongMemEvalV2QuestionHaystack(_ClosedModel):
    """One ordered question-to-haystack mapping record."""

    question_id: str = Field(min_length=1, max_length=512)
    trajectory_ids: tuple[str, ...] = Field(min_length=1, max_length=_MAX_LINKS)


class LongMemEvalV2Provenance(_ClosedModel):
    """Content-safe provenance and explicit non-score evidence classification."""

    dataset_license_id: str = Field(pattern=_LICENSE_ID.pattern)
    huggingface_revision: str = Field(pattern=_HF_REVISION.pattern)
    question_input_digest: str = Field(pattern=_SHA256.pattern)
    trajectory_input_digest: str = Field(pattern=_SHA256.pattern)
    mapping_input_digest: str = Field(pattern=_SHA256.pattern)
    source_envelope_digest: str = Field(pattern=_SHA256.pattern)
    evidence_kind: Literal["input_provenance_only"]


class LongMemEvalV2InputEvidence(_ClosedModel):
    """Immutable local input evidence, never a benchmark score report."""

    provenance: LongMemEvalV2Provenance
    questions: tuple[LongMemEvalV2Question, ...] = Field(min_length=1)
    trajectories: tuple[LongMemEvalV2Trajectory, ...] = Field(min_length=1)
    mappings: tuple[LongMemEvalV2QuestionHaystack, ...] = Field(min_length=1)


def load_longmemeval_v2_input(
    question_path: Path,
    trajectory_path: Path,
    mapping_path: Path,
    *,
    dataset_license_id: str,
    huggingface_revision: str,
) -> LongMemEvalV2InputEvidence:
    """Load local V2 inputs and return input/provenance evidence only."""
    license_id = _required_provenance(dataset_license_id, _LICENSE_ID, "license")
    revision = _required_provenance(huggingface_revision, _HF_REVISION, "revision")
    question_bytes = _read_input(question_path, "questions")
    trajectory_bytes = _read_input(trajectory_path, "trajectories")
    mapping_bytes = _read_input(mapping_path, "mapping")
    questions = _load_records(question_bytes, LongMemEvalV2Question, "question")
    trajectories = _load_records(trajectory_bytes, LongMemEvalV2Trajectory, "trajectory")
    mappings = _load_records(mapping_bytes, LongMemEvalV2QuestionHaystack, "mapping")
    _reject_duplicate_ids(questions, "question_id", "question")
    _reject_duplicate_ids(trajectories, "trajectory_id", "trajectory")
    _reject_duplicate_ids(mappings, "question_id", "mapping")
    _reject_duplicate_mapping_links(mappings)
    question_ids = {item.question_id for item in questions}
    trajectory_ids = {item.trajectory_id for item in trajectories}
    if {item.question_id for item in mappings} != question_ids:
        raise EvidenceContractError("longmemeval_v2_question_mapping_incomplete")
    if any(
        trajectory_id not in trajectory_ids
        for item in mappings
        for trajectory_id in item.trajectory_ids
    ):
        raise EvidenceContractError("longmemeval_v2_trajectory_cross_reference_missing")
    digests = {
        "dataset_license_id": license_id,
        "huggingface_revision": revision,
        "question_input_digest": hashlib.sha256(question_bytes).hexdigest(),
        "trajectory_input_digest": hashlib.sha256(trajectory_bytes).hexdigest(),
        "mapping_input_digest": hashlib.sha256(mapping_bytes).hexdigest(),
    }
    envelope = json.dumps(digests, sort_keys=True, separators=(",", ":")).encode("utf-8")
    provenance = LongMemEvalV2Provenance(
        **digests,
        source_envelope_digest=hashlib.sha256(envelope).hexdigest(),
        evidence_kind="input_provenance_only",
    )
    return LongMemEvalV2InputEvidence(
        provenance=provenance,
        questions=tuple(questions),
        trajectories=tuple(trajectories),
        mappings=tuple(mappings),
    )


def _read_input(path: Path, label: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceContractError(f"longmemeval_v2_{label}_unreadable") from exc
    if not raw.strip():
        raise EvidenceContractError(f"longmemeval_v2_{label}_empty")
    return raw


def _load_records(raw: bytes, model: type[BaseModel], label: str) -> list[Any]:
    lines = raw.splitlines()
    if not lines or len(lines) > _MAX_RECORDS:
        raise EvidenceContractError(f"longmemeval_v2_{label}_records_invalid")
    records: list[Any] = []
    for line in lines:
        if len(line) > _MAX_RECORD_BYTES or not line.strip():
            raise EvidenceContractError(f"longmemeval_v2_{label}_record_invalid")
        try:
            value: Any = json.loads(
                line,
                object_pairs_hook=_no_duplicate_json_keys,
                parse_constant=_reject_non_finite,
            )
            if not isinstance(value, Mapping):
                raise ValueError("record must be an object")
            records.append(model.model_validate(value))
        except (
            _DuplicateJsonKeyError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            ValidationError,
        ) as exc:
            raise EvidenceContractError(f"longmemeval_v2_{label}_record_invalid") from exc
    return records


def _reject_duplicate_ids(records: list[Any], field: str, label: str) -> None:
    values = [getattr(record, field) for record in records]
    if len(values) != len(set(values)):
        raise EvidenceContractError(f"longmemeval_v2_{label}_id_duplicate")


def _reject_duplicate_mapping_links(mappings: list[Any]) -> None:
    if any(len(item.trajectory_ids) != len(set(item.trajectory_ids)) for item in mappings):
        raise EvidenceContractError("longmemeval_v2_mapping_trajectory_id_duplicate")


def _required_provenance(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise EvidenceContractError(f"longmemeval_v2_{label}_invalid")
    return value


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"unsupported JSON constant: {value}")


__all__ = [
    "LongMemEvalV2InputEvidence",
    "LongMemEvalV2Provenance",
    "LongMemEvalV2Question",
    "LongMemEvalV2QuestionHaystack",
    "LongMemEvalV2Trajectory",
    "LongMemEvalV2Turn",
    "load_longmemeval_v2_input",
]
