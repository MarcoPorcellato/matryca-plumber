"""Contract for the isolated release-qualification build inputs."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROJECT_PATH = REPOSITORY_ROOT / "pyproject.toml"
RUNTIME_LOCK_PATH = REPOSITORY_ROOT / "uv.lock"
QUALIFICATION_PROJECT_DIRECTORY = REPOSITORY_ROOT / "release-qualification-build"
QUALIFICATION_PROJECT_PATH = QUALIFICATION_PROJECT_DIRECTORY / "pyproject.toml"
QUALIFICATION_LOCK_PATH = QUALIFICATION_PROJECT_DIRECTORY / "uv.lock"


def test_qualification_build_project_is_separate_from_runtime_project() -> None:
    assert QUALIFICATION_PROJECT_PATH != RUNTIME_PROJECT_PATH
    assert QUALIFICATION_LOCK_PATH != RUNTIME_LOCK_PATH
    assert QUALIFICATION_PROJECT_DIRECTORY != REPOSITORY_ROOT
    assert QUALIFICATION_PROJECT_PATH.is_file(), (
        "the qualification build project must have its own pyproject.toml"
    )
    assert QUALIFICATION_LOCK_PATH.is_file(), (
        "the qualification build project must have its own resolved lock"
    )


def test_qualification_build_lock_contains_reviewed_static_closure() -> None:
    assert QUALIFICATION_LOCK_PATH.is_file(), (
        "the qualification build lock must exist before its closure can be reviewed"
    )

    lock = tomllib.loads(QUALIFICATION_LOCK_PATH.read_text(encoding="utf-8"))
    package_records = lock["package"]
    packages_by_name = {package["name"]: package for package in package_records}

    assert len(packages_by_name) == len(package_records)
    assert set(packages_by_name) == {
        "matryca-plumber-release-qualification-build",
        "packaging",
        "setuptools",
        "wheel",
    }
    assert packages_by_name["matryca-plumber-release-qualification-build"] == {
        "name": "matryca-plumber-release-qualification-build",
        "version": "0.0.0",
        "source": {"virtual": "."},
        "dependencies": [{"name": "setuptools"}, {"name": "wheel"}],
        "metadata": {
            "requires-dist": [
                {"name": "setuptools", "specifier": ">=61"},
                {"name": "wheel"},
            ]
        },
    }

    reviewed_versions = {
        "packaging": "26.3",
        "setuptools": "84.0.0",
        "wheel": "0.48.0",
    }
    for name, version in reviewed_versions.items():
        assert packages_by_name[name]["version"] == version
        assert packages_by_name[name]["source"] == {"registry": "https://pypi.org/simple"}

    assert packages_by_name["packaging"].get("dependencies", []) == []
    assert packages_by_name["setuptools"].get("dependencies", []) == []
    assert packages_by_name["wheel"]["dependencies"] == [{"name": "packaging"}]


def test_qualification_build_project_declares_only_reviewed_static_inputs() -> None:
    assert QUALIFICATION_PROJECT_PATH.is_file(), (
        "the qualification build project must exist before its inputs can be reviewed"
    )

    runtime_project = tomllib.loads(RUNTIME_PROJECT_PATH.read_text(encoding="utf-8"))
    qualification_project = tomllib.loads(QUALIFICATION_PROJECT_PATH.read_text(encoding="utf-8"))

    reviewed_static_build_requirements = ["setuptools>=61", "wheel"]
    static_build_requirements = runtime_project["build-system"]["requires"]
    qualification_metadata = qualification_project["project"]
    direct_build_inputs = qualification_metadata["dependencies"]

    assert static_build_requirements == reviewed_static_build_requirements
    assert direct_build_inputs == reviewed_static_build_requirements
    assert "optional-dependencies" not in qualification_metadata
    assert "dependency-groups" not in qualification_project
    assert (
        qualification_metadata["requires-python"] == runtime_project["project"]["requires-python"]
    )
    assert qualification_project["tool"]["uv"] == {"package": False}
