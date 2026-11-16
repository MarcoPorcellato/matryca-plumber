"""Verify a release distribution after isolated installation."""

from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shlex
import stat
import subprocess
import tempfile
import threading
import time
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import IO, Literal, NoReturn, cast
from urllib.parse import urlparse

from scripts.build_release_artifacts import _PUBLIC_CONTRACT_RESOURCE_MEMBERS
from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification import process as process_module
from scripts.release_qualification import windows_installation as windows_authority
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.windows_launcher import (
    expected_windows_console_launcher,
    verify_windows_console_launcher,
)

_MAX_RECORD_BYTES = 8 * 1024 * 1024
_MAX_RECORD_ROWS = 20_000
_MAX_PROBE_BYTES = 1024 * 1024
_MAX_INSTALLED_FILE_BYTES = 64 * 1024 * 1024
_MAX_INSTALLED_TOTAL_BYTES = 512 * 1024 * 1024
_MAX_TCK_SECONDS = 30
_RESOURCE_FILES = tuple(sorted(_PUBLIC_CONTRACT_RESOURCE_MEMBERS))
_TCKS = {
    "scripts/run_plumber_consumer_package_v1_tck.py": "plumber.consumer.package/v1",
    "scripts/run_plumber_graph_read_v1_tck.py": "plumber.graph.read/v1",
    "scripts/run_plumber_graph_topology_v1_tck.py": "plumber.graph.topology/v1",
}
_INSTALLER_METADATA = frozenset(
    {"INSTALLER", "direct_url.json", "REQUESTED", "uv_cache.json", "uv_build.json"}
)
_ENTRY_POINTS = frozenset({"matryca", "matryca-plumber", "matryca-logseq-llm-wiki"})
_HASH_ALGORITHMS = frozenset({"sha256", "sha384", "sha512"})
_IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True, slots=True)
class BuildGenerator:
    """Sanitized generator identity recorded by installed WHEEL metadata."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class InstalledReceipt:
    """Sanitized evidence for one isolated wheel or sdist installation."""

    kind: Literal["wheel", "sdist"]
    operating_system: str
    architecture: str
    python_version: str
    version: str
    location_class: str
    record_sha256: str
    resource_sha256: str
    dependency_sha256: str
    dependencies: tuple[tuple[str, str], ...]
    build_generator: BuildGenerator
    tck_outcomes: tuple[str, str, str]
    schema_version: int = 2
    windows_launcher: windows_authority.WindowsLauncherProof | None = None

    def to_dict(self) -> dict[str, object]:
        """Return stable JSON-compatible receipt data without local paths."""
        if type(self.schema_version) is not int or self.schema_version != 2:
            _fail("Installed receipt schema version must be integer 2.")
        if self.operating_system == "windows":
            if not isinstance(self.windows_launcher, windows_authority.WindowsLauncherProof):
                _fail("Windows installed receipt requires an independent launcher proof.")
            if self.python_version != self.windows_launcher.interpreter.version:
                _fail("Windows installed receipt and launcher proof Python versions differ.")
        elif self.windows_launcher is not None:
            _fail("Windows launcher proof is invalid on a non-Windows installed receipt.")
        value = asdict(self)
        value["dependencies"] = [
            {"name": name, "version": version} for name, version in self.dependencies
        ]
        value["build_generator"] = asdict(self.build_generator)
        value["windows_launcher"] = (
            self.windows_launcher.to_dict() if self.windows_launcher is not None else None
        )
        return value

    def to_json(self) -> str:
        """Serialize receipt data as canonical compact JSON."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _safe_root(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        _fail(f"{label} must be a regular directory.")
    return path.resolve(strict=True)


def _git_value(source_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=source_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not verify selected source provenance.") from error


def _verify_source(source_root: Path, binding: BundleBinding) -> set[str]:
    commit = _git_value(source_root, "rev-parse", "HEAD")
    tree = _git_value(source_root, "rev-parse", "HEAD^{tree}")
    status = _git_value(source_root, "status", "--porcelain", "--untracked-files=all")
    if commit != binding.source_commit or tree != binding.source_tree or status:
        _fail("Source checkout does not match the clean bound commit and tree.")
    try:
        tracked = subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "-z", binding.source_commit],
            cwd=source_root,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not enumerate selected source files.") from error
    return {item.decode("utf-8") for item in tracked.split(b"\0") if item}


def _payload_map(source_root: Path, tracked: set[str]) -> dict[str, Path]:
    gateway = bundle_module._gateway_source_files({name: "" for name in tracked})
    expected: dict[str, Path] = {}
    for name in tracked:
        if name in gateway or (name.startswith("src/") and name.endswith(".py")):
            expected[name] = source_root / name
        elif name.startswith("contracts/"):
            expected[f"src/contract_artifacts/{name}"] = source_root / name
        elif name in _TCKS:
            expected[f"src/contract_artifacts/tck/{PurePosixPath(name).name}"] = source_root / name
        elif name == "frontend/__init__.py" or name.startswith("frontend/dist/"):
            expected[name] = source_root / name
    for member in _PUBLIC_CONTRACT_RESOURCE_MEMBERS:
        if member.startswith("src/contract_artifacts/contracts/"):
            source_name = member.removeprefix("src/contract_artifacts/")
        else:
            source_name = f"scripts/{PurePosixPath(member).name}"
        if source_name not in tracked:
            _fail("Selected source is missing a required contract or TCK resource.")
    return expected


def _authenticated_archive(
    artifact: Path, binding: BundleBinding, kind: Literal["wheel", "sdist"], *, policy: str = "rc4"
) -> tuple[dict[str, tuple[int, str]], dict[str, bytes]]:
    """Authenticate archive bytes against independent binding before using content."""
    bundle_module._validate_binding(binding, policy=policy)
    if artifact.is_symlink() or not artifact.is_file():
        _fail("Bound release artifact must be an existing regular file.")
    expected_name = binding.wheel_name if kind == "wheel" else binding.sdist_name
    if artifact.name != expected_name:
        _fail("Release artifact filename does not match its bound kind and version.")
    expected_size = binding.wheel_size if kind == "wheel" else binding.sdist_size
    expected_digest = binding.wheel_sha256 if kind == "wheel" else binding.sdist_sha256
    size, digest = bundle_module._archive_sha256(artifact)
    if size != expected_size or digest != expected_digest:
        _fail("Release artifact bytes do not match the independent binding.")
    if kind == "wheel":
        members, contents = bundle_module._read_wheel(artifact)
        expected_inventory = binding.wheel_inventory_sha256
    else:
        members, contents, _directories = bundle_module._read_sdist(
            artifact, f"matryca_plumber-{binding.version}"
        )
        expected_inventory = binding.sdist_inventory_sha256
    if bundle_module._inventory_digest(members) != expected_inventory:
        _fail("Release artifact inventory does not match the independent binding.")
    gateway = bundle_module._gateway_source_files(
        {name: member.sha256 for name, member in members.items()}
    )

    payload: dict[str, tuple[int, str]] = {}
    metadata: dict[str, bytes] = {}
    dist_info_roots = {
        member.name.split("/", 1)[0]
        for member in members.values()
        if member.name.endswith(".dist-info/METADATA")
    }
    if kind == "wheel":
        if len(dist_info_roots) != 1:
            _fail("Authenticated wheel must contain exactly one dist-info root.")
        dist_info_root = next(iter(dist_info_roots))
        for name, member in members.items():
            if name in gateway or name.startswith(("src/", "frontend/")):
                payload[name] = (member.size, member.sha256)
            elif name.startswith(f"{dist_info_root}/") and not name.endswith("/RECORD"):
                payload[name] = (member.size, member.sha256)
                if name.endswith("/METADATA"):
                    metadata["METADATA"] = contents[name]
    else:
        for name, member in members.items():
            if name in gateway or name.startswith(("src/", "frontend/")):
                payload[name] = (member.size, member.sha256)
            elif name.startswith("contracts/"):
                payload[f"src/contract_artifacts/{name}"] = (member.size, member.sha256)
            elif name in _TCKS:
                installed_name = f"src/contract_artifacts/tck/{PurePosixPath(name).name}"
                payload[installed_name] = (member.size, member.sha256)
            elif name in {"LICENSE", "NOTICE"}:
                payload[f"matryca_plumber-{binding.version}.dist-info/licenses/{name}"] = (
                    member.size,
                    member.sha256,
                )
            elif name == "PKG-INFO":
                metadata["METADATA"] = contents[name]
                payload[f"matryca_plumber-{binding.version}.dist-info/METADATA"] = (
                    member.size,
                    member.sha256,
                )
    return payload, metadata


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_bounded(path: Path) -> bytes:
    if _IS_WINDOWS and path.parent.name == "Scripts" and path.suffix.lower() == ".exe":
        return windows_authority.read_authority_file(path, limit=windows_authority.LAUNCHER_LIMIT)
    size = path.stat().st_size
    if size < 0 or size > _MAX_INSTALLED_FILE_BYTES:
        _fail("Installed distribution file exceeds the size limit.")
    with path.open("rb") as stream:
        payload = stream.read(_MAX_INSTALLED_FILE_BYTES + 1)
    if len(payload) != size or len(payload) > _MAX_INSTALLED_FILE_BYTES:
        _fail("Installed distribution file changed or exceeds the size limit.")
    return payload


