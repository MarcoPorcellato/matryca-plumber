"""Synthetic installed-package integrity and provenance checks."""

from __future__ import annotations

import base64
import csv
import hashlib
import inspect
import io
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from scripts.build_release_artifacts import _PUBLIC_CONTRACT_RESOURCE_MEMBERS
from scripts.qualify_release_package import main as qualify_main
from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import installed as installed_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification import windows_installation as windows_authority
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.installed import InstalledReceipt, _run_bounded, verify_installed

VERSION = "2.0.1rc4"
DIST_NAME = "matryca_plumber-2.0.1rc4.dist-info"
TCKS = (
    "run_plumber_consumer_package_v1_tck.py",
    "run_plumber_graph_read_v1_tck.py",
    "run_plumber_graph_topology_v1_tck.py",
)


def test_windows_authority_inputs_are_explicit_and_keyword_only() -> None:
    parameters = inspect.signature(verify_installed).parameters
    required = {
        "windows_installation_descriptor",
        "expected_windows_installation_sha256",
        "windows_template",
        "installer",
    }
    assert required <= set(parameters), (
        "Independent Windows installed authority inputs are missing."
    )
    assert all(parameters[name].kind is inspect.Parameter.KEYWORD_ONLY for name in required)


def test_installed_receipt_declares_schema_and_absent_posix_windows_proof() -> None:
    receipt = InstalledReceipt(
        "wheel",
        "linux",
        "x86_64",
        "3.12.14",
        VERSION,
        "isolated-venv-site-packages",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        (),
        installed_module.BuildGenerator("setuptools", "84.1.0"),
        ("PASS", "PASS", "PASS"),
    )
    value = receipt.to_dict()
    assert value.get("schema_version") == 2, "Installed receipt schema v2 is missing."
    assert "windows_launcher" in value and value["windows_launcher"] is None


@pytest.mark.parametrize("mutation", ["schema", "posix-proof", "windows-no-proof"])
def test_installed_receipt_serializer_rejects_invalid_new_fields(mutation: str) -> None:
    from tests.test_release_package_windows_installation import _proof_document

    receipt = InstalledReceipt(
        "wheel",
        "linux",
        "x86_64",
        "3.12.14",
        VERSION,
        "isolated-venv-site-packages",
        "a" * 64,
        "b" * 64,
        "c" * 64,
        (),
        installed_module.BuildGenerator("setuptools", "84.1.0"),
        ("PASS", "PASS", "PASS"),
    )
    if mutation == "schema":
        receipt = replace(receipt, schema_version=True)
    elif mutation == "posix-proof":
        receipt = replace(
            receipt,
            windows_launcher=windows_authority.WindowsLauncherProof.from_dict(_proof_document()),
        )
    else:
        receipt = replace(receipt, operating_system="windows")
    with pytest.raises(ValueError, match="Windows|schema"):
        receipt.to_dict()


@pytest.mark.parametrize("windows", [True, False])
def test_windows_authority_arguments_reject_before_archive_or_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    windows: bool,
) -> None:
    from tests.test_release_package_windows_installation import _binding

    monkeypatch.setattr(installed_module, "_IS_WINDOWS", windows)
    monkeypatch.setattr(
        installed_module,
        "_authenticated_archive",
        lambda *_a, **_k: pytest.fail("invalid authority read the archive"),
    )
    monkeypatch.setattr(
        installed_module,
        "_selected_environment",
        lambda *_a: pytest.fail("invalid authority launched a probe"),
    )
    with pytest.raises(ValueError, match="Windows"):
        verify_installed(
            tmp_path / "python.exe",
            _binding(),
            tmp_path,
            "wheel",
            artifact=tmp_path / "archive",
            windows_template=tmp_path / "template",
        )


