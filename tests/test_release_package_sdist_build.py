from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import scripts.qualify_release_package as cli
import scripts.release_qualification.sdist_build as sdist_build
from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.sdist_build import (
    _parse_build_system,
    _verify_generated_wheel,
)


def _wheel(
    path: Path,
    *,
    name: str = "matryca_plumber-2.0.1rc4-py3-none-any.whl",
    version: str = "2.0.1rc4",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "matryca_plumber-2.0.1rc4.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: {version}\n\n",
        )
        archive.writestr(
            "matryca_plumber-2.0.1rc4.dist-info/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        )
    if path.name != name:
        renamed = path.with_name(name)
        path.rename(renamed)
        return renamed
    return path


def _package_set(*items: tuple[str, str]) -> dict[str, str]:
    return {name: version for name, version in items}


def test_windows_bounded_runner_uses_shared_gate_and_raw_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    class _Process:
        stdout = object()

        def wait(self, timeout: float) -> int:
            return 0

    class _Owned:
        process = _Process()

        def require_empty(self) -> None:
            return None

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            return 0

        def close(self) -> None:
            return None

    class _Reader:
        data = bytearray(b"synthetic output")
        errors: list[BaseException] = []
        overflowed = False

        def __init__(self, stream: object, *, limit: int) -> None:
            self.stream = stream
            self.thread = type("_Thread", (), {"ident": 1})()
            self.limit = limit

        def start(self) -> None:
            return None

        def wait_ready(self, _timeout: float) -> bool:
            return True

        def release(self) -> None:
            return None

        def wait(self, _timeout: float) -> bool:
            return True

        def cancel_and_join(self, *, deadline: float) -> None:
            return None

    def _start(command: list[str], **kwargs: object) -> _Owned:
        calls.append({"command": command, **kwargs})
        return _Owned()

    monkeypatch.setattr(sdist_build, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(process_module, "start_process", _start)
    monkeypatch.setattr(process_module, "WindowsPipeReader", _Reader)

    result = sdist_build._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=2, capture=True)

    assert result.returncode == 0
    assert result.stdout == b"synthetic output"
    assert calls[0]["windows"] is True
    assert calls[0]["windows_gate_code"] == process_module.WINDOWS_GATE_CODE
    assert calls[0]["bufsize"] == 0


def test_bounded_runner_rejects_nonfinite_deadline_before_process_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        process_module,
        "start_process",
        lambda *_args, **_kwargs: pytest.fail("invalid deadline started a process"),
    )
    with pytest.raises(ValueError, match="command parameters"):
        sdist_build._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=float("nan"))


def _requirement_records(
    requirements: tuple[str, ...],
    installed: dict[str, str],
    *,
    target_os: str = "linux",
    target_architecture: str = "x64",
    python_implementation: str = "CPython",
    python_version: str = "3.12.8",
) -> tuple[sdist_build.BuildRequirementRecord, ...]:
    return sdist_build._build_requirement_records(
        requirements,
        installed,
        label="dynamic PEP 517 build requirement",
        target_os=target_os,
        target_architecture=target_architecture,
        python_implementation=python_implementation,
        python_version=python_version,
    )


def test_build_system_requires_are_read_as_explicit_pep518_requirements() -> None:
    backend, requirements = _parse_build_system(
        b"[build-system]\nrequires=['setuptools>=61', 'wheel']\n"
        b"build-backend='setuptools.build_meta'\n"
    )

    assert backend == "setuptools.build_meta"
    assert requirements == ("setuptools>=61", "wheel")


def test_missing_or_unsupported_build_system_is_rejected() -> None:
    with pytest.raises(ValueError, match="build-system"):
        _parse_build_system(b"[project]\nname='matryca-plumber'\n")

    with pytest.raises(ValueError, match="backend"):
        _parse_build_system(
            b"[build-system]\nrequires=['setuptools>=61']\nbuild-backend='unknown.backend'\n"
        )

    with pytest.raises(ValueError, match="extras are not permitted"):
        _parse_build_system(
            b"[build-system]\nrequires=['setuptools[security]>=61']\n"
            b"build-backend='setuptools.build_meta'\n"
        )