def _parse_record(record: Path, site: Path, env_root: Path) -> dict[str, tuple[Path, str, str]]:
    if record.is_symlink() or not record.is_file():
        _fail("Installed distribution RECORD is missing or not a regular file.")
    if record.stat().st_size > _MAX_RECORD_BYTES:
        _fail("Installed distribution RECORD exceeds the size limit.")
    try:
        with record.open("r", encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream, strict=True))
    except (OSError, UnicodeError, csv.Error) as error:
        raise ValueError("Installed distribution RECORD is malformed.") from error
    if not rows:
        _fail("Installed distribution RECORD is empty.")
    if len(rows) > _MAX_RECORD_ROWS:
        _fail("Installed distribution RECORD contains too many rows.")

    parsed: dict[str, tuple[Path, str, str]] = {}
    for row in rows:
        if len(row) != 3:
            _fail("Installed distribution RECORD row must contain three fields.")
        raw_name, digest, size = row
        name = raw_name.replace("\\", "/")
        if name.lower().endswith((".pyc", ".pyo")):
            _fail("Installed distribution contains generated bytecode.")
        relative = PurePosixPath(name)
        if (
            not name
            or "\x00" in name
            or relative.is_absolute()
            or re.match(r"^[A-Za-z]:", name)
            or any(part in {"", "."} for part in name.split("/"))
            or relative.as_posix() != name
        ):
            _fail("Installed distribution RECORD contains an unsafe path.")
        if name in parsed:
            _fail("Installed distribution RECORD contains a duplicate path.")
        script_root = env_root / ("Scripts" if os.name == "nt" else "bin")
        candidate = site.joinpath(*relative.parts)
        if _IS_WINDOWS:
            # Inspect the owned components before resolving RECORD's allowed traversal.
            lexical = Path(os.path.abspath(candidate)) if ".." in relative.parts else candidate
            if not _within(lexical, env_root):
                _fail("Installed Windows RECORD path escapes the selected environment.")
            windows_authority.reject_path_redirection(site)
            windows_authority.reject_path_redirection(env_root / "Scripts")
            windows_authority.reject_path_redirection(lexical)
        if ".." in relative.parts:
            candidate = candidate.resolve(strict=False)
            expected_scripts = {
                (script_root / (f"{entry}.exe" if os.name == "nt" else entry)).resolve(strict=False)
                for entry in _ENTRY_POINTS
            }
            if candidate not in expected_scripts:
                _fail("Installed distribution RECORD contains an unsafe path.")
            canonical = os.path.relpath(candidate, site).replace(os.sep, "/")
            if canonical != name:
                _fail("Installed distribution RECORD contains a noncanonical script path.")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as error:
            raise ValueError("Installed distribution RECORD names a missing file.") from error
        if candidate.is_symlink():
            _fail("Installed distribution RECORD path may not link into the source checkout.")
        if not resolved.is_file():
            _fail("Installed distribution RECORD path is not a regular file.")
        if not (_within(resolved, site) or _within(resolved, env_root)):
            _fail("Installed distribution RECORD path escapes the selected environment.")
        if not digest and not size:
            parts = PurePosixPath(name).parts
            generated_metadata = (
                len(parts) == 2
                and parts[0].endswith(".dist-info")
                and parts[1] in _INSTALLER_METADATA
            )
            if name != record.relative_to(site).as_posix() and not generated_metadata:
                _fail("Empty RECORD hash and size are not allowed for this file.")
        parsed[name] = (resolved, digest, size)
    if record.relative_to(site).as_posix() not in parsed:
        _fail("Installed distribution RECORD does not list itself.")
    return parsed


def _verify_record_entry(name: str, entry: tuple[Path, str, str], record_name: str) -> None:
    path, encoded_hash, encoded_size = entry
    payload = _read_bounded(path)
    if name == record_name and not encoded_hash and not encoded_size:
        return
    if not encoded_hash:
        if PurePosixPath(name).name not in _INSTALLER_METADATA:
            _fail("Installed distribution payload is missing a RECORD hash.")
    else:
        algorithm, separator, encoded = encoded_hash.partition("=")
        if not separator or algorithm.lower() not in _HASH_ALGORITHMS:
            _fail("Installed distribution RECORD hash algorithm is too weak or malformed.")
        try:
            actual = (
                base64.urlsafe_b64encode(hashlib.new(algorithm.lower(), payload).digest())
                .decode("ascii")
                .rstrip("=")
            )
        except ValueError as error:
            raise ValueError(
                "Installed distribution RECORD hash algorithm is unsupported."
            ) from error
        if not encoded or encoded.rstrip("=") != actual:
            _fail("Installed distribution RECORD hash does not match its file.")
    if not encoded_size:
        if PurePosixPath(name).name not in _INSTALLER_METADATA:
            _fail("Installed distribution payload is missing a RECORD size.")
    elif not re.fullmatch(r"(?:0|[1-9][0-9]*)", encoded_size) or int(encoded_size) != len(payload):
        _fail("Installed distribution RECORD size does not match its file.")


def _distribution(site: Path, expected_version: str) -> tuple[Path, str]:
    candidates: list[Path] = []
    version: str | None = None
    for directory in site.glob("*.dist-info"):
        metadata = directory / "METADATA"
        if directory.is_symlink() or metadata.is_symlink() or not metadata.is_file():
            continue
        try:
            distribution = importlib.metadata.PathDistribution(directory)
            name = distribution.metadata.get("Name", "")
            found_version = distribution.version
        except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
            continue
        if re.sub(r"[-_.]+", "-", name).lower() == "matryca-plumber":
            candidates.append(directory)
            version = found_version
    if len(candidates) != 1 or version != expected_version:
        _fail("Installed package identity or version does not match the binding.")
    if version is None:
        _fail("Installed package version is missing.")
    return candidates[0], version