def test_windows_unbound_descriptor_never_launches_selected_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_release_package_windows_installation import _binding, _descriptor_document

    descriptor = tmp_path / "descriptor.json"
    descriptor.write_text(__import__("json").dumps(_descriptor_document()))
    (tmp_path / "python.exe").write_bytes(b"synthetic identity, never executed")
    monkeypatch.setattr(installed_module, "_IS_WINDOWS", True)
    monkeypatch.setattr(installed_module, "_authenticated_archive", lambda *_a, **_k: ({}, {}))
    monkeypatch.setattr(
        installed_module,
        "_verify_source",
        lambda *_a: {"scripts/release_qualification/windows_installation.py"},
    )
    monkeypatch.setattr(
        installed_module,
        "_selected_environment",
        lambda *_a: pytest.fail("unbound descriptor launched a probe"),
    )
    with pytest.raises(ValueError, match="external authenticated digest"):
        verify_installed(
            tmp_path / "python.exe",
            _binding(),
            tmp_path,
            "wheel",
            artifact=tmp_path / "archive",
            windows_installation_descriptor=descriptor,
            expected_windows_installation_sha256="0" * 64,
            windows_template=tmp_path / "template",
            installer=tmp_path / "uv.exe",
        )


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
@pytest.mark.parametrize("executable_pth", [False, True])
def test_schema_v1_refuses_unbound_windows_startup_authority_before_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: Literal["wheel", "sdist"],
    executable_pth: bool,
) -> None:
    """A synthetic schema-v1 descriptor must never authorize target startup."""
    from tests.test_release_package_windows_installation import _binding, _descriptor_document

    descriptor_bytes = json.dumps(_descriptor_document(kind)).encode()
    descriptor = tmp_path / "descriptor.json"
    descriptor.write_bytes(descriptor_bytes)
    python = tmp_path / "python.exe"
    python.write_bytes(b"synthetic target; never executed")
    if executable_pth:
        python.with_name("python._pth").write_bytes(b"inert synthetic startup override")

    monkeypatch.setattr(installed_module, "_IS_WINDOWS", True)
    load_descriptor = windows_authority.load_windows_installation_descriptor

    def load_descriptor_then_spy(
        path: Path, *, expected_sha256: str
    ) -> windows_authority.WindowsInstallationDescriptor:
        parsed = load_descriptor(path, expected_sha256=expected_sha256)
        monkeypatch.setattr(
            windows_authority,
            "canonical_windows_interpreter_path",
            lambda *_a: pytest.fail("schema-v1 gate ran after interpreter-path authority use"),
        )
        return parsed

    monkeypatch.setattr(
        windows_authority, "load_windows_installation_descriptor", load_descriptor_then_spy
    )
    monkeypatch.setattr(installed_module, "_authenticated_archive", lambda *_a, **_k: ({}, {}))
    monkeypatch.setattr(
        installed_module,
        "_verify_source",
        lambda *_a: {"scripts/release_qualification/windows_installation.py"},
    )
    monkeypatch.setattr(
        installed_module,
        "_selected_environment",
        lambda *_a: pytest.fail("schema-v1 startup authority reached the selected interpreter"),
    )
    monkeypatch.setattr(
        installed_module,
        "_isolated_probe",
        lambda *_a: pytest.fail("schema-v1 startup authority reached the isolated probe"),
    )

    with pytest.raises(ValueError, match=r"Windows.*NO-GO.*startup authority"):
        verify_installed(
            python,
            _binding(),
            tmp_path,
            kind,
            artifact=tmp_path / "archive",
            windows_installation_descriptor=descriptor,
            expected_windows_installation_sha256=hashlib.sha256(descriptor_bytes).hexdigest(),
            windows_template=tmp_path / "template.exe",
            installer=tmp_path / "uv.exe",
        )


def test_windows_context_rejects_replaced_same_byte_authority(tmp_path: Path) -> None:
    from tests.test_release_package_windows_installation import _descriptor_document

    descriptor = windows_authority.WindowsInstallationDescriptor.from_bytes(
        json.dumps(_descriptor_document()).encode()
    )
    path = tmp_path / "authority"
    path.write_bytes(b"same bytes")
    context = installed_module._WindowsInstallationContext(
        descriptor,
        b"not an admitted template",
        ((path, hashlib.sha256(b"same bytes").hexdigest(), 100, None),),
    )
    context.revalidate()
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"same bytes")
    replacement.replace(path)
    with pytest.raises(ValueError, match="identity|changed"):
        context.revalidate()


def _startup_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    env_root = tmp_path / "owned-environment"
    site = env_root / "Lib/site-packages"
    site.mkdir(parents=True)
    config = env_root / "pyvenv.cfg"
    config.write_bytes(b"include-system-site-packages = false\nversion = 3.12.14\n")
    return env_root, site, config


@pytest.mark.parametrize(
    "mutation", ["config", "replace", "pth", "sitecustomize", "usercustomize", "inventory"]
)
def test_windows_startup_state_rejects_later_mutation(tmp_path: Path, mutation: str) -> None:
    env_root, site, config = _startup_fixture(tmp_path)
    capture = getattr(installed_module, "_capture_windows_startup", None)
    assert callable(capture), "Retained Windows startup authority is missing."
    startup = capture(env_root)
    startup.revalidate()
    if mutation == "config":
        config.write_bytes(b"include-system-site-packages = true\n")
    elif mutation == "replace":
        replacement = env_root / "replacement"
        replacement.write_bytes(config.read_bytes())
        replacement.replace(config)
    else:
        name = {
            "pth": "unsafe.pth",
            "sitecustomize": "sitecustomize.py",
            "usercustomize": "usercustomize.pyd",
            "inventory": "new-installed-package",
        }[mutation]
        (site / name).write_bytes(b"inert synthetic bytes, never imported")
    with pytest.raises(ValueError, match="Windows"):
        startup.revalidate()


@pytest.mark.parametrize(
    "hook", ["unsafe.pth", "sitecustomize.py", "sitecustomize", "USERCUSTOMIZE.PYD"]
)
def test_windows_startup_state_rejects_preexisting_hooks(tmp_path: Path, hook: str) -> None:
    env_root, site, _config = _startup_fixture(tmp_path)
    (site / hook).write_bytes(b"inert synthetic bytes, never imported")
    capture = getattr(installed_module, "_capture_windows_startup", None)
    assert callable(capture), "Retained Windows startup authority is missing."
    with pytest.raises(ValueError, match="startup hook"):
        capture(env_root)


