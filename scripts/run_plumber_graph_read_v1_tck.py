#!/usr/bin/env python3
"""Validate canonical ``plumber.graph.read/v1`` synthetic fixture bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CONTRACT_ROOT: Final[Path] = ROOT / "contracts" / "plumber.graph.read" / "v1"
DEFAULT_MANIFEST: Final[Path] = CONTRACT_ROOT / "manifest.json"
CONTRACT_ID: Final[str] = "plumber.graph.read/v1"
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576
MAX_FIXTURES: Final[int] = 32
MAX_STRING_LENGTH: Final[int] = 128
ALLOWED_FIXTURE_ROOT: Final[PurePosixPath] = PurePosixPath("fixtures")
FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {"content", "markdown", "path", "text", "title"}
)
Capability = Literal["graph.identify", "page.read", "block.subtree.read.complete"]
Outcome = Literal["pass", "rejected", "unsupported", "error"]


class Profile(BaseModel):
    """Content-free declaration of one synthetic contract participant."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fixture_kind: Literal["profile"]
    contract_id: Literal["plumber.graph.read/v1"]
    schema_version: Literal[1]
    profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    role: Literal["producer", "consumer"]
    capabilities: tuple[Capability, ...] = Field(min_length=1, max_length=MAX_FIXTURES)


class Session(BaseModel):
    """Opaque lifecycle binding; it never carries host state or credentials."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    state: Literal["active", "closed", "rejected"]


class OperationFixture(BaseModel):
    """One content-free result fixture declared by the canonical manifest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fixture_kind: Literal["operation-result"]
    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    contract_id: Literal["plumber.graph.read/v1"]
    schema_version: Literal[1]
    producer_profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    consumer_profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    graph_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    session: Session
    source_revision: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    operation: Capability
    requested_capability: str | None = Field(
        default=None, min_length=1, max_length=MAX_STRING_LENGTH
    )
    outcome: Outcome
    reason: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    result: dict[str, object]


class ManifestEntry(BaseModel):
    """Declared fixture outcome in the bounded public catalogue."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    fixture_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    expected_outcome: Outcome


class Manifest(BaseModel):
    """Canonical static contract fixture catalogue."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_id: Literal["plumber.graph.read/v1"]
    schema_version: Literal[1]
    status: Literal["proposed"]
    artifact_kind: Literal["static-contract-fixture-catalogue"]
    schema_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    producer_profile_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    consumer_profile_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    fixtures: tuple[ManifestEntry, ...] = Field(min_length=1, max_length=MAX_FIXTURES)


