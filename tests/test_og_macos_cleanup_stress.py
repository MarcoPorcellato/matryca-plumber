"""Bounded native overflow stress for the experimental macOS process reader."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Any

from matryca_plumber.graph_gateway import consumer
from scripts.release_qualification import process


def run_stress(work: Path, *, iterations: int = 200) -> dict[str, Any]:
    """Run the two installed-TCK overflow snippets under one owned CPU load."""
    if sys.platform != "darwin" or platform.python_implementation() != "CPython":
        raise ValueError("native macOS CPython is required")
    if sys.version_info[:2] not in ((3, 12), (3, 13)) or not 1 <= iterations <= 200:
        raise ValueError("unsupported stress bounds")
    if work.is_symlink() or work.exists() or work.parent.is_symlink():
        raise ValueError("stress work root must be fresh")
    work.mkdir(mode=0o700)
    ready = work / "load-ready"
    environment = {"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"}
    load_code = (
        "import pathlib,sys,time;"
        "pathlib.Path(sys.argv[1]).write_bytes(b'r');"
        "deadline=time.monotonic()+90\n"
        "while time.monotonic()<deadline: pass\n"
    )
    load = process.start_process(
        [sys.executable, "-I", "-B", "-c", load_code, str(ready)],
        cwd=work,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        windows=False,
    )
    rows: list[dict[str, Any]] = []
    primary: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        startup_deadline = time.monotonic() + 3.0
        while not ready.exists() and time.monotonic() < startup_deadline:
            time.sleep(0.01)
        if not ready.is_file() or ready.read_bytes() != b"r":
            raise RuntimeError("CPU-load fixture did not start")
        deadline = time.monotonic() + 60.0
        controls = (
            ("stdout_overflow", "import os;os.write(1,b'x'*65536)", {"max_stdout_bytes": 32}),
            ("stderr_overflow", "import os;os.write(2,b'x'*4096)", {"max_stderr_bytes": 32}),
        )
        for reason, snippet, bounds in controls:
            for _ in range(iterations):
                if time.monotonic() >= deadline:
                    raise TimeoutError("bounded native stress deadline exceeded")
                try:
                    consumer._run_child(
                        (sys.executable, "-I", "-B", "-c", snippet),
                        cwd=work,
                        env=environment,
                        execution_timeout=3.0,
                        cleanup_budget=1.0,
                        **bounds,
                    )
                except consumer.ChildFailure as error:
                    row = {
                        "control": reason,
                        "reason": error.reason,
                        "cleanup_ok": error.cleanup_ok,
                        "events": list(error.cleanup_events),
                        "signal_observations": list(error.signal_observations),
                        "snapshot": error.cleanup_snapshot,
                    }
                    rows.append(row)
                    if error.reason != reason or not error.cleanup_ok or error.cleanup_events:
                        raise RuntimeError("native overflow cleanup was not verified") from error
                    snapshot = error.cleanup_snapshot
                    if (
                        snapshot is None
                        or snapshot["child_poll"] != "returncode_observed"
                        or snapshot["group_check"] != "absent_observed"
                        or snapshot["cleanup_gate"] is not True
                    ):
                        raise RuntimeError(
                            "native terminal observations were incomplete"
                        ) from error
                else:
                    raise RuntimeError("overflow control unexpectedly succeeded")
    except BaseException as error:
        primary = error
    finally:
        try:
            load.terminate(grace_seconds=0.1)
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            load.reap_and_dispose_handle(timeout=5.0)
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            load.close()
        except BaseException as error:
            cleanup_errors.append(error)
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "pass" if primary is None and not cleanup_errors else "failed",
        "evidence": "native macOS synthetic overflow controls under owned CPU load",
        "python_version": platform.python_version(),
        "consumer_sha256": hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest(),
        "owner_sha256": hashlib.sha256(Path(process.__file__).read_bytes()).hexdigest(),
        "iterations_per_control": iterations,
        "completed": len(rows),
        "cleanup_failures": sum(not row["cleanup_ok"] or bool(row["events"]) for row in rows),
        "observed_eperm_cases": sum(bool(row["signal_observations"]) for row in rows),
        "load_cleanup_verified": not cleanup_errors,
        "primary_error_type": None if primary is None else type(primary).__name__,
        "cleanup_error_types": [type(error).__name__ for error in cleanup_errors],
        "rows": rows,
    }
    return report


class StressBoundsTests(unittest.TestCase):
    def test_invalid_iteration_count_never_starts_a_child(self) -> None:
        with self.assertRaises(ValueError):
            run_stress(Path("/not-used"), iterations=201)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=200)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink() or args.output.parent.is_symlink():
        raise ValueError("stress report must be fresh")
    report = run_stress(args.work, iterations=args.iterations)
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(payload) > 524_288:
        raise ValueError("stress report exceeds its finite limit")
    with args.output.open("xb") as stream:
        stream.write(payload)
    print(
        json.dumps({key: value for key, value in report.items() if key != "rows"}, sort_keys=True)
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
