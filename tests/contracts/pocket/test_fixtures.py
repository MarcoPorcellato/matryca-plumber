from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from src.contracts.pocket.canonical import JsonValue, PocketContractError, canonical_json_bytes
from src.contracts.pocket.models import (
    DocumentV1,
    EvidenceV1,
    PackManifestV1,
    validate_record_set,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_ROOT = ROOT / "contracts/pocket/v1"
FIXTURE_ROOT = CONTRACT_ROOT / "fixtures"
SCHEMA_ROOT = CONTRACT_ROOT / "schemas"
VECTOR_PATH = CONTRACT_ROOT / "vectors/canonical-json.json"
MAX_JSON_BYTES = 1_000_000
MAX_JSONL_ROW_BYTES = 128_000


@dataclass(frozen=True, slots=True)
class FixtureExpectation:
    schema_status: str
    contract_status: str
    contract_error_code: str | None = None


def _read_bounded(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    raw = path.read_bytes()
    assert len(raw) <= limit, path
    return raw


def _load_json(path: Path) -> object:
    return json.loads(_read_bounded(path))


def _load_jsonl(path: Path) -> tuple[object, ...]:
    raw = _read_bounded(path)
    assert raw.endswith(b"\n"), path
    rows: list[object] = []
    for line in raw.splitlines():
        assert line and len(line) <= MAX_JSONL_ROW_BYTES, path
        rows.append(json.loads(line))
    return tuple(rows)


def load_expectation(path: Path) -> FixtureExpectation:
    raw = _load_json(path)
    assert isinstance(raw, dict)
    assert set(raw) in (
        {"contract_status", "schema_status"},
        {"contract_error_code", "contract_status", "schema_status"},
    )
    return FixtureExpectation(**raw)


def _schema_errors(case_root: Path) -> Iterator[object]:
    for filename, value in (
        ("pack-manifest.schema.json", _load_json(case_root / "manifest.json")),
        ("document.schema.json", _load_jsonl(case_root / "documents.jsonl")),
        ("evidence.schema.json", _load_jsonl(case_root / "evidence.jsonl")),
    ):
        schema = _load_json(SCHEMA_ROOT / filename)
        assert isinstance(schema, dict)
        validator = Draft202012Validator(schema)
        if isinstance(value, tuple):
            for row in value:
                yield from validator.iter_errors(row)
        else:
            yield from validator.iter_errors(value)


def _contract_error(case_root: Path) -> str | None:
    try:
        manifest = PackManifestV1.model_validate(_load_json(case_root / "manifest.json"))
        documents = tuple(
            DocumentV1.model_validate(row) for row in _load_jsonl(case_root / "documents.jsonl")
        )
        evidence = tuple(
            EvidenceV1.model_validate(row) for row in _load_jsonl(case_root / "evidence.jsonl")
        )
        validate_record_set(manifest, documents, evidence)
    except ValueError as error:
        return str(error)
    return None


def _case_roots() -> tuple[Path, ...]:
    return tuple(sorted(path for path in FIXTURE_ROOT.glob("*/*") if path.is_dir()))


def test_fixture_cases_declare_and_meet_independent_schema_and_contract_statuses() -> None:
    cases = _case_roots()
    assert {case.relative_to(FIXTURE_ROOT).as_posix() for case in cases} == {
        "invalid/content-root-mismatch",
        "invalid/duplicate-source",
        "invalid/invalid-commit",
        "invalid/invalid-locator-range",
        "invalid/missing-document-reference",
        "invalid/missing-source-reference",
        "invalid/non-nfc-title",
        "invalid/noncanonical-files",
        "invalid/unknown-field",
        "invalid/unsafe-path",
        "valid/minimal",
        "valid/unicode-citation",
    }
    for case in cases:
        expectation = load_expectation(case / "expectation.json")
        schema_status = "invalid" if tuple(_schema_errors(case)) else "valid"
        contract_error = _contract_error(case)
        contract_status = "invalid" if contract_error else "valid"
        assert schema_status == expectation.schema_status, case
        assert contract_status == expectation.contract_status, case
        if expectation.contract_error_code is None:
            assert contract_error is None, case
        else:
            assert (
                contract_error is not None and expectation.contract_error_code in contract_error
            ), case


def test_canonical_vectors_bind_bytes_digests_and_recursive_values() -> None:
    raw = _load_json(VECTOR_PATH)
    assert isinstance(raw, dict)
    cases = raw["cases"]
    assert isinstance(cases, list)
    names = {case["name"] for case in cases if isinstance(case, dict)}
    assert {"nested-objects", "ordered-array"}.issubset(names)
    for case in cases:
        assert isinstance(case, dict)
        value = cast(JsonValue, case["value"])
        if "error_code" in case:
            with pytest.raises(PocketContractError, match=case["error_code"]):
                canonical_json_bytes(value)
            continue
        raw_bytes = canonical_json_bytes(value)
        assert raw_bytes.decode("utf-8") == case["canonical_text"]
        assert hashlib.sha256(raw_bytes).hexdigest() == case["sha256"]


def test_duplicate_source_fixture_isolates_the_source_id_invariant() -> None:
    raw = _load_json(FIXTURE_ROOT / "invalid/duplicate-source/manifest.json")
    assert isinstance(raw, dict)
    sources = raw["sources"]
    assert isinstance(sources, list)
    source_ids = [source["source_id"] for source in sources]
    source_revisions = [(source["repository_slug"], source["source_commit"]) for source in sources]
    assert len(source_ids) != len(set(source_ids))
    assert len(source_revisions) == len(set(source_revisions))
