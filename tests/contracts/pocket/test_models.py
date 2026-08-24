from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError
from src.contracts.pocket.models import (
    MAX_PATH_BYTES,
    MAX_RECORDS,
    DocumentV1,
    EvidenceV1,
    PackFileV1,
    PackManifestV1,
    SourceRevisionV1,
    payload_content_root,
    validate_record_set,
)

_A = "a" * 40
_B = "b" * 40
_DIGEST = "c" * 64


def _source(source_id: str = "knowledge") -> SourceRevisionV1:
    return SourceRevisionV1(
        source_id=source_id,
        repository_slug="Example/Knowledge",
        source_commit=_A,
    )


def _file(path: str = "payload/documents.jsonl") -> PackFileV1:
    return PackFileV1(
        path=path,
        media_type="application/x-ndjson",
        size_bytes=17,
        sha256=_DIGEST,
        record_count=1,
    )


def _valid_manifest_payload() -> dict[str, object]:
    files = (_file(),)
    return {
        "format_version": "matryca-pocket-pack.v1",
        "contract_version": "matryca-pocket-contract.v1",
        "pack_id": "01890f3e-7b2a-7cc3-98c4-dc0c0c07398f",
        "created_at": "2026-08-24T12:00:00Z",
        "generator_id": "matryca-knowledge",
        "generator_commit": _B,
        "signature_algorithm": "ed25519",
        "key_id": "alpha1-test-key",
        "sources": [_source().model_dump()],
        "files": [item.model_dump() for item in files],
        "content_root": payload_content_root(files),
    }


def _manifest() -> PackManifestV1:
    return PackManifestV1.model_validate(_valid_manifest_payload())


def _document(document_id: str = "doc-001") -> DocumentV1:
    return DocumentV1(
        document_id=document_id,
        source_id="knowledge",
        title="Documento sintetico",
        source_path="docs/example.md",
        media_type="text/markdown",
    )


def _evidence(evidence_id: str = "evidence-001") -> EvidenceV1:
    return EvidenceV1(
        evidence_id=evidence_id,
        document_id="doc-001",
        locator_kind="line_range",
        locator_start=10,
        locator_end=12,
        cited_text="Contenuto sintetico verificabile.",
    )


def test_record_set_accepts_complete_references() -> None:
    validate_record_set(_manifest(), (_document(),), (_evidence(),))


def test_record_set_rejects_missing_source_and_document_references() -> None:
    missing_source = DocumentV1.model_validate({**_document().model_dump(), "source_id": "missing"})
    with pytest.raises(ValueError, match="missing_source_reference"):
        validate_record_set(_manifest(), (missing_source,), ())

    missing_document = EvidenceV1.model_validate(
        {**_evidence().model_dump(), "document_id": "missing"}
    )
    with pytest.raises(ValueError, match="missing_document_reference"):
        validate_record_set(_manifest(), (_document(),), (missing_document,))


def test_evidence_rejects_reversed_locator_and_non_nfc_text() -> None:
    with pytest.raises(ValueError, match="invalid_locator_range"):
        EvidenceV1.model_validate(
            {**_evidence().model_dump(), "locator_start": 12, "locator_end": 10}
        )
    with pytest.raises(ValueError, match="non_nfc_string"):
        EvidenceV1.model_validate({**_evidence().model_dump(), "cited_text": "Citta\u0300"})


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("document_id", "UPPER", "invalid_document_id"),
        ("source_id", "UPPER", "invalid_source_id"),
        ("title", "Citta\u0300", "non_nfc_string"),
        ("media_type", "Text/markdown", "invalid_media_type"),
        ("source_path", "/docs/example.md", "unsafe_bundle_path"),
        ("source_path", "docs\\example.md", "unsafe_bundle_path"),
        ("source_path", "docs/line\nbreak.md", "unsafe_bundle_path"),
        ("source_path", "docs//example.md", "unsafe_bundle_path"),
        ("source_path", "docs/./example.md", "unsafe_bundle_path"),
        ("source_path", "docs/../example.md", "unsafe_bundle_path"),
        ("source_path", "docs/citta\u0300.md", "non_nfc_string"),
        ("source_path", f"docs/{'x' * MAX_PATH_BYTES}", "unsafe_bundle_path"),
    ],
)
def test_document_rejects_invalid_scalars_and_source_paths(
    field: str,
    value: str,
    code: str,
) -> None:
    payload = _document().model_dump()
    payload[field] = value
    with pytest.raises(ValueError, match=code):
        DocumentV1.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("evidence_id", "UPPER", "invalid_evidence_id"),
        ("document_id", "UPPER", "invalid_document_id"),
        ("locator_kind", "offset", "literal_error"),
        ("locator_start", 0, "greater_than_equal"),
        ("locator_end", MAX_RECORDS + 1, "less_than_equal"),
    ],
)
def test_evidence_rejects_invalid_scalars(
    field: str,
    value: str | int,
    code: str,
) -> None:
    payload = _evidence().model_dump()
    payload[field] = value
    with pytest.raises(ValueError, match=code):
        EvidenceV1.model_validate(payload)


