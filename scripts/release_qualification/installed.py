"""Verify a release distribution after isolated installation."""

from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import importlib.metadata
import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
import threading
import time
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, NoReturn
from urllib.parse import urlparse

from scripts.build_release_artifacts import _PUBLIC_CONTRACT_RESOURCE_MEMBERS
from scripts.release_qualification import bundle as bundle_module
from scripts.release_qualification.bundle import BundleBinding

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

    def to_dict(self) -> dict[str, object]:
        """Return stable JSON-compatible receipt data without local paths."""
        value = asdict(self)
        value["dependencies"] = [
            {"name": name, "version": version} for name, version in self.dependencies
        ]
        value["build_generator"] = asdict(self.build_generator)
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
    expected: dict[str, Path] = {}
    for name in tracked:
        if name.startswith("src/") and name.endswith(".py"):
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
    artifact: Path, binding: BundleBinding, kind: Literal["wheel", "sdist"]
) -> tuple[dict[str, tuple[int, str]], dict[str, bytes]]:
    """Authenticate archive bytes against independent binding before using content."""
    bundle_module._validate_binding(binding)
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
            if name.startswith(("src/", "frontend/")):
                payload[name] = (member.size, member.sha256)
            elif name.startswith(f"{dist_info_root}/") and not name.endswith("/RECORD"):
                payload[name] = (member.size, member.sha256)
                if name.endswith("/METADATA"):
                    metadata["METADATA"] = contents[name]
    else:
        for name, member in members.items():
            if name.startswith("src/") or name.startswith("frontend/"):
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
            if name.startswith(("src/", "frontend/"))
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
) -> None:
    if _IS_WINDOWS:
        _fail(
            "Windows installed-package qualification is NO-GO until generated launcher bytes "
            "have independent installer-template authority."
        )
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


def _run_bounded(
    argv: list[str], *, cwd: Path, timeout: int, output_limit: int = _MAX_PROBE_BYTES
) -> tuple[int, bytes, bytes]:
    """Run child with bounded pipe collection and terminate its process group on overflow."""
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=(os.name != "nt"),
        )
    except OSError as error:
        raise ValueError("Isolated interpreter subprocess could not be started.") from error
    assert process.stdout is not None and process.stderr is not None
    collected: list[bytearray] = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(stream: object, target: bytearray) -> None:
        while chunk := stream.read(64 * 1024):  # type: ignore[attr-defined]
            remaining = output_limit + 1 - len(target)
            if remaining > 0:
                target.extend(chunk[:remaining])
            if len(chunk) > remaining or len(target) > output_limit:
                overflow.set()

    readers = [
        threading.Thread(target=drain, args=(process.stdout, collected[0]), daemon=True),
        threading.Thread(target=drain, args=(process.stderr, collected[1]), daemon=True),
    ]
    for reader in readers:
        reader.start()

    def terminate_group() -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            if process.poll() is None:
                process.kill()

    deadline = time.monotonic() + timeout
    timed_out = False
    while process.poll() is None:
        if overflow.is_set():
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.01)
    if process.poll() is None:
        terminate_group()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    terminate_group()
    for reader in readers:
        reader.join(timeout=1)
    if any(reader.is_alive() for reader in readers):
        terminate_group()
        for reader in readers:
            reader.join(timeout=5)
    if any(reader.is_alive() for reader in readers):
        process.stdout.close()
        process.stderr.close()
        _fail("Isolated subprocess left an output-producing descendant alive.")
    if overflow.is_set():
        _fail("Isolated subprocess exceeded the output bound.")
    if timed_out:
        _fail("Isolated subprocess exceeded its time limit.")
    return process.returncode, bytes(collected[0]), bytes(collected[1])


