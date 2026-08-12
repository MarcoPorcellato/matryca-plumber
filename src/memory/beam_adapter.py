"""Local-only BEAM input and provenance adapter.

This boundary accepts one already acquired ``chat.json`` and its colocated
``probing_questions.json``.  It never downloads BEAM, invokes a model, reads a
vault, scores answers, or persists results.  The caller supplies the stable
chat identifier because BEAM encodes it in the directory layout, not the JSON.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .benchmark_protocol import DatasetPin
from .evidence_models import EvidenceContractError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_BATCHES = 10_000
_MAX_TURNS = 100_000
_MAX_QUESTIONS = 100_000
_MAX_BYTES = 64 * 1024 * 1024


class _DuplicateJsonKeyError(ValueError):
    """Raised when JSON would otherwise silently overwrite a member."""


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BeamTurn(_ClosedModel):
    """One source-ordered BEAM conversation turn."""

    role: Literal["user", "assistant"]
    turn_id: str = Field(min_length=1, max_length=512)
    content: str = Field(min_length=1, max_length=65_536)


class BeamConversation(_ClosedModel):
    """One caller-named BEAM chat, retaining source order only."""

    chat_id: str = Field(min_length=1, max_length=512)
    turns: tuple[BeamTurn, ...] = Field(min_length=1, max_length=_MAX_TURNS)


class BeamQuestion(_ClosedModel):
    """One retrieval question linked to its colocated chat by ``chat_id``."""

    question_id: str = Field(min_length=1, max_length=1_024)
    chat_id: str = Field(min_length=1, max_length=512)
    category: str = Field(min_length=1, max_length=512)
    question: str = Field(min_length=1, max_length=65_536)


class BeamProvenance(_ClosedModel):
    """Exact public-source and raw-byte binding for one BEAM local bundle."""

    dataset: DatasetPin
    chat_input_digest: str = Field(pattern=_SHA256.pattern)
    questions_input_digest: str = Field(pattern=_SHA256.pattern)
    source_envelope_digest: str = Field(pattern=_SHA256.pattern)
    evidence_kind: Literal["local_input_provenance_only"]


class BeamInputEvidence(_ClosedModel):
    """Immutable local BEAM input evidence, never a benchmark result."""

    provenance: BeamProvenance
    conversation: BeamConversation
    questions: tuple[BeamQuestion, ...] = Field(min_length=1, max_length=_MAX_QUESTIONS)


def load_beam_input(
    chat_path: Path,
    questions_path: Path,
    *,
    chat_id: str,
    dataset: DatasetPin,
) -> BeamInputEvidence:
    """Load one local BEAM chat/question bundle with fail-closed provenance."""
    if dataset.suite != "beam":
        raise EvidenceContractError("beam_dataset_suite_mismatch")
    chat_id = _required_text(chat_id, "beam_chat_id_invalid")
    chat_bytes = _read_input(chat_path, "chat")
    questions_bytes = _read_input(questions_path, "questions")
    batches = _load_json(chat_bytes, "chat")
    questions_by_category = _load_json(questions_bytes, "questions")
    turns = _parse_turns(batches)
    questions = _parse_questions(questions_by_category, chat_id)
    envelope = json.dumps(
        {
            "chat_id": chat_id,
            "dataset": dataset.model_dump(mode="json"),
            "chat_input_digest": hashlib.sha256(chat_bytes).hexdigest(),
            "questions_input_digest": hashlib.sha256(questions_bytes).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    provenance = BeamProvenance(
        dataset=dataset,
        chat_input_digest=hashlib.sha256(chat_bytes).hexdigest(),
        questions_input_digest=hashlib.sha256(questions_bytes).hexdigest(),
        source_envelope_digest=hashlib.sha256(envelope).hexdigest(),
        evidence_kind="local_input_provenance_only",
    )
    return BeamInputEvidence(
        provenance=provenance,
        conversation=BeamConversation(chat_id=chat_id, turns=tuple(turns)),
        questions=tuple(questions),
    )


def _read_input(path: Path, label: str) -> bytes:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceContractError(f"beam_{label}_unreadable") from exc
    if not raw.strip() or len(raw) > _MAX_BYTES:
        raise EvidenceContractError(f"beam_{label}_invalid")
    return raw


def _load_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_no_duplicate_json_keys,
            parse_constant=_reject_non_finite,
        )
    except (
        _DuplicateJsonKeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise EvidenceContractError(f"beam_{label}_invalid") from exc


def _parse_turns(value: Any) -> list[BeamTurn]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise EvidenceContractError("beam_chat_invalid")
    if len(value) > _MAX_BATCHES:
        raise EvidenceContractError("beam_chat_invalid")
    turns: list[BeamTurn] = []
    turn_ids: set[str] = set()
    for batch in value:
        if not isinstance(batch, Mapping) or set(batch) != {"batch_number", "turns"}:
            raise EvidenceContractError("beam_chat_invalid")
        source_turns = batch["turns"]
        if not isinstance(source_turns, Sequence) or isinstance(source_turns, (str, bytes)):
            raise EvidenceContractError("beam_chat_invalid")
        for source_turn in source_turns:
            if not isinstance(source_turn, Mapping):
                raise EvidenceContractError("beam_chat_invalid")
            try:
                turn = BeamTurn(
                    role=source_turn["role"],
                    turn_id=_required_text(source_turn["id"], "beam_turn_id_invalid"),
                    content=_required_text(source_turn["content"], "beam_turn_content_invalid"),
                )
            except (KeyError, ValidationError, EvidenceContractError) as exc:
                raise EvidenceContractError("beam_chat_invalid") from exc
            if turn.turn_id in turn_ids:
                raise EvidenceContractError("beam_turn_id_duplicate")
            turn_ids.add(turn.turn_id)
            turns.append(turn)
            if len(turns) > _MAX_TURNS:
                raise EvidenceContractError("beam_chat_invalid")
    if not turns:
        raise EvidenceContractError("beam_chat_invalid")
    return turns


def _parse_questions(value: Any, chat_id: str) -> list[BeamQuestion]:
    if not isinstance(value, Mapping) or not value:
        raise EvidenceContractError("beam_questions_invalid")
    questions: list[BeamQuestion] = []
    for category, entries in value.items():
        category = _required_text(category, "beam_question_category_invalid")
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)) or not entries:
            raise EvidenceContractError("beam_questions_invalid")
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, Mapping):
                raise EvidenceContractError("beam_questions_invalid")
            try:
                question = _required_text(entry["question"], "beam_question_invalid")
            except (KeyError, EvidenceContractError) as exc:
                raise EvidenceContractError("beam_questions_invalid") from exc
            questions.append(
                BeamQuestion(
                    question_id=f"{chat_id}:{category}:{index}",
                    chat_id=chat_id,
                    category=category,
                    question=question,
                )
            )
            if len(questions) > _MAX_QUESTIONS:
                raise EvidenceContractError("beam_questions_invalid")
    if not questions:
        raise EvidenceContractError("beam_questions_invalid")
    return questions


def _required_text(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceContractError(error)
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
    "BeamConversation",
    "BeamInputEvidence",
    "BeamProvenance",
    "BeamQuestion",
    "BeamTurn",
    "load_beam_input",
]
