"""Closed provenance binding for caller-supplied public benchmark inputs."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .benchmark_protocol import DatasetPin, SuiteName
from .evidence_models import EvidenceContractError

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PublicSuiteInputProvenance(BaseModel):
    """Pinned public-suite identity and expected digest for one local input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: DatasetPin
    raw_input_digest: str = Field(pattern=_SHA256.pattern)
    evidence_kind: Literal["local_input_provenance_only"]


def verify_public_suite_input(
    provenance: PublicSuiteInputProvenance,
    raw_bytes: bytes,
    *,
    expected_suite: SuiteName,
) -> str:
    """Fail closed unless supplied bytes match the declared public-suite pin."""

    if provenance.dataset.suite != expected_suite:
        raise EvidenceContractError("public_suite_provenance_suite_mismatch")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if digest != provenance.raw_input_digest:
        raise EvidenceContractError("public_suite_input_digest_mismatch")
    return digest


__all__ = ["PublicSuiteInputProvenance", "verify_public_suite_input"]
