"""Contracts for independently bound release build-environment descriptors."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_ENVIRONMENT_MODULE = "scripts.release_qualification.build_environment"
TARGETS = ("linux-x64", "macos-arm64", "windows-x64")


def _contract() -> ModuleType:
    if importlib.util.find_spec(BUILD_ENVIRONMENT_MODULE) is None:
        pytest.fail("the release build-environment contract has not been implemented")
    return importlib.import_module(BUILD_ENVIRONMENT_MODULE)


def _packages() -> list[dict[str, str]]:
    return [
        {"name": "packaging", "version": "24.2"},
        {"name": "setuptools", "version": "75.6.0"},
    ]


def _manifest_sha256(packages: list[dict[str, str]]) -> str:
    canonical = json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _descriptor_document() -> dict[str, object]:
    packages = _packages()
    return {
        "schema_version": 1,
        "source_commit": "1" * 40,
        "source_tree": "2" * 40,
        "binding_sha256": "3" * 64,
        "sdist_name": "matryca_plumber-2.0.1rc4.tar.gz",
        "sdist_size": 1234,
        "sdist_sha256": "4" * 64,
        "build_lock_sha256": "5" * 64,
        "provisioning_recipe_sha256": "6" * 64,
        "provisioning_evidence_sha256": "7" * 64,
        "uv_version": "0.9.15",
        "uv_sha256": "8" * 64,
        "target_os": "linux",
        "target_architecture": "x64",
        "python_implementation": "CPython",
        "python_version": "3.12.8",
        "python_executable_sha256": "9" * 64,
        "packages": packages,
        "packages_sha256": _manifest_sha256(packages),
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _expected_bindings_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "build_lock_sha256": "a" * 64,
        "provisioning_recipe_sha256": "b" * 64,
        "targets": {
            target: {
                "descriptor_sha256": str(index) * 64,
                "provisioning_evidence_sha256": str(index + 3) * 64,
            }
            for index, target in enumerate(TARGETS, start=1)
        },
    }


def test_provisioning_recipe_is_fixed_and_path_free() -> None:
    recipe_path = REPOSITORY_ROOT / "release-qualification-build" / "provisioning-recipe.json"
    assert recipe_path.is_file(), "the qualification provisioning recipe must be checked in"
    recipe = json.loads(recipe_path.read_bytes())

    assert recipe == {
        "schema_version": 1,
        "project": "release-qualification-build",
        "lockfile": "uv.lock",
        "operation": "uv-sync-locked",
        "project_installation_allowed": False,
        "resolution_allowed": False,
        "repair_allowed": False,
        "verify_locked_artifact_hashes": True,
    }


def test_descriptor_requires_independent_expected_sha256(tmp_path: Path) -> None:
    contract = _contract()
    descriptor_path = tmp_path / "descriptor.json"
    raw = _json_bytes(_descriptor_document())
    descriptor_path.write_bytes(raw)

    with pytest.raises(TypeError):
        contract.load_build_environment_descriptor(descriptor_path)
    with pytest.raises(ValueError, match="expected descriptor SHA-256"):
        contract.load_build_environment_descriptor(
            descriptor_path,
            expected_sha256="0" * 64,
        )


@pytest.mark.parametrize("schema_version", [2, True])
def test_descriptor_rejects_wrong_schema_version(schema_version: object) -> None:
    document = _descriptor_document()
    document["schema_version"] = schema_version

    with pytest.raises(ValueError, match="schema version"):
        _contract().BuildEnvironmentDescriptor.from_bytes(_json_bytes(document))


@pytest.mark.parametrize(
    ("field_changes"),
    [
        {"source_commit": "f" * 40},
        {"build_lock_sha256": "e" * 64},
        {"uv_sha256": "d" * 64},
        {"target_os": "macos", "target_architecture": "arm64"},
    ],
)
def test_descriptor_rejects_source_lock_tool_and_target_mismatch(
    tmp_path: Path, field_changes: dict[str, str]
) -> None:
    document = _descriptor_document()
    original_sha256 = hashlib.sha256(_json_bytes(document)).hexdigest()
    document.update(field_changes)
    descriptor_path = tmp_path / "descriptor.json"
    descriptor_path.write_bytes(_json_bytes(document))

    with pytest.raises(ValueError, match="expected descriptor SHA-256"):
        _contract().load_build_environment_descriptor(
            descriptor_path,
            expected_sha256=original_sha256,
        )


@pytest.mark.parametrize(
    ("field_changes"),
    [
        {"target_os": "linux", "target_architecture": "arm64"},
        {"target_os": "windows", "target_architecture": "arm64"},
        {"target_os": "macos", "target_architecture": "x64"},
        {"python_implementation": "PyPy"},
        {"python_version": "3.13.0"},
    ],
)
def test_descriptor_rejects_unsupported_environment_context(
    field_changes: dict[str, str],
) -> None:
    document = _descriptor_document()
    document.update(field_changes)

    with pytest.raises(ValueError):
        _contract().BuildEnvironmentDescriptor.from_bytes(_json_bytes(document))


def test_descriptor_rejects_duplicate_and_unknown_fields() -> None:
    raw = _json_bytes(_descriptor_document())
    duplicate_key = raw.replace(
        b'"schema_version":1',
        b'"schema_version":1,"schema_version":1',
        1,
    )
    assert duplicate_key != raw

    with pytest.raises(ValueError, match="duplicate"):
        _contract().BuildEnvironmentDescriptor.from_bytes(duplicate_key)

    document = _descriptor_document()
    document["unexpected"] = "not accepted"
    with pytest.raises(ValueError, match="fields"):
        _contract().BuildEnvironmentDescriptor.from_bytes(_json_bytes(document))


def test_descriptor_manifest_is_canonical_and_complete() -> None:
    contract = _contract()
    descriptor = contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(_descriptor_document()))
    assert descriptor.packages == (("packaging", "24.2"), ("setuptools", "75.6.0"))

    unsorted_document = _descriptor_document()
    unsorted_packages = list(reversed(_packages()))
    unsorted_document["packages"] = unsorted_packages
    unsorted_document["packages_sha256"] = _manifest_sha256(unsorted_packages)
    with pytest.raises(ValueError, match="canonical"):
        contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(unsorted_document))

    duplicate_document = _descriptor_document()
    duplicate_packages = _packages() + [_packages()[0]]
    duplicate_document["packages"] = duplicate_packages
    duplicate_document["packages_sha256"] = _manifest_sha256(duplicate_packages)
    with pytest.raises(ValueError, match="canonical|unique"):
        contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(duplicate_document))

    incomplete_document = _descriptor_document()
    incomplete_packages = [{"name": "setuptools"}]
    incomplete_document["packages"] = incomplete_packages
    incomplete_document["packages_sha256"] = _manifest_sha256(
        [{"name": "setuptools", "version": "75.6.0"}]
    )
    with pytest.raises(ValueError, match="package"):
        contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(incomplete_document))

    empty_document = _descriptor_document()
    empty_document["packages"] = []
    empty_document["packages_sha256"] = hashlib.sha256(b"[]").hexdigest()
    with pytest.raises(ValueError, match="package"):
        contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(empty_document))

    digest_mismatch_document = _descriptor_document()
    digest_mismatch_document["packages_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="manifest digest"):
        contract.BuildEnvironmentDescriptor.from_bytes(_json_bytes(digest_mismatch_document))


def test_expected_build_bindings_require_exact_target_set(tmp_path: Path) -> None:
    contract = _contract()
    document = _expected_bindings_document()
    bindings = contract.ExpectedBuildEnvironmentBindings.from_bytes(_json_bytes(document))
    assert tuple(bindings.targets) == TARGETS
    with pytest.raises(TypeError):
        bindings.targets["linux-x64"] = bindings.targets["linux-x64"]

    missing_target = _expected_bindings_document()
    del missing_target["targets"]["windows-x64"]  # type: ignore[index]
    with pytest.raises(ValueError, match="target"):
        contract.ExpectedBuildEnvironmentBindings.from_bytes(_json_bytes(missing_target))

    extra_target = _expected_bindings_document()
    extra_target["targets"]["freebsd-x64"] = {  # type: ignore[index]
        "descriptor_sha256": "c" * 64,
        "provisioning_evidence_sha256": "d" * 64,
    }
    with pytest.raises(ValueError, match="target"):
        contract.ExpectedBuildEnvironmentBindings.from_bytes(_json_bytes(extra_target))

    bindings_path = tmp_path / "expected-build-environments.json"
    bindings_path.write_bytes(_json_bytes(document))
    loaded = contract.load_expected_build_environment_bindings(bindings_path)
    assert loaded == bindings