def test_dynamic_pep517_requirement_must_be_satisfied_without_installing() -> None:
    actual = _package_set(("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    raw = (
        "wheel>=0.45",
        "platform-only>=2; sys_platform == 'win32'",
    )

    records = _requirement_records(raw, actual)

    assert records == (
        sdist_build.BuildRequirementRecord("wheel>=0.45", True, ("wheel", "0.46.1")),
        sdist_build.BuildRequirementRecord(raw[1], False, None),
    )


def test_dynamic_requirement_marker_environment_matches_target_platforms() -> None:
    cases = (
        ("linux", "x64", "linux", "x86_64", "posix"),
        ("macos", "arm64", "darwin", "arm64", "posix"),
        ("windows", "x64", "win32", "AMD64", "nt"),
    )
    for target, architecture, sys_platform, machine, os_name in cases:
        environment = sdist_build._marker_environment(target, architecture, "3.12.8")
        assert environment["sys_platform"] == sys_platform
        assert environment["platform_machine"] == machine
        assert environment["os_name"] == os_name
        assert environment["python_version"] == "3.12"
        assert environment["implementation_name"] == "cpython"


def test_dynamic_requirement_extras_are_rejected() -> None:
    with pytest.raises(ValueError, match="extras are not permitted"):
        _requirement_records(("wheel[speedups]>=0.45",), {"wheel": "0.46.1"})


def test_dynamic_requirement_rejects_unbound_platform_marker() -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _requirement_records(("wheel>=0.45; platform_release == 'test'",), {"wheel": "0.46.1"})


def test_dynamic_requirement_rejects_unbound_extra_marker() -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _requirement_records(("wheel>=0.45; extra == 'speedups'",), {"wheel": "0.46.1"})


@pytest.mark.parametrize("marker_name", ["extras", "dependency_groups"])
def test_dynamic_requirement_rejects_unbound_context_marker(marker_name: str) -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _requirement_records((f"wheel>=0.45; {marker_name} == 'speedups'",), {"wheel": "0.46.1"})


def test_dynamic_requirement_rejects_unknown_marker_context() -> None:
    with pytest.raises(ValueError, match="invalid"):
        _requirement_records(("wheel>=0.45; unknown_platform == 'value'",), {"wheel": "0.46.1"})


def test_python_identity_uses_isolated_venv_prefix_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = Path(sys.executable)
    current_prefix = Path(sys.prefix).resolve()
    current_base_prefix = Path(sys.base_prefix).resolve()
    current_version = ".".join(map(str, sys.version_info[:3]))
    is_supported_venv = sys.version_info[:2] == (3, 12) and current_prefix != current_base_prefix
    real_run_bounded = sdist_build._run_bounded
    observed_commands: list[list[str]] = []
    observed_results: list[sdist_build._CommandResult] = []

    def bounded_identity_probe(
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout: float = 900.0,
        capture: bool = False,
    ) -> sdist_build._CommandResult:
        observed_commands.append(command)
        result = real_run_bounded(command, cwd=cwd, timeout=min(timeout, 10.0), capture=capture)
        observed_results.append(result)
        return result

    monkeypatch.setattr(sdist_build, "_run_bounded", bounded_identity_probe)

    if is_supported_venv:
        resolved, implementation, version = sdist_build._python_identity(executable)
        assert resolved == executable.resolve(strict=True)
        assert implementation == "CPython"
        assert version == current_version
    else:
        # The helper qualifies only Python 3.12 venvs; CI's Python 3.13 runtime
        # and non-venv interpreters must remain fail-closed, not skipped.
        with pytest.raises(ValueError, match="supported interpreter in a provisioned environment"):
            sdist_build._python_identity(executable)

    assert len(observed_commands) == 1
    assert observed_commands[0][0] == str(executable)
    assert observed_commands[0][1] == "-I"
    assert "-S" not in observed_commands[0]
    assert len(observed_results) == 1
    identity = json.loads(observed_results[0].stdout)
    assert identity["implementation"] == "CPython"
    assert identity["version"] == current_version
    assert Path(identity["prefix"]).resolve() == current_prefix
    assert Path(identity["base_prefix"]).resolve() == current_base_prefix


def test_build_requirement_record_accepts_inapplicable_marker_without_satisfier() -> None:
    expression = "win-only>=2; sys_platform == 'win32'"

    records = _requirement_records((expression,), {"wheel": "0.46.1"})

    assert records == (sdist_build.BuildRequirementRecord(expression, False, None),)
    assert records[0].expression == expression
    assert records[0].satisfier is None


def test_build_requirement_record_rejects_forged_marker_or_satisfier() -> None:
    installed = {"setuptools": "80.9.0", "wheel": "0.46.1"}
    context = {
        "target_os": "linux",
        "target_architecture": "x64",
        "python_implementation": "CPython",
        "python_version": "3.12.8",
    }
    forged = sdist_build.BuildRequirementRecord("wheel>=0.45; sys_platform == 'linux'", False, None)
    with pytest.raises(ValueError, match="marker applicability is forged"):
        forged.validate(installed, **context)

    with pytest.raises(ValueError, match="name"):
        sdist_build.BuildRequirementRecord("wheel>=0.45", True, ("setuptools", "80.9.0"))
    with pytest.raises(ValueError, match="version does not satisfy"):
        sdist_build.BuildRequirementRecord("wheel>=0.45", True, ("wheel", "0.44"))
    with pytest.raises(ValueError, match="needs an exact observed satisfier"):
        sdist_build.BuildRequirementRecord("wheel>=0.45", True, None)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_contains_child_after_direct_parent_exits(tmp_path: Path) -> None:
    marker = tmp_path / "orphan-side-effect"
    child_code = (
        "import os,time\n"
        "from pathlib import Path\n"
        "pid = os.fork()\n"
        "if pid == 0:\n"
        "    time.sleep(0.4)\n"
        f"    Path({str(marker)!r}).write_text('escaped')\n"
        "    os._exit(0)\n"
        "os._exit(0)\n"
    )

    with pytest.raises(ValueError, match="left background descendants"):
        sdist_build._run_bounded([sys.executable, "-I", "-c", child_code], timeout=3)

    time.sleep(0.5)
    assert not marker.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_cleans_group_when_capture_waits_after_parent_exit(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "reader-timeout-side-effect"
    child_code = (
        "import os,time\n"
        "from pathlib import Path\n"
        "pid = os.fork()\n"
        "if pid == 0:\n"
        "    time.sleep(0.5)\n"
        f"    Path({str(marker)!r}).write_text('escaped')\n"
        "    os._exit(0)\n"
        "os._exit(0)\n"
    )

    with pytest.raises(ValueError, match="left background descendants"):
        sdist_build._run_bounded([sys.executable, "-I", "-c", child_code], timeout=3, capture=True)

    assert not marker.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_returns_zero_when_no_group_descendants_remain() -> None:
    result = sdist_build._run_bounded([sys.executable, "-I", "-c", "pass"], timeout=3)

    assert result.returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_accepts_fast_commands_in_a_new_session() -> None:
    for _ in range(25):
        result = sdist_build._run_bounded([sys.executable, "-I", "-c", "pass"], timeout=3)
        assert result.returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_reaps_timed_out_direct_child_while_draining_group() -> None:
    with pytest.raises(ValueError, match="exceeded its timeout"):
        sdist_build._run_bounded(
            [sys.executable, "-I", "-c", "import time; time.sleep(30)"], timeout=0.1
        )


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups are required")
def test_bounded_runner_kills_timed_out_child_that_ignores_sigterm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sdist_build, "_TERMINATE_SECONDS", 0.15)
    with pytest.raises(ValueError, match="exceeded its timeout"):
        sdist_build._run_bounded(
            [
                sys.executable,
                "-I",
                "-c",
                "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
            ],
            timeout=0.1,
        )


def test_backend_query_suppresses_bounded_hook_chatter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sdist_build,
        "_checked_output",
        lambda *_args, **_kwargs: (
            b'running egg_info\n{"backend":"setuptools.build_meta",'
            b'"version":"80.9.0","requirements":["wheel>=0.45"]}\n'
        ),
    )

    backend, version, requirements = sdist_build._query_backend(tmp_path / "python", tmp_path)

    assert (backend, version, requirements) == (
        "setuptools.build_meta",
        "80.9.0",
        ("wheel>=0.45",),
    )


