"""Offline regressions for the public RC installation qualification."""

import hashlib
import json
import os
import subprocess
import sys
from argparse import Namespace
from copy import deepcopy
from errno import ENOENT
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml


@pytest.mark.parametrize(
    ("target", "case", "builder", "historic"),
    [
        ("macos-arm64", "clean-wheel", False, False),
        ("macos-arm64", "from-alpha", False, True),
        ("linux-x86_64", "clean-sdist", False, False),
        ("linux-x86_64", "clean-wheel", True, False),
        ("linux-x86_64", "from-stable", False, False),
        ("linux-x86_64", "from-alpha", False, False),
        ("linux-aarch64", "clean-sdist", True, False),
        ("linux-x86_64", "clean-sdist", True, True),
    ],
)
def test_case_rejects_unadmitted_work(
    target: str, case: str, builder: bool, historic: bool
) -> None:
    from scripts.release_qualification.first_stable_s3 import select_case

    with pytest.raises(ValueError):
        select_case(
            target,
            case,
            Path("/builder") if builder else None,
            Path("/historic") if historic else None,
        )


@pytest.mark.parametrize(
    ("target", "case", "builder", "historic", "expected"),
    [
        ("linux-x86_64", "clean-wheel", False, False, ("wheel", None)),
        ("linux-x86_64", "clean-sdist", True, False, ("sdist", None)),
        ("macos-arm64", "clean-sdist", True, False, ("sdist", None)),
        ("linux-x86_64", "from-stable", False, True, ("wheel", "2.0.0")),
        ("linux-x86_64", "from-alpha", False, True, ("wheel", "2.1.0a4")),
    ],
)
def test_case_catalog(
    target: str, case: str, builder: bool, historic: bool, expected: tuple[str, str | None]
) -> None:
    from scripts.release_qualification.first_stable_s3 import select_case

    assert (
        select_case(
            target,
            case,
            Path("/builder") if builder else None,
            Path("/historic") if historic else None,
        )
        == expected
    )


def test_historical_lock_projects_only_native_hashed_closure() -> None:
    from scripts.release_qualification.first_stable_s3 import historical_dependencies

    signed_hash = "sha256:" + "c" * 64
    export = (
        f'Example_Name==1.2; sys_platform == "linux" --hash={signed_hash}\n'
        f'Example_Name==1.1; sys_platform == "darwin" --hash={signed_hash}\n'
    )
    assert historical_dependencies(export, "linux-x86_64") == {"example-name": "1.2"}


@pytest.mark.parametrize(
    "lines",
    [
        ["other>=1 --hash=HASH"],
        ["other @ https://example.invalid/a --hash=HASH"],
        ["other==1"],
        ["other==1 --hash=HASH", "Other==1 --hash=HASH"],
        ['other==1; platform_release == "custom" --hash=HASH'],
        ["matryca-plumber==1 --hash=HASH"],
        ['other==1; sys_platform == "win32" --hash=HASH'],
    ],
)
def test_historical_lock_rejects_unbound_missing_or_duplicate_entries(lines: list[str]) -> None:
    from scripts.release_qualification.first_stable_s3 import historical_dependencies

    with pytest.raises(ValueError):
        historical_dependencies(
            "\n".join(lines).replace("HASH", "sha256:" + "c" * 64), "linux-x86_64"
        )


def test_rollback_requires_exact_plumber_and_parser_record_restoration() -> None:
    from scripts.release_qualification.first_stable_s3 import require_restored_records

    before = ("a" * 64, "b" * 64)
    require_restored_records(before, before)
    for different in (("e" * 64, before[1]), (before[0], "e" * 64)):
        with pytest.raises(ValueError, match="RECORD"):
            require_restored_records(before, different)