def _mocked_windows_installation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate: Callable[[str, dict[str, Path]], None],
) -> tuple[Callable[[], InstalledReceipt], dict[str, Path], list[str]]:
    """Real orchestration/revalidation; artifact/native observations are explicit stubs.

    No official template is admitted or patched. The inert launchers and the
    independently specified proof are not represented as a native installation.
    """
    from tests.test_release_package_windows_installation import (
        _binding,
        _descriptor_document,
        _proof_document,
    )

    authority = windows_authority
    env_root, site, config = _startup_fixture(tmp_path)
    scripts = env_root / "Scripts"
    scripts.mkdir()
    python = scripts / "python.exe"
    python.write_bytes(b"inert interpreter; never executed")
    launchers = []
    for name in ENTRY_POINTS:
        path = scripts / f"{name}.exe"
        path.write_bytes(b"inert launcher; never executed")
        launchers.append(path)
    evidence = tmp_path / "independent-authority"
    evidence.write_bytes(b"fixed independent synthetic authority")
    descriptor = authority.WindowsInstallationDescriptor.from_bytes(
        json.dumps(_descriptor_document()).encode()
    )
    proof = authority.WindowsLauncherProof.from_dict(_proof_document())
    context = installed_module._WindowsInstallationContext(
        descriptor,
        b"not an admitted template",
        ((evidence, hashlib.sha256(evidence.read_bytes()).hexdigest(), 1024, None),),
        startup=installed_module._capture_windows_startup(env_root),
    )
    source = tmp_path / "source"
    source.mkdir()
    artifact = tmp_path / "original.whl"
    paths = {
        "env": env_root,
        "site": site,
        "config": config,
        "authority": evidence,
        "launcher": launchers[0],
        "artifact": artifact,
    }
    phases: list[str] = []

    def phase(name: str) -> None:
        phases.append(name)
        mutate(name, paths)

    def authenticated_archive(
        selected: Path, binding: BundleBinding, kind: str, **kwargs: object
    ) -> tuple[dict[str, object], dict[str, bytes]]:
        assert selected == artifact and binding == _binding() and kind == "wheel"
        return {}, {}

    def inputs(*args: object) -> installed_module._WindowsInstallationContext:
        assert args == (
            python,
            _binding(),
            source,
            "wheel",
            tmp_path / "descriptor.json",
            "a" * 64,
            tmp_path / "template",
            tmp_path / "installer",
        )
        context.revalidate()
        phase("admission")
        return context

    def selected_environment(selected: Path) -> tuple[Path, Path, str, str, str]:
        assert selected == python
        phase("identity")
        return env_root, site, "3.12.14", "windows", "amd64"

    records = {
        os.path.relpath(path, site).replace(os.sep, "/"): (path, "", "") for path in launchers
    }

    def inventory(
        *args: object, **kwargs: object
    ) -> tuple[str, str, installed_module.BuildGenerator, object]:
        assert args[-1] == records and kwargs["windows_context"] is context
        phase("inventory")
        return "b" * 64, "c" * 64, installed_module.BuildGenerator("setuptools", "84.1.0"), proof

    def probe(*args: object) -> tuple[Path, Path, str, str, str, str, tuple[tuple[str, str], ...]]:
        assert args == (python, env_root, site, source)
        phase("probe")
        return (
            site,
            site / "src/__init__.py",
            hashlib.sha256(b"[]").hexdigest(),
            "3.12.14",
            "windows",
            "amd64",
            (),
        )

    tck_ids = {
        "run_plumber_consumer_package_v1_tck.py": "plumber.consumer.package/v1",
        "run_plumber_graph_read_v1_tck.py": "plumber.graph.read/v1",
        "run_plumber_graph_topology_v1_tck.py": "plumber.graph.topology/v1",
    }
    calls = 0

    def bounded(argv: list[str], **kwargs: object) -> tuple[int, bytes, bytes]:
        nonlocal calls
        assert argv[0:3] == [str(python), "-I", "-S"]
        assert kwargs["timeout"] == 30 and argv[-2] == str(site)
        calls += 1
        assert calls <= 3
        script = Path(argv[-1]).name
        phase(f"tck-{calls}")
        return 0, json.dumps({"contract_id": tck_ids[script]}).encode(), b""

    def final_scripts(*args: object, **kwargs: object) -> object:
        assert args == (records, site, env_root, dict(authority.SCRIPT_PAIRS))
        assert kwargs["windows_context"] is context
        phase("final-proof")
        return proof

    monkeypatch.setattr(installed_module, "_IS_WINDOWS", True)
    monkeypatch.setattr(installed_module, "_authenticated_archive", authenticated_archive)
    monkeypatch.setattr(
        installed_module,
        "_verify_source",
        lambda *_a: {"scripts/release_qualification/windows_installation.py"},
    )
    monkeypatch.setattr(installed_module, "_windows_inputs", inputs)
    monkeypatch.setattr(installed_module, "_payload_map", lambda *_a: {})
    monkeypatch.setattr(installed_module, "_selected_environment", selected_environment)
    monkeypatch.setattr(
        installed_module, "_distribution", lambda *_a: (site / "project.dist-info", VERSION)
    )
    monkeypatch.setattr(installed_module, "_parse_record", lambda *_a: records)
    monkeypatch.setattr(installed_module, "_verify_inventory", inventory)
    monkeypatch.setattr(installed_module, "_isolated_probe", probe)
    monkeypatch.setattr(installed_module, "_run_bounded", bounded)
    monkeypatch.setattr(
        installed_module, "_expected_scripts", lambda *_a: dict(authority.SCRIPT_PAIRS)
    )
    monkeypatch.setattr(installed_module, "_verify_entry_point_scripts", final_scripts)

    def run() -> InstalledReceipt:
        return verify_installed(
            python,
            _binding(),
            source,
            "wheel",
            artifact=artifact,
            windows_installation_descriptor=tmp_path / "descriptor.json",
            expected_windows_installation_sha256="a" * 64,
            windows_template=tmp_path / "template",
            installer=tmp_path / "installer",
        )

    return run, paths, phases