def test_backend_query_sink_rejects_excessive_hook_chatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setuptools = ModuleType("setuptools")
    setuptools.__dict__["__version__"] = "80.9.0"
    setuptools.__path__ = []
    build_meta = ModuleType("setuptools.build_meta")

    def query(_config: dict[str, object]) -> list[str]:
        print("x" * (sdist_build._MAX_CAPTURE_BYTES + 1))
        return []

    build_meta.__dict__["get_requires_for_build_wheel"] = query
    setuptools.__dict__["build_meta"] = build_meta
    monkeypatch.setitem(sys.modules, "setuptools", setuptools)
    monkeypatch.setitem(sys.modules, "setuptools.build_meta", build_meta)

    with pytest.raises(RuntimeError, match="exceeded its limit"):
        exec(compile(sdist_build._BACKEND_QUERY, "<backend-query-test>", "exec"), {})


@pytest.mark.parametrize(
    "dynamic,actual",
    [
        (("missing-build-helper>=1",), {"setuptools": "80.9.0"}),
        (("not a requirement ???",), {"setuptools": "80.9.0"}),
        (("helper @ https://example.invalid/helper.whl",), {"helper": "1.0"}),
    ],
)
def test_dynamic_pep517_requirement_fails_closed_when_unverifiable(
    dynamic: tuple[str, ...], actual: dict[str, str]
) -> None:
    with pytest.raises(ValueError, match="dynamic PEP 517 build requirement"):
        _requirement_records(dynamic, actual)


