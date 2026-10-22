from __future__ import annotations

import copy
import hashlib
import json
import os
import selectors
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any, cast

import pytest
from matryca_plumber.graph_gateway.resources import PackageResources


def _package_resources() -> PackageResources:
    from matryca_plumber.graph_gateway.resources import _load_package_resources

    return _load_package_resources()


def _validation_package() -> PackageResources:
    from matryca_plumber.graph_gateway.resources import PackageResources

    project = Path(__file__).resolve().parents[1]
    golden_path = (
        project / "matryca_plumber/graph_gateway/resources/og-v1/golden/topology.result.json"
    )
    schema_bytes = {
        key: (project / f"contracts/plumber.graph.{key}/v1/schema.json").read_bytes()
        for key in ("read", "topology")
    }
    descriptor = {
        "profile": "plumber.og.operational/v1",
        "operations": ["graph.identify", "graph.topology.snapshot.complete"],
        "wire": {
            "read": {"id": "read-1", "producer_profile_id": "rp", "consumer_profile_id": "rc"},
            "topology": {
                "id": "topology-1",
                "producer_profile_id": "tp",
                "consumer_profile_id": "tc",
            },
        },
    }
    descriptor_bytes = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    assets = {
        "dependency-profile.json": b'{"project":{"version":"2.0.1rc4"}}',
        "fixture-manifest.json": (
            b'{"independent_expectations":{"page_nodes":5,"block_nodes":9,'
            b'"reference_edges":2,"result_complete":true}}'
        ),
        "golden/topology.result.json": golden_path.read_bytes(),
    }
    return PackageResources(
        descriptor=descriptor,
        descriptor_bytes=descriptor_bytes,
        descriptor_sha256=hashlib.sha256(descriptor_bytes).hexdigest(),
        manifest={},
        manifest_bytes=b"{}",
        manifest_sha256=hashlib.sha256(b"{}").hexdigest(),
        assets=assets,
        schema_digests={},
        schema_bytes=schema_bytes,
        module_bytes={},
        package_paths=frozenset(),
    )


def _valid_tck_response(package: PackageResources) -> tuple[dict[str, Any], bytes]:
    from matryca_plumber.graph_gateway.wire import _encode, _snapshot_document

    from tests.test_og_graph_gateway_wire import _inputs

    profile, versions, session, identity, topology = _inputs()
    golden = json.loads(package.assets["golden/topology.result.json"])
    revision = golden["provenance"]["source_revision"]
    session["source_revision"] = revision
    identity["source_revision"] = revision
    topology["source_revision"] = revision
    topology["result"] = golden
    output = _snapshot_document(profile, versions, session, identity, topology)
    output["descriptor_sha256"] = package.descriptor_sha256
    return output, _encode(output)


def test_operational_resource_bundle_authenticates_declared_bytes() -> None:
    package = _package_resources()
    descriptor = package.descriptor

    assert package.descriptor_sha256 == hashlib.sha256(package.descriptor_bytes).hexdigest()
    assert descriptor["profile"] == "plumber.og.operational/v1"
    assert descriptor["qualification"] == "unqualified"
    assert descriptor["source_mode"] == "og_markdown"
    assert [row["state"] for row in descriptor["matrix"]] == ["planned"] * 4
    assert package.manifest_sha256 == hashlib.sha256(package.manifest_bytes).hexdigest()
    assert set(package.assets) == set(package.manifest["files"])
    assert package.schema_digests == {
        "read": "250438c57580c811c3e10b2a59089ffbb23ea2f1f66c4c53acc8ace0a9ee8569",
        "topology": "613f765376f2091b3dad2569ce19d9931f455b026f5ed495178526e87da1397a",
    }
    for name, payload in package.assets.items():
        assert hashlib.sha256(payload).hexdigest() == package.manifest["files"][name]


def test_tck_fixture_manifest_admits_actual_shipped_fixture_bytes() -> None:
    from matryca_plumber.graph_gateway.tck import _fixture_files

    files = _fixture_files(_package_resources())

    assert hashlib.sha256(files["pages/B.md"]).hexdigest() == (
        "83680d7150820edfd610e23e3e4b41f263337c86bccc4893f85485093d416bd9"
    )


@pytest.mark.parametrize(
    ("mutation", "package_paths"),
    [
        ("asset", None),
        ("extra", None),
        ("alias", None),
        ("duplicate-key", None),
        ("schema-version-bool", None),
    ],
)
def test_operational_resource_mutation_is_fail_closed(
    mutation: str, package_paths: set[str] | None
) -> None:
    from matryca_plumber.graph_gateway.resources import (
        PackageResourceError,
        _verify_package_resources,
    )

    package = _package_resources()
    assets = dict(package.assets)
    manifest_bytes = package.manifest_bytes
    available = set(package.package_paths if package_paths is None else package_paths)
    if mutation == "asset":
        name = next(iter(assets))
        assets[name] += b"tampered"
    elif mutation == "extra":
        assets["unexpected.json"] = b"{}\n"
        available.add("resources/og-v1/unexpected.json")
    elif mutation == "alias":
        manifest = json.loads(manifest_bytes)
        name = next(iter(manifest["files"]))
        manifest["files"][f"./{name}"] = manifest["files"].pop(name)
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    elif mutation == "schema-version-bool":
        manifest = json.loads(manifest_bytes)
        manifest["schema_version"] = True
        manifest_bytes = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
    else:
        manifest_bytes = b'{"schema_version":1,"files":{},"files":{}}\n'

    with pytest.raises(PackageResourceError):
        _verify_package_resources(
            package.descriptor_bytes,
            manifest_bytes,
            assets,
            available,
            package.schema_bytes,
            package.module_bytes,
        )


@pytest.mark.parametrize(
    "binding", ["manifest-profile", "descriptor-manifest", "descriptor-profile"]
)
def test_operational_metadata_links_reject_independent_digest_tampering(binding: str) -> None:
    from matryca_plumber.graph_gateway.resources import (
        PackageResourceError,
        _verify_package_resources,
    )

    package = _package_resources()
    _verify_package_resources(
        package.descriptor_bytes,
        package.manifest_bytes,
        package.assets,
        package.package_paths,
        package.schema_bytes,
        package.module_bytes,
    )
    descriptor = json.loads(package.descriptor_bytes)
    manifest = json.loads(package.manifest_bytes)
    manifest_bytes = package.manifest_bytes
    if binding == "manifest-profile":
        manifest["files"]["dependency-profile.json"] = "0" * 64
        manifest_bytes = json.dumps(manifest).encode()
        descriptor["resource_digests"]["manifest"] = hashlib.sha256(manifest_bytes).hexdigest()
    elif binding == "descriptor-manifest":
        descriptor["resource_digests"]["manifest"] = "0" * 64
    else:
        descriptor["resource_digests"]["dependency_profile"] = "0" * 64

    with pytest.raises(PackageResourceError):
        _verify_package_resources(
            json.dumps(descriptor).encode(),
            manifest_bytes,
            package.assets,
            package.package_paths,
            package.schema_bytes,
            package.module_bytes,
        )


def _assert_certifi_security_record(lock: dict[str, Any], requirements: bytes) -> None:
    """Reject a stale or unbound trust-store selection in either runtime pin."""
    records = [item for item in lock["package"] if item["name"] == "certifi"]
    assert len(records) == 1
    assert records[0] == {
        "name": "certifi",
        "version": "2026.10.19",
        "source": {"registry": "https://pypi.org/simple"},
        "sdist": {
            "url": (
                "https://files.pythonhosted.org/packages/a6/bd/"
                "1436c50cc46699de0230fbaacc1d1de7bfec413176099949e9d5112e88f2/"
                "certifi-2026.10.19.tar.gz"
            ),
            "hash": "sha256:035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae",
            "size": 137598,
            "upload-time": "2026-10-20T02:24:16.604Z",
        },
        "wheels": [
            {
                "url": (
                    "https://files.pythonhosted.org/packages/c4/51/"
                    "29046e48f693c54e5b7412216d447a1d8362c9653148d98c02cdf65fa733/"
                    "certifi-2026.10.19-py3-none-any.whl"
                ),
                "hash": "sha256:42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b",
                "size": 136464,
                "upload-time": "2026-10-20T02:24:15.072Z",
            }
        ],
    }
    lines = requirements.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith(b"certifi==")]
    assert len(starts) == 1
    start = starts[0]
    end = start + 1
    while end < len(lines) and lines[end].startswith(b" "):
        end += 1
    assert lines[start:end] == [
        b"certifi==2026.10.19 \\",
        b"    --hash=sha256:035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae \\",
        b"    --hash=sha256:42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b",
    ]


def test_certifi_runtime_lock_and_export_match_official_fixed_release() -> None:
    project = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
    requirements = (
        project
        / "matryca_plumber/graph_gateway/resources/og-v1/requirements-og-v1-parser-1.9.0.txt"
    ).read_bytes()
    _assert_certifi_security_record(lock, requirements)


@pytest.mark.parametrize(
    "mutation",
    [
        "lock-version",
        "export-version",
        "wheel-hash",
        "sdist-hash",
        "registry",
        "artifact-url",
        "missing-export-hash",
        "duplicate-record",
    ],
)
def test_certifi_security_record_rejects_stale_or_tampered_input(mutation: str) -> None:
    project = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
    requirements = (
        project
        / "matryca_plumber/graph_gateway/resources/og-v1/requirements-og-v1-parser-1.9.0.txt"
    ).read_bytes()
    record = next(item for item in lock["package"] if item["name"] == "certifi")
    if mutation == "lock-version":
        record["version"] = "2026.5.20"
    elif mutation == "export-version":
        requirements = requirements.replace(b"certifi==2026.10.19", b"certifi==2026.5.20", 1)
    elif mutation == "wheel-hash":
        record["wheels"][0]["hash"] = "sha256:" + "0" * 64
    elif mutation == "sdist-hash":
        record["sdist"]["hash"] = "sha256:" + "0" * 64
    elif mutation == "registry":
        record["source"]["registry"] = "https://example.invalid/simple"
    elif mutation == "artifact-url":
        record["sdist"]["url"] = "https://example.invalid/certifi-2026.10.19.tar.gz"
    elif mutation == "missing-export-hash":
        requirements = requirements.replace(
            b"035c1e85572b141bf1c3a3eff0e33a8eb74917522f2559075ff8d2fea780a1ae", b"", 1
        )
    else:
        lock["package"].append(copy.deepcopy(record))

    with pytest.raises(AssertionError):
        _assert_certifi_security_record(lock, requirements)


def test_hash_locked_dependency_profile_matches_parser_lock_closure() -> None:
    package = _package_resources()
    profile = json.loads(package.assets["dependency-profile.json"])

    assert profile["profile_id"] == "og-v1-parser-1.9.0"
    assert profile["parser"] == {"name": "logseq-matryca-parser", "version": "1.9.0"}
    assert profile["lock_source"] == "uv.lock"
    assert profile["matrix"] == package.descriptor["matrix"]
    assert profile["qualification"] == "unqualified"
    assert profile["project"] == {"name": "matryca-plumber", "version": "2.1.0a3"}
    assert profile["export"]["entry_count"] == 73
    assert profile["export"]["kind"] == "uv-export-runtime-closure"
    requirements = package.assets["requirements-og-v1-parser-1.9.0.txt"]
    package_prefix = profile["export"].get("package_prefix")
    native_sha256 = profile["export"].get("native_sha256")
    assert package_prefix == "--require-hashes\n"
    assert native_sha256 == "6d138edc0b82853752d22f1f118b5a13d5b6517ef12677c00360e4a98de35ff0"
    assert requirements.startswith(package_prefix.encode())
    native_requirements = requirements[len(package_prefix.encode()) :]
    assert hashlib.sha256(native_requirements).hexdigest() == native_sha256
    assert b"aiohttp==3.14.4 \\\n" in requirements
    assert b"yarl==1.25.1 \\\n" in requirements
    assert b"certifi==2026.10.19 \\\n" in requirements
    assert b"gitpython==3.2.1 \\\n" in requirements
    assert b"multidict==6.9.1 \\\n" in requirements
    assert b"logseq-matryca-parser==1.9.0 \\\n" in requirements
    pinned_entries = sum(
        b"==" in line and not line.startswith(b" ") for line in requirements.splitlines()
    )
    assert pinned_entries == profile["export"]["entry_count"]
    assert hashlib.sha256(requirements).hexdigest() == profile["requirements"]["sha256"]
    lock = Path(__file__).resolve().parents[1] / "uv.lock"
    assert hashlib.sha256(lock.read_bytes()).hexdigest() == profile["lock_sha256"]


