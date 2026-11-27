"""Ordinary workflow namespace, topology, and installer contract."""

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ordinary_matrix_uses_distinct_uploads_and_never_publishes() -> None:
    from scripts.release_qualification.first_stable_matrix import FIRST_STABLE_ROWS

    path = ROOT / ".github/workflows/package-qualification.yml"
    definition = cast(dict[str, Any], yaml.load(path.read_text(), Loader=yaml.BaseLoader))
    assert set(definition["on"]) == {"workflow_dispatch", "pull_request"}
    assert definition["permissions"] == {}
    jobs = definition["jobs"]
    actual: dict[str, str] = {}
    for name, job in jobs.items():
        if "ROW_KEY" not in job.get("env", {}):
            continue
        key = job["env"]["ROW_KEY"]
        assert key not in actual
        actual[key] = name
        assert job["name"] == f"Install first-stable ({key})"
        assert job["needs"] == ["admit", "build"]
        assert "strategy" not in job
        assert job["runs-on"] == ("macos-15" if "-macos-" in key else "ubuntu-24.04")
        assert job["outputs"] == {
            "row-key": "${{ steps.identity.outputs.row-key }}",
            "artifact-id": "${{ steps.upload.outputs.artifact-id }}",
            "artifact-sha256": "${{ steps.upload.outputs.artifact-digest }}",
        }
        assert not job.get("continue-on-error")
    assert set(actual) == {row.key for row in FIRST_STABLE_ROWS}
    assert set(jobs["aggregate"]["needs"]) == {"admit", "build", *actual.values()}
    assert jobs["linux-startup"]["runs-on"] == "ubuntu-24.04"
    assert jobs["linux-startup"]["needs"] == ["admit"]
    for job in jobs.values():
        assert set(job.get("permissions", {}).values()) <= {"read"}
        for step in job["steps"]:
            assert ("run" in step) != ("uses" in step)
            if "uses" in step:
                assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])
    assert not (ROOT / ".github/workflows/release-package-qualification.yml").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="Ordinary qualification uses POSIX shells.")
@pytest.mark.parametrize("need_builder", ["no", "yes"])
def test_row_shell_preserves_optional_builder_arguments(tmp_path: Path, need_builder: str) -> None:
    path = ROOT / ".github/workflows/package-qualification.yml"
    workflow = cast(dict[str, Any], yaml.load(path.read_text(), Loader=yaml.BaseLoader))
    steps = workflow["jobs"]["minimum-linux-312-wheel"]["steps"]
    (step,) = (step for step in steps if step.get("name") == "Install and verify exact row")
    assert step["shell"] == "bash"

    fake_python = tmp_path / "synthetic python"
    fake_python.write_text("#!/bin/sh\nprintf '%s\\000' \"$@\"\n", encoding="ascii")
    fake_python.chmod(0o700)
    task_root = tmp_path / "runner root with spaces *"
    output = tmp_path / "github-output"
    env = {
        "NEED_BUILDER": need_builder,
        "TASK_ROOT": str(task_root),
        "TOOLS_PYTHON": str(fake_python),
        "UV_BIN": "synthetic uv",
        "BASE_PYTHON": "synthetic runtime",
        "GITHUB_OUTPUT": str(output),
        "ROW_KEY": "synthetic-row",
    }
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stderr == b""
    expected = [
        "-B",
        "-m",
        "scripts.release_qualification.first_stable_job",
        "row",
        "--uv",
        "synthetic uv",
        "--runtime",
        "synthetic runtime",
        "--inputs",
        str(task_root / "first-stable-inputs"),
        "--work",
        str(task_root / "first-stable-row-work"),
        "--output",
        str(task_root / "first-stable-row-report"),
    ]
    if need_builder == "yes":
        expected.extend(["--builder", str(task_root / "first-stable-builder/bin/python")])
    assert result.stdout.decode().split("\0") == [*expected, ""]
    assert output.read_text(encoding="ascii") == "row-key=synthetic-row\n"


