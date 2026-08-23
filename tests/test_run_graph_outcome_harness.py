"""Tests for the deterministic synthetic graph-outcome report runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.run_graph_outcome_harness import OutcomeHarnessError, build_report, run_harness

_REVISION = "b" * 40


def test_report_is_deterministic_and_keeps_the_expected_boundaries() -> None:
    first = run_harness(_REVISION)
    second = run_harness(_REVISION)
    report = json.loads(first)

    assert first == second
    assert report["status"] == "completed"
    assert report["checks"] == {
        "default_scenario_order": True,
        "strict_read_only_completed": True,
        "unauthorized_tool_rejected": True,
        "stale_mutation_vetoed": True,
        "default_reset_isolation": True,
        "policy_transition_reset_isolation": True,
    }
    assert [episode["scenario"] for episode in report["episodes"]] == [
        "strict-read-only-success",
        "unauthorized-tool-request",
        "stale-unverified-mutation",
    ]
    assert report["non_goals"]


def test_report_has_no_repository_paths_or_synthetic_fixture_content() -> None:
    report = run_harness(_REVISION)
    repository = str(Path(__file__).resolve().parents[1])

    assert repository not in report
    assert "canonical.md" not in report
    assert "synthetic graph outcome page" not in report
    assert "/private/" not in report


def test_runner_refuses_invalid_revision_and_existing_output(tmp_path: Path) -> None:
    with pytest.raises(OutcomeHarnessError, match="40-character"):
        build_report("not-a-revision")

    output = tmp_path / "report.json"
    output.write_text("preserve", encoding="utf-8")
    with pytest.raises(OutcomeHarnessError, match="overwrite"):
        run_harness(_REVISION, output_path=output)
    assert output.read_text(encoding="utf-8") == "preserve"


def test_runner_writes_a_new_explicit_output(tmp_path: Path) -> None:
    output = tmp_path / "report.json"

    serialized = run_harness(_REVISION, output_path=output)

    assert output.read_text(encoding="utf-8") == serialized