def test_mocked_windows_verification_completes_all_observations_and_rechecks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run, _paths, phases = _mocked_windows_installation(tmp_path, monkeypatch, lambda *_a: None)
    receipt = run()
    assert phases == [
        "admission",
        "identity",
        "inventory",
        "probe",
        "tck-1",
        "tck-2",
        "tck-3",
        "final-proof",
    ]
    assert receipt.windows_launcher is not None
    serialized = receipt.to_dict()["windows_launcher"]
    assert isinstance(serialized, dict)
    assert serialized["profile"] == "windows-x64-console-nonrelocatable/v1"
    assert receipt.schema_version == 2 and receipt.tck_outcomes == ("PASS", "PASS", "PASS")


@pytest.mark.parametrize(
    "phase", ["admission", "identity", "inventory", "probe", "tck-1", "tck-2", "tck-3"]
)
@pytest.mark.parametrize("mutation", ["config", "hook", "authority-replace"])
def test_windows_orchestration_stops_after_execution_authority_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    mutation: str,
) -> None:
    def mutate(current: str, paths: dict[str, Path]) -> None:
        if current != phase:
            return
        if mutation == "config":
            paths["config"].write_bytes(b"include-system-site-packages = true\n")
        elif mutation == "hook":
            (paths["site"] / "injected.pth").write_bytes(b"inert hook; never imported")
        else:
            replacement = tmp_path / "replacement-authority"
            replacement.write_bytes(paths["authority"].read_bytes())
            replacement.replace(paths["authority"])

    run, _paths, phases = _mocked_windows_installation(tmp_path, monkeypatch, mutate)
    with pytest.raises(ValueError, match="Windows"):
        run()
    assert "final-proof" not in phases
    if phase == "admission":
        assert phases == ["admission"]
    elif phase in {"identity", "inventory"}:
        assert "probe" not in phases
    elif phase == "probe":
        assert "tck-1" not in phases
    else:
        assert phases[-1] == phase


@pytest.mark.parametrize("phase", ["inventory", "probe", "tck-3"])
@pytest.mark.parametrize("mutation", ["bytes", "same-byte-replace"])
def test_windows_orchestration_rejects_launcher_change_before_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    mutation: str,
) -> None:
    def mutate(current: str, paths: dict[str, Path]) -> None:
        if current != phase:
            return
        launcher = paths["launcher"]
        if mutation == "bytes":
            launcher.write_bytes(b"changed inert launcher")
        else:
            replacement = tmp_path / "replacement-launcher"
            replacement.write_bytes(launcher.read_bytes())
            replacement.replace(launcher)

    run, _paths, phases = _mocked_windows_installation(tmp_path, monkeypatch, mutate)
    with pytest.raises(ValueError, match="launcher identity changed"):
        run()
    assert "final-proof" not in phases


