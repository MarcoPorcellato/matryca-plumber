"""Synthetic installed-package integrity and provenance checks."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from scripts.build_release_artifacts import _PUBLIC_CONTRACT_RESOURCE_MEMBERS
from scripts.qualify_release_package import main as qualify_main
from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import installed as installed_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.installed import InstalledReceipt, _run_bounded, verify_installed

VERSION = "2.0.1rc4"
DIST_NAME = "matryca_plumber-2.0.1rc4.dist-info"
TCKS = (
    "run_plumber_consumer_package_v1_tck.py",
    "run_plumber_graph_read_v1_tck.py",
    "run_plumber_graph_topology_v1_tck.py",
)


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
