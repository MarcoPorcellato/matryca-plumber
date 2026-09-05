"""Contract-boundary tests for canonical ``plumber.graph.topology/v1`` artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from scripts.run_plumber_graph_topology_v1_tck import TckError, run_tck

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "contracts" / "plumber.graph.topology" / "v1"


def test_schema_declares_complete_topology_capability_and_read_session_binding() -> None:
    """Topology has one complete-only capability and binds only to graph-read sessions."""
    schema = json.loads((CONTRACT_ROOT / "schema.json").read_text(encoding="utf-8"))
    definitions = schema["$defs"]

    assert definitions["profile"]["properties"]["capabilities"]["items"] == {
        "const": "graph.topology.snapshot.complete"
    }
    assert definitions["operationResult"]["properties"]["outcome"] == {
        "enum": ["pass", "rejected", "unsupported"]
    }
    assert definitions["operationResult"]["properties"]["session"]["$ref"] == "#/$defs/readSession"
    assert definitions["readSession"]["properties"]["contract_id"] == {
        "const": "plumber.graph.read/v1"
    }


def test_tck_rejects_content_bearing_topology_node_metadata(tmp_path: Path) -> None:
    """A static topology fixture may not normalize titles, text, or paths as evidence."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["result"]["nodes"][0]["title"] = "private graph title"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="fixture schema validation failed"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_provenance_revision_that_is_not_bound_to_session(tmp_path: Path) -> None:
    """Topology provenance cannot claim a different source revision than its session."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["result"]["provenance"]["source_revision"] = "revision.foreign.v1"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="provenance source revision does not match session binding"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_noncanonical_node_order(tmp_path: Path) -> None:
    """A complete snapshot must be parent-before-child canonical preorder."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    nodes = fixture["result"]["nodes"]
    fixture["result"]["nodes"] = [nodes[1], nodes[0], *nodes[2:]]
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="topology nodes are not in canonical preorder"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_mismatched_participant_limits(tmp_path: Path) -> None:
    """v1 profiles are exact bounds, not an implicit minimum-limit negotiation."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    profile_path = copied_contract / "fixtures" / "consumer-profile-v1.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["limits"]["max_nodes"] = 1
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(TckError, match="producer and consumer profile limits must match exactly"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_unadmitted_error_outcome_before_result_admission(tmp_path: Path) -> None:
    """Schema must not leave a content-bearing error-result bypass in a static v1 artifact."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["outcome"] = "error"
    fixture["result"] = {"content": "private graph text"}
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="fixture schema validation failed"):
        run_tck(copied_contract / "manifest.json")