def test_windows_bounded_runner_uses_shared_gate_and_raw_readers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    class _Process:
        stdout = object()
        stderr = object()

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
        errors: list[BaseException] = []
        overflowed = False

        def __init__(self, stream: object, *, limit: int) -> None:
            self.stream = stream
            self.thread = type("_Thread", (), {"ident": 1})()
            self.limit = limit
            self.data = bytearray(b"stdout" if stream is _Owned.process.stdout else b"stderr")

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

    monkeypatch.setattr(installed_module, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(process_module, "start_process", _start)
    monkeypatch.setattr(process_module, "WindowsPipeReader", _Reader)

    code, stdout, stderr = installed_module._run_bounded(
        ["synthetic-child"], cwd=tmp_path, timeout=2
    )

    assert (code, stdout, stderr) == (0, b"stdout", b"stderr")
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
    with pytest.raises(ValueError, match="subprocess parameters"):
        # This cast is static-only: validation must still receive non-finite NaN.
        installed_module._run_bounded(
            ["synthetic-child"], cwd=tmp_path, timeout=cast(int, float("nan"))
        )


TCK_IDS = (
    "plumber.consumer.package/v1",
    "plumber.graph.read/v1",
    "plumber.graph.topology/v1",
)
ENTRY_POINTS = (
    "matryca",
    "matryca-plumber",
    "matryca-logseq-llm-wiki",
)


def test_alpha_installed_authentication_requires_explicit_policy_before_file_access(
    tmp_path: Path,
) -> None:
    binding = BundleBinding(
        "a" * 40,
        "b" * 40,
        "2.1.0a3",
        "matryca_plumber-2.1.0a3-py3-none-any.whl",
        1,
        "c" * 64,
        "matryca_plumber-2.1.0a3.tar.gz",
        1,
        "d" * 64,
        "e" * 64,
        "f" * 64,
    )
    with pytest.raises(ValueError, match="version"):
        verify_installed(
            tmp_path / "python", binding, tmp_path, "wheel", artifact=tmp_path / binding.wheel_name
        )
    with pytest.raises(ValueError, match="existing regular file"):
        verify_installed(
            tmp_path / "python",
            binding,
            tmp_path,
            "wheel",
            artifact=tmp_path / binding.wheel_name,
            policy="og-alpha3",
        )


def test_alpha_installed_policy_reaches_real_nested_archive_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_release_package_bundle import _alpha_inputs

    source, commit, ledger, dist = _alpha_inputs(tmp_path)
    binding = bundle_module.build_binding(source, dist, ledger, commit, policy="og-alpha3")

    def stop_after_archive(*_args: object, **_kwargs: object) -> None:
        raise ValueError("authenticated archive reached")

    monkeypatch.setattr(installed_module, "_safe_root", stop_after_archive)
    with pytest.raises(ValueError, match="authenticated archive reached"):
        verify_installed(
            tmp_path / "python",
            binding,
            source,
            "wheel",
            artifact=dist / binding.wheel_name,
            policy="og-alpha3",
        )


def _hash(payload: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode().rstrip("=")
    return f"sha256={digest}"


def _artifact_binding(source: Path, wheel: Path, sdist: Path) -> BundleBinding:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=source, text=True
    ).strip()
    wheel_members, _ = bundle_module._read_wheel(wheel)
    sdist_members, _, _ = bundle_module._read_sdist(sdist, f"matryca_plumber-{VERSION}")
    wheel_size, wheel_hash = bundle_module._archive_sha256(wheel)
    sdist_size, sdist_hash = bundle_module._archive_sha256(sdist)
    return BundleBinding(
        source_commit=commit,
        source_tree=tree,
        version=VERSION,
        wheel_name=f"matryca_plumber-{VERSION}-py3-none-any.whl",
        wheel_size=wheel_size,
        wheel_sha256=wheel_hash,
        sdist_name=f"matryca_plumber-{VERSION}.tar.gz",
        sdist_size=sdist_size,
        sdist_sha256=sdist_hash,
        wheel_inventory_sha256=bundle_module._inventory_digest(wheel_members),
        sdist_inventory_sha256=bundle_module._inventory_digest(sdist_members),
    )


def _site_packages(python: Path) -> Path:
    probe = subprocess.run(
        [str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(probe.stdout.strip())


def _install_fixture(
    tmp_path: Path, *, kind: str = "wheel"
) -> tuple[Path, Path, Path, Path, BundleBinding]:
    if os.name == "nt":
        pytest.skip("Synthetic installation fixture currently covers POSIX only.")
    env = tmp_path / "env"
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("The locked test environment requires uv to create its disposable venv.")
    uv_env = os.environ.copy()
    uv_env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    base_python = str(vars(sys).get("_base_executable", sys.executable))
    subprocess.run(
        [uv, "venv", "--python", base_python, str(env)],
        check=True,
        capture_output=True,
        env=uv_env,
    )
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    site = _site_packages(python)
    source = tmp_path / "source"
    (source / "contracts").mkdir(parents=True)
    (source / "scripts").mkdir()
    (source / "src").mkdir()
    (source / "frontend").mkdir()
    package = site / "src"
    (package / "contract_artifacts").mkdir(parents=True)
    (site / "frontend/dist").mkdir(parents=True)

    source_files: dict[str, bytes] = {}
    for member in sorted(_PUBLIC_CONTRACT_RESOURCE_MEMBERS):
        if member.startswith("src/contract_artifacts/contracts/"):
            relative = member.removeprefix("src/contract_artifacts/")
            source_name = relative
        else:
            source_name = f"scripts/{Path(member).name}"
        payload = f"fixture: {member}\n".encode()
        source_files[source_name] = payload
        src_destination = (
            package / "contract_artifacts" / relative
            if member.startswith("src/contract_artifacts/contracts/")
            else package / "contract_artifacts/tck" / Path(member).name
        )
        src_destination.parent.mkdir(parents=True, exist_ok=True)
        src_destination.write_bytes(payload)
        (source / source_name).parent.mkdir(parents=True, exist_ok=True)
        (source / source_name).write_bytes(payload)

    source_modules = {
        "src/__init__.py": b'"""Installed test package."""\n',
        "frontend/__init__.py": b"",
    }
    for name, payload in source_modules.items():
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    (package / "__init__.py").write_bytes(source_modules["src/__init__.py"])
    (site / "frontend/__init__.py").write_bytes(source_modules["frontend/__init__.py"])
    (site / "frontend/dist/index.html").write_bytes(b"<!doctype html>\n")
    for name in TCKS:
        contract_id = TCK_IDS[TCKS.index(name)]
        tck = package / "contract_artifacts/tck" / name
        tck.parent.mkdir(parents=True, exist_ok=True)
        tck.write_text(
            "import json\n"
            f"print(json.dumps({{'contract_id': {contract_id!r}, 'status': 'pass'}}))\n",
            encoding="utf-8",
        )
        (source / "scripts" / name).write_bytes(tck.read_bytes())

    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    for name, payload in {
        "pyproject.toml": (
            b"[project]\nname='matryca-plumber'\nversion='2.0.1rc4'\n\n"
            b"[project.scripts]\nmatryca='src.cli:main'\n"
            b"matryca-plumber='src.plumber_entry:main'\n"
            b"matryca-logseq-llm-wiki='src.main:main'\n"
        ),
        "LICENSE": b"Apache License 2.0\n",
        "NOTICE": b"Copyright 2026\n",
        "README.md": b"Fixture release package.\n",
        "setup.py": b"from setuptools import setup\nsetup()\n",
        "MANIFEST.in": b"graft contracts\n",
    }.items():
        (source / name).write_bytes(payload)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
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
        cwd=source,
        check=True,
    )

    dist_info = site / DIST_NAME
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        f"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: {VERSION}\n\n",
        encoding="utf-8",
    )
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\nGenerator: setuptools (84.0.0)\n"
        "Root-Is-Purelib: true\nTag: py3-none-any\n",
        encoding="utf-8",
    )
    (dist_info / "INSTALLER").write_text("uv\n", encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(
        "[console_scripts]\nmatryca = src.cli:main\n"
        "matryca-plumber = src.plumber_entry:main\n"
        "matryca-logseq-llm-wiki = src.main:main\n",
        encoding="utf-8",
    )
    (dist_info / "top_level.txt").write_text("frontend\nsrc\n", encoding="utf-8")
    (dist_info / "licenses").mkdir()
    (dist_info / "licenses/LICENSE").write_bytes((source / "LICENSE").read_bytes())
    (dist_info / "licenses/NOTICE").write_bytes((source / "NOTICE").read_bytes())
    script_dir = env / ("Scripts" if os.name == "nt" else "bin")
    script_targets = {
        "matryca": "src.cli:main",
        "matryca-plumber": "src.plumber_entry:main",
        "matryca-logseq-llm-wiki": "src.main:main",
    }
    for entry_point in ENTRY_POINTS:
        script = script_dir / (f"{entry_point}.exe" if os.name == "nt" else entry_point)
        if os.name == "nt":
            script.write_bytes(b"MZ fixture launcher")
        else:
            module, function = script_targets[entry_point].split(":")
            script.write_text(
                f"#!{python}\n"
                "# -*- coding: utf-8 -*-\n"
                "import sys\n"
                f"from {module} import {function}\n"
                'if __name__ == "__main__":\n'
                '    if sys.argv[0].endswith("-script.pyw"):\n'
                "        sys.argv[0] = sys.argv[0][:-11]\n"
                '    elif sys.argv[0].endswith(".exe"):\n'
                "        sys.argv[0] = sys.argv[0][:-4]\n"
                f"    sys.exit({function}())\n",
                encoding="utf-8",
            )

    dist = tmp_path / "artifacts"
    dist.mkdir()
    wheel = dist / f"matryca_plumber-{VERSION}-py3-none-any.whl"
    wheel_members: dict[str, bytes] = {}
    for root_name in ("src", "frontend"):
        root = site / root_name
        for path in root.rglob("*"):
            if path.is_file():
                wheel_members[path.relative_to(site).as_posix()] = path.read_bytes()
    for path in dist_info.rglob("*"):
        if path.is_file() and path.name not in {"RECORD", "INSTALLER"}:
            wheel_members[path.relative_to(site).as_posix()] = path.read_bytes()
    wheel_members[f"{DIST_NAME}/RECORD"] = b""
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in sorted(wheel_members.items()):
            archive.writestr(name, payload)

    sdist = dist / f"matryca_plumber-{VERSION}.tar.gz"
    root_name = f"matryca_plumber-{VERSION}"
    sdist_members: dict[str, bytes] = {}
    for path in source.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            sdist_members[path.relative_to(source).as_posix()] = path.read_bytes()
    sdist_members["frontend/dist/index.html"] = (site / "frontend/dist/index.html").read_bytes()
    sdist_members["PKG-INFO"] = (dist_info / "METADATA").read_bytes()
    sdist_members["setup.cfg"] = b"[egg_info]\ntag_build =\n"
    with tarfile.open(sdist, "w:gz") as archive:
        for name, payload in sorted(sdist_members.items()):
            info = tarfile.TarInfo(f"{root_name}/{name}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))

    binding = _artifact_binding(source, wheel, sdist)

    files = [
        path
        for path in site.rglob("*")
        if path.is_file() and path.name != "RECORD" and not path.name.startswith("_virtualenv.")
    ]
    record_rows = []
    for path in sorted(files):
        relative = os.path.relpath(path, site).replace(os.sep, "/")
        content = path.read_bytes()
        record_rows.append([relative, _hash(content), str(len(content))])
    for entry_point in ENTRY_POINTS:
        script = script_dir / (f"{entry_point}.exe" if os.name == "nt" else entry_point)
        relative = os.path.relpath(script, site).replace(os.sep, "/")
        payload = script.read_bytes()
        record_rows.append([relative, _hash(payload), str(len(payload))])
    record_rows.append([f"{DIST_NAME}/RECORD", "", ""])
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(record_rows)
    (dist_info / "RECORD").write_text(output.getvalue(), encoding="utf-8")
    artifact = wheel if kind == "wheel" else sdist
    return python, source, site, artifact, binding


def test_installed_receipt_is_sanitized_and_runs_all_installed_tcks(tmp_path: Path) -> None:
    python, source, _site, artifact, binding = _install_fixture(tmp_path)
    assert not subprocess.check_output(
        ["git", "ls-files", "frontend/dist"], cwd=source, text=True
    ).strip()
    receipt = verify_installed(python, binding, source, "wheel", artifact=artifact)

    assert isinstance(receipt, InstalledReceipt)
    assert receipt.version == VERSION
    assert receipt.kind == "wheel"
    assert receipt.build_generator.name == "setuptools"
    assert receipt.build_generator.version == "84.0.0"
    assert receipt.dependencies == ()
    assert receipt.dependency_sha256 == hashlib.sha256(b"[]").hexdigest()
    child_python = subprocess.check_output(
        [str(python), "-I", "-c", "import platform; print(platform.python_version())"],
        text=True,
    ).strip()
    assert receipt.python_version == child_python
    assert receipt.operating_system == platform.system().lower()
    assert receipt.architecture == platform.machine().lower()
    assert len(receipt.resource_sha256) == 64
    assert len(receipt.record_sha256) == 64
    assert receipt.tck_outcomes == ("PASS", "PASS", "PASS")
    assert not any(
        "/" in value or "\\" in value
        for value in receipt.to_dict().values()
        if isinstance(value, str)
    )
    assert set(receipt.to_dict()) == {
        "schema_version",
        "windows_launcher",
        "kind",
        "operating_system",
        "architecture",
        "python_version",
        "version",
        "location_class",
        "record_sha256",
        "resource_sha256",
        "dependency_sha256",
        "dependencies",
        "build_generator",
        "tck_outcomes",
    }


def test_source_distribution_install_matches_its_authenticated_archive(tmp_path: Path) -> None:
    python, source, _site, artifact, binding = _install_fixture(tmp_path, kind="sdist")

    receipt = verify_installed(python, binding, source, "sdist", artifact=artifact)

    assert receipt.kind == "sdist"
    assert receipt.build_generator.name == "setuptools"
    assert receipt.build_generator.version == "84.0.0"
    assert receipt.tck_outcomes == ("PASS", "PASS", "PASS")


def test_dependency_receipt_is_sorted_sanitized_and_digest_bound(tmp_path: Path) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    for dist_name, name, version in (
        ("example_dependency", "Example_Dependency", "1.0"),
        ("zeta", "zeta", "2.0"),
    ):
        extra = site / f"{dist_name}-{version}.dist-info"
        extra.mkdir()
        (extra / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n",
            encoding="utf-8",
        )
    receipt = verify_installed(python, binding, source, "wheel", artifact=artifact)

    assert receipt.dependencies == (("example-dependency", "1.0"), ("zeta", "2.0"))
    assert (
        receipt.dependency_sha256
        == hashlib.sha256(b'[["example-dependency","1.0"],["zeta","2.0"]]').hexdigest()
    )
    assert receipt.to_dict()["dependencies"] == [
        {"name": "example-dependency", "version": "1.0"},
        {"name": "zeta", "version": "2.0"},
    ]


def test_dependency_probe_rejects_normalized_name_duplicates(tmp_path: Path) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    for dist_name, name, version in (
        ("example_dependency", "Example_Dependency", "1.0"),
        ("example-dependency", "example-dependency", "2.0"),
    ):
        extra = site / f"{dist_name}-{version}.dist-info"
        extra.mkdir()
        (extra / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n\n",
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="duplicate distributions"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


@pytest.mark.parametrize(
    "generator",
    ["setuptools (84.0.0) extra", "Setuptools (84.0.0)", "setuptools ()", "setuptools (../1)"],
)
def test_wheel_generator_must_be_an_exact_sanitized_name_and_version(
    tmp_path: Path, generator: str
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path, kind="sdist")
    wheel_metadata = site / DIST_NAME / "WHEEL"
    wheel_metadata.write_text(
        "Wheel-Version: 1.0\nGenerator: " + generator + "\n"
        "Root-Is-Purelib: true\nTag: py3-none-any\n",
        encoding="utf-8",
    )
    record = site / DIST_NAME / "RECORD"
    with record.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    row = next(row for row in rows if row[0] == f"{DIST_NAME}/WHEEL")
    row[1:] = [_hash(wheel_metadata.read_bytes()), str(wheel_metadata.stat().st_size)]
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record.write_text(output.getvalue(), encoding="utf-8")

    with pytest.raises(ValueError, match="WHEEL metadata"):
        verify_installed(python, binding, source, "sdist", artifact=artifact)


def test_artifact_bytes_must_match_independent_binding(tmp_path: Path) -> None:
    python, source, _site, artifact, binding = _install_fixture(tmp_path)
    with artifact.open("ab") as stream:
        stream.write(b"tampered")

    with pytest.raises(ValueError, match="artifact"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_wrong_kind_artifact_is_rejected(tmp_path: Path) -> None:
    python, source, _site, artifact, binding = _install_fixture(tmp_path, kind="sdist")

    with pytest.raises(ValueError, match="filename"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_installed_metadata_must_match_authenticated_wheel_not_edited_record(
    tmp_path: Path,
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    entry_points = site / DIST_NAME / "entry_points.txt"
    entry_points.write_text("[console_scripts]\nforged = src.cli:main\n", encoding="utf-8")
    record = site / DIST_NAME / "RECORD"
    rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
    row = next(row for row in rows if row[0] == f"{DIST_NAME}/entry_points.txt")
    row[1], row[2] = _hash(entry_points.read_bytes()), str(entry_points.stat().st_size)
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record.write_text(output.getvalue(), encoding="utf-8")

    with pytest.raises(ValueError, match="archive|inventory|metadata"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_startup_and_package_code_do_not_run_before_integrity_gate(tmp_path: Path) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    marker = tmp_path / "startup-marker"
    pth = site / "qualification_probe.pth"
    pth.write_text(
        "import pathlib; pathlib.Path(" + repr(str(marker)) + ").write_text('startup')\n",
        encoding="utf-8",
    )
    init_file = site / "src/__init__.py"
    init_file.write_text(
        "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('package')\n",
        encoding="utf-8",
    )
    record = site / DIST_NAME / "RECORD"
    rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
    init_row = next(row for row in rows if row[0] == "src/__init__.py")
    init_row[1:] = [_hash(init_file.read_bytes()), str(init_file.stat().st_size)]
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record.write_text(output.getvalue(), encoding="utf-8")

    with pytest.raises(ValueError, match="authenticated archive"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)

    assert not marker.exists()


@pytest.mark.parametrize("record_mode", ["unrecorded", "empty", "hashed"])
@pytest.mark.parametrize("suffix", [".pyc", ".pyo"])
def test_installed_bytecode_is_rejected_before_import(
    tmp_path: Path, record_mode: str, suffix: str
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    cache = site / f"src/__init__{suffix}"
    cache.write_bytes(b"fixture bytecode")
    if record_mode != "unrecorded":
        record = site / DIST_NAME / "RECORD"
        rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
        row = [cache.relative_to(site).as_posix(), "", ""]
        if record_mode == "hashed":
            row[1:] = [_hash(cache.read_bytes()), str(cache.stat().st_size)]
        rows.append(row)
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8")

    with pytest.raises(ValueError, match="bytecode"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_windows_installed_qualification_fails_closed_before_interpreter_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python, source, _site, artifact, binding = _install_fixture(tmp_path)
    monkeypatch.setattr(installed_module, "_IS_WINDOWS", True, raising=False)

    with pytest.raises(ValueError, match="Windows.*NO-GO"):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_uv_shell_entry_point_wrapper_is_bound_when_venv_path_has_spaces(
    tmp_path: Path,
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path / "venv with spaces")
    env_root = python.parent.parent
    record = site / DIST_NAME / "RECORD"
    rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
    for entry_point in ENTRY_POINTS:
        script = env_root / "bin" / entry_point
        original = script.read_bytes()
        _shebang, _newline, body = original.partition(b"\n")
        launcher = (
            f"#!/bin/sh\n'''exec' {shlex.quote(str(python))} \"$0\" \"$@\"\n' '''\n"
        ).encode()
        script.write_bytes(launcher + body)
        relative = os.path.relpath(script, site).replace(os.sep, "/")
        row = next(row for row in rows if row[0] == relative)
        row[1:] = [_hash(script.read_bytes()), str(script.stat().st_size)]
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record.write_text(output.getvalue(), encoding="utf-8")

    receipt = verify_installed(python, binding, source, "wheel", artifact=artifact)

    assert receipt.tck_outcomes == ("PASS", "PASS", "PASS")


@pytest.mark.skipif(os.name == "nt", reason="Process-group descendant cleanup is POSIX-specific.")
def test_bounded_runner_kills_descendant_that_inherits_output_pipes(tmp_path: Path) -> None:
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
    )

    with pytest.raises(ValueError, match="left an output-producing descendant alive"):
        _run_bounded([sys.executable, "-c", code], cwd=tmp_path, timeout=5)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_record", "RECORD"),
        ("malformed_record", "RECORD"),
        ("unlisted_file", "unlisted"),
        ("traversal", "path"),
        ("empty_payload_hash", "hash"),
        ("empty_payload_size", "size"),
        ("missing_frontend", "frontend"),
        ("tampered_resource", "resource"),
        ("missing_tck", "TCK"),
        ("checkout_origin", "checkout"),
    ],
)
def test_installed_verifier_fails_closed_on_record_and_provenance_mutations(
    tmp_path: Path, mutation: str, message: str
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    record = site / DIST_NAME / "RECORD"
    if mutation == "missing_record":
        record.unlink()
    elif mutation == "malformed_record":
        record.write_text("one,two\n", encoding="utf-8")
    elif mutation == "unlisted_file":
        (site / "src/unlisted.py").write_text("UNLISTED = True\n", encoding="utf-8")
    elif mutation == "traversal":
        record.write_text("../outside,sha256=abc,1\n", encoding="utf-8")
    elif mutation in {"empty_payload_hash", "empty_payload_size"}:
        rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
        target = next(row for row in rows if row[0] == "src/__init__.py")
        target[1 if mutation == "empty_payload_hash" else 2] = ""
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8")
    elif mutation == "missing_frontend":
        (site / "frontend/dist/index.html").unlink()
        rows = [
            row
            for row in csv.reader(record.open(encoding="utf-8", newline=""))
            if row[0] != "frontend/dist/index.html"
        ]
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8")
    elif mutation == "tampered_resource":
        resource_path = site / "src/contract_artifacts/contracts/plumber.graph.read/v1/schema.json"
        resource_path.write_bytes(resource_path.read_bytes() + b"tampered")
        rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
        changed = next(row for row in rows if row[0] == resource_path.relative_to(site).as_posix())
        changed[1] = _hash(resource_path.read_bytes())
        changed[2] = str(resource_path.stat().st_size)
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8")
    elif mutation == "missing_tck":
        tck_path = site / "src/contract_artifacts/tck" / TCKS[0]
        tck_path.unlink()
        rows = [
            row
            for row in csv.reader(record.open(encoding="utf-8", newline=""))
            if row[0] != tck_path.relative_to(site).as_posix()
        ]
        output = io.StringIO(newline="")
        csv.writer(output, lineterminator="\n").writerows(rows)
        record.write_text(output.getvalue(), encoding="utf-8")
    elif mutation == "checkout_origin":
        init_file = site / "src/__init__.py"
        init_file.unlink()
        init_file.symlink_to(source / "src/__init__.py")

    with pytest.raises(ValueError, match=message):
        verify_installed(python, binding, source, "wheel", artifact=artifact)


def test_record_self_and_generated_installer_metadata_may_have_empty_hash_fields(
    tmp_path: Path,
) -> None:
    python, source, site, artifact, binding = _install_fixture(tmp_path)
    record = site / DIST_NAME / "RECORD"
    rows = list(csv.reader(record.open(encoding="utf-8", newline="")))
    installer = next(row for row in rows if row[0] == f"{DIST_NAME}/INSTALLER")
    installer[1:] = ["", ""]
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    record.write_text(output.getvalue(), encoding="utf-8")

    receipt = verify_installed(python, binding, source, "wheel", artifact=artifact)

    assert receipt.tck_outcomes == ("PASS", "PASS", "PASS")


def test_verify_installed_cli_requires_independent_binding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("EXPECTED_BINDING_JSON", raising=False)

    with pytest.raises(SystemExit) as error:
        qualify_main(
            [
                "verify-installed",
                "--python",
                "/tmp/python",
                "--source-root",
                "/tmp/source",
                "--artifact",
                "/tmp/artifact.whl",
                "--kind",
                "wheel",
            ]
        )

    assert error.value.code == 2
    assert "EXPECTED_BINDING_JSON is required" in capsys.readouterr().err
