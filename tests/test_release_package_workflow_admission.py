"""Keep incomplete Stage A qualification unavailable for manual dispatch."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from scripts import qualify_release_package as release_cli

from tests.test_release_package_windows_installation import _binding, _expected_document

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


def test_cli_forwards_all_independent_windows_installation_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    class Receipt:
        def to_json(self) -> str:
            return '{"synthetic":true}'

    def verify(*args: object, **kwargs: object) -> Receipt:
        captured["args"] = args
        captured.update(kwargs)
        return Receipt()

    monkeypatch.setenv("EXPECTED_BINDING_JSON", _binding().to_json())
    monkeypatch.setattr(release_cli, "verify_installed", verify)
    args = [
        "verify-installed",
        "--python",
        str(tmp_path / "python.exe"),
        "--source-root",
        str(tmp_path),
        "--artifact",
        str(tmp_path / "original.whl"),
        "--kind",
        "wheel",
        "--windows-installation-descriptor",
        str(tmp_path / "descriptor.json"),
        "--expected-windows-installation-sha256",
        "a" * 64,
        "--windows-template",
        str(tmp_path / "template.exe"),
        "--installer",
        str(tmp_path / "uv.exe"),
    ]
    assert release_cli.main(args) == 0
    assert captured["windows_installation_descriptor"] == tmp_path / "descriptor.json"
    assert captured["expected_windows_installation_sha256"] == "a" * 64
    assert captured["windows_template"] == tmp_path / "template.exe"
    assert captured["installer"] == tmp_path / "uv.exe"
    assert captured["artifact"] == tmp_path / "original.whl"
    assert json.loads(capsys.readouterr().out) == {"synthetic": True}


def test_cli_rejects_forged_expected_file_before_aggregate_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "expected.json"
    path.write_bytes(json.dumps(_expected_document()).encode())
    monkeypatch.setattr(
        release_cli, "load_expected_build_environment_bindings", lambda _p: object()
    )
    monkeypatch.setattr(
        release_cli,
        "verify_receipts",
        lambda *_a, **_k: pytest.fail("unbound input reached aggregation"),
    )
    args = [
        "verify-receipts",
        "--receipt-dir",
        str(tmp_path),
        "--expected-commit",
        "a" * 40,
        "--expected-tree",
        "b" * 40,
        "--expected-binding",
        _binding().to_json(),
        "--expected-build-environments",
        str(tmp_path / "build.json"),
        "--expected-windows-installations",
        str(path),
        "--expected-windows-installations-sha256",
        "0" * 64,
        "--artifact-id",
        "1",
        "--artifact-digest",
        hashlib.sha256(b"artifact").hexdigest(),
        "--run-id",
        "2",
    ]
    with pytest.raises(SystemExit) as error:
        release_cli.main(args)
    assert error.value.code == 2
    assert "external authenticated digest" in capsys.readouterr().err


def test_cli_aggregate_has_no_implicit_windows_expectation_default() -> None:
    with pytest.raises(SystemExit) as error:
        release_cli._parser().parse_args(["verify-receipts", "--receipt-dir", "none"])
    assert error.value.code == 2
