#!/usr/bin/env python3
"""Emit a deterministic, content-free report from the synthetic outcome harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Final

from src.memory.graph_outcome_harness import (
    DefaultHarnessRun,
    EpisodeRun,
    ResetIsolationProof,
    run_default_scenarios,
    run_policy_transition_reset_proof,
)
from src.memory.graph_outcome_protocol import GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION

_SOURCE_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REPORT_SCHEMA_VERSION: Final[str] = "matryca-graph-outcome-synthetic-report.v1"


class OutcomeHarnessError(ValueError):
    """Raised when an operator request cannot produce a bounded report."""


def _receipt_sha256(run: EpisodeRun) -> str:
    return hashlib.sha256(run.receipt_bytes).hexdigest()


def _episode_summary(run: EpisodeRun) -> dict[str, object]:
    return {
        "scenario": run.scenario,
        "task_bundle_digest": run.task.task_bundle_id,
        "report_id": run.report.report_id,
        "status": run.report.status,
        "validation": "passed" if run.validation_succeeded else "rejected",
        "validation_error": run.validation_error,
        "receipt_sha256": _receipt_sha256(run),
        "dimensions": [item.model_dump(mode="json") for item in run.report.dimensions],
        "metrics": run.report.metrics.model_dump(mode="json"),
        "executed_tool_ids": list(run.executed_tool_ids),
        "failure_codes": list(run.failure_codes),
        "roots_distinct": run.roots_distinct,
        "roots_outside_repository": run.roots_outside_repository,
        "cleanup_verified": run.cleanup_verified,
    }


def _reset_summary(proof: ResetIsolationProof) -> dict[str, object]:
    return {
        "first_receipt_sha256": _receipt_sha256(proof.first),
        "second_receipt_sha256": _receipt_sha256(proof.second),
        "distinct_episode_roots": proof.distinct_episode_roots,
        "no_content_leak": proof.no_content_leak,
        "cleanup_verified": proof.cleanup_verified,
    }


def build_report(source_revision: str) -> dict[str, object]:
    """Run the bounded synthetic suite and return content-free result metadata."""
    if not _SOURCE_REVISION.fullmatch(source_revision):
        raise OutcomeHarnessError("source_revision must be a lowercase 40-character SHA-1")

    default_run: DefaultHarnessRun = run_default_scenarios()
    policy_transition = run_policy_transition_reset_proof()
    episodes = [_episode_summary(run) for run in default_run.episodes]
    checks = {
        "default_scenario_order": [episode["scenario"] for episode in episodes]
        == [
            "strict-read-only-success",
            "unauthorized-tool-request",
            "stale-unverified-mutation",
        ],
        "strict_read_only_completed": episodes[0]["status"] == "completed"
        and episodes[0]["validation"] == "passed",
        "unauthorized_tool_rejected": episodes[1]["status"] == "abstained"
        and episodes[1]["validation"] == "rejected",
        "stale_mutation_vetoed": episodes[2]["status"] == "vetoed"
        and episodes[2]["validation"] == "passed",
        "default_reset_isolation": default_run.reset_isolation.no_content_leak
        and default_run.reset_isolation.cleanup_verified,
        "policy_transition_reset_isolation": policy_transition.no_content_leak
        and policy_transition.cleanup_verified,
    }
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "runner": "matryca-graph-outcome-synthetic-harness-v1",
        "receipt_kind": "deterministic-content-free-self-check",
        "source_revision": source_revision,
        "protocol_schema_version": GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
        "status": "completed" if all(checks.values()) else "rejected",
        "checks": checks,
        "episodes": episodes,
        "default_reset_isolation": _reset_summary(default_run.reset_isolation),
        "policy_transition_reset_isolation": _reset_summary(policy_transition),
        "non_goals": [
            "agent qualification",
            "real vault execution",
            "real Shadow database execution",
            "provider or model evaluation",
            "external-system interoperability qualification",
            "release qualification",
        ],
    }


def run_harness(source_revision: str, *, output_path: Path | None = None) -> str:
    """Serialize a report deterministically and write only to a new output file."""
    serialized = (
        json.dumps(
            build_report(source_revision),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    if output_path is not None:
        if output_path.exists():
            raise OutcomeHarnessError("refusing to overwrite existing output file")
        if not output_path.parent.is_dir():
            raise OutcomeHarnessError("output parent directory is missing")
        output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_harness(args.source_revision, output_path=args.output)
    except (OSError, OutcomeHarnessError) as exc:
        print(f"graph-outcome synthetic harness rejected: {exc}", file=sys.stderr)
        return 2
    if args.output is None:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