def _selected_environment(python: Path) -> tuple[Path, Path, str, str, str]:
    code = (
        "import json, platform, sys\n"
        "print(json.dumps({'python': platform.python_version(), "
        "'os': platform.system().lower(), 'machine': platform.machine().lower()}))\n"
    )
    code_result, stdout, _stderr = _run_bounded(
        [str(python), "-I", "-S", "-c", code], cwd=python.parent, timeout=_MAX_TCK_SECONDS
    )
    if code_result != 0:
        _fail("Selected interpreter environment could not be resolved.")
    try:
        result = json.loads(stdout)
        version, operating_system, architecture = result["python"], result["os"], result["machine"]
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        raise ValueError("Selected interpreter environment response is malformed.") from error
    if not all(
        isinstance(item, str) and item for item in (version, operating_system, architecture)
    ):
        _fail("Selected interpreter identity is malformed.")
    environment_root = python.parent.parent.resolve(strict=True)
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
) -> tuple[str, str, BuildGenerator]:
    src_root = site / "src"
    frontend_root = site / "frontend"
    actual_payload = {f"src/{name}" for name in _scope_files(src_root, label="package")} | {
        f"frontend/{name}" for name in _scope_files(frontend_root, label="frontend")
    }
    expected_names = {
        name for name in archive_payload if name.startswith("src/") or name.startswith("frontend/")
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
    for name, entry in record_entries.items():
        _verify_record_entry(name, entry, record_name)
    listed = set(record_entries)
    _verify_entry_point_scripts(record_entries, site, env_root, scripts)
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
    )


def _isolated_probe(
    python: Path, env_root: Path, site: Path, source_root: Path
) -> tuple[Path, Path, str, str, str, str, tuple[tuple[str, str], ...]]:
    code = (
        "import importlib.metadata, json, platform, sys, sysconfig\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import src, frontend\n"
        "dists = sorted((d.metadata.get('Name', ''), d.version) "
        "for d in importlib.metadata.distributions())\n"
        "print(json.dumps({'src': src.__file__, 'frontend': frontend.__file__, "
        "'purelib': sysconfig.get_paths()['purelib'], 'prefix': sys.prefix, "
        "'base_prefix': sys.base_prefix, 'python': platform.python_version(), "
        "'os': platform.system().lower(), 'machine': platform.machine().lower(), "
        "'deps': dists}))\n"
    )
    with tempfile.TemporaryDirectory(prefix="matryca-installed-probe-") as cache_prefix:
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


def _run_tcks(python: Path, site: Path, source_root: Path) -> tuple[str, str, str]:
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
) -> InstalledReceipt:
    """Verify installed files, import origin, resources, RECORD, and static TCKs."""
    if kind not in {"wheel", "sdist"}:
        _fail("Installed distribution kind must be wheel or sdist.")
    archive_payload, archive_metadata = _authenticated_archive(artifact, binding, kind)
    if _IS_WINDOWS:
        _fail(
            "Windows installed-package qualification is NO-GO until generated launcher bytes "
            "have independent installer-template authority."
        )
    _safe_root(source_root, "Source root")
    interpreter = python.absolute()
    if not interpreter.is_file():
        _fail("Selected interpreter does not exist or is not a file.")
    tracked = _verify_source(source_root, binding)
    expected_payload = _payload_map(source_root, tracked)
    source_root = source_root.resolve(strict=True)
    probe_env_root, site, _python_version, _operating_system, _architecture = _selected_environment(
        interpreter
    )
    dist_info, version = _distribution(site, binding.version)
    record = dist_info / "RECORD"
    record_entries = _parse_record(record, site, probe_env_root)
    record_sha256, resource_sha256, build_generator = _verify_inventory(
        site,
        probe_env_root,
        source_root,
        dist_info,
        expected_payload,
        archive_payload,
        archive_metadata,
        kind,
        record_entries,
    )
    (
        site,
        _origin,
        dependency_sha256,
        python_version,
        operating_system,
        architecture,
        dependencies,
    ) = _isolated_probe(interpreter, probe_env_root, site, source_root)
    tck_outcomes = _run_tcks(interpreter, site, source_root)
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
    )