def _expected_scripts(source_root: Path) -> dict[str, str]:
    try:
        with (source_root / "pyproject.toml").open("rb") as stream:
            parsed = tomllib.load(stream)
        scripts = parsed["project"]["scripts"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("Bound source entry-point configuration is malformed.") from error
    expected = {
        "matryca": "src.cli:main",
        "matryca-plumber": "src.plumber_entry:main",
        "matryca-logseq-llm-wiki": "src.main:main",
    }
    if scripts != expected:
        _fail("Bound source console-script map is not the reviewed release map.")
    return expected


def _verify_generated_metadata(
    dist_info: Path,
    source_root: Path,
    archive_payload: dict[str, tuple[int, str]],
    kind: Literal["wheel", "sdist"],
) -> tuple[dict[str, str], BuildGenerator]:
    """Validate the finite installer/build metadata classes accepted by this task."""
    required = {
        "METADATA",
        "WHEEL",
        "entry_points.txt",
        "top_level.txt",
        "licenses/LICENSE",
        "licenses/NOTICE",
        "RECORD",
    }
    optional = {"INSTALLER", "direct_url.json", "REQUESTED", "uv_cache.json"}
    if kind == "sdist":
        optional.add("uv_build.json")
    actual = _scope_files(dist_info, label="distribution metadata")
    if not required <= actual or actual - required - optional:
        _fail("Installed distribution metadata inventory is incomplete or unexpected.")
    for name in actual & optional:
        path = dist_info / name
        content = _read_bounded(path)
        if name == "INSTALLER":
            if content.strip() != b"uv":
                _fail("Installed distribution INSTALLER metadata is unexpected.")
        elif name == "REQUESTED":
            if content:
                _fail("Installed distribution REQUESTED metadata is malformed.")
        elif name == "direct_url.json":
            try:
                direct_url = json.loads(content)
                url = direct_url["url"]
                details = direct_url.get("archive_info", direct_url.get("dir_info"))
                parsed_url = urlparse(url)
            except (TypeError, KeyError, json.JSONDecodeError, ValueError) as error:
                raise ValueError("Installed direct_url metadata is malformed.") from error
            if (
                set(direct_url) - {"url", "archive_info", "dir_info"}
                or ("archive_info" in direct_url) == ("dir_info" in direct_url)
                or not isinstance(url, str)
                or parsed_url.scheme != "file"
                or not isinstance(details, dict)
            ):
                _fail("Installed direct_url metadata is outside the accepted local-install form.")
        elif name == "uv_cache.json":
            try:
                cache = json.loads(content)
                timestamp = cache["timestamp"]
                seconds, nanos = timestamp["secs_since_epoch"], timestamp["nanos_since_epoch"]
            except (TypeError, KeyError, json.JSONDecodeError, ValueError) as error:
                raise ValueError("Installed uv cache metadata is malformed.") from error
            if (
                set(cache) != {"timestamp", "commit", "tags", "env", "directories"}
                or set(timestamp) != {"secs_since_epoch", "nanos_since_epoch"}
                or not isinstance(seconds, int)
                or not isinstance(nanos, int)
                or not 0 <= nanos < 1_000_000_000
                or (cache["commit"] is not None and not isinstance(cache["commit"], str))
                or (cache["tags"] is not None and not isinstance(cache["tags"], list))
                or not isinstance(cache["env"], dict)
                or not isinstance(cache["directories"], dict)
            ):
                _fail("Installed uv cache metadata is outside the accepted schema.")
        elif name == "uv_build.json" and json.loads(content) != {}:
            _fail("Installed uv build metadata is outside the accepted schema.")

    wheel = (dist_info / "WHEEL").read_text(encoding="utf-8")
    wheel_fields: dict[str, list[str]] = {}
    for line in wheel.splitlines():
        if not line:
            continue
        key, separator, value = line.partition(":")
        if not separator or key not in {"Wheel-Version", "Generator", "Root-Is-Purelib", "Tag"}:
            _fail("Installed WHEEL metadata contains an unknown field.")
        wheel_fields.setdefault(key, []).append(value.strip())
    generator_value = wheel_fields.get("Generator", [""])[0]
    generator_match = re.fullmatch(
        r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]{0,99}) "
        r"\((?P<version>[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127})\)",
        generator_value,
    )
    if (
        wheel_fields.get("Wheel-Version") != ["1.0"]
        or wheel_fields.get("Root-Is-Purelib") != ["true"]
        or wheel_fields.get("Tag") != ["py3-none-any"]
        or len(wheel_fields.get("Generator", [])) != 1
        or generator_match is None
        or generator_match.group("name") != "setuptools"
    ):
        _fail("Installed WHEEL metadata does not match the accepted pure-Python wheel.")

    scripts = _expected_scripts(source_root)
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string((dist_info / "entry_points.txt").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, configparser.Error) as error:
        raise ValueError("Installed entry-point metadata is malformed.") from error
    if parser.sections() != ["console_scripts"] or dict(parser["console_scripts"]) != scripts:
        _fail("Installed entry-point metadata differs from the bound source project.")
    expected_top_level = sorted(
        {
            name.split("/", 1)[0]
            for name in archive_payload
            if name.startswith(("src/", "frontend/", "matryca_plumber/"))
        }
    )
    top_level = (dist_info / "top_level.txt").read_text(encoding="utf-8").splitlines()
    if top_level != expected_top_level:
        _fail("Installed top-level package metadata differs from the authenticated payload.")
    return scripts, BuildGenerator(
        name=generator_match.group("name"), version=generator_match.group("version")
    )


def _verify_entry_point_scripts(
    entries: dict[str, tuple[Path, str, str]],
    site: Path,
    env_root: Path,
    scripts: dict[str, str],
    *,
    windows_context: _WindowsInstallationContext | None = None,
) -> windows_authority.WindowsLauncherProof | None:
    if _IS_WINDOWS:
        if windows_context is None:
            _fail("Windows installed-package qualification is NO-GO without independent authority.")
        return windows_context.observe_launchers(entries, site, env_root, scripts)
    script_dir_name = "Scripts" if os.name == "nt" else "bin"
    script_root = (env_root / script_dir_name).resolve(strict=True)
    expected_names = {
        os.path.relpath(
            script_root / (f"{name}.exe" if os.name == "nt" else name),
            site,
        ).replace(os.sep, "/")
        for name in scripts
    }
    observed_names = {
        name for name, (path, _digest, _size) in entries.items() if _within(path, script_root)
    }
    if observed_names != expected_names:
        _fail("Installed console-script inventory differs from entry-point metadata.")
    for name, target in scripts.items():
        record_name = next(
            candidate
            for candidate in entries
            if entries[candidate][0]
            == (script_root / (f"{name}.exe" if os.name == "nt" else name)).resolve()
        )
        path = entries[record_name][0]
        payload = _read_bounded(path)
        if os.name == "nt":
            if not payload.startswith(b"MZ"):
                _fail("Installed Windows console-script launcher is malformed.")
            continue
        module, separator, function = target.partition(":")
        if not separator:
            _fail("Bound console-script target is malformed.")
        expected_body = (
            "# -*- coding: utf-8 -*-\n"
            "import sys\n"
            f"from {module} import {function}\n"
            'if __name__ == "__main__":\n'
            '    if sys.argv[0].endswith("-script.pyw"):\n'
            "        sys.argv[0] = sys.argv[0][:-11]\n"
            '    elif sys.argv[0].endswith(".exe"):\n'
            "        sys.argv[0] = sys.argv[0][:-4]\n"
            f"    sys.exit({function}())\n"
        ).encode()
        first_line, separator_bytes, body = payload.partition(b"\n")
        direct_wrapper = first_line == f"#!{env_root / 'bin/python'}".encode()
        shell_prefix = (
            "#!/bin/sh\n"
            f"'''exec' {shlex.quote(str(env_root / 'bin/python'))} \"$0\" \"$@\"\n"
            "' '''\n"
        ).encode()
        shell_wrapper = (
            payload.startswith(shell_prefix) and payload[len(shell_prefix) :] == expected_body
        )
        if not separator_bytes or not ((direct_wrapper and body == expected_body) or shell_wrapper):
            _fail("Installed console-script wrapper differs from its authenticated entry point.")
    return None


