"""Regression tests for the staged GitHub Actions evidence contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_workflow() -> dict[str, Any]:
    loaded = yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _step_by_name(job: dict[str, Any], name: str) -> dict[str, Any]:
    steps = job.get("steps")
    assert isinstance(steps, list)
    step = next(item for item in steps if isinstance(item, dict) and item.get("name") == name)
    return cast(dict[str, Any], step)


def test_frontend_tests_remain_in_the_blocking_gate() -> None:
    workflow = _load_ci_workflow()
    gate = workflow["jobs"]["ironclad-gatekeeper"]
    assert "continue-on-error" not in gate

    frontend = _step_by_name(gate, "Build React cockpit")

    assert frontend["working-directory"] == "frontend"
    commands = str(frontend["run"]).splitlines()
    assert commands == ["npm ci", "npm run lint", "npm run test", "npm run build"]

    ci_gate = _step_by_name(gate, "Run CI gate (format check, Ruff, Mypy, Pytest)")
    assert ci_gate["run"] == "make ci"


def test_stacked_pull_requests_run_the_established_blocking_gates() -> None:
    workflow = _load_ci_workflow()
    triggers = workflow["on"]

    assert triggers["push"]["branches"] == ["main"]
    assert triggers["pull_request"] == {}

    jobs = workflow["jobs"]
    gate = jobs["ironclad-gatekeeper"]
    assert "if" not in gate
    assert gate["timeout-minutes"] == "20"

    dependency_review = jobs["dependency-review"]
    assert dependency_review["if"] == "github.event_name == 'pull_request'"
    assert dependency_review["timeout-minutes"] == "5"

    shadow = jobs["shadow-cross-platform"]
    assert "if" not in shadow
    assert shadow["timeout-minutes"] == "15"

    python_313 = jobs["python-313-evidence"]
    assert python_313["if"] == "github.event_name == 'push' || github.base_ref == 'main'"


def test_python_313_evidence_lane_is_bounded_and_non_blocking() -> None:
    workflow = _load_ci_workflow()
    job = workflow["jobs"]["python-313-evidence"]

    assert job["runs-on"] == "ubuntu-latest"
    assert job["continue-on-error"] == "true"
    assert job["timeout-minutes"] == "15"

    setup = _step_by_name(job, "Install uv and Python 3.13")
    assert setup["with"]["python-version"] == "3.13"

    sync = _step_by_name(job, "Sync locked Python dependencies")
    assert sync["run"] == "uv sync --locked --extra dev"

    test = _step_by_name(job, "Run full Python 3.13 test evidence")
    assert test["run"] == "uv run pytest -n auto -q -o addopts="
    assert all("upload-artifact" not in str(step.get("uses", "")) for step in job["steps"])

    rendered_steps = "\n".join(
        f"{step.get('name', '')}\n{step.get('run', '')}" for step in job["steps"]
    ).lower()
    for duplicated_work in ("node", "npm", "frontend", "docs", "ruff", "mypy", "make ci"):
        assert duplicated_work not in rendered_steps
