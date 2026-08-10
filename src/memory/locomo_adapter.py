"""Local-only LoCoMo normalization for retrieval evaluation.

The adapter accepts an already acquired public ``locomo10.json``-shaped file.
It never downloads data, follows image URLs, invokes models, writes results, or
touches a vault.  Public conversation text lives only in the returned in-memory
cases; callers must retain produced outcomes through ``benchmark_protocol``'s
opaque artifact boundary rather than serializing this adapter's values.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .evidence_models import EvidenceContractError

_SESSION_KEY = re.compile(r"^session_(?P<index>[1-9][0-9]*)$")


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LocomoTurn(_ClosedModel):
    """One public LoCoMo dialogue turn retained only for a local evaluation."""

    turn_id: str = Field(min_length=1, max_length=256)
    session_index: int = Field(ge=1)
    speaker: str = Field(min_length=1, max_length=256)
    text: str = Field(min_length=1)


class LocomoRetrievalCase(_ClosedModel):
    """A normalized QA item with its document-level retrieval evidence."""

    case_id: str = Field(min_length=1, max_length=256)
    sample_id: str = Field(min_length=1, max_length=256)
    category: str = Field(min_length=1, max_length=256)
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    turns: tuple[LocomoTurn, ...] = Field(min_length=1)
    evidence_turn_ids: tuple[str, ...]
    evidence_available: bool


class LocomoDataset(_ClosedModel):
    """A deterministic, locally loaded LoCoMo retrieval-evaluation dataset."""

    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: tuple[LocomoRetrievalCase, ...] = Field(min_length=1)


def load_locomo_retrieval_cases(path: Path) -> LocomoDataset:
    """Load documented LoCoMo conversations and QA evidence from one local file.

    Unknown upstream fields, including optional image metadata, are deliberately
    ignored. Required fields are validated fail-closed so malformed data cannot
    silently become a benchmark result.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise EvidenceContractError("locomo_dataset_unreadable") from exc
    try:
        raw: Any = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise EvidenceContractError("locomo_dataset_invalid_json") from exc
    if not isinstance(raw, list) or not raw:
        raise EvidenceContractError("locomo_dataset_must_be_nonempty_list")

    cases: list[LocomoRetrievalCase] = []
    seen_case_ids: set[str] = set()
    for sample_index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise EvidenceContractError("locomo_sample_invalid")
        sample_id = _required_text(item, "sample_id", error="locomo_sample_id_invalid")
        conversation = item.get("conversation")
        if not isinstance(conversation, Mapping):
            raise EvidenceContractError("locomo_conversation_invalid")
        turns = _turns(conversation)
        turn_ids = {turn.turn_id for turn in turns}
        questions = item.get("qa")
        if not isinstance(questions, list) or not questions:
            raise EvidenceContractError("locomo_qa_invalid")
        for question_index, question in enumerate(questions):
            if not isinstance(question, Mapping):
                raise EvidenceContractError("locomo_qa_invalid")
            case_id = f"{sample_id}:{question_index + 1}"
            if case_id in seen_case_ids:
                raise EvidenceContractError("locomo_case_id_duplicate")
            seen_case_ids.add(case_id)
            if "evidence" not in question:
                raise EvidenceContractError("locomo_evidence_invalid")
            evidence_turn_ids = _evidence_ids(question["evidence"], turn_ids)
            cases.append(
                LocomoRetrievalCase(
                    case_id=case_id,
                    sample_id=sample_id,
                    category=_required_scalar_text(
                        question,
                        "category",
                        error="locomo_category_invalid",
                    ),
                    question=_required_text(question, "question", error="locomo_question_invalid"),
                    expected_answer=_answer(question),
                    turns=turns,
                    evidence_turn_ids=evidence_turn_ids,
                    evidence_available=bool(evidence_turn_ids),
                )
            )
        if sample_index >= 10_000:
            raise EvidenceContractError("locomo_dataset_too_many_samples")
    return LocomoDataset(
        source_digest=hashlib.sha256(raw_bytes).hexdigest(),
        cases=tuple(cases),
    )


def _turns(conversation: Mapping[str, Any]) -> tuple[LocomoTurn, ...]:
    sessions: list[tuple[int, Sequence[Any]]] = []
    for key, value in conversation.items():
        match = _SESSION_KEY.fullmatch(key) if isinstance(key, str) else None
        if match is None:
            continue
        if not isinstance(value, list) or not value:
            raise EvidenceContractError("locomo_session_invalid")
        sessions.append((int(match.group("index")), value))
    if not sessions:
        raise EvidenceContractError("locomo_sessions_missing")
    if len({index for index, _turns_value in sessions}) != len(sessions):
        raise EvidenceContractError("locomo_session_duplicate")

    turns: list[LocomoTurn] = []
    turn_ids: set[str] = set()
    for session_index, session_turns in sorted(sessions):
        for turn in session_turns:
            if not isinstance(turn, Mapping):
                raise EvidenceContractError("locomo_turn_invalid")
            raw_turn_id = turn.get("dia_id")
            if isinstance(raw_turn_id, bool) or not isinstance(raw_turn_id, (int, str)):
                raise EvidenceContractError("locomo_turn_id_invalid")
            turn_id = str(raw_turn_id).strip()
            if not turn_id or turn_id in turn_ids:
                raise EvidenceContractError("locomo_turn_id_invalid")
            turn_ids.add(turn_id)
            turns.append(
                LocomoTurn(
                    turn_id=turn_id,
                    session_index=session_index,
                    speaker=_required_text(turn, "speaker", error="locomo_speaker_invalid"),
                    text=_required_text(turn, "text", error="locomo_turn_text_invalid"),
                )
            )
    return tuple(turns)


def _evidence_ids(value: object, turn_ids: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise EvidenceContractError("locomo_evidence_invalid")
    normalized: list[str] = []
    for raw_turn_id in value:
        if isinstance(raw_turn_id, bool) or not isinstance(raw_turn_id, (int, str)):
            raise EvidenceContractError("locomo_evidence_invalid")
        turn_id = str(raw_turn_id).strip()
        if not turn_id or turn_id not in turn_ids or turn_id in normalized:
            raise EvidenceContractError("locomo_evidence_invalid")
        normalized.append(turn_id)
    return tuple(normalized)


def _required_text(value: Mapping[str, Any], key: str, *, error: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise EvidenceContractError(error)
    return raw.strip()


def _required_scalar_text(value: Mapping[str, Any], key: str, *, error: str) -> str:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, str)):
        raise EvidenceContractError(error)
    normalized = str(raw).strip()
    if not normalized:
        raise EvidenceContractError(error)
    return normalized


def _answer(value: Mapping[str, Any]) -> str:
    """Read the standard answer or the documented category-5 adversarial answer."""
    if "answer" in value:
        return _required_scalar_text(value, "answer", error="locomo_answer_invalid")
    return _required_scalar_text(value, "adversarial_answer", error="locomo_answer_invalid")


__all__ = [
    "LocomoDataset",
    "LocomoRetrievalCase",
    "LocomoTurn",
    "load_locomo_retrieval_cases",
]
