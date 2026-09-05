"""Behavior tests for the canonical ``plumber.graph.read/v1`` fixture TCK."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.run_plumber_graph_read_v1_tck import TckError, run_tck

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_plumber_graph_read_v1_tck.py"
CONTRACT_ROOT = ROOT / "contracts" / "plumber.graph.read" / "v1"


def test_tck_emits_content_free_receipt_for_canonical_fixture_set() -> None:
    """A complete ordered-subtree fixture admits without serving graph content."""
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["contract_id"] == "plumber.graph.read/v1"
    assert receipt["receipt_kind"] == "deterministic-fixture-attestation"
    assert receipt["status"] == "proposed"
    assert {entry["id"] for entry in receipt["entries"]} == {
        "identify-pass-v1",
        "page-read-pass-v1",
        "ordered-subtree-pass-v1",
        "foreign-graph-rejected-v1",
        "incomplete-subtree-rejected-v1",
        "unsupported-capability-v1",
    }
    assert all("content" not in entry for entry in receipt["entries"])


def test_tck_rejects_a_fixture_catalogue_without_canonical_schema(tmp_path: Path) -> None:
    """A manifest cannot bind fixtures when its declared canonical schema is absent."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    (copied_contract / "schema.json").unlink()

    with pytest.raises(TckError, match="canonical schema is missing"):
        run_tck(copied_contract / "manifest.json")


def test_tck_rejects_content_bearing_page_fixture(tmp_path: Path) -> None:
    """Fixture TCK must not normalize or attest graph content as contract evidence."""
    copied_contract = tmp_path / "v1"
    shutil.copytree(CONTRACT_ROOT, copied_contract)
    page_fixture = copied_contract / "fixtures" / "page-read-pass-v1.json"
    payload = json.loads(page_fixture.read_text(encoding="utf-8"))
    payload["result"]["content"] = "private graph text"
    page_fixture.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TckError, match="fixture schema validation failed"):
        run_tck(copied_contract / "manifest.json")
