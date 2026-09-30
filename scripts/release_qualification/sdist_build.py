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

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.installed import _authenticated_archive, _verify_source

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PYTHON_VERSION = re.compile(r"3\.12\.[0-9]+(?:[A-Za-z0-9.+-]*)?\Z")
_MAX_CAPTURE_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 512 * 1024 * 1024
_MAX_BUILD_REQUIREMENT_LENGTH = 2048
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
    python_version: str
    uv_version: str
    uv_sha256: str
    backend: str
    backend_version: str
    static_requirements: tuple[str, ...]
    dynamic_requirement_expressions: tuple[str, ...]
    dynamic_requirements: tuple[tuple[str, str], ...]
    build_packages: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, object]:
        """Return stable JSON data without local paths or raw command output."""
        value = asdict(self)
        value["dynamic_requirements"] = [
            {"name": name, "version": version} for name, version in self.dynamic_requirements
        ]
        value["build_packages"] = [
            {"name": name, "version": version} for name, version in self.build_packages
        ]
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


def _marker_environment(platform: str, architecture: str, python_version: str) -> dict[str, str]:
    """Build the same bounded PEP 508 marker environment for helper and verifier."""
    if _PYTHON_VERSION.fullmatch(python_version) is None:
        _fail("Build marker Python version is invalid.")
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
            "implementation_name": "cpython",
            "implementation_version": python_version,
            "os_name": "nt" if platform == "windows" else "posix",
            "platform_machine": machine,
            "platform_python_implementation": "CPython",
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
    marker_names = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", marker_expression))
    if marker_names & {
        "dependency_groups",
        "extra",
        "extras",
        "platform_release",
        "platform_version",
    }:
        _fail("Authenticated sdist requirement uses an unbound platform marker.")


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


def _verify_dynamic_requirements(
    dynamic: tuple[str, ...],
    installed: dict[str, str],
    *,
    platform: str,
    architecture: str,
    python_version: str,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    if (
        len(dynamic) > 256
        or any(not isinstance(item, str) for item in dynamic)
        or len(set(dynamic)) != len(dynamic)
    ):
        _fail("PEP 517 backend returned invalid dynamic build requirements.")
    environment = _marker_environment(platform, architecture, python_version)
    verified: set[tuple[str, str]] = set()
    for raw in dynamic:
        requirement = _parse_requirement(raw, "dynamic build requirement")
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        name = canonicalize_name(requirement.name)
        version = installed.get(name)
        if version is None:
            _fail("A dynamic build requirement is not already installed.")
        try:
            parsed_version = Version(version)
        except Exception as error:
            raise ValueError("Installed build package has an invalid version.") from error
        if requirement.specifier and parsed_version not in requirement.specifier:
            _fail("A dynamic build requirement is not satisfied by the observed build environment.")
        verified.add((name, version))
    return dynamic, tuple(sorted(verified))


def _parse_static_requirements(
    requirements: tuple[str, ...],
    installed: dict[str, str],
    *,
    platform: str,
    architecture: str,
    python_version: str,
) -> None:
    environment = _marker_environment(platform, architecture, python_version)
    for raw in requirements:
        requirement = _parse_requirement(raw, "static build requirement")
        if requirement.marker and not requirement.marker.evaluate(environment):
            continue
        name = canonicalize_name(requirement.name)
        version = installed.get(name)
        if version is None:
            _fail("A declared PEP 518 build requirement is missing from the isolated environment.")
        try:
            parsed_version = Version(version)
        except Exception as error:
            raise ValueError("Installed build package has an invalid version.") from error
        if requirement.specifier and parsed_version not in requirement.specifier:
            _fail("A declared PEP 518 requirement does not match its installed version.")


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


def _python_version(executable: Path) -> str:
    output = (
        _checked_output(
            [
                str(executable),
                "-I",
                "-S",
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3])))",
            ]
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if not _PYTHON_VERSION.fullmatch(output):
        _fail("Qualification requires a Python 3.12 interpreter.")
    return output