def _windows_startup_inventory(site: Path) -> tuple[tuple[int, int, int], tuple[str, ...]]:
    windows_authority.reject_path_redirection(site)
    before = site.lstat()
    if not stat.S_ISDIR(before.st_mode):
        _fail("Windows site startup root is not a directory.")
    identity = (before.st_dev, before.st_ino, before.st_mode)
    names: list[str] = []
    for count, entry in enumerate(site.iterdir(), 1):
        if count > 20_000:
            _fail("Windows site inventory exceeds its startup-inspection bound.")
        name = entry.name.lower()
        if name.endswith(".pth") or name.split(".")[0] in {"sitecustomize", "usercustomize"}:
            _fail("Windows selected environment contains an executable site startup hook.")
        names.append(entry.name)
    windows_authority.reject_path_redirection(site)
    after = site.lstat()
    if (after.st_dev, after.st_ino, after.st_mode) != identity:
        _fail("Windows site startup root identity changed during inspection.")
    return identity, tuple(sorted(names))


def _windows_startup_config(config: Path) -> tuple[tuple[int, int, int, int, int], str]:
    identity = windows_authority.authority_file_identity(config)
    raw = windows_authority.read_authority_file(config, limit=65_536)
    fields: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = (part.strip().lower() for part in line.split("=", 1))
        if key in fields:
            _fail("Windows selected environment has duplicate configuration keys.")
        fields[key] = value
    if fields.get("include-system-site-packages") != "false":
        _fail("Windows selected environment permits unqualified system site packages.")
    if windows_authority.authority_file_identity(config) != identity:
        _fail("Windows startup configuration identity changed during inspection.")
    return identity, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class _WindowsStartupState:
    config: Path
    site: Path
    config_identity: tuple[int, int, int, int, int]
    config_sha256: str
    site_identity: tuple[int, int, int]
    site_inventory: tuple[str, ...]

    def revalidate(self) -> None:
        if _windows_startup_config(self.config) != (self.config_identity, self.config_sha256):
            _fail("Windows startup configuration changed during verification.")
        if _windows_startup_inventory(self.site) != (self.site_identity, self.site_inventory):
            _fail("Windows site startup inventory changed during verification.")


def _capture_windows_startup(env_root: Path) -> _WindowsStartupState:
    config, site = env_root / "pyvenv.cfg", env_root / "Lib/site-packages"
    config_identity, config_sha256 = _windows_startup_config(config)
    site_identity, site_inventory = _windows_startup_inventory(site)
    return _WindowsStartupState(
        config, site, config_identity, config_sha256, site_identity, site_inventory
    )


@dataclass(frozen=True, slots=True)
class _WindowsInstallationContext:
    descriptor: windows_authority.WindowsInstallationDescriptor
    template: bytes
    inputs: tuple[tuple[Path, str, int, int | None], ...]
    startup: _WindowsStartupState | None = None
    identities: tuple[tuple[int, int, int, int, int], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identities",
            tuple(windows_authority.authority_file_identity(path) for path, _, _, _ in self.inputs),
        )

    def revalidate(self) -> None:
        if self.startup is not None:
            self.startup.revalidate()
        for (path, digest, limit, size), identity in zip(self.inputs, self.identities, strict=True):
            if windows_authority.authority_file_identity(path) != identity:
                _fail("Windows independent installation input identity changed.")
            if (
                windows_authority.hash_authority_file(path, limit=limit, expected_size=size)
                != digest
            ):
                _fail("Windows independent installation input changed during verification.")
            if windows_authority.authority_file_identity(path) != identity:
                _fail("Windows independent installation input identity changed during reading.")

    def observe_launchers(
        self,
        entries: dict[str, tuple[Path, str, str]],
        site: Path,
        env_root: Path,
        scripts: dict[str, str],
    ) -> windows_authority.WindowsLauncherProof:
        descriptor = self.descriptor
        if scripts != dict(windows_authority.SCRIPT_PAIRS):
            _fail("Windows console-script metadata differs from the independent recipe.")
        script_root = env_root / "Scripts"
        windows_authority.reject_path_redirection(script_root)
        expected_names = {
            os.path.relpath(script_root / f"{name}.exe", site).replace(os.sep, "/")
            for name, _ in windows_authority.SCRIPT_PAIRS
        }
        observed_names = {
            name for name, (path, _, _) in entries.items() if _within(path, script_root)
        }
        if observed_names != expected_names:
            _fail("Windows installed console-script inventory differs from independent authority.")
        proofs: list[windows_authority.LauncherIdentity] = []
        for script in descriptor.scripts:
            path = script_root / f"{script.name}.exe"
            raw = windows_authority.read_authority_file(
                path, limit=windows_authority.LAUNCHER_LIMIT
            )
            payload = windows_authority.console_script_payload(
                script.name, script.target, interpreter_display_path=descriptor.interpreter_path
            )
            expected = expected_windows_console_launcher(
                self.template, descriptor.interpreter_path, payload
            )
            verify_windows_console_launcher(
                raw, self.template, descriptor.interpreter_path, payload
            )
            proofs.append(
                windows_authority.LauncherIdentity(
                    script.name,
                    script.target,
                    script.payload_sha256,
                    len(expected),
                    hashlib.sha256(expected).hexdigest(),
                )
            )
        return windows_authority.WindowsLauncherProof.from_dict(
            {
                "schema_version": 1,
                "profile": windows_authority.PROFILE,
                "descriptor_sha256": descriptor.descriptor_sha256,
                "installation_evidence_sha256": descriptor.installation_evidence_sha256,
                "installer": asdict(descriptor.installer),
                "template": asdict(descriptor.template),
                "recipe_sha256": descriptor.recipe_sha256,
                "interpreter": asdict(descriptor.interpreter),
                "scripts": [asdict(proof) for proof in proofs],
            }
        )


def _windows_inputs(
    python: Path,
    binding: BundleBinding,
    source_root: Path,
    kind: Literal["wheel", "sdist"],
    descriptor_path: Path,
    descriptor_sha256: str,
    template_path: Path,
    installer: Path,
) -> _WindowsInstallationContext:
    descriptor = windows_authority.load_windows_installation_descriptor(
        descriptor_path, expected_sha256=descriptor_sha256
    )
    descriptor.verify_binding(binding, kind)
    # Schema v1 cannot bind every executable/DLL ._pth lookup location; refuse rather than guess.
    if descriptor.schema_version == 1:
        _fail(
            "Windows installed-package qualification is NO-GO: "
            "independent executable/DLL startup authority is unavailable."
        )
    if (
        windows_authority.canonical_windows_interpreter_path(str(python.absolute()))
        != descriptor.interpreter_path
    ):
        _fail("Selected Windows interpreter differs from its independent display path.")
    recipe = source_root / "scripts/release_qualification/windows_installation.py"
    inputs = (
        (descriptor_path, descriptor_sha256, windows_authority.JSON_LIMIT, None),
        (recipe, descriptor.recipe_sha256, windows_authority.RECIPE_LIMIT, None),
        (
            python,
            descriptor.interpreter.executable_sha256,
            windows_authority.EXECUTABLE_LIMIT,
            None,
        ),
        (
            installer,
            descriptor.installer.executable_sha256,
            windows_authority.EXECUTABLE_LIMIT,
            windows_authority.INSTALLER_SIZE,
        ),
        (
            template_path,
            descriptor.template.sha256,
            descriptor.template.size,
            descriptor.template.size,
        ),
    )
    template = windows_authority.read_authority_file(
        template_path, limit=descriptor.template.size, expected_size=descriptor.template.size
    )
    # Normal site startup is needed for CPython 3.12 venv identity. Reject
    # hooks and retain the execution-affecting state for every later launch.
    startup = _capture_windows_startup(python.absolute().parent.parent)
    context = _WindowsInstallationContext(descriptor, template, inputs, startup=startup)
    context.revalidate()
    return context


