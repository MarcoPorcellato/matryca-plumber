"""Tests for closed public-suite local-input provenance."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError
from src.memory.benchmark_protocol import DatasetPin
from src.memory.evidence_models import EvidenceContractError
from src.memory.public_suite_provenance import (
    PublicSuiteInputProvenance,
    verify_public_suite_input,
)


def _provenance(raw: bytes = b"public fixture") -> PublicSuiteInputProvenance:
    return PublicSuiteInputProvenance(
        dataset=DatasetPin(
            suite="locomo",
            dataset_id="locomo-v1",
            repository_slug="snap-research/locomo",
            dataset_revision="a" * 40,
            license_id="CC-BY-4.0",
        ),
        raw_input_digest=hashlib.sha256(raw).hexdigest(),
        evidence_kind="local_input_provenance_only",
    )


def test_provenance_is_closed_immutable_and_binds_exact_bytes() -> None:
    raw = b"public fixture"
    provenance = _provenance(raw)

    assert (
        verify_public_suite_input(provenance, raw, expected_suite="locomo")
        == hashlib.sha256(raw).hexdigest()
    )
    with pytest.raises(ValidationError):
        provenance.raw_input_digest = "a" * 64
    with pytest.raises(ValueError):
        PublicSuiteInputProvenance.model_validate({**provenance.model_dump(), "path": "/unsafe"})
    with pytest.raises(EvidenceContractError, match="public_suite_input_digest_mismatch"):
        verify_public_suite_input(provenance, b"different", expected_suite="locomo")
    with pytest.raises(EvidenceContractError, match="public_suite_provenance_suite_mismatch"):
        verify_public_suite_input(provenance, raw, expected_suite="longmemeval")
