#!/usr/bin/env python3
"""Validate canonical ``plumber.consumer.package/v1`` static profile packages."""

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
CONTRACT_ROOT: Final[Path] = ROOT / "contracts" / "plumber.consumer.package" / "v1"
DEFAULT_MANIFEST: Final[Path] = CONTRACT_ROOT / "manifest.json"
CONTRACT_ID: Final[str] = "plumber.consumer.package/v1"
MAX_ARTIFACT_BYTES: Final[int] = 1_048_576
MAX_PACKAGES: Final[int] = 2
MAX_STRING_LENGTH: Final[int] = 128
FIXTURES_ROOT: Final[PurePosixPath] = PurePosixPath("fixtures")
QUALIFICATION_STATUS: Final[str] = "static-only-unqualified"
READ_CONTRACT_ID: Final[str] = "plumber.graph.read/v1"
TOPOLOGY_CONTRACT_ID: Final[str] = "plumber.graph.topology/v1"
READ_CAPABILITY: Final[str] = "graph.identify"
TOPOLOGY_CAPABILITY: Final[str] = "graph.topology.snapshot.complete"
CONSUMER_IDS: Final[frozenset[str]] = frozenset({"matryca.brain", "matryca.trama"})


class Limits(BaseModel):
    """Exact static topology bounds carried by an unqualified consumer package."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    max_nodes: Literal[1024]
    max_edges: Literal[4096]


class ContractBinding(BaseModel):
    """Immutable reference to one canonical Plumber contract fixture pair."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    contract_id: Literal["plumber.graph.read/v1", "plumber.graph.topology/v1"]
    schema_version: Literal[1]
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_consumer_profile_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    intended_capabilities: list[str] = Field(min_length=1, max_length=1)
    limits: Limits | None = None


class ConsumerPackage(BaseModel):
    """One product's static, non-operational contract intention declaration."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    fixture_kind: Literal["consumer-contract-profile"]
    contract_id: Literal["plumber.consumer.package/v1"]
    schema_version: Literal[1]
    package_id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    consumer_id: Literal["matryca.brain", "matryca.trama"]
    qualification_status: Literal["static-only-unqualified"]
    bindings: list[ContractBinding] = Field(min_length=2, max_length=2)


class ManifestEntry(BaseModel):
    """One declared package under the canonical static package catalogue."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    consumer_id: Literal["matryca.brain", "matryca.trama"]
    package_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)


