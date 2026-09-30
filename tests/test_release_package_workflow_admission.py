"""Keep incomplete Stage A qualification unavailable for manual dispatch."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "windows-process-lifecycle.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_stage_a_workflow_is_not_deployable_while_windows_is_no_go() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "workflows"
        / "release-package-qualification.yml"
    )
    assert not workflow.exists(), "Stage A workflow must not be deployable while Windows is NO-GO"


def test_windows_process_lifecycle_workflow_is_pr_only_read_only_and_narrow() -> None:
    assert WORKFLOW.is_file(), "Native lifecycle regression workflow is missing"
    workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(workflow, dict)
    definition = cast(dict[str, Any], workflow)

    triggers = definition["on"]
    assert set(triggers) == {"pull_request"}
    assert triggers["pull_request"]["paths"] == [
        ".github/workflows/windows-process-lifecycle.yml",
        "pyproject.toml",
        "scripts/release_qualification/focused.py",
        "scripts/release_qualification/process.py",
        "tests/test_release_package_focused.py",
        "tests/test_release_package_workflow_admission.py",
        "tests/test_release_qualification_process.py",
        "uv.lock",
    ]
    assert definition["permissions"] == {"contents": "read"}

    jobs = definition["jobs"]
    assert set(jobs) == {"process-lifecycle"}
    job = jobs["process-lifecycle"]
    assert job["runs-on"] == "windows-latest"
    assert int(job["timeout-minutes"]) <= 10
    references = [step["uses"] for step in job["steps"] if "uses" in step]
    assert references == [
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv@bec219d24cd3e171d82865faccec33120bb574f4",
    ]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "uv sync --locked --extra dev" in commands
    assert (
        "tests/test_release_package_focused.py::test_windows_job_kills_descendant_that_closed_stdio"
        in commands
    )
    assert (
        "tests/test_release_package_focused.py::test_command_timeout_kills_descendants_then_allows_healthy_command"
        in commands
    )

    ci = yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(ci, dict)
    ci_jobs = cast(dict[str, Any], ci)["jobs"]
    assert "process-lifecycle" not in ci_jobs["ironclad-gatekeeper"]["needs"]
