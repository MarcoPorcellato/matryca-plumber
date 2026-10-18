"""Acquire only hash-bound qualification tools, without installing or executing them."""

from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import os
import platform
import re
import stat
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Protocol

VERSION = "0.12.19"
SOURCE = "bea138450f0e620a4ce5765b0e38cff7b9f0799f"
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 128 * 1024 * 1024
MAX_MEMBERS = 32
ATTEMPT_SECONDS = 120


class AcquisitionError(RuntimeError):
    """A failed closed bootstrap boundary; the owned evidence stays preserved."""


class _Readable(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


@dataclass(frozen=True)
class Asset:
    filename: str
    size: int
    sha256: str
    member: str
    system: str
    machines: tuple[str, ...]

    @property
    def url(self) -> str:
        return f"https://github.com/astral-sh/uv/releases/download/{VERSION}/{self.filename}"


ASSETS = {
    "linux-x86_64": Asset(
        "uv-x86_64-unknown-linux-gnu.tar.gz",
        19831732,
        "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8",
        "uv-x86_64-unknown-linux-gnu/uv",
        "Linux",
        ("x86_64",),
    ),
    "macos-arm64": Asset(
        "uv-aarch64-apple-darwin.tar.gz",
        16988553,
        "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba",
        "uv-aarch64-apple-darwin/uv",
        "Darwin",
        ("arm64",),
    ),
    "windows-x64": Asset(
        "uv-x86_64-pc-windows-msvc.zip",
        17955780,
        "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0",
        "uv.exe",
        "Windows",
        ("AMD64", "x86_64"),
    ),
}


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AcquisitionError("attempt_deadline")
    return min(10.0, remaining)


def _bootstrap() -> dict[str, object]:
    if platform.python_implementation() != "CPython" or sys.version_info[:2] < (3, 12):
        raise AcquisitionError("unsupported_bootstrap")
    return {
        "implementation": "CPython",
        "version": list(sys.version_info[:3]),
        "executable": str(Path(sys.executable).resolve(strict=True)),
    }


def _asset(name: str) -> Asset:
    asset = ASSETS.get(name)
    if (
        asset is None
        or platform.system() != asset.system
        or platform.machine() not in asset.machines
    ):
        raise AcquisitionError("platform_mismatch")
    if os.environ.get("UV_ARCHIVE_SHA256", asset.sha256) != asset.sha256:
        raise AcquisitionError("workflow_pin_mismatch")
    return asset


def _metadata(path: Path, *, directory: bool = False) -> os.stat_result:
    try:
        value = path.lstat()
    except OSError as error:
        raise AcquisitionError("unsafe_path") from error
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400:
        raise AcquisitionError("unsafe_path")
    if path.is_symlink() or (hasattr(os, "getuid") and value.st_uid != os.getuid()):
        raise AcquisitionError("unsafe_path")
    return value


def _root(root: Path, runner_temp: Path, *, fresh: bool) -> Path:
    try:
        runner = runner_temp.resolve(strict=True)
        _metadata(runner, directory=True)
        if (
            not root.is_absolute()
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", root.name)
            or root.parent.resolve(strict=True) != runner
        ):
            raise AcquisitionError("root_outside_runner_temp")
        root = runner / root.name
        if fresh:
            if root.exists() or root.is_symlink():
                raise AcquisitionError("root_not_fresh")
            root.mkdir(mode=0o700)
            (root / "bin").mkdir(mode=0o700)
        _metadata(root, directory=True)
        _metadata(root / "bin", directory=True)
        return root
    except OSError as error:
        raise AcquisitionError("unsafe_root") from error


def _read_file(path: Path, limit: int) -> bytes:
    before = _metadata(path)
    if before.st_size > limit:
        raise AcquisitionError("file_limit")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        with os.fdopen(os.open(path, flags), "rb") as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(limit + 1)
        after = _metadata(path)
    except OSError as error:
        raise AcquisitionError("unsafe_file_read") from error

    def identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    if (
        identity(before) != identity(opened)
        or identity(before) != identity(after)
        or len(data) != before.st_size
    ):
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        diagnostic = json.dumps(
            {
                "code": "file_changed",
                "implementation": sys.implementation.name,
                "version": dict(
                    zip(
                        ("major", "minor", "micro", "releaselevel", "serial"),
                        sys.version_info,
                        strict=True,
                    )
                ),
                "before_opened": {
                    field: getattr(before, field) == getattr(opened, field) for field in fields
                },
                "before_after": {
                    field: getattr(before, field) == getattr(after, field) for field in fields
                },
                "length_equal": len(data) == before.st_size,
            },
            sort_keys=True,
        )
        if len(diagnostic.encode("utf-8")) + 1 <= 4096:
            with contextlib.suppress(OSError):
                print(diagnostic, file=sys.stderr)
        raise AcquisitionError("file_changed")
    return data


def _new_file(path: Path) -> BinaryIO:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    return os.fdopen(os.open(path, flags, 0o600), "wb")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _url(url: str, asset: Asset) -> None:
    try:
        parsed = urllib.parse.urlsplit(url)
        valid = (
            len(url) <= 8192
            and not any(ord(c) <= 32 or ord(c) == 127 for c in url)
            and parsed.scheme == "https"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and not parsed.fragment
            and (
                (
                    parsed.hostname == "github.com"
                    and parsed.path == urllib.parse.urlsplit(asset.url).path
                    and not parsed.query
                )
                or parsed.hostname
                in {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}
            )
        )
    except ValueError as error:
        raise AcquisitionError("untrusted_redirect") from error
    if not valid:
        raise AcquisitionError("untrusted_redirect")


def _download(asset: Asset, path: Path, deadline: float) -> None:
    if not 0 < asset.size <= MAX_ARCHIVE_BYTES:
        raise AcquisitionError("archive_limit")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    url = asset.url
    for redirect in range(4):
        _url(url, asset)
        request = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
        try:
            response = opener.open(request, timeout=_remaining(deadline))
        except urllib.error.HTTPError as error:
            with contextlib.closing(error):
                if error.code not in (301, 302, 303, 307, 308) or redirect == 3:
                    raise AcquisitionError("request_failed") from error
                location = error.headers.get("Location")
                if location is None:
                    raise AcquisitionError("missing_redirect") from error
                url = urllib.parse.urljoin(url, location)
            continue
        except (OSError, urllib.error.URLError) as error:
            raise AcquisitionError("request_failed") from error
        with contextlib.closing(response):
            if response.status != 200:
                raise AcquisitionError("request_failed")
            length = response.headers.get("Content-Length")
            if length is not None and length != str(asset.size):
                raise AcquisitionError("archive_size_mismatch")
            digest = hashlib.sha256()
            total = 0
            with _new_file(path) as output:
                while True:
                    _remaining(deadline)
                    chunk = response.read(min(65536, asset.size - total + 1))
                    if not chunk:
                        break
                    if len(chunk) > asset.size - total:
                        raise AcquisitionError("archive_size_mismatch")
                    output.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
            if total != asset.size or digest.hexdigest() != asset.sha256:
                raise AcquisitionError("archive_identity_mismatch")
        return
    raise AcquisitionError("redirect_limit")


def _bounded_bytes(stream: _Readable, limit: int, deadline: float) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        _remaining(deadline)
        chunk = stream.read(min(65536, limit - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > limit:
            raise AcquisitionError("expansion_limit")
        chunks.append(chunk)


def _name(name: str, seen: set[str]) -> str:
    canonical = name[:-1] if name.endswith("/") else name
    parts = canonical.split("/")
    if (
        len(name) > 1024
        or "\\" in name
        or ":" in name
        or any(part in ("", ".", "..") for part in parts)
        or PurePosixPath(canonical).is_absolute()
        or canonical.casefold() in seen
    ):
        raise AcquisitionError("unsafe_archive_member")
    seen.add(canonical.casefold())
    return canonical


def _admit_tar_headers(expanded: bytes, deadline: float) -> None:
    """Count raw headers before tarfile can consume extension metadata."""
    offset = 0
    count = 0
    while offset + 512 <= len(expanded):
        _remaining(deadline)
        header = expanded[offset : offset + 512]
        if header == bytes(512):
            if offset + 1024 > len(expanded) or any(expanded[offset:]):
                raise AcquisitionError("invalid_tar_termination")
            return
        count += 1
        if count > MAX_MEMBERS:
            raise AcquisitionError("member_limit")
        kind = header[156:157]
        if kind not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
            raise AcquisitionError("unsupported_tar_header")
        size_field = header[124:136].strip(b"\0 ") or b"0"
        if any(value not in b"01234567" for value in size_field):
            raise AcquisitionError("invalid_tar_size")
        size = int(size_field, 8)
        if size > MAX_EXPANDED_BYTES or (kind == tarfile.DIRTYPE and size):
            raise AcquisitionError("expansion_limit")
        offset += 512 + ((size + 511) // 512) * 512
        if offset > len(expanded):
            raise AcquisitionError("truncated_tar_member")
    raise AcquisitionError("missing_tar_termination")


def _payload(asset: Asset, raw: bytes, deadline: float) -> bytes:
    seen: set[str] = set()
    total = 0
    found: bytes | None = None
    try:
        if asset.filename.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(raw)) as zip_archive:
                entries = zip_archive.infolist()
                if len(entries) > MAX_MEMBERS:
                    raise AcquisitionError("member_limit")
                for zip_info in entries:
                    _remaining(deadline)
                    name = _name(zip_info.filename, seen)
                    mode = stat.S_IFMT(zip_info.external_attr >> 16)
                    directory = zip_info.is_dir()
                    if (
                        mode not in (0, stat.S_IFDIR if directory else stat.S_IFREG)
                        or (zip_info.external_attr & 0x10 and not directory)
                        or (directory and zip_info.file_size != 0)
                        or zip_info.external_attr & 0x400
                        or zip_info.flag_bits & 1
                    ):
                        raise AcquisitionError("special_archive_member")
                    total += zip_info.file_size
                    if total > MAX_EXPANDED_BYTES:
                        raise AcquisitionError("expansion_limit")
                    if name == asset.member:
                        if zip_info.is_dir() or zip_info.file_size > MAX_EXECUTABLE_BYTES:
                            raise AcquisitionError("executable_limit")
                        with zip_archive.open(zip_info) as zip_stream:
                            found = _bounded_bytes(zip_stream, MAX_EXECUTABLE_BYTES, deadline)
                        if len(found) != zip_info.file_size:
                            raise AcquisitionError("member_size_mismatch")
                    elif PurePosixPath(name).name.casefold() in ("uv", "uv.exe"):
                        raise AcquisitionError("unexpected_executable")
        else:
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                expanded = _bounded_bytes(compressed, MAX_EXPANDED_BYTES, deadline)
            _admit_tar_headers(expanded, deadline)
            with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as tar_archive:
                for count, tar_info in enumerate(tar_archive, start=1):
                    _remaining(deadline)
                    if count > MAX_MEMBERS:
                        raise AcquisitionError("member_limit")
                    name = _name(tar_info.name, seen)
                    if tar_info.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
                        raise AcquisitionError("special_archive_member")
                    total += tar_info.size
                    if total > MAX_EXPANDED_BYTES:
                        raise AcquisitionError("expansion_limit")
                    if name == asset.member:
                        if not tar_info.isfile() or tar_info.size > MAX_EXECUTABLE_BYTES:
                            raise AcquisitionError("executable_limit")
                        tar_stream = tar_archive.extractfile(tar_info)
                        if tar_stream is None:
                            raise AcquisitionError("missing_executable")
                        with tar_stream:
                            found = _bounded_bytes(tar_stream, MAX_EXECUTABLE_BYTES, deadline)
                        if len(found) != tar_info.size:
                            raise AcquisitionError("member_size_mismatch")
                    elif PurePosixPath(name).name.casefold() in ("uv", "uv.exe"):
                        raise AcquisitionError("unexpected_executable")
    except (OSError, EOFError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        raise AcquisitionError("invalid_archive") from error
    if not found:
        raise AcquisitionError("missing_executable")
    return found


def _record(root: Path, asset: Asset, executable: Path, digest: str) -> dict[str, object]:
    return {
        "expected_version": VERSION,
        "source": SOURCE,
        "asset": asset.filename,
        "archive_sha256": asset.sha256,
        "archive_bytes": asset.size,
        "executable_sha256": digest,
        "uv_path": str(executable.resolve(strict=True)),
        "bootstrap": _bootstrap(),
    }


def acquire(root: Path, runner_temp: Path, platform_name: str) -> dict[str, object]:
    """Authenticate one exact official archive into a previously absent owned root."""
    deadline = time.monotonic() + ATTEMPT_SECONDS
    _bootstrap()
    asset = _asset(platform_name)
    root = _root(root, runner_temp, fresh=True)
    archive = root / ("archive.zip" if asset.filename.endswith(".zip") else "archive.tar.gz")
    _download(asset, archive, deadline)
    raw = _read_file(archive, MAX_ARCHIVE_BYTES)
    if len(raw) != asset.size or hashlib.sha256(raw).hexdigest() != asset.sha256:
        raise AcquisitionError("archive_identity_mismatch")
    payload = _payload(asset, raw, deadline)
    executable = root / "bin" / ("uv.exe" if asset.system == "Windows" else "uv")
    with _new_file(executable) as output:
        output.write(payload)
    if os.name != "nt":
        executable.chmod(0o700)
    result = _record(root, asset, executable, hashlib.sha256(payload).hexdigest())
    _remaining(deadline)
    with _new_file(root / "acquisition.json") as output:
        output.write((json.dumps(result, sort_keys=True) + "\n").encode())
    return result


def verify(root: Path, runner_temp: Path, platform_name: str) -> dict[str, object]:
    """Recompute identity against fixed archive pins, never trusting record digests."""
    deadline = time.monotonic() + ATTEMPT_SECONDS
    _bootstrap()
    asset = _asset(platform_name)
    root = _root(root, runner_temp, fresh=False)
    archive = root / ("archive.zip" if asset.filename.endswith(".zip") else "archive.tar.gz")
    raw = _read_file(archive, MAX_ARCHIVE_BYTES)
    if len(raw) != asset.size or hashlib.sha256(raw).hexdigest() != asset.sha256:
        raise AcquisitionError("archive_identity_mismatch")
    payload = _payload(asset, raw, deadline)
    executable = root / "bin" / ("uv.exe" if asset.system == "Windows" else "uv")
    actual = _read_file(executable, MAX_EXECUTABLE_BYTES)
    if actual != payload:
        raise AcquisitionError("executable_identity_mismatch")
    result = _record(root, asset, executable, hashlib.sha256(actual).hexdigest())
    try:
        record = json.loads(_read_file(root / "acquisition.json", 16384))
    except (ValueError, UnicodeError) as error:
        raise AcquisitionError("invalid_record") from error
    if not isinstance(record, dict) or set(record) != set(result):
        raise AcquisitionError("invalid_record")
    if any(record[key] != value for key, value in result.items() if key != "bootstrap"):
        raise AcquisitionError("record_identity_mismatch")
    _remaining(deadline)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("acquire", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--runner-temp", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=tuple(ASSETS))
    args = parser.parse_args()
    try:
        if not sys.flags.isolated or not sys.dont_write_bytecode:
            raise AcquisitionError("isolated_bootstrap_required")
        operation = acquire if args.operation == "acquire" else verify
        result = operation(args.root, args.runner_temp, args.platform)
        print(json.dumps(result, sort_keys=True))
    except (AcquisitionError, OSError) as error:
        code = str(error) if isinstance(error, AcquisitionError) else "filesystem_error"
        print(f"uv acquisition error: {code}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
