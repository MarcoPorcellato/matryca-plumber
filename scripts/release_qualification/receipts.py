"""Fail-closed validation for sanitized cross-platform qualification receipts."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, NoReturn

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.focused import focused_nodes
from scripts.release_qualification.sdist_build import _marker_environment

_SOURCE_ID = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ARTIFACT_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DECIMAL_ID = re.compile(r"[1-9][0-9]*\Z")
_UV_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-zA-Z0-9.+-]*)\Z")
_PYTHON_VERSION = re.compile(r"3\.12\.[0-9]+(?:[a-zA-Z0-9.+-]*)\Z")
_GENERATOR_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}\Z")
_DEPENDENCY_NAME = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,198}[a-z0-9])?\Z")
_DEPENDENCY_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}\Z")
_MAX_RECEIPT_BYTES = 256 * 1024
_MAX_LOCK_BYTES = 2 * 1024 * 1024
_MAX_DEPENDENCIES = 4096
_MAX_BUILD_REQUIREMENTS = 256
_MAX_BUILD_REQUIREMENT_LENGTH = 2048
_MAX_BUILD_WHEEL_BYTES = 512 * 1024 * 1024
_MAX_SOURCE_METADATA_BYTES = 1024 * 1024
_PLATFORMS = (("linux", "x64"), ("macos", "arm64"), ("windows", "x64"))
_RECEIPT_FIELDS = frozenset(
    {
        "run_id",
        "source_sha",
        "source_tree",
        "artifact_id",
        "artifact_digest",
        "os",
        "architecture",
        "lock_sha256",
        "uv",
        "wheel",
        "sdist",
        "sdist_build",
        "focused",
    }
)
_ARCHIVE_FIELDS = frozenset({"name", "size", "sha256", "inventory_sha256", "installed"})
_INSTALLED_FIELDS = frozenset(
    {
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
)
_FOCUSED_FIELDS = frozenset(
    {"source_commit", "platform", "selected", "selected_nodes", "passed", "failed", "skipped"}
)
_SDIST_BUILD_FIELDS = frozenset(
    {
        "schema_version",
        "source_commit",
        "source_tree",
        "binding_sha256",
        "sdist_name",
        "sdist_size",
        "sdist_sha256",
        "wheel_name",
        "wheel_size",
        "wheel_sha256",
        "python_version",
        "uv_version",
        "uv_sha256",
        "backend",
        "backend_version",
        "static_requirements",
        "dynamic_requirement_expressions",
        "dynamic_requirements",
        "build_packages",
    }
)


@dataclass(frozen=True, slots=True)
class ReceiptVerification:
    """Sanitized summary after all required platform rows match their bindings."""

    run_id: str
    source_commit: str
    source_tree: str
    artifact_id: str
    artifact_digest: str
    lock_sha256: str
    platforms: tuple[str, str, str]

    def to_dict(self) -> dict[str, object]:
        """Return stable, path-free summary data for the qualification CLI."""
        return asdict(self)


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("Receipt JSON contains a duplicate JSON object key.")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"Receipt JSON contains a non-standard constant: {value}.")


def _read_receipt(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        _fail("Receipt files must be regular, non-symlink JSON files.")
    try:
        before = path.stat()
        if before.st_size <= 0 or before.st_size > _MAX_RECEIPT_BYTES:
            _fail("Qualification receipt file size limit exceeded.")
        with path.open("rb") as stream:
            payload = stream.read(_MAX_RECEIPT_BYTES + 1)
        after = path.stat()
    except OSError as error:
        raise ValueError("Could not read a qualification receipt.") from error
    if len(payload) > _MAX_RECEIPT_BYTES:
        _fail("Qualification receipt file size limit exceeded.")
    if len(payload) != before.st_size or after.st_size != before.st_size:
        _fail("Qualification receipt changed while being read.")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError(
            "Qualification receipt JSON is malformed or exceeds parser limits."
        ) from error
    if not isinstance(value, dict):
        _fail("Qualification receipt must be a JSON object.")
    return value


def _check_fields(value: object, expected: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"{label} receipt fields are invalid.")
    return value


def _check_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256 digest.")
    return value


def _check_positive_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _DECIMAL_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical positive decimal ID.")
    return value


def _expected_lock_sha256() -> str:
    lockfile = Path(__file__).resolve().parents[2] / "uv.lock"
    if lockfile.is_symlink() or not lockfile.is_file():
        _fail("The checked-out uv.lock must be a regular file.")
    try:
        before = lockfile.stat()
        if before.st_size <= 0 or before.st_size > _MAX_LOCK_BYTES:
            _fail("The checked-out uv.lock size limit is exceeded.")
        digest = hashlib.sha256()
        size = 0
        with lockfile.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                size += len(chunk)
                if size > _MAX_LOCK_BYTES:
                    _fail("The checked-out uv.lock size limit is exceeded.")
                digest.update(chunk)
        after = lockfile.stat()
    except OSError as error:
        raise ValueError("Could not read the checked-out uv.lock.") from error
    if size != before.st_size or after.st_size != before.st_size:
        _fail("The checked-out uv.lock changed while being hashed.")
    return digest.hexdigest()


def _expected_static_build_requirements() -> tuple[str, ...]:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproject.is_symlink() or not pyproject.is_file():
        _fail("The checked-out pyproject.toml must be a regular file.")
    try:
        before = pyproject.stat()
        if before.st_size <= 0 or before.st_size > _MAX_SOURCE_METADATA_BYTES:
            _fail("The checked-out pyproject.toml size limit is exceeded.")
        with pyproject.open("rb") as stream:
            payload = stream.read(_MAX_SOURCE_METADATA_BYTES + 1)
        after = pyproject.stat()
    except OSError as error:
        raise ValueError("Could not read the checked-out pyproject.toml.") from error
    if (
        len(payload) != before.st_size
        or len(payload) > _MAX_SOURCE_METADATA_BYTES
        or after.st_size != before.st_size
    ):
        _fail("The checked-out pyproject.toml changed while being read.")
    try:
        document = tomllib.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("The checked-out pyproject.toml is invalid.") from error
    build_system = document.get("build-system")
    requirements = build_system.get("requires") if isinstance(build_system, dict) else None
    if (
        not isinstance(requirements, list)
        or not requirements
        or len(requirements) > _MAX_BUILD_REQUIREMENTS
        or any(
            not isinstance(requirement, str)
            or not requirement.strip()
            or len(requirement) > _MAX_BUILD_REQUIREMENT_LENGTH
            for requirement in requirements
        )
    ):
        _fail("The checked-out PEP 518 requirements have an invalid shape.")
    return tuple(requirements)


def _read_receipt_directory(receipt_dir: Path, expected_count: int) -> list[dict[str, Any]]:
    if receipt_dir.is_symlink() or not receipt_dir.is_dir():
        _fail("Receipt directory must be a regular, non-symlink directory.")
    try:
        entries: list[Path] = []
        for path in receipt_dir.iterdir():
            if path.suffix != ".json" or path.is_symlink() or not path.is_file():
                _fail("Receipt directory must contain only regular JSON files.")
            entries.append(path)
            if len(entries) > expected_count:
                _fail("Receipt directory contains unexpected entries.")
    except OSError as error:
        raise ValueError("Could not enumerate qualification receipt directory.") from error
    entries.sort(key=lambda item: item.name)
    if len(entries) != expected_count:
        _fail(f"Receipt directory must contain exactly {expected_count} platform receipt files.")
    names = [path.name for path in entries]
    if len(set(names)) != len(names):
        _fail("Receipt filenames must be unique.")
    return [_read_receipt(path) for path in entries]


def _normalize_architecture(value: object, label: str) -> str:
    if not isinstance(value, str):
        _fail(f"{label} architecture is invalid.")
    normalized = value.lower()
    aliases = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(f"{label} architecture is unsupported.") from error


def _validate_installed(
    value: object,
    *,
    kind: str,
    platform: str,
    architecture: str,
    binding: BundleBinding,
) -> tuple[str, tuple[tuple[str, str], ...], str, str]:
    installed = _check_fields(value, _INSTALLED_FIELDS, f"{kind} installed")
    expected_os = {"linux": "linux", "macos": "darwin", "windows": "windows"}[platform]
    if installed["kind"] != kind or installed["operating_system"] != expected_os:
        _fail(f"{kind} install receipt does not match its platform row.")
    if _normalize_architecture(installed["architecture"], kind) != architecture:
        _fail(f"{kind} install architecture does not match its platform row.")
    if (
        not isinstance(installed["python_version"], str)
        or _PYTHON_VERSION.fullmatch(installed["python_version"]) is None
    ):
        _fail(f"{kind} install receipt does not use Python 3.12.")
    if installed["version"] != binding.version:
        _fail(f"{kind} installed project version does not match the bundle binding.")
    if installed["location_class"] != "isolated-venv-site-packages":
        _fail(f"{kind} install receipt is not from an isolated environment.")
    _check_digest(installed["record_sha256"], f"{kind} RECORD digest")
    _check_digest(installed["resource_sha256"], f"{kind} resource digest")
    dependency_sha256 = _check_digest(installed["dependency_sha256"], f"{kind} dependency digest")
    generator = _check_fields(
        installed["build_generator"], frozenset({"name", "version"}), f"{kind} build generator"
    )
    if (
        generator["name"] != "setuptools"
        or not isinstance(generator["version"], str)
        or _GENERATOR_VERSION.fullmatch(generator["version"]) is None
    ):
        _fail(f"{kind} build generator record is invalid.")
    raw_dependencies = installed["dependencies"]
    if not isinstance(raw_dependencies, list) or len(raw_dependencies) > _MAX_DEPENDENCIES:
        _fail(f"{kind} dependency records are invalid or exceed the count limit.")
    dependencies: list[tuple[str, str]] = []
    for item in raw_dependencies:
        dependency = _check_fields(item, frozenset({"name", "version"}), f"{kind} dependency")
        name, version = dependency["name"], dependency["version"]
        if (
            not isinstance(name, str)
            or len(name) > 200
            or _DEPENDENCY_NAME.fullmatch(name) is None
            or not isinstance(version, str)
            or _DEPENDENCY_VERSION.fullmatch(version) is None
        ):
            _fail(f"{kind} dependency record is invalid.")
        dependencies.append((name, version))
    canonical_dependencies = tuple(dependencies)
    if tuple(sorted(canonical_dependencies)) != canonical_dependencies or len(
        {name for name, _version in canonical_dependencies}
    ) != len(canonical_dependencies):
        _fail(f"{kind} dependencies are not in canonical order or contain duplicates.")
    actual_dependency_sha256 = hashlib.sha256(
        json.dumps(canonical_dependencies, separators=(",", ":")).encode()
    ).hexdigest()
    if actual_dependency_sha256 != dependency_sha256:
        _fail(f"{kind} dependency records do not match their digest.")
    tck_outcomes = installed["tck_outcomes"]
    if not isinstance(tck_outcomes, list) or tck_outcomes != ["PASS", "PASS", "PASS"]:
        _fail(f"{kind} installed TCK receipt is incomplete or failed.")
    return (
        dependency_sha256,
        canonical_dependencies,
        generator["version"],
        installed["python_version"],
    )


def _validate_archive(
    value: object,
    *,
    kind: str,
    platform: str,
    architecture: str,
    binding: BundleBinding,
) -> tuple[str, tuple[tuple[str, str], ...], str, str]:
    archive = _check_fields(value, _ARCHIVE_FIELDS, f"{kind} archive")
    expected = {
        "wheel": (binding.wheel_name, binding.wheel_size, binding.wheel_sha256),
        "sdist": (binding.sdist_name, binding.sdist_size, binding.sdist_sha256),
    }[kind]
    inventory_digest = {
        "wheel": binding.wheel_inventory_sha256,
        "sdist": binding.sdist_inventory_sha256,
    }[kind]
    if (
        archive["name"] != expected[0]
        or type(archive["size"]) is not int
        or archive["size"] != expected[1]
        or archive["sha256"] != expected[2]
        or archive["inventory_sha256"] != inventory_digest
    ):
        _fail(f"{kind} receipt does not match independent binding.")
    return _validate_installed(
        archive["installed"],
        kind=kind,
        platform=platform,
        architecture=architecture,
        binding=binding,
    )


def _validate_focused(value: object, platform: str, source_commit: str) -> None:
    focused = _check_fields(value, _FOCUSED_FIELDS, "focused test")
    nodes = focused_nodes(platform)  # type: ignore[arg-type]
    expected_count = len(nodes)
    if (
        focused["source_commit"] != source_commit
        or focused["platform"] != platform
        or type(focused["selected"]) is not int
        or focused["selected"] != expected_count
        or focused["selected_nodes"] != list(nodes)
        or type(focused["passed"]) is not int
        or focused["passed"] != expected_count
        or type(focused["failed"]) is not int
        or focused["failed"] != 0
        or type(focused["skipped"]) is not int
        or focused["skipped"] != 0
    ):
        _fail("Focused test receipt is incomplete or failed.")


def _validate_build_package_manifest(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or len(value) > _MAX_DEPENDENCIES:
        _fail("sdist build package manifest is invalid or exceeds its count limit.")
    packages: list[tuple[str, str]] = []
    for item in value:
        package = _check_fields(item, frozenset({"name", "version"}), "sdist build package")
        name, version = package["name"], package["version"]
        if (
            not isinstance(name, str)
            or len(name) > 200
            or _DEPENDENCY_NAME.fullmatch(name) is None
            or canonicalize_name(name) != name
            or not isinstance(version, str)
            or _DEPENDENCY_VERSION.fullmatch(version) is None
        ):
            _fail("sdist build package manifest contains invalid values.")
        try:
            Version(version)
        except Exception as error:
            raise ValueError("sdist build package manifest contains an invalid version.") from error
        packages.append((name, version))
    canonical = tuple(packages)
    if tuple(sorted(canonical)) != canonical or len({name for name, _ in canonical}) != len(
        canonical
    ):
        _fail("sdist build package manifest is not canonical (sorted and unique).")
    return canonical


def _validate_sdist_build(
    value: object,
    *,
    binding: BundleBinding,
    expected_commit: str,
    expected_tree: str,
    platform: str,
    architecture: str,
    uv_version: str,
    uv_sha256: str,
    installed_python: str,
    expected_static_requirements: tuple[str, ...],
) -> str:
    """Validate sanitized build provenance for the temporary sdist-derived wheel."""
    build = _check_fields(value, _SDIST_BUILD_FIELDS, "sdist build")
    binding_sha256 = hashlib.sha256(binding.to_json().encode("utf-8")).hexdigest()
    if (
        type(build["schema_version"]) is not int
        or build["schema_version"] != 1
        or build["source_commit"] != expected_commit
        or build["source_tree"] != expected_tree
        or build["binding_sha256"] != binding_sha256
        or build["sdist_name"] != binding.sdist_name
        or type(build["sdist_size"]) is not int
        or build["sdist_size"] != binding.sdist_size
        or build["sdist_sha256"] != binding.sdist_sha256
    ):
        _fail("sdist build receipt does not match the bound source and bundle.")
    if (
        build["wheel_name"] != binding.wheel_name
        or type(build["wheel_size"]) is not int
        or build["wheel_size"] <= 0
        or build["wheel_size"] > _MAX_BUILD_WHEEL_BYTES
    ):
        _fail("sdist build temporary wheel identity or size is invalid.")
    _check_digest(build["wheel_sha256"], "sdist build temporary wheel digest")

    python_version = build["python_version"]
    if (
        not isinstance(python_version, str)
        or _PYTHON_VERSION.fullmatch(python_version) is None
        or python_version != installed_python
    ):
        _fail("sdist build Python version does not match its isolated install receipt.")
    if build["uv_version"] != uv_version or build["uv_sha256"] != uv_sha256:
        _fail("sdist build receipt does not match its platform uv binding.")
    if build["backend"] != "setuptools.build_meta":
        _fail("sdist build backend is unsupported.")
    backend_version = build["backend_version"]
    if (
        not isinstance(backend_version, str)
        or _GENERATOR_VERSION.fullmatch(backend_version) is None
    ):
        _fail("sdist build backend version is invalid.")
    try:
        Version(backend_version)
    except Exception as error:
        raise ValueError("sdist build backend version is invalid.") from error

    package_pairs = _validate_build_package_manifest(build["build_packages"])
    package_versions = dict(package_pairs)
    if package_versions.get("setuptools") != backend_version:
        _fail("sdist build backend version does not match its package manifest.")

    static_requirements = build["static_requirements"]
    if (
        not isinstance(static_requirements, list)
        or not static_requirements
        or len(static_requirements) > _MAX_BUILD_REQUIREMENTS
        or any(
            not isinstance(requirement, str)
            or not requirement.strip()
            or len(requirement) > _MAX_BUILD_REQUIREMENT_LENGTH
            or any(ord(character) < 32 for character in requirement)
            for requirement in static_requirements
        )
        or len(set(static_requirements)) != len(static_requirements)
    ):
        _fail("sdist static build requirements are invalid or exceed their bounds.")
    if tuple(static_requirements) != expected_static_requirements:
        _fail("sdist static build requirements differ from checked-out source metadata.")
    environment = _marker_environment(platform, architecture, installed_python)
    unsupported_marker_values = {
        "dependency_groups",
        "extra",
        "extras",
        "platform_release",
        "platform_version",
    }
    for raw_requirement in static_requirements:
        try:
            requirement = Requirement(raw_requirement)
        except (TypeError, ValueError) as error:
            raise ValueError("sdist static build requirement is invalid.") from error
        if requirement.url:
            _fail("sdist static build requirements cannot contain direct URLs.")
        if requirement.extras:
            _fail("sdist static build requirement extras are not permitted.")
        marker_expression = raw_requirement.partition(";")[2]
        marker_names = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", marker_expression))
        if marker_names & unsupported_marker_values:
            _fail("sdist static build requirement uses an unbound platform marker.")
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        installed_version = package_versions.get(canonicalize_name(requirement.name))
        if installed_version is None or (
            requirement.specifier and Version(installed_version) not in requirement.specifier
        ):
            _fail("sdist static build requirements are not satisfied by the package manifest.")

    dynamic_expressions = build["dynamic_requirement_expressions"]
    if (
        not isinstance(dynamic_expressions, list)
        or len(dynamic_expressions) > _MAX_BUILD_REQUIREMENTS
        or any(
            not isinstance(expression, str)
            or not expression.strip()
            or len(expression) > _MAX_BUILD_REQUIREMENT_LENGTH
            or any(ord(character) < 32 for character in expression)
            for expression in dynamic_expressions
        )
        or len(set(dynamic_expressions)) != len(dynamic_expressions)
    ):
        _fail("sdist dynamic build requirement expressions are invalid or exceed their bounds.")
    dynamic_requirements = build["dynamic_requirements"]
    if (
        not isinstance(dynamic_requirements, list)
        or len(dynamic_requirements) > _MAX_BUILD_REQUIREMENTS
    ):
        _fail("sdist dynamic build requirements are invalid or exceed their count limit.")
    dynamic_pairs: list[tuple[str, str]] = []
    for item in dynamic_requirements:
        package = _check_fields(item, frozenset({"name", "version"}), "sdist dynamic requirement")
        name, version = package["name"], package["version"]
        if (
            not isinstance(name, str)
            or _DEPENDENCY_NAME.fullmatch(name) is None
            or canonicalize_name(name) != name
            or not isinstance(version, str)
            or _DEPENDENCY_VERSION.fullmatch(version) is None
        ):
            _fail("sdist dynamic build requirement contains invalid values.")
        dynamic_pairs.append((name, version))
    canonical_dynamic = tuple(dynamic_pairs)
    if tuple(sorted(canonical_dynamic)) != canonical_dynamic or len(
        {name for name, _ in canonical_dynamic}
    ) != len(canonical_dynamic):
        _fail("sdist dynamic build requirements are not canonical (sorted and unique).")
    if canonical_dynamic and not dynamic_expressions:
        _fail("sdist dynamic build requirement expressions are missing.")
    verified_dynamic: set[tuple[str, str]] = set()
    for raw_requirement in dynamic_expressions:
        try:
            requirement = Requirement(raw_requirement)
        except (TypeError, ValueError) as error:
            raise ValueError("sdist dynamic build requirement expression is invalid.") from error
        if requirement.url:
            _fail("sdist dynamic build requirement expressions cannot contain direct URLs.")
        if requirement.extras:
            _fail("sdist dynamic build requirement expression extras are not permitted.")
        marker_expression = raw_requirement.partition(";")[2]
        marker_names = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", marker_expression))
        if marker_names & unsupported_marker_values:
            _fail("sdist dynamic build requirement uses an unbound platform marker.")
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        name = canonicalize_name(requirement.name)
        installed_version = package_versions.get(name)
        if installed_version is None or (
            requirement.specifier and Version(installed_version) not in requirement.specifier
        ):
            _fail("sdist dynamic build requirements are not satisfied by the package manifest.")
        verified_dynamic.add((name, installed_version))
    if tuple(sorted(verified_dynamic)) != canonical_dynamic:
        _fail(
            "sdist dynamic build requirements do not match the package manifest "
            "or declared expressions."
        )
    return backend_version


def verify_receipts(
    receipt_dir: Path,
    *,
    expected_commit: str,
    expected_tree: str,
    expected_binding: BundleBinding,
    artifact_id: str,
    artifact_digest: str,
    run_id: str,
    expected_platform_count: int = 3,
) -> ReceiptVerification:
    """Verify exactly three sanitized rows against the independent build handoff.

    The function verifies receipt claims and their cross-job bindings. It does not
    independently derive installed dependency membership from the lockfile; the
    workflow's `uv sync --locked` step supplies that execution evidence. It does
    bind every row to the exact checked-out lockfile and requires matching wheel
    and sdist dependency-set digests within each platform.
    """
    if expected_platform_count != len(_PLATFORMS):
        _fail("Exactly three qualification platforms are required.")
    if _SOURCE_ID.fullmatch(expected_commit) is None or _SOURCE_ID.fullmatch(expected_tree) is None:
        _fail("Expected source commit and tree must be lowercase full Git IDs.")
    if not isinstance(expected_binding, BundleBinding):
        _fail("Expected bundle binding must be a validated BundleBinding.")
    bundle_module._validate_binding(expected_binding)
    if (
        expected_binding.source_commit != expected_commit
        or expected_binding.source_tree != expected_tree
    ):
        _fail("Expected source identity does not match the independent bundle binding.")
    _check_positive_id(run_id, "Expected run ID")
    _check_positive_id(artifact_id, "Expected artifact ID")
    if not isinstance(artifact_digest, str) or _ARTIFACT_DIGEST.fullmatch(artifact_digest) is None:
        _fail("Expected artifact digest must be a lowercase 64-character SHA-256 value.")

    expected_lock = _expected_lock_sha256()
    expected_static_requirements = _expected_static_build_requirements()
    receipts = _read_receipt_directory(receipt_dir, expected_platform_count)
    observed: dict[tuple[str, str], dict[str, Any]] = {}
    for receipt in receipts:
        row = _check_fields(receipt, _RECEIPT_FIELDS, "platform")
        platform = row["os"]
        architecture = row["architecture"]
        if not isinstance(platform, str) or not isinstance(architecture, str):
            _fail("Platform receipt OS and architecture must be strings.")
        key = (platform, architecture)
        if key not in _PLATFORMS or key in observed:
            _fail("Receipts must contain exactly one receipt for each required platform.")
        if (
            row["run_id"] != run_id
            or row["source_sha"] != expected_commit
            or row["source_tree"] != expected_tree
            or row["artifact_id"] != artifact_id
            or row["artifact_digest"] != artifact_digest
        ):
            _fail("Platform receipt does not match the expected run, source, or artifact binding.")
        if row["lock_sha256"] != expected_lock:
            _fail("Platform receipt lock digest does not match the checked-out uv.lock.")

        uv = _check_fields(row["uv"], frozenset({"version", "sha256"}), "uv tool")
        if not isinstance(uv["version"], str) or _UV_VERSION.fullmatch(uv["version"]) is None:
            _fail("Platform receipt uv version is invalid.")
        _check_digest(uv["sha256"], "uv executable digest")

        (
            wheel_dependency_sha256,
            wheel_dependencies,
            _,
            _,
        ) = _validate_archive(
            row["wheel"],
            kind="wheel",
            platform=platform,
            architecture=architecture,
            binding=expected_binding,
        )
        (
            sdist_dependency_sha256,
            sdist_dependencies,
            sdist_generator_version,
            sdist_python_version,
        ) = _validate_archive(
            row["sdist"],
            kind="sdist",
            platform=platform,
            architecture=architecture,
            binding=expected_binding,
        )
        if (
            wheel_dependency_sha256 != sdist_dependency_sha256
            or wheel_dependencies != sdist_dependencies
        ):
            _fail("Installed dependency digest differs between wheel and sdist environments.")
        backend_version = _validate_sdist_build(
            row["sdist_build"],
            binding=expected_binding,
            expected_commit=expected_commit,
            expected_tree=expected_tree,
            platform=platform,
            architecture=architecture,
            uv_version=uv["version"],
            uv_sha256=uv["sha256"],
            installed_python=sdist_python_version,
            expected_static_requirements=expected_static_requirements,
        )
        if sdist_generator_version != backend_version:
            _fail("sdist install generator differs from observed build backend version.")
        _validate_focused(row["focused"], platform, expected_commit)
        observed[key] = row

    if set(observed) != set(_PLATFORMS):
        _fail("Receipts must contain exactly one receipt for each required platform.")
    lock_digests = {row["lock_sha256"] for row in observed.values()}
    if len(lock_digests) != 1:
        _fail("Lock digest differs between platform receipts.")
    uv_versions = {row["uv"]["version"] for row in observed.values()}
    if len(uv_versions) != 1:
        _fail("uv version differs between platform receipts.")

    platforms = tuple(f"{platform}/{architecture}" for platform, architecture in _PLATFORMS)
    return ReceiptVerification(
        run_id=run_id,
        source_commit=expected_commit,
        source_tree=expected_tree,
        artifact_id=artifact_id,
        artifact_digest=artifact_digest,
        lock_sha256=expected_lock,
        platforms=platforms,  # type: ignore[arg-type]
    )