def test_code_module_byte_changes_fail_descriptor_authentication() -> None:
    from matryca_plumber.graph_gateway.resources import (
        PackageResourceError,
        _verify_package_resources,
    )

    package = _package_resources()
    modules = dict(package.module_bytes)
    modules["consumer.py"] += b"# changed\n"
    with pytest.raises(PackageResourceError):
        _verify_package_resources(
            package.descriptor_bytes,
            package.manifest_bytes,
            package.assets,
            package.package_paths,
            package.schema_bytes,
            modules,
        )


def test_package_loader_rejects_unsafe_module_path_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    import matryca_plumber.graph_gateway.resources as package_resources
    from matryca_plumber.graph_gateway.resources import PackageResourceError

    project = Path(__file__).resolve().parents[1]
    gateway = tmp_path / "matryca_plumber" / "graph_gateway"
    shutil.copytree(
        project / "matryca_plumber/graph_gateway/resources/og-v1",
        gateway / "resources/og-v1",
    )
    for module_name in ("consumer.py", "tck.py"):
        shutil.copy2(project / "matryca_plumber/graph_gateway" / module_name, gateway)
    descriptor_path = gateway / "resources/og-v1/descriptor.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["code_modules"][0]["path"] = "../outside.py"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    outside = gateway.parent / "outside.py"
    outside.write_bytes(b"synthetic outside module")

    real_open = Path.open
    opened_outside: list[Path] = []

    def track_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.resolve(strict=False) == outside:
            opened_outside.append(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(package_resources, "files", lambda _package: gateway)
    monkeypatch.setattr(Path, "open", track_open)
    with pytest.raises(PackageResourceError):
        package_resources._load_package_resources()
    assert opened_outside == []


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_package_loader_rejects_nonregular_module_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    import os
    import shutil

    import matryca_plumber.graph_gateway.resources as package_resources
    from matryca_plumber.graph_gateway.resources import PackageResourceError

    project = Path(__file__).resolve().parents[1]
    gateway = tmp_path / "matryca_plumber" / "graph_gateway"
    shutil.copytree(
        project / "matryca_plumber/graph_gateway/resources/og-v1",
        gateway / "resources/og-v1",
    )
    module_path = gateway / "consumer.py"
    shutil.copy2(project / "matryca_plumber/graph_gateway/consumer.py", module_path)
    module_path.unlink()
    if kind == "symlink":
        outside = tmp_path / "outside.py"
        outside.write_bytes(b"synthetic outside module")
        module_path.symlink_to(outside)
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFO creation is unavailable on this platform")
        os.mkfifo(module_path)

    real_open = Path.open
    attempted_module_open: list[Path] = []

    def guard_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == module_path:
            attempted_module_open.append(path)
            raise OSError("synthetic blocked special-file open")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(package_resources, "files", lambda _package: gateway)
    monkeypatch.setattr(Path, "open", guard_open)
    with pytest.raises(PackageResourceError):
        package_resources._load_package_resources()
    assert attempted_module_open == []


def test_package_loader_rejects_symlink_resource_root_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    import matryca_plumber.graph_gateway.resources as package_resources
    from matryca_plumber.graph_gateway.resources import PackageResourceError

    project = Path(__file__).resolve().parents[1]
    gateway = tmp_path / "matryca_plumber" / "graph_gateway"
    shutil.copytree(
        project / "matryca_plumber/graph_gateway/resources/og-v1",
        gateway / "resources/og-v1",
    )
    root = gateway / "resources/og-v1"
    target = gateway / "resources/og-v1-target"
    root.rename(target)
    root.symlink_to(target, target_is_directory=True)

    real_open = Path.open
    opened_resources: list[Path] = []

    def track_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if target in path.parents or path == target:
            opened_resources.append(path)
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(package_resources, "files", lambda _package: gateway)
    monkeypatch.setattr(Path, "open", track_open)
    with pytest.raises(PackageResourceError):
        package_resources._load_package_resources()
    assert opened_resources == []


def test_consumer_group_finalizer_error_still_uses_kill_reap_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    children = []

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def fail_before_termination(*_args: object, **_kwargs: object) -> bool:
        raise KeyboardInterrupt("synthetic group finalizer interruption")

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    monkeypatch.setattr(consumer, "_cleanup_group", fail_before_termination)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=0.5,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is False
    assert "group_finalize_failed" in failure.value.cleanup_events
    assert children[0].poll() is not None
    assert consumer._group_state(children[0].pid) is False


def test_consumer_finalizes_unregistered_pipes_after_deadline_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    real_monotonic = consumer.time.monotonic
    calls = 0
    children = []

    class TrackedPipe:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        @property
        def closed(self) -> bool:
            return bool(self.stream.closed)

        def fileno(self) -> int:
            return int(self.stream.fileno())

        def close(self) -> None:
            self.stream.close()

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        child.stdout = TrackedPipe(child.stdout)
        child.stderr = TrackedPipe(child.stderr)
        children.append(child)
        return child

    def interrupt_first_clock_read() -> float:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("synthetic deadline initialization interruption")
        return float(real_monotonic())

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    monkeypatch.setattr(consumer.time, "monotonic", interrupt_first_clock_read)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=0.5,
        )
    assert failure.value.reason == "interrupted"
    assert failure.value.cleanup_ok is True
    assert children[0].poll() is not None
    assert children[0].stdout.closed is True
    assert children[0].stderr.closed is True


def test_consumer_close_after_cleanup_deadline_is_not_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    children = []

    class SlowClosePipe:
        def __init__(self, stream: Any) -> None:
            self.stream = stream

        @property
        def closed(self) -> bool:
            return bool(self.stream.closed)

        def fileno(self) -> int:
            return int(self.stream.fileno())

        def close(self) -> None:
            self.stream.close()
            time.sleep(0.05)

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        child.stdout = SlowClosePipe(child.stdout)
        child.stderr = SlowClosePipe(child.stderr)
        children.append(child)
        return child

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "pass"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=0.02,
        )
    assert failure.value.reason == "cleanup_error"
    assert failure.value.cleanup_ok is False
    assert "cleanup_deadline_exceeded" in failure.value.cleanup_events
    assert children[0].poll() is not None


def test_consumer_reads_bounded_child_output_and_reaps_it(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.consumer import _run_child

    result = _run_child(
        [sys.executable, "-I", "-B", "-c", "import sys;print('ok');print('diag',file=sys.stderr)"],
        cwd=tmp_path,
        env={"LC_ALL": "C", "LANG": "C"},
        execution_timeout=3,
        cleanup_budget=2,
    )

    assert result.returncode == 0
    assert result.stdout == b"ok\n"
    assert result.stderr == b"diag\n"
    assert result.cleanup_ok is True


@pytest.mark.parametrize(
    ("stream", "expected"), [("stdout", "stdout_overflow"), ("stderr", "stderr_overflow")]
)
def test_consumer_overflow_terminates_owned_group(
    tmp_path: Path, stream: str, expected: str
) -> None:
    from matryca_plumber.graph_gateway.consumer import ChildFailure, _run_child

    expression = (
        "import sys;sys.stdout.write('x'*4096);sys.stdout.flush()"
        if stream == "stdout"
        else "import sys;sys.stderr.write('x'*4096);sys.stderr.flush()"
    )
    with pytest.raises(ChildFailure) as failure:
        _run_child(
            [sys.executable, "-I", "-B", "-c", expression],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=2,
            max_stdout_bytes=32,
            max_stderr_bytes=32,
        )
    assert failure.value.reason == expected
    assert failure.value.cleanup_ok is True


def test_consumer_timeout_terminates_direct_child(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.consumer import ChildFailure, _run_child

    with pytest.raises(ChildFailure) as failure:
        _run_child(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=2,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is True


def test_consumer_escalates_to_kill_when_child_ignores_term(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.consumer import ChildFailure, _run_child

    with pytest.raises(ChildFailure) as failure:
        _run_child(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)",
            ],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=0.4,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is True


def test_consumer_selector_failure_still_cleans_owned_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    children = []

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def broken_selector() -> object:
        raise OSError("private selector failure")

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    monkeypatch.setattr(consumer.selectors, "DefaultSelector", broken_selector)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=1,
        )
    assert failure.value.reason == "internal"
    assert failure.value.cleanup_ok is True
    assert children[0].poll() is not None


def test_consumer_read_and_cleanup_errors_preserve_failure_and_report_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    real_killpg = consumer.os.killpg
    children = []

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        children.append(child)
        monkeypatch.setattr(consumer.os, "read", read_error)
        return child

    def read_error(_fd: int, _size: int) -> bytes:
        raise OSError("private read failure")

    def signal_then_report_error(group_id: int, signal_number: int) -> None:
        real_killpg(group_id, signal_number)
        if signal_number == consumer.signal.SIGTERM:
            raise OSError("private cleanup diagnostic")

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    monkeypatch.setattr(consumer.os, "killpg", signal_then_report_error)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import time;print('ready',flush=True);time.sleep(30)",
            ],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=1,
        )
    assert failure.value.reason == "read_error"
    assert failure.value.cleanup_ok is False
    assert "term_signal_failed" in failure.value.cleanup_events
    assert failure.value.cleanup_events[:3] == (
        "term_signal_failed",
        "term_signal_type_os_error_failed",
        "term_signal_errno_unavailable_failed",
    )
    assert set(failure.value.cleanup_events).issubset(
        {
            "term_signal_failed",
            "term_signal_type_os_error_failed",
            "term_signal_errno_unavailable_failed",
            "kill_signal_failed",
        }
    )
    assert children[0].poll() is not None


def test_consumer_pipe_selector_close_error_does_not_skip_finalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_selector = consumer.selectors.DefaultSelector

    class CloseErrorSelector:
        def __init__(self) -> None:
            self.selector = real_selector()

        def register(self, *args: object, **kwargs: object) -> object:
            return self.selector.register(*args, **kwargs)

        def select(self, *args: object, **kwargs: object) -> object:
            return self.selector.select(*args, **kwargs)

        def unregister(self, *args: object, **kwargs: object) -> object:
            return self.selector.unregister(*args, **kwargs)

        def get_map(self) -> object:
            return self.selector.get_map()

        def close(self) -> None:
            self.selector.close()
            raise OSError("private close failure")

    monkeypatch.setattr(consumer.selectors, "DefaultSelector", CloseErrorSelector)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "pass"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=1,
        )
    assert failure.value.reason == "cleanup_error"
    assert failure.value.cleanup_ok is False
    assert failure.value.cleanup_events == ("selector_close_failed",)


def test_consumer_reaps_after_interrupted_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_wait = consumer.subprocess.Popen.wait
    calls = 0

    def interrupt_once(process: Any, timeout: float | None = None) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InterruptedError("private wait interruption")
        return real_wait(process, timeout=timeout)

    monkeypatch.setattr(consumer.subprocess.Popen, "wait", interrupt_once)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)",
            ],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=0.4,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is True
    assert failure.value.cleanup_events == ()
    assert calls >= 2


def test_consumer_pipe_close_error_does_not_skip_group_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_popen = consumer.subprocess.Popen
    children = []

    class CloseErrorPipe:
        def __init__(self, stream: Any, child: Any) -> None:
            self.stream = stream
            self.child = child

        def fileno(self) -> int:
            return int(self.stream.fileno())

        @property
        def closed(self) -> bool:
            return bool(self.stream.closed)

        def close(self) -> None:
            assert self.child.poll() is not None
            self.stream.close()
            raise OSError("private pipe close failure")

    def wrap_pipes(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        child.stdout = CloseErrorPipe(child.stdout, child)
        child.stderr = CloseErrorPipe(child.stderr, child)
        children.append(child)
        return child

    monkeypatch.setattr(consumer.subprocess, "Popen", wrap_pipes)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import os,time;os.close(1);os.close(2);time.sleep(30)",
            ],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=0.5,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is False
    assert failure.value.cleanup_events == ("pipe_close_failed",)
    assert children[0].poll() is not None


def test_consumer_retries_interrupted_selector_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_selector = consumer.selectors.DefaultSelector
    calls = 0

    class InterruptedSelector:
        def __init__(self) -> None:
            self.selector = real_selector()

        def register(self, *args: object, **kwargs: object) -> object:
            return self.selector.register(*args, **kwargs)

        def select(self, *args: object, **kwargs: object) -> object:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise InterruptedError("private selector interruption")
            return self.selector.select(*args, **kwargs)

        def unregister(self, *args: object, **kwargs: object) -> object:
            return self.selector.unregister(*args, **kwargs)

        def get_map(self) -> object:
            return self.selector.get_map()

        def close(self) -> None:
            self.selector.close()

    monkeypatch.setattr(consumer.selectors, "DefaultSelector", InterruptedSelector)
    result = consumer._run_child(
        [sys.executable, "-I", "-B", "-c", "print('ok')"],
        cwd=tmp_path,
        env={"LC_ALL": "C", "LANG": "C"},
        execution_timeout=3,
        cleanup_budget=1,
    )
    assert result.stdout == b"ok\n"
    assert result.cleanup_ok is True
    assert calls >= 2


