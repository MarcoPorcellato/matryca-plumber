"""Tests for clean-source release archive verification."""

from __future__ import annotations

import io
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
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
