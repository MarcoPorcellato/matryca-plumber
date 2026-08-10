"""Tests for the local-only LoCoMo retrieval adapter."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from src.memory.evidence_models import EvidenceContractError
from src.memory.locomo_adapter import load_locomo_retrieval_cases


def _dataset() -> list[object]:
    return [
        {
            "sample_id": "locomo-sample-1",
            "conversation": {
                "speaker_a": "A",
                "speaker_b": "B",
                "session_2_date_time": "2024-01-02",
                "session_2": [
                    {"speaker": "B", "dia_id": "turn-2", "text": "The revised plan is active."},
                ],
                "session_1": [
                    {
                        "speaker": "A",
                        "dia_id": "turn-1",
                        "text": "The earlier plan was provisional.",
                        "img_url": "https://example.invalid/not-followed",
                    },
                ],
            },
            "qa": [
                {
                    "question": "Which plan is active?",
                    "answer": "The revised plan.",
                    "category": 2,
                    "evidence": ["turn-2"],
                },
                {
                    "question": "What is the unreleased codename?",
                    "adversarial_answer": 2022,
                    "category": 5,
                    "evidence": [],
                },
            ],
        }
    ]


def _write_dataset(tmp_path: Path, payload: object | None = None) -> Path:
    path = tmp_path / "locomo10.json"
    path.write_text(json.dumps(_dataset() if payload is None else payload), encoding="utf-8")
    return path


def test_adapter_normalizes_sessions_evidence_and_abstention_deterministically(
    tmp_path: Path,
) -> None:
    path = _write_dataset(tmp_path)

    dataset = load_locomo_retrieval_cases(path)

    assert dataset.source_digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert [case.case_id for case in dataset.cases] == ["locomo-sample-1:1", "locomo-sample-1:2"]
    assert [turn.turn_id for turn in dataset.cases[0].turns] == ["turn-1", "turn-2"]
    assert dataset.cases[0].evidence_turn_ids == ("turn-2",)
    assert dataset.cases[0].category == "2"
    assert dataset.cases[0].evidence_available is True
    assert dataset.cases[1].evidence_turn_ids == ()
    assert dataset.cases[1].category == "5"
    assert dataset.cases[1].expected_answer == "2022"
    assert dataset.cases[1].evidence_available is False


def test_adapter_never_opens_network_or_follows_optional_image_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_dataset(tmp_path)

    def reject_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Unexpected network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket, "gethostbyname", reject_network)

    assert len(load_locomo_retrieval_cases(path).cases) == 2


@pytest.mark.parametrize(
    "payload,error",
    [
        ([], "locomo_dataset_must_be_nonempty_list"),
        ([{"sample_id": "x", "conversation": {}, "qa": []}], "locomo_sessions_missing"),
        (
            [
                {
                    "sample_id": "x",
                    "conversation": {"session_1": [{"speaker": "a", "dia_id": "t", "text": "x"}]},
                    "qa": [
                        {"question": "q", "answer": "a", "category": "c", "evidence": ["missing"]}
                    ],
                }
            ],
            "locomo_evidence_invalid",
        ),
        (
            [
                {
                    "sample_id": "x",
                    "conversation": {"session_1": [{"speaker": "a", "dia_id": "t", "text": "x"}]},
                    "qa": [{"question": "q", "answer": "a", "category": 1}],
                }
            ],
            "locomo_evidence_invalid",
        ),
    ],
)
def test_adapter_fails_closed_for_malformed_required_evidence(
    tmp_path: Path,
    payload: object,
    error: str,
) -> None:
    with pytest.raises(EvidenceContractError, match=error):
        load_locomo_retrieval_cases(_write_dataset(tmp_path, payload))