class TckError(ValueError):
    """Raised when a static artifact fails canonical fixture admission."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> bytes:
    if not path.is_file():
        raise TckError(f"{path.name}: missing or not a file")
    raw = path.read_bytes()
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise TckError(f"{path.name}: exceeds bounded size limit")
    return raw


def _artifact_path(relative_path: str, *, contract_root: Path) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise TckError("artifact path must not be absolute or traverse")
    if not relative.parts or relative.parts[0] != ALLOWED_FIXTURE_ROOT.parts[0]:
        raise TckError("artifact path must be under fixtures")
    candidate = (contract_root / Path(*relative.parts)).resolve(strict=False)
    try:
        candidate.relative_to(contract_root.resolve())
    except ValueError as exc:
        raise TckError("artifact path escapes contract root") from exc
    return candidate


def _load_canonical_schema(
    relative_path: str, *, contract_root: Path
) -> tuple[bytes, Draft202012Validator]:
    relative = PurePosixPath(relative_path)
    if relative != PurePosixPath("schema.json"):
        raise TckError("canonical schema path must be schema.json")
    path = contract_root / Path(*relative.parts)
    if not path.is_file():
        raise TckError("canonical schema is missing or is not a file")
    raw = _load_json(path)
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TckError("canonical schema is not valid JSON") from exc
    if not isinstance(schema, dict):
        raise TckError("canonical schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise TckError("canonical schema must declare JSON Schema draft 2020-12")
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict) or {"profile", "operationResult"} - definitions.keys():
        raise TckError("canonical schema is missing required definitions")
    for definition_name in ("profile", "operationResult"):
        definition = definitions[definition_name]
        if not isinstance(definition, dict):
            raise TckError("canonical schema definition must be an object")
        contract_property = definition.get("properties", {}).get("contract_id")
        if not isinstance(contract_property, dict) or contract_property.get("const") != CONTRACT_ID:
            raise TckError("canonical schema contract id must match plumber.graph.read/v1")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise TckError("canonical schema is invalid") from exc
    return raw, Draft202012Validator(schema)


def _validate_schema_instance(
    raw: bytes,
    *,
    validator: Draft202012Validator,
    artifact_name: str,
) -> None:
    try:
        instance = json.loads(raw)
        validator.validate(instance)
    except (json.JSONDecodeError, JsonSchemaValidationError) as exc:
        raise TckError(f"{artifact_name}: fixture schema validation failed") from exc


def _load_manifest(manifest_path: Path) -> tuple[Manifest, bytes]:
    raw = _load_json(manifest_path)
    try:
        manifest = Manifest.model_validate_json(raw)
    except ValidationError as exc:
        raise TckError(f"manifest validation failed: {exc.error_count()} error(s)") from exc
    entry_ids = [entry.id for entry in manifest.fixtures]
    if len(entry_ids) != len(set(entry_ids)):
        raise TckError("manifest contains duplicate fixture id")
    return manifest, raw


def _load_profile(
    relative_path: str,
    *,
    contract_root: Path,
    expected_role: str,
    validator: Draft202012Validator,
) -> Profile:
    path = _artifact_path(relative_path, contract_root=contract_root)
    raw = _load_json(path)
    _validate_schema_instance(raw, validator=validator, artifact_name=path.name)
    try:
        profile = Profile.model_validate_json(raw)
    except ValidationError as exc:
        raise TckError(
            f"{path.name}: profile validation failed: {exc.error_count()} error(s)"
        ) from exc
    if profile.role != expected_role:
        raise TckError(f"{path.name}: expected {expected_role} profile")
    return profile


def _validate_ordered_nodes(result: dict[str, object]) -> None:
    _require_exact_result_keys(result, {"root_block_id", "complete", "ordered_nodes"}, "subtree")
    if result.get("complete") is not True:
        raise TckError("complete subtree result must declare complete=true")
    root_id = result.get("root_block_id")
    nodes = result.get("ordered_nodes")
    if not isinstance(root_id, str) or not root_id:
        raise TckError("complete subtree result requires root_block_id")
    if not isinstance(nodes, list) or not nodes:
        raise TckError("complete subtree result requires ordered_nodes")
    seen_ids: set[str] = set()
    expected_ordinals: dict[str | None, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise TckError("ordered subtree node must be an object")
        if set(node) != {"id", "parent_id", "ordinal"}:
            raise TckError("ordered subtree node contains unsupported field")
        node_id = node.get("id")
        parent_id = node.get("parent_id")
        ordinal = node.get("ordinal")
        if not isinstance(node_id, str) or not node_id or node_id in seen_ids:
            raise TckError("ordered subtree nodes require unique ids")
        if parent_id is not None and not isinstance(parent_id, str):
            raise TckError("ordered subtree parent_id must be an id or null")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
            raise TckError("ordered subtree ordinal must be a non-negative integer")
        if ordinal != expected_ordinals.get(parent_id, 0):
            raise TckError("ordered subtree ordinal sequence is not contiguous")
        expected_ordinals[parent_id] = ordinal + 1
        seen_ids.add(node_id)
    if root_id not in seen_ids:
        raise TckError("complete subtree root_block_id must be present")


def _require_exact_result_keys(
    result: dict[str, object], expected: set[str], result_name: str
) -> None:
    if set(result) != expected:
        raise TckError(f"{result_name} result contains unsupported field")


def _reject_content_bearing_fields(value: object) -> None:
    """Keep fixture outcomes limited to opaque identifiers and structural metadata."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_RESULT_FIELDS:
                raise TckError(f"content-bearing field is forbidden: {key}")
            _reject_content_bearing_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_content_bearing_fields(nested)


