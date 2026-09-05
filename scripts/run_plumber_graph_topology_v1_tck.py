#!/usr/bin/env python3
"""Validate canonical ``plumber.graph.topology/v1`` synthetic fixture bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CONTRACT_ROOT: Final[Path] = ROOT / "contracts" / "plumber.graph.topology" / "v1"
DEFAULT_MANIFEST: Final[Path] = CONTRACT_ROOT / "manifest.json"
CONTRACT_ID: Final[str] = "plumber.graph.topology/v1"
READ_CONTRACT_ID: Final[str] = "plumber.graph.read/v1"
CAPABILITY: Final[str] = "graph.topology.snapshot.complete"
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576
MAX_FIXTURES: Final[int] = 32
MAX_STRING_LENGTH: Final[int] = 128
ALLOWED_FIXTURE_ROOT: Final[PurePosixPath] = PurePosixPath("fixtures")
FORBIDDEN_RESULT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "content",
        "markdown",
        "path",
        "text",
        "title",
        "uri",
        "url",
        "host",
        "graph_root",
        "parser",
        "properties",
    }
)
Outcome = Literal["pass", "rejected", "unsupported"]


class Limits(BaseModel):
    """Bounded structural result envelope declared by one static participant."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    max_nodes: int = Field(ge=1, le=4096)
    max_edges: int = Field(ge=1, le=16384)


class Profile(BaseModel):
    """Content-free declaration of one synthetic topology participant."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    fixture_kind: Literal["profile"]
    contract_id: Literal["plumber.graph.topology/v1"]
    schema_version: Literal[1]
    profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    role: Literal["producer", "consumer"]
    capabilities: list[Literal["graph.topology.snapshot.complete"]] = Field(
        min_length=1, max_length=1
    )
    limits: Limits


class ReadSession(BaseModel):
    """Opaque binding to a Plumber graph-read v1 session; never host state."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    contract_id: Literal["plumber.graph.read/v1"]
    schema_version: Literal[1]
    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    state: Literal["active", "closed", "expired", "rejected"]


class TopologyRequest(BaseModel):
    """Content-free consumer request binding presented to a topology producer."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    session_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    graph_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)


class TopologyNode(BaseModel):
    """One anonymous structural node; parentage, not an edge, models containment."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    kind: Literal["page", "block"]
    parent_id: str | None = Field(default=None, min_length=1, max_length=MAX_STRING_LENGTH)
    ordinal: int = Field(ge=0)


class ReferenceEdge(BaseModel):
    """One non-containment structural relation between declared opaque nodes."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    source_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    target_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    kind: Literal["reference"]


class TopologyProvenance(BaseModel):
    """Non-host provenance binding topology to the exact graph-read source revision."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    kind: Literal["derived-structural"]
    source_contract_id: Literal["plumber.graph.read/v1"]
    source_schema_version: Literal[1]
    source_revision: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)


class TopologyResult(BaseModel):
    """Complete-only anonymous topology projection for one bound graph snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    topology_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    complete: bool
    nodes: list[TopologyNode] = Field(max_length=4096)
    edges: list[ReferenceEdge] = Field(max_length=16384)
    provenance: TopologyProvenance


class OperationFixture(BaseModel):
    """One static topology operation result declared by the canonical manifest."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fixture_kind: Literal["operation-result"]
    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    contract_id: Literal["plumber.graph.topology/v1"]
    schema_version: Literal[1]
    producer_profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    consumer_profile_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    session: ReadSession
    graph_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    source_revision: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    operation: Literal["graph.topology.snapshot.complete"]
    requested_capability: str | None = Field(
        default=None, min_length=1, max_length=MAX_STRING_LENGTH
    )
    request: TopologyRequest
    outcome: Outcome
    reason: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    result: dict[str, object]


