from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from src.memory.evidence_models import (
    EvidenceContractError,
    EvidenceEvent,
    EvidenceRef,
    MemoryCandidate,
    canonical_event_bytes,
)

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64


def _candidate() -> MemoryCandidate:
    return MemoryCandidate(
        candidate_id=_DIGEST_A,
        candidate_kind="semantic-claim",
        observed_at="2026-08-10T12:00:00+00:00",
        evidence_refs=(EvidenceRef("benchmark", _DIGEST_B, _DIGEST_C),),
    )


def test_event_is_immutable_and_byte_stable() -> None:
    event = EvidenceEvent(candidate=_candidate(), recorded_at="2026-08-10T12:01:00Z")

    assert event.recorded_at == "2026-08-10T12:01:00Z"
    assert canonical_event_bytes(event) == canonical_event_bytes(event)
    assert len(event.event_id) == 64
    with pytest.raises(FrozenInstanceError):
        event.__setattr__("recorded_at", "2026-08-11T00:00:00Z")


def test_models_reject_content_bearing_or_unpinned_provenance() -> None:
    unsafe_source = "/private/note.md"
    with pytest.raises(EvidenceContractError, match="invalid_source_id") as exc_info:
        EvidenceRef("graph-block", unsafe_source, _DIGEST_C)
    assert unsafe_source not in str(exc_info.value)
    with pytest.raises(EvidenceContractError, match="missing_evidence_refs"):
        MemoryCandidate(
            candidate_id=_DIGEST_A,
            candidate_kind="semantic-claim",
            observed_at="2026-08-10T12:00:00Z",
            evidence_refs=(),
        )


def test_evidence_refs_must_be_canonical_and_unique() -> None:
    first = EvidenceRef("benchmark", _DIGEST_B, _DIGEST_C)
    second = EvidenceRef("graph-block", _DIGEST_C, _DIGEST_A)

    with pytest.raises(EvidenceContractError, match="evidence_refs_not_canonical"):
        MemoryCandidate(
            candidate_id=_DIGEST_A,
            candidate_kind="semantic-claim",
            observed_at="2026-08-10T12:00:00Z",
            evidence_refs=(second, first),
        )
    with pytest.raises(EvidenceContractError, match="duplicate_evidence_ref"):
        MemoryCandidate(
            candidate_id=_DIGEST_A,
            candidate_kind="semantic-claim",
            observed_at="2026-08-10T12:00:00Z",
            evidence_refs=(second, second),
        )
