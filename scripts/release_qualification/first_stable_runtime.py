"""Authenticate and safely unpack a selected first-stable CPython archive."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import posixpath
import stat
import tarfile
from pathlib import Path, PurePosixPath

_MAX_COMPRESSED = 80 * 1024 * 1024
_MAX_EXPANDED = 288 * 1024 * 1024
_MAX_MEMBERS = 6_000
_MINORS = {"3.12.16": "3.12", "3.13.18": "3.13"}


def _member_path(name: str) -> PurePosixPath:
    if (
        not name.isascii()
        or len(name) > 1024
        or any(ord(character) < 32 or ord(character) == 127 for character in name)
        or "\\" in name
        or not (name == "python" or name.startswith("python/"))
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise ValueError("Unexpected runtime archive member path.")
    return PurePosixPath(name)


def _inventory(
    archive: tarfile.TarFile, *, case_sensitive: bool
) -> dict[PurePosixPath, tarfile.TarInfo]:
    members: dict[PurePosixPath, tarfile.TarInfo] = {}
    spellings: dict[str, PurePosixPath] = {}
    for item in archive:
        path = _member_path(item.name)
        if len(members) >= _MAX_MEMBERS or path in members:
            raise ValueError("Duplicate or excessive runtime archive members.")
        if not (item.isfile() or item.isdir() or item.issym()) or item.issparse():
            raise ValueError("Runtime archive member type is not permitted.")
        if item.size < 0 or item.size > _MAX_EXPANDED or (not item.isfile() and item.size != 0):
            raise ValueError("Invalid runtime archive member size.")
        if not case_sensitive:
            for prefix in (path, *path.parents):
                key = str(prefix).casefold()
                if spellings.setdefault(key, prefix) != prefix:
                    raise ValueError("Case-insensitive runtime archive name collision.")
        members[path] = item
    for path, item in members.items():
        if any(parent in members and not members[parent].isdir() for parent in path.parents):
            raise ValueError("Runtime archive member would traverse a non-directory.")
        if item.issym():
            _require_internal_link(path, members)
    return members


def _require_internal_link(
    start: PurePosixPath, members: dict[PurePosixPath, tarfile.TarInfo]
) -> None:
    path = start
    seen: set[PurePosixPath] = set()
    while members[path].issym():
        if path in seen:
            raise ValueError("Runtime archive contains a symlink cycle.")
        seen.add(path)
        link = members[path].linkname
        tail = link
        while tail.startswith("../"):
            tail = tail[3:]
        _member_path("python/" + tail)
        path = _member_path(posixpath.normpath(str(path.parent / link)))
        if path not in members:
            raise ValueError("Runtime archive symlink has no authenticated target.")
    if not members[path].isfile():
        raise ValueError("Runtime archive symlink does not target a regular file.")


def extract_runtime(
    archive: Path,
    destination: Path,
    version: str,
    expected_size: int,
    expected_sha256: str,
    *,
    case_sensitive: bool,
) -> Path:
    """Extract exact bytes to a fresh directory in a task-owned parent.

    Pass an independent archive identity. This operation is byte-only and
    cannot establish a native startup, ABI or license conclusion. The caller
    must enforce an operation deadline and supply the actual filesystem policy.
    """
    minor = _MINORS.get(version)
    if minor is None or type(expected_size) is not int or not 0 < expected_size <= _MAX_COMPRESSED:
        raise ValueError("Unsupported runtime version or archive size.")
    if (
        not destination.is_absolute()
        or destination.parent.resolve(strict=True) != destination.parent
    ):
        raise ValueError("Runtime destination parent must be canonical and task-owned.")
    fd = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != expected_size:
            raise ValueError("Runtime archive is not the expected regular file.")
        compressed = stream.read(expected_size + 1)
    if (
        len(compressed) != expected_size
        or hashlib.sha256(compressed).hexdigest() != expected_sha256
    ):
        raise ValueError("Runtime archive digest does not match the admitted input.")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as zipped:
        expanded = zipped.read(_MAX_EXPANDED + 1)
    if len(expanded) > _MAX_EXPANDED:
        raise ValueError("Runtime archive exceeds the expanded size limit.")
    executable = PurePosixPath(f"python/bin/python{minor}")
    notice = PurePosixPath(f"python/lib/python{minor}/LICENSE.txt")
    with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as unpack:
        members = _inventory(unpack, case_sensitive=case_sensitive)
        if any(path not in members or not members[path].isfile() for path in (executable, notice)):
            raise ValueError("Runtime archive lacks its regular executable or license notice.")
        if not members[executable].mode & stat.S_IXUSR or members[notice].size == 0:
            raise ValueError("Runtime archive executable or license notice is invalid.")
        destination.mkdir(mode=0o700)
        unpack.extractall(destination, members=members.values(), filter="data")
    return destination / executable
