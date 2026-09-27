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
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.sdist_build import (
    _parse_build_system,
    _verify_dynamic_requirements,
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

    expressions, normalized = _verify_dynamic_requirements(
        raw, actual, platform="linux", architecture="x64", python_version="3.12.8"
    )

    assert expressions == raw
    assert normalized == (("wheel", "0.46.1"),)


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


def test_dynamic_requirement_extras_are_rejected() -> None:
    with pytest.raises(ValueError, match="extras are not permitted"):
        _verify_dynamic_requirements(
            ("wheel[speedups]>=0.45",),
            {"wheel": "0.46.1"},
            platform="linux",
            architecture="x64",
            python_version="3.12.8",
        )


def test_dynamic_requirement_rejects_unbound_platform_marker() -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify_dynamic_requirements(
            ("wheel>=0.45; platform_release == 'test'",),
            {"wheel": "0.46.1"},
            platform="linux",
            architecture="x64",
            python_version="3.12.8",
        )


def test_dynamic_requirement_rejects_unbound_extra_marker() -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify_dynamic_requirements(
            ("wheel>=0.45; extra == 'speedups'",),
            {"wheel": "0.46.1"},
            platform="linux",
            architecture="x64",
            python_version="3.12.8",
        )


@pytest.mark.parametrize("marker_name", ["extras", "dependency_groups"])
def test_dynamic_requirement_rejects_unbound_context_marker(marker_name: str) -> None:
    with pytest.raises(ValueError, match="unbound platform marker"):
        _verify_dynamic_requirements(
            (f"wheel>=0.45; {marker_name} == 'speedups'",),
            {"wheel": "0.46.1"},
            platform="linux",
            architecture="x64",
            python_version="3.12.8",
        )


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
    with pytest.raises(ValueError, match="dynamic build requirement"):
        _verify_dynamic_requirements(
            dynamic,
            actual,
            platform="linux",
            architecture="x64",
            python_version="3.12.8",
        )


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


def _fake_build_commands(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dynamic: tuple[str, ...] = (),
    tamper_sdist: Path | None = None,
) -> list[list[str]]:
    commands: list[list[str]] = []
    package_listing = json.dumps(
        [{"name": "setuptools", "version": "80.9.0"}, {"name": "wheel", "version": "0.46.1"}]
    ).encode()

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        timeout: float = 0,
        capture: bool = False,
    ) -> sdist_build._CommandResult:
        commands.append(command)
        if command[-1:] == ["--version"]:
            return sdist_build._CommandResult(0, b"uv 0.12.16")
        if "python" in Path(command[0]).name and "-S" in command:
            return sdist_build._CommandResult(0, b"3.12.13")
        if (
            "python" in Path(command[0]).name
            and len(command) > 3
            and "setuptools.build_meta" in command[3]
        ):
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
        if "python" in Path(command[0]).name and "-c" in command:
            return sdist_build._CommandResult(
                0,
                json.dumps(
                    {
                        "prefix": str(Path(command[0]).parent.parent),
                        "base_prefix": str(Path(command[0]).parent.parent.parent),
                        "version": "3.12.13",
                    }
                ).encode(),
            )
        if command[1:3] == ["venv", "--no-project"]:
            env_path = Path(command[-1])
            (env_path / "bin").mkdir(parents=True)
            (env_path / "bin" / "python").symlink_to(sys.executable)
            return sdist_build._CommandResult(0, b"")
        if command[1:4] == ["pip", "list", "--format"]:
            return sdist_build._CommandResult(0, package_listing)
        if command[1:3] == ["build", "--wheel"]:
            out_dir = Path(command[command.index("--out-dir") + 1])
            _wheel(out_dir / "matryca_plumber-2.0.1rc4-py3-none-any.whl")
            if tamper_sdist is not None:
                tamper_sdist.write_bytes(tamper_sdist.read_bytes() + b"changed")
            return sdist_build._CommandResult(0, b"")
        return sdist_build._CommandResult(0, b"")

    monkeypatch.setattr(sdist_build, "_run_bounded", fake_run)
    return commands


def test_prepare_sdist_build_uses_private_no_isolation_build_and_returns_path_free_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    uv = tmp_path / "uv"
    uv.write_bytes(b"trusted uv placeholder")
    python = Path(sys.executable)
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
    )

    assert (output_dir / binding.wheel_name).is_file()
    assert receipt.sdist_sha256 == binding.sdist_sha256
    assert receipt.source_commit == commit
    assert receipt.build_packages == (("setuptools", "80.9.0"), ("wheel", "0.46.1"))
    assert receipt.dynamic_requirement_expressions == dynamic
    assert receipt.dynamic_requirements == (("wheel", "0.46.1"),)
    build_command = next(command for command in commands if command[1:3] == ["build", "--wheel"])
    assert "--no-build-isolation" in build_command
    assert "--python" in build_command
    serialized = receipt.to_json()
    assert json.loads(serialized)["dynamic_requirement_expressions"] == list(dynamic)
    assert str(tmp_path) not in serialized
    assert "sdist_build" not in serialized


def test_prepare_sdist_build_fails_when_dynamic_requirement_is_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    uv = tmp_path / "uv"
    uv.write_bytes(b"trusted uv placeholder")
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    commands = _fake_build_commands(monkeypatch, dynamic=("undeclared-helper>=1",))

    with pytest.raises(ValueError, match="dynamic build requirement"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            Path(sys.executable),
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
        )

    assert not any(command[1:3] == ["build", "--wheel"] for command in commands)
    assert list(output_dir.iterdir()) == []


def test_prepare_sdist_build_rejects_sdist_mutation_after_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, commit, tree, pyproject = _source_checkout(tmp_path)
    artifact = _sdist(tmp_path / "dist" / "matryca_plumber-2.0.1rc4.tar.gz", pyproject)
    binding = _binding_for_sdist(source, commit, tree, artifact)
    uv = tmp_path / "uv"
    uv.write_bytes(b"trusted uv placeholder")
    output_dir = tmp_path / "private-output"
    output_dir.mkdir()
    _fake_build_commands(monkeypatch, tamper_sdist=artifact)

    with pytest.raises(ValueError, match="changed during qualification"):
        sdist_build.prepare_sdist_build(
            artifact,
            binding,
            source,
            Path(sys.executable),
            uv,
            hashlib.sha256(uv.read_bytes()).hexdigest(),
            output_dir,
        )

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
    receipt_json = '{"schema_version":1,"sdist_sha256":"' + "4" * 64 + '"}'
    calls: list[tuple[object, ...]] = []

    def fake_prepare(*args: object) -> SimpleNamespace:
        calls.append(args)
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
        ]
    )
    arguments.handler(arguments)

    assert calls and calls[0][1] == binding
    assert capsys.readouterr().out == receipt_json + "\n"