def test_hosted_workflow_cannot_run_automatically_or_publish() -> None:
    definition = Path(__file__).resolve().parents[1] / ".github/workflows/s3-public-rc1.yml"
    workflow = yaml.load(definition.read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {}
    jobs = workflow["jobs"]
    assert {key: job["runs-on"] for key, job in jobs.items()} == {
        "linux": "ubuntu-24.04",
        "macos": "macos-15",
    }
    for job in jobs.values():
        assert job["permissions"] == {"contents": "read"}
        assert "environment" not in job
        for step in job["steps"]:
            action = step.get("uses")
            if action is not None:
                name, pin = action.split("@")
                assert name in {
                    "actions/checkout",
                    "actions/setup-python",
                    "actions/upload-artifact",
                }
                assert len(pin) == 40 and all(digit in "0123456789abcdef" for digit in pin)
            if action and action.startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"


@pytest.mark.parametrize("failure", ["safe-child", "unsafe-child", "os-error"])
def test_case_persists_filtered_public_fetch_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from scripts.release_qualification import first_stable_s3 as s3
    from scripts.release_qualification import sdist_build
    from scripts.release_qualification.first_stable_host import PINS

    root = tmp_path.resolve()
    uv = root / "uv"
    uv.write_bytes(b"installer")
    monkeypatch.setattr(
        os,
        "environ",
        {
            "RUNNER_TEMP": str(root),
            "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "10",
            "GITHUB_RUN_ATTEMPT": "1",
            "S3_UV_SHA256": hashlib.sha256(b"installer").hexdigest(),
        },
    )
    monkeypatch.setattr(os, "umask", lambda _mode: 0)
    monkeypatch.setattr(s3, "_disk", lambda _root: None)
    monkeypatch.setattr(
        s3,
        "_admit_host",
        lambda target, _runtime: {
            "archive_sha256": PINS[target, "3.12.16"].sha256,
            "implementation": "CPython",
            "platform": target,
            "version": "3.12.16",
            "executable_sha256": "b" * 64,
            "cleanup": "verified",
        },
    )
    monkeypatch.setattr(s3, "require_source", lambda *_args: None)
    calls = []

    def stopped(command: list[str], **_options: object) -> SimpleNamespace:
        if command == [str(uv), "--version"]:
            return SimpleNamespace(returncode=0, stdout=b"uv 0.12.19")
        calls.append(command)
        assert "alpha-public-fetch" in command
        if failure == "os-error":
            raise FileNotFoundError(ENOENT, "token=do-not-keep", "/private/host-path")
        child = _fetch_failure()
        if failure == "unsafe-child":
            child["message"] = "token=do-not-keep"
        return SimpleNamespace(returncode=1, stdout=json.dumps(child).encode())

    monkeypatch.setattr(sdist_build, "_run_bounded", stopped)
    reports = root / "reports"
    reports.mkdir()
    output = reports / "clean-wheel.json"
    with pytest.raises((ValueError, OSError)):
        s3.qualify(
            Namespace(
                target="linux-x86_64",
                case="clean-wheel",
                source=root / "producer",
                builder=None,
                baseline_source=None,
                uv=uv,
                runtime=root / "python",
                work=root / "work",
                output=output,
            )
        )
    row = json.loads(output.read_bytes())
    assert len(calls) == 1
    assert row["result"] == "FAIL"
    assert row["stage"] == "public-acquisition"
    expected_failure = (
        _fetch_failure()
        if failure == "safe-child"
        else {
            **_fetch_failure(),
            "cause_type": None,
            "http_status": None,
            "message": "Error details redacted.",
        }
    )
    if failure == "os-error":
        expected_failure.update(error_type="FileNotFoundError", errno=ENOENT)
    assert row["acquisition_diagnostic"] == {
        "step": "github-fetch",
        "asset": "binding.json",
        "returncode": None if failure == "os-error" else 1,
        "failure": expected_failure,
    }
    assert row["stages"] == {}
    assert b"do-not-keep" not in output.read_bytes()
    assert b"/private/host-path" not in output.read_bytes()
    s3.verify_reports(reports, "linux-x86_64", "failure", "a" * 40, 10)


def _fetch_failure() -> dict[str, object]:
    return {
        "schema_version": 1,
        "error_type": "ValueError",
        "cause_type": "HTTPError",
        "message": "Public redirect limit or HTTP failure.",
        "http_status": 403,
        "errno": None,
    }


@pytest.mark.skipif(os.name == "nt", reason="Hosted S3 report shell runs only on POSIX")
@pytest.mark.parametrize(
    ("outcome", "mutation", "allowed"),
    [
        ("success", None, True),
        ("success", "wrong-run", False),
        ("success", "unsafe-link", False),
        ("success", "case-failed", False),
        ("failure", "case-failed", True),
        ("success", "missing", False),
        ("success", "incomplete-evidence", False),
        ("success", "wrong-producer", False),
        ("success", "wrong-cleanup", False),
        ("success", "no-sdist-builder", False),
        ("success", "incomplete-builder-descriptor", False),
        ("success", "wrong-builder-python", False),
        ("success", "sensitive-field", False),
        ("failure", "acquisition-diagnostic", True),
        ("failure", "acquisition-unsafe-message", False),
        ("failure", "acquisition-wrong-asset", False),
        ("failure", "acquisition-wrong-stage", False),
        ("failure", "acquisition-wrong-code", False),
        ("success", "acquisition-spoofed-success", False),
    ],
)
def test_workflow_checks_real_report_before_upload(
    tmp_path: Path, outcome: str, mutation: str | None, allowed: bool
) -> None:
    definition = Path(__file__).resolve().parents[1] / ".github/workflows/s3-public-rc1.yml"
    workflow = yaml.load(definition.read_text(), Loader=yaml.BaseLoader)
    script = next(
        step["run"] for step in workflow["jobs"]["macos"]["steps"] if step.get("id") == "reports"
    )
    reports = tmp_path / "s3-reports"
    reports.mkdir()
    report = reports / "clean-sdist.json"
    sha = "a" * 40
    if mutation == "unsafe-link":
        outside = tmp_path / "outside.json"
        outside.write_text("{}", encoding="ascii")
        report.symlink_to(outside)
    elif mutation != "missing":
        from scripts.release_qualification.first_stable_s3 import _EXPORT, _FIXTURE_SHA
        from scripts.release_qualification.first_stable_s3_inputs import _RC_BINDING

        row = _example_sdist_report(sha, json.loads(_RC_BINDING.to_json()), _EXPORT, _FIXTURE_SHA)
        if mutation == "case-failed":
            row["result"] = "FAIL"
            row["stage"] = "locked-sdist-build"
            row["failure_class"] = "ValueError"
            del row["sdist_build"]
        if mutation == "wrong-run":
            row["run_id"] = 11
        if mutation == "incomplete-evidence":
            del row["installed_rc1"]
        if mutation == "wrong-producer":
            row["producer_commit"] = "c" * 40
        if mutation == "wrong-cleanup":
            row["runtime"]["cleanup"] = "uncertain"
        if mutation == "no-sdist-builder":
            del row["sdist_build"]
        if mutation == "incomplete-builder-descriptor":
            del row["sdist_build"]["descriptor"]["python_executable_sha256"]
        if mutation == "wrong-builder-python":
            row["sdist_build"]["provisioning"]["environment"]["python_executable_sha256"] = "a" * 64
        if mutation == "sensitive-field":
            row["stages"]["rc1"]["stderr"] = "/Users/fixture/secret"
        if mutation and mutation.startswith("acquisition-"):
            row["result"] = "FAIL"
            row["stage"] = "public-acquisition"
            row["failure_class"] = "ValueError"
            row["acquisition_diagnostic"] = {
                "step": "github-fetch",
                "asset": "binding.json",
                "returncode": 1,
                "failure": _fetch_failure(),
            }
            if mutation == "acquisition-unsafe-message":
                row["acquisition_diagnostic"]["failure"]["message"] = "token=do-not-keep"
            if mutation == "acquisition-wrong-asset":
                row["acquisition_diagnostic"]["asset"] = "arbitrary.txt"
            if mutation == "acquisition-wrong-stage":
                row["stage"] = "rc-export"
            if mutation == "acquisition-wrong-code":
                row["acquisition_diagnostic"]["returncode"] = True
            if mutation == "acquisition-spoofed-success":
                row["result"] = "PASS"
                row["stage"] = "final-integrity"
                del row["failure_class"]
        report.write_text(json.dumps(row), encoding="ascii")
    completed = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script],
        env={
            "PATH": os.defpath,
            "S3_TOOLS": sys.executable,
            "S3_ROOT": str(tmp_path),
            "TARGET": "macos-arm64",
            "GITHUB_SHA": sha,
            "GITHUB_RUN_ID": "10",
            "CASES_OUTCOME": outcome,
        },
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert (completed.returncode == 0) is allowed, completed.stderr