class ManifestEntry(BaseModel):
    """Declared fixture outcome in the bounded public catalogue."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    fixture_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    expected_outcome: Outcome


class Manifest(BaseModel):
    """Canonical static topology contract fixture catalogue."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    contract_id: Literal["plumber.graph.topology/v1"]
    schema_version: Literal[1]
    status: Literal["proposed"]
    artifact_kind: Literal["static-contract-fixture-catalogue"]
    schema_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    producer_profile_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    consumer_profile_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    fixtures: list[ManifestEntry] = Field(min_length=1, max_length=MAX_FIXTURES)


class TckError(ValueError):
    """Raised when a static artifact fails canonical topology fixture admission."""


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
    if PurePosixPath(relative_path) != PurePosixPath("schema.json"):
        raise TckError("canonical schema path must be schema.json")
    raw = _load_json(contract_root / "schema.json")
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TckError("canonical schema is not valid JSON") from exc
    if not isinstance(schema, dict):
        raise TckError("canonical schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise TckError("canonical schema must declare JSON Schema draft 2020-12")
    definitions = schema.get("$defs")
    required = {"profile", "operationResult", "readSession", "topologyResult"}
    if not isinstance(definitions, dict) or required - definitions.keys():
        raise TckError("canonical schema is missing required definitions")
    for definition_name in ("profile", "operationResult"):
        definition = definitions[definition_name]
        contract_property = definition.get("properties", {}).get("contract_id")
        if not isinstance(contract_property, dict) or contract_property.get("const") != CONTRACT_ID:
            raise TckError("canonical schema contract id must match plumber.graph.topology/v1")
    read_contract = definitions["readSession"].get("properties", {}).get("contract_id")
    if not isinstance(read_contract, dict) or read_contract.get("const") != READ_CONTRACT_ID:
        raise TckError("canonical schema must bind plumber.graph.read/v1 sessions")
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
        validator.validate(json.loads(raw))
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


def _require_matching_profile_limits(producer: Profile, consumer: Profile) -> None:
    """Avoid implicit limit negotiation in this complete-only v1 artifact."""
    if producer.limits != consumer.limits:
        raise TckError("producer and consumer profile limits must match exactly")


def _reject_content_bearing_fields(value: object) -> None:
    """Keep fixtures restricted to anonymous structural metadata."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_RESULT_FIELDS:
                raise TckError(f"content-bearing field is forbidden: {key}")
            _reject_content_bearing_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_content_bearing_fields(nested)


def _require_empty_result(result: dict[str, object], fixture_id: str) -> None:
    if result:
        raise TckError(f"{fixture_id}: rejected or unsupported topology result must be empty")


def _require_bound_request(fixture: OperationFixture) -> None:
    if fixture.request.session_id != fixture.session.id:
        raise TckError("session binding rejected")
    if fixture.request.graph_id != fixture.graph_id:
        raise TckError("graph binding rejected")


def _validate_nodes(nodes: list[TopologyNode]) -> None:
    node_by_id: dict[str, TopologyNode] = {}
    children: dict[str | None, list[TopologyNode]] = defaultdict(list)
    for node in nodes:
        if node.id in node_by_id:
            raise TckError("topology nodes require unique ids")
        node_by_id[node.id] = node
    for node in nodes:
        if node.parent_id is not None and node.parent_id not in node_by_id:
            raise TckError("topology node parent is not a declared node")
        children[node.parent_id].append(node)
    for siblings in children.values():
        ordinals = sorted(node.ordinal for node in siblings)
        if ordinals != list(range(len(siblings))):
            raise TckError("topology sibling ordinals are not contiguous")

    expected: list[str] = []

    def visit(parent_id: str | None) -> None:
        for child in sorted(children[parent_id], key=lambda node: (node.ordinal, node.id)):
            expected.append(child.id)
            visit(child.id)

    visit(None)
    if len(expected) != len(nodes):
        raise TckError("topology parentage contains a cycle")
    if [node.id for node in nodes] != expected:
        raise TckError("topology nodes are not in canonical preorder")


def _validate_edges(edges: list[ReferenceEdge], nodes: list[TopologyNode]) -> None:
    node_ids = {node.id for node in nodes}
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (edge.kind, edge.source_id, edge.target_id)
        if key in seen:
            raise TckError("topology edges require unique relations")
        seen.add(key)
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            raise TckError("reference edge endpoint is not a declared node")
    if [(edge.kind, edge.source_id, edge.target_id) for edge in edges] != sorted(seen):
        raise TckError("topology edges are not in canonical order")


def _validate_complete_result(
    fixture: OperationFixture,
    *,
    producer: Profile,
    consumer: Profile,
) -> None:
    try:
        result = TopologyResult.model_validate(fixture.result)
    except ValidationError as exc:
        raise TckError("complete topology result validation failed") from exc
    if result.complete is not True:
        raise TckError("complete topology result must declare complete=true")
    if result.provenance.source_revision != fixture.source_revision:
        raise TckError("provenance source revision does not match session binding")
    if len(result.nodes) > producer.limits.max_nodes:
        raise TckError("topology node count exceeds declared profile bounds")
    if len(result.edges) > producer.limits.max_edges:
        raise TckError("topology edge count exceeds declared profile bounds")
    _validate_nodes(result.nodes)
    _validate_edges(result.edges, result.nodes)


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
        _require_bound_request(fixture)
        if fixture.session.state != "active":
            raise TckError(f"{entry.id}: passing fixture requires active session")
        if CAPABILITY not in producer.capabilities or CAPABILITY not in consumer.capabilities:
            raise TckError(f"{entry.id}: passing fixture requires supported capability")
        _validate_complete_result(fixture, producer=producer, consumer=consumer)
    elif fixture.outcome == "rejected":
        _require_empty_result(fixture.result, entry.id)
        if fixture.reason == "graph-binding-rejected":
            if (
                fixture.session.state != "active"
                or fixture.request.session_id != fixture.session.id
            ):
                raise TckError(f"{entry.id}: graph rejection requires an active session binding")
            if fixture.request.graph_id == fixture.graph_id:
                raise TckError(f"{entry.id}: graph rejection requires a foreign graph request")
        elif fixture.reason == "session-not-active":
            _require_bound_request(fixture)
            if fixture.session.state == "active":
                raise TckError(f"{entry.id}: inactive session rejection requires terminal session")
        elif fixture.reason in {"topology-incomplete", "topology-bounds-exceeded"}:
            _require_bound_request(fixture)
            if fixture.session.state != "active":
                raise TckError(f"{entry.id}: topology rejection requires active session")
        else:
            raise TckError(f"{entry.id}: rejected fixture has unknown stable reason")
    elif fixture.outcome == "unsupported":
        _require_empty_result(fixture.result, entry.id)
        _require_bound_request(fixture)
        requested = fixture.requested_capability
        if fixture.session.state != "active" or fixture.reason != "capability-unsupported":
            raise TckError(f"{entry.id}: unsupported fixture requires active capability request")
        if (
            requested is None
            or requested in producer.capabilities
            and requested in consumer.capabilities
        ):
            raise TckError(f"{entry.id}: unsupported capability is advertised")
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
    _require_matching_profile_limits(producer, consumer)
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
        "runner": "plumber-graph-topology-v1-tck",
        "receipt_kind": "deterministic-fixture-attestation",
        "scope": "canonical-plumber-graph-topology-v1-fixture-profile-binding",
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
            "Shadow cache use",
            "graph mutation or event delivery",
            "consumer runtime compatibility qualification",
        ],
    }


def run_tck(manifest_path: Path = DEFAULT_MANIFEST) -> str:
    """Return one deterministic content-free fixture-attestation receipt."""
    receipt = build_receipt(manifest_path)
    return json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the static topology fixture TCK without invoking a graph provider."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        print(run_tck(args.manifest), end="")
    except (OSError, TckError) as exc:
        print(f"plumber graph topology v1 TCK rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
