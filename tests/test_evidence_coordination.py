"""Deterministic, side-effect-free contract tests for Memory P0 coordination (#447)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from scripts import bench_bm25_query_cache as benchmark
from src.memory.evidence_coordination import (
    COORDINATION_SCHEMA_VERSION,
    P0EvidencePacket,
    archive_event_ref,
    canonical_packet_bytes,
    recall_contract_ref,
    scorecard_payload_ref,
)
from src.memory.evidence_models import (
    EvidenceContractError,
    EvidenceEvent,
    EvidenceRef,
    MemoryCandidate,
)
from src.memory.recall import RecallBundle, stable_recall_fingerprint

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_REVISION = "d" * 40


def _event() -> EvidenceEvent:
    return EvidenceEvent(
        candidate=MemoryCandidate(
            candidate_id=_A,
            candidate_kind="semantic-claim",
            observed_at="2026-08-10T12:00:00Z",
            evidence_refs=(EvidenceRef("benchmark", _B, _C),),
        ),
        recorded_at="2026-08-10T12:01:00Z",
    )


def _bundle() -> RecallBundle:
    bundle = RecallBundle(
        state="completed",
        code="recall_completed",
        graph_generation=7,
        normalized_query="opaque normalized query",
        limit=3,
        fingerprint=_B,
        no_progress_signature=_C,
        per_turn_expansion_budget=50,
    )
    return bundle.model_copy(
        update={"fingerprint": stable_recall_fingerprint(bundle.cache_stable_prefix())}
    )


def _scorecard() -> dict[str, object]:
    return {
        "manifest_schema_version": 1,
        "manifest_dataset_id": "synthetic-hard-negatives.v1",
        "scorecard_fingerprint": _C,
        "evaluation_scope": {"retrieval_only": True, "end_to_end_answer_evaluated": False},
    }


def _packet() -> P0EvidencePacket:
    return P0EvidencePacket(
        source_revision=_REVISION,
        recall_ref=recall_contract_ref(_bundle()),
        scorecard_ref=scorecard_payload_ref(_scorecard()),
        archive_ref=archive_event_ref(_event()),
    )


def test_packet_is_byte_stable_immutable_and_content_free() -> None:
    packet = _packet()

    assert packet.schema_version == COORDINATION_SCHEMA_VERSION
    assert canonical_packet_bytes(packet) == canonical_packet_bytes(packet)
    assert len(packet.packet_id) == 64
    assert b"opaque normalized query" not in canonical_packet_bytes(packet)
    assert P0EvidencePacket.from_dict(packet.to_dict()) == packet
    with pytest.raises(FrozenInstanceError):
        packet.__setattr__("decision", "accepted")


def test_packet_rejects_unknown_persisted_fields() -> None:
    payload = _packet().to_dict() | {"raw_query": "must not persist"}
    with pytest.raises(EvidenceContractError, match="unexpected_packet_fields"):
        P0EvidencePacket.from_dict(payload)


@pytest.mark.parametrize(
    "changed",
    [
        lambda packet: replace(packet, source_revision="e" * 40),
        lambda packet: replace(packet, recall_ref=EvidenceRef("canonical-recall", _A, _C)),
        lambda packet: replace(packet, scorecard_ref=EvidenceRef("benchmark-scorecard", _A, _C)),
        lambda packet: replace(packet, archive_ref=EvidenceRef("evidence-archive-event", _A, _C)),
    ],
)
def test_every_governed_reference_change_invalidates_packet_id(
    changed: Callable[[P0EvidencePacket], P0EvidencePacket],
) -> None:
    packet = _packet()
    assert changed(packet).packet_id != packet.packet_id


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("source_revision", "not-a-commit", "invalid_source_revision"),
        ("claim_label", "end_to_end", "invalid_claim_label"),
        ("metric_layers", ("retrieval", "answer"), "invalid_metric_layers"),
        ("decision", "accepted", "invalid_decision"),
        (
            "schema_version",
            "governed-evidence-packet.v2",
            "unsupported_coordination_schema_version",
        ),
    ],
)
def test_packet_rejects_ungoverned_claim_expansion(
    field: str,
    value: str | tuple[str, ...],
    error: str,
) -> None:
    payload = _packet().to_dict()
    payload[field] = list(value) if field == "metric_layers" else value
    with pytest.raises(EvidenceContractError, match=error):
        P0EvidencePacket.from_dict(payload)


def test_adapters_are_deterministic_and_never_open_external_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.memory.evidence_archive.EvidenceArchive.for_graph",
        lambda *_args, **_kwargs: pytest.fail("coordination must not open the archive"),
    )
    assert recall_contract_ref(_bundle()) == recall_contract_ref(_bundle())
    assert scorecard_payload_ref(_scorecard()) == scorecard_payload_ref(_scorecard())
    assert archive_event_ref(_event()) == archive_event_ref(_event())


def test_recall_adapter_rejects_a_forged_but_well_formed_fingerprint() -> None:
    forged = _bundle().model_copy(update={"fingerprint": _A})

    with pytest.raises(EvidenceContractError, match="recall_fingerprint_unproven"):
        recall_contract_ref(forged)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "manifest_schema_version": "bad/path",
            "manifest_dataset_id": "dataset",
            "scorecard_fingerprint": _C,
        },
        {
            "manifest_schema_version": "scorecard.v1",
            "manifest_dataset_id": "dataset",
            "scorecard_fingerprint": _C,
            "evaluation_scope": {"retrieval_only": False, "end_to_end_answer_evaluated": True},
        },
        {
            "manifest_schema_version": 1,
            "manifest_dataset_id": "dataset",
            "scorecard_fingerprint": _C,
            "evaluation_scope": {
                "retrieval_only": True,
                "end_to_end_answer_evaluated": False,
                "raw": "not accepted",
            },
        },
    ],
)
def test_scorecard_adapter_rejects_unpinned_or_non_retrieval_claims(
    payload: dict[str, object],
) -> None:
    with pytest.raises(EvidenceContractError):
        scorecard_payload_ref(payload)


def test_scorecard_adapter_accepts_the_real_p0_scorecard_payload() -> None:
    manifest_path = Path(__file__).parent / "fixtures" / "bm25_hard_negative_manifest_v1.json"
    manifest, _manifest_digest = benchmark._read_manifest(manifest_path)  # noqa: SLF001
    payload = benchmark._run_scorecard_benchmark(  # noqa: SLF001
        manifest,
        top_k=8,
    )

    reference = scorecard_payload_ref(payload)

    assert reference.source_kind == "benchmark-scorecard"
    assert reference.revision_digest == payload["scorecard_fingerprint"]


def test_coordination_module_has_no_runtime_or_storage_dependency() -> None:
    source = __import__("src.memory.evidence_coordination", fromlist=["__file__"]).__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")
    for forbidden in ("sqlite3", "pathlib", "EvidenceArchive", "open_shadow", "os.", "subprocess"):
        assert forbidden not in text
