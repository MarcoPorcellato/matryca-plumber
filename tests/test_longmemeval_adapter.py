"""Tests for the local-only LongMemEval retrieval adapter."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
from src.memory.benchmark_protocol import DatasetPin
from src.memory.evidence_models import EvidenceContractError
from src.memory.longmemeval_adapter import LongMemEvalDataset, load_longmemeval_retrieval_cases
from src.memory.public_suite_provenance import PublicSuiteInputProvenance


def _case(*, question_id: str = "q-1") -> dict[str, object]:
    return {
        "question_id": question_id,
        "question_type": "multi_session",
        "question": "What changed?",
        "answer": "The revised plan.",
        "question_date": "2024-01-03",
        "haystack_session_ids": ["session-z", "session-a"],
        "haystack_dates": ["2024-01-01", "2024-01-02"],
        "haystack_sessions": [
            [
                {"role": "user", "content": "The old plan."},
                {"role": "assistant", "content": "It was provisional."},
            ],
            [
                {"role": "user", "content": "The revised plan.", "has_answer": True},
            ],
        ],
        "answer_session_ids": ["session-a"],
        "unknown_field": {"ignored": True},
    }


def _write_dataset(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "longmemeval_s_cleaned.json"
    path.write_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return path


def _provenance(path: Path, *, digest: str | None = None) -> PublicSuiteInputProvenance:
    return PublicSuiteInputProvenance(
        dataset=DatasetPin(
            suite="longmemeval",
            dataset_id="longmemeval-v1",
            repository_slug="xiaowu0162/longmemeval",
            dataset_revision="b" * 40,
            license_id="MIT",
        ),
        raw_input_digest=digest or hashlib.sha256(path.read_bytes()).hexdigest(),
        evidence_kind="local_input_provenance_only",
    )


def _load(path: Path) -> LongMemEvalDataset:
    return load_longmemeval_retrieval_cases(path, provenance=_provenance(path))


def test_normalizes_digest_evidence_and_preserves_upstream_order(tmp_path: Path) -> None:
    payload = [_case()]
    path = _write_dataset(tmp_path, payload)

    dataset = _load(path)
    case = dataset.cases[0]

    assert dataset.source_digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert case.case_id == "q-1"
    assert [session.session_id for session in case.sessions] == ["session-z", "session-a"]
    assert [session.date for session in case.sessions] == ["2024-01-01", "2024-01-02"]
    assert case.evidence_session_ids == ("session-a",)
    assert case.evidence_turn_ids == ("session-a:turn-1",)
    assert case.is_abstention is False
    assert case.sessions[0].turns[0].turn_id == "session-z:turn-1"
    # Unknown upstream fields are intentionally ignored for forward compatibility.
    assert case.question == "What changed?"
    assert case.model_config["extra"] == "forbid"


def test_digest_is_stable_and_abs_is_metadata_not_inferred_evidence(tmp_path: Path) -> None:
    payload = [_case(question_id="q-2_abs")]
    path = _write_dataset(tmp_path, payload)

    first = _load(path)
    second = _load(path)

    assert first == second
    assert first.cases[0].is_abstention is True
    assert first.cases[0].evidence_session_ids == ("session-a",)

    abstention_path = _write_dataset(
        tmp_path,
        [{**_case(question_id="q-3_abs"), "answer_session_ids": []}],
    )
    abstention = _load(abstention_path).cases[0]
    assert abstention.is_abstention is True
    assert abstention.evidence_session_ids == ()
    assert abstention.evidence_turn_ids == ("session-a:turn-1",)


def test_preserves_multiple_evidence_and_oracle_style_nonchronological_order(
    tmp_path: Path,
) -> None:
    payload = _case()
    payload["haystack_dates"] = ["2024-12-31", "2023-01-01"]
    payload["answer_session_ids"] = ["session-a", "session-z"]

    case = _load(_write_dataset(tmp_path, [payload])).cases[0]

    assert [session.session_id for session in case.sessions] == ["session-z", "session-a"]
    assert [session.date for session in case.sessions] == ["2024-12-31", "2023-01-01"]
    assert case.evidence_session_ids == ("session-a", "session-z")


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"question": ""}, "longmemeval_question_invalid"),
        ({"haystack_session_ids": ["session-z"]}, "longmemeval_session_alignment_invalid"),
        (
            {"haystack_sessions": [[{"role": "system", "content": "bad"}], []]},
            "longmemeval_turn_role_invalid",
        ),
        ({"answer_session_ids": ["missing"]}, "longmemeval_answer_session_reference_invalid"),
        (
            {
                "haystack_sessions": [
                    [{"role": "user", "content": "x", "has_answer": "yes"}],
                    [{"role": "user", "content": "y"}],
                ]
            },
            "longmemeval_turn_has_answer_invalid",
        ),
    ],
)
def test_invalid_required_values_and_references_fail_closed(
    tmp_path: Path, change: dict[str, object], error: str
) -> None:
    payload = _case()
    payload.update(change)

    with pytest.raises(EvidenceContractError, match=f"^{error}$"):
        _load(_write_dataset(tmp_path, [payload]))


def test_duplicate_question_ids_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(EvidenceContractError, match="^longmemeval_case_id_duplicate$"):
        _load(_write_dataset(tmp_path, [_case(), _case()]))


@pytest.mark.parametrize("payload", [[], {}, {"question_id": "q"}, ["not-a-case"]])
def test_invalid_top_level_shape_fails_closed(tmp_path: Path, payload: object) -> None:
    with pytest.raises(EvidenceContractError):
        _load(_write_dataset(tmp_path, payload))


def test_invalid_json_and_unreadable_file_fail_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"not-json")
    with pytest.raises(EvidenceContractError, match="^longmemeval_dataset_invalid_json$"):
        _load(invalid)

    with pytest.raises(EvidenceContractError, match="^longmemeval_dataset_unreadable$"):
        load_longmemeval_retrieval_cases(
            tmp_path / "missing.json",
            provenance=_provenance(tmp_path / "missing.json", digest="a" * 64),
        )


def test_duplicate_json_key_and_oversized_model_field_fail_closed(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_bytes(b'[{"question_id":"q-1","question_id":"q-2"}]')
    with pytest.raises(EvidenceContractError, match="^longmemeval_dataset_invalid_json$"):
        _load(duplicate)

    payload = _case()
    payload["question_id"] = "q" * 513
    with pytest.raises(EvidenceContractError, match="^longmemeval_case_invalid$"):
        _load(_write_dataset(tmp_path, [payload]))

    payload = _case()
    payload["haystack_session_ids"] = ["s" * 513, "session-a"]
    with pytest.raises(EvidenceContractError, match="^longmemeval_case_invalid$"):
        _load(_write_dataset(tmp_path, [payload]))


def test_adapter_makes_no_network_calls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket, "socket", fail)
    _load(_write_dataset(tmp_path, [_case()]))


def test_adapter_rejects_wrong_suite_or_digest(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, [_case()])
    provenance = _provenance(path)
    with pytest.raises(EvidenceContractError, match="public_suite_input_digest_mismatch"):
        load_longmemeval_retrieval_cases(
            path,
            provenance=provenance.model_copy(update={"raw_input_digest": "c" * 64}),
        )
    with pytest.raises(EvidenceContractError, match="public_suite_provenance_suite_mismatch"):
        load_longmemeval_retrieval_cases(
            path,
            provenance=provenance.model_copy(
                update={"dataset": provenance.dataset.model_copy(update={"suite": "locomo"})}
            ),
        )