def test_document_and_evidence_are_closed_and_frozen() -> None:
    document = _document()
    evidence = _evidence()
    with pytest.raises(ValueError, match="unexpected_fields"):
        DocumentV1.model_validate({**document.model_dump(), "secret": "forbidden"})
    with pytest.raises(ValueError, match="unexpected_fields"):
        EvidenceV1.model_validate({**evidence.model_dump(), "secret": "forbidden"})
    with pytest.raises(ValidationError, match="frozen"):
        document.title = "changed"
    with pytest.raises(ValidationError, match="frozen"):
        evidence.cited_text = "changed"


@pytest.mark.parametrize(
    ("documents", "evidence", "code"),
    [
        ((_document("doc-002"), _document("doc-001")), (), "noncanonical_order"),
        ((_document(), _document()), (), "duplicate_document_id"),
        (
            (_document(),),
            (_evidence("evidence-002"), _evidence("evidence-001")),
            "noncanonical_order",
        ),
        ((_document(),), (_evidence(), _evidence()), "duplicate_evidence_id"),
    ],
)
def test_record_set_rejects_noncanonical_or_duplicate_identifiers(
    documents: tuple[DocumentV1, ...],
    evidence: tuple[EvidenceV1, ...],
    code: str,
) -> None:
    with pytest.raises(ValueError, match=code):
        validate_record_set(_manifest(), documents, evidence)


@pytest.mark.parametrize("record_kind", ["documents", "evidence"])
def test_record_set_rejects_too_many_records(record_kind: str) -> None:
    documents = (_document(),) * (MAX_RECORDS + 1) if record_kind == "documents" else ()
    evidence = (_evidence(),) * (MAX_RECORDS + 1) if record_kind == "evidence" else ()
    with pytest.raises(ValueError, match="too_many_records"):
        validate_record_set(_manifest(), documents, evidence)


def test_manifest_is_closed_frozen_sorted_and_content_bound() -> None:
    files = (_file(),)
    manifest = PackManifestV1(
        format_version="matryca-pocket-pack.v1",
        contract_version="matryca-pocket-contract.v1",
        pack_id="01890f3e-7b2a-7cc3-98c4-dc0c0c07398f",
        created_at="2026-08-24T12:00:00Z",
        generator_id="matryca-knowledge",
        generator_commit=_B,
        signature_algorithm="ed25519",
        key_id="alpha1-test-key",
        sources=(_source(),),
        files=files,
        content_root=payload_content_root(files),
    )

    assert manifest.content_root == payload_content_root(files)
    with pytest.raises(ValueError, match="unexpected_fields"):
        PackManifestV1.model_validate({**manifest.model_dump(), "secret": "forbidden"})
    with pytest.raises(ValidationError, match="frozen"):
        manifest.key_id = "changed"


