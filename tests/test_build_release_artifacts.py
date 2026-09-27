"""Tests for clean-source release archive verification."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
import scripts.build_release_artifacts as release_builder
from scripts.build_release_artifacts import (
    _REQUIRED_MEMBERS,
    _normalize_sdist_timestamps,
    _tracked_snapshot,
    build_release_artifacts,
    verify_release_archives,
)

_PUBLIC_CONTRACT_RESOURCE_MEMBERS = (
    "src/contract_artifacts/contracts/plumber.consumer.package/v1/fixtures/matryca-brain-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.consumer.package/v1/fixtures/matryca-trama-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.consumer.package/v1/manifest.json",
    "src/contract_artifacts/contracts/plumber.consumer.package/v1/schema.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/consumer-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/foreign-graph-rejected-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/identify-pass-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/incomplete-subtree-rejected-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/ordered-subtree-pass-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/page-read-pass-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/producer-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/fixtures/unsupported-capability-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/manifest.json",
    "src/contract_artifacts/contracts/plumber.graph.read/v1/schema.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/closed-session-rejected-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/consumer-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/foreign-graph-rejected-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/incomplete-topology-rejected-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/producer-profile-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/topology-complete-pass-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/fixtures/unsupported-capability-v1.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/manifest.json",
    "src/contract_artifacts/contracts/plumber.graph.topology/v1/schema.json",
    "src/contract_artifacts/tck/run_plumber_consumer_package_v1_tck.py",
    "src/contract_artifacts/tck/run_plumber_graph_read_v1_tck.py",
    "src/contract_artifacts/tck/run_plumber_graph_topology_v1_tck.py",
)
_SOURCE_CONTRACT_RESOURCE_MEMBERS = tuple(
    member.replace("src/contract_artifacts/contracts/", "contracts/").replace(
        "src/contract_artifacts/tck/", "scripts/"
    )
    for member in _PUBLIC_CONTRACT_RESOURCE_MEMBERS
)


def _metadata(version: str) -> bytes:
    return f"Metadata-Version: 2.4\nName: matryca-plumber\nVersion: {version}\n".encode()


def _write_wheel(
    path: Path,
    version: str,
    extra_members: tuple[str, ...] = (),
    *,
    include_public_contract_resources: bool = True,
) -> None:
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("src/__init__.py", "")
        bundle.writestr("frontend/dist/index.html", "<!doctype html>")
        bundle.writestr(f"matryca_plumber-{version}.dist-info/METADATA", _metadata(version))
        if include_public_contract_resources:
            for member in _PUBLIC_CONTRACT_RESOURCE_MEMBERS:
                bundle.writestr(member, "public static contract resource")
        for member in extra_members:
            bundle.writestr(member, "forbidden")


def _write_sdist(
    path: Path,
    version: str,
    extra_members: tuple[str, ...] = (),
    *,
    include_public_contract_resources: bool = True,
) -> None:
    prefix = f"matryca_plumber-{version}"
    with tarfile.open(path, "w:gz") as bundle:
        for member, content in (
            (f"{prefix}/src/__init__.py", b""),
            (f"{prefix}/frontend/dist/index.html", b"<!doctype html>"),
            (f"{prefix}/PKG-INFO", _metadata(version)),
            *(
                (f"{prefix}/{member}", b"public static contract resource")
                for member in _SOURCE_CONTRACT_RESOURCE_MEMBERS
                if include_public_contract_resources
            ),
            *((f"{prefix}/{member}", b"forbidden") for member in extra_members),
        ):
            info = tarfile.TarInfo(member)
            info.size = len(content)
            bundle.addfile(info, io.BytesIO(content))


def _write_archives(tmp_path: Path, version: str = "2.0.0a5") -> None:
    _write_wheel(tmp_path / f"matryca_plumber-{version}-py3-none-any.whl", version)
    _write_sdist(tmp_path / f"matryca_plumber-{version}.tar.gz", version)


def test_verify_release_archives_accepts_matching_complete_archives(tmp_path: Path) -> None:
    _write_archives(tmp_path)

    wheel, sdist = verify_release_archives(tmp_path, "2.0.0-alpha.5")

    assert wheel.suffix == ".whl"
    assert sdist.name.endswith(".tar.gz")


def test_verify_release_archives_rejects_compiled_cache_in_wheel(tmp_path: Path) -> None:
    _write_archives(tmp_path)
    wheel = next(tmp_path.glob("*.whl"))
    _write_wheel(wheel, "2.0.0a5", ("frontend/dist/__pycache__/stale.pyc",))

    with pytest.raises(ValueError, match="compiled Python artifacts"):
        verify_release_archives(tmp_path, "2.0.0-alpha.5")


def test_verify_release_archives_rejects_version_drift(tmp_path: Path) -> None:
    _write_archives(tmp_path, "2.0.0a4")

    with pytest.raises(ValueError, match="metadata version"):
        verify_release_archives(tmp_path, "2.0.0-alpha.5")


def test_verify_release_archives_rejects_missing_frontend_content(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "matryca_plumber-2.0.0a5-py3-none-any.whl", "2.0.0a5")
    _write_sdist(tmp_path / "matryca_plumber-2.0.0a5.tar.gz", "2.0.0a5")
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel, "w") as bundle:
        bundle.writestr("src/__init__.py", "")
        bundle.writestr("matryca_plumber-2.0.0a5.dist-info/METADATA", _metadata("2.0.0a5"))

    with pytest.raises(ValueError, match="missing required release content"):
        verify_release_archives(tmp_path, "2.0.0-alpha.5")


def test_verify_release_archives_requires_public_contract_resources(tmp_path: Path) -> None:
    assert set(_PUBLIC_CONTRACT_RESOURCE_MEMBERS).issubset(_REQUIRED_MEMBERS)
    assert "contracts/plumber.graph.topology/v1/schema.json" in _SOURCE_CONTRACT_RESOURCE_MEMBERS
    assert "scripts/run_plumber_graph_topology_v1_tck.py" in _SOURCE_CONTRACT_RESOURCE_MEMBERS
    _write_wheel(
        tmp_path / "matryca_plumber-2.0.0a5-py3-none-any.whl",
        "2.0.0a5",
        include_public_contract_resources=False,
    )
    _write_sdist(
        tmp_path / "matryca_plumber-2.0.0a5.tar.gz",
        "2.0.0a5",
        include_public_contract_resources=False,
    )

    with pytest.raises(ValueError, match="missing required release content"):
        verify_release_archives(tmp_path, "2.0.0-alpha.5")


def test_normalize_sdist_timestamps_makes_equivalent_archives_byte_identical(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    for archive, timestamp in ((first, 10), (second, 20)):
        with tarfile.open(archive, "w:gz") as bundle:
            info = tarfile.TarInfo("package/file.txt")
            info.mtime = timestamp
            payload = b"same payload"
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))

    _normalize_sdist_timestamps(first, 1)
    _normalize_sdist_timestamps(second, 1)

    assert first.read_bytes() == second.read_bytes()


def test_tracked_snapshot_excludes_ignored_build_residue(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / ".gitignore").write_text(
        "__pycache__/\n*.pyc\nfrontend/dist/\nbuild/\n*.egg-info/\n", encoding="utf-8"
    )
    (repo / "tracked.txt").write_text("tracked input\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "tracked release input",
        ],
        cwd=repo,
        check=True,
    )

    ignored_files = (
        repo / "src" / "__pycache__" / "module.cpython-312.pyc",
        repo / "frontend" / "dist" / "stale.js",
        repo / "build" / "lib" / "generated.py",
        repo / "matryca_plumber.egg-info" / "SOURCES.txt",
    )
    for path in ignored_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored residue\n", encoding="utf-8")

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    _tracked_snapshot(repo, snapshot)

    assert (snapshot / "tracked.txt").read_text(encoding="utf-8") == "tracked input\n"
    assert all(not (snapshot / path.relative_to(repo)).exists() for path in ignored_files)


def test_build_release_artifacts_refuses_nonempty_output_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist"
    output_dir.mkdir()
    (output_dir / "existing-artifact.whl").write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="Refusing to mix release artifacts"):
        build_release_artifacts(tmp_path / "unused-repository", output_dir)


def _release_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "[project]\nname='matryca-plumber'\nversion='2.0.1rc4'\n", encoding="utf-8"
    )
    (repo / "src").mkdir()
    (repo / "src" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "src" / "worker.py").write_text("VALUE = 7\n", encoding="utf-8")
    (repo / "frontend").mkdir()
    (repo / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    for member in _PUBLIC_CONTRACT_RESOURCE_MEMBERS:
        path = repo / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"public static contract resource")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-qm",
            "release fixture",
        ],
        cwd=repo,
        check=True,
    )
    return repo


def _fake_release_commands(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> None:
    if command[0] == "git":
        subprocess.run(command, cwd=cwd, check=True, env=env)
        return
    if command[:3] == ["npm", "run", "build"]:
        output = cwd / "dist" / "index.html"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("<!doctype html>\n", encoding="utf-8")
    elif command[:3] == ["uv", "build", "--sdist"]:
        artifacts = Path(command[4])
        artifacts.mkdir(parents=True, exist_ok=True)
        _write_sdist(artifacts / "matryca_plumber-2.0.1rc4.tar.gz", "2.0.1rc4")
    elif command[:3] == ["uv", "build", "--wheel"]:
        artifacts = Path(command[4])
        _write_wheel(artifacts / "matryca_plumber-2.0.1rc4-py3-none-any.whl", "2.0.1rc4")


def test_builder_default_keeps_only_the_two_distribution_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _release_repo(tmp_path)
    monkeypatch.setattr(release_builder, "_run", _fake_release_commands)
    monkeypatch.setattr(
        release_builder,
        "_snapshot_records",
        lambda _root: pytest.fail("default artifact build must not snapshot file records"),
    )
    check_output_commands: list[list[str]] = []
    original_check_output = subprocess.check_output

    def record_check_output(command: list[str], *, cwd: Path, text: bool) -> str:
        check_output_commands.append(command)
        result = original_check_output(command, cwd=cwd, text=text)
        assert isinstance(result, str)
        return result

    monkeypatch.setattr(subprocess, "check_output", record_check_output)
    output = tmp_path / "dist"

    wheel, sdist = build_release_artifacts(repo, output)

    assert {path.name for path in output.iterdir()} == {wheel.name, sdist.name}
    assert wheel.suffix == ".whl"
    assert sdist.name.endswith(".tar.gz")
    assert check_output_commands == [["git", "log", "-1", "--format=%ct", "HEAD"]]


def test_builder_writes_optional_ledger_outside_output_after_archive_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _release_repo(tmp_path)
    monkeypatch.setattr(release_builder, "_run", _fake_release_commands)
    output = tmp_path / "dist"
    ledger = tmp_path / "evidence" / "content-ledger.json"

    build_release_artifacts(repo, output, content_ledger_path=ledger)

    content = json.loads(ledger.read_text(encoding="utf-8"))
    tracked = {item["name"]: item["sha256"] for item in content["selected_source_files"]}
    generated = {item["name"]: item["sha256"] for item in content["frontend_files"]}
    assert tracked["src/worker.py"]
    assert generated == {
        "frontend/dist/index.html": hashlib.sha256(b"<!doctype html>\n").hexdigest()
    }
    assert {path.name for path in output.iterdir()} == {
        "matryca_plumber-2.0.1rc4-py3-none-any.whl",
        "matryca_plumber-2.0.1rc4.tar.gz",
    }


def test_builder_default_still_rejects_empty_frontend_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _release_repo(tmp_path)

    def fake_empty_frontend(
        command: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> None:
        if command[0] == "git":
            subprocess.run(command, cwd=cwd, check=True, env=env)
        elif command[:3] == ["npm", "run", "build"]:
            (cwd / "dist").mkdir()

    monkeypatch.setattr(release_builder, "_run", fake_empty_frontend)

    with pytest.raises(ValueError, match="Frontend build produced no files"):
        build_release_artifacts(repo, tmp_path / "dist")


def test_builder_rejects_ledger_inside_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "dist"

    with pytest.raises(ValueError, match="outside"):
        build_release_artifacts(
            tmp_path / "unused-repository", output, content_ledger_path=output / "ledger.json"
        )


def test_builder_does_not_write_ledger_when_archive_build_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _release_repo(tmp_path)

    def fail_wheel(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
        if command[0] == "git":
            subprocess.run(command, cwd=cwd, check=True, env=env)
            return
        if command[:3] == ["uv", "build", "--sdist"]:
            artifacts = Path(command[4])
            artifacts.mkdir(parents=True, exist_ok=True)
            _write_sdist(artifacts / "matryca_plumber-2.0.1rc4.tar.gz", "2.0.1rc4")
            return
        if command[:3] == ["uv", "build", "--wheel"]:
            raise RuntimeError("synthetic wheel build failure")
        if command[:3] == ["npm", "run", "build"]:
            output = cwd / "dist" / "index.html"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("<!doctype html>\n", encoding="utf-8")

    monkeypatch.setattr(release_builder, "_run", fail_wheel)
    ledger = tmp_path / "evidence" / "ledger.json"

    with pytest.raises(RuntimeError, match="synthetic wheel build failure"):
        build_release_artifacts(repo, tmp_path / "dist", content_ledger_path=ledger)

    assert not ledger.exists()


def test_content_ledger_publication_does_not_overwrite_concurrent_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = tmp_path / "content-ledger.json"
    original_link = os.link
    concurrent_payload = b"concurrent writer owns this path\n"
    attempted = False

    def race_link(source: str | Path, destination: str | Path) -> None:
        nonlocal attempted
        attempted = True
        Path(destination).write_bytes(concurrent_payload)
        original_link(source, destination)

    monkeypatch.setattr(os, "link", race_link)

    with pytest.raises(FileExistsError):
        release_builder._write_content_ledger(ledger, {"schema_version": 1})

    assert attempted
    assert ledger.read_bytes() == concurrent_payload
