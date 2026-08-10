"""Tests for the local-only LongMemEval-V2 input adapter."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError
from src.memory.evidence_models import EvidenceContractError
from src.memory.longmemeval_adapter import LongMemEvalDataset
from src.memory.longmemeval_v2_adapter import (
    LongMemEvalV2InputEvidence,
    load_longmemeval_v2_input,
)

_REVISION = "0123456789abcdef0123456789abcdef01234567"


def _write_jsonl(tmp_path: Path, name: str, records: list[object]) -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return path


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    questions = _write_jsonl(
        tmp_path,
        "questions.jsonl",
        [
            {"question_id": "q-2", "question": "Later?"},
            {"question_id": "q-1", "question": "What changed?"},
        ],
    )
    trajectories = _write_jsonl(
        tmp_path,
        "trajectories.jsonl",
        [
            {"trajectory_id": "haystack-b", "turns": [{"role": "assistant", "content": "B"}]},
            {"trajectory_id": "haystack-a", "turns": [{"role": "user", "content": "A"}]},
        ],
    )
    mappings = _write_jsonl(
        tmp_path,
        "mapping.jsonl",
        [
            {"question_id": "q-2", "trajectory_ids": ["haystack-b"]},
            {"question_id": "q-1", "trajectory_ids": ["haystack-a", "haystack-b"]},
        ],
    )
    return questions, trajectories, mappings


def test_load_is_deterministic_ordered_and_digest_pinned(tmp_path: Path) -> None:
    questions, trajectories, mappings = _inputs(tmp_path)
    first = load_longmemeval_v2_input(
        questions, trajectories, mappings, dataset_license_id="MIT", huggingface_revision=_REVISION
    )
    second = load_longmemeval_v2_input(
        questions, trajectories, mappings, dataset_license_id="MIT", huggingface_revision=_REVISION
    )

    assert first == second
    assert [item.question_id for item in first.questions] == ["q-2", "q-1"]
    assert [item.trajectory_id for item in first.trajectories] == ["haystack-b", "haystack-a"]
    assert [item.question_id for item in first.mappings] == ["q-2", "q-1"]
    assert (
        first.provenance.question_input_digest == hashlib.sha256(questions.read_bytes()).hexdigest()
    )
    assert len(first.provenance.source_envelope_digest) == 64
    assert first.provenance.evidence_kind == "input_provenance_only"
    with pytest.raises(ValidationError):
        first.questions[0].question = "mutated"


def test_unsupported_and_oversized_records_fail_closed(tmp_path: Path) -> None:
    questions, trajectories, mappings = _inputs(tmp_path)
    questions.write_text(
        '{"question_id":"q-1","question":"ok","unsupported":true}\n', encoding="utf-8"
    )
    with pytest.raises(EvidenceContractError, match="longmemeval_v2_question_record_invalid"):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )
    questions, trajectories, mappings = _inputs(tmp_path)
    trajectories.write_text(
        json.dumps(
            {"trajectory_id": "haystack-a", "turns": [{"role": "user", "content": "x" * 65_537}]}
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(EvidenceContractError, match="longmemeval_v2_trajectory_record_invalid"):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (b"{not-json}\n", "longmemeval_v2_question_record_invalid"),
        (
            b'{"question_id":"q-1","question":"a","question":"b"}\n',
            "longmemeval_v2_question_record_invalid",
        ),
        (b'{"question_id":"q-1","question":NaN}\n', "longmemeval_v2_question_record_invalid"),
        (
            b'{"question_id":"q-1","question":Infinity}\n',
            "longmemeval_v2_question_record_invalid",
        ),
        (
            b'{"question_id":"q-1","question":-Infinity}\n',
            "longmemeval_v2_question_record_invalid",
        ),
    ],
)
def test_malformed_json_fails_closed(tmp_path: Path, payload: bytes, error: str) -> None:
    _questions, trajectories, mappings = _inputs(tmp_path)
    bad = tmp_path / "bad.jsonl"
    bad.write_bytes(payload)
    with pytest.raises(EvidenceContractError, match=error):
        load_longmemeval_v2_input(
            bad, trajectories, mappings, dataset_license_id="MIT", huggingface_revision=_REVISION
        )


def test_duplicate_ids_and_invalid_mapping_cross_reference_fail_closed(tmp_path: Path) -> None:
    questions, trajectories, mappings = _inputs(tmp_path)
    questions.write_text(
        '{"question_id":"q-1","question":"a"}\n{"question_id":"q-1","question":"b"}\n',
        encoding="utf-8",
    )
    with pytest.raises(EvidenceContractError, match="longmemeval_v2_question_id_duplicate"):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )
    questions, trajectories, mappings = _inputs(tmp_path)
    mappings.write_text(
        '{"question_id":"q-1","trajectory_ids":["missing"]}\n{"question_id":"q-2","trajectory_ids":["haystack-b"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(
        EvidenceContractError, match="longmemeval_v2_trajectory_cross_reference_missing"
    ):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )
    mappings.write_text(
        '{"question_id":"q-1","trajectory_ids":["haystack-a","haystack-a"]}\n{"question_id":"q-2","trajectory_ids":["haystack-b"]}\n',
        encoding="utf-8",
    )
    with pytest.raises(
        EvidenceContractError, match="longmemeval_v2_mapping_trajectory_id_duplicate"
    ):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )
    mappings.write_text('{"question_id":"q-1","trajectory_ids":["haystack-a"]}\n', encoding="utf-8")
    with pytest.raises(EvidenceContractError, match="longmemeval_v2_question_mapping_incomplete"):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id="MIT",
            huggingface_revision=_REVISION,
        )


@pytest.mark.parametrize(
    ("license_id", "revision"),
    [("", _REVISION), ("MIT", "not-a-revision"), ("CC BY 4.0", _REVISION)],
)
def test_missing_or_malformed_provenance_fails_closed(
    tmp_path: Path, license_id: str, revision: str
) -> None:
    questions, trajectories, mappings = _inputs(tmp_path)
    with pytest.raises(EvidenceContractError, match="longmemeval_v2_(license|revision)_invalid"):
        load_longmemeval_v2_input(
            questions,
            trajectories,
            mappings,
            dataset_license_id=license_id,
            huggingface_revision=revision,
        )


def test_no_network_side_effects_and_v1_separation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "socket", fail_socket)
    paths = _inputs(tmp_path)
    before = {path: path.stat().st_mtime_ns for path in paths}
    result = load_longmemeval_v2_input(
        *paths, dataset_license_id="MIT", huggingface_revision=_REVISION
    )
    after = {path: path.stat().st_mtime_ns for path in before}
    assert before == after
    assert isinstance(result, LongMemEvalV2InputEvidence)
    assert LongMemEvalDataset.__module__.endswith("longmemeval_adapter")
    assert result.__class__.__module__.endswith("longmemeval_v2_adapter")