def _run_bounded(
    argv: list[str], *, cwd: Path, timeout: int, output_limit: int = _MAX_PROBE_BYTES
) -> tuple[int, bytes, bytes]:
    """Run child with bounded pipe collection and terminate its process group on overflow."""
    if (
        not argv
        or isinstance(timeout, bool)
        or not math.isfinite(timeout)
        or timeout <= 0
        or timeout > _MAX_TCK_SECONDS
        or output_limit <= 0
    ):
        _fail("Isolated subprocess parameters are invalid.")
    collected: list[bytearray] = [bytearray(), bytearray()]
    overflow = threading.Event()
    reader_failed = threading.Event()
    reader_errors: list[BaseException] = []
    windows_readers: list[process_module.WindowsPipeReader] = []
    readers: list[threading.Thread] = []
    succeeded = False
    primary_error: BaseException | None = None
    result: tuple[int, bytes, bytes] | None = None
    cleanup_errors: list[BaseException] = []
    job_active_processes: object | None = None
    deadline = time.monotonic() + timeout
    try:
        owned = process_module.start_process(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            windows=os.name == "nt",
            windows_gate_code=(process_module.WINDOWS_GATE_CODE if os.name == "nt" else None),
            bufsize=0 if os.name == "nt" else -1,
        )
    except OSError as error:
        raise ValueError("Isolated interpreter subprocess could not be started.") from error
    process = owned.process
    if os.name == "nt":
        job_active_processes = getattr(getattr(owned, "job", None), "active_processes", None)
    try:
        assert process.stdout is not None and process.stderr is not None
        if os.name == "nt":
            for stream in (process.stdout, process.stderr):
                windows_readers.append(process_module.WindowsPipeReader(stream, limit=output_limit))
            for reader in windows_readers:
                reader.start()
            for reader in windows_readers:
                if not reader.wait_ready(max(0.0, deadline - time.monotonic())):
                    _fail("Isolated subprocess output readers did not become ready.")
            for reader in windows_readers:
                reader.release()
        else:

            def drain(stream: object, target: bytearray) -> None:
                try:
                    while chunk := stream.read(64 * 1024):  # type: ignore[attr-defined]
                        remaining = output_limit + 1 - len(target)
                        if remaining > 0:
                            target.extend(chunk[:remaining])
                        if len(chunk) > remaining or len(target) > output_limit:
                            overflow.set()
                except BaseException as error:
                    reader_errors.append(error)
                    reader_failed.set()

            readers.append(
                threading.Thread(target=drain, args=(process.stdout, collected[0]), daemon=True)
            )
            readers.append(
                threading.Thread(target=drain, args=(process.stderr, collected[1]), daemon=True)
            )
            for posix_reader in readers:
                posix_reader.start()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _fail("Isolated subprocess exceeded its time limit.")
            try:
                returncode = process.wait(timeout=min(remaining, 0.05))
                break
            except subprocess.TimeoutExpired:
                if reader_failed.is_set():
                    _fail("Isolated subprocess output reader failed.")
                if any(reader.failed.is_set() or reader.errors for reader in windows_readers):
                    _fail("Isolated subprocess output reader failed.")
                if overflow.is_set() or any(reader.overflowed for reader in windows_readers):
                    _fail("Isolated subprocess exceeded the output bound.")
        if os.name == "nt":
            if callable(job_active_processes):
                if job_active_processes():
                    for reader in windows_readers:
                        reader.stop.set()
                    owned.require_empty()
                    _fail("Windows qualification Job Object retained active processes.")
            else:
                owned.require_empty()
            for reader in windows_readers:
                if callable(job_active_processes):
                    while not reader.wait(0):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            _fail("Isolated subprocess output reader did not terminate.")
                        if reader.wait(min(0.05, remaining)):
                            break
                        if job_active_processes():
                            for active_reader in windows_readers:
                                active_reader.stop.set()
                            owned.require_empty()
                            _fail("Windows qualification Job Object retained active processes.")
                elif not reader.wait(max(0.0, deadline - time.monotonic())):
                    _fail("Isolated subprocess output reader did not terminate.")
                if reader.errors:
                    _fail("Isolated subprocess output reader failed.")
                if reader.overflowed:
                    _fail("Isolated subprocess exceeded the output bound.")
            for reader in windows_readers:
                if callable(job_active_processes):
                    reader.stop.set()
                else:
                    stop = getattr(reader, "stop", None)
                    if stop is not None:
                        stop.set()
            if callable(job_active_processes):
                if job_active_processes():
                    owned.require_empty()
                    _fail("Windows qualification Job Object retained active processes.")
                owned.require_empty()
            collected = [reader.data[:output_limit] for reader in windows_readers]
        else:
            if owned.group_exists():
                owned.terminate(grace_seconds=0, immediate=True)
                _fail("Isolated subprocess left an output-producing descendant alive.")
            reader_deadline = time.monotonic() + process_module.TERMINATION_WAIT_SECONDS
            for posix_reader in readers:
                posix_reader.join(
                    timeout=max(0.0, min(deadline, reader_deadline) - time.monotonic())
                )
                if posix_reader.is_alive():
                    _fail("Isolated subprocess output reader did not terminate.")
            if reader_errors:
                _fail("Isolated subprocess output reader failed.")
        if overflow.is_set():
            _fail("Isolated subprocess exceeded the output bound.")
        result = (returncode, bytes(collected[0]), bytes(collected[1]))
        succeeded = True
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if not succeeded:
            if os.name == "nt":
                for reader in windows_readers:
                    try:
                        if callable(job_active_processes):
                            reader.stop.set()
                        else:
                            stop = getattr(reader, "stop", None)
                            if stop is not None:
                                stop.set()
                    except BaseException as error:
                        cleanup_errors.append(error)
            try:
                owned.terminate(grace_seconds=0, immediate=True)
            except BaseException as error:
                cleanup_errors.append(error)
        if os.name == "nt":
            cleanup_deadline = time.monotonic() + process_module._READER_CLEANUP_SECONDS
            for reader in windows_readers:
                if process_module._WINDOWS_OBSERVER_POISONED:
                    if not any(
                        stream is reader.stream and thread is reader.thread
                        for stream, thread, _handle in process_module._POISONED_READER_RESOURCES
                    ):
                        process_module._POISONED_READER_RESOURCES.append(
                            (reader.stream, reader.thread, reader.thread_handle)
                        )
                    continue
                try:
                    if reader.thread.ident is None:
                        reader.close_stream()
                    else:
                        reader.cancel_and_join(deadline=cleanup_deadline)
                except BaseException as error:
                    cleanup_errors.append(error)
            windows_cleanup_streams: tuple[IO[bytes] | None, IO[bytes] | None] = (
                process.stdout,
                process.stderr,
            )
            for windows_cleanup_stream in windows_cleanup_streams:
                if windows_cleanup_stream is not None and not any(
                    windows_cleanup_stream is reader.stream for reader in windows_readers
                ):
                    try:
                        windows_cleanup_stream.close()
                    except BaseException as error:
                        cleanup_errors.append(error)
            try:
                owned.reap_and_dispose_handle(timeout=process_module.TERMINATION_WAIT_SECONDS)
            except BaseException as error:
                cleanup_errors.append(error)
            try:
                owned.close()
            except BaseException as error:
                cleanup_errors.append(error)
        else:
            cleanup_deadline = time.monotonic() + process_module.TERMINATION_WAIT_SECONDS
            for posix_reader in readers:
                try:
                    if posix_reader.ident is not None and posix_reader.is_alive():
                        owned.terminate(grace_seconds=0, immediate=True)
                        posix_reader.join(timeout=max(0.0, cleanup_deadline - time.monotonic()))
                    if posix_reader.is_alive():
                        raise ValueError("Isolated subprocess output reader did not stop.")
                except BaseException as error:
                    cleanup_errors.append(error)
            if any(posix_reader.is_alive() for posix_reader in readers):
                cleanup_errors.append(
                    ValueError("Isolated subprocess output reader remains live; pipes stay owned.")
                )
            else:
                for posix_cleanup_stream in (process.stdout, process.stderr):
                    try:
                        cast(IO[bytes], posix_cleanup_stream).close()
                    except BaseException as error:
                        cleanup_errors.append(error)
            try:
                owned.reap_and_dispose_handle(timeout=process_module.TERMINATION_WAIT_SECONDS)
            except BaseException as error:
                cleanup_errors.append(error)
        if cleanup_errors:
            if primary_error is not None:
                for cleanup_error in cleanup_errors:
                    primary_error.add_note(
                        f"Subprocess cleanup also failed: {type(cleanup_error).__name__}."
                    )
            else:
                raise ValueError("Isolated subprocess cleanup failed.") from cleanup_errors[0]
    assert result is not None
    return result