def _validate_fixture(
    fixture: OperationFixture,
    *,
    entry: ManifestEntry,
    producer: Profile,
    consumer: Profile,
) -> str:
    if fixture.id != entry.id:
        raise TckError(f"{entry.id}: fixture id mismatch")
    if fixture.producer_profile_id != producer.profile_id:
        raise TckError(f"{entry.id}: producer profile binding rejected")
    if fixture.consumer_profile_id != consumer.profile_id:
        raise TckError(f"{entry.id}: consumer profile binding rejected")
    if fixture.outcome != entry.expected_outcome:
        raise TckError(f"{entry.id}: declared expected_outcome does not match fixture outcome")
    _reject_content_bearing_fields(fixture.result)

    if fixture.outcome == "pass":
        if fixture.session.state != "active":
            raise TckError(f"{entry.id}: passing fixture requires active session")
        if (
            fixture.operation not in producer.capabilities
            or fixture.operation not in consumer.capabilities
        ):
            raise TckError(f"{entry.id}: passing fixture requires supported capability")
        if fixture.operation == "graph.identify":
            _require_exact_result_keys(fixture.result, {"graph_id"}, "graph identity")
            if fixture.result.get("graph_id") != fixture.graph_id:
                raise TckError(f"{entry.id}: graph identity result must match binding")
        elif fixture.operation == "page.read":
            _require_exact_result_keys(fixture.result, {"page_id"}, "page read")
            page_id = fixture.result.get("page_id")
            if not isinstance(page_id, str) or not page_id:
                raise TckError(f"{entry.id}: page read requires opaque page_id")
        else:
            _validate_ordered_nodes(fixture.result)
    elif fixture.outcome == "rejected":
        if fixture.reason == "graph-binding-rejected":
            _require_exact_result_keys(fixture.result, {"graph_id"}, "foreign graph")
            if fixture.result.get("graph_id") == fixture.graph_id:
                raise TckError(f"{entry.id}: foreign graph rejection requires foreign graph id")
        elif fixture.reason == "subtree-incomplete":
            _require_exact_result_keys(
                fixture.result,
                {"root_block_id", "complete", "ordered_nodes"},
                "incomplete subtree",
            )
            if fixture.result.get("complete") is not False:
                raise TckError(f"{entry.id}: incomplete subtree rejection requires complete=false")
        else:
            raise TckError(f"{entry.id}: rejected fixture has unknown stable reason")
    elif fixture.outcome == "unsupported":
        requested = fixture.requested_capability
        if fixture.reason != "capability-unsupported" or requested is None:
            raise TckError(f"{entry.id}: unsupported fixture requires capability reason")
        if requested in producer.capabilities and requested in consumer.capabilities:
            raise TckError(f"{entry.id}: unsupported capability is advertised")
        _require_exact_result_keys(fixture.result, set(), "unsupported capability")
    else:
        raise TckError(f"{entry.id}: error fixtures are not admitted by this TCK")
    return fixture.reason


def build_receipt(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    """Validate static bindings and return a deterministic content-free receipt."""
    manifest, raw_manifest = _load_manifest(manifest_path)
    contract_root = manifest_path.resolve().parent
    raw_schema, validator = _load_canonical_schema(
        manifest.schema_path, contract_root=contract_root
    )
    producer = _load_profile(
        manifest.producer_profile_path,
        contract_root=contract_root,
        expected_role="producer",
        validator=validator,
    )
    consumer = _load_profile(
        manifest.consumer_profile_path,
        contract_root=contract_root,
        expected_role="consumer",
        validator=validator,
    )
    entries: list[dict[str, object]] = []
    for entry in manifest.fixtures:
        fixture_path = _artifact_path(entry.fixture_path, contract_root=contract_root)
        raw_fixture = _load_json(fixture_path)
        _validate_schema_instance(raw_fixture, validator=validator, artifact_name=entry.id)
        try:
            fixture = OperationFixture.model_validate_json(raw_fixture)
        except ValidationError as exc:
            raise TckError(
                f"{entry.id}: fixture validation failed: {exc.error_count()} error(s)"
            ) from exc
        reason = _validate_fixture(fixture, entry=entry, producer=producer, consumer=consumer)
        entries.append(
            {
                "id": entry.id,
                "fixture_sha256": hashlib.sha256(raw_fixture).hexdigest(),
                "expected_outcome": entry.expected_outcome,
                "actual_outcome": fixture.outcome,
                "reason": reason,
                "fixture_validation": "validated",
            }
        )
    return {
        "runner": "plumber-graph-read-v1-tck",
        "receipt_kind": "deterministic-fixture-attestation",
        "scope": "canonical-plumber-graph-read-v1-fixture-profile-binding",
        "contract_id": manifest.contract_id,
        "schema_version": manifest.schema_version,
        "status": manifest.status,
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "schema_sha256": hashlib.sha256(raw_schema).hexdigest(),
        "entries": entries,
        "non_goals": [
            "Logseq host execution",
            "Parser execution or public DTO reuse",
            "MCP or CLI transport",
            "Logseq DB support or fallback",
            "graph mutation or event delivery",
            "consumer runtime compatibility qualification",
        ],
    }


def run_tck(
    manifest_path: Path = DEFAULT_MANIFEST,
) -> str:
    """Return one deterministic content-free fixture-attestation receipt."""
    receipt = build_receipt(manifest_path)
    return json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the static fixture TCK from a shell without invoking a graph provider."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        print(run_tck(args.manifest), end="")
    except (OSError, TckError) as exc:
        print(f"plumber graph read v1 TCK rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