def test_consumer_uses_one_group_finalizer_and_keeps_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer_module

    consumer: Any = cast(Any, consumer_module)

    real_cleanup_group = consumer._cleanup_group
    calls = 0
    children = []
    real_popen = consumer.subprocess.Popen

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def cleanup_then_interrupt(
        process: Any, deadline: float, events: list[str], **kwargs: Any
    ) -> Any:
        nonlocal calls
        calls += 1
        real_cleanup_group(process, deadline, events, **kwargs)
        raise KeyboardInterrupt("private finalizer interruption")

    monkeypatch.setattr(consumer.subprocess, "Popen", capture_child)
    monkeypatch.setattr(consumer, "_cleanup_group", cleanup_then_interrupt)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=0.1,
            cleanup_budget=0.5,
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_ok is False
    assert failure.value.cleanup_events == ("group_finalize_failed",)
    assert calls == 1
    assert children[0].poll() is not None


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("read", "result", "graph_id"), "foreign-graph"),
        (("read", "id"), "foreign-read"),
        (("read", "producer_profile_id"), "foreign-producer"),
        (("read", "operation"), "page.read"),
        (("topology", "id"), "foreign-topology"),
        (("topology", "consumer_profile_id"), "foreign-consumer"),
    ],
)
def test_tck_rejects_wire_identity_or_binding_mismatch(
    field_path: tuple[str, ...], value: str
) -> None:
    from matryca_plumber.graph_gateway.tck import TCKFailure, _validate_success_response
    from matryca_plumber.graph_gateway.wire import _encode

    package = _validation_package()
    output, _ = _valid_tck_response(package)
    target = output
    for component in field_path[:-1]:
        target = target[component]
    target[field_path[-1]] = value
    with pytest.raises(TCKFailure):
        _validate_success_response(_encode(output), package)


@pytest.mark.parametrize("mutation", ["preorder", "parentage", "ordinal", "edge", "edge-order"])
def test_tck_validates_complete_topology_structure_without_golden(mutation: str) -> None:
    from matryca_plumber.graph_gateway.tck import TCKFailure, _validate_success_response
    from matryca_plumber.graph_gateway.wire import _encode

    package = _validation_package()
    output, _ = _valid_tck_response(package)
    result = output["topology"]["result"]
    if mutation == "preorder":
        result["nodes"][1], result["nodes"][2] = result["nodes"][2], result["nodes"][1]
    elif mutation == "parentage":
        result["nodes"][1]["parent_id"] = None
    elif mutation == "ordinal":
        result["nodes"][10]["ordinal"] = 8
    elif mutation == "edge":
        result["edges"][0]["target_id"] = "missing-node"
    else:
        result["edges"].reverse()
    with pytest.raises(TCKFailure, match="topology_structure"):
        _validate_success_response(_encode(output), package, require_golden=False)


def test_tck_repeat_requires_fresh_session_id() -> None:
    from copy import deepcopy

    from matryca_plumber.graph_gateway.tck import TCKFailure, _assert_repeat_response

    package = _validation_package()
    first, _ = _valid_tck_response(package)
    repeated = deepcopy(first)
    with pytest.raises(TCKFailure, match="repeat_session_reused"):
        _assert_repeat_response(first, repeated)
    repeated["read"]["session"]["id"] = "repeat-session"
    repeated["topology"]["request"]["session_id"] = "repeat-session"
    repeated["topology"]["session"]["id"] = "repeat-session"
    _assert_repeat_response(first, repeated)


def test_tck_tracks_unique_session_ids_across_all_successful_phases() -> None:
    from copy import deepcopy

    from matryca_plumber.graph_gateway.tck import TCKFailure, _assert_fresh_session

    package = _validation_package()
    first, _ = _valid_tck_response(package)
    first_id = first["read"]["session"]["id"]
    seen = {first_id}
    for phase in ("repeat", "relocation", "source_change"):
        reused = deepcopy(first)
        with pytest.raises(TCKFailure, match="session_reused"):
            _assert_fresh_session(reused, seen)
        fresh = deepcopy(first)
        session_id = f"{phase}-session"
        fresh["read"]["session"]["id"] = session_id
        fresh["topology"]["request"]["session_id"] = session_id
        fresh["topology"]["session"]["id"] = session_id
        _assert_fresh_session(fresh, seen)
        seen.add(session_id)
    assert seen == {first_id, "repeat-session", "relocation-session", "source_change-session"}


def test_tck_source_mutation_must_change_revision_and_golden_result() -> None:
    from copy import deepcopy

    from matryca_plumber.graph_gateway.tck import TCKFailure, _assert_source_change

    package = _validation_package()
    original, _ = _valid_tck_response(package)
    changed = deepcopy(original)
    changed["read"]["source_revision"] = "changed-revision"
    changed["topology"]["source_revision"] = "changed-revision"
    with pytest.raises(TCKFailure, match="source_change_missed"):
        _assert_source_change(original, changed)


def test_tck_environment_fingerprint_binds_distribution_and_resource_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    import matryca_plumber.graph_gateway.tck as tck

    package = _validation_package()

    class Distribution:
        def __init__(self, version: str, record: str) -> None:
            self.metadata = {"Name": "synthetic-dependency"}
            self.version = version
            self.record = record

        def read_text(self, _name: str) -> str:
            return self.record

    current = [Distribution("1.0", "first-record")]
    artifact_state = ["initial-artifact-inventory"]
    mutable_tck: Any = cast(Any, tck)
    monkeypatch.setattr(mutable_tck.importlib.metadata, "distributions", lambda: iter(current))
    monkeypatch.setattr(tck, "_load_package_resources", lambda: package)
    monkeypatch.setattr(tck, "_environment_bytecode_roots", lambda: ())
    monkeypatch.setattr(
        tck,
        "_environment_artifact_fingerprint",
        lambda _roots: artifact_state[0],
    )
    first = tck._environment_fingerprint(package)

    current[:] = [Distribution("2.0", "changed-record")]
    assert tck._environment_fingerprint(package) != first

    changed = replace(package, module_bytes={"consumer.py": b"changed module bytes"})
    current[:] = [Distribution("1.0", "first-record")]
    monkeypatch.setattr(tck, "_load_package_resources", lambda: changed)
    assert tck._environment_fingerprint(package) != first

    monkeypatch.setattr(tck, "_load_package_resources", lambda: package)
    artifact_state[0] = "changed-artifact-inventory"
    assert tck._environment_fingerprint(package) != first


def test_tck_environment_artifact_fingerprint_detects_pyc_and_record_mutation(
    tmp_path: Path,
) -> None:
    from matryca_plumber.graph_gateway.tck import _environment_artifact_fingerprint

    root = tmp_path / "site-packages"
    bytecode = root / "sample" / "__pycache__" / "module.pyc"
    record = root / "sample-1.0.dist-info" / "RECORD"
    bytecode.parent.mkdir(parents=True)
    record.parent.mkdir(parents=True)
    bytecode.write_bytes(b"initial bytecode")
    record.write_bytes(b"sample/module.py,,\n")

    initial = _environment_artifact_fingerprint((root,))
    bytecode.write_bytes(b"changed bytecode")
    after_bytecode = _environment_artifact_fingerprint((root,))
    assert after_bytecode != initial
    record.write_bytes(b"sample/module.py,changed,\n")
    assert _environment_artifact_fingerprint((root,)) != after_bytecode


@pytest.mark.parametrize("relative", ["package/runtime.py", "package/_native.so"])
def test_tck_environment_artifact_fingerprint_detects_import_payload_mutation(
    tmp_path: Path, relative: str
) -> None:
    from matryca_plumber.graph_gateway.tck import _environment_artifact_fingerprint

    root = tmp_path / "site-packages"
    payload = root / relative
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"initial import payload")
    initial = _environment_artifact_fingerprint((root,))
    payload.write_bytes(b"changed import payload")
    assert _environment_artifact_fingerprint((root,)) != initial


def test_tck_environment_artifact_inventory_fails_closed_on_uncovered_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck

    root = tmp_path / "site-packages"
    payload = root / "package/runtime.py"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"too large")
    monkeypatch.setattr(tck, "_MAX_ENVIRONMENT_FILE_BYTES", 4)
    with pytest.raises(tck.TCKFailure, match="environment_bounds"):
        tck._environment_artifact_fingerprint((root,))


def test_tck_fingerprints_installed_state_before_and_after_each_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "stable"))
    calls = []
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def child(_argv: tuple[str, ...], **_kwargs: Any) -> ChildResult:
        calls.append("invoked")
        return ChildResult(0, b"", b"", True)

    monkeypatch.setattr(tck, "_run_child", child)
    result = tck._invoke_snapshot(
        root,
        work_root,
        package,
        expected_environment_sha256="stable",
    )
    assert result.cleanup_ok is True
    assert calls == ["invoked"]


def test_tck_stops_before_child_when_environment_fingerprint_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.tck import TCKFailure

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    calls = []
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: "changed")
    monkeypatch.setattr(tck, "_run_child", lambda *_args, **_kwargs: calls.append("invoked"))
    with pytest.raises(TCKFailure, match="environment_changed"):
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="baseline",
        )
    assert calls == []


def test_tck_preserves_primary_and_cleanup_evidence_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildFailure

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "stable"))
    inventory_calls: list[tuple[Path, Path]] = []
    real_inventory = tck._invocation_inventory

    def record_inventory(root_arg: Path, work_root_arg: Path) -> Any:
        inventory_calls.append((root_arg, work_root_arg))
        return real_inventory(root_arg, work_root_arg)

    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))
    monkeypatch.setattr(tck, "_invocation_inventory", record_inventory)

    def failed_child(*_args: Any, **_kwargs: Any) -> Any:
        raise ChildFailure("timeout", cleanup_ok=False, cleanup_events=("pipe_close_failed",))

    monkeypatch.setattr(tck, "_run_child", failed_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_status == "uncertain"
    assert failure.value.cleanup_events == ("pipe_close_failed",)
    assert len(inventory_calls) == 2


@pytest.mark.parametrize("interrupted_observation", ["owned_tree", "environment"])
def test_tck_child_failure_survives_interrupted_post_child_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted_observation: str,
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildFailure

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    real_inventory = tck._invocation_inventory
    inventory_calls = 0
    environment_calls = 0

    def inventory(root_arg: Path, work_root_arg: Path) -> Any:
        nonlocal inventory_calls
        inventory_calls += 1
        if interrupted_observation == "owned_tree" and inventory_calls == 2:
            raise KeyboardInterrupt
        return real_inventory(root_arg, work_root_arg)

    def environment_fingerprint(_package: PackageResources) -> str:
        nonlocal environment_calls
        environment_calls += 1
        if interrupted_observation == "environment" and environment_calls == 2:
            raise KeyboardInterrupt
        return "stable"

    def failed_child(*_args: Any, **_kwargs: Any) -> None:
        raise ChildFailure("timeout", cleanup_ok=False, cleanup_events=("pipe_close_failed",))

    monkeypatch.setattr(tck, "_invocation_inventory", inventory)
    monkeypatch.setattr(tck, "_environment_fingerprint", environment_fingerprint)
    monkeypatch.setattr(tck, "_run_child", failed_child)

    try:
        tck._invoke_child(
            ("synthetic-child",),
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )
    except tck.TCKFailure as error:
        failure = error
    except BaseException as error:
        pytest.fail(
            f"post-child interruption escaped without a TCK failure: {type(error).__name__}"
        )
    else:
        pytest.fail("child failure was not retained")

    assert failure.reason == "timeout"
    assert failure.cleanup_status == "uncertain"
    assert "pipe_close_failed" in failure.cleanup_events
    assert failure.cleanup_events.count("owned_inventory_unavailable") == (
        interrupted_observation == "owned_tree"
    )
    assert failure.cleanup_events.count("environment_inventory_unavailable") == (
        interrupted_observation == "environment"
    )
    assert inventory_calls == 2
    assert environment_calls == 2


def test_tck_reports_inventory_error_as_one_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "stable"))
    calls = 0
    real_inventory = tck._invocation_inventory

    def inventory_failure(root_arg: Path, work_root_arg: Path) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_inventory(root_arg, work_root_arg)
        raise tck.TCKFailure("owned_inventory_unavailable")

    def successful_child(*_args: Any, **_kwargs: Any) -> ChildResult:
        return ChildResult(0, b"", b"", True)

    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))
    monkeypatch.setattr(tck, "_invocation_inventory", inventory_failure)
    monkeypatch.setattr(tck, "_run_child", successful_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )

    assert failure.value.reason == "owned_inventory_unavailable"
    assert failure.value.cleanup_status == "uncertain"
    assert failure.value.cleanup_events == ("owned_inventory_unavailable",)


