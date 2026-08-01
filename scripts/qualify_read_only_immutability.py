#!/usr/bin/env python3
"""Run the strict read-only E2E gate and emit deterministic JSON evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for the JSON evidence")
    return parser


def _run_gate() -> tuple[int, dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="matryca-read-only-gate-") as raw_tmp:
        evidence_path = Path(raw_tmp) / "evidence.json"
        env = os.environ.copy()
        env["MATRYCA_READ_ONLY_QUALIFICATION_EVIDENCE"] = str(evidence_path)
        completed = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-cov",
                "tests/test_read_only_immutability_e2e.py::test_read_only_immutability_qualification",
            ],
            check=False,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0 or not evidence_path.is_file():
            return completed.returncode or 1, {
                "schema_version": 1,
                "status": "FAIL",
                "reason": "qualification_test_failed",
            }
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("status") != "PASS":
            return 1, {
                "schema_version": 1,
                "status": "FAIL",
                "reason": "invalid_evidence",
            }
        return 0, payload


def main() -> int:
    args = _parser().parse_args()
    return_code, payload = _run_gate()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
