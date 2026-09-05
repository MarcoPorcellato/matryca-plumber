"""Contract-boundary tests for canonical ``plumber.graph.read/v1`` artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts.run_plumber_graph_read_v1_tck import TckError, run_tck

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "plumber.graph.read" / "v1"


def test_schema_declares_optional_requested_capability_for_unsupported_result() -> None:
    """Consumers can distinguish an unsupported requested capability from its operation."""
    schema = json.loads((CONTRACT_ROOT / "schema.json").read_text(encoding="utf-8"))
    operation_properties = schema["$defs"]["operationResult"]["properties"]

    assert operation_properties.get("requested_capability") == {"$ref": "#/$defs/opaqueId"}


def test_tck_rejects_fixture_that_violates_canonical_opaque_id_schema(tmp_path: Path) -> None:
    """Fixture admission follows the checked-in JSON Schema, not only Python models."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    page_fixture = copied_contract / "fixtures" / "page-read-pass-v1.json"
    payload = json.loads(page_fixture.read_text(encoding="utf-8"))
    payload["result"]["page_id"] = "opaque id with spaces"
    page_fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TckError, match="fixture schema validation failed"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_page_metadata_outside_canonical_result_shape(tmp_path: Path) -> None:
    """A page result must contain only its opaque contract identifier."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    page_fixture = copied_contract / "fixtures" / "page-read-pass-v1.json"
    payload = json.loads(page_fixture.read_text(encoding="utf-8"))
    payload["result"]["unexpected"] = "value"
    page_fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TckError, match="fixture schema validation failed"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_schema_that_drifted_from_canonical_contract_id(tmp_path: Path) -> None:
    """Profile and operation fixtures cannot bind a schema for another contract."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    schema_path = copied_contract / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$defs"]["operationResult"]["properties"]["contract_id"]["const"] = "other.graph.read/v1"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(TckError, match="canonical schema contract id"):
        run_tck(copied_contract / "manifest.json")
