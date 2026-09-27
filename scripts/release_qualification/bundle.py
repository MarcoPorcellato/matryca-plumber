"""Strict release archive inventory and cross-job handoff binding."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import tarfile
import tomllib
import zipfile
from dataclasses import asdict, dataclass
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ID = re.compile(r"^[0-9a-f]{40}$")
_FORBIDDEN_SUFFIXES = {".pyc", ".pyd", ".pyo"}
_MAX_ARCHIVE_FILE_BYTES = 512 * 1024 * 1024
_MAX_ARCHIVE_MEMBER_BYTES = 64 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 512 * 1024 * 1024
_MAX_ARCHIVE_MEMBER_COUNT = 10_000
_MAX_CENTRAL_DIRECTORY_BYTES = 16 * 1024 * 1024
_MAX_METADATA_BYTES = 1024 * 1024
_HASH_CHUNK_BYTES = 1024 * 1024
_KNOWN_METADATA_CLASSES = {
    "wheel.dist-info.METADATA",
    "wheel.dist-info.WHEEL",
    "wheel.dist-info.RECORD",
    "wheel.dist-info.entry_points.txt",
    "wheel.dist-info.top_level.txt",
    "wheel.dist-info.licenses.LICENSE",
    "wheel.dist-info.licenses.NOTICE",
    "sdist.PKG-INFO",
    "sdist.setup.cfg",
    "sdist.egg-info.SOURCES.txt",
    "sdist.egg-info.PKG-INFO",
    "sdist.egg-info.dependency_links.txt",
    "sdist.egg-info.entry_points.txt",
    "sdist.egg-info.requires.txt",
    "sdist.egg-info.top_level.txt",
}
_REQUIRED_METADATA_CLASSES = _KNOWN_METADATA_CLASSES
_SDIST_SELECTED_ROOT_FILES = {
    "pyproject.toml",
    "README.md",
    "LICENSE",
    "NOTICE",
    "setup.py",
    "MANIFEST.in",
}
_SDIST_TCK_FILES = {
    "scripts/run_plumber_consumer_package_v1_tck.py",
    "scripts/run_plumber_graph_read_v1_tck.py",
    "scripts/run_plumber_graph_topology_v1_tck.py",
}


@dataclass(frozen=True, slots=True)
class BundleBinding:
    """Immutable source and byte identity for one release package pair."""

    source_commit: str
    source_tree: str
    version: str
    wheel_name: str
    wheel_size: int
    wheel_sha256: str
    sdist_name: str
    sdist_size: int
    sdist_sha256: str
    wheel_inventory_sha256: str
    sdist_inventory_sha256: str

    def to_json(self) -> str:
        """Serialize the binding as canonical compact JSON."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, value: str) -> BundleBinding:
        """Parse and validate a compact binding received across a job boundary."""
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("Invalid binding JSON.") from error
        if not isinstance(parsed, dict) or set(parsed) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid binding fields.")
        try:
            result = cls(**parsed)
        except TypeError as error:
            raise ValueError("Invalid binding fields.") from error
        _validate_binding(result)
        if result.to_json() != value:
            raise ValueError("Binding JSON is not canonical.")
        return result


@dataclass(frozen=True, slots=True)
class _Member:
    name: str
    size: int
    sha256: str