def test_tck_child_failure_still_rejects_graph_inventory_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildFailure

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "stable"))
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def mutate_then_fail(*_args: Any, **_kwargs: Any) -> None:
        (root / "child-output.md").write_text("mutated\n", encoding="utf-8")
        raise ChildFailure("timeout", cleanup_ok=True)

    monkeypatch.setattr(tck, "_run_child", mutate_then_fail)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )
    assert failure.value.reason == "timeout"
    assert failure.value.cleanup_status == "verified"
    assert "owned_inventory_changed" in failure.value.cleanup_events


def test_tck_child_failure_still_compares_after_environment_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildFailure

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "changed"))
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def fail_child(*_args: Any, **_kwargs: Any) -> None:
        raise ChildFailure("timeout", cleanup_ok=True)

    monkeypatch.setattr(tck, "_run_child", fail_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )
    assert failure.value.reason == "timeout"
    assert "environment_fingerprint_changed" in failure.value.cleanup_events


def test_tck_rejects_fixture_mutation_after_child_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    (root / "page.md").write_text("before\n", encoding="utf-8")
    fingerprints = iter(("stable", "stable"))
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def mutate_after_output(*_args: Any, **_kwargs: Any) -> ChildResult:
        (root / "page.md").write_text("after output\n", encoding="utf-8")
        return ChildResult(0, b"synthetic output", b"", True)

    monkeypatch.setattr(tck, "_run_child", mutate_after_output)
    with pytest.raises(tck.TCKFailure, match="invocation_tree_changed"):
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )


def test_tck_rejects_owned_work_root_empty_directory_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    fingerprints = iter(("stable", "stable"))
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def add_empty_directory(*_args: Any, **_kwargs: Any) -> ChildResult:
        (work_root / "unexpected-empty").mkdir()
        return ChildResult(0, b"synthetic output", b"", True)

    monkeypatch.setattr(tck, "_run_child", add_empty_directory)
    with pytest.raises(tck.TCKFailure, match="invocation_tree_changed"):
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )


@pytest.mark.parametrize("mutation", ["addition", "removal"])
def test_tck_rejects_graph_addition_or_removal_during_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    original = root / "page.md"
    original.write_text("stable\n", encoding="utf-8")
    fingerprints = iter(("stable", "stable"))
    monkeypatch.setattr(tck, "_environment_fingerprint", lambda _package: next(fingerprints))

    def mutate_after_output(*_args: Any, **_kwargs: Any) -> ChildResult:
        if mutation == "addition":
            (root / "added.md").write_text("synthetic\n", encoding="utf-8")
        else:
            original.unlink()
        return ChildResult(0, b"synthetic output", b"", True)

    monkeypatch.setattr(tck, "_run_child", mutate_after_output)
    with pytest.raises(tck.TCKFailure, match="invocation_tree_changed"):
        tck._invoke_snapshot(
            root,
            work_root,
            package,
            expected_environment_sha256="stable",
        )