def _example_sdist_report(
    sha: str, binding: dict[str, Any], export: str, fixture: str
) -> dict[str, Any]:
    """Real schema-shaped synthetic input to the workflow's shell validator."""
    from scripts.release_qualification.alpha1_matrix import digest
    from scripts.release_qualification.first_stable_host import PINS
    from scripts.release_qualification.first_stable_s3 import (
        _BUILDER_LOCK,
        _BUILDER_PACKAGES,
        _BUILDER_RECIPE,
    )

    parser = "logseq-matryca-parser"
    packages = [{"name": parser, "version": "1.11.4"}]
    record = "b" * 64
    native = {
        "build_lock_sha256": _BUILDER_LOCK,
        "python_implementation": "CPython",
        "python_version": "3.12.16",
        "python_executable_sha256": "4" * 64,
        "uv_version": "0.12.19",
        "uv_sha256": "5" * 64,
        "target_os": "macos",
        "target_architecture": "arm64",
    }
    original = {
        "source_commit": binding["source_commit"],
        "source_tree": binding["source_tree"],
        "binding_sha256": digest(binding),
        "sdist_name": binding["sdist_name"],
        "sdist_size": binding["sdist_size"],
        "sdist_sha256": binding["sdist_sha256"],
        "provisioning_recipe_sha256": _BUILDER_RECIPE,
    }
    provisioning = {
        "instance": "current-macos-arm64-cpython-3.12.16-sdist",
        "run_id": "10",
        "run_attempt": 1,
        "operation": "uv-sync-locked-no-install-project",
        "environment": {**native, "packages": _BUILDER_PACKAGES},
    }
    descriptor = {
        **original,
        **native,
        "schema_version": 1,
        "packages": _BUILDER_PACKAGES,
        "packages_sha256": digest(_BUILDER_PACKAGES),
        "provisioning_evidence_sha256": digest(provisioning),
    }
    return {
        "schema_version": 1,
        "producer_commit": binding["source_commit"],
        "producer_tree": binding["source_tree"],
        "producer_tag": "v2.1.0-rc.1",
        "producer_tag_object": "959ad1ce70d956aa6085bc5d1e0acc9853621e8b",
        "producer_publication_run": 45996481639,
        "target": "macos-arm64",
        "case": "clean-sdist",
        "kind": "sdist",
        "result": "PASS",
        "stage": "final-integrity",
        "verifier_commit": sha,
        "run_id": 10,
        "run_attempt": 1,
        "runtime": {
            "archive_sha256": PINS["macos-arm64", "3.12.16"].sha256,
            "implementation": "CPython",
            "platform": "macos-arm64",
            "version": "3.12.16",
            "executable_sha256": "4" * 64,
            "cleanup": "verified",
        },
        "uv_sha256": "5" * 64,
        "operations": [
            {"name": name, "exit": 0, "cleanup": "verified", "stdout_sha256": None}
            for name in (
                "installer-version",
                "rc-export",
                "new-venv",
                "install-locked-closure",
                "install-exact-wheel",
                "rc1-dependency-check",
                "rc1-inventory",
                "rc1-nested-read",
            )
        ],
        "stages": {
            "rc1": {
                "version": "2.1.0rc1",
                "inventory": {"matryca-plumber": "2.1.0rc1", parser: "1.11.4"},
                "fixture_sha256": fixture,
                "plumber_record_sha256": record,
                "parser_record_sha256": "c" * 64,
            }
        },
        "binding": binding,
        "locked_export_sha256": export,
        "profile_sha256": "f" * 64,
        "sdist_build": {
            "provisioning": provisioning,
            "descriptor": descriptor,
            "receipt": {
                **original,
                **native,
                "schema_version": 2,
                "wheel_name": binding["wheel_name"],
                "wheel_sha256": "e" * 64,
                "wheel_size": 1,
                "backend": "setuptools.build_meta",
                "backend_version": "84.1.0",
                "static_requirement_records": [
                    {
                        "expression": "setuptools>=61",
                        "marker_applicable": True,
                        "satisfier": {"name": "setuptools", "version": "84.1.0"},
                    },
                    {
                        "expression": "wheel",
                        "marker_applicable": True,
                        "satisfier": {"name": "wheel", "version": "0.48.0"},
                    },
                ],
                "dynamic_requirement_records": [],
                "provisioned_packages": _BUILDER_PACKAGES,
                "before_hooks_packages": _BUILDER_PACKAGES,
                "after_hooks_packages": _BUILDER_PACKAGES,
                "after_build_packages": _BUILDER_PACKAGES,
                "environment_descriptor_sha256": digest(descriptor),
                "provisioning_evidence_sha256": digest(provisioning),
            },
        },
        "installed_rc1": {
            "schema_version": 1,
            "row_key": "current-macos-arm64-cpython-3.12.16-sdist",
            "candidate_tag": "v2.1.0-rc.1",
            "source_commit": binding["source_commit"],
            "source_tree": binding["source_tree"],
            "original_artifact": {
                "name": binding["sdist_name"],
                "size": binding["sdist_size"],
                "sha256": binding["sdist_sha256"],
            },
            "installed": {
                "kind": "sdist",
                "operating_system": "darwin",
                "architecture": "arm64",
                "version": "2.1.0rc1",
                "python_version": "3.12.16",
                "location_class": "isolated-venv-site-packages",
                "dependencies": packages,
                "dependency_sha256": hashlib.sha256(
                    json.dumps([[parser, "1.11.4"]], separators=(",", ":")).encode()
                ).hexdigest(),
                "record_sha256": record,
                "resource_sha256": "d" * 64,
                "tck_outcomes": ["PASS"] * 3,
            },
        },
    }


