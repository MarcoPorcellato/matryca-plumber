"""Strict contracts for independently provisioned release build environments."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

_SOURCE_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SDIST_NAME = re.compile(r"matryca_plumber-([A-Za-z0-9.!+_-]{1,128})\.tar\.gz\Z")
_UV_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*)\Z")
_PYTHON_VERSION = re.compile(r"3\.12\.[0-9]+(?:[A-Za-z0-9.+-]*)\Z")
_PACKAGE_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,198}[a-z0-9])?\Z")
_PACKAGE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}\Z")
_SUPPORTED_TARGETS = (("linux", "x64"), ("macos", "arm64"), ("windows", "x64"))
_TARGET_KEYS = tuple(
    f"{operating_system}-{architecture}" for operating_system, architecture in _SUPPORTED_TARGETS
)
_MAX_JSON_BYTES = 256 * 1024
_MAX_PACKAGES = 4096

_DESCRIPTOR_FIELDS = frozenset(
    {
        "schema_version",
        "source_commit",
        "source_tree",
        "binding_sha256",
        "sdist_name",
        "sdist_size",
        "sdist_sha256",
        "build_lock_sha256",
        "provisioning_recipe_sha256",
        "provisioning_evidence_sha256",
        "uv_version",
        "uv_sha256",
        "target_os",
        "target_architecture",
        "python_implementation",
        "python_version",
        "python_executable_sha256",
        "packages",
        "packages_sha256",
    }
)
_PACKAGE_FIELDS = frozenset({"name", "version"})
_EXPECTED_BINDING_FIELDS = frozenset(
    {"schema_version", "build_lock_sha256", "provisioning_recipe_sha256", "targets"}
)
_TARGET_BINDING_FIELDS = frozenset({"descriptor_sha256", "provisioning_evidence_sha256"})


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("Build-environment JSON contains a duplicate object key.")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"Build-environment JSON contains a non-standard constant: {value}.")


def _parse_json_object(raw: bytes, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > _MAX_JSON_BYTES:
        _fail(f"{label} JSON is empty or exceeds its size limit.")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(f"{label} JSON is malformed or exceeds parser limits.") from error
    if not isinstance(value, dict):
        _fail(f"{label} JSON must be an object.")
    return value


def _check_fields(value: object, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"{label} fields are invalid.")
    return value


def _check_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest.")
    return value


def _check_source_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _SOURCE_ID.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase full Git ID.")
    return value


def _canonical_manifest_bytes(packages: tuple[tuple[str, str], ...]) -> bytes:
    manifest = [{"name": name, "version": version} for name, version in packages]
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _validate_package_manifest(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or not value or len(value) > _MAX_PACKAGES:
        _fail("Build-environment package manifest is empty, invalid, or exceeds its count limit.")

    packages: list[tuple[str, str]] = []
    for item in value:
        package = _check_fields(item, _PACKAGE_FIELDS, "Build-environment package")
        name, version = package["name"], package["version"]
        if (
            not isinstance(name, str)
            or len(name) > 200
            or _PACKAGE_NAME.fullmatch(name) is None
            or canonicalize_name(name) != name
            or not isinstance(version, str)
            or _PACKAGE_VERSION.fullmatch(version) is None
        ):
            _fail("Build-environment package manifest contains invalid values.")
        try:
            Version(version)
        except InvalidVersion as error:
            raise ValueError(
                "Build-environment package manifest has an invalid version."
            ) from error
        packages.append((name, version))

    canonical = tuple(packages)
    if tuple(sorted(canonical)) != canonical or len({name for name, _ in canonical}) != len(
        canonical
    ):
        _fail("Build-environment package manifest is not canonical (sorted and unique).")
    return canonical


def _read_regular_json_file(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        _fail(f"{label} must be a regular, non-symlink JSON file.")
    try:
        before = path.stat()
        if before.st_size <= 0 or before.st_size > _MAX_JSON_BYTES:
            _fail(f"{label} size limit is exceeded.")
        with path.open("rb") as stream:
            raw = stream.read(_MAX_JSON_BYTES + 1)
        after = path.stat()
    except OSError as error:
        raise ValueError(f"Could not read {label}.") from error
    if (
        path.is_symlink()
        or not path.is_file()
        or len(raw) > _MAX_JSON_BYTES
        or len(raw) != before.st_size
        or after.st_size != before.st_size
    ):
        _fail(f"{label} changed while being read or exceeds its size limit.")
    return raw


@dataclass(frozen=True, slots=True)
class BuildEnvironmentDescriptor:
    """Path-free identity and complete package manifest for one provisioned target."""

    schema_version: int
    source_commit: str
    source_tree: str
    binding_sha256: str
    sdist_name: str
    sdist_size: int
    sdist_sha256: str
    build_lock_sha256: str
    provisioning_recipe_sha256: str
    provisioning_evidence_sha256: str
    uv_version: str
    uv_sha256: str
    target_os: str
    target_architecture: str
    python_implementation: str
    python_version: str
    python_executable_sha256: str
    packages: tuple[tuple[str, str], ...]
    packages_sha256: str

    @classmethod
    def from_bytes(cls, raw: bytes) -> BuildEnvironmentDescriptor:
        """Parse structurally valid schema v1 JSON; the loader binds its exact bytes."""
        document = _check_fields(
            _parse_json_object(raw, "Build-environment descriptor"),
            _DESCRIPTOR_FIELDS,
            "Build-environment descriptor",
        )
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            _fail("Build-environment descriptor schema version is unsupported.")

        source_commit = _check_source_id(document["source_commit"], "Source commit")
        source_tree = _check_source_id(document["source_tree"], "Source tree")
        binding_sha256 = _check_digest(document["binding_sha256"], "Bundle binding digest")
        sdist_name = document["sdist_name"]
        if not isinstance(sdist_name, str) or _SDIST_NAME.fullmatch(sdist_name) is None:
            _fail("Source distribution name is invalid.")
        sdist_version = _SDIST_NAME.fullmatch(sdist_name)
        assert sdist_version is not None
        try:
            Version(sdist_version.group(1))
        except InvalidVersion as error:
            raise ValueError("Source distribution version is invalid.") from error
        if type(document["sdist_size"]) is not int or document["sdist_size"] <= 0:
            _fail("Source distribution size must be a positive integer.")
        sdist_size = document["sdist_size"]

        sdist_sha256 = _check_digest(document["sdist_sha256"], "Source distribution digest")
        build_lock_sha256 = _check_digest(document["build_lock_sha256"], "Build lock digest")
        recipe_sha256 = _check_digest(
            document["provisioning_recipe_sha256"], "Provisioning recipe digest"
        )
        evidence_sha256 = _check_digest(
            document["provisioning_evidence_sha256"], "Provisioning evidence digest"
        )

        uv_version = document["uv_version"]
        if not isinstance(uv_version, str) or _UV_VERSION.fullmatch(uv_version) is None:
            _fail("uv version is invalid.")
        uv_sha256 = _check_digest(document["uv_sha256"], "uv executable digest")

        target_os = document["target_os"]
        target_architecture = document["target_architecture"]
        if (
            not isinstance(target_os, str)
            or not isinstance(target_architecture, str)
            or (target_os, target_architecture) not in _SUPPORTED_TARGETS
        ):
            _fail("Build-environment target operating system or architecture is unsupported.")

        python_implementation = document["python_implementation"]
        if python_implementation != "CPython":
            _fail("Build-environment Python implementation is unsupported.")
        python_version = document["python_version"]
        if not isinstance(python_version, str) or _PYTHON_VERSION.fullmatch(python_version) is None:
            _fail("Build-environment Python version is invalid.")
        python_executable_sha256 = _check_digest(
            document["python_executable_sha256"], "Python executable digest"
        )

        packages = _validate_package_manifest(document["packages"])
        packages_sha256 = _check_digest(
            document["packages_sha256"], "Build-environment package manifest digest"
        )
        observed_manifest_sha256 = hashlib.sha256(_canonical_manifest_bytes(packages)).hexdigest()
        if packages_sha256 != observed_manifest_sha256:
            _fail(
                "Build-environment package manifest digest does not match its canonical contents."
            )

        return cls(
            schema_version=1,
            source_commit=source_commit,
            source_tree=source_tree,
            binding_sha256=binding_sha256,
            sdist_name=sdist_name,
            sdist_size=sdist_size,
            sdist_sha256=sdist_sha256,
            build_lock_sha256=build_lock_sha256,
            provisioning_recipe_sha256=recipe_sha256,
            provisioning_evidence_sha256=evidence_sha256,
            uv_version=uv_version,
            uv_sha256=uv_sha256,
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
            python_executable_sha256=python_executable_sha256,
            packages=packages,
            packages_sha256=packages_sha256,
        )


def load_build_environment_descriptor(
    path: Path, *, expected_sha256: str
) -> BuildEnvironmentDescriptor:
    """Load only the descriptor whose exact bytes match a caller-supplied digest."""
    if not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None:
        _fail("An independent expected descriptor SHA-256 is required.")
    raw = _read_regular_json_file(path, "Build-environment descriptor")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail(
            "Build-environment descriptor differs from the independent expected descriptor SHA-256."
        )
    return BuildEnvironmentDescriptor.from_bytes(raw)


@dataclass(frozen=True, slots=True)
class TargetEnvironmentBinding:
    """Independent expected descriptor and provisioner-evidence digests for a target."""

    descriptor_sha256: str
    provisioning_evidence_sha256: str


@dataclass(frozen=True, slots=True)
class ExpectedBuildEnvironmentBindings:
    """Aggregator-owned bindings for every required target, not target admission."""

    schema_version: int
    build_lock_sha256: str
    provisioning_recipe_sha256: str
    targets: Mapping[str, TargetEnvironmentBinding]

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", MappingProxyType(dict(self.targets)))

    @classmethod
    def from_bytes(cls, raw: bytes) -> ExpectedBuildEnvironmentBindings:
        """Parse schema v1 independent target bindings with an exact target set."""
        document = _check_fields(
            _parse_json_object(raw, "Expected build-environment bindings"),
            _EXPECTED_BINDING_FIELDS,
            "Expected build-environment bindings",
        )
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            _fail("Expected build-environment bindings schema version is unsupported.")
        build_lock_sha256 = _check_digest(document["build_lock_sha256"], "Build lock digest")
        recipe_sha256 = _check_digest(
            document["provisioning_recipe_sha256"], "Provisioning recipe digest"
        )
        targets = document["targets"]
        if not isinstance(targets, dict) or set(targets) != set(_TARGET_KEYS):
            _fail("Expected build-environment bindings must include the exact target set.")

        parsed_targets: dict[str, TargetEnvironmentBinding] = {}
        for target in _TARGET_KEYS:
            binding = _check_fields(targets[target], _TARGET_BINDING_FIELDS, "Target binding")
            parsed_targets[target] = TargetEnvironmentBinding(
                descriptor_sha256=_check_digest(
                    binding["descriptor_sha256"], f"{target} descriptor digest"
                ),
                provisioning_evidence_sha256=_check_digest(
                    binding["provisioning_evidence_sha256"],
                    f"{target} provisioning evidence digest",
                ),
            )
        return cls(
            schema_version=1,
            build_lock_sha256=build_lock_sha256,
            provisioning_recipe_sha256=recipe_sha256,
            targets=parsed_targets,
        )


def load_expected_build_environment_bindings(path: Path) -> ExpectedBuildEnvironmentBindings:
    """Load the strict, path-free independent bindings consumed by aggregation."""
    raw = _read_regular_json_file(path, "Expected build-environment bindings")
    return ExpectedBuildEnvironmentBindings.from_bytes(raw)