def test_locked_install_plan_has_separate_authenticated_local_candidate(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_job import install_commands

    uv, python, profile, wheel = [
        tmp_path / name for name in ("uv", "venv/bin/python", "requirements.txt", "bound.whl")
    ]
    dependencies, candidate = install_commands(uv, python, profile, wheel)
    assert dependencies[:3] == [str(uv), "pip", "install"]
    assert "--require-hashes" in dependencies
    assert "--no-deps" in dependencies
    assert dependencies[dependencies.index("--only-binary") + 1] == ":all:"
    assert dependencies[dependencies.index("--requirement") + 1] == str(profile)
    assert "--no-index" in candidate and "--offline" in candidate and "--no-deps" in candidate
    assert candidate[-1] == str(wheel)
    assert str(wheel) not in dependencies and str(profile) not in candidate


@pytest.mark.skipif(sys.platform == "win32", reason="Ordinary package builds use POSIX ownership.")
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("valid", "Reached canonical build"),
        ("missing", "Locked export must be a bounded regular file"),
        ("oversized", "Locked export must be a bounded regular file"),
        ("failed", "Locked runtime export failed"),
    ],
)
def test_noisy_locked_export_still_requires_valid_file_and_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, expected: str
) -> None:
    from scripts.release_qualification import first_stable_job, sdist_build

    uv = tmp_path / "uv"
    output = tmp_path / "build"
    requirements = f"pydantic==2.13.4 --hash=sha256:{'a' * 64}\n"
    run_bounded = sdist_build._run_bounded

    def run_fake_export(
        command: list[str], *, cwd: Path, timeout: float, capture: bool
    ) -> sdist_build._CommandResult:
        assert command[:2] == [str(uv), "export"]
        assert command[-2:] == ["--output-file", str(output / "runtime-lock.txt")]
        return run_bounded(
            [
                sys.executable,
                "-I",
                "-B",
                "-S",
                "-c",
                "from pathlib import Path\n"
                "import sys\n"
                "path, mode, requirements = sys.argv[1:]\n"
                "if mode != 'missing':\n"
                "    data = b'x' * 1_048_577 if mode == 'oversized' else requirements.encode()\n"
                "    Path(path).write_bytes(data)\n"
                "sys.stdout.buffer.write(b'x' * 65_537)\n"
                "raise SystemExit(7 if mode == 'failed' else 0)\n",
                command[-1],
                mode,
                requirements,
            ],
            cwd=cwd,
            timeout=timeout,
            capture=capture,
        )

    def stop_before_build(*_args: object, **_kwargs: object) -> None:
        assert (output / "runtime-lock.txt").read_bytes() == requirements.encode("ascii")
        raise ValueError("Reached canonical build")

    monkeypatch.setenv("SELECTED_SOURCE", "a" * 40)
    monkeypatch.setenv("CANDIDATE_TAG", "v2.1.0-rc.1")
    monkeypatch.setenv("SELECTED_VERSION", "2.1.0rc1")
    monkeypatch.setattr(sdist_build, "_run_bounded", run_fake_export)
    monkeypatch.setattr(first_stable_job, "build_alpha", stop_before_build)
    with pytest.raises(ValueError, match=expected):
        first_stable_job.build(tmp_path, uv, Path(sys.executable), output)


def test_admission_cannot_silently_select_alpha_or_skip_missing_material() -> None:
    from scripts.release_qualification.first_stable_job import require_ordinary_admission

    with pytest.raises(ValueError, match="first-stable package version"):
        require_ordinary_admission("v2.1.0-alpha.4", "2.1.0a4", None, "")
    with pytest.raises(ValueError, match="admission"):
        require_ordinary_admission("v2.1.0-rc.1", "2.1.0rc1", None, "a" * 64)


def test_admission_binds_all_four_distinct_runtime_archives() -> None:
    from scripts.release_qualification.first_stable_admission import require_ordinary_admission
    from scripts.release_qualification.first_stable_host import PINS

    rows = [
        {
            "platform": platform,
            "python": version,
            "archive_sha256": pin.sha256,
            "build_evidence_sha256": "a" * 64,
            "notices_sha256": "b" * 64,
        }
        for (platform, version), pin in PINS.items()
    ]
    good = json.dumps({"schema_version": 1, "runtime_inputs": rows}).encode()
    require_ordinary_admission("v2.1.0-rc.1", "2.1.0rc1", good, hashlib.sha256(good).hexdigest())
    rows[-1] = rows[0]
    bad = json.dumps({"schema_version": 1, "runtime_inputs": rows}).encode()
    with pytest.raises(ValueError, match="exact selected inputs"):
        require_ordinary_admission("v2.1.0-rc.1", "2.1.0rc1", bad, hashlib.sha256(bad).hexdigest())