def _validate_binding(binding: BundleBinding) -> None:
    if (
        not isinstance(binding.source_commit, str)
        or not isinstance(binding.source_tree, str)
        or not _SOURCE_ID.fullmatch(binding.source_commit)
        or not _SOURCE_ID.fullmatch(binding.source_tree)
    ):
        raise ValueError("Binding source commit and tree must be lowercase full Git IDs.")
    if not isinstance(binding.version, str) or not re.fullmatch(
        r"2\.0\.1rc[0-9]+", binding.version
    ):
        raise ValueError("Binding version is invalid.")
    if binding.wheel_name != f"matryca_plumber-{binding.version}-py3-none-any.whl":
        raise ValueError("Binding wheel name is invalid.")
    if binding.sdist_name != f"matryca_plumber-{binding.version}.tar.gz":
        raise ValueError("Binding source distribution name is invalid.")
    if not isinstance(binding.wheel_name, str) or not isinstance(binding.sdist_name, str):
        raise ValueError("Binding archive names are invalid.")
    for size in (binding.wheel_size, binding.sdist_size):
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("Binding archive size is invalid.")
    for digest in (
        binding.wheel_sha256,
        binding.sdist_sha256,
        binding.wheel_inventory_sha256,
        binding.sdist_inventory_sha256,
    ):
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError("Binding digest is invalid.")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_stream(
    stream: Any, *, max_bytes: int, retain: bool = False
) -> tuple[int, str, bytes | None]:
    digest = hashlib.sha256()
    retained = bytearray() if retain else None
    size = 0
    while chunk := stream.read(_HASH_CHUNK_BYTES):
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("Archive member size limit exceeded while decompressing.")
        digest.update(chunk)
        if retained is not None:
            retained.extend(chunk)
    return size, digest.hexdigest(), bytes(retained) if retained is not None else None


def _check_archive_file(path: Path) -> int:
    size = path.stat().st_size
    if size <= 0 or size > _MAX_ARCHIVE_FILE_BYTES:
        raise ValueError("Archive file size limit exceeded.")
    return size


def _archive_sha256(path: Path) -> tuple[int, str]:
    size = _check_archive_file(path)
    with path.open("rb") as stream:
        actual_size, digest, _ = _hash_stream(stream, max_bytes=_MAX_ARCHIVE_FILE_BYTES)
    if actual_size != size:
        raise ValueError("Archive changed while its digest was being calculated.")
    return size, digest


def _preflight_wheel_zip(stream: Any, archive_size: int) -> None:
    """Bound and validate ZIP structure before ZipFile parses its directory."""
    eocd_signature = b"PK\x05\x06"
    eocd_size = 22
    tail_size = min(archive_size, eocd_size + 0xFFFF)
    stream.seek(archive_size - tail_size)
    tail = stream.read(tail_size)
    eocd_index = tail.rfind(eocd_signature)
    if eocd_index < 0 or eocd_index + eocd_size > len(tail):
        raise ValueError("Wheel ZIP end-of-central-directory record is missing or malformed.")
    record = struct.unpack_from("<4s4H2LH", tail, eocd_index)
    if eocd_index + eocd_size + record[-1] != len(tail):
        raise ValueError("Wheel ZIP end-of-central-directory comment is malformed or trailing.")

    (
        _signature,
        disk_number,
        central_disk,
        disk_entry_count,
        entry_count,
        central_size,
        central_offset,
        _comment_size,
    ) = record
    eocd_offset = archive_size - tail_size + eocd_index
    if eocd_offset >= 20:
        stream.seek(eocd_offset - 20)
        if stream.read(4) == b"PK\x06\x07":
            raise ValueError("ZIP64 wheels are not supported.")
    if (
        disk_number == 0xFFFF
        or central_disk == 0xFFFF
        or disk_entry_count == 0xFFFF
        or entry_count == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    ):
        raise ValueError("ZIP64 wheels are not supported.")
    if disk_number != 0 or central_disk != 0 or disk_entry_count != entry_count:
        raise ValueError("Multi-disk wheels are not supported.")
    if entry_count > _MAX_ARCHIVE_MEMBER_COUNT:
        raise ValueError("Archive member count limit exceeded.")
    if central_size > _MAX_CENTRAL_DIRECTORY_BYTES:
        raise ValueError("Wheel central directory size limit exceeded.")
    if central_offset + central_size != eocd_offset:
        raise ValueError("Wheel central directory bounds are inconsistent.")

    stream.seek(central_offset)
    consumed = 0
    for _ in range(entry_count):
        header = stream.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ValueError("Wheel central directory entry is malformed.")
        compressed_size = struct.unpack_from("<I", header, 20)[0]
        uncompressed_size = struct.unpack_from("<I", header, 24)[0]
        name_size, extra_size, comment_size = struct.unpack_from("<3H", header, 28)
        disk_start = struct.unpack_from("<H", header, 34)[0]
        local_offset = struct.unpack_from("<I", header, 42)[0]
        if (
            compressed_size == 0xFFFFFFFF
            or uncompressed_size == 0xFFFFFFFF
            or disk_start == 0xFFFF
            or local_offset == 0xFFFFFFFF
        ):
            raise ValueError("ZIP64 wheel members are not supported.")
        if disk_start != 0:
            raise ValueError("Multi-disk wheel members are not supported.")
        variable_size = name_size + extra_size + comment_size
        consumed += 46 + variable_size
        if consumed > central_size:
            raise ValueError("Wheel central directory entry exceeds declared bounds.")
        if name_size:
            stream.seek(name_size, 1)
        extra = stream.read(extra_size)
        if len(extra) != extra_size:
            raise ValueError("Wheel central directory extra field is truncated.")
        extra_offset = 0
        while extra_offset < len(extra):
            if extra_offset + 4 > len(extra):
                raise ValueError("Wheel central directory extra field is malformed.")
            field_id, field_size = struct.unpack_from("<HH", extra, extra_offset)
            extra_offset += 4
            if extra_offset + field_size > len(extra):
                raise ValueError("Wheel central directory extra field is malformed.")
            if field_id == 0x0001:
                raise ValueError("ZIP64 wheel members are not supported.")
            extra_offset += field_size
        if comment_size:
            stream.seek(comment_size, 1)
    if consumed != central_size:
        raise ValueError("Wheel central directory size does not match its entries.")


