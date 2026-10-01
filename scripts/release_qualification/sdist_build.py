"""Build a temporary wheel from an authenticated source archive without isolation."""

from __future__ import annotations

import hashlib
import json
import os
import platform as host_platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import tomllib
import zipfile
from dataclasses import asdict, dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import NoReturn, cast

from packaging.markers import UndefinedEnvironmentName, default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification.build_environment import (
    BuildEnvironmentDescriptor,
    load_build_environment_descriptor,
)
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.installed import _authenticated_archive, _verify_source

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PYTHON_VERSION = re.compile(r"3\.12\.[0-9]+(?:[A-Za-z0-9.+-]*)?\Z")
_MAX_CAPTURE_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 512 * 1024 * 1024
_MAX_BUILD_REQUIREMENT_LENGTH = 2048
_MAX_BUILD_LOCK_BYTES = 32 * 1024 * 1024
_MAX_PROVISIONING_RECIPE_BYTES = 1024 * 1024
_COMMAND_TIMEOUT_SECONDS = 15 * 60
_TERMINATE_SECONDS = 3.0
_PROCESS_GROUP_POLL_SECONDS = process_module.PROCESS_GROUP_POLL_SECONDS
_BACKEND = "setuptools.build_meta"
_BACKEND_QUERY = f"""import contextlib, io, json, setuptools, setuptools.build_meta
class _BoundedTextBuffer(io.StringIO):
    def __init__(self):
        super().__init__()
        self._written = 0
    def write(self, value):
        size = len(value.encode('utf-8'))
        if self._written + size > {_MAX_CAPTURE_BYTES}:
            raise RuntimeError('PEP 517 backend output exceeded its limit')
        self._written += size
        return super().write(value)
with contextlib.redirect_stdout(_BoundedTextBuffer()):
    requirements = setuptools.build_meta.get_requires_for_build_wheel({{}})
print(json.dumps({{"backend": "setuptools.build_meta", "version": setuptools.__version__,
                  "requirements": requirements}}, separators=(",", ":")))
"""


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


@dataclass(frozen=True, slots=True)
class BuildRequirementRecord:
    """One exact PEP 518/517 expression and its observed locked satisfier."""

    expression: str
    marker_applicable: bool
    satisfier: tuple[str, str] | None

    def __post_init__(self) -> None:
        if type(self.marker_applicable) is not bool:
            _fail("Build requirement marker applicability must be a boolean.")
        requirement = _parse_requirement(self.expression, "build requirement record")
        if self.satisfier is None:
            if self.marker_applicable:
                _fail("An applicable build requirement needs an exact observed satisfier.")
            if requirement.marker is None:
                _fail("A markerless build requirement cannot be inapplicable.")
            return
        if not self.marker_applicable:
            _fail("An inapplicable build requirement cannot have a satisfier.")
        if not isinstance(self.satisfier, tuple) or len(self.satisfier) != 2:
            _fail("Build requirement satisfier must be an exact name/version pair.")
        name, version = self.satisfier
        if (
            not isinstance(name, str)
            or not isinstance(version, str)
            or canonicalize_name(name) != name
            or canonicalize_name(requirement.name) != name
        ):
            _fail("Build requirement satisfier name does not match its expression.")
        try:
            parsed_version = Version(version)
        except Exception as error:
            raise ValueError("Build requirement satisfier version is invalid.") from error
        if requirement.specifier and parsed_version not in requirement.specifier:
            _fail("Build requirement satisfier version does not satisfy its expression.")

    def to_dict(self) -> dict[str, object]:
        """Return the exact receipt record without exposing local paths."""
        satisfier: dict[str, str] | None = None
        if self.satisfier is not None:
            satisfier = {"name": self.satisfier[0], "version": self.satisfier[1]}
        return {
            "expression": self.expression,
            "marker_applicable": self.marker_applicable,
            "satisfier": satisfier,
        }

    def validate(
        self,
        installed: dict[str, str],
        *,
        target_os: str,
        target_architecture: str,
        python_implementation: str,
        python_version: str,
    ) -> None:
        """Recompute marker and exact satisfier claims for one admitted context."""
        applicable, satisfier = _requirement_observation(
            self.expression,
            installed,
            label="build requirement",
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
        )
        if self.marker_applicable is not applicable:
            _fail("Build requirement record marker applicability is forged.")
        if self.satisfier != satisfier:
            _fail("Build requirement record satisfier is forged or incompatible.")