def test_original_pair_upload_cannot_be_relabelled_as_current_attempt() -> None:
    from scripts.release_qualification.first_stable_aggregate import require_build_upload
    from scripts.release_qualification.first_stable_evidence import FirstStableRun

    expected = FirstStableRun(repository_id=123, run_id=456, attempt=2, source_commit="a" * 40)
    jobs = {
        "jobs": [
            {
                "name": "Build original first-stable artifacts",
                "status": "completed",
                "conclusion": "success",
                "head_sha": "a" * 40,
                "run_id": 456,
                "run_attempt": 2,
            }
        ]
    }
    artifacts = {
        "artifacts": [
            {
                "name": "first-stable-inputs-456-2",
                "id": 789,
                "digest": f"sha256:{'b' * 64}",
                "expired": False,
                "workflow_run": {
                    "id": 456,
                    "repository_id": 123,
                    "head_repository_id": 123,
                    "head_sha": "a" * 40,
                },
            }
        ]
    }
    outputs = {"artifact-id": "789", "artifact-sha256": "b" * 64}
    require_build_upload(expected, outputs, jobs, artifacts)
    jobs["jobs"][0]["run_attempt"] = 1
    with pytest.raises(ValueError, match="not bound"):
        require_build_upload(expected, outputs, jobs, artifacts)


@pytest.mark.skipif(sys.platform == "win32", reason="Ordinary startup uses POSIX ownership only.")
def test_native_owner_rejects_nonclean_startup(tmp_path: Path) -> None:
    from scripts.release_qualification.first_stable_host import _run_owned

    stdout, stderr = tmp_path / "stdout", tmp_path / "stderr"
    python = str(Path(sys.executable).resolve(strict=True))
    with pytest.raises(ValueError, match="not clean"):
        _run_owned(
            [python, "-I", "-B", "-S", "-c", "import sys; print('diagnostic', file=sys.stderr)"],
            tmp_path,
            stdout,
            stderr,
            10,
        )
    assert stdout.read_bytes() == b""
    assert stderr.read_bytes() == b"diagnostic\n"


@pytest.mark.parametrize("mutation", [None, "runtime", "attempt", "artifact", "installed"])
def test_aggregate_revalidates_installed_row_inputs(tmp_path: Path, mutation: str | None) -> None:
    from scripts.release_qualification.alpha1_matrix import digest
    from scripts.release_qualification.first_stable_aggregate import require_row_document
    from scripts.release_qualification.first_stable_evidence import FirstStableRun
    from scripts.release_qualification.first_stable_installed import write_installed_row
    from scripts.release_qualification.first_stable_profiles import resolve_profile

    from tests.test_release_package_first_stable_installed import _pair, _receipt

    binding = _pair()
    expected = FirstStableRun(repository_id=12, run_id=345, attempt=2, source_commit="a" * 40)
    tag = "v2.1.0-rc.1"
    row = "current-macos-arm64-cpython-3.13.18-wheel"
    export = f"pydantic==2.13.4 --hash=sha256:{'a' * 64}\n"
    profile = resolve_profile(export, "current", "macos-arm64", "3.13.18")
    installed_path = tmp_path / "receipt.json"
    write_installed_row(
        installed_path, row, tag, binding, dict(profile.packages), _receipt("wheel")
    )
    installed = json.loads(installed_path.read_bytes())
    report: dict[str, Any] = {
        "schema_version": 1,
        "run_id": 345,
        "attempt": 2,
        "binding_sha256": digest(asdict(binding)),
        "locked_export_sha256": hashlib.sha256(export.encode()).hexdigest(),
        "profile_sha256": hashlib.sha256(profile.requirements.encode()).hexdigest(),
        "runtime": {
            "implementation": "CPython",
            "platform": "macos-arm64",
            "version": "3.13.18",
            "cleanup": "verified",
            "executable_sha256": "3" * 64,
            "archive_sha256": "1afd3983237c2a10277345f235be730e9cb49a123e0574ed252dbf3a841a24e4",
        },
        "build": None,
        "installed": installed,
    }
    if mutation == "runtime":
        report["runtime"]["cleanup"] = "unknown"
    elif mutation == "attempt":
        report["attempt"] = 1
    elif mutation == "artifact":
        installed["original_artifact"]["sha256"] = "0" * 64
    elif mutation == "installed":
        installed["installed"]["dependencies"][0]["version"] = "1.9.0"
    if mutation is not None:
        with pytest.raises(ValueError):
            require_row_document(
                report,
                expected=expected,
                row_key=row,
                binding=binding,
                candidate_tag=tag,
                export=export,
                source=ROOT,
            )
    else:
        require_row_document(
            report,
            expected=expected,
            row_key=row,
            binding=binding,
            candidate_tag=tag,
            export=export,
            source=ROOT,
        )