class Manifest(BaseModel):
    """Static package catalogue; never a runtime discovery mechanism."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    contract_id: Literal["plumber.consumer.package/v1"]
    schema_version: Literal[1]
    status: Literal["proposed"]
    artifact_kind: Literal["static-consumer-package-catalogue"]
    schema_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    packages: list[ManifestEntry] = Field(min_length=2, max_length=MAX_PACKAGES)


class TckError(ValueError):
    """Raised when a static consumer package fails deterministic admission."""


def _load_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise TckError(f"{path.name}: missing or not a file")
    raw = path.read_bytes()
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise TckError(f"{path.name}: exceeds bounded size limit")
    return raw


def _load_json(path: Path) -> tuple[bytes, object]:
    raw = _load_bytes(path)
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TckError(f"{path.name}: invalid JSON") from exc


def _package_path(relative_path: str, *, contract_root: Path) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise TckError("package path must not be absolute or traverse")
    if not relative.parts or relative.parts[0] != FIXTURES_ROOT.parts[0]:
        raise TckError("package path must be under fixtures")
    candidate = contract_root.joinpath(*relative.parts).resolve(strict=False)
    try:
        candidate.relative_to(contract_root.resolve())
    except ValueError as exc:
        raise TckError("package path escapes contract root") from exc
    return candidate


def _load_schema(contract_root: Path, schema_path: str) -> Draft202012Validator:
    if PurePosixPath(schema_path) != PurePosixPath("schema.json"):
        raise TckError("canonical schema path must be schema.json")
    _, schema = _load_json(contract_root / "schema.json")
    if not isinstance(schema, dict):
        raise TckError("canonical schema must be an object")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise TckError("canonical schema must declare JSON Schema draft 2020-12")
    contract_id = schema.get("properties", {}).get("contract_id")
    if not isinstance(contract_id, dict) or contract_id.get("const") != CONTRACT_ID:
        raise TckError("canonical schema contract id must match plumber.consumer.package/v1")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise TckError("canonical schema is invalid") from exc
    return Draft202012Validator(schema)


def _load_manifest(manifest_path: Path) -> tuple[Manifest, bytes]:
    raw, _ = _load_json(manifest_path)
    try:
        manifest = Manifest.model_validate_json(raw)
    except ValidationError as exc:
        raise TckError(f"manifest validation failed: {exc.error_count()} error(s)") from exc
    consumer_ids = [entry.consumer_id for entry in manifest.packages]
    if len(consumer_ids) != len(set(consumer_ids)):
        raise TckError("manifest contains duplicate consumer id")
    if set(consumer_ids) != CONSUMER_IDS:
        raise TckError("manifest must declare exactly the canonical consumer ids")
    return manifest, raw


def _reference_paths(contract_id: str) -> tuple[Path, Path]:
    if contract_id == READ_CONTRACT_ID:
        root = ROOT / "contracts" / "plumber.graph.read" / "v1"
    elif contract_id == TOPOLOGY_CONTRACT_ID:
        root = ROOT / "contracts" / "plumber.graph.topology" / "v1"
    else:
        raise TckError("package binding has unknown contract")
    return root / "schema.json", root / "fixtures" / "consumer-profile-v1.json"


def _require_reference_binding(binding: ContractBinding) -> None:
    schema_path, profile_path = _reference_paths(binding.contract_id)
    actual_schema_hash = hashlib.sha256(_load_bytes(schema_path)).hexdigest()
    if binding.schema_sha256 != actual_schema_hash:
        raise TckError(f"{binding.contract_id}: schema hash binding rejected")
    profile_raw, profile = _load_json(profile_path)
    actual_profile_hash = hashlib.sha256(profile_raw).hexdigest()
    if binding.canonical_consumer_profile_sha256 != actual_profile_hash:
        raise TckError(f"{binding.contract_id}: consumer profile hash binding rejected")
    if not isinstance(profile, dict) or profile.get("role") != "consumer":
        raise TckError(f"{binding.contract_id}: canonical consumer profile is invalid")

    capabilities = binding.intended_capabilities
    if binding.contract_id == READ_CONTRACT_ID:
        if capabilities != [READ_CAPABILITY] or binding.limits is not None:
            raise TckError("read binding must declare graph.identify without topology limits")
    else:
        if capabilities != [TOPOLOGY_CAPABILITY] or binding.limits is None:
            raise TckError("topology binding must declare complete topology with exact limits")
        profile_limits = profile.get("limits")
        if not isinstance(profile_limits, dict) or profile_limits != binding.limits.model_dump():
            raise TckError("topology binding limits must match canonical consumer profile")


def _validate_package(
    package: ConsumerPackage,
    *,
    entry: ManifestEntry,
) -> None:
    if package.consumer_id != entry.consumer_id:
        raise TckError("package consumer id does not match manifest")
    if package.qualification_status != QUALIFICATION_STATUS:
        raise TckError("package must remain static-only-unqualified")
    if package.package_id != f"{package.consumer_id}.consumer.v1":
        raise TckError("package id must bind the declared consumer identity")
    bindings = {binding.contract_id: binding for binding in package.bindings}
    if len(bindings) != len(package.bindings):
        raise TckError("package contains duplicate contract binding")
    if set(bindings) != {READ_CONTRACT_ID, TOPOLOGY_CONTRACT_ID}:
        raise TckError("package must bind read identity and complete topology together")
    for binding in bindings.values():
        _require_reference_binding(binding)


def build_receipt(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    """Validate static packages and return one deterministic content-free receipt."""
    manifest, manifest_raw = _load_manifest(manifest_path)
    contract_root = manifest_path.resolve().parent
    validator = _load_schema(contract_root, manifest.schema_path)
    entries: list[dict[str, object]] = []
    package_ids: set[str] = set()
    for entry in manifest.packages:
        package_path = _package_path(entry.package_path, contract_root=contract_root)
        package_raw, package_json = _load_json(package_path)
        try:
            validator.validate(package_json)
        except JsonSchemaValidationError as exc:
            raise TckError(f"{entry.consumer_id}: package schema validation failed") from exc
        try:
            package = ConsumerPackage.model_validate_json(package_raw)
        except ValidationError as exc:
            raise TckError(f"{entry.consumer_id}: package validation failed") from exc
        if package.package_id in package_ids:
            raise TckError("catalogue contains duplicate package id")
        package_ids.add(package.package_id)
        _validate_package(package, entry=entry)
        entries.append(
            {
                "consumer_id": package.consumer_id,
                "package_id": package.package_id,
                "package_sha256": hashlib.sha256(package_raw).hexdigest(),
                "qualification_status": package.qualification_status,
            }
        )
    return {
        "runner": "plumber-consumer-package-v1-tck",
        "receipt_kind": "deterministic-fixture-attestation",
        "scope": "canonical-plumber-consumer-package-v1-static-profile-binding",
        "contract_id": manifest.contract_id,
        "schema_version": manifest.schema_version,
        "status": manifest.status,
        "qualification_status": QUALIFICATION_STATUS,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "entries": entries,
        "non_goals": [
            "consumer runtime compatibility qualification",
            "Parser import or execution",
            "Logseq source, DB, or Shadow access",
            "MCP, CLI, endpoint, or UI transport",
            "graph mutation or event delivery",
        ],
    }


def run_tck(manifest_path: Path = DEFAULT_MANIFEST) -> str:
    """Return one deterministic static package fixture-attestation receipt."""
    receipt = build_receipt(manifest_path)
    return json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run static package admission without invoking a provider or consumer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        print(run_tck(args.manifest), end="")
    except (OSError, TckError) as exc:
        print(f"plumber consumer package v1 TCK rejected: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