def _selected_environment(python: Path) -> tuple[Path, Path, str, str, str]:
    code = (
        "import json, platform, sys\n"
        "print(json.dumps({'python': platform.python_version(), "
        "'os': platform.system().lower(), 'machine': platform.machine().lower(), "
        "'implementation': platform.python_implementation(), 'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix}))\n"
    )
    code_result, stdout, _stderr = _run_bounded(
        [str(python), "-I", *([] if _IS_WINDOWS else ["-S"]), "-c", code],
        cwd=python.parent,
        timeout=_MAX_TCK_SECONDS,
    )
    if code_result != 0:
        _fail("Selected interpreter environment could not be resolved.")
    try:
        result = json.loads(stdout)
        version, operating_system, architecture = result["python"], result["os"], result["machine"]
        if _IS_WINDOWS and (
            result.get("implementation") != "CPython"
            or operating_system != "windows"
            or architecture not in {"amd64", "x86_64"}
        ):
            _fail("Windows interpreter implementation or native architecture is unsupported.")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        raise ValueError("Selected interpreter environment response is malformed.") from error
    if not all(
        isinstance(item, str) and item for item in (version, operating_system, architecture)
    ):
        _fail("Selected interpreter identity is malformed.")
    environment_root = python.parent.parent.resolve(strict=True)
    if _IS_WINDOWS and (
        not isinstance(result.get("prefix"), str)
        or Path(result["prefix"]).resolve(strict=True) != environment_root
        or result.get("prefix") == result.get("base_prefix")
    ):
        _fail("Windows selected interpreter is not using its bound virtual environment.")
    config = environment_root / "pyvenv.cfg"
    if config.is_symlink() or not config.is_file():
        _fail("Selected interpreter is not inside a virtual environment.")
    major_minor = ".".join(version.split(".")[:2])
    candidates = (
        [environment_root / "Lib" / "site-packages"]
        if os.name == "nt"
        else [environment_root / "lib" / f"python{major_minor}" / "site-packages"]
    )
    purelib = next((candidate for candidate in candidates if candidate.is_dir()), None)
    if purelib is None or purelib.is_symlink() or not _within(purelib.resolve(), environment_root):
        _fail("Selected interpreter is not inside an isolated virtual environment.")
    return environment_root, purelib.resolve(strict=True), version, operating_system, architecture


def _scope_files(root: Path, *, label: str) -> set[str]:
    if not root.exists():
        return set()
    if root.is_symlink() or not root.is_dir():
        _fail(f"Installed {label} root is not a regular directory.")
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            _fail(f"Installed {label} contains a source checkout or environment symlink.")
        if path.is_file():
            if label in {"package", "frontend"} and path.suffix.lower() in {".pyc", ".pyo"}:
                _fail("Installed distribution contains generated bytecode.")
            files.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            _fail(f"Installed {label} contains a special file.")
    return files


