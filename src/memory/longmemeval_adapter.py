"""Local-only normalization for acquired LongMemEval cleaned JSON data.

Unknown upstream fields are intentionally ignored for forward compatibility;
the returned Pydantic models remain frozen and closed contracts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .evidence_models import EvidenceContractError

_MAX_CASES = 10_000
_MAX_SESSIONS = 10_000
_MAX_TURNS_PER_SESSION = 10_000


class _DuplicateJsonKeyError(ValueError):
    """Raised when a JSON object would otherwise silently overwrite a key."""


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LongMemEvalTurn(_ClosedModel):
    """One retained public turn from an in-memory evaluation case."""

    turn_id: str = Field(min_length=1, max_length=512)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    has_answer: bool = False


class LongMemEvalSession(_ClosedModel):
    """One haystack session, kept in the exact upstream sequence."""

    session_id: str = Field(min_length=1, max_length=512)
    date: str = Field(min_length=1, max_length=512)
    turns: tuple[LongMemEvalTurn, ...] = Field(min_length=1)


class LongMemEvalRetrievalCase(_ClosedModel):
    """A deterministic LongMemEval question and its separate evidence views."""

    case_id: str = Field(min_length=1, max_length=512)
    question_id: str = Field(min_length=1, max_length=512)
    question_type: str = Field(min_length=1, max_length=512)
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    question_date: str = Field(min_length=1, max_length=512)
    sessions: tuple[LongMemEvalSession, ...] = Field(min_length=1)
    evidence_session_ids: tuple[str, ...]
    evidence_turn_ids: tuple[str, ...]
    is_abstention: bool


class LongMemEvalDataset(_ClosedModel):
    """A locally loaded, digest-pinned LongMemEval dataset."""

    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: tuple[LongMemEvalRetrievalCase, ...] = Field(min_length=1)


def load_longmemeval_retrieval_cases(path: Path) -> LongMemEvalDataset:
    """Load one acquired cleaned/oracle LongMemEval JSON file without side effects."""
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise EvidenceContractError("longmemeval_dataset_unreadable") from exc
    try:
        raw: Any = json.loads(raw_bytes, object_pairs_hook=_no_duplicate_json_keys)
    except (_DuplicateJsonKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceContractError("longmemeval_dataset_invalid_json") from exc
    if not isinstance(raw, list) or not raw:
        raise EvidenceContractError("longmemeval_dataset_must_be_nonempty_list")
    if len(raw) > _MAX_CASES:
        raise EvidenceContractError("longmemeval_dataset_too_many_cases")

    cases: list[LongMemEvalRetrievalCase] = []
    seen_case_ids: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise EvidenceContractError("longmemeval_case_invalid")
        try:
            case = _normalize_case(item)
        except ValidationError as exc:
            raise EvidenceContractError("longmemeval_case_invalid") from exc
        if case.case_id in seen_case_ids:
            raise EvidenceContractError("longmemeval_case_id_duplicate")
        seen_case_ids.add(case.case_id)
        cases.append(case)
    try:
        return LongMemEvalDataset(
            source_digest=hashlib.sha256(raw_bytes).hexdigest(),
            cases=tuple(cases),
        )
    except ValidationError as exc:
        raise EvidenceContractError("longmemeval_dataset_invalid") from exc


def _normalize_case(item: Mapping[str, Any]) -> LongMemEvalRetrievalCase:
    question_id = _required_text(item, "question_id", "longmemeval_question_id_invalid")
    question_type = _required_text(item, "question_type", "longmemeval_question_type_invalid")
    question = _required_text(item, "question", "longmemeval_question_invalid")
    answer = _required_text(item, "answer", "longmemeval_answer_invalid")
    question_date = _required_text(item, "question_date", "longmemeval_question_date_invalid")
    session_ids = _required_text_list(item, "haystack_session_ids")
    session_dates = _required_text_list(item, "haystack_dates")
    raw_sessions = item.get("haystack_sessions")
    answer_ids = _required_text_list(item, "answer_session_ids", allow_empty=True)
    if not isinstance(raw_sessions, list) or not raw_sessions:
        raise EvidenceContractError("longmemeval_haystack_sessions_invalid")
    if len(raw_sessions) > _MAX_SESSIONS or len(session_ids) != len(raw_sessions):
        raise EvidenceContractError("longmemeval_session_alignment_invalid")
    if len(session_dates) != len(raw_sessions):
        raise EvidenceContractError("longmemeval_date_alignment_invalid")
    if len(set(session_ids)) != len(session_ids):
        raise EvidenceContractError("longmemeval_session_id_duplicate")
    if len(set(answer_ids)) != len(answer_ids):
        raise EvidenceContractError("longmemeval_answer_session_id_duplicate")

    sessions: list[LongMemEvalSession] = []
    evidence_turn_ids: list[str] = []
    for session_id, date, raw_turns in zip(session_ids, session_dates, raw_sessions, strict=True):
        if not isinstance(raw_turns, list) or not raw_turns:
            raise EvidenceContractError("longmemeval_session_invalid")
        if len(raw_turns) > _MAX_TURNS_PER_SESSION:
            raise EvidenceContractError("longmemeval_session_too_many_turns")
        turns: list[LongMemEvalTurn] = []
        for turn_index, raw_turn in enumerate(raw_turns, start=1):
            if not isinstance(raw_turn, Mapping):
                raise EvidenceContractError("longmemeval_turn_invalid")
            role = raw_turn.get("role")
            if role not in ("user", "assistant"):
                raise EvidenceContractError("longmemeval_turn_role_invalid")
            content = _required_text(raw_turn, "content", "longmemeval_turn_content_invalid")
            has_answer = raw_turn.get("has_answer", False)
            if not isinstance(has_answer, bool):
                raise EvidenceContractError("longmemeval_turn_has_answer_invalid")
            turn_id = f"{session_id}:turn-{turn_index}"
            turns.append(
                LongMemEvalTurn(
                    turn_id=turn_id,
                    role=role,
                    content=content,
                    has_answer=has_answer,
                )
            )
            if has_answer:
                evidence_turn_ids.append(turn_id)
        sessions.append(LongMemEvalSession(session_id=session_id, date=date, turns=tuple(turns)))

    session_id_set = set(session_ids)
    if any(answer_id not in session_id_set for answer_id in answer_ids):
        raise EvidenceContractError("longmemeval_answer_session_reference_invalid")
    try:
        return LongMemEvalRetrievalCase(
            case_id=question_id,
            question_id=question_id,
            question_type=question_type,
            question=question,
            expected_answer=answer,
            question_date=question_date,
            sessions=tuple(sessions),
            evidence_session_ids=tuple(answer_ids),
            evidence_turn_ids=tuple(evidence_turn_ids),
            is_abstention=question_id.endswith("_abs"),
        )
    except ValidationError as exc:
        raise EvidenceContractError("longmemeval_case_invalid") from exc


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object while rejecting duplicate members deterministically."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(key)
        result[key] = value
    return result


def _required_text(value: Mapping[str, Any], key: str, error: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise EvidenceContractError(error)
    return raw.strip()


def _required_text_list(
    value: Mapping[str, Any], key: str, *, allow_empty: bool = False
) -> list[str]:
    raw = value.get(key)
    if not isinstance(raw, list) or (not raw and not allow_empty):
        raise EvidenceContractError(f"longmemeval_{key}_invalid")
    error = f"longmemeval_{key}_invalid"
    normalized = [_required_text({"value": entry}, "value", error) for entry in raw]
    return normalized


__all__ = [
    "LongMemEvalDataset",
    "LongMemEvalRetrievalCase",
    "LongMemEvalSession",
    "LongMemEvalTurn",
    "load_longmemeval_retrieval_cases",
]
