"""Behavior tests for static ``plumber.consumer.package/v1`` admission."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_plumber_consumer_package_v1_tck.py"


def test_tck_emits_static_unqualified_receipt_for_trama_and_brain() -> None:
    """Product package declarations remain static intent, never runtime evidence."""
    result = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["contract_id"] == "plumber.consumer.package/v1"
    assert receipt["receipt_kind"] == "deterministic-fixture-attestation"
    assert receipt["qualification_status"] == "static-only-unqualified"
    assert {entry["consumer_id"] for entry in receipt["entries"]} == {
        "matryca.brain",
        "matryca.trama",
    }
    assert all("runtime" not in entry for entry in receipt["entries"])