@pytest.mark.parametrize("mutation", [None, "missing", "record", "inventory"])
def test_transition_report_requires_actual_rollback(mutation: str | None) -> None:
    from scripts.release_qualification.first_stable_host import PINS
    from scripts.release_qualification.first_stable_s3 import (
        _EXPORT,
        _FIXTURE_SHA,
        _check_report,
    )
    from scripts.release_qualification.first_stable_s3_inputs import _RC_BINDING, BASELINES

    binding = json.loads(_RC_BINDING.to_json())
    sha = "a" * 40
    row = _example_sdist_report(sha, binding, _EXPORT, _FIXTURE_SHA)
    del row["sdist_build"]
    pin = BASELINES["2.0.0"]
    row.update(
        kind="wheel",
        case="from-stable",
        target="linux-x86_64",
        baseline_restored=True,
        baseline={
            "source_commit": pin.commit,
            "source_tree": pin.tree,
            "wheel_name": pin.wheel_name,
            "wheel_sha256": pin.wheel_sha256,
            "export_sha256": "9" * 64,
        },
    )
    row["runtime"].update(
        platform="linux-x86_64", archive_sha256=PINS["linux-x86_64", "3.12.16"].sha256
    )
    receipt = row["installed_rc1"]
    receipt["row_key"] = "current-linux-x86_64-cpython-3.12.16-wheel"
    receipt["original_artifact"] = {
        "name": binding["wheel_name"],
        "size": binding["wheel_size"],
        "sha256": binding["wheel_sha256"],
    }
    receipt["installed"].update(kind="wheel", operating_system="linux", architecture="x86_64")
    stage = {
        "version": "2.0.0",
        "inventory": {"matryca-plumber": "2.0.0", "logseq-matryca-parser": "1.7.1"},
        "fixture_sha256": _FIXTURE_SHA,
        "plumber_record_sha256": "b" * 64,
        "parser_record_sha256": "c" * 64,
    }
    row["stages"].update(baseline=stage, rollback=deepcopy(stage))
    row["operations"] = [
        {"name": name, "exit": 0, "cleanup": "verified", "stdout_sha256": None}
        for name in (
            "installer-version",
            "rc-export",
            "new-venv",
            "historical-export",
            "baseline-sync",
            "baseline-dependency-check",
            "baseline-inventory",
            "baseline-nested-read",
            "upgrade-sync",
            "rc1-dependency-check",
            "rc1-inventory",
            "rc1-nested-read",
            "rollback-sync",
            "rollback-dependency-check",
            "rollback-inventory",
            "rollback-nested-read",
        )
    ]
    if mutation is None:
        _check_report(row, "from-stable", "linux-x86_64", sha, 10, fail_allowed=False)
        return
    if mutation == "missing":
        del row["stages"]["rollback"]
    elif mutation == "record":
        row["stages"]["rollback"]["parser_record_sha256"] = "d" * 64
    else:
        row["stages"]["rollback"]["inventory"]["unused"] = "1.0"
    with pytest.raises(ValueError):
        _check_report(row, "from-stable", "linux-x86_64", sha, 10, fail_allowed=False)
