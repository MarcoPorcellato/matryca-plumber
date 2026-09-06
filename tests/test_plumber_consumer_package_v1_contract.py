"""Boundary tests for static ``plumber.consumer.package/v1`` artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts.run_plumber_consumer_package_v1_tck import TckError, run_tck

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "plumber.consumer.package" / "v1"


def test_schema_fixes_static_unqualified_product_profile_boundary() -> None:
    """Product declarations cannot be mistaken for a runtime capability claim."""
    schema = json.loads((CONTRACT_ROOT / "schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]

    assert properties["contract_id"] == {"const": "plumber.consumer.package/v1"}
    assert properties["qualification_status"] == {"const": "static-only-unqualified"}
    assert properties["consumer_id"]["enum"] == ["matryca.brain", "matryca.trama"]


def test_tck_rejects_profile_hash_drift(tmp_path: Path) -> None:
    """A package must pin the exact canonical consumer-profile bytes it names."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "matryca-trama-profile-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["bindings"][0]["canonical_consumer_profile_sha256"] = "0" * 64
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="consumer profile hash binding rejected"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_schema_hash_drift(tmp_path: Path) -> None:
    """A package must pin the exact canonical contract-schema bytes it names."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "matryca-brain-profile-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["bindings"][1]["schema_sha256"] = "0" * 64
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="schema hash binding rejected"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_package_that_drops_read_identity_binding(tmp_path: Path) -> None:
    """Topology intent cannot omit its graph-read session dependency."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "matryca-brain-profile-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["bindings"][0] = fixture["bindings"][1]
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="package contains duplicate contract binding"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_runtime_surface_field(tmp_path: Path) -> None:
    """Static packages contain no transport or consumer-wiring configuration."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "matryca-brain-profile-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["endpoint"] = "https://consumer.example.invalid"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="package schema validation failed"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_manifest_package_path_traversal(tmp_path: Path) -> None:
    """Package admission never follows a caller-controlled path outside fixtures."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    manifest_path = copied_contract / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packages"][0]["package_path"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(TckError, match="package path must not be absolute or traverse"):
        run_tck(manifest_path)