def _verify_venv_interpreter(
    executable: Path, expected_prefix: Path, expected_version: str
) -> None:
    probe = (
        'import json,sys; print(json.dumps({"prefix":sys.prefix,"base_prefix":sys.base_prefix,'
        "\"version\":'.'.join(map(str,sys.version_info[:3]))},separators=(',',':')))"
    )
    try:
        value = json.loads(_checked_output([str(executable), "-I", "-c", probe]))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Isolated build interpreter identity is malformed.") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"prefix", "base_prefix", "version"}
        or Path(str(value["prefix"])).resolve() != expected_prefix.resolve()
        or Path(str(value["base_prefix"])).resolve() == expected_prefix.resolve()
        or value["version"] != expected_version
    ):
        _fail("uv did not create an isolated build interpreter at the expected path and version.")


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
) -> SdistBuildReceipt:
    """Build one temporary wheel from an authenticated sdist in a private venv.

    The temporary wheel is placed only in an empty directory outside the bound
    source checkout. Dynamic PEP 517 requirements are checked against the
    already installed static build environment and are never installed here.
    """
    if os.name == "nt":
        _fail("Windows build-process containment is not qualified for this helper.")
    bundle_module._validate_binding(binding)
    source_root = source_root.resolve(strict=True)
    _verify_source(source_root, binding)
    output_dir = _require_new_directory(wheel_output_dir, "Temporary wheel output directory")
    if output_dir == source_root or source_root in output_dir.parents:
        _fail("Temporary wheel output must remain outside the bound source checkout.")
    if artifact.is_symlink() or not artifact.is_file():
        _fail("Bound source distribution must be a regular file.")
    if not python.is_file() or not python.resolve(strict=True).is_file():
        _fail("Selected Python interpreter must be a regular executable file.")
    uv, uv_digest = _safe_uv(uv_executable, uv_sha256)
    uv_version = _read_uv_version(uv)
    python_version = _python_version(python)
    expected_sdist_sha256 = binding.sdist_sha256
    initial_size, initial_digest = bundle_module._archive_sha256(artifact)
    if initial_size != binding.sdist_size or initial_digest != expected_sdist_sha256:
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

        build_env = temporary_root / "build-env"
        build_python = build_env / "bin" / "python"
        wheel_build_dir = temporary_root / "wheel-output"
        wheel_build_dir.mkdir(mode=0o700)
        _checked_output([str(uv), "venv", "--no-project", "--python", str(python), str(build_env)])
        if not build_python.is_file() or not build_python.resolve(strict=True).is_file():
            _fail("uv did not create the expected isolated build interpreter.")
        _verify_venv_interpreter(build_python, build_env, python_version)
        install_result = _run_bounded(
            [str(uv), "pip", "install", "--python", str(build_python), *static_requirements],
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
        if install_result.returncode != 0:
            _fail("Could not install the declared static PEP 518 build requirements.")
        manifest = _read_package_manifest(uv, build_python)
        packages = dict(manifest)
        target_platform, target_architecture = _native_marker_target()
        _parse_static_requirements(
            static_requirements,
            packages,
            platform=target_platform,
            architecture=target_architecture,
            python_version=python_version,
        )
        dynamic_backend, backend_version, dynamic_raw = _query_backend(build_python, hook_source)
        if dynamic_backend != backend:
            _fail("PEP 517 backend identity changed during its requirements query.")
        _verify_dynamic_requirements(
            dynamic_raw,
            packages,
            platform=target_platform,
            architecture=target_architecture,
            python_version=python_version,
        )
        observed_backend_version = packages.get("setuptools")
        if observed_backend_version is None or backend_version != observed_backend_version:
            _fail("PEP 517 backend version does not match the observed build manifest.")
        if _read_package_manifest(uv, build_python) != manifest:
            _fail("PEP 517 hook changed the isolated build package manifest.")

        build_extraction_root = temporary_root / "build-source"
        build_extraction_root.mkdir(mode=0o700)
        build_source = _extract_sdist(artifact, build_extraction_root, binding)

        build_command = [
            str(uv),
            "build",
            "--wheel",
            "--no-build-isolation",
            "--no-config",
            "--python",
            str(build_python),
            "--out-dir",
            str(wheel_build_dir),
            str(build_source),
        ]
        if _sha256_file(Path(str(uv))) != uv_digest:
            _fail("Selected uv executable changed before the sdist build.")
        build_result = _run_bounded(build_command, timeout=_COMMAND_TIMEOUT_SECONDS)
        if build_result.returncode != 0:
            _fail("uv could not build the authenticated source distribution without isolation.")
        if _sha256_file(Path(str(uv))) != uv_digest:
            _fail("Selected uv executable changed during qualification.")
        if _read_package_manifest(uv, build_python) != manifest:
            _fail("Isolated build package manifest changed during qualification.")
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
        output_wheel_path = _copy_wheel(generated[0], output_dir, binding.wheel_name)
        copied_wheel = _verify_generated_wheel(
            output_wheel_path, binding.wheel_name, "matryca-plumber", binding.version
        )
        if copied_wheel != temporary_wheel:
            _fail("Preserved temporary wheel differs from the verified build output.")

    dynamic_expressions, dynamic_verified = _verify_dynamic_requirements(
        dynamic_raw,
        packages,
        platform=target_platform,
        architecture=target_architecture,
        python_version=python_version,
    )
    return SdistBuildReceipt(
        schema_version=1,
        source_commit=binding.source_commit,
        source_tree=binding.source_tree,
        binding_sha256=hashlib.sha256(binding.to_json().encode("utf-8")).hexdigest(),
        sdist_name=binding.sdist_name,
        sdist_size=initial_size,
        sdist_sha256=initial_digest,
        wheel_name=copied_wheel.name,
        wheel_size=copied_wheel.size,
        wheel_sha256=copied_wheel.sha256,
        python_version=python_version,
        uv_version=uv_version,
        uv_sha256=uv_digest,
        backend=backend,
        backend_version=backend_version,
        static_requirements=static_requirements,
        dynamic_requirement_expressions=dynamic_expressions,
        dynamic_requirements=dynamic_verified,
        build_packages=manifest,
    )
