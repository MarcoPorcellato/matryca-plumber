#!/usr/bin/env python3
"""Build release archives from a clean, tracked source snapshot."""

from __future__ import annotations

import argparse
import copy
import gzip
import os
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_FORBIDDEN_SUFFIXES = {".pyc", ".pyd", ".pyo"}
_REQUIRED_MEMBERS = {"src/__init__.py", "frontend/dist/index.html"}


def project_version(repo_root: Path) -> str:
    """Return the declared project version from the release source."""
    with (repo_root / "pyproject.toml").open("rb") as handle:
        pyproject = tomllib.load(handle)
    return str(pyproject["project"]["version"])


def normalized_version(version: str) -> str:
    """Normalize the prerelease spellings used by setuptools metadata."""
    return version.replace("-alpha.", "a").replace("-beta.", "b").replace("-rc.", "rc")


def _archive_members(archive: Path) -> tuple[list[str], bytes]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.namelist()
            metadata = next(name for name in members if name.endswith(".dist-info/METADATA"))
            return members, bundle.read(metadata)

    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getnames()
        metadata = next(name for name in members if name.endswith("/PKG-INFO"))
        member = bundle.extractfile(metadata)
        if member is None:
            raise ValueError(f"Could not read {metadata} from {archive}")
        return members, member.read()


def _artifact_paths(output_dir: Path) -> tuple[Path, Path]:
    wheels = sorted(output_dir.glob("*.whl"))
    sdist = _single_sdist(output_dir)
    if len(wheels) != 1:
        raise ValueError(
            "Expected exactly one wheel and one source distribution in "
            f"{output_dir}, found {len(wheels)} wheel(s) and one source distribution."
        )
    return wheels[0], sdist


def _single_sdist(output_dir: Path) -> Path:
    sdists = sorted(output_dir.glob("*.tar.gz"))
    if len(sdists) != 1:
        raise ValueError(
            f"Expected exactly one source distribution in {output_dir}, found {len(sdists)}."
        )
    return sdists[0]


def verify_release_archives(output_dir: Path, expected_version: str) -> tuple[Path, Path]:
    """Reject incomplete, stale, or compiled-artifact release archives."""
    wheel, sdist = _artifact_paths(output_dir)
    expected_metadata_version = normalized_version(expected_version)

    for archive in (wheel, sdist):
        members, raw_metadata = _archive_members(archive)
        metadata = BytesParser().parsebytes(raw_metadata)
        if metadata["Version"] != expected_metadata_version:
            raise ValueError(
                f"{archive.name}: metadata version {metadata['Version']!r} does not match "
                f"{expected_metadata_version!r}."
            )

        normalized_members = {
            "/".join(Path(member).parts[1:]) if archive.suffix != ".whl" else member
            for member in members
        }
        missing = _REQUIRED_MEMBERS - normalized_members
        if missing:
            raise ValueError(f"{archive.name}: missing required release content: {sorted(missing)}")

        forbidden = [
            member
            for member in members
            if "__pycache__" in Path(member).parts
            or Path(member).suffix.lower() in _FORBIDDEN_SUFFIXES
        ]
        if forbidden:
            raise ValueError(
                f"{archive.name}: compiled Python artifacts are not permitted: {forbidden}"
            )

    return wheel, sdist


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True, env=env)


def _source_date_epoch(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%ct", "HEAD"], cwd=repo_root, text=True
    ).strip()


def _normalize_sdist_timestamps(archive: Path, epoch: int) -> None:
    """Rewrite tar and gzip timestamps without changing the sdist payload."""
    normalized_tar = archive.parent / f"{archive.stem}.normalized.tar"
    normalized_archive = archive.parent / f"{archive.name}.normalized"
    with (
        tarfile.open(archive, "r:gz") as source,
        tarfile.open(normalized_tar, "w", format=tarfile.PAX_FORMAT) as destination,
    ):
        for member in source:
            normalized = copy.copy(member)
            normalized.mtime = epoch
            normalized.uid = 0
            normalized.gid = 0
            normalized.uname = ""
            normalized.gname = ""
            normalized.pax_headers = {
                key: value for key, value in normalized.pax_headers.items() if key != "mtime"
            }
            if member.isfile():
                payload = source.extractfile(member)
                if payload is None:
                    raise ValueError(f"Could not read {member.name} from {archive}")
                destination.addfile(normalized, payload)
            else:
                destination.addfile(normalized)

    with (
        normalized_tar.open("rb") as source,
        normalized_archive.open("wb") as target,
        gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=epoch) as destination,
    ):
        shutil.copyfileobj(source, destination)
    normalized_tar.unlink()
    normalized_archive.replace(archive)


def _tracked_snapshot(repo_root: Path, destination: Path) -> None:
    archive = destination.parent / "source.tar"
    _run(["git", "archive", "--format=tar", f"--output={archive}", "HEAD"], cwd=repo_root)
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")


def build_release_artifacts(repo_root: Path, output_dir: Path) -> tuple[Path, Path]:
    """Build an sdist and a wheel from a disposable clean source snapshot."""
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Refusing to mix release artifacts with existing files in {output_dir}")

    expected_version = project_version(repo_root)
    source_date_epoch = _source_date_epoch(repo_root)
    build_env = {**os.environ, "SOURCE_DATE_EPOCH": source_date_epoch}
    with tempfile.TemporaryDirectory(prefix="matryca-release-build-") as temporary:
        staging_root = Path(temporary)
        source_root = staging_root / "source"
        source_root.mkdir()
        _tracked_snapshot(repo_root, source_root)

        frontend = source_root / "frontend"
        _run(["npm", "ci"], cwd=frontend, env=build_env)
        _run(["npm", "run", "build"], cwd=frontend, env=build_env)

        artifacts = staging_root / "artifacts"
        artifacts.mkdir()
        _run(
            ["uv", "build", "--sdist", "--out-dir", str(artifacts), str(source_root)],
            cwd=source_root,
            env=build_env,
        )
        sdist = _single_sdist(artifacts)
        _normalize_sdist_timestamps(sdist, int(source_date_epoch))
        _run(
            ["uv", "build", "--wheel", "--out-dir", str(artifacts), str(sdist)],
            cwd=source_root,
            env=build_env,
        )
        wheel, sdist = verify_release_archives(artifacts, expected_version)

        output_dir.mkdir(parents=True, exist_ok=True)
        copied_wheel = output_dir / wheel.name
        copied_sdist = output_dir / sdist.name
        shutil.copy2(wheel, copied_wheel)
        shutil.copy2(sdist, copied_sdist)
        return copied_wheel, copied_sdist


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()

    wheel, sdist = build_release_artifacts(args.repo_root.resolve(), args.output_dir.resolve())
    print(f"release archives built: {sdist} {wheel}")


if __name__ == "__main__":
    main()
