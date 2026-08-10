"""Tests for the local-only BEAM input adapter."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from src.memory.beam_adapter import BeamInputEvidence, load_beam_input
from src.memory.benchmark_protocol import DatasetPin
from src.memory.evidence_models import EvidenceContractError

_REVISION = "3e12035532eb85768f1a7cd779832b650c4b2ef9"


def _dataset() -> DatasetPin:
    return DatasetPin(
        suite="beam",
        dataset_id="beam-100k",
        repository_slug="mohammadtavakoli78/BEAM",
        dataset_revision=_REVISION,
        license_id="CC-BY-SA-4.0",
    )


def _inputs(tmp_path: Path) -> tuple[Path, Path]:
    chat = tmp_path / "chat.json"
    chat.write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "turns": [
                        {"role": "user", "id": "1,1", "content": "First topic"},
                        {"role": "assistant", "id": "1,2", "content": "Acknowledged"},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    questions = tmp_path / "probing_questions.json"
    questions.write_text(
        json.dumps(
            {
                "information_extraction": [
                    {"question": "What was the topic?", "ideal_answer": "First"}
                ],
                "event_ordering": [{"question": "What happened first?"}],
            }
        ),
        encoding="utf-8",
    )
    return chat, questions


def _load(tmp_path: Path) -> BeamInputEvidence:
    chat, questions = _inputs(tmp_path)
    return load_beam_input(chat, questions, chat_id="100K/1", dataset=_dataset())


def test_load_is_deterministic_ordered_and_digest_bound(tmp_path: Path) -> None:
    first = _load(tmp_path)
    second = _load(tmp_path)

    assert first == second
    assert [turn.turn_id for turn in first.conversation.turns] == ["1,1", "1,2"]
    assert [question.question_id for question in first.questions] == [
        "100K/1:information_extraction:1",
        "100K/1:event_ordering:1",
    ]
    assert (
        first.provenance.chat_input_digest
        == hashlib.sha256((tmp_path / "chat.json").read_bytes()).hexdigest()
    )
    assert first.provenance.evidence_kind == "local_input_provenance_only"


@pytest.mark.parametrize(
    ("chat_payload", "question_payload", "error"),
    [
        (b'[{"batch_number":1,"turns":[]} ]', None, "beam_chat_invalid"),
        (
            b'[{"batch_number":1,"turns":[{"role":"user","id":"x","id":"y","content":"a"}]}]',
            None,
            "beam_chat_invalid",
        ),
        (None, b'{"category":[{"question":"a","question":"b"}]}', "beam_questions_invalid"),
        (None, b'{"category":[{}]}', "beam_questions_invalid"),
    ],
)
def test_invalid_or_duplicate_source_fields_fail_closed(
    tmp_path: Path, chat_payload: bytes | None, question_payload: bytes | None, error: str
) -> None:
    chat, questions = _inputs(tmp_path)
    if chat_payload is not None:
        chat.write_bytes(chat_payload)
    if question_payload is not None:
        questions.write_bytes(question_payload)
    with pytest.raises(EvidenceContractError, match=error):
        load_beam_input(chat, questions, chat_id="100K/1", dataset=_dataset())


def test_suite_mismatch_and_duplicate_turn_ids_fail_closed(tmp_path: Path) -> None:
    chat, questions = _inputs(tmp_path)
    with pytest.raises(EvidenceContractError, match="beam_dataset_suite_mismatch"):
        load_beam_input(
            chat,
            questions,
            chat_id="100K/1",
            dataset=_dataset().model_copy(update={"suite": "locomo"}),
        )
    chat.write_text(
        json.dumps(
            [
                {
                    "batch_number": 1,
                    "turns": [
                        {"role": "user", "id": "x", "content": "a"},
                        {"role": "assistant", "id": "x", "content": "b"},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(EvidenceContractError, match="beam_turn_id_duplicate"):
        load_beam_input(chat, questions, chat_id="100K/1", dataset=_dataset())


def test_no_network_or_write_side_effects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", fail_socket)
    paths = _inputs(tmp_path)
    before = {path: path.stat().st_mtime_ns for path in paths}
    result = load_beam_input(*paths, chat_id="100K/1", dataset=_dataset())
    assert before == {path: path.stat().st_mtime_ns for path in paths}
    assert isinstance(result, BeamInputEvidence)