def test_tck_tree_fingerprint_binds_empty_directories(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.tck import _fingerprint_tree

    root = tmp_path / "fixture"
    root.mkdir()
    (root / "page.md").write_text("stable\n", encoding="utf-8")
    before = _fingerprint_tree(root).sha256
    (root / "empty").mkdir()
    assert _fingerprint_tree(root).sha256 != before


def test_tck_lifecycle_controls_observe_native_and_injected_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.tck as tck

    package = _validation_package()
    work_root = tmp_path / "owned-work"
    root = work_root / "graph"
    root.mkdir(parents=True)
    environment_reads: list[str] = []

    def record_environment_fingerprint(_package: PackageResources) -> str:
        environment_reads.append("fingerprint")
        return "stable"

    monkeypatch.setattr(tck, "_environment_fingerprint", record_environment_fingerprint)

    outcomes = tck._run_lifecycle_controls(root, work_root, package, "stable")

    assert [outcome["id"] for outcome in outcomes] == [
        "native-timeout-cleanup",
        "native-stdout-overflow-cleanup",
        "native-stderr-overflow-cleanup",
        "native-same-group-survivor-kill-escalation",
        "injected-cleanup-interruption-fallback",
    ]
    assert [outcome["status"] for outcome in outcomes] == ["pass"] * 5
    assert [outcome["evidence"] for outcome in outcomes[:3]] == ["native_synthetic_child"] * 3
    assert outcomes[4]["evidence"].startswith("injected_finalizer_fault;")
    assert outcomes[3]["evidence"] == "native_synthetic_child; SIGKILL observed for owned group"
    assert len(environment_reads) == 10
    assert str(tmp_path) not in json.dumps(outcomes)


def test_tck_interrupted_control_mismatch_checks_child_group_and_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matryca_plumber.graph_gateway.consumer as consumer
    import matryca_plumber.graph_gateway.tck as tck

    mutable_consumer: Any = cast(Any, consumer)
    observations: list[str] = []

    class FakePipe:
        @property
        def closed(self) -> bool:
            observations.append("stdout" if self is child.stdout else "stderr")
            return False

    class FakeChild:
        pid = 431

        def __init__(self) -> None:
            self.stdout = FakePipe()
            self.stderr = FakePipe()

        def poll(self) -> int | None:
            observations.append("poll")
            return None

    child = FakeChild()
    package = _validation_package()

    def fake_popen(*_args: Any, **_kwargs: Any) -> FakeChild:
        return child

    def group_state(_pid: int) -> bool | None:
        observations.append("group")
        return None

    def mismatched_invocation(*_args: Any, **_kwargs: Any) -> None:
        mutable_consumer.subprocess.Popen(("synthetic-child",))
        raise tck.TCKFailure(
            "unexpected_child_failure",
            cleanup_status="uncertain",
            cleanup_events=("group_finalize_failed",),
        )

    monkeypatch.setattr(mutable_consumer.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(consumer, "_group_state", group_state)
    monkeypatch.setattr(tck, "_invoke_child", mismatched_invocation)

    with pytest.raises(tck.TCKFailure) as failure:
        tck._run_interrupted_cleanup_control(
            tmp_path / "graph",
            tmp_path / "owned-work",
            package,
            "unused-environment-fingerprint",
        )

    assert failure.value.reason == "injected_cleanup_interruption"
    assert failure.value.cleanup_status == "uncertain"
    assert "group_finalize_failed" in failure.value.cleanup_events
    assert observations == ["poll", "group", "stdout", "stderr"]


def test_tck_control_interruption_retains_owned_root_and_stops_later_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    import matryca_plumber.graph_gateway.tck as tck
    from matryca_plumber.graph_gateway.resources import PackageResourceError

    mutable_tck: Any = cast(Any, tck)
    package = replace(_validation_package(), module_bytes={"gateway.py": b"source"})
    work_root = tmp_path / "owned-tck-root"
    later_calls: list[str] = []
    child_calls: list[str] = []

    def create_work_root(*_args: Any, **_kwargs: Any) -> str:
        work_root.mkdir()
        return str(work_root)

    def reject_mutated_package(*_args: Any, **_kwargs: Any) -> None:
        raise PackageResourceError()

    def interrupt_fixture_copy(_package: PackageResources, root: Path) -> None:
        root.mkdir(parents=True)
        (root / "partial.md").write_bytes(b"synthetic partial fixture")
        raise KeyboardInterrupt

    def unexpected_child(*_args: Any, **_kwargs: Any) -> Any:
        child_calls.append("child")
        raise AssertionError("child invocation continued after interruption")

    def unexpected_lifecycle(*_args: Any, **_kwargs: Any) -> Any:
        later_calls.append("lifecycle")
        raise AssertionError("later lifecycle control continued after interruption")

    monkeypatch.setattr(mutable_tck.tempfile, "mkdtemp", create_work_root)
    monkeypatch.setattr(tck, "_fixture_files", lambda _package: {"pages/B.md": b"synthetic"})
    monkeypatch.setattr(tck, "_verify_package_resources", reject_mutated_package)
    monkeypatch.setattr(tck, "_copy_private_fixtures", interrupt_fixture_copy)
    monkeypatch.setattr(mutable_tck.os, "chmod", lambda *_args: None)
    monkeypatch.setattr(tck, "_invoke_snapshot", unexpected_child)
    monkeypatch.setattr(tck, "_run_lifecycle_controls", unexpected_lifecycle)

    with pytest.raises(tck.TCKFailure) as failure:
        tck._run_controls(package, "stable")

    assert failure.value.reason == "control_interrupted"
    assert failure.value.cleanup_status == "uncertain"
    assert "control_interrupted" in failure.value.cleanup_events
    assert work_root.is_dir()
    assert child_calls == []
    assert later_calls == []


def test_tck_owned_root_cleanup_interruption_preserves_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    import matryca_plumber.graph_gateway.tck as tck

    mutable_tck: Any = cast(Any, tck)
    package = replace(_validation_package(), module_bytes={"gateway.py": b"source"})
    work_root = tmp_path / "owned-tck-root"
    steps: list[str] = []

    def create_work_root(*_args: Any, **_kwargs: Any) -> str:
        work_root.mkdir()
        return str(work_root)

    def reject_mutated_package(*_args: Any, **_kwargs: Any) -> None:
        from matryca_plumber.graph_gateway.resources import PackageResourceError

        steps.append("verify")
        raise PackageResourceError()

    def fail_fixture_copy(_package: PackageResources, root: Path) -> None:
        steps.append("copy")
        root.mkdir(parents=True)
        raise tck.TCKFailure("fixture_copy", cleanup_status="verified")

    def interrupt_rmtree(*_args: Any, **_kwargs: Any) -> None:
        steps.append("cleanup")
        raise KeyboardInterrupt

    monkeypatch.setattr(mutable_tck.tempfile, "mkdtemp", create_work_root)
    monkeypatch.setattr(tck, "_fixture_files", lambda _package: {"pages/B.md": b"synthetic"})
    monkeypatch.setattr(tck, "_verify_package_resources", reject_mutated_package)
    monkeypatch.setattr(tck, "_copy_private_fixtures", fail_fixture_copy)
    monkeypatch.setattr(mutable_tck.os, "chmod", lambda *_args: None)
    monkeypatch.setattr(mutable_tck.shutil, "rmtree", interrupt_rmtree)

    try:
        tck._run_controls(package, "stable")
    except tck.TCKFailure as error:
        failure = error
    except BaseException as error:
        pytest.fail(f"owned-root cleanup interruption escaped: {type(error).__name__}")
    else:
        pytest.fail("primary control failure was not retained")

    assert failure.reason == "fixture_copy", f"steps={steps!r}"
    assert failure.cleanup_status == "uncertain"
    assert "owned_work_root_cleanup_failed" in failure.cleanup_events
    assert work_root.is_dir()


def _tck_owned_alias_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import tempfile

    actual = (tmp_path / "canonical-parent").resolve()
    actual.mkdir()
    alias = tmp_path / "parent-alias"
    alias.symlink_to(actual, target_is_directory=True)
    owned_root = alias / "owned-tck-root"

    def allocate_owned_root(*_args: Any, **_kwargs: Any) -> str:
        owned_root.mkdir(mode=0o700)
        return str(owned_root)

    monkeypatch.setattr(tempfile, "mkdtemp", allocate_owned_root)
    return owned_root


def test_tck_canonicalizes_only_newly_owned_root_before_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    package = _package_resources()
    lexical_root = _tck_owned_alias_root(tmp_path, monkeypatch)
    expected_root = lexical_root.resolve()
    observed: list[tuple[Path, Path]] = []

    def stop_at_snapshot(root: Path, work_root: Path, *_args: Any, **_kwargs: Any) -> Any:
        observed.append((root, work_root))
        raise tck.TCKFailure("synthetic_boundary", cleanup_status="verified")

    monkeypatch.setattr(tck, "_invoke_snapshot", stop_at_snapshot)
    with pytest.raises(tck.TCKFailure, match="synthetic_boundary"):
        tck._run_controls(package, "synthetic")

    assert observed == [(expected_root / "first", expected_root)]
    assert not lexical_root.exists()


@pytest.mark.parametrize("interruption", [OSError, RuntimeError, KeyboardInterrupt])
def test_tck_owned_root_resolution_failure_retains_without_children(
    interruption: type[BaseException], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    package = _package_resources()
    lexical_root = _tck_owned_alias_root(tmp_path, monkeypatch)
    original_resolve = Path.resolve
    later_calls: list[str] = []

    def fail_owned_resolution(path: Path, strict: bool = False) -> Path:
        if path == lexical_root:
            raise interruption()
        return original_resolve(path, strict=strict)

    def forbid_fixture_copy(*_args: Any, **_kwargs: Any) -> None:
        later_calls.append("fixture-copy")
        raise tck.TCKFailure("unexpected_fixture_copy")

    monkeypatch.setattr(Path, "resolve", fail_owned_resolution)
    monkeypatch.setattr(tck, "_copy_private_fixtures", forbid_fixture_copy)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._run_controls(package, "synthetic")

    assert failure.value.reason == "control_interrupted"
    assert failure.value.cleanup_status == "uncertain"
    assert lexical_root.is_dir()
    assert later_calls == []


@pytest.mark.parametrize(
    ("returncode", "stderr", "expected"),
    [
        (
            4,
            b'{"error":"source_rejected"}\n',
            {"returncode": 4, "stderr": "gateway_error", "error": "source_rejected"},
        ),
        (70, b"", {"returncode": 70, "stderr": "empty"}),
        (0, b"PRIVATE-CANARY", {"returncode": 0, "stderr": "unclassified"}),
        (1, b'{"error":"source_rejected"}', {"returncode": 1, "stderr": "unclassified"}),
        (4, b'{"error":"/private/PRIVATE-CANARY"}', {"returncode": 4, "stderr": "unclassified"}),
        (
            4,
            b'{"error":"source_rejected","detail":"PRIVATE-CANARY"}',
            {"returncode": 4, "stderr": "unclassified"},
        ),
        (
            4,
            b'{"error":"source_rejected","error":"internal"}',
            {"returncode": 4, "stderr": "unclassified"},
        ),
        (4, b"X" * 513, {"returncode": 4, "stderr": "unclassified"}),
        (4, b"\xff", {"returncode": 4, "stderr": "unclassified"}),
    ],
)
def test_tck_failed_snapshot_report_keeps_only_sanitized_child_evidence(
    returncode: int,
    stderr: bytes,
    expected: dict[str, int | str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from matryca_plumber.graph_gateway import tck
    from matryca_plumber.graph_gateway.consumer import ChildResult

    lexical_root = _tck_owned_alias_root(tmp_path, monkeypatch)
    prefix = tmp_path / "synthetic-installed-prefix"
    prefix.mkdir()
    module = prefix / "synthetic-tck.py"
    module.write_text("# synthetic installed origin\n", encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(tck, "__file__", str(module))
    monkeypatch.setattr(
        tck, "_installed_identity", lambda: {"installed_origin": True, "editable": False}
    )
    monkeypatch.setattr(tck, "_environment", lambda *_args: {"sha256": "synthetic"})
    monkeypatch.setattr(tck, "_planned_row", lambda *_args: True)
    monkeypatch.setattr(
        tck,
        "_invoke_snapshot",
        lambda *_args, **_kwargs: ChildResult(returncode, b"PRIVATE-CANARY", stderr, True),
    )

    code, report = tck._execute(tmp_path / "report.json")

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "snapshot_failed"
    assert report.get("child_failure") == expected
    assert report["checks"] == [
        {"id": "installed-origin", "status": "pass"},
        {"id": "resource-and-code-byte-authentication", "status": "pass"},
    ]
    assert report["cleanup"] == {
        "status": "verified",
        "primary_failure": "snapshot_failed",
        "events": [],
        "retained_owned_synthetic_root": False,
    }
    assert not lexical_root.exists()
    assert "PRIVATE-CANARY" not in json.dumps(report)
    assert str(tmp_path) not in json.dumps(report)


def test_tck_case_inventory_separates_native_and_injected_lifecycle_evidence() -> None:
    cases_path = (
        Path(__file__).resolve().parents[1]
        / "matryca_plumber/graph_gateway/resources/og-v1/tck-cases.json"
    )
    cases = json.loads(cases_path.read_bytes())

    assert cases["consumer_lifecycle_controls"] == {
        "native_synthetic_child": [
            "native-timeout-cleanup",
            "native-stdout-overflow-cleanup",
            "native-stderr-overflow-cleanup",
            "native-same-group-survivor-kill-escalation",
        ],
        "injected_fault": ["injected-cleanup-interruption-fallback"],
    }
    assert "before-after-graph-and-owned-work-root-inventory" in cases["cases"]
    assert "bounded-environment-import-payload-inventory" in cases["cases"]
    assert "globally-unique-success-session-identities" in cases["cases"]
    assert cases["environment_inventory"] == {
        "roots": ["sysconfig.purelib", "sysconfig.platlib"],
        "max_entries": 100000,
        "max_file_bytes": 67108864,
        "max_total_file_bytes": 536870912,
        "coverage": (
            "all regular-file bytes and directory names; unknown, unreadable, or "
            "over-budget state fails closed"
        ),
    }
    assert cases["source_unit_controls"]["page_mapping_integrity"] == [
        "tests/test_og_topology_session_read.py::test_topology_rejects_missing_extra_and_duplicate_page_mappings[missing]",
        "tests/test_og_topology_session_read.py::test_topology_rejects_missing_extra_and_duplicate_page_mappings[extra]",
        "tests/test_og_topology_session_read.py::test_topology_rejects_missing_extra_and_duplicate_page_mappings[duplicate]",
    ]
    assert cases["source_unit_controls"]["source_addition_removal"] == [
        "tests/test_og_topology_snapshot.py::test_verification_rejects_same_size_edit_addition_and_removal"
    ]
    assert cases["source_unit_controls"]["post_child_graph_addition_removal"] == [
        "tests/test_og_operational_package.py::test_tck_rejects_graph_addition_or_removal_during_child[addition]",
        "tests/test_og_operational_package.py::test_tck_rejects_graph_addition_or_removal_during_child[removal]",
    ]
    assert cases["source_unit_controls"]["capture_integrity"] == [
        "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_non_regular_source_before_descriptor_open_or_parser",
        "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_snapshot_that_grows_during_read",
        "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_same_size_external_symlink_swapped_after_containment",
        "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_same_size_replacement_inode_after_descriptor_read",
        "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_invalid_utf8_snapshot_before_parser_invocation",
        "tests/test_og_topology_snapshot.py::test_capture_counts_entries_before_descent_and_acceptance",
        "tests/test_og_topology_snapshot.py::test_capture_accepts_inclusive_walk_limits",
        "tests/test_og_topology_snapshot.py::test_capture_enforces_inclusive_byte_limits",
    ]
    assert len(cases["source_unit_controls"]["finite_source_boundaries"]) == 11


def test_fixture_manifest_canaries_are_real_block_text_and_property_values() -> None:
    project = Path(__file__).resolve().parents[1]
    resource_root = project / "matryca_plumber/graph_gateway/resources/og-v1"
    manifest = json.loads((resource_root / "fixture-manifest.json").read_bytes())

    assert manifest["privacy_canaries"] == {
        "block_text": {
            "fixture": "pages/B.md",
            "value": "PRIVACY-CANARY-BLOCK-TEXT",
        },
        "property_value": {
            "fixture": "pages/B.md",
            "property": "test-canary",
            "value": "PRIVACY-CANARY-PROPERTY-VALUE",
        },
    }
    fixture = (resource_root / "fixtures/pages/B.md").read_bytes()
    assert b"- Alpha parent PRIVACY-CANARY-BLOCK-TEXT" in fixture
    assert b"test-canary:: PRIVACY-CANARY-PROPERTY-VALUE" in fixture
    assert manifest["independent_expectations"] == {
        "block_nodes": 9,
        "explicit_page_ids": 4,
        "page_nodes": 5,
        "reference_edges": 2,
        "result_complete": True,
    }


def test_tck_fixture_loader_validates_canary_locations_before_privacy_scan() -> None:
    from dataclasses import replace

    from matryca_plumber.graph_gateway.tck import TCKFailure, _check_fixture_no_leak, _fixture_files

    fixture = (
        b"title:: B\n"
        b"test-canary:: PRIVACY-CANARY-PROPERTY-VALUE\n"
        b"- Alpha parent PRIVACY-CANARY-BLOCK-TEXT\n"
    )
    manifest: dict[str, Any] = {
        "fixture_profile": "og-v1-synthetic-structure",
        "license": "Apache-2.0",
        "files": {"pages/B.md": {"sha256": hashlib.sha256(fixture).hexdigest()}},
        "independent_expectations": {
            "block_nodes": 9,
            "explicit_page_ids": 4,
            "page_nodes": 5,
            "reference_edges": 2,
            "result_complete": True,
        },
        "privacy_canaries": {
            "block_text": {
                "fixture": "pages/B.md",
                "value": "PRIVACY-CANARY-BLOCK-TEXT",
            },
            "property_value": {
                "fixture": "pages/B.md",
                "property": "test-canary",
                "value": "PRIVACY-CANARY-PROPERTY-VALUE",
            },
        },
        "schema_version": 1,
    }
    package = _validation_package()
    assets = dict(package.assets)
    assets["fixture-manifest.json"] = json.dumps(manifest).encode()
    assets["fixtures/pages/B.md"] = fixture
    package = replace(package, assets=assets)

    files = _fixture_files(package)
    assert files == {"pages/B.md": fixture}
    with pytest.raises(TCKFailure, match="fixture_content_leak"):
        _check_fixture_no_leak(
            b"PRIVACY-CANARY-PROPERTY-VALUE", Path("/private/root"), files, package
        )

    malformed = fixture.replace(b"test-canary:: ", b"not-a-property: ")
    manifest["files"]["pages/B.md"]["sha256"] = hashlib.sha256(malformed).hexdigest()
    malformed_assets = dict(package.assets)
    malformed_assets["fixture-manifest.json"] = json.dumps(manifest).encode()
    malformed_assets["fixtures/pages/B.md"] = malformed
    with pytest.raises(TCKFailure, match="fixture_manifest"):
        _fixture_files(replace(package, assets=malformed_assets))


def test_consumer_rejects_success_with_surviving_same_group_child(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.consumer import ChildFailure, _run_child

    expression = (
        "import subprocess,sys;"
        "subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)'],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "sys.stdout.write('{\"valid\":true}\\n');sys.stdout.flush()"
    )
    with pytest.raises(ChildFailure) as failure:
        _run_child(
            [sys.executable, "-I", "-B", "-c", expression],
            cwd=tmp_path,
            env={"LC_ALL": "C", "LANG": "C"},
            execution_timeout=3,
            cleanup_budget=2,
        )
    assert failure.value.reason == "surviving_process_group"
    assert failure.value.cleanup_ok is True


def test_installed_origin_rejects_repository_and_editable_locations(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.tck import _is_installed_origin

    source = tmp_path / "repo/matryca_plumber/graph_gateway/tck.py"
    installed = tmp_path / "venv/lib/python3.12/site-packages/matryca_plumber/graph_gateway/tck.py"
    source.parent.mkdir(parents=True)
    installed.parent.mkdir(parents=True)
    source.write_text("# source\n", encoding="utf-8")
    installed.write_text("# installed\n", encoding="utf-8")
    assert _is_installed_origin(source, installed, {"dir_info": {"editable": True}}) is False
    assert _is_installed_origin(installed, installed, {"dir_info": {"editable": True}}) is False
    assert _is_installed_origin(installed, installed, {}) is True


def test_tck_validates_schema_descriptor_and_golden_bindings() -> None:
    from matryca_plumber.graph_gateway.tck import TCKFailure, _validate_success_response
    from matryca_plumber.graph_gateway.wire import _encode, _snapshot_document

    from tests.test_og_graph_gateway_wire import _inputs

    package = _package_resources()
    values = _inputs()
    package_version = json.loads(package.assets["dependency-profile.json"])["project"]["version"]
    values[1]["plumber"] = package_version
    golden = json.loads(package.assets["golden/topology.result.json"])
    revision = golden["provenance"]["source_revision"]
    session, identity, topology = values[2], values[3], values[4]
    session["source_revision"] = revision
    identity["source_revision"] = revision
    topology["source_revision"] = revision
    topology["result"] = golden
    output = _snapshot_document(*values)
    output["descriptor_sha256"] = package.descriptor_sha256
    encoded = _encode(output)

    checked = _validate_success_response(encoded, package)
    assert checked["topology"]["result"] == golden

    output["versions"]["plumber"] = "2.0.1rc4"
    with pytest.raises(TCKFailure, match="response_binding"):
        _validate_success_response(_encode(output), package)
    output["versions"]["plumber"] = package_version

    output["descriptor_sha256"] = "0" * 64
    with pytest.raises(TCKFailure, match="response_binding"):
        _validate_success_response(_encode(output), package)


def test_tck_response_parser_rejects_duplicate_keys() -> None:
    from matryca_plumber.graph_gateway.tck import TCKFailure, _strict_document

    with pytest.raises(TCKFailure, match="invalid_json"):
        _strict_document(b'{"error":"source_rejected","error":"internal"}\n')


@pytest.mark.parametrize(
    ("identity", "outside_prefix"),
    [
        ({"installed_origin": False, "editable": False}, False),
        ({"installed_origin": False, "editable": True}, False),
        ({"installed_origin": True, "editable": False}, True),
    ],
    ids=["source", "editable", "outside-prefix"],
)
def test_tck_refuses_origins_before_environment_inventory_or_controls(
    identity: dict[str, bool],
    outside_prefix: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from matryca_plumber.graph_gateway import tck
    from matryca_plumber.graph_gateway.resources import _load_package_resources

    events: list[str] = []
    load_resources = _load_package_resources

    def authenticate_resources() -> PackageResources:
        package = load_resources()
        events.append("authenticated-resources")
        return package

    def installed_identity() -> dict[str, Any]:
        assert events == ["authenticated-resources"]
        events.append("identity")
        return dict(identity)

    def forbidden_later_operation(*_args: Any) -> Any:
        events.append("forbidden-environment-or-controls")
        raise tck.TCKFailure("environment_bounds")

    monkeypatch.setattr(tck, "_load_package_resources", authenticate_resources)
    monkeypatch.setattr(tck, "_installed_identity", installed_identity)
    monkeypatch.setattr(tck, "_environment", forbidden_later_operation)
    monkeypatch.setattr(tck, "_environment_fingerprint", forbidden_later_operation)
    monkeypatch.setattr(tck, "_run_controls", forbidden_later_operation)
    if outside_prefix:
        prefix = tmp_path / "prefix"
        prefix.mkdir()
        outside_module = tmp_path / "outside-tck.py"
        outside_module.write_text("# synthetic origin\n", encoding="utf-8")
        monkeypatch.setattr(sys, "prefix", str(prefix))
        monkeypatch.setattr(tck, "__file__", str(outside_module))

    code, report = tck._execute(tmp_path / "report.json")

    assert code == 2
    assert report["status"] == "not_run"
    assert report["reason"] == "not_installed"
    assert report["qualification"] == "unqualified"
    assert report["checks"] == []
    assert report["environment"] == {
        "installed_origin": False,
        "editable": identity["editable"],
        "sha256": None,
        "fingerprint_scope": "not collected: execution origin rejected",
    }
    assert events == ["authenticated-resources", "identity"]
    assert report["resources"]["assets"]
    assert report["resources"]["descriptor_sha256"]
    assert report["resources"]["manifest_sha256"]
    assert capsys.readouterr().out == ""
    assert str(tmp_path) not in json.dumps(report)


@pytest.mark.parametrize("reason", ["environment_bounds", "environment_unreadable"])
def test_installed_tck_preserves_environment_failure_after_origin_admission(
    reason: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from matryca_plumber.graph_gateway import tck

    prefix = tmp_path / "prefix"
    prefix.mkdir()
    module = prefix / "installed-tck.py"
    module.write_text("# synthetic installed origin\n", encoding="utf-8")
    events: list[str] = []

    def fail_inventory(_package: PackageResources) -> str:
        events.append("environment-inventory")
        raise tck.TCKFailure(reason)

    def forbidden_controls(*_args: Any) -> Any:
        events.append("controls")
        pytest.fail("controls ran after failed environment inventory")

    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(tck, "__file__", str(module))
    monkeypatch.setattr(
        tck, "_installed_identity", lambda: {"installed_origin": True, "editable": False}
    )
    monkeypatch.setattr(tck, "_environment_fingerprint", fail_inventory)
    monkeypatch.setattr(tck, "_run_controls", forbidden_controls)

    code, report = tck._execute(tmp_path / "report.json")

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == reason
    assert report["qualification"] == "unqualified"
    assert report["checks"] == []
    assert events == ["environment-inventory"]
    assert "environment" not in report
    assert report["resources"]["assets"]


def test_source_tck_refuses_installed_evidence_and_emits_path_free_report(tmp_path: Path) -> None:
    from matryca_plumber.graph_gateway.tck import _execute

    code, report = _execute(tmp_path / "report.json")

    assert code == 2
    assert report["status"] == "not_run"
    assert report["reason"] == "not_installed"
    assert report["qualification"] == "unqualified"
    serialized = json.dumps(report)
    assert str(tmp_path) not in serialized
    assert "PRIVACY-CANARY-PAGE-TITLE" not in serialized


def _synthetic_signal_finalization(
    error: BaseException, monkeypatch: pytest.MonkeyPatch
) -> tuple[bool, tuple[str, ...]]:
    """Exercise real finalization with no native child or process signal."""
    import os
    import signal
    import time

    from matryca_plumber.graph_gateway import consumer

    polls = iter((None, 0))
    states = iter((True, False))
    signals: list[tuple[int, int]] = []

    class ReapedChild:
        pid = 4242
        stdout = None
        stderr = None

        def poll(self) -> int | None:
            return next(polls)

    def fail_signal(group_id: int, signum: int) -> None:
        signals.append((group_id, signum))
        raise error

    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(consumer, "_group_state", lambda _group_id: next(states))
    monkeypatch.setattr(os, "killpg", fail_signal)
    events: list[str] = []
    cleanup_ok = consumer._finalize_child(cast(Any, ReapedChild()), None, {}, 1.0, events)
    assert signals == [(4242, signal.SIGTERM)]
    return cleanup_ok, tuple(events)


@pytest.mark.parametrize(
    ("error", "category", "errno_category"),
    [
        (PermissionError(13, "PRIVATE-CANARY"), "permission_error", "eacces"),
        (InterruptedError(4, "PRIVATE-CANARY"), "interrupted_error", "eintr"),
        (OSError(22, "PRIVATE-CANARY"), "os_error", "einval"),
        (OSError(777, "PRIVATE-CANARY"), "os_error", "other"),
        (OSError("PRIVATE-CANARY"), "os_error", "unavailable"),
        (RuntimeError("PRIVATE-CANARY"), "exception", "not_applicable"),
        (KeyboardInterrupt("PRIVATE-CANARY"), "keyboard_interrupt", "not_applicable"),
        (SystemExit("PRIVATE-CANARY"), "system_exit", "not_applicable"),
        (BaseException("PRIVATE-CANARY"), "base_exception", "not_applicable"),
    ],
)
def test_consumer_term_failure_details_are_finite_and_never_verify_cleanup(
    error: BaseException,
    category: str,
    errno_category: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup_ok, events = _synthetic_signal_finalization(error, monkeypatch)

    assert cleanup_ok is False
    assert events == (
        "term_signal_failed",
        f"term_signal_type_{category}_failed",
        f"term_signal_errno_{errno_category}_failed",
    )
    assert len(json.dumps(events)) < 256
    assert "PRIVATE-CANARY" not in json.dumps(events)


def test_consumer_eperm_observation_needs_all_terminal_cleanup_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cleanup_ok, events = _synthetic_signal_finalization(
        PermissionError(1, "PRIVATE-CANARY"), monkeypatch
    )
    # The fixture independently observes a reaped child and group absence.
    # The live-group, interruption, reader and deadline tests retain the veto.
    assert cleanup_ok is True
    assert events == ()


@pytest.mark.parametrize("kind", ["bool", "object", "raises"])
def test_consumer_term_classification_rejects_hostile_errno_without_escape(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import consumer

    class OpaqueIdentity:
        def __hash__(self) -> int:
            raise AssertionError("errno must not be hashed")

        def __eq__(self, _other: object) -> bool:
            raise AssertionError("errno must not be compared")

        def __str__(self) -> str:
            raise AssertionError("errno must not be coerced")

    class UnreadableErrno(OSError):
        def __getattribute__(self, name: str) -> Any:
            if name == "errno":
                raise KeyboardInterrupt("PRIVATE-CANARY")
            return super().__getattribute__(name)

    error = OSError("PRIVATE-CANARY")
    if kind == "raises":
        error = UnreadableErrno("PRIVATE-CANARY")
    else:
        cast(Any, error).errno = True if kind == "bool" else OpaqueIdentity()
    events: list[str] = []
    consumer._note_term_signal_failure(events, error)

    assert events == [
        "term_signal_failed",
        "term_signal_type_os_error_failed",
        "term_signal_errno_unknown_failed",
    ]
    assert "PRIVATE-CANARY" not in json.dumps(events)


@pytest.mark.parametrize("lookup_subclass", [True, False])
def test_consumer_esrch_remains_verified_without_failure_diagnostics(
    lookup_subclass: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    error: OSError = ProcessLookupError(errno.ESRCH, "PRIVATE-CANARY")
    if not lookup_subclass:
        error = OSError("PRIVATE-CANARY")
        error.errno = errno.ESRCH
    cleanup_ok, events = _synthetic_signal_finalization(error, monkeypatch)

    assert cleanup_ok is True
    assert events == ()


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("stderr_overflow", "stderr_overflow"),
        ("timeout", "timeout"),
        ("read_error", "read_error"),
        ("/private/PRIVATE-CANARY", "unclassified"),
        (True, "unclassified"),
        (1, "unclassified"),
    ],
)
def test_tck_native_failure_preserves_only_allowlisted_child_reason(
    reason: Any, expected: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    def failed_child(*_args: Any, **_kwargs: Any) -> Any:
        raise tck.TCKFailure(
            reason,
            cleanup_status="uncertain",
            cleanup_events=("term_signal_failed",),
        )

    monkeypatch.setattr(tck, "_invoke_child", failed_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._expect_native_child_failure(
            "native-stderr-overflow-cleanup",
            ("synthetic-interpreter",),
            tmp_path,
            tmp_path,
            _validation_package(),
            "synthetic",
            "stderr_overflow",
        )

    assert failure.value.reason == "native-stderr-overflow-cleanup"
    assert failure.value.cleanup_status == "uncertain"
    assert failure.value.cleanup_events == ("term_signal_failed",)
    assert failure.value.child_failure_reason == expected
    assert failure.value.child_failure is None


def test_tck_child_reason_rejects_hostile_objects_without_comparison() -> None:
    from matryca_plumber.graph_gateway import tck

    class OpaqueReason:
        def __hash__(self) -> int:
            raise AssertionError("reason must not be hashed")

        def __eq__(self, _other: object) -> bool:
            raise AssertionError("reason must not be compared")

        def __str__(self) -> str:
            raise AssertionError("reason must not be coerced")

    failure = tck.TCKFailure(
        "native-stderr-overflow-cleanup", child_failure_reason=cast(Any, OpaqueReason())
    )

    assert failure.child_failure_reason == "unclassified"


def _admit_synthetic_tck_report_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from matryca_plumber.graph_gateway import tck

    prefix = tmp_path / "synthetic-prefix"
    prefix.mkdir()
    module = prefix / "synthetic-tck.py"
    module.write_text("# synthetic installed origin\n", encoding="utf-8")
    monkeypatch.setattr(sys, "prefix", str(prefix))
    monkeypatch.setattr(tck, "__file__", str(module))
    monkeypatch.setattr(
        tck, "_installed_identity", lambda: {"installed_origin": True, "editable": False}
    )
    monkeypatch.setattr(tck, "_environment", lambda *_args: {"sha256": "synthetic"})
    monkeypatch.setattr(tck, "_planned_row", lambda *_args: True)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("stderr_overflow", "stderr_overflow"),
        ("/private/PRIVATE-CANARY", "unclassified"),
        (None, None),
    ],
)
def test_tck_failure_report_adds_only_bounded_optional_reason(
    reason: str | None, expected: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    _admit_synthetic_tck_report_origin(tmp_path, monkeypatch)

    def failed_controls(*_args: Any, **_kwargs: Any) -> Any:
        raise tck.TCKFailure(
            "native-stderr-overflow-cleanup",
            cleanup_status="uncertain",
            cleanup_events=("term_signal_failed",),
            child_failure_reason=reason,
        )

    monkeypatch.setattr(tck, "_run_controls", failed_controls)
    code, report = tck._execute(tmp_path / "report.json")

    assert code == 1
    assert report["status"] == "failed"
    assert report["reason"] == "native-stderr-overflow-cleanup"
    assert report["qualification"] == "unqualified"
    assert report["cleanup"] == {
        "status": "uncertain",
        "primary_failure": "native-stderr-overflow-cleanup",
        "events": ["term_signal_failed"],
        "retained_owned_synthetic_root": True,
    }
    if expected is None:
        assert "diagnostics" not in report
    else:
        assert report["diagnostics"] == {"child_failure_reason": expected}
    assert "child_failure" not in report
    assert "PRIVATE-CANARY" not in json.dumps(report)
    assert str(tmp_path) not in json.dumps(report)


def _complete_cleanup_snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "availability": "complete",
        "last_phase": "cleanup_group",
        "child_poll": "returncode_observed",
        "group_check": "absent_observed",
        "group_gate": True,
        "selector_gate": True,
        "streams_gate": True,
        "deadline_check": "not_exceeded",
        "cleanup_gate": True,
    }


def _snapshot_synthetic_finalizer(
    monkeypatch: pytest.MonkeyPatch,
    *,
    instrumented: bool = True,
    term_error: bool = False,
    close_error: bool = False,
    selector_error: bool = False,
) -> tuple[bool, tuple[str, ...], dict[str, object] | None, list[str]]:
    import errno
    import signal

    from matryca_plumber.graph_gateway import consumer

    trace: list[str] = []

    class Pipe:
        closed = False

        def close(self) -> None:
            trace.append("close")
            self.closed = True
            if close_error:
                raise OSError("PRIVATE-SNAPSHOT-CANARY")

    class Child:
        pid = 4242
        stdout = Pipe()
        stderr = Pipe()
        polls = 0

        def poll(self) -> int | None:
            trace.append("poll")
            self.polls += 1
            return None if term_error and self.polls == 1 else 0

    child = Child()

    def group_state(_pid: int) -> bool:
        trace.append("group")
        return term_error and child.polls == 1

    def killpg(pid: int, signum: int) -> None:
        assert pid == 4242
        assert signum == signal.SIGTERM
        trace.append("term")
        raise PermissionError(errno.EPERM, "PRIVATE-SNAPSHOT-CANARY")

    def clock() -> float:
        trace.append("clock")
        return 0.0

    monkeypatch.setattr(consumer, "_group_state", group_state)
    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(time, "monotonic", clock)
    events: list[str] = []

    class Selector:
        def close(self) -> None:
            trace.append("selector-close")
            raise RuntimeError("PRIVATE-SNAPSHOT-CANARY")

    selector = cast(Any, Selector()) if selector_error else None
    if instrumented:
        snapshot = consumer._CleanupSnapshot()
        result = consumer._finalize_child(
            cast(Any, child), selector, {}, 1.0, events, snapshot=snapshot
        )
        document = consumer._cleanup_snapshot_document(snapshot)
    else:
        result = consumer._finalize_child(cast(Any, child), selector, {}, 1.0, events)
        document = None
    return result, tuple(events), document, trace


@pytest.mark.parametrize("term_error", [False, True])
@pytest.mark.parametrize("close_error", [False, True])
@pytest.mark.parametrize("selector_error", [False, True])
def test_cleanup_snapshot_preserves_policy_and_operation_trace(
    term_error: bool, close_error: bool, selector_error: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = _snapshot_synthetic_finalizer(
        monkeypatch,
        instrumented=False,
        term_error=term_error,
        close_error=close_error,
        selector_error=selector_error,
    )
    observed = _snapshot_synthetic_finalizer(
        monkeypatch,
        term_error=term_error,
        close_error=close_error,
        selector_error=selector_error,
    )

    assert (observed[0], observed[1], observed[3]) == (plain[0], plain[1], plain[3])
    expected = _complete_cleanup_snapshot()
    expected["cleanup_gate"] = not close_error and not selector_error
    expected["streams_gate"] = not close_error
    expected["selector_gate"] = not selector_error
    assert observed[2] == expected
    assert "PRIVATE-SNAPSHOT-CANARY" not in json.dumps(observed[2])
    if term_error and (close_error or selector_error):
        assert observed[0] is False
        assert set(
            (
                "term_signal_failed",
                "term_signal_type_permission_error_failed",
                "term_signal_errno_eperm_failed",
            )
        ).issubset(observed[1])
    elif term_error:
        assert observed[0] is True
        assert observed[1] == ()


def test_cleanup_snapshot_fallback_does_not_reuse_prior_samples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from matryca_plumber.graph_gateway import consumer

    snapshot = consumer._CleanupSnapshot()
    snapshot.last_phase = "cleanup_group"
    snapshot.child_poll = "returncode_observed"
    snapshot.group_check = "absent_observed"
    monkeypatch.setattr(os, "killpg", lambda *_args: None)

    class InterruptedChild:
        pid = 4242

        def poll(self) -> int:
            raise KeyboardInterrupt("PRIVATE-SNAPSHOT-CANARY")

    monkeypatch.setattr(consumer, "_group_state", lambda _pid: None)
    monkeypatch.setattr(time, "monotonic", lambda: 2.0)
    events: list[str] = []
    result = consumer._kill_reap_fallback(
        cast(Any, InterruptedChild()), 1.0, events, snapshot=snapshot
    )
    document = consumer._cleanup_snapshot_document(snapshot)

    assert result is False
    assert document["availability"] == "partial"
    assert document["last_phase"] == "kill_reap_fallback"
    assert document["child_poll"] == "failed"
    assert document["group_check"] == "unknown"
    assert document["cleanup_gate"] is None
    assert events == ["fallback_poll_failed", "fallback_group_check_failed"]


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_cleanup_snapshot_recording_fault_cannot_skip_cleanup(
    error: type[BaseException], monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import consumer

    original_record = consumer._CleanupSnapshot.record
    calls = 0

    def fail_once(self: Any, **values: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error("PRIVATE-SNAPSHOT-CANARY")
        original_record(self, **values)

    monkeypatch.setattr(consumer._CleanupSnapshot, "record", fail_once)
    if error is RuntimeError:
        result = _snapshot_synthetic_finalizer(monkeypatch)
        assert result[0] is True
        assert result[1] == ()
        assert result[2] is not None
        assert result[2]["availability"] == "unavailable"
        assert result[3].count("close") == 2
    else:
        closed: list[str] = []

        class Pipe:
            closed = False

            def close(self) -> None:
                self.closed = True
                closed.append("pipe")

        class Child:
            pid = 4242
            stdout = Pipe()
            stderr = Pipe()

            def poll(self) -> int:
                return 0

        monkeypatch.setattr(time, "monotonic", lambda: 0.0)
        monkeypatch.setattr(consumer, "_group_state", lambda _pid: False)
        snapshot = consumer._CleanupSnapshot()
        events: list[str] = []
        with pytest.raises(error):
            consumer._finalize_child(cast(Any, Child()), None, {}, 1.0, events, snapshot=snapshot)
        assert closed == ["pipe", "pipe"]
        assert consumer._cleanup_snapshot_document(snapshot)["availability"] == "unavailable"


def test_cleanup_snapshot_absent_child_has_no_terminal_evidence() -> None:
    from matryca_plumber.graph_gateway import consumer

    document = consumer._cleanup_snapshot_document(consumer._CleanupSnapshot())

    assert document["availability"] == "unavailable"
    assert document["last_phase"] == "not_observed"
    assert document["child_poll"] == "not_observed"
    assert document["group_check"] == "not_observed"
    assert document["group_gate"] is None
    assert document["selector_gate"] is None
    assert document["streams_gate"] is None
    assert document["cleanup_gate"] is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("availability", "/private/PRIVATE-SNAPSHOT-CANARY"),
        ("child_poll", "alive"),
        ("group_check", True),
        ("group_gate", 1),
        ("selector_gate", 0),
        ("streams_gate", "true"),
        ("deadline_check", "PRIVATE-SNAPSHOT-CANARY"),
        ("cleanup_gate", 1),
        ("group_gate", None),
        ("child_poll", "not_observed"),
        ("deadline_check", "exceeded"),
        ("unexpected", "PRIVATE-SNAPSHOT-CANARY"),
    ],
)
def test_cleanup_snapshot_untrusted_fields_cannot_claim_completeness(
    key: str,
    value: Any,
) -> None:
    from matryca_plumber.graph_gateway import tck

    supplied = _complete_cleanup_snapshot()
    supplied[key] = value
    failure = tck.TCKFailure("synthetic", cleanup_snapshot=supplied)

    assert isinstance(failure.cleanup_snapshot, dict)
    assert failure.cleanup_snapshot["availability"] == "unavailable"
    assert failure.cleanup_snapshot["cleanup_gate"] is None
    assert "PRIVATE-SNAPSHOT-CANARY" not in json.dumps(failure.cleanup_snapshot)


def test_cleanup_snapshot_missing_field_cannot_claim_completeness() -> None:
    from matryca_plumber.graph_gateway import tck

    supplied = _complete_cleanup_snapshot()
    del supplied["child_poll"]
    failure = tck.TCKFailure("synthetic", cleanup_snapshot=supplied)

    assert isinstance(failure.cleanup_snapshot, dict)
    assert failure.cleanup_snapshot["availability"] == "unavailable"


def test_cleanup_snapshot_report_preserves_failure_and_retention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    _admit_synthetic_tck_report_origin(tmp_path, monkeypatch)
    supplied = _complete_cleanup_snapshot()
    supplied["cleanup_gate"] = False

    def failed_controls(*_args: Any) -> Any:
        raise tck.TCKFailure(
            "native-stdout-overflow-cleanup",
            cleanup_status="uncertain",
            cleanup_events=("term_signal_failed",),
            child_failure_reason="stdout_overflow",
            cleanup_snapshot=supplied,
        )

    monkeypatch.setattr(tck, "_run_controls", failed_controls)
    code, report = tck._execute(tmp_path / "report.json")

    assert code == 1
    assert report["status"] == "failed"
    assert report["qualification"] == "unqualified"
    assert report["cleanup"] == {
        "status": "uncertain",
        "primary_failure": "native-stdout-overflow-cleanup",
        "events": ["term_signal_failed"],
        "retained_owned_synthetic_root": True,
    }
    assert report["diagnostics"] == {
        "child_failure_reason": "stdout_overflow",
        "cleanup_snapshot": supplied,
    }
    assert len(json.dumps(report["diagnostics"]["cleanup_snapshot"]).encode()) <= 1024


def test_cleanup_snapshot_native_wrapper_cannot_waive_event_veto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    supplied = _complete_cleanup_snapshot()
    supplied["cleanup_gate"] = False

    def failed_child(*_args: Any, **_kwargs: Any) -> Any:
        raise tck.TCKFailure(
            "stdout_overflow",
            cleanup_status="uncertain",
            cleanup_events=("term_signal_failed",),
            cleanup_snapshot=supplied,
        )

    monkeypatch.setattr(tck, "_invoke_child", failed_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._expect_native_child_failure(
            "native-stdout-overflow-cleanup",
            ("synthetic",),
            tmp_path,
            tmp_path,
            _validation_package(),
            "synthetic",
            "stdout_overflow",
        )
    assert failure.value.reason == "native-stdout-overflow-cleanup"
    assert failure.value.cleanup_status == "uncertain"
    assert failure.value.cleanup_events == ("term_signal_failed",)
    assert failure.value.cleanup_snapshot == supplied


def test_tck_success_report_has_no_diagnostics_and_preserves_cleanup_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    _admit_synthetic_tck_report_origin(tmp_path, monkeypatch)
    monkeypatch.setattr(tck, "_run_controls", lambda *_args: [])
    code, report = tck._execute(tmp_path / "report.json")

    assert code == 0
    assert report["status"] == "pass"
    assert report["reason"] == "black_box_controls_passed"
    assert report["qualification"] == "unqualified"
    assert report["cleanup"] == {"status": "verified", "retained_owned_synthetic_root": False}
    assert "diagnostics" not in report
    assert "child_failure" not in report


@pytest.mark.parametrize("post_failure", ["none", "tree", "environment"])
def test_cleanup_snapshot_survives_post_child_inventory_failure(
    post_failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import consumer, tck

    root = tmp_path / "owned" / "graph"
    root.mkdir(parents=True)
    supplied = _complete_cleanup_snapshot()
    supplied["cleanup_gate"] = False
    real_inventory = tck._invocation_inventory
    calls = {"tree": 0, "environment": 0}

    def inventory(root_arg: Path, work_root_arg: Path) -> Any:
        calls["tree"] += 1
        if post_failure == "tree" and calls["tree"] == 2:
            raise KeyboardInterrupt("PRIVATE-SNAPSHOT-CANARY")
        return real_inventory(root_arg, work_root_arg)

    def environment(_package: PackageResources) -> str:
        calls["environment"] += 1
        if post_failure == "environment" and calls["environment"] == 2:
            raise KeyboardInterrupt("PRIVATE-SNAPSHOT-CANARY")
        return "stable"

    def failed_child(*_args: Any, **_kwargs: Any) -> Any:
        raise consumer.ChildFailure(
            "stdout_overflow",
            cleanup_ok=False,
            cleanup_events=("term_signal_failed",),
            cleanup_snapshot=supplied,
        )

    monkeypatch.setattr(tck, "_invocation_inventory", inventory)
    monkeypatch.setattr(tck, "_environment_fingerprint", environment)
    monkeypatch.setattr(tck, "_run_child", failed_child)
    with pytest.raises(tck.TCKFailure) as failure:
        tck._invoke_child(
            ("synthetic",),
            root,
            root.parent,
            _validation_package(),
            expected_environment_sha256="stable",
        )

    assert failure.value.reason == "stdout_overflow"
    assert failure.value.cleanup_status == "uncertain"
    assert failure.value.cleanup_snapshot == supplied
    assert failure.value.cleanup_events == (
        ("term_signal_failed", "owned_inventory_unavailable")
        if post_failure == "tree"
        else ("term_signal_failed", "environment_inventory_unavailable")
        if post_failure == "environment"
        else ("term_signal_failed",)
    )
    assert calls == {"tree": 2, "environment": 2}


@pytest.mark.parametrize("error", [ValueError, KeyboardInterrupt, SystemExit])
def test_cleanup_snapshot_encoding_failure_cannot_mask_primary(
    error: type[BaseException], monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import tck

    def broken_encoding(*_args: Any, **_kwargs: Any) -> str:
        raise error("PRIVATE-SNAPSHOT-CANARY")

    monkeypatch.setattr(json, "dumps", broken_encoding)
    failure = tck.TCKFailure(
        "stdout_overflow",
        cleanup_status="uncertain",
        cleanup_events=("term_signal_failed",),
        cleanup_snapshot=_complete_cleanup_snapshot(),
    )
    assert failure.reason == "stdout_overflow"
    assert failure.cleanup_events == ("term_signal_failed",)
    assert isinstance(failure.cleanup_snapshot, dict)
    assert failure.cleanup_snapshot["availability"] == "unavailable"


@pytest.mark.parametrize("deadline", ["ok", "exceeded", "failed"])
def test_cleanup_snapshot_deadline_observation_does_not_add_clock_samples(
    deadline: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import consumer

    class Child:
        pid = 4242
        stdout = None
        stderr = None

        def poll(self) -> int:
            return 0

    clocks = 0

    def clock() -> float:
        nonlocal clocks
        clocks += 1
        if clocks == 1 or deadline == "ok":
            return 0.0
        if deadline == "exceeded":
            return 2.0
        raise KeyboardInterrupt("PRIVATE-SNAPSHOT-CANARY")

    monkeypatch.setattr(time, "monotonic", clock)
    monkeypatch.setattr(consumer, "_group_state", lambda _pid: False)
    snapshot = consumer._CleanupSnapshot()
    events: list[str] = []
    result = consumer._finalize_child(cast(Any, Child()), None, {}, 1.0, events, snapshot=snapshot)
    document = consumer._cleanup_snapshot_document(snapshot)

    assert clocks == 2
    assert result is (deadline == "ok")
    assert document["availability"] == "complete"
    assert document["deadline_check"] == ("not_exceeded" if deadline == "ok" else deadline)
    assert document["group_gate"] is (deadline == "ok")
    assert document["cleanup_gate"] is result


def test_cleanup_snapshot_permission_denial_is_not_physical_presence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import signal

    from matryca_plumber.graph_gateway import consumer

    class Child:
        pid = 4242

        def poll(self) -> None:
            return None

    def killpg(_pid: int, signum: int) -> None:
        if signum != signal.SIGKILL:
            raise PermissionError("PRIVATE-SNAPSHOT-CANARY")

    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(time, "monotonic", lambda: 2.0)
    snapshot = consumer._CleanupSnapshot()
    events: list[str] = []
    result = consumer._kill_reap_fallback(cast(Any, Child()), 1.0, events, snapshot=snapshot)
    document = consumer._cleanup_snapshot_document(snapshot)

    assert result is False
    assert document["group_check"] == "present_or_denied_observed"
    assert document["child_poll"] == "no_returncode_observed"
    assert document["cleanup_gate"] is None


def test_cleanup_snapshot_interruption_preserves_owner_primary_and_readers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from matryca_plumber.graph_gateway import consumer

    class Pipe:
        closed = False

        def close(self) -> None:
            self.closed = True

    class Child:
        pid = 4242
        stdout = Pipe()
        stderr = Pipe()
        returncode = 0

        def poll(self) -> int:
            return 0

    child = Child()
    original = consumer._CleanupSnapshot.record
    calls = 0

    def interrupted_capture(self: Any, **values: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyboardInterrupt("PRIVATE-SNAPSHOT-CANARY")
        original(self, **values)

    def selector_failure() -> Any:
        raise RuntimeError("PRIMARY-SYNTHETIC-FAILURE")

    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(selectors, "DefaultSelector", selector_failure)
    monkeypatch.setattr(consumer, "_group_state", lambda _pid: False)
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(consumer._CleanupSnapshot, "record", interrupted_capture)
    with pytest.raises(consumer.ChildFailure) as failure:
        consumer._run_child(("synthetic",), cwd=tmp_path, env={})

    assert failure.value.reason == "internal"
    assert failure.value.cleanup_ok is False
    assert failure.value.cleanup_events == ("finalizer_failed",)
    assert child.stdout.closed is True
    assert child.stderr.closed is True
    assert isinstance(failure.value.cleanup_snapshot, dict)
    assert failure.value.cleanup_snapshot["availability"] == "unavailable"


def _eperm_cleanup_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    delayed_polls: int,
    final_deadline: bool = False,
    reader_failure: bool = False,
) -> tuple[bool, list[str], list[int]]:
    """Model a zombie's delayed poll visibility without sending a native signal."""
    import errno
    import os
    import signal
    import time

    from matryca_plumber.graph_gateway import consumer

    signals: list[int] = []

    class ZombieChild:
        pid = 4242
        stdout = None
        stderr = None
        returncode: int | None = None
        polls = 0

        def poll(self) -> int | None:
            self.polls += 1
            if self.polls > delayed_polls:
                self.returncode = 0
            return self.returncode

        def wait(self, timeout: float) -> int:
            self.returncode = 0
            return 0

    child = ZombieChild()

    def killpg(_group: int, signum: int) -> None:
        if child.returncode is not None:
            raise ProcessLookupError(errno.ESRCH, "synthetic absent group")
        if signum:
            signals.append(signum)
        raise PermissionError(errno.EPERM, "synthetic zombie-only group")

    class Reader:
        def close(self) -> None:
            if reader_failure:
                raise RuntimeError("synthetic reader close failure")

    clock = iter((0.0, 0.0, 2.0)) if final_deadline else None
    monkeypatch.setattr(os, "killpg", killpg)
    monkeypatch.setattr(time, "monotonic", lambda: next(clock) if clock else 0.0)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    events: list[str] = []
    ok = consumer._finalize_child(cast(Any, child), cast(Any, Reader()), {}, 1.0, events)
    assert child.returncode == 0
    assert all(value in (signal.SIGTERM, signal.SIGKILL) for value in signals)
    return ok, events, signals


@pytest.mark.parametrize("delayed_polls", [0, 1, 2])
def test_eperm_zombie_race_requires_reap_and_absence(
    delayed_polls: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok, events, signals = _eperm_cleanup_fixture(monkeypatch, delayed_polls=delayed_polls)
    assert ok is True
    assert events == []
    assert bool(signals) is (delayed_polls != 0)


@pytest.mark.parametrize("gate", ["deadline", "reader"])
def test_eperm_observations_survive_later_finalization_failure(
    gate: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    ok, events, _signals = _eperm_cleanup_fixture(
        monkeypatch,
        delayed_polls=1,
        final_deadline=gate == "deadline",
        reader_failure=gate == "reader",
    )
    assert ok is False
    assert "term_signal_failed" in events
    assert "term_signal_errno_eperm_failed" in events
    assert (
        "cleanup_deadline_exceeded" if gate == "deadline" else "selector_close_failed"
    ) in events


def test_eperm_observations_survive_cleanup_helper_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from matryca_plumber.graph_gateway import consumer

    original = consumer._cleanup_group

    def cleanup_then_interrupt(*args: Any, **kwargs: Any) -> bool:
        original(*args, **kwargs)
        raise KeyboardInterrupt("synthetic interruption after signal")

    monkeypatch.setattr(consumer, "_cleanup_group", cleanup_then_interrupt)
    ok, events, _signals = _eperm_cleanup_fixture(monkeypatch, delayed_polls=1)
    assert ok is False
    assert "group_finalize_failed" in events
    assert "term_signal_errno_eperm_failed" in events


def test_eperm_live_group_remains_unverified_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno
    import itertools
    import os
    import subprocess
    import time

    from matryca_plumber.graph_gateway import consumer

    class LiveChild:
        pid = 4242
        stdout = None
        stderr = None
        returncode = None

        def poll(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            raise subprocess.TimeoutExpired("synthetic", timeout)

    def denied(_group: int, _signum: int) -> None:
        raise PermissionError(errno.EPERM, "synthetic live permission denial")

    clock = itertools.count(step=0.1)
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(os, "killpg", denied)
    events: list[str] = []
    ok = consumer._finalize_child(cast(Any, LiveChild()), None, {}, 0.5, events)
    assert ok is False
    assert "cleanup_deadline_exceeded" in events
    assert "term_signal_errno_eperm_failed" in events
    assert "kill_signal_failed" in events


def test_eperm_observations_survive_final_snapshot_interruption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno
    import os
    import time

    from matryca_plumber.graph_gateway import consumer

    class Child:
        pid = 4242
        stdout = None
        stderr = None
        polls = 0

        def poll(self) -> int | None:
            self.polls += 1
            return None if self.polls == 1 else 0

    def denied(_group: int, _signum: int) -> None:
        raise PermissionError(errno.EPERM, "synthetic zombie")

    record = consumer._CleanupSnapshot.record

    def interrupted_final_capture(self: Any, **values: Any) -> None:
        if "cleanup_gate" in values:
            raise KeyboardInterrupt("synthetic final recording interruption")
        record(self, **values)

    states = iter((True, False))
    monkeypatch.setattr(consumer, "_group_state", lambda _group: next(states))
    monkeypatch.setattr(os, "killpg", denied)
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(consumer._CleanupSnapshot, "record", interrupted_final_capture)
    events: list[str] = []
    with pytest.raises(KeyboardInterrupt):
        consumer._finalize_child(
            cast(Any, Child()), None, {}, 1.0, events, snapshot=consumer._CleanupSnapshot()
        )
    assert "term_signal_errno_eperm_failed" in events


@pytest.mark.parametrize("initial_eperm", [True, False])
def test_eperm_post_wait_distinguishes_transient_denial_from_live_survivor(
    initial_eperm: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import errno
    import os
    import selectors
    import subprocess
    import time

    from matryca_plumber.graph_gateway import consumer

    class Pipe:
        closed = False

        def fileno(self) -> int:
            return 0

        def close(self) -> None:
            self.closed = True

    class Child:
        pid = 4242
        stdout = Pipe()
        stderr = Pipe()
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def wait(self, timeout: float) -> int:
            self.returncode = 0
            return 0

    class EmptySelector:
        def register(self, *_args: Any) -> None:
            pass

        def get_map(self) -> dict[str, object]:
            return {}

        def close(self) -> None:
            pass

    probes = 0

    def group_state(_group: int, signum: int) -> None:
        nonlocal probes
        assert signum == 0
        probes += 1
        if probes == 1:
            if initial_eperm:
                raise PermissionError(errno.EPERM, "synthetic exiting group")
            return
        raise ProcessLookupError(errno.ESRCH, "synthetic absent group")

    child = Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(selectors, "DefaultSelector", EmptySelector)
    monkeypatch.setattr(os, "set_blocking", lambda *_args: None)
    monkeypatch.setattr(os, "killpg", group_state)
    monkeypatch.setattr(time, "monotonic", lambda: 0.0)
    if initial_eperm:
        result = consumer._run_child(("synthetic",), cwd=tmp_path, env={})
        assert result.cleanup_ok is True
        assert result.cleanup_events == ()
    else:
        with pytest.raises(consumer.ChildFailure) as failure:
            consumer._run_child(("synthetic",), cwd=tmp_path, env={})
        assert failure.value.reason == "surviving_process_group"
        assert failure.value.cleanup_ok is True
    assert probes == 2
    assert child.stdout.closed and child.stderr.closed
