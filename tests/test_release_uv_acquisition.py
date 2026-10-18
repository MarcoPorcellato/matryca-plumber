"""Synthetic-only checks for the qualification bootstrap; no real downloads."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import shlex
import stat
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import replace
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "linux-x86_64": ("Linux", "x86_64", "uv-x86_64-unknown-linux-gnu/uv"),
    "macos-arm64": ("Darwin", "arm64", "uv-aarch64-apple-darwin/uv"),
    "windows-x64": ("Windows", "AMD64", "uv.exe"),
}
PAYLOAD = b"synthetic bytes: never an executable"


@pytest.fixture
def helper(monkeypatch: pytest.MonkeyPatch) -> Any:
    path = ROOT / "scripts/release_qualification/uv_acquisition.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("qualified_uv_acquisition", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _archive(member: str, platform_name: str, *, link: bool = False) -> bytes:
    buffer = io.BytesIO()
    if platform_name == "windows-x64":
        with zipfile.ZipFile(buffer, "w") as zip_archive:
            zip_item = zipfile.ZipInfo(member)
            zip_item.create_system = 3
            zip_item.external_attr = (stat.S_IFLNK | 0o777 if link else stat.S_IFREG | 0o755) << 16
            zip_archive.writestr(zip_item, PAYLOAD)
    else:
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar_archive:
            tar_item = tarfile.TarInfo(member)
            tar_item.size = len(PAYLOAD)
            if link:
                tar_item.type = tarfile.SYMTYPE
                tar_item.linkname = "outside"
            tar_archive.addfile(tar_item, io.BytesIO(PAYLOAD))
    return buffer.getvalue()


class _Response(io.BytesIO):
    status = 200

    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(payload))


class _Transport:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.redirects: list[str] = []
        self.requests: list[str] = []

    def open(self, request: urllib.request.Request, *, timeout: float) -> _Response:
        assert 0 < timeout <= 10
        self.requests.append(request.full_url)
        assert not any(
            key.lower() in {"authorization", "cookie", "proxy-authorization"}
            for key in request.headers
        )
        if self.redirects:
            headers = Message()
            headers["Location"] = self.redirects.pop(0)
            raise urllib.error.HTTPError(request.full_url, 302, "redirect", headers, None)
        return _Response(self.payload)


def _bind(helper: Any, monkeypatch: pytest.MonkeyPatch, name: str, raw: bytes) -> _Transport:
    assert helper is not None, "The verified acquisition boundary is missing."
    system, machine, _ = PINS[name]
    monkeypatch.setattr(helper.platform, "system", lambda: system)
    monkeypatch.setattr(helper.platform, "machine", lambda: machine)
    monkeypatch.setitem(
        helper.ASSETS,
        name,
        replace(helper.ASSETS[name], size=len(raw), sha256=hashlib.sha256(raw).hexdigest()),
    )
    transport = _Transport(raw)
    monkeypatch.setattr(helper.urllib.request, "build_opener", lambda *args: transport)
    return transport


@pytest.mark.parametrize("name", list(PINS))
def test_archive_is_authenticated_and_verify_never_requests_network(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    raw = _archive(PINS[name][2], name)
    transport = _bind(helper, monkeypatch, name, raw)
    root = tmp_path / "owned"
    result = helper.acquire(root, tmp_path, name)
    executable = root / "bin" / ("uv.exe" if name == "windows-x64" else "uv")
    assert executable.read_bytes() == PAYLOAD
    assert result["executable_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert result["archive_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["expected_version"] == "0.12.19"
    assert len(transport.requests) == 1
    monkeypatch.setattr(
        helper.urllib.request,
        "build_opener",
        lambda *args: pytest.fail("verification requested network"),
    )
    assert helper.verify(root, tmp_path, name)["uv_path"] == str(executable.resolve())


@pytest.mark.parametrize("member", ["../uv", "/uv", "a\\uv", "C:uv", "other/uv", "UV"])
@pytest.mark.parametrize("name", ["linux-x86_64", "windows-x64"])
def test_wrong_or_unsafe_member_is_never_extracted(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, member: str
) -> None:
    _bind(helper, monkeypatch, name, _archive(member, name))
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, name)
    assert not (tmp_path / "owned/bin/uv").exists()
    assert not (tmp_path / "owned/bin/uv.exe").exists()


@pytest.mark.parametrize("name", list(PINS))
def test_archive_links_are_refused(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    _bind(helper, monkeypatch, name, _archive(PINS[name][2], name, link=True))
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, name)


@pytest.mark.parametrize("kind", ["existing", "symlink", "outside"])
def test_root_refusal_precedes_network(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    _bind(helper, monkeypatch, "linux-x86_64", b"not requested")
    monkeypatch.setattr(
        helper.urllib.request, "build_opener", lambda *args: pytest.fail("no request allowed")
    )
    root = tmp_path / "owned"
    if kind == "existing":
        root.mkdir()
    elif kind == "symlink":
        root.symlink_to(tmp_path, target_is_directory=True)
    else:
        root = tmp_path / "nested/owned"
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(root, tmp_path, "linux-x86_64")


@pytest.mark.parametrize("kind", ["short", "oversized", "digest", "malformed"])
def test_untrusted_bytes_fail_before_extraction(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    raw = (
        b"not an archive"
        if kind == "malformed"
        else _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    )
    _bind(helper, monkeypatch, "linux-x86_64", raw)
    asset = helper.ASSETS["linux-x86_64"]
    if kind == "short":
        monkeypatch.setitem(helper.ASSETS, "linux-x86_64", replace(asset, size=len(raw) + 1))
    elif kind == "oversized":
        monkeypatch.setitem(helper.ASSETS, "linux-x86_64", replace(asset, size=len(raw) - 1))
    elif kind == "digest":
        monkeypatch.setitem(helper.ASSETS, "linux-x86_64", replace(asset, sha256="0" * 64))
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert not (tmp_path / "owned/bin/uv").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/file",
        "https://example.com/file",
        "https://release-assets.githubusercontent.com.evil.invalid/file",
        "https://user:secret@release-assets.githubusercontent.com/file",
        "https://release-assets.githubusercontent.com:444/file",
        "https://release-assets.githubusercontent.com/file#fragment",
        "https://github.com/another/release",
    ],
)
def test_untrusted_redirect_is_never_contacted(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, url: str
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)
    transport.redirects = [url]
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert len(transport.requests) == 1


def test_redirect_budget_has_no_retry(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)
    transport.redirects = ["https://release-assets.githubusercontent.com/file"] * 4
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert len(transport.requests) == 4


@pytest.mark.parametrize("target", ["executable", "archive", "record", "symlink"])
def test_verify_does_not_trust_replacement_or_self_attestation(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    _bind(helper, monkeypatch, "linux-x86_64", raw)
    root = tmp_path / "owned"
    helper.acquire(root, tmp_path, "linux-x86_64")
    if target == "executable":
        (root / "bin/uv").write_bytes(b"replaced")
    elif target == "archive":
        (root / "archive.tar.gz").write_bytes(b"replaced")
    elif target == "symlink":
        (root / "bin/uv").unlink()
        (root / "bin/uv").symlink_to(tmp_path / "outside")
    else:
        record = json.loads((root / "acquisition.json").read_text())
        record["source"] = "0" * 40
        (root / "acquisition.json").write_text(json.dumps(record))
    with pytest.raises(helper.AcquisitionError):
        helper.verify(root, tmp_path, "linux-x86_64")


def test_newer_bootstrap_does_not_change_tooling_python(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    _bind(helper, monkeypatch, "linux-x86_64", raw)
    monkeypatch.setattr(helper.sys, "version_info", (3, 14, 0))
    monkeypatch.setenv("UV_PYTHON", "3.12")
    helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert helper.os.environ["UV_PYTHON"] == "3.12"
    monkeypatch.setattr(helper.platform, "machine", lambda: "arm64")
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "second", tmp_path, "linux-x86_64")


@pytest.mark.parametrize("kind", ["duplicate", "case_collision", "too_many", "too_large"])
def test_archive_inventory_is_bounded_before_extraction(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        names = [PINS["linux-x86_64"][2]]
        if kind == "duplicate":
            names.append(names[0])
        elif kind == "case_collision":
            names.append(names[0].upper())
        elif kind == "too_many":
            names.extend(f"extra-{i}" for i in range(33))
        for name in names:
            item = tarfile.TarInfo(name)
            item.size = 1
            archive.addfile(item, io.BytesIO(b"x"))
    _bind(helper, monkeypatch, "linux-x86_64", buffer.getvalue())
    if kind == "too_large":
        monkeypatch.setattr(helper, "MAX_EXECUTABLE_BYTES", 0)
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")


def test_native_lane_is_non_publishing() -> None:
    path = ROOT / ".github/workflows/uv-acquisition-qualification.yml"
    assert path.is_file(), "The non-publishing native lane is missing."
    workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["on"]) == {"pull_request", "push"}
    assert workflow["on"]["pull_request"]["types"] == ["opened", "synchronize"]
    job = workflow["jobs"]["bootstrap"]
    assert int(job["timeout-minutes"]) <= 10
    assert {(row["os"], row["platform"]) for row in job["strategy"]["matrix"]["include"]} == {
        ("ubuntu-24.04", "linux-x86_64"),
        ("macos-15", "macos-arm64"),
        ("windows-latest", "windows-x64"),
    }
    text = path.read_text()
    assert "workflow_dispatch" not in text and "id-token" not in text
    assert "uv python install" not in text and "uv sync" not in text
    assert "root_not_fresh" in text and "--version" in text


def _verification_script() -> str:
    value = yaml.load(
        (ROOT / ".github/workflows/uv-acquisition-qualification.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    steps = value["jobs"]["bootstrap"]["steps"]
    return str(
        next(step["run"] for step in steps if step.get("name") == "Verify selected uv acquisition")
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "valid",
        "missing_python",
        "missing_install",
        "missing_bin",
        "newer_python",
        "outside_install",
        "outside_bin",
    ],
)
def test_workflow_binding_guards_execute_before_helper_or_tool_use(
    tmp_path: Path, mutation: str
) -> None:
    root = str(tmp_path / "owned")
    environment = {
        "PATH": os.defpath,
        "UV_PYTHON": "3.12",
        "MATRYCA_UV_ROOT": root,
        "UV_PYTHON_INSTALL_DIR": root + "/python",
        "UV_PYTHON_BIN_DIR": root + "/python-bin",
    }
    if mutation.startswith("missing_"):
        key = {
            "missing_python": "UV_PYTHON",
            "missing_install": "UV_PYTHON_INSTALL_DIR",
            "missing_bin": "UV_PYTHON_BIN_DIR",
        }[mutation]
        environment.pop(key)
    elif mutation == "newer_python":
        environment["UV_PYTHON"] = "3.14"
    elif mutation == "outside_install":
        environment["UV_PYTHON_INSTALL_DIR"] = "/outside"
    elif mutation == "outside_bin":
        environment["UV_PYTHON_BIN_DIR"] = "/outside"
    guards = _verification_script().split("python -I -B ", 1)[0]
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", guards],
        env=environment,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert (result.returncode == 0) is (mutation == "valid")


def test_poisoned_path_is_refused_before_any_executable_runs(tmp_path: Path) -> None:
    root = tmp_path / "owned"
    trusted = root / "bin"
    trusted.mkdir(parents=True)
    poisoned = tmp_path / "poison"
    poisoned.mkdir()
    for path in (trusted / "uv", poisoned / "uv"):
        path.write_text('#!/bin/sh\nprintf used > "$SYNTHETIC_MARKER"\nprintf "uv 0.12.19\\n"\n')
        path.chmod(0o700)
    marker = tmp_path / "executed"
    environment = {
        "PATH": str(poisoned) + os.pathsep + os.defpath,
        "RUNNER_OS": "Linux",
        "RUNNER_TEMP": str(tmp_path),
        "MATRYCA_UV_ROOT": str(root),
        "MATRYCA_UV_PLATFORM": "linux-x86_64",
        "UV_PYTHON": "3.12",
        "UV_PYTHON_INSTALL_DIR": str(root / "python"),
        "UV_PYTHON_BIN_DIR": str(root / "python-bin"),
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "SYNTHETIC_MARKER": str(marker),
    }
    # The helper boundary is covered separately; exercise this real workflow shell guard.
    script = "python() { return 0; }\n" + _verification_script()
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", script],
        env=environment,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode != 0 and not marker.exists()


def test_body_byte_limit_is_enforced_without_a_content_length(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)

    class Chunked(_Response):
        def __init__(self) -> None:
            super().__init__(raw + b"x")
            self.headers = Message()

    monkeypatch.setattr(transport, "open", lambda request, timeout: Chunked())
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert (tmp_path / "owned/archive.tar.gz").stat().st_size <= len(raw)


def test_expired_deadline_does_not_start_a_request(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)
    monkeypatch.setattr(helper, "ATTEMPT_SECONDS", -1)
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert transport.requests == []


@pytest.mark.parametrize("metadata", ["unix_directory", "dos_directory"])
def test_selected_zip_member_requires_regular_metadata(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, metadata: str
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        item = zipfile.ZipInfo("uv.exe")
        item.create_system = 3
        item.external_attr = (stat.S_IFREG | 0o755) << 16
        if metadata == "unix_directory":
            item.external_attr = (stat.S_IFDIR | 0o755) << 16
        else:
            item.external_attr |= 0x10
        archive.writestr(item, PAYLOAD)
    _bind(helper, monkeypatch, "windows-x64", buffer.getvalue())
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "windows-x64")


@pytest.mark.parametrize(
    "kind", ["contiguous", "sparse", "pax", "gnu_long", "extension_budget", "truncated"]
)
def test_raw_tar_metadata_is_admitted_before_normalization(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    member = PINS["linux-x86_64"][2]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.GNU_FORMAT) as archive:
        if kind in ("pax", "gnu_long", "extension_budget"):
            for _ in range(33 if kind == "extension_budget" else 1):
                extra = tarfile.TarInfo("metadata")
                extra.type = tarfile.XGLTYPE if kind == "pax" else tarfile.GNUTYPE_LONGNAME
                data = b"13 comment=x\n" if kind == "pax" else member.encode() + b"\0"
                extra.size = len(data)
                archive.addfile(extra, io.BytesIO(data))
        item = tarfile.TarInfo(member)
        item.size = len(PAYLOAD)
        if kind == "contiguous":
            item.type = tarfile.CONTTYPE
        elif kind == "sparse":
            item.type = tarfile.GNUTYPE_SPARSE
        archive.addfile(item, io.BytesIO(PAYLOAD))
    raw = stream.getvalue()
    if kind == "truncated":
        raw = raw[:1024]
    _bind(helper, monkeypatch, "linux-x86_64", gzip.compress(raw))
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")


def test_transport_timeout_is_terminal_without_retry(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)
    calls = []

    def fail(request: Any, *, timeout: float) -> Any:
        calls.append((request.full_url, timeout))
        raise TimeoutError("synthetic transport timeout")

    monkeypatch.setattr(transport, "open", fail)
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert len(calls) == 1


def test_reparse_metadata_is_refused_before_network(
    helper: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = _archive(PINS["linux-x86_64"][2], "linux-x86_64")
    transport = _bind(helper, monkeypatch, "linux-x86_64", raw)
    original = Path.lstat

    class Reparse:
        st_file_attributes = 0x400

        def __init__(self, value: os.stat_result) -> None:
            self.st_mode = value.st_mode
            self.st_uid = value.st_uid

    monkeypatch.setattr(Path, "lstat", lambda path: Reparse(original(path)))
    with pytest.raises(helper.AcquisitionError):
        helper.acquire(tmp_path / "owned", tmp_path, "linux-x86_64")
    assert transport.requests == []


@pytest.mark.parametrize(
    "kind,minor",
    [("tooling", 12), ("tooling", 13), ("tooling", 14), ("runtime", 13), ("runtime", 12)],
)
def test_workflow_actual_interpreter_assertions_are_independent(kind: str, minor: int) -> None:
    codes = []
    for filename in ("release.yml", "og-public-artifact-qualification.yml"):
        workflow = yaml.load(
            (ROOT / ".github/workflows" / filename).read_text(), Loader=yaml.BaseLoader
        )
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                for line in step.get("run", "").splitlines():
                    if " -I -B -c " not in line or "sys.version_info[:2]" not in line:
                        continue
                    words = shlex.split(line)
                    code = words[words.index("-c") + 1]
                    if ("sys.argv[1]" in code) is (kind == "runtime"):
                        codes.append(code)
                        if kind == "runtime":
                            assert (
                                'runtime="$(uv python find --no-python-downloads "$RUNTIME_MINOR")"'
                                in step["run"]
                            )
    assert codes
    for code in codes:
        # Simulate a newer bootstrap selecting a wrong tooling/build interpreter,
        # or an independent 3.13 runtime row, using the actual workflow assertion.
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                f"import sys; sys.version_info=(3,{minor},0); exec({code!r})",
                "3.13",
            ],
            capture_output=True,
            timeout=5,
            check=False,
        )
        assert (result.returncode == 0) is (minor == (13 if kind == "runtime" else 12))


@pytest.mark.parametrize(
    "field", ["st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "length"]
)
@pytest.mark.parametrize("phase", ["opened", "after"])
def test_changed_read_emits_only_captured_boolean_diagnostics(
    helper: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    field: str,
    phase: str,
) -> None:
    path = tmp_path / "private-secret-name"
    path.write_bytes(PAYLOAD)
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    values = {name: 98765432101234567 for name in fields}
    values["st_size"] = len(PAYLOAD) + (1 if field == "length" else 0)
    before = SimpleNamespace(**values)
    changed = dict(values)
    if field != "length":
        changed[field] += 1
    opened = SimpleNamespace(**(changed if phase == "opened" else values))
    after = SimpleNamespace(**(changed if phase == "after" else values))
    captured = iter((before, after))
    monkeypatch.setattr(helper, "_metadata", lambda path: next(captured))
    monkeypatch.setattr(helper.os, "fstat", lambda fd: opened)
    with pytest.raises(helper.AcquisitionError, match="^file_changed$"):
        helper._read_file(path, 4096)
    output = capsys.readouterr()
    assert output.out == "" and len(output.err.encode()) <= 4096
    diagnostic = json.loads(output.err)
    assert set(diagnostic) == {
        "code",
        "implementation",
        "version",
        "before_opened",
        "before_after",
        "length_equal",
    }
    assert diagnostic["code"] == "file_changed"
    assert diagnostic["implementation"] == sys.implementation.name
    assert diagnostic["version"] == dict(
        zip(("major", "minor", "micro", "releaselevel", "serial"), sys.version_info, strict=True)
    )
    for comparison, target in (("before_opened", "opened"), ("before_after", "after")):
        assert set(diagnostic[comparison]) == set(fields)
        for name in fields:
            value = diagnostic[comparison][name]
            assert type(value) is bool
            assert value is not (field == name and phase == target)
    assert diagnostic["length_equal"] is (field != "length")
    assert "private-secret-name" not in output.err and str(tmp_path) not in output.err
    assert "98765432101234567" not in output.err
    with pytest.raises(StopIteration):
        next(captured)


def test_stable_read_emits_no_diagnostic(
    helper: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "stable"
    path.write_bytes(PAYLOAD)
    assert helper._read_file(path, 4096) == PAYLOAD
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "phase", ["acquisition", "verification", "refusal", "success", "missing_observation"]
)
def test_native_report_executes_truthful_failure_ordering(tmp_path: Path, phase: str) -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/uv-acquisition-qualification.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    job = workflow["jobs"]["bootstrap"]
    assert "MATRYCA_UV_ROOT" not in job["env"]
    assert all("runner." not in value for value in job["env"].values())
    assert job["env"]["MATRYCA_UV_PLATFORM"] == "${{ matrix.platform }}"
    step = next(
        item for item in job["steps"] if item.get("name") == "Emit sanitized bootstrap evidence"
    )
    assert step["env"]["MATRYCA_UV_ROOT"] == "${{ runner.temp }}/matryca-uv"
    outcomes = {
        "acquisition": ("failure", "skipped", "skipped"),
        "verification": ("success", "failure", "skipped"),
        "refusal": ("success", "success", "failure"),
        "success": ("success", "success", "success"),
        "missing_observation": ("success", "success", "success"),
    }[phase]
    marker = tmp_path / "helper-calls"
    record = {
        "expected_version": "0.12.19",
        "source": "s" * 40,
        "asset": "synthetic",
        "archive_sha256": "a" * 64,
        "archive_bytes": 4,
        "executable_sha256": "b" * 64,
    }
    prefix = (
        'python() { if [ "${3:-}" = scripts/release_qualification/uv_acquisition.py ]; then '
        + 'printf called >> "$SYNTHETIC_MARKER"; '
        + "printf '%s\\n' \"$SYNTHETIC_RECORD\"; else "
        + shlex.quote(sys.executable)
        + ' "$@"; fi; }\n'
    )
    environment = {
        "PATH": os.defpath,
        "RUNNER_TEMP": str(tmp_path),
        "MATRYCA_UV_PLATFORM": "linux-x86_64",
        "MATRYCA_UV_ROOT": str(tmp_path / "not-created"),
        "ACQUISITION_OUTCOME": outcomes[0],
        "VERIFICATION_OUTCOME": outcomes[1],
        "REFUSAL_OUTCOME": outcomes[2],
        "OBSERVED_UV_VERSION": "0.12.19" if phase in ("refusal", "success") else "",
        "REFUSAL_STATUS": "PASS" if phase in ("success", "missing_observation") else "",
        "SYNTHETIC_MARKER": str(marker),
        "SYNTHETIC_RECORD": json.dumps(record),
    }
    result = subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", prefix + str(step["run"])],
        env=environment,
        capture_output=True,
        timeout=5,
        check=False,
    )
    if phase == "missing_observation":
        assert result.returncode != 0
        return
    assert result.returncode == 0, result.stderr.decode()
    report = json.loads((tmp_path / "bootstrap-report.json").read_text())
    assert report["status"] == ("PASS" if phase == "success" else "FAIL")
    assert report["acquisition"] == ("FAIL" if phase == "acquisition" else "PASS")
    assert report["verification"] == (
        "NOT_RUN" if phase == "acquisition" else "FAIL" if phase == "verification" else "PASS"
    )
    assert report["existing_root_refusal"] == (
        "PASS" if phase == "success" else "FAIL" if phase == "refusal" else "NOT_RUN"
    )
    assert marker.exists() is (phase == "success")
    if phase == "success":
        assert report["observed_version"] == "0.12.19"
        assert all(report[k] == v for k, v in record.items())
    else:
        assert "executable_sha256" not in report and "source" not in report