def _verify_inventory(
    site: Path,
    env_root: Path,
    source_root: Path,
    dist_info: Path,
    expected_payload: dict[str, Path],
    archive_payload: dict[str, tuple[int, str]],
    archive_metadata: dict[str, bytes],
    kind: Literal["wheel", "sdist"],
    record_entries: dict[str, tuple[Path, str, str]],
    *,
    windows_context: _WindowsInstallationContext | None = None,
) -> tuple[str, str, BuildGenerator, windows_authority.WindowsLauncherProof | None]:
    src_root = site / "src"
    frontend_root = site / "frontend"
    actual_payload = (
        {f"src/{name}" for name in _scope_files(src_root, label="package")}
        | {f"frontend/{name}" for name in _scope_files(frontend_root, label="frontend")}
        | {
            f"matryca_plumber/{name}"
            for name in _scope_files(site / "matryca_plumber", label="package")
        }
    )
    bundle_module._gateway_source_files({name: "" for name in actual_payload})
    bundle_module._gateway_source_files(
        {name: digest for name, (_, digest) in archive_payload.items()}
    )
    expected_names = {
        name
        for name in archive_payload
        if name.startswith(("src/", "frontend/", "matryca_plumber/"))
    }
    if actual_payload != expected_names:
        missing = expected_names - actual_payload
        if missing and any(name.startswith("frontend/dist/") for name in missing):
            _fail("Installed frontend file is missing.")
        if missing:
            _fail(f"Installed TCK/module is missing: {sorted(missing)[0]}.")
        _fail("Installed distribution contains an unlisted payload file.")

    actual_dist_info = _scope_files(dist_info, label="distribution metadata")
    dist_info_prefix = dist_info.relative_to(site).as_posix() + "/"
    authenticated_metadata = {
        name.removeprefix(dist_info_prefix)
        for name in archive_payload
        if name.startswith(dist_info_prefix)
    }
    generated_by_sdist = (
        {"WHEEL", "entry_points.txt", "top_level.txt"} if kind == "sdist" else set()
    )
    expected_dist_info = authenticated_metadata | generated_by_sdist | {"RECORD"}
    if (
        actual_dist_info - expected_dist_info - _INSTALLER_METADATA
        or expected_dist_info - actual_dist_info
    ):
        _fail("Installed distribution metadata inventory is incomplete or unexpected.")
    scripts, build_generator = _verify_generated_metadata(
        dist_info, source_root, archive_payload, kind
    )

    record_name = (dist_info / "RECORD").relative_to(site).as_posix()
    script_root = env_root / ("Scripts" if os.name == "nt" else "bin")
    script_names = {
        os.path.relpath(script_root / (f"{name}.exe" if os.name == "nt" else name), site).replace(
            os.sep, "/"
        )
        for name in scripts
    }
    total_recorded_bytes = 0
    for name, entry in record_entries.items():
        if not (
            name in expected_names or name.startswith(dist_info_prefix) or name in script_names
        ):
            _fail(f"Installed distribution RECORD contains an unowned path: {name}.")
        size = entry[0].stat().st_size
        total_recorded_bytes += size
        if size > _MAX_INSTALLED_FILE_BYTES or total_recorded_bytes > _MAX_INSTALLED_TOTAL_BYTES:
            _fail("Installed distribution RECORD paths exceed the total size limit.")
    windows_proof = _verify_entry_point_scripts(
        record_entries, site, env_root, scripts, windows_context=windows_context
    )
    for name, entry in record_entries.items():
        _verify_record_entry(name, entry, record_name)
    listed = set(record_entries)
    payload_record_names = expected_names | {
        path.relative_to(site).as_posix() for path in dist_info.rglob("*") if path.is_file()
    }
    missing_rows = payload_record_names - listed
    if missing_rows:
        _fail("Installed distribution payload is absent from RECORD.")

    total = 0
    for name, (expected_size, expected_digest) in archive_payload.items():
        if name.endswith("/RECORD") or name.endswith(".dist-info/RECORD"):
            continue
        archive_record_entry = record_entries.get(name)
        if archive_record_entry is None:
            raise ValueError("Authenticated archive payload is absent from RECORD.")
        payload = _read_bounded(archive_record_entry[0])
        total += len(payload)
        if total > _MAX_INSTALLED_TOTAL_BYTES:
            _fail("Installed distribution total size exceeds the limit.")
        if len(payload) != expected_size or hashlib.sha256(payload).hexdigest() != expected_digest:
            if "/contract_artifacts/" in name:
                _fail("Installed contract resource differs from authenticated archive inventory.")
            _fail("Installed distribution payload differs from authenticated archive inventory.")

    for name, source_path in expected_payload.items():
        archive_entry = archive_payload.get(name)
        if archive_entry is None:
            _fail("Authenticated archive is missing a tracked package payload.")
        if source_path.is_symlink():
            _fail("Selected source payload must not be a symlink.")
        try:
            source_resolved = source_path.resolve(strict=True)
            source_bytes = _read_bounded(source_resolved)
        except OSError as error:
            raise ValueError("Selected source payload is missing.") from error
        if not _within(source_resolved, source_root):
            _fail("Selected source payload escapes its bound checkout.")
        if (
            len(source_bytes) != archive_entry[0]
            or hashlib.sha256(source_bytes).hexdigest() != archive_entry[1]
        ):
            _fail("Authenticated archive payload differs from the bound source checkout.")

    for name, payload in archive_metadata.items():
        target = dist_info / name
        if target.is_symlink() or not target.is_file() or _read_bounded(target) != payload:
            _fail("Installed distribution metadata differs from authenticated archive metadata.")

    inventory = "\n".join(
        f"{name},{entry[1]},{entry[2]}" for name, entry in sorted(record_entries.items())
    ).encode()
    resource_rows = []
    for member in _RESOURCE_FILES:
        if member.startswith("src/contract_artifacts/contracts/"):
            installed_name = member.removeprefix("src/contract_artifacts/")
            source_name = installed_name
        else:
            installed_name = f"tck/{PurePosixPath(member).name}"
            source_name = f"scripts/{PurePosixPath(member).name}"
        installed_path = site / "src/contract_artifacts" / installed_name
        resource_rows.append(
            f"{source_name}:{hashlib.sha256(installed_path.read_bytes()).hexdigest()}"
        )
    return (
        hashlib.sha256(inventory).hexdigest(),
        hashlib.sha256("\n".join(resource_rows).encode()).hexdigest(),
        build_generator,
        windows_proof,
    )


def _isolated_probe(
    python: Path, env_root: Path, site: Path, source_root: Path
) -> tuple[Path, Path, str, str, str, str, tuple[tuple[str, str], ...]]:
    namespace_root = site / "matryca_plumber"
    if namespace_root.is_symlink():
        _fail("Installed gateway namespace provenance must not be a symlink.")
    has_gateway = namespace_root.exists()
    code = (
        "import importlib.metadata, json, platform, sys, sysconfig\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import src, frontend\n"
        "gateway = {}\n"
        "if sys.argv[2] == 'gateway':\n"
        "    import matryca_plumber, matryca_plumber.graph_gateway\n"
        "    for name, module in (('matryca_plumber', matryca_plumber), "
        "('matryca_plumber.graph_gateway', matryca_plumber.graph_gateway)):\n"
        "        gateway[name] = {'file': getattr(module, '__file__', None), "
        "'spec': getattr(getattr(module, '__spec__', None), 'origin', None)}\n"
        "dists = sorted((d.metadata.get('Name', ''), d.version) "
        "for d in importlib.metadata.distributions())\n"
        "print(json.dumps({'src': src.__file__, 'frontend': frontend.__file__, "
        "'purelib': sysconfig.get_paths()['purelib'], 'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix, 'python': platform.python_version(), "
        "'os': platform.system().lower(), 'machine': platform.machine().lower(), "
        "'deps': dists, 'gateway': gateway}))\n"
    )
    with tempfile.TemporaryDirectory(prefix="matryca-installed-probe-") as cache_prefix:
        returncode, stdout, _stderr = _run_bounded(
            [
                str(python),
                "-I",
                *([] if _IS_WINDOWS else ["-S"]),
                "-X",
                f"pycache_prefix={cache_prefix}",
                "-c",
                code,
                str(site),
                "gateway" if has_gateway else "historical",
            ],
            cwd=env_root,
            timeout=_MAX_TCK_SECONDS,
        )
    if returncode:
        _fail("Isolated interpreter provenance probe failed or exceeded output bounds.")
    try:
        result = json.loads(stdout)
        src_origin = Path(result["src"]).resolve(strict=True)
        frontend_origin = Path(result["frontend"]).resolve(strict=True)
        purelib = site.resolve(strict=True)
        python_version = result["python"]
        operating_system = result["os"]
        architecture = result["machine"]
        raw_dependencies = result["deps"]
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        raise ValueError("Isolated interpreter provenance response is malformed.") from error
    if not all(
        isinstance(value, str) and value
        for value in (python_version, operating_system, architecture)
    ) or not isinstance(raw_dependencies, list):
        _fail("Isolated interpreter provenance response is malformed.")
    if any(_within(origin, source_root) for origin in (src_origin, frontend_origin)):
        _fail("Installed import provenance resolves to the source checkout.")
    if (
        purelib.parent == purelib
        or not _within(purelib, env_root)
        or not _within(src_origin, purelib)
        or not _within(frontend_origin, purelib)
    ):
        _fail("Installed import provenance does not resolve from this isolated environment.")
    if has_gateway:
        origins = result.get("gateway")
        expected_origins = {
            "matryca_plumber": purelib / "matryca_plumber/__init__.py",
            "matryca_plumber.graph_gateway": purelib / "matryca_plumber/graph_gateway/__init__.py",
        }
        if not isinstance(origins, dict) or set(origins) != set(expected_origins):
            _fail("Installed gateway namespace provenance is missing or unexpected.")
        for name, expected_origin in expected_origins.items():
            value = origins[name]
            if (
                not isinstance(value, dict)
                or set(value) != {"file", "spec"}
                or not all(isinstance(part, str) and part for part in value.values())
            ):
                _fail("Installed gateway namespace provenance is malformed.")
            try:
                file_origin = Path(value["file"]).resolve(strict=True)
                spec_origin = Path(value["spec"]).resolve(strict=True)
                expected_origin = expected_origin.resolve(strict=True)
            except (OSError, TypeError, ValueError) as error:
                raise ValueError("Installed gateway namespace provenance is malformed.") from error
            if file_origin != expected_origin or spec_origin != expected_origin:
                _fail("Installed gateway namespace provenance differs from its authenticated file.")
            if not _within(file_origin, purelib) or _within(file_origin, source_root):
                _fail("Installed gateway namespace provenance escapes its authenticated site.")
    dependency_pairs: list[tuple[str, str]] = []
    for item in raw_dependencies:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(part, str) and part for part in item)
        ):
            _fail("Installed dependency metadata contains an invalid name or version.")
        raw_name, version = item
        name = re.sub(r"[-_.]+", "-", raw_name).lower()
        if name in {"matryca-plumber", "pip"}:
            continue
        if (
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,198}[a-z0-9])?", name) is None
            or len(version) > 128
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", version) is None
        ):
            _fail("Installed dependency metadata contains an invalid name or version.")
        dependency_pairs.append((name, version))
    canonical_dependencies = tuple(sorted(dependency_pairs))
    if len({name for name, _version in canonical_dependencies}) != len(canonical_dependencies):
        _fail("Installed dependency metadata contains duplicate distributions.")
    if len(canonical_dependencies) > 4096:
        _fail("Installed dependency metadata contains too many distributions.")
    return (
        purelib,
        src_origin,
        hashlib.sha256(
            json.dumps(canonical_dependencies, separators=(",", ":")).encode()
        ).hexdigest(),
        python_version,
        operating_system,
        architecture,
        canonical_dependencies,
    )