def _canonical_member_name(name: str) -> str:
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError(f"Unsafe archive path: {name!r}.")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in name.split("/")) or path.is_absolute():
        raise ValueError(f"Unsafe archive path: {name!r}.")
    normalized = path.as_posix()
    if normalized != name.rstrip("/"):
        raise ValueError(f"Non-canonical archive path: {name!r}.")
    return normalized


def _check_member_name(name: str, seen: set[str], folded: set[str]) -> str:
    normalized = _canonical_member_name(name)
    key = normalized.casefold()
    if normalized in seen:
        raise ValueError(f"Duplicate archive member: {normalized}.")
    if key in folded:
        raise ValueError(f"Case-colliding archive member: {normalized}.")
    seen.add(normalized)
    folded.add(key)
    parts = PurePosixPath(normalized).parts
    if "__pycache__" in parts or PurePosixPath(normalized).suffix.lower() in _FORBIDDEN_SUFFIXES:
        raise ValueError(f"Compiled Python artifacts are not permitted: {normalized}.")
    return normalized


def _read_wheel(path: Path) -> tuple[dict[str, _Member], dict[str, bytes]]:
    archive_size = _check_archive_file(path)
    with path.open("rb") as stream:
        _preflight_wheel_zip(stream, archive_size)
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            return _read_wheel_archive(archive)


def _read_wheel_archive(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, _Member], dict[str, bytes]]:
    members: dict[str, _Member] = {}
    contents: dict[str, bytes] = {}
    seen: set[str] = set()
    folded: set[str] = set()
    infos = archive.infolist()
    if len(infos) > _MAX_ARCHIVE_MEMBER_COUNT:
        raise ValueError("Archive member count limit exceeded.")
    total_size = 0
    for info in infos:
        name = _check_member_name(info.filename, seen, folded)
        if info.is_dir():
            raise ValueError(f"Unexpected directory member in wheel: {name}.")
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = mode & 0o170000
        if file_type not in {0, 0o100000}:
            raise ValueError(f"Link or special wheel member is not permitted: {name}.")
        if info.file_size < 0 or info.file_size > _MAX_ARCHIVE_MEMBER_BYTES:
            raise ValueError("Archive member size limit exceeded.")
        if total_size + info.file_size > _MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError("Archive total decompressed size limit exceeded.")
        retain = name.endswith(".dist-info/METADATA")
        if retain and info.file_size > _MAX_METADATA_BYTES:
            raise ValueError("Archive metadata size limit exceeded.")
        with archive.open(info, "r") as stream:
            size, digest, payload = _hash_stream(
                stream, max_bytes=_MAX_ARCHIVE_MEMBER_BYTES, retain=retain
            )
        if size != info.file_size:
            raise ValueError(f"Archive member size does not match header: {name}.")
        total_size += size
        if total_size > _MAX_ARCHIVE_TOTAL_BYTES:
            raise ValueError("Archive total decompressed size limit exceeded.")
        members[name] = _Member(name, size, digest)
        if payload is not None:
            contents[name] = payload
    return members, contents