@dataclass(frozen=True, slots=True)
class SdistBuildReceipt:
    """Path-free provenance for a temporary wheel built from one bound sdist."""

    schema_version: int
    source_commit: str
    source_tree: str
    binding_sha256: str
    sdist_name: str
    sdist_size: int
    sdist_sha256: str
    wheel_name: str
    wheel_size: int
    wheel_sha256: str
    build_lock_sha256: str
    environment_descriptor_sha256: str
    provisioning_recipe_sha256: str
    provisioning_evidence_sha256: str
    target_os: str
    target_architecture: str
    python_implementation: str
    python_version: str
    python_executable_sha256: str
    uv_version: str
    uv_sha256: str
    backend: str
    backend_version: str
    static_requirement_records: tuple[BuildRequirementRecord, ...]
    dynamic_requirement_records: tuple[BuildRequirementRecord, ...]
    provisioned_packages: tuple[tuple[str, str], ...]
    before_hooks_packages: tuple[tuple[str, str], ...]
    after_hooks_packages: tuple[tuple[str, str], ...]
    after_build_packages: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        """Return stable JSON data without local paths or raw command output."""
        value = asdict(self)
        value["static_requirement_records"] = [
            record.to_dict() for record in self.static_requirement_records
        ]
        value["dynamic_requirement_records"] = [
            record.to_dict() for record in self.dynamic_requirement_records
        ]
        for field in (
            "provisioned_packages",
            "before_hooks_packages",
            "after_hooks_packages",
            "after_build_packages",
        ):
            packages = cast(tuple[tuple[str, str], ...], getattr(self, field))
            value[field] = [{"name": name, "version": version} for name, version in packages]
        return value

    def to_json(self) -> str:
        """Serialize compact canonical receipt JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class _WheelArtifact:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _CommandResult:
    returncode: int
    stdout: bytes


def _parse_build_system(pyproject: bytes) -> tuple[str, tuple[str, ...]]:
    if not pyproject or len(pyproject) > 1024 * 1024:
        _fail("Authenticated sdist pyproject metadata is missing or too large.")
    try:
        document = tomllib.loads(pyproject.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("Authenticated sdist pyproject metadata is invalid.") from error
    build_system = document.get("build-system")
    if not isinstance(build_system, dict):
        _fail("Authenticated sdist must declare a PEP 518 build-system.")
    backend = build_system.get("build-backend")
    requirements = build_system.get("requires")
    backend_path = build_system.get("backend-path", [])
    if backend != _BACKEND or backend_path not in ([], None):
        _fail("Authenticated sdist declares an unsupported build backend.")
    if (
        not isinstance(requirements, list)
        or not requirements
        or any(not isinstance(item, str) or not item.strip() for item in requirements)
    ):
        _fail("Authenticated sdist has invalid static build requirements.")
    normalized = tuple(requirements)
    if len(set(normalized)) != len(normalized):
        _fail("Authenticated sdist contains duplicate static build requirements.")
    for raw in normalized:
        requirement = _parse_requirement(raw, "static build requirement")
        if requirement.url:
            _fail("Direct URL build requirements are not permitted.")
    return _BACKEND, normalized


def _marker_environment(
    platform: str,
    architecture: str,
    python_version: str,
    python_implementation: str = "CPython",
) -> dict[str, str]:
    """Build the same bounded PEP 508 marker environment for helper and verifier."""
    if _PYTHON_VERSION.fullmatch(python_version) is None:
        _fail("Build marker Python version is invalid.")
    if python_implementation != "CPython":
        _fail("Build marker Python implementation is unsupported.")
    try:
        machine = {
            ("linux", "x64"): "x86_64",
            ("macos", "arm64"): "arm64",
            ("windows", "x64"): "AMD64",
        }[(platform, architecture)]
        system = {"linux": "Linux", "macos": "Darwin", "windows": "Windows"}[platform]
        sys_platform = {"linux": "linux", "macos": "darwin", "windows": "win32"}[platform]
    except KeyError as error:
        raise ValueError("Build marker platform or architecture is unsupported.") from error
    environment = cast(dict[str, str], default_environment())
    environment.update(
        {
            "implementation_name": python_implementation.casefold(),
            "implementation_version": python_version,
            "os_name": "nt" if platform == "windows" else "posix",
            "platform_machine": machine,
            "platform_python_implementation": python_implementation,
            "platform_system": system,
            "python_full_version": python_version,
            "python_version": ".".join(python_version.split(".")[:2]),
            "sys_platform": sys_platform,
        }
    )
    return environment


def _native_marker_target() -> tuple[str, str]:
    """Return the target represented by this native build worker."""
    target_platform = {
        "darwin": "macos",
        "linux": "linux",
        "win32": "windows",
    }.get(sys.platform)
    target_architecture = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "x64",
        "AMD64": "x64",
    }.get(host_platform.machine())
    if target_platform is None or target_architecture is None:
        _fail("Native build worker platform or architecture is unsupported.")
    if (target_platform, target_architecture) not in {
        ("linux", "x64"),
        ("macos", "arm64"),
        ("windows", "x64"),
    }:
        _fail("Native build worker platform or architecture is unsupported.")
    return target_platform, target_architecture


def _reject_unbound_marker(raw: str) -> None:
    marker_expression = raw.partition(";")[2]
    without_literals = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "", marker_expression)
    marker_names = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", without_literals))
    marker_names -= {"and", "or", "not", "in"}
    if marker_names & {
        "dependency_groups",
        "extra",
        "extras",
        "platform_release",
        "platform_version",
    }:
        _fail("Authenticated sdist requirement uses an unbound platform marker.")
    if marker_names - set(default_environment()):
        _fail("Authenticated sdist requirement uses an unknown platform marker.")


def _parse_requirement(raw: str, label: str) -> Requirement:
    if (
        not isinstance(raw, str)
        or not raw.strip()
        or len(raw) > _MAX_BUILD_REQUIREMENT_LENGTH
        or any(ord(character) < 32 for character in raw)
    ):
        _fail(f"Authenticated sdist has an invalid or unbounded {label}.")
    try:
        requirement = Requirement(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Authenticated sdist has an invalid {label}.") from error
    if requirement.url:
        _fail(f"Authenticated sdist has an unverifiable URL {label}.")
    if requirement.extras:
        _fail(f"Authenticated sdist {label} extras are not permitted.")
    _reject_unbound_marker(raw)
    return requirement


def _requirement_observation(
    raw: str,
    installed: dict[str, str],
    *,
    label: str,
    target_os: str,
    target_architecture: str,
    python_implementation: str,
    python_version: str,
) -> tuple[bool, tuple[str, str] | None]:
    requirement = _parse_requirement(raw, label)
    environment = _marker_environment(
        target_os, target_architecture, python_version, python_implementation
    )
    applicable = True
    if requirement.marker is not None:
        try:
            applicable = requirement.marker.evaluate(environment)
        except (UndefinedEnvironmentName, KeyError, ValueError) as error:
            raise ValueError(
                "Build requirement uses an unknown or unbound marker context."
            ) from error
    if not applicable:
        return False, None
    name = canonicalize_name(requirement.name)
    version = installed.get(name)
    if version is None:
        _fail(f"An applicable {label} is not satisfied by the observed build environment.")
    try:
        parsed_version = Version(version)
    except Exception as error:
        raise ValueError("Observed build package has an invalid version.") from error
    if requirement.specifier and parsed_version not in requirement.specifier:
        _fail(f"An applicable {label} is not satisfied by the observed build environment.")
    return True, (name, version)


def _build_requirement_records(
    requirements: tuple[str, ...],
    installed: dict[str, str],
    *,
    label: str,
    target_os: str,
    target_architecture: str,
    python_implementation: str,
    python_version: str,
) -> tuple[BuildRequirementRecord, ...]:
    if (
        len(requirements) > 256
        or any(not isinstance(item, str) for item in requirements)
        or len(set(requirements)) != len(requirements)
    ):
        _fail(f"PEP 517 backend returned invalid {label}s.")
    records: list[BuildRequirementRecord] = []
    for raw in requirements:
        applicable, satisfier = _requirement_observation(
            raw,
            installed,
            label=label,
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
        )
        record = BuildRequirementRecord(raw, applicable, satisfier)
        record.validate(
            installed,
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
        )
        records.append(record)
    return tuple(records)


def _verify_generated_wheel(
    path: Path, expected_name: str, expected_distribution: str, expected_version: str
) -> _WheelArtifact:
    if path.is_symlink() or not path.is_file() or path.name != expected_name:
        _fail("Generated wheel filename or file type does not match the bound release package.")
    size, digest = bundle_module._archive_sha256(path)
    members, contents = bundle_module._read_wheel(path)
    metadata_members = [name for name in members if name.endswith(".dist-info/METADATA")]
    wheel_members = [name for name in members if name.endswith(".dist-info/WHEEL")]
    if len(metadata_members) != 1 or len(wheel_members) != 1:
        _fail("Generated wheel does not contain one unambiguous distribution identity.")
    try:
        metadata = BytesParser().parsebytes(contents[metadata_members[0]], headersonly=True)
        name = canonicalize_name(metadata.get("Name", ""))
        version = metadata.get("Version", "")
        with zipfile.ZipFile(path) as archive:
            wheel_bytes = archive.read(wheel_members[0])
        if len(wheel_bytes) > 1024 * 1024:
            _fail("Generated wheel metadata exceeds its size limit.")
        wheel_text = wheel_bytes.decode("utf-8")
    except (KeyError, OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile) as error:
        raise ValueError("Generated wheel metadata is malformed.") from error
    if name != canonicalize_name(expected_distribution) or version != expected_version:
        _fail("Generated wheel distribution identity does not match the bound package version.")
    wheel_lines = {line.strip() for line in wheel_text.splitlines() if line.strip()}
    if "Root-Is-Purelib: true" not in wheel_lines or "Tag: py3-none-any" not in wheel_lines:
        _fail("Generated wheel has an unsupported or unexpected platform shape.")
    return _WheelArtifact(path.name, size, digest)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ValueError("Could not verify qualification input bytes.") from error
    return digest.hexdigest()


def _sha256_regular_file(path: Path, label: str, maximum_bytes: int) -> str:
    if path.is_symlink() or not path.is_file():
        _fail(f"{label} must be a regular, non-symlink file.")
    try:
        before = path.stat()
        if before.st_size <= 0 or before.st_size > maximum_bytes:
            _fail(f"{label} exceeds its size limit.")
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                size += len(chunk)
                if size > maximum_bytes:
                    _fail(f"{label} exceeds its size limit.")
                digest.update(chunk)
        after = path.stat()
    except OSError as error:
        raise ValueError(f"Could not hash {label}.") from error
    if (
        path.is_symlink()
        or not path.is_file()
        or size != before.st_size
        or after.st_size != before.st_size
        or after.st_ino != before.st_ino
        or after.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} changed while being hashed.")
    return digest.hexdigest()


def _locked_build_identity(source_root: Path) -> tuple[str, str]:
    project_dir = source_root / "release-qualification-build"
    if project_dir.is_symlink() or not project_dir.is_dir():
        _fail("Checked-out dedicated build project must be a regular directory.")
    try:
        resolved_project = project_dir.resolve(strict=True)
        resolved_project.relative_to(source_root)
    except (OSError, ValueError) as error:
        raise ValueError(
            "Dedicated build project must remain beneath the checked-out source."
        ) from error
    lock = resolved_project / "uv.lock"
    recipe = resolved_project / "provisioning-recipe.json"
    for path in (lock, recipe):
        try:
            path.resolve(strict=True).relative_to(source_root)
        except (OSError, ValueError) as error:
            raise ValueError(
                "Dedicated build inputs must remain beneath the checked-out source."
            ) from error
    return (
        _sha256_regular_file(lock, "Dedicated build lock", _MAX_BUILD_LOCK_BYTES),
        _sha256_regular_file(recipe, "Provisioning recipe", _MAX_PROVISIONING_RECIPE_BYTES),
    )


def _verify_descriptor_binding(
    descriptor: BuildEnvironmentDescriptor, binding: BundleBinding
) -> str:
    binding_sha256 = hashlib.sha256(binding.to_json().encode("utf-8")).hexdigest()
    if (
        descriptor.source_commit != binding.source_commit
        or descriptor.source_tree != binding.source_tree
        or descriptor.binding_sha256 != binding_sha256
    ):
        _fail("Build-environment descriptor source or bundle binding does not match the artifact.")
    if (
        descriptor.sdist_name != binding.sdist_name
        or descriptor.sdist_size != binding.sdist_size
        or descriptor.sdist_sha256 != binding.sdist_sha256
    ):
        _fail("Build-environment descriptor sdist identity does not match the artifact.")
    return binding_sha256


def _run_bounded(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = _COMMAND_TIMEOUT_SECONDS,
    capture: bool = False,
) -> _CommandResult:
    if not command or timeout <= 0:
        _fail("Qualification command parameters are invalid.")
    if os.name == "nt":
        _fail("Windows build-process containment is not qualified for this helper.")
    try:
        owned = process_module.start_process(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            windows=False,
        )
    except OSError as error:
        raise ValueError("Could not start a bounded qualification command.") from error
    process = owned.process
    output = bytearray()
    overflow = threading.Event()
    reader: threading.Thread | None = None
    if capture:
        assert process.stdout is not None

        def drain() -> None:
            assert process.stdout is not None
            while chunk := process.stdout.read(8192):
                if len(output) + len(chunk) > _MAX_CAPTURE_BYTES:
                    overflow.set()
                elif not overflow.is_set():
                    output.extend(chunk)

        reader = threading.Thread(target=drain, name="sdist-build-output", daemon=True)
        reader.start()

    try:
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                owned.terminate(grace_seconds=_TERMINATE_SECONDS)
                process.wait(timeout=_TERMINATE_SECONDS)
                _fail("A qualification command exceeded its timeout.")
            try:
                returncode = process.wait(timeout=min(remaining, _PROCESS_GROUP_POLL_SECONDS))
                break
            except subprocess.TimeoutExpired:
                if overflow.is_set():
                    owned.terminate(grace_seconds=_TERMINATE_SECONDS)
                    returncode = process.wait(timeout=_TERMINATE_SECONDS)
                    break
        # A successful direct child can leave background descendants holding
        # files or captured pipes. Their existence invalidates a synchronous
        # result even if cleanup succeeds, so record it before terminating.
        group_had_descendants = owned.group_exists()
        owned.terminate(grace_seconds=_TERMINATE_SECONDS)
        if reader is not None:
            reader.join(timeout=1.0)
            if reader.is_alive():
                owned.terminate(grace_seconds=_TERMINATE_SECONDS)
                _fail("Qualification command output did not terminate cleanly.")
        if overflow.is_set():
            _fail("Qualification command output exceeded its capture limit.")
        if group_had_descendants:
            _fail("Qualification command left background descendants after direct-child exit.")
        return _CommandResult(returncode, bytes(output))
    finally:
        owned.terminate(grace_seconds=_TERMINATE_SECONDS)
        if process.poll() is None:
            process.wait(timeout=_TERMINATE_SECONDS)
        if process.stdout is not None:
            process.stdout.close()


def _checked_output(command: list[str], *, cwd: Path | None = None) -> bytes:
    result = _run_bounded(command, cwd=cwd, capture=True)
    if result.returncode != 0:
        _fail("A required qualification probe failed.")
    return result.stdout


def _read_package_manifest(uv: Path, python: Path) -> tuple[tuple[str, str], ...]:
    payload = _checked_output([str(uv), "pip", "list", "--format", "json", "--python", str(python)])
    try:
        values = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Isolated build package manifest is malformed.") from error
    if not isinstance(values, list) or len(values) > 4096:
        _fail("Isolated build package manifest has an invalid shape.")
    packages: dict[str, str] = {}
    for row in values:
        if not isinstance(row, dict) or set(row) != {"name", "version"}:
            _fail("Isolated build package manifest contains an invalid row.")
        raw_name, version = row["name"], row["version"]
        if not isinstance(raw_name, str) or not isinstance(version, str):
            _fail("Isolated build package manifest contains invalid values.")
        name = canonicalize_name(raw_name)
        if not name or name in packages:
            _fail("Isolated build package manifest contains duplicate package names.")
        try:
            Version(version)
        except Exception as error:
            raise ValueError(
                "Isolated build package manifest contains an invalid version."
            ) from error
        packages[name] = version
    return tuple(sorted(packages.items()))


def _read_uv_version(uv: Path) -> str:
    output = _checked_output([str(uv), "--version"]).decode("utf-8", errors="strict").strip()
    match = re.fullmatch(r"uv ([0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*)", output)
    if match is None:
        _fail("uv version output has an unsupported shape.")
    return match.group(1)


def _query_backend(build_python: Path, source_root: Path) -> tuple[str, str, tuple[str, ...]]:
    output = _checked_output([str(build_python), "-I", "-c", _BACKEND_QUERY], cwd=source_root)
    try:
        lines = [line for line in output.decode("utf-8").splitlines() if line.strip()]
        if not lines:
            _fail("PEP 517 backend hook returned no result.")
        value = json.loads(lines[-1])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("PEP 517 backend hook returned malformed output.") from error
    if not isinstance(value, dict) or set(value) != {"backend", "version", "requirements"}:
        _fail("PEP 517 backend hook returned an invalid result shape.")
    backend, version, requirements = value["backend"], value["version"], value["requirements"]
    if (
        backend != _BACKEND
        or not isinstance(version, str)
        or not isinstance(requirements, list)
        or len(requirements) > 256
        or any(not isinstance(item, str) for item in requirements)
    ):
        _fail("PEP 517 backend hook returned an unsupported result.")
    return backend, version, tuple(requirements)


def _python_identity(executable: Path) -> tuple[Path, str, str]:
    try:
        resolved = executable.resolve(strict=True)
    except OSError as error:
        raise ValueError("Could not resolve the selected Python interpreter.") from error
    if not executable.is_file() or not resolved.is_file():
        _fail("Selected Python interpreter must be an existing regular executable file.")
    probe = (
        "import json,platform,sys; print(json.dumps({"
        "'implementation':platform.python_implementation(),"
        "'version':'.'.join(map(str,sys.version_info[:3])),"
        "'prefix':sys.prefix,'base_prefix':sys.base_prefix},separators=(',',':')))"
    )
    try:
        value = json.loads(_checked_output([str(executable), "-I", "-c", probe]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Provisioned Python interpreter identity is malformed.") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"implementation", "version", "prefix", "base_prefix"}
        or not isinstance(value["implementation"], str)
        or not isinstance(value["version"], str)
        or not isinstance(value["prefix"], str)
        or not isinstance(value["base_prefix"], str)
        or value["implementation"] != "CPython"
        or not _PYTHON_VERSION.fullmatch(value["version"])
        or Path(value["prefix"]).resolve() == Path(value["base_prefix"]).resolve()
    ):
        _fail("Selected Python is not a supported interpreter in a provisioned environment.")
    return resolved, value["implementation"], value["version"]


def _require_new_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        _fail(f"{label} must be an existing regular directory.")
    resolved = path.resolve(strict=True)
    if any(resolved.iterdir()):
        _fail(f"{label} must be empty before qualification.")
    return resolved


def _safe_uv(uv_executable: Path, expected_sha256: str) -> tuple[Path, str]:
    if not _SHA256.fullmatch(expected_sha256):
        _fail("Expected uv executable SHA-256 must be a lowercase full digest.")
    try:
        resolved = uv_executable.resolve(strict=True)
    except OSError as error:
        raise ValueError("Could not resolve the selected uv executable.") from error
    if not resolved.is_file() or _sha256_file(resolved) != expected_sha256:
        _fail("Selected uv executable does not match its expected SHA-256.")
    return resolved, expected_sha256


def _extract_sdist(artifact: Path, destination: Path, binding: BundleBinding) -> Path:
    root_name = f"matryca_plumber-{binding.version}"
    members, _contents, _directories = bundle_module._read_sdist(artifact, root_name)
    try:
        with tarfile.open(artifact, "r:gz") as archive:
            archive.extractall(destination, filter="data")
    except (OSError, tarfile.TarError, ValueError) as error:
        raise ValueError(
            "Could not extract the authenticated source distribution safely."
        ) from error
    source_root = destination / root_name
    if source_root.is_symlink() or not source_root.is_dir():
        _fail("Authenticated source distribution root is missing after extraction.")
    pyproject = source_root / "pyproject.toml"
    if pyproject.is_symlink() or not pyproject.is_file():
        _fail("Authenticated source distribution has no regular pyproject.toml.")
    try:
        actual_members: set[str] = set()
        for item in source_root.rglob("*"):
            if item.is_symlink():
                _fail("Authenticated source distribution contains an extracted symlink.")
            if item.is_file():
                name = item.relative_to(source_root).as_posix()
                if name not in members:
                    _fail("Extracted source distribution contains an unbound file.")
                size, digest = bundle_module._archive_sha256(item)
                member = members[name]
                if size != member.size or digest != member.sha256:
                    _fail("Extracted source distribution bytes differ from authenticated members.")
                actual_members.add(name)
        if actual_members != set(members):
            _fail("Extracted source distribution is incomplete.")
    except OSError as error:
        raise ValueError("Could not verify extracted source distribution contents.") from error
    return source_root


def _copy_wheel(source: Path, output_dir: Path, expected_name: str) -> Path:
    target = output_dir / expected_name
    if target.exists() or target.is_symlink():
        _fail("Temporary wheel output already exists.")
    created = False
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with source.open("rb") as source_stream, os.fdopen(descriptor, "wb") as target_stream:
            shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)
            target_stream.flush()
            os.fsync(target_stream.fileno())
    except OSError as error:
        if created:
            target.unlink(missing_ok=True)
        raise ValueError("Could not preserve the generated temporary wheel.") from error
    return target


def prepare_sdist_build(
    artifact: Path,
    binding: BundleBinding,
    source_root: Path,
    python: Path,
    uv_executable: Path,
    uv_sha256: str,
    wheel_output_dir: Path,
    *,
    environment_descriptor: Path,
    expected_build_environment_sha256: str,
) -> SdistBuildReceipt:
    """Build one temporary wheel from an authenticated sdist in a provisioned environment.

    This consumer never creates or repairs an environment. It records an output
    wheel only after exact identity, requirement, and package-manifest checks.
    """
    if os.name == "nt":
        _fail("Windows build-process containment is not qualified for this helper.")
    bundle_module._validate_binding(binding)
    descriptor = load_build_environment_descriptor(
        environment_descriptor, expected_sha256=expected_build_environment_sha256
    )
    source_root = source_root.resolve(strict=True)
    _verify_source(source_root, binding)
    binding_sha256 = _verify_descriptor_binding(descriptor, binding)
    lock_sha256, recipe_sha256 = _locked_build_identity(source_root)
    if lock_sha256 != descriptor.build_lock_sha256:
        _fail("Checked-out dedicated build lock does not match the environment descriptor.")
    if recipe_sha256 != descriptor.provisioning_recipe_sha256:
        _fail("Checked-out provisioning recipe does not match the environment descriptor.")
    target_os, target_architecture = _native_marker_target()
    if (descriptor.target_os, descriptor.target_architecture) != (target_os, target_architecture):
        _fail("Build-environment target does not match the native build worker.")
    output_dir = _require_new_directory(wheel_output_dir, "Temporary wheel output directory")
    if output_dir == source_root or source_root in output_dir.parents:
        _fail("Temporary wheel output must remain outside the bound source checkout.")
    if artifact.is_symlink() or not artifact.is_file():
        _fail("Bound source distribution must be a regular file.")
    python_executable, python_implementation, python_version = _python_identity(python)
    python_executable_sha256 = _sha256_file(python_executable)
    if (
        python_implementation != descriptor.python_implementation
        or python_version != descriptor.python_version
        or python_executable_sha256 != descriptor.python_executable_sha256
    ):
        _fail("Selected Python interpreter identity does not match the environment descriptor.")
    uv, uv_digest = _safe_uv(uv_executable, uv_sha256)
    if uv_digest != descriptor.uv_sha256:
        _fail("Selected uv executable does not match the environment descriptor.")
    uv_version = _read_uv_version(uv)
    if uv_version != descriptor.uv_version:
        _fail("Selected uv version does not match the environment descriptor.")
    expected_sdist_sha256 = descriptor.sdist_sha256
    initial_size, initial_digest = bundle_module._archive_sha256(artifact)
    if (
        initial_size != descriptor.sdist_size
        or initial_digest != expected_sdist_sha256
        or initial_size != binding.sdist_size
        or initial_digest != binding.sdist_sha256
    ):
        _fail("Selected source distribution does not match the independent bundle binding.")
    if _sha256_file(Path(str(uv))) != uv_digest:
        _fail("Selected uv executable changed during qualification preflight.")

    _payload, metadata = _authenticated_archive(artifact, binding, "sdist")
    pkg_info = metadata.get("METADATA")
    if pkg_info is None:
        _fail("Authenticated source distribution has no package identity metadata.")
    package_metadata = BytesParser().parsebytes(pkg_info, headersonly=True)
    if (
        canonicalize_name(package_metadata.get("Name", "")) != "matryca-plumber"
        or package_metadata.get("Version") != binding.version
    ):
        _fail("Authenticated source distribution identity differs from its binding.")

    provisioned_packages = descriptor.packages
    before_hooks_packages: tuple[tuple[str, str], ...]
    after_hooks_packages: tuple[tuple[str, str], ...]
    after_build_packages: tuple[tuple[str, str], ...]
    static_requirement_records: tuple[BuildRequirementRecord, ...]
    dynamic_requirement_records: tuple[BuildRequirementRecord, ...]
    with tempfile.TemporaryDirectory(prefix="matryca-sdist-build-") as temporary:
        temporary_root = Path(temporary)
        extraction_root = temporary_root / "source"
        extraction_root.mkdir(mode=0o700)
        hook_source = _extract_sdist(artifact, extraction_root, binding)
        pyproject_bytes = (hook_source / "pyproject.toml").read_bytes()
        backend, static_requirements = _parse_build_system(pyproject_bytes)
        try:
            project = tomllib.loads(pyproject_bytes.decode("utf-8")).get("project", {})
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
            raise ValueError("Authenticated sdist project metadata is invalid.") from error
        if (
            not isinstance(project, dict)
            or canonicalize_name(str(project.get("name", ""))) != "matryca-plumber"
            or project.get("version") != binding.version
            or "version" in project.get("dynamic", [])
        ):
            _fail("Authenticated source project identity must be static and match its binding.")

        wheel_build_dir = temporary_root / "wheel-output"
        wheel_build_dir.mkdir(mode=0o700)
        before_hooks_packages = _read_package_manifest(uv, python)
        if before_hooks_packages != provisioned_packages:
            _fail("Observed package manifest differs from the provisioned descriptor before hooks.")
        static_requirement_records = _build_requirement_records(
            static_requirements,
            dict(before_hooks_packages),
            label="static PEP 518 build requirement",
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
        )
        dynamic_backend, backend_version, dynamic_raw = _query_backend(python, hook_source)
        if dynamic_backend != backend:
            _fail("PEP 517 backend identity changed during its requirements query.")
        after_hooks_packages = _read_package_manifest(uv, python)
        if after_hooks_packages != provisioned_packages:
            _fail("Observed package manifest changed after build hooks.")
        packages_after_hooks = dict(after_hooks_packages)
        dynamic_requirement_records = _build_requirement_records(
            dynamic_raw,
            packages_after_hooks,
            label="dynamic PEP 517 build requirement",
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
        )
        observed_backend_version = packages_after_hooks.get("setuptools")
        if observed_backend_version is None or backend_version != observed_backend_version:
            _fail("PEP 517 backend version does not match the provisioned build manifest.")

        build_extraction_root = temporary_root / "build-source"
        build_extraction_root.mkdir(mode=0o700)
        build_source = _extract_sdist(artifact, build_extraction_root, binding)
        prebuild_size, prebuild_digest = bundle_module._archive_sha256(artifact)
        if prebuild_size != initial_size or prebuild_digest != expected_sdist_sha256:
            _fail("Authenticated source distribution changed before the sdist build.")

        build_command = [
            str(uv),
            "build",
            "--wheel",
            "--no-build-isolation",
            "--no-config",
            "--python",
            str(python),
            "--out-dir",
            str(wheel_build_dir),
            str(build_source),
        ]
        if (
            _sha256_file(Path(str(uv))) != uv_digest
            or _sha256_file(python_executable) != python_executable_sha256
        ):
            _fail("Selected build executable changed before the sdist build.")
        if _locked_build_identity(source_root) != (lock_sha256, recipe_sha256):
            _fail("Checked-out dedicated build inputs changed before the sdist build.")
        build_result = _run_bounded(build_command, timeout=_COMMAND_TIMEOUT_SECONDS)
        if build_result.returncode != 0:
            _fail("uv could not build the authenticated source distribution without isolation.")
        after_build_packages = _read_package_manifest(uv, python)
        if after_build_packages != provisioned_packages:
            _fail("Observed package manifest changed after the wheel build.")
        if (
            _sha256_file(Path(str(uv))) != uv_digest
            or _sha256_file(python_executable) != python_executable_sha256
        ):
            _fail("Selected build executable changed during qualification.")
        final_size, final_digest = bundle_module._archive_sha256(artifact)
        if final_size != initial_size or final_digest != expected_sdist_sha256:
            _fail("Authenticated source distribution changed during qualification.")
        generated = list(wheel_build_dir.iterdir())
        if len(generated) != 1 or generated[0].is_symlink() or not generated[0].is_file():
            _fail("Source distribution build did not produce exactly one wheel.")
        temporary_wheel = _verify_generated_wheel(
            generated[0], binding.wheel_name, "matryca-plumber", binding.version
        )
        if temporary_wheel.size > _MAX_OUTPUT_BYTES:
            _fail("Generated temporary wheel exceeds the qualification size limit.")
        receipt = SdistBuildReceipt(
            schema_version=2,
            source_commit=binding.source_commit,
            source_tree=binding.source_tree,
            binding_sha256=binding_sha256,
            sdist_name=binding.sdist_name,
            sdist_size=initial_size,
            sdist_sha256=initial_digest,
            wheel_name=temporary_wheel.name,
            wheel_size=temporary_wheel.size,
            wheel_sha256=temporary_wheel.sha256,
            build_lock_sha256=lock_sha256,
            environment_descriptor_sha256=expected_build_environment_sha256,
            provisioning_recipe_sha256=descriptor.provisioning_recipe_sha256,
            provisioning_evidence_sha256=descriptor.provisioning_evidence_sha256,
            target_os=target_os,
            target_architecture=target_architecture,
            python_implementation=python_implementation,
            python_version=python_version,
            python_executable_sha256=python_executable_sha256,
            uv_version=uv_version,
            uv_sha256=uv_digest,
            backend=backend,
            backend_version=backend_version,
            static_requirement_records=static_requirement_records,
            dynamic_requirement_records=dynamic_requirement_records,
            provisioned_packages=provisioned_packages,
            before_hooks_packages=before_hooks_packages,
            after_hooks_packages=after_hooks_packages,
            after_build_packages=after_build_packages,
        )
        output_wheel_path = _copy_wheel(generated[0], output_dir, binding.wheel_name)
        try:
            copied_wheel = _verify_generated_wheel(
                output_wheel_path, binding.wheel_name, "matryca-plumber", binding.version
            )
            if copied_wheel != temporary_wheel:
                _fail("Preserved temporary wheel differs from the verified build output.")
        except BaseException:
            output_wheel_path.unlink(missing_ok=True)
            raise

    return receipt