def _run_tcks(
    python: Path,
    site: Path,
    source_root: Path,
    *,
    windows_context: _WindowsInstallationContext | None = None,
) -> tuple[str, str, str]:
    outcomes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="matryca-installed-tck-") as working_name:
        working = Path(working_name)
        for source_name, expected_id in _TCKS.items():
            installed = site / "src/contract_artifacts/tck" / Path(source_name).name
            code = (
                "import runpy, sys\n"
                "site, script = sys.argv[1], sys.argv[2]\n"
                "sys.path.insert(0, site)\n"
                "sys.argv = [script]\n"
                "runpy.run_path(script, run_name='__main__')\n"
            )
            with tempfile.TemporaryDirectory(
                prefix="matryca-tck-pycache-", dir=working
            ) as cache_prefix:
                if windows_context is not None:
                    windows_context.revalidate()
                returncode, stdout, _stderr = _run_bounded(
                    [
                        str(python),
                        "-I",
                        "-S",
                        "-X",
                        f"pycache_prefix={cache_prefix}",
                        "-c",
                        code,
                        str(site),
                        str(installed),
                    ],
                    cwd=working,
                    timeout=_MAX_TCK_SECONDS,
                )
                if windows_context is not None:
                    windows_context.revalidate()
            if returncode != 0:
                _fail("Installed TCK failed or exceeded output bounds.")
            try:
                receipt = json.loads(stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("Installed TCK did not emit a valid JSON receipt.") from error
            if not isinstance(receipt, dict) or receipt.get("contract_id") != expected_id:
                _fail("Installed TCK receipt does not match its expected contract.")
            outcomes.append("PASS")
    if len(outcomes) != 3:
        _fail("Installed TCK selection is incomplete.")
    return (outcomes[0], outcomes[1], outcomes[2])


def verify_installed(
    python: Path,
    binding: BundleBinding,
    source_root: Path,
    kind: Literal["wheel", "sdist"],
    *,
    artifact: Path,
    policy: str = "rc4",
    windows_installation_descriptor: Path | None = None,
    expected_windows_installation_sha256: str | None = None,
    windows_template: Path | None = None,
    installer: Path | None = None,
) -> InstalledReceipt:
    """Verify installed files, import origin, resources, RECORD, and static TCKs."""
    if kind not in {"wheel", "sdist"}:
        _fail("Installed distribution kind must be wheel or sdist.")
    inputs = (
        windows_installation_descriptor,
        expected_windows_installation_sha256,
        windows_template,
        installer,
    )
    if _IS_WINDOWS and any(value is None for value in inputs):
        _fail(
            "Windows installed-package qualification is NO-GO without all "
            "independent authority inputs."
        )
    if not _IS_WINDOWS and any(value is not None for value in inputs):
        _fail("Windows installation inputs are invalid on a non-Windows verifier.")
    archive_payload, archive_metadata = _authenticated_archive(
        artifact, binding, kind, policy=policy
    )
    _safe_root(source_root, "Source root")
    interpreter = python.absolute()
    if not interpreter.is_file():
        _fail("Selected interpreter does not exist or is not a file.")
    tracked = _verify_source(source_root, binding)
    windows_context = None
    if _IS_WINDOWS:
        assert (
            windows_installation_descriptor is not None
            and expected_windows_installation_sha256 is not None
            and windows_template is not None
            and installer is not None
        )
        if "scripts/release_qualification/windows_installation.py" not in tracked:
            _fail("Windows payload recipe is not bound by the selected source tree.")
        windows_context = _windows_inputs(
            interpreter,
            binding,
            source_root,
            kind,
            windows_installation_descriptor,
            expected_windows_installation_sha256,
            windows_template,
            installer,
        )
    expected_payload = _payload_map(source_root, tracked)
    source_root = source_root.resolve(strict=True)
    if windows_context is not None:
        windows_context.revalidate()
    probe_env_root, site, selected_python_version, _operating_system, _architecture = (
        _selected_environment(interpreter)
    )
    if (
        windows_context is not None
        and selected_python_version != windows_context.descriptor.interpreter.version
    ):
        _fail("Windows interpreter version differs from its independent identity.")
    dist_info, version = _distribution(site, binding.version)
    record = dist_info / "RECORD"
    record_entries = _parse_record(record, site, probe_env_root)
    launcher_identities = {
        path: windows_authority.authority_file_identity(path)
        for path, _, _ in record_entries.values()
        if windows_context is not None and _within(path, probe_env_root / "Scripts")
    }
    record_sha256, resource_sha256, build_generator, windows_proof = _verify_inventory(
        site,
        probe_env_root,
        source_root,
        dist_info,
        expected_payload,
        archive_payload,
        archive_metadata,
        kind,
        record_entries,
        windows_context=windows_context,
    )
    if windows_context is not None:
        windows_context.revalidate()
    (
        site,
        _origin,
        dependency_sha256,
        python_version,
        operating_system,
        architecture,
        dependencies,
    ) = _isolated_probe(interpreter, probe_env_root, site, source_root)
    if windows_context is None:
        tck_outcomes = _run_tcks(interpreter, site, source_root)
    else:
        windows_context.revalidate()
        tck_outcomes = _run_tcks(interpreter, site, source_root, windows_context=windows_context)
    if windows_context is not None:
        if (
            python_version != windows_context.descriptor.interpreter.version
            or operating_system != "windows"
            or architecture not in {"amd64", "x86_64"}
        ):
            _fail("Windows installed observation differs from its independent interpreter profile.")
        windows_context.revalidate()
        if any(
            windows_authority.authority_file_identity(path) != identity
            for path, identity in launcher_identities.items()
        ):
            _fail("Windows installed launcher identity changed during qualification.")
        final_proof = _verify_entry_point_scripts(
            record_entries,
            site,
            probe_env_root,
            _expected_scripts(source_root),
            windows_context=windows_context,
        )
        if windows_proof != final_proof:
            _fail("Windows launchers changed during installed qualification.")
    return InstalledReceipt(
        kind=kind,
        operating_system=operating_system,
        architecture=architecture,
        python_version=python_version,
        version=version,
        location_class="isolated-venv-site-packages",
        record_sha256=record_sha256,
        resource_sha256=resource_sha256,
        dependency_sha256=dependency_sha256,
        dependencies=dependencies,
        build_generator=build_generator,
        tck_outcomes=tck_outcomes,
        windows_launcher=windows_proof,
    )