@pytest.mark.parametrize(
    ("validator", "payload"),
    [
        (SourceRevisionV1.model_validate, _source().model_dump()),
        (PackFileV1.model_validate, _file().model_dump()),
        (PackManifestV1.model_validate, _valid_manifest_payload()),
    ],
)
def test_closed_models_reject_unknown_fields(
    validator: Callable[[object], object],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="unexpected_fields"):
        validator({**payload, "secret": "forbidden"})


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("source_commit", "ABC", "invalid_source_commit"),
        ("repository_slug", "missing-slash", "invalid_repository_slug"),
        ("source_id", "UPPER", "invalid_source_id"),
        ("source_id", "citta\u0300", "non_nfc_string"),
    ],
)
def test_source_revision_rejects_invalid_scalars(
    field: str,
    value: str,
    code: str,
) -> None:
    payload = _source().model_dump()
    payload[field] = value
    with pytest.raises(ValueError, match=code):
        SourceRevisionV1.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("media_type", "Application/json", "invalid_media_type"),
        ("sha256", "C" * 64, "invalid_sha256"),
        ("path", "payload/citta\u0300.jsonl", "non_nfc_string"),
        ("size_bytes", -1, "greater_than_equal"),
        ("record_count", 1_000_001, "less_than_equal"),
    ],
)
def test_pack_file_rejects_invalid_scalars(
    field: str,
    value: str | int,
    code: str,
) -> None:
    payload = _file().model_dump()
    payload[field] = value
    with pytest.raises(ValueError, match=code):
        PackFileV1.model_validate(payload)


def test_manifest_rejects_unsafe_paths_noncanonical_order_and_bad_root() -> None:
    with pytest.raises(ValueError, match="unsafe_bundle_path"):
        _file("../secret")
    with pytest.raises(ValueError, match="noncanonical_order"):
        PackManifestV1.model_validate(
            {
                **_valid_manifest_payload(),
                "files": [_file("payload/z").model_dump(), _file("payload/a").model_dump()],
            }
        )
    with pytest.raises(ValueError, match="content_root_mismatch"):
        PackManifestV1.model_validate({**_valid_manifest_payload(), "content_root": "0" * 64})


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("/payload/documents.jsonl", "unsafe_bundle_path"),
        ("payload/./documents.jsonl", "unsafe_bundle_path"),
        ("payload/../documents.jsonl", "unsafe_bundle_path"),
        ("payload\\documents.jsonl", "unsafe_bundle_path"),
        ("payload/line\nbreak.jsonl", "unsafe_bundle_path"),
        ("manifest.json", "unsafe_bundle_path"),
    ],
)
def test_pack_file_rejects_unsafe_paths(path: str, code: str) -> None:
    with pytest.raises(ValueError, match=code):
        _file(path)


def test_manifest_rejects_duplicate_source_revision() -> None:
    duplicate = SourceRevisionV1(
        source_id="wiki",
        repository_slug="Example/Knowledge",
        source_commit=_A,
    )
    with pytest.raises(ValueError, match="duplicate_source_revision"):
        PackManifestV1.model_validate(
            {
                **_valid_manifest_payload(),
                "sources": [_source().model_dump(), duplicate.model_dump()],
            }
        )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("pack_id", "not-a-uuid", "invalid_pack_id"),
        ("pack_id", "01890f3e-7b2a-6cc3-98c4-dc0c0c07398f", "invalid_pack_id"),
        ("created_at", "2026-08-24T12:00:00+00:00", "invalid_created_at"),
        ("generator_id", "UPPER", "invalid_generator_id"),
        ("generator_commit", "B" * 40, "invalid_generator_commit"),
        ("key_id", "UPPER", "invalid_key_id"),
        ("content_root", "C" * 64, "invalid_content_root"),
    ],
)
def test_manifest_rejects_invalid_scalars(
    field: str,
    value: str,
    code: str,
) -> None:
    with pytest.raises(ValueError, match=code):
        PackManifestV1.model_validate({**_valid_manifest_payload(), field: value})


def test_manifest_rejects_duplicate_source_ids_and_file_paths() -> None:
    duplicate_source = SourceRevisionV1(
        source_id="knowledge",
        repository_slug="Example/Wiki",
        source_commit=_A,
    )
    duplicate_file = _file()
    with pytest.raises(ValueError, match="duplicate_source_id"):
        PackManifestV1.model_validate(
            {
                **_valid_manifest_payload(),
                "sources": [_source().model_dump(), duplicate_source.model_dump()],
            }
        )
    with pytest.raises(ValueError, match="duplicate_file_path"):
        PackManifestV1.model_validate(
            {
                **_valid_manifest_payload(),
                "files": [_file().model_dump(), duplicate_file.model_dump()],
            }
        )
