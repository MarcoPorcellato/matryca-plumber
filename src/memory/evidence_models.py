"""Privacy-safe, immutable P0 evidence and candidate contracts.

These records deliberately contain only opaque provenance identifiers and
bounded classifications.  They never carry vault text, prompts, credentials,
or filesystem paths.  They model *candidate* memory only: P0 cannot accept,
promote, or mutate canonical Logseq knowledge.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

EVIDENCE_SCHEMA_VERSION = 1
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceContractError(ValueError):
    """A content-free validation failure for an evidence contract."""


def _identifier(value: str, *, field: str) -> str:
    normalized = value.strip()
    if not _IDENTIFIER.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _sha256(value: str, *, field: str) -> str:
    normalized = value.strip().lower()
    if not _SHA256.fullmatch(normalized):
        raise EvidenceContractError(f"invalid_{field}")
    return normalized


def _timestamp(value: str, *, field: str) -> str:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise EvidenceContractError(f"invalid_{field}") from exc
    if parsed.tzinfo is None:
        raise EvidenceContractError(f"invalid_{field}")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Opaque, revision-pinned provenance for one candidate observation."""

    source_kind: str
    source_id: str
    revision_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_kind", _identifier(self.source_kind, field="source_kind"))
        object.__setattr__(self, "source_id", _sha256(self.source_id, field="source_id"))
        object.__setattr__(
            self,
            "revision_digest",
            _sha256(self.revision_digest, field="revision_digest"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "revision_digest": self.revision_digest,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvidenceRef:
        _require_exact_keys(value, {"source_kind", "source_id", "revision_digest"})
        return cls(
            source_kind=_required_string(value, "source_kind"),
            source_id=_required_string(value, "source_id"),
            revision_digest=_required_string(value, "revision_digest"),
        )


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """A proposed memory with traceable, immutable P0 provenance only."""

    candidate_id: str
    candidate_kind: str
    observed_at: str
    evidence_refs: tuple[EvidenceRef, ...]
    status: Literal["proposed"] = "proposed"

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _sha256(self.candidate_id, field="candidate_id"))
        object.__setattr__(
            self,
            "candidate_kind",
            _identifier(self.candidate_kind, field="candidate_kind"),
        )
        object.__setattr__(self, "observed_at", _timestamp(self.observed_at, field="observed_at"))
        if self.status != "proposed":
            raise EvidenceContractError("invalid_candidate_status")
        refs = tuple(self.evidence_refs)
        if not refs:
            raise EvidenceContractError("missing_evidence_refs")
        if len(refs) > 32:
            raise EvidenceContractError("too_many_evidence_refs")
        if any(not isinstance(ref, EvidenceRef) for ref in refs):
            raise EvidenceContractError("invalid_evidence_ref")
        if tuple(sorted(refs, key=_ref_sort_key)) != refs:
            raise EvidenceContractError("evidence_refs_not_canonical")
        if len({_ref_sort_key(ref) for ref in refs}) != len(refs):
            raise EvidenceContractError("duplicate_evidence_ref")
        object.__setattr__(self, "evidence_refs", refs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_kind": self.candidate_kind,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "observed_at": self.observed_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> MemoryCandidate:
        _require_exact_keys(
            value,
            {"candidate_id", "candidate_kind", "evidence_refs", "observed_at", "status"},
        )
        raw_refs = value.get("evidence_refs")
        if not isinstance(raw_refs, list):
            raise EvidenceContractError("invalid_evidence_refs")
        refs: list[EvidenceRef] = []
        for raw_ref in raw_refs:
            if not isinstance(raw_ref, Mapping):
                raise EvidenceContractError("invalid_evidence_ref")
            refs.append(EvidenceRef.from_dict(raw_ref))
        status = _required_string(value, "status")
        if status != "proposed":
            raise EvidenceContractError("invalid_candidate_status")
        return cls(
            candidate_id=_required_string(value, "candidate_id"),
            candidate_kind=_required_string(value, "candidate_kind"),
            observed_at=_required_string(value, "observed_at"),
            evidence_refs=tuple(refs),
            status=cast(Literal["proposed"], status),
        )


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    """One immutable, replay-safe observation recorded by the P0 archive."""

    candidate: MemoryCandidate
    recorded_at: str
    event_type: Literal["candidate_observed"] = "candidate_observed"
    schema_version: int = EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, MemoryCandidate):
            raise EvidenceContractError("invalid_candidate")
        object.__setattr__(self, "recorded_at", _timestamp(self.recorded_at, field="recorded_at"))
        if self.event_type != "candidate_observed":
            raise EvidenceContractError("invalid_event_type")
        if self.schema_version != EVIDENCE_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_schema_version")

    @property
    def event_id(self) -> str:
        return hashlib.sha256(canonical_event_bytes(self)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "event_type": self.event_type,
            "recorded_at": self.recorded_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvidenceEvent:
        _require_exact_keys(value, {"candidate", "event_type", "recorded_at", "schema_version"})
        raw_candidate = value.get("candidate")
        if not isinstance(raw_candidate, Mapping):
            raise EvidenceContractError("invalid_candidate")
        event_type = _required_string(value, "event_type")
        if event_type != "candidate_observed":
            raise EvidenceContractError("invalid_event_type")
        return cls(
            candidate=MemoryCandidate.from_dict(raw_candidate),
            recorded_at=_required_string(value, "recorded_at"),
            event_type=cast(Literal["candidate_observed"], event_type),
            schema_version=_required_int(value, "schema_version"),
        )


def canonical_event_bytes(event: EvidenceEvent) -> bytes:
    """Return byte-stable canonical JSON for an immutable evidence event."""
    return json.dumps(
        event.to_dict(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _required_string(value: Mapping[str, Any], key: str) -> str:
    raw = value.get(key)
    if not isinstance(raw, str):
        raise EvidenceContractError(f"invalid_{key}")
    return raw


def _required_int(value: Mapping[str, Any], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise EvidenceContractError(f"invalid_{key}")
    return raw


def _require_exact_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    """Reject unmodeled persisted fields before they can bypass privacy validation."""
    if set(value) != expected:
        raise EvidenceContractError("unexpected_fields")


def _ref_sort_key(value: EvidenceRef) -> tuple[str, str, str]:
    return value.source_kind, value.source_id, value.revision_digest


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "EvidenceContractError",
    "EvidenceEvent",
    "EvidenceRef",
    "MemoryCandidate",
    "canonical_event_bytes",
]
