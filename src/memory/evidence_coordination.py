"""Pure, privacy-safe coordination contracts for the Memory P0 evidence gate.

This module joins the independently owned P0 outputs without persisting,
executing, accepting, or promoting anything.  Its values contain only opaque
identifiers and bounded labels, so a packet cannot become a second semantic
memory store or a canonical-write authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

from .evidence_models import (
    EvidenceContractError,
    EvidenceEvent,
    EvidenceRef,
    canonical_event_bytes,
)
from .recall import RECALL_SCHEMA_VERSION, RecallBundle, stable_recall_fingerprint

COORDINATION_SCHEMA_VERSION = "governed-evidence-packet.v1"
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

P0ClaimLabel = Literal["retrieval_only"]
P0MetricLayer = Literal["retrieval"]
P0Decision = Literal["proposed"]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _identifier(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EvidenceContractError(f"invalid_{field}")
    return value


def _digest_string(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EvidenceContractError(f"invalid_{field}")
    return value


def _schema_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise EvidenceContractError("invalid_scorecard_schema")
    return value


def _required_string(value: Mapping[str, Any], *, field: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str):
        raise EvidenceContractError(f"invalid_{field}")
    return raw


@dataclass(frozen=True, slots=True)
class P0EvidencePacket:
    """A content-free, byte-stable reference bundle for one P0 retrieval claim.

    ``decision`` is intentionally restricted to ``proposed``.  Human curation
    and any accepted/rejected transition belong to later canonical-write work;
    constructing this packet never grants that authority.
    """

    source_revision: str
    recall_ref: EvidenceRef
    scorecard_ref: EvidenceRef
    archive_ref: EvidenceRef
    claim_label: P0ClaimLabel = "retrieval_only"
    metric_layers: tuple[P0MetricLayer, ...] = ("retrieval",)
    decision: P0Decision = "proposed"
    schema_version: str = COORDINATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source_revision, str) or not _GIT_REVISION.fullmatch(
            self.source_revision
        ):
            raise EvidenceContractError("invalid_source_revision")
        for field, value in (
            ("recall_ref", self.recall_ref),
            ("scorecard_ref", self.scorecard_ref),
            ("archive_ref", self.archive_ref),
        ):
            if not isinstance(value, EvidenceRef):
                raise EvidenceContractError(f"invalid_{field}")
        if self.claim_label != "retrieval_only":
            raise EvidenceContractError("invalid_claim_label")
        layers = tuple(self.metric_layers)
        if layers != ("retrieval",):
            raise EvidenceContractError("invalid_metric_layers")
        object.__setattr__(self, "metric_layers", layers)
        if self.decision != "proposed":
            raise EvidenceContractError("invalid_decision")
        if self.schema_version != COORDINATION_SCHEMA_VERSION:
            raise EvidenceContractError("unsupported_coordination_schema_version")

    @property
    def packet_id(self) -> str:
        """Return the stable content address of this packet's governed claim."""
        return hashlib.sha256(canonical_packet_bytes(self)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "archive_ref": self.archive_ref.to_dict(),
            "claim_label": self.claim_label,
            "decision": self.decision,
            "metric_layers": list(self.metric_layers),
            "recall_ref": self.recall_ref.to_dict(),
            "schema_version": self.schema_version,
            "scorecard_ref": self.scorecard_ref.to_dict(),
            "source_revision": self.source_revision,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> P0EvidencePacket:
        expected = {
            "archive_ref",
            "claim_label",
            "decision",
            "metric_layers",
            "recall_ref",
            "schema_version",
            "scorecard_ref",
            "source_revision",
        }
        if set(value) != expected:
            raise EvidenceContractError("unexpected_packet_fields")
        raw_layers = value.get("metric_layers")
        if not isinstance(raw_layers, list) or any(
            not isinstance(layer, str) for layer in raw_layers
        ):
            raise EvidenceContractError("invalid_metric_layers")
        refs: dict[str, EvidenceRef] = {}
        for field in ("recall_ref", "scorecard_ref", "archive_ref"):
            raw_ref = value.get(field)
            if not isinstance(raw_ref, Mapping):
                raise EvidenceContractError(f"invalid_{field}")
            refs[field] = EvidenceRef.from_dict(raw_ref)
        source_revision = _required_string(value, field="source_revision")
        claim_label = _required_string(value, field="claim_label")
        decision = _required_string(value, field="decision")
        schema_version = _required_string(value, field="schema_version")
        return cls(
            source_revision=source_revision,
            recall_ref=refs["recall_ref"],
            scorecard_ref=refs["scorecard_ref"],
            archive_ref=refs["archive_ref"],
            claim_label=cast(P0ClaimLabel, claim_label),
            metric_layers=tuple(cast(P0MetricLayer, layer) for layer in raw_layers),
            decision=cast(P0Decision, decision),
            schema_version=schema_version,
        )


def canonical_packet_bytes(packet: P0EvidencePacket) -> bytes:
    """Return canonical JSON without semantic content, paths, or volatile metrics."""
    return json.dumps(
        packet.to_dict(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def recall_contract_ref(bundle: RecallBundle) -> EvidenceRef:
    """Pin a #186 recall bundle through its stable, generation-bound fingerprint."""
    if not isinstance(bundle, RecallBundle) or bundle.schema_version != RECALL_SCHEMA_VERSION:
        raise EvidenceContractError("invalid_recall_bundle")
    fingerprint = _digest_string(bundle.fingerprint, field="recall_fingerprint")
    if fingerprint != stable_recall_fingerprint(bundle.cache_stable_prefix()):
        raise EvidenceContractError("recall_fingerprint_unproven")
    return EvidenceRef(
        source_kind="canonical-recall",
        source_id=_digest({"kind": "canonical-recall", "fingerprint": fingerprint}),
        revision_digest=fingerprint,
    )


def scorecard_payload_ref(payload: Mapping[str, Any]) -> EvidenceRef:
    """Pin a retrieval-only #448 scorecard without retaining its raw payload."""
    if not isinstance(payload, Mapping):
        raise EvidenceContractError("invalid_scorecard_payload")
    schema_version = _schema_version(payload.get("manifest_schema_version"))
    dataset_id = _identifier(payload.get("manifest_dataset_id"), field="scorecard_dataset")
    fingerprint = _digest_string(
        payload.get("scorecard_fingerprint"), field="scorecard_fingerprint"
    )
    scope = payload.get("evaluation_scope")
    if (
        not isinstance(scope, Mapping)
        or set(scope) != {"retrieval_only", "end_to_end_answer_evaluated"}
        or scope.get("retrieval_only") is not True
        or scope.get("end_to_end_answer_evaluated") is not False
    ):
        raise EvidenceContractError("invalid_scorecard_scope")
    return EvidenceRef(
        source_kind="benchmark-scorecard",
        source_id=_digest(
            {
                "dataset_id": dataset_id,
                "kind": "benchmark-scorecard",
                "schema_version": schema_version,
            }
        ),
        revision_digest=fingerprint,
    )


def archive_event_ref(event: EvidenceEvent) -> EvidenceRef:
    """Pin one append-only #449 event without opening or writing its archive."""
    if not isinstance(event, EvidenceEvent):
        raise EvidenceContractError("invalid_evidence_event")
    event_id = _digest_string(event.event_id, field="event_id")
    if hashlib.sha256(canonical_event_bytes(event)).hexdigest() != event_id:
        raise EvidenceContractError("invalid_evidence_event")
    return EvidenceRef(
        source_kind="evidence-archive-event",
        source_id=event.candidate.candidate_id,
        revision_digest=event_id,
    )


__all__ = [
    "COORDINATION_SCHEMA_VERSION",
    "P0ClaimLabel",
    "P0Decision",
    "P0EvidencePacket",
    "P0MetricLayer",
    "archive_event_ref",
    "canonical_packet_bytes",
    "recall_contract_ref",
    "scorecard_payload_ref",
]