def _read_sdist(
    path: Path, expected_root: str
) -> tuple[dict[str, _Member], dict[str, bytes], set[str]]:
    members: dict[str, _Member] = {}
    contents: dict[str, bytes] = {}
    directories: set[str] = set()
    seen: set[str] = set()
    folded: set[str] = set()
    _check_archive_file(path)
    with tarfile.open(path, "r|gz") as archive:
        total_size = 0
        member_count = 0
        for info in archive:
            member_count += 1
            if member_count > _MAX_ARCHIVE_MEMBER_COUNT:
                raise ValueError("Archive member count limit exceeded.")
            name = _check_member_name(info.name, seen, folded)
            if name == expected_root:
                if not info.isdir():
                    raise ValueError("Source distribution root is not a directory.")
                directories.add("")
                continue
            if not name.startswith(f"{expected_root}/"):
                raise ValueError(f"Unexpected source distribution root member: {name}.")
            relative = name[len(expected_root) + 1 :]
            if not relative:
                raise ValueError(f"Invalid source distribution member: {name}.")
            if info.isdir():
                directories.add(relative)
                continue
            if not info.isfile():
                raise ValueError(
                    f"Link or special source distribution member is not permitted: {name}."
                )
            stream = archive.extractfile(info)
            if stream is None:
                raise ValueError(f"Could not read source distribution member: {name}.")
            if info.size < 0 or info.size > _MAX_ARCHIVE_MEMBER_BYTES:
                raise ValueError("Archive member size limit exceeded.")
            if total_size + info.size > _MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("Archive total decompressed size limit exceeded.")
            retain = relative == "PKG-INFO"
            if retain and info.size > _MAX_METADATA_BYTES:
                raise ValueError("Archive metadata size limit exceeded.")
            with stream:
                size, digest, payload = _hash_stream(
                    stream, max_bytes=_MAX_ARCHIVE_MEMBER_BYTES, retain=retain
                )
            if size != info.size:
                raise ValueError(f"Archive member size does not match header: {relative}.")
            total_size += size
            if total_size > _MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("Archive total decompressed size limit exceeded.")
            members[relative] = _Member(relative, size, digest)
            if payload is not None:
                contents[relative] = payload
    return members, contents, directories


