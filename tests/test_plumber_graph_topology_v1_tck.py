"""Behavior tests for canonical ``plumber.graph.topology/v1`` static TCK."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.run_plumber_graph_topology_v1_tck import TckError, run_tck

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_plumber_graph_topology_v1_tck.py"
CONTRACT_ROOT = ROOT / "contracts" / "plumber.graph.topology" / "v1"


def test_tck_emits_content_free_receipt_for_complete_topology_fixture_set() -> None:
    """Canonical static topology fixtures admit without opening a graph provider."""
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["contract_id"] == "plumber.graph.topology/v1"
    assert receipt["receipt_kind"] == "deterministic-fixture-attestation"
    assert receipt["status"] == "proposed"
    assert {entry["id"] for entry in receipt["entries"]} == {
        "topology-complete-pass-v1",
        "foreign-graph-rejected-v1",
        "closed-session-rejected-v1",
        "incomplete-topology-rejected-v1",
        "unsupported-capability-v1",
    }
    assert all("content" not in entry for entry in receipt["entries"])


def test_tck_rejects_reference_edge_with_unknown_endpoint(tmp_path: Path) -> None:
    """No topology edge may point outside the complete declared node set."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["result"]["edges"][0]["target_id"] = "node.unknown"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="reference edge endpoint is not a declared node"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_partial_topology_as_a_passing_result(tmp_path: Path) -> None:
    """v1 has no pagination, continuation, or partial successful topology response."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["result"]["complete"] = False
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="complete topology result must declare complete=true"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_topology_that_exceeds_negotiated_profile_bounds(tmp_path: Path) -> None:
    """A successful static result cannot silently exceed either participant's bounds."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    for profile_name in ("producer-profile-v1.json", "consumer-profile-v1.json"):
        profile_path = copied_contract / "fixtures" / profile_name
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["limits"]["max_nodes"] = 1
        profile_path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(TckError, match="topology node count exceeds declared profile bounds"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_noncanonical_reference_edge_order(tmp_path: Path) -> None:
    """Reference edges must have a deterministic canonical order."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    fixture_path = copied_contract / "fixtures" / "topology-complete-pass-v1.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    fixture["result"]["edges"].append(
        {"source_id": "page.beta", "target_id": "page.alpha", "kind": "reference"}
    )
    fixture["result"]["edges"].reverse()
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(TckError, match="topology edges are not in canonical order"):
        run_tck(copied_contract / "manifest.json")