def test_generated_wheel_is_bound_to_expected_name_identity_and_bytes(tmp_path: Path) -> None:
    path = _wheel(tmp_path / "out" / "matryca_plumber-2.0.1rc4-py3-none-any.whl")

    result = _verify_generated_wheel(
        path,
        "matryca_plumber-2.0.1rc4-py3-none-any.whl",
        "matryca-plumber",
        "2.0.1rc4",
    )

    assert result.name == "matryca_plumber-2.0.1rc4-py3-none-any.whl"
    assert result.size == path.stat().st_size
    assert result.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_generated_wheel_rejects_wrong_shape_or_project_identity(tmp_path: Path) -> None:
    wrong_name = _wheel(tmp_path / "wrong" / "matryca_plumber-2.0.1rc4-py3-none-any.whl")
    with pytest.raises(ValueError, match="filename"):
        _verify_generated_wheel(
            wrong_name,
            "matryca_plumber-2.0.1rc4-py3-none-win_amd64.whl",
            "matryca-plumber",
            "2.0.1rc4",
        )

    wrong_identity = tmp_path / "other" / "matryca_plumber-2.0.1rc4-py3-none-any.whl"
    wrong_identity.parent.mkdir()
    with zipfile.ZipFile(wrong_identity, "w") as archive:
        archive.writestr(
            "matryca_plumber-2.0.1rc4.dist-info/METADATA",
            "Metadata-Version: 2.4\nName: other-project\nVersion: 2.0.1rc4\n\n",
        )
        archive.writestr("matryca_plumber-2.0.1rc4.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    with pytest.raises(ValueError, match="identity"):
        _verify_generated_wheel(wrong_identity, wrong_identity.name, "matryca-plumber", "2.0.1rc4")


def test_generated_wheel_rejects_version_different_from_bundle(tmp_path: Path) -> None:
    path = _wheel(
        tmp_path / "wrong-version" / "matryca_plumber-2.0.1rc4-py3-none-any.whl",
        version="2.0.1rc3",
    )

    with pytest.raises(ValueError, match="identity"):
        _verify_generated_wheel(path, path.name, "matryca-plumber", expected_version="2.0.1rc4")


def _source_checkout(tmp_path: Path) -> tuple[Path, str, str, bytes]:
    root = tmp_path / "source"
    root.mkdir()
    build_system = (
        b"[build-system]\nrequires=['setuptools>=61', 'wheel']\n"
        b"build-backend='setuptools.build_meta'\n\n"
        b"[project]\nname='matryca-plumber'\nversion='2.0.1rc4'\n"
    )
    (root / "pyproject.toml").write_bytes(build_system)
    (root / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    locked_build = root / "release-qualification-build"
    locked_build.mkdir()
    (locked_build / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (locked_build / "provisioning-recipe.json").write_text(
        '{"schema_version":1,"project":"release-qualification-build"}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    return root, commit, tree, build_system


def _sdist(path: Path, pyproject: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = b"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: 2.0.1rc4\n\n"
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in {
            "pyproject.toml": pyproject,
            "PKG-INFO": metadata,
            "module.py": b"VALUE = 1\n",
        }.items():
            info = tarfile.TarInfo(f"matryca_plumber-2.0.1rc4/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


def _binding_for_sdist(source: Path, commit: str, tree: str, artifact: Path) -> BundleBinding:
    members, _contents, _directories = bundle_module._read_sdist(
        artifact, "matryca_plumber-2.0.1rc4"
    )
    size, digest = bundle_module._archive_sha256(artifact)
    return BundleBinding(
        source_commit=commit,
        source_tree=tree,
        version="2.0.1rc4",
        wheel_name="matryca_plumber-2.0.1rc4-py3-none-any.whl",
        wheel_size=1,
        wheel_sha256="0" * 64,
        sdist_name=artifact.name,
        sdist_size=size,
        sdist_sha256=digest,
        wheel_inventory_sha256="0" * 64,
        sdist_inventory_sha256=bundle_module._inventory_digest(members),
    )


def _build_environment_inputs(
    tmp_path: Path,
    source: Path,
    binding: BundleBinding,
    *,
    target_os: str = "linux",
    target_architecture: str = "x64",
) -> tuple[Path, Path, Path, str]:
    environment = tmp_path / "provisioned"
    python = environment / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"synthetic provisioned CPython executable")
    uv = tmp_path / "uv"
    uv.write_bytes(b"synthetic authenticated uv executable")

    packages = (("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    package_bytes = json.dumps(
        [{"name": name, "version": version} for name, version in packages],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    lock = source / "release-qualification-build" / "uv.lock"
    recipe = source / "release-qualification-build" / "provisioning-recipe.json"
    descriptor = {
        "schema_version": 1,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "binding_sha256": hashlib.sha256(binding.to_json().encode()).hexdigest(),
        "sdist_name": binding.sdist_name,
        "sdist_size": binding.sdist_size,
        "sdist_sha256": binding.sdist_sha256,
        "build_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "provisioning_recipe_sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
        "provisioning_evidence_sha256": "9" * 64,
        "uv_version": "0.12.16",
        "uv_sha256": hashlib.sha256(uv.read_bytes()).hexdigest(),
        "target_os": target_os,
        "target_architecture": target_architecture,
        "python_implementation": "CPython",
        "python_version": "3.12.13",
        "python_executable_sha256": hashlib.sha256(python.read_bytes()).hexdigest(),
        "packages": [{"name": name, "version": version} for name, version in packages],
        "packages_sha256": hashlib.sha256(package_bytes).hexdigest(),
    }
    descriptor_path = tmp_path / "build-environment.json"
    descriptor_bytes = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    descriptor_path.write_bytes(descriptor_bytes)
    return python, uv, descriptor_path, hashlib.sha256(descriptor_bytes).hexdigest()


def _fake_consume_only_commands(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dynamic: tuple[str, ...] = (),
    manifests: tuple[tuple[tuple[str, str], ...], ...] | None = None,
    tamper_sdist: Path | None = None,
) -> list[list[str]]:
    commands: list[list[str]] = []
    package_rows = manifests or (
        (("setuptools", "80.9.0"), ("wheel", "0.46.1")),
        (("setuptools", "80.9.0"), ("wheel", "0.46.1")),
        (("setuptools", "80.9.0"), ("wheel", "0.46.1")),
    )
    observation = 0

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout: float = 0,
        capture: bool = False,
    ) -> sdist_build._CommandResult:
        nonlocal observation
        commands.append(command)
        if command[0].endswith("/uv") and command[1:] == ["--version"]:
            return sdist_build._CommandResult(0, b"uv 0.12.16")
        if "-I" in command and "-c" in command and "platform.python_implementation" in command[-1]:
            return sdist_build._CommandResult(
                0,
                json.dumps(
                    {
                        "implementation": "CPython",
                        "version": "3.12.13",
                        "prefix": str(Path(command[0]).parent.parent),
                        "base_prefix": str(Path(command[0]).parent.parent.parent),
                    }
                ).encode(),
            )
        if len(command) > 3 and "setuptools.build_meta" in command[3]:
            return sdist_build._CommandResult(
                0,
                json.dumps(
                    {
                        "backend": "setuptools.build_meta",
                        "version": "80.9.0",
                        "requirements": list(dynamic),
                    }
                ).encode(),
            )
        if command[1:4] == ["pip", "list", "--format"]:
            selected = package_rows[min(observation, len(package_rows) - 1)]
            observation += 1
            return sdist_build._CommandResult(
                0,
                json.dumps(
                    [{"name": name, "version": version} for name, version in selected]
                ).encode(),
            )
        if command[1:3] == ["build", "--wheel"]:
            out_dir = Path(command[command.index("--out-dir") + 1])
            _wheel(out_dir / "matryca_plumber-2.0.1rc4-py3-none-any.whl")
            if tamper_sdist is not None:
                tamper_sdist.write_bytes(tamper_sdist.read_bytes() + b"changed")
            return sdist_build._CommandResult(0, b"")
        raise AssertionError(f"Unexpected synthetic command: {command!r}")

    monkeypatch.setattr(sdist_build, "_run_bounded", fake_run)
    monkeypatch.setattr(sdist_build, "_native_marker_target", lambda: ("linux", "x64"))
    return commands


def test_prepare_sdist_build_never_provisions_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_consume_only_commands(monkeypatch)

    receipt = sdist_build.prepare_sdist_build(
        artifact,
        binding,
        source,
        python,
        uv,
        hashlib.sha256(uv.read_bytes()).hexdigest(),
        output_dir,
        environment_descriptor=descriptor,
        expected_build_environment_sha256=descriptor_sha256,
    )

    assert (output_dir / binding.wheel_name).is_file()
    assert receipt.schema_version == 2
    assert receipt.build_lock_sha256
    assert receipt.environment_descriptor_sha256 == descriptor_sha256
    assert receipt.before_hooks_packages == receipt.after_hooks_packages
    assert receipt.after_hooks_packages == receipt.after_build_packages
    assert commands
    assert not any("venv" in command[1:] for command in commands)
    assert not any(command[1:3] == ["pip", "install"] for command in commands)
    assert not any("sync" in command for command in commands)
    assert not any(
        command[1:2] in (["lock"], ["resolve"], ["compile"], ["install"]) for command in commands
    )


def test_prepare_sdist_build_rejects_unbound_descriptor_before_backend_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_consume_only_commands(monkeypatch)
    backend_queries = 0

    def unexpected_backend_query(*_args: object, **_kwargs: object) -> None:
        nonlocal backend_queries
        backend_queries += 1

    monkeypatch.setattr(sdist_build, "_query_backend", unexpected_backend_query)

    with pytest.raises(ValueError, match="independent expected descriptor SHA-256"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256="0" * 64,
        )

    assert backend_queries == 0
    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_commit", "f" * 40),
        ("source_tree", "e" * 40),
        ("binding_sha256", "0" * 64),
        ("sdist_name", "matryca_plumber-2.0.1rc3.tar.gz"),
        ("sdist_size", "increment"),
        ("sdist_sha256", "0" * 64),
        ("build_lock_sha256", "0" * 64),
        ("provisioning_recipe_sha256", "0" * 64),
        ("target_os", "windows"),
        ("target_architecture", "arm64"),
        ("python_implementation", "PyPy"),
        ("python_version", "3.12.12"),
        ("python_executable_sha256", "0" * 64),
        ("uv_version", "0.12.15"),
        ("uv_sha256", "0" * 64),
    ],
)
def test_prepare_sdist_build_rejects_observed_identity_mismatch_before_backend_query(
    field: str,
    value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, _descriptor_sha256 = _build_environment_inputs(
        tmp_path, source, binding
    )
    document = json.loads(descriptor.read_bytes())
    if field == "target_architecture":
        document["target_os"] = "macos"
        document[field] = value
    else:
        document[field] = document[field] + 1 if value == "increment" else value
    descriptor_bytes = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    descriptor.write_bytes(descriptor_bytes)
    descriptor_sha256 = hashlib.sha256(descriptor_bytes).hexdigest()
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_consume_only_commands(monkeypatch)

    with pytest.raises(ValueError):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert not any("setuptools.build_meta" in command for command in commands)
    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


@pytest.mark.parametrize("drift_stage", ["before-hooks", "after-hooks"])
def test_prepare_sdist_build_rejects_prebuild_drift(
    drift_stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    provisioned = (("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    drifted = (("setuptools", "80.9.1"), ("wheel", "0.46.1"))
    manifests = (
        (drifted, provisioned, provisioned)
        if drift_stage == "before-hooks"
        else (provisioned, drifted, provisioned)
    )
    commands = _fake_consume_only_commands(monkeypatch, manifests=manifests)

    with pytest.raises(ValueError, match="package manifest"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_build_rejects_postbuild_drift_without_preserving_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    provisioned = (("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    drifted = (("setuptools", "80.9.1"), ("wheel", "0.46.1"))
    commands = _fake_consume_only_commands(
        monkeypatch, manifests=(provisioned, provisioned, drifted)
    )

    with pytest.raises(ValueError, match="package manifest"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


def _fake_build_commands(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dynamic: tuple[str, ...] = (),
    tamper_sdist: Path | None = None,
    manifests: tuple[tuple[tuple[str, str], ...], ...] | None = None,
) -> list[list[str]]:
    return _fake_consume_only_commands(
        monkeypatch, dynamic=dynamic, manifests=manifests, tamper_sdist=tamper_sdist
    )


def test_prepare_sdist_build_uses_private_no_isolation_build_and_returns_path_free_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    dynamic = ("wheel>=0.45", "platform-only>=2; sys_platform == 'win32'")
    commands = _fake_build_commands(monkeypatch, dynamic=dynamic)

    receipt = sdist_build.prepare_sdist_build(
        artifact,
        binding,
        source,
        python,
        uv,
        hashlib.sha256(uv.read_bytes()).hexdigest(),
        output_dir,
        environment_descriptor=descriptor,
        expected_build_environment_sha256=descriptor_sha256,
    )

    assert (output_dir / binding.wheel_name).is_file()
    assert receipt.sdist_sha256 == binding.sdist_sha256
    assert receipt.source_commit == commit
    assert receipt.schema_version == 2
    assert receipt.provisioned_packages == (("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    assert receipt.before_hooks_packages == receipt.provisioned_packages
    assert receipt.after_hooks_packages == receipt.provisioned_packages
    assert receipt.after_build_packages == receipt.provisioned_packages
    assert receipt.static_requirement_records == (
        sdist_build.BuildRequirementRecord("setuptools>=61", True, ("setuptools", "80.9.0")),
        sdist_build.BuildRequirementRecord("wheel", True, ("wheel", "0.46.1")),
    )
    assert receipt.dynamic_requirement_records == (
        sdist_build.BuildRequirementRecord("wheel>=0.45", True, ("wheel", "0.46.1")),
        sdist_build.BuildRequirementRecord(dynamic[1], False, None),
    )
    build_command = next(command for command in commands if command[1:3] == ["build", "--wheel"])
    assert "--no-build-isolation" in build_command
    assert "--python" in build_command
    assert build_command[build_command.index("--python") + 1] == str(python)
    assert (
        len([command for command in commands if command[1:4] == ["pip", "list", "--format"]]) == 3
    )
    assert not any("venv" in command[1:] for command in commands)
    assert not any(command[1:3] == ["pip", "install"] for command in commands)
    assert not any("sync" in command for command in commands)
    serialized = receipt.to_json()
    data = json.loads(serialized)
    assert data["dynamic_requirement_records"] == [
        {
            "expression": "wheel>=0.45",
            "marker_applicable": True,
            "satisfier": {"name": "wheel", "version": "0.46.1"},
        },
        {"expression": dynamic[1], "marker_applicable": False, "satisfier": None},
    ]
    assert data["provisioned_packages"] == data["before_hooks_packages"]
    assert "build_packages" not in data
    assert str(tmp_path) not in serialized
    assert "sdist_build" not in serialized


def test_prepare_sdist_build_fails_when_dynamic_requirement_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_build_commands(monkeypatch, dynamic=("undeclared-helper>=1",))

    with pytest.raises(ValueError, match="dynamic PEP 517 build requirement"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert not any(command[1:3] == ["pip", "install"] for command in commands)
    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_build_fails_closed_on_unlocked_dynamic_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_consume_only_commands(monkeypatch, dynamic=("unlocked-build-tool>=1",))

    with pytest.raises(ValueError, match="dynamic PEP 517 build requirement"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert any("setuptools.build_meta" in argument for command in commands for argument in command)
    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert not any("venv" in command[1:] for command in commands)
    assert not any(command[1:3] == ["pip", "install"] for command in commands)
    assert not any("sync" in command for command in commands)
    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_build_rejects_sdist_mutation_after_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    _fake_build_commands(monkeypatch, tamper_sdist=artifact)

    with pytest.raises(ValueError, match="changed during qualification"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_build_rehashes_original_sdist_before_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    python, uv, descriptor, descriptor_sha256 = _build_environment_inputs(tmp_path, source, binding)
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_build_commands(monkeypatch)
    real_extract = sdist_build._extract_sdist
    extraction_count = 0

    def mutate_after_build_extraction(
        archive_path: Path, destination: Path, bundle: BundleBinding
    ) -> Path:
        nonlocal extraction_count
        extracted = real_extract(archive_path, destination, bundle)
        extraction_count += 1
        if extraction_count == 2:
            archive_path.write_bytes(archive_path.read_bytes() + b"changed before build")
        return extracted

    monkeypatch.setattr(sdist_build, "_extract_sdist", mutate_after_build_extraction)

    with pytest.raises(ValueError, match="changed before the sdist build"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            python,
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
            environment_descriptor=descriptor,
            expected_build_environment_sha256=descriptor_sha256,
        )

    assert extraction_count == 2
    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_cli_emits_only_sanitized_receipt_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    binding = BundleBinding(
        source_commit="1" * 40,
        source_tree="2" * 40,
        version="2.0.1rc4",
        wheel_name="matryca_plumber-2.0.1rc4-py3-none-any.whl",
        wheel_size=1,
        wheel_sha256="3" * 64,
        sdist_name="matryca_plumber-2.0.1rc4.tar.gz",
        sdist_size=1,
        sdist_sha256="4" * 64,
        wheel_inventory_sha256="5" * 64,
        sdist_inventory_sha256="6" * 64,
    )
    monkeypatch.setenv("EXPECTED_BINDING_JSON", binding.to_json())
    receipt_json = '{"schema_version":2,"sdist_sha256":"' + "4" * 64 + '"}'
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_prepare(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        return SimpleNamespace(to_json=lambda: receipt_json)

    monkeypatch.setattr(cli, "prepare_sdist_build", fake_prepare)
    arguments = cli._parser().parse_args(
        [
            "prepare-sdist-build",
            "--artifact",
            "bound.tar.gz",
            "--source-root",
            "source",
            "--python",
            "python",
            "--uv",
            "uv",
            "--uv-sha256",
            "7" * 64,
            "--wheel-output",
            "private-output",
            "--build-environment-descriptor",
            "environment.json",
            "--expected-build-environment-sha256",
            "8" * 64,
        ]
    )
    arguments.handler(arguments)

    assert calls and calls[0][0][1] == binding
    assert calls[0][1] == {
        "environment_descriptor": Path("environment.json"),
        "expected_build_environment_sha256": "8" * 64,
    }
    assert capsys.readouterr().out == receipt_json + "\n"