def _read_ledger(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("Content ledger size limit exceeded.")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Could not read content ledger.") from error
    required = {
        "schema_version",
        "source_commit",
        "source_tree",
        "version",
        "selected_source_files",
        "frontend_files",
        "generated_metadata_classes",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value["schema_version"] != 1
        or isinstance(value["schema_version"], bool)
    ):
        raise ValueError("Content ledger has invalid fields or schema version.")
    if (
        not isinstance(value["source_commit"], str)
        or not isinstance(value["source_tree"], str)
        or not _SOURCE_ID.fullmatch(value["source_commit"])
        or not _SOURCE_ID.fullmatch(value["source_tree"])
    ):
        raise ValueError("Content ledger source identity is invalid.")
    if not isinstance(value["version"], str) or not re.fullmatch(
        r"2\.0\.1rc[0-9]+", value["version"]
    ):
        raise ValueError("Content ledger version is invalid.")
    for key in ("selected_source_files", "frontend_files"):
        if not isinstance(value[key], list):
            raise ValueError(f"Content ledger {key} must be a list.")
        paths: set[str] = set()
        folded: set[str] = set()
        for item in value[key]:
            if not isinstance(item, dict) or set(item) != {"name", "sha256"}:
                raise ValueError(f"Content ledger {key} entry is invalid.")
            name = _canonical_member_name(item["name"])
            if name in paths or name.casefold() in folded:
                raise ValueError(f"Duplicate content-ledger path: {name}.")
            if not isinstance(item["sha256"], str) or not _SHA256.fullmatch(item["sha256"]):
                raise ValueError(f"Content-ledger digest is invalid for {name}.")
            paths.add(name)
            folded.add(name.casefold())
        if not paths:
            raise ValueError(f"Content ledger {key} cannot be empty.")
    if not isinstance(value["generated_metadata_classes"], list) or any(
        not isinstance(name, str) for name in value["generated_metadata_classes"]
    ):
        raise ValueError("Content ledger metadata classes are invalid.")
    return value


def _ledger_map(items: list[dict[str, str]]) -> dict[str, str]:
    return {item["name"]: item["sha256"] for item in items}


def _expected_sdist_source_files(source: dict[str, str]) -> dict[str, str]:
    return {
        name: digest
        for name, digest in source.items()
        if name.startswith(("src/", "contracts/"))
        or (name.startswith("tests/test_") and name.count("/") == 1 and name.endswith(".py"))
        or name in _SDIST_SELECTED_ROOT_FILES
        or name in _SDIST_TCK_FILES
        or name == "frontend/__init__.py"
    }


def _expected_wheel_source_files(source: dict[str, str]) -> dict[str, str]:
    expected = {
        name: digest
        for name, digest in source.items()
        if name.startswith("src/") and name.endswith(".py")
    }
    for name, digest in source.items():
        if name.startswith("contracts/"):
            expected[f"src/contract_artifacts/{name}"] = digest
        elif name in _SDIST_TCK_FILES:
            expected[f"src/contract_artifacts/tck/{PurePosixPath(name).name}"] = digest
    if "frontend/__init__.py" in source:
        expected["frontend/__init__.py"] = source["frontend/__init__.py"]
    return expected


def _metadata_members(ledger: dict[str, Any], members: dict[str, _Member], kind: str) -> set[str]:
    classes = ledger["generated_metadata_classes"]
    if len(classes) != len(set(classes)) or set(classes) - _KNOWN_METADATA_CLASSES:
        raise ValueError("Content ledger contains unknown generated metadata classes.")
    expected: set[str] = set()
    wheel_root = ""
    if kind == "wheel":
        wheel_roots = {
            name.split("/", 1)[0] for name in members if name.endswith(".dist-info/METADATA")
        }
        if len(wheel_roots) != 1:
            raise ValueError("Wheel must contain one generated .dist-info metadata directory.")
        wheel_root = next(iter(wheel_roots))
    for item in classes:
        if item.startswith("wheel.dist-info."):
            if kind != "wheel":
                continue
            suffix = item.removeprefix("wheel.dist-info.")
            if suffix.startswith("licenses."):
                suffix = suffix.replace("licenses.", "licenses/", 1)
            expected.add(f"{wheel_root}/{suffix}")
        elif item == "sdist.PKG-INFO":
            if kind != "sdist":
                continue
            expected.add("PKG-INFO")
        elif item == "sdist.setup.cfg":
            if kind != "sdist":
                continue
            expected.add("setup.cfg")
        elif item == "sdist.egg-info.SOURCES.txt":
            if kind != "sdist":
                continue
            matches = {name for name in members if name.endswith(".egg-info/SOURCES.txt")}
            if len(matches) != 1:
                raise ValueError("Source distribution must contain one generated SOURCES.txt.")
            expected.update(matches)
        elif item.startswith("sdist.egg-info."):
            if kind != "sdist":
                continue
            filename = item.removeprefix("sdist.egg-info.")
            roots = {
                name.removesuffix("/PKG-INFO")
                for name in members
                if name.endswith(".egg-info/PKG-INFO")
            }
            if len(roots) != 1:
                raise ValueError("Source distribution must contain one generated egg-info root.")
            expected.add(f"{next(iter(roots))}/{filename}")
    return expected


def _verify_inventory(
    members: dict[str, _Member], expected: dict[str, str], metadata: set[str], kind: str
) -> None:
    expected_names = set(expected) | metadata
    observed_names = set(members)
    missing = sorted(expected_names - observed_names)
    if missing:
        raise ValueError(f"{kind} missing expected release content: {missing}.")
    extra = sorted(observed_names - expected_names)
    if extra:
        raise ValueError(f"{kind} contains unowned unexpected members: {extra}.")
    for name, expected_digest in expected.items():
        observed = members[name]
        if observed.sha256 != expected_digest:
            raise ValueError(f"{kind} payload digest differs from ledger: {name}.")


def _inventory_digest(members: dict[str, _Member]) -> str:
    payload = json.dumps(
        [asdict(members[name]) for name in sorted(members)],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def _verify_sdist_directories(directories: set[str], expected_files: set[str]) -> None:
    allowed = {""}
    for name in expected_files:
        parts = PurePosixPath(name).parts
        allowed.update("/".join(parts[:index]) for index in range(1, len(parts)))
    unexpected = sorted(directories - allowed)
    if unexpected:
        raise ValueError(f"sdist contains unexpected directories: {unexpected}.")


def _metadata_version(contents: dict[str, bytes], suffix: str, archive: str) -> str:
    matches = [payload for name, payload in contents.items() if name.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"{archive} must contain exactly one {suffix}.")
    metadata = BytesParser().parsebytes(matches[0])
    if metadata.get("Name") != "matryca-plumber":
        raise ValueError(f"{archive} metadata package name does not match matryca-plumber.")
    version = metadata.get("Version")
    if not version:
        raise ValueError(f"{archive} metadata has no version.")
    return version


def _verify_pair(dist: Path, ledger: dict[str, Any]) -> tuple[Path, Path, str, str]:
    if not dist.is_dir() or dist.is_symlink():
        raise ValueError("Distribution path must be a real directory.")
    wheels = sorted(path for path in dist.iterdir() if path.name.endswith(".whl"))
    sdists = sorted(path for path in dist.iterdir() if path.name.endswith(".tar.gz"))
    unexpected = sorted(path.name for path in dist.iterdir() if path.suffix not in {".whl", ".gz"})
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("Expected exactly one wheel and one source distribution.")
    if unexpected or len(list(dist.iterdir())) != 2:
        raise ValueError(f"Distribution directory contains unexpected files: {unexpected}.")
    if any(path.is_symlink() or not path.is_file() for path in (*wheels, *sdists)):
        raise ValueError("Distribution archives must be regular files.")
    version = ledger["version"].replace("-alpha.", "a").replace("-beta.", "b").replace("-rc.", "rc")
    expected_wheel_name = f"matryca_plumber-{version}-py3-none-any.whl"
    expected_sdist_name = f"matryca_plumber-{version}.tar.gz"
    if wheels[0].name != expected_wheel_name or sdists[0].name != expected_sdist_name:
        raise ValueError("Distribution filenames do not match the normalized project version.")

    source = _ledger_map(ledger["selected_source_files"])
    frontend = _ledger_map(ledger["frontend_files"])
    wheel_members, wheel_contents = _read_wheel(wheels[0])
    sdist_members, sdist_contents, sdist_directories = _read_sdist(
        sdists[0], f"matryca_plumber-{version}"
    )
    metadata_classes = set(ledger["generated_metadata_classes"])
    if metadata_classes != _REQUIRED_METADATA_CLASSES:
        raise ValueError("Content ledger generated metadata classes are incomplete or unexpected.")
    wheel_metadata = _metadata_members(ledger, wheel_members, "wheel")
    sdist_metadata = _metadata_members(ledger, sdist_members, "sdist")
    wheel_expected = _expected_wheel_source_files(source)
    wheel_expected.update(frontend)
    for filename in ("LICENSE", "NOTICE"):
        license_names = [name for name in wheel_metadata if name.endswith(f"/licenses/{filename}")]
        if len(license_names) != 1 or filename not in source:
            raise ValueError(
                f"Wheel generated license metadata {filename} is missing or duplicated."
            )
        wheel_expected[license_names[0]] = source[filename]
    sdist_expected = _expected_sdist_source_files(source)
    sdist_expected.update(frontend)
    _verify_inventory(wheel_members, wheel_expected, wheel_metadata, "wheel")
    _verify_inventory(sdist_members, sdist_expected, sdist_metadata, "sdist")
    _verify_sdist_directories(sdist_directories, set(sdist_expected) | sdist_metadata)
    if _metadata_version(wheel_contents, "/METADATA", wheels[0].name) != version:
        raise ValueError("Wheel metadata version does not match the content ledger.")
    if _metadata_version(sdist_contents, "PKG-INFO", sdists[0].name) != version:
        raise ValueError("Source distribution metadata version does not match the content ledger.")
    return wheels[0], sdists[0], _inventory_digest(wheel_members), _inventory_digest(sdist_members)


def _git_value(repository: Path, argument: str) -> str:
    import subprocess

    try:
        return subprocess.check_output(
            ["git", "rev-parse", argument], cwd=repository, text=True, stderr=subprocess.PIPE
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"Could not resolve repository {argument}.") from error


def _git_tree_file_digests(repository: Path) -> dict[str, str]:
    process = subprocess.Popen(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise ValueError("Could not read selected Git tree archive.")
    digests: dict[str, str] = {}
    seen: set[str] = set()
    folded: set[str] = set()
    total_size = 0
    member_count = 0
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for info in archive:
                member_count += 1
                if member_count > _MAX_ARCHIVE_MEMBER_COUNT:
                    raise ValueError("Selected Git tree member count limit exceeded.")
                name = _check_member_name(info.name, seen, folded)
                if info.isdir():
                    continue
                if not info.isfile():
                    raise ValueError(f"Selected Git tree contains a special member: {name}.")
                if info.size < 0 or info.size > _MAX_ARCHIVE_MEMBER_BYTES:
                    raise ValueError("Selected Git tree member size limit exceeded.")
                total_size += info.size
                if total_size > _MAX_ARCHIVE_TOTAL_BYTES:
                    raise ValueError("Selected Git tree total size limit exceeded.")
                stream = archive.extractfile(info)
                if stream is None:
                    raise ValueError(f"Could not read selected Git tree member: {name}.")
                with stream:
                    size, digest, _ = _hash_stream(stream, max_bytes=_MAX_ARCHIVE_MEMBER_BYTES)
                if size != info.size:
                    raise ValueError(f"Selected Git tree member size mismatch: {name}.")
                digests[name] = digest
    except Exception:
        process.kill()
        process.wait()
        raise
    finally:
        process.stdout.close()
    stderr = process.stderr.read()
    return_code = process.wait()
    process.stderr.close()
    if return_code != 0:
        raise ValueError(f"Could not export selected Git tree: {stderr.decode(errors='replace')}.")
    return digests


def build_binding(
    repository: Path, dist: Path, ledger: Path, expected_commit: str
) -> BundleBinding:
    """Verify one exact-commit distribution pair and bind its archive bytes."""
    if not _SOURCE_ID.fullmatch(expected_commit):
        raise ValueError("Expected source commit must be a lowercase full Git ID.")
    source_commit = _git_value(repository, "HEAD")
    source_tree = _git_value(repository, "HEAD^{tree}")
    if source_commit != expected_commit:
        raise ValueError("Repository HEAD does not match expected source commit.")
    content_ledger = _read_ledger(ledger)
    if content_ledger["source_commit"] != source_commit:
        raise ValueError("Content ledger source commit does not match repository HEAD.")
    if content_ledger["source_tree"] != source_tree:
        raise ValueError("Content ledger source tree does not match repository HEAD.")
    selected_source = _ledger_map(content_ledger["selected_source_files"])
    if selected_source != _git_tree_file_digests(repository):
        raise ValueError("Content ledger selected source does not match selected Git tree files.")
    try:
        project = tomllib.loads((repository / "pyproject.toml").read_text(encoding="utf-8"))
        declared_version = project["project"]["version"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as error:
        raise ValueError("Could not resolve project version from the selected source.") from error
    if content_ledger["version"] != declared_version:
        raise ValueError("Content ledger version does not match selected source pyproject.toml.")
    wheel, sdist, wheel_inventory, sdist_inventory = _verify_pair(dist, content_ledger)
    version = (
        content_ledger["version"]
        .replace("-alpha.", "a")
        .replace("-beta.", "b")
        .replace("-rc.", "rc")
    )
    wheel_size, wheel_digest = _archive_sha256(wheel)
    sdist_size, sdist_digest = _archive_sha256(sdist)
    binding = BundleBinding(
        source_commit=source_commit,
        source_tree=source_tree,
        version=version,
        wheel_name=wheel.name,
        wheel_size=wheel_size,
        wheel_sha256=wheel_digest,
        sdist_name=sdist.name,
        sdist_size=sdist_size,
        sdist_sha256=sdist_digest,
        wheel_inventory_sha256=wheel_inventory,
        sdist_inventory_sha256=sdist_inventory,
    )
    _validate_binding(binding)
    return binding


def canonical_manifest(binding: BundleBinding) -> bytes:
    """Return the canonical two-line SHA256SUMS representation."""
    _validate_binding(binding)
    return (
        f"{binding.wheel_sha256}  {binding.wheel_name}\n"
        f"{binding.sdist_sha256}  {binding.sdist_name}\n"
    ).encode("ascii")


def verify_handoff(dist: Path, manifest: Path, expected: BundleBinding) -> None:
    """Verify downloaded archives against independent build-job binding values."""
    _validate_binding(expected)
    canonical_path = dist / "SHA256SUMS"
    if (
        manifest.name != "SHA256SUMS"
        or manifest != canonical_path
        or manifest.is_symlink()
        or not manifest.is_file()
    ):
        raise ValueError("Manifest must be the exact dist/SHA256SUMS regular file.")
    expected_manifest = canonical_manifest(expected)
    if (
        manifest.stat().st_size != len(expected_manifest)
        or manifest.read_bytes() != expected_manifest
    ):
        raise ValueError("SHA256SUMS manifest does not match expected binding.")
    if not dist.is_dir() or dist.is_symlink():
        raise ValueError("Distribution path must be a real directory.")
    entries = list(dist.iterdir())
    if {path.name for path in entries} != {
        expected.wheel_name,
        expected.sdist_name,
        manifest.name,
    } or any(path.is_symlink() or not path.is_file() for path in entries):
        raise ValueError("Handoff directory contains missing or unexpected files.")
    for path, name, size, digest in (
        (
            dist / expected.wheel_name,
            expected.wheel_name,
            expected.wheel_size,
            expected.wheel_sha256,
        ),
        (
            dist / expected.sdist_name,
            expected.sdist_name,
            expected.sdist_size,
            expected.sdist_sha256,
        ),
    ):
        actual_size, actual_digest = _archive_sha256(path)
        if path.name != name or actual_size != size or actual_digest != digest:
            raise ValueError(f"Downloaded archive differs from independent binding: {name}.")
    wheel_members, wheel_contents = _read_wheel(dist / expected.wheel_name)
    sdist_members, sdist_contents, sdist_directories = _read_sdist(
        dist / expected.sdist_name, f"matryca_plumber-{expected.version}"
    )
    _verify_sdist_directories(sdist_directories, set(sdist_members))
    if _metadata_version(wheel_contents, "/METADATA", expected.wheel_name) != expected.version:
        raise ValueError("Downloaded wheel metadata version differs from independent binding.")
    if _metadata_version(sdist_contents, "PKG-INFO", expected.sdist_name) != expected.version:
        raise ValueError(
            "Downloaded source distribution metadata version differs from independent binding."
        )
    if _inventory_digest(wheel_members) != expected.wheel_inventory_sha256:
        raise ValueError("Downloaded wheel inventory differs from independent binding.")
    if _inventory_digest(sdist_members) != expected.sdist_inventory_sha256:
        raise ValueError(
            "Downloaded source distribution inventory differs from independent binding."
        )
