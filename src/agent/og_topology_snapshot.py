"""Private finite capture for quiescent OG graphs; not an atomic snapshot protocol."""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root
from .og_parser_identity_adapter import (
    _file_identity,
    _OgSnapshotReadError,
    _require_regular_source,
)

MAX_CAPTURE_FILES = 1024
MAX_CAPTURE_FILE_BYTES = 1024 * 1024
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_CAPTURE_ENTRIES = 8192
MAX_CAPTURE_DIRECTORIES = 1024
MAX_CAPTURE_DEPTH = 32
_DESCRIPTOR_CAPABLE = (
    os.open in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
    and os.scandir in os.supports_fd
    and all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"))
)


@dataclass(frozen=True)
class CapturedOgPage:
    logical_path: str
    content: bytes
    sha256: str


@dataclass(frozen=True)
class OgTopologyCapture:
    pages: tuple[CapturedOgPage, ...]
    source_revision: str


@dataclass
class _DirectoryFrame:
    descriptor: int
    logical_path: str
    depth: int
    entries: Iterator[os.DirEntry[str]]
    resources: ExitStack


def _require_directory(metadata: os.stat_result) -> None:
    if not stat.S_ISDIR(metadata.st_mode):
        raise _OgSnapshotReadError("source_rejected", "OG topology source rejected")


@contextmanager
def _directory_descriptor(name: str | Path, *, parent: int | None) -> Iterator[int]:
    """Open relative to the retained parent; never resolve a discovered directory link."""
    if not _DESCRIPTOR_CAPABLE:
        raise _OgSnapshotReadError("source_rejected", "OG topology descriptor access unavailable")
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    _require_directory(before)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, dir_fd=parent)
    try:
        opened = os.fstat(descriptor)
        _require_directory(opened)
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise _OgSnapshotReadError("source_changed", "OG topology directory changed")
        yield descriptor
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _require_directory(after)
        if (opened.st_dev, opened.st_ino) != (after.st_dev, after.st_ino):
            raise _OgSnapshotReadError("source_changed", "OG topology directory changed")
    finally:
        os.close(descriptor)


def _frame(parent: int, name: str, logical_path: str, depth: int) -> _DirectoryFrame:
    resources = ExitStack()
    try:
        descriptor = resources.enter_context(_directory_descriptor(name, parent=parent))
        entries = resources.enter_context(os.scandir(descriptor))
        return _DirectoryFrame(descriptor, logical_path, depth, entries, resources)
    except BaseException:
        resources.close()
        raise


def _capture_page(parent: int, name: str, logical_path: str, remaining: int) -> CapturedOgPage:
    """Preserve descriptor-bound reader checks without reopening a mutable parent path."""
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    _require_regular_source(before)
    maximum = min(MAX_CAPTURE_FILE_BYTES, remaining)
    if before.st_size > maximum:
        raise _OgSnapshotReadError("bounds_exceeded", "OG topology byte limit exceeded")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    descriptor = os.open(name, flags, dir_fd=parent)
    try:
        opened = os.fstat(descriptor)
        _require_regular_source(opened)
        if _file_identity(before) != _file_identity(opened):
            raise _OgSnapshotReadError("source_changed", "OG snapshot changed during read")
        if opened.st_size > maximum:
            raise _OgSnapshotReadError("bounds_exceeded", "OG topology byte limit exceeded")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read(maximum + 1)
        after = os.stat(name, dir_fd=parent, follow_symlinks=False)
        _require_regular_source(after)
        if len(content) > maximum or after.st_size > maximum:
            raise _OgSnapshotReadError("bounds_exceeded", "OG topology byte limit exceeded")
        if _file_identity(opened) != _file_identity(after):
            raise _OgSnapshotReadError("source_changed", "OG snapshot changed during read")
    finally:
        os.close(descriptor)
    content.decode("utf-8")
    return CapturedOgPage(logical_path, content, hashlib.sha256(content).hexdigest())


def _close_frames(frames: list[_DirectoryFrame]) -> None:
    """A failed frame finalizer cannot suppress closing the remaining owned frames."""
    primary = sys.exception()
    first_error: BaseException | None = None
    while frames:
        try:
            frames.pop().resources.close()
        except BaseException as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        if primary is not None:
            primary.add_note("OG topology directory cleanup failed")
        else:
            raise first_error


def _admit_og_topology_root(root: Path) -> Path:
    """Reject differing root interpretations before any Markdown capture."""
    try:
        if root.is_symlink():
            raise _OgSnapshotReadError("source_rejected", "OG topology source rejected")
        lexical = Path(os.path.abspath(root))
        resolved = resolved_graph_root(root)
    except _OgSnapshotReadError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        raise _OgSnapshotReadError("source_rejected", "OG topology source rejected") from exc
    if lexical != resolved:
        raise _OgSnapshotReadError("source_rejected", "OG topology root interpretation rejected")
    return resolved


def capture_og_topology(root: Path) -> OgTopologyCapture:
    """Capture only the two admitted subtrees, with finite work before every descent/read."""
    root = _admit_og_topology_root(root)
    pages: list[CapturedOgPage] = []
    total_bytes = 0
    visited = 0
    directories = 1  # The selected root is depth zero and counts as one directory.
    frames: list[_DirectoryFrame] = []
    try:
        with _directory_descriptor(root, parent=None) as root_descriptor:
            for name in ("pages", "journals"):
                try:
                    metadata = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                visited += 1
                if visited > MAX_CAPTURE_ENTRIES or directories >= MAX_CAPTURE_DIRECTORIES:
                    raise _OgSnapshotReadError("bounds_exceeded", "OG topology walk limit exceeded")
                _require_directory(metadata)
                directories += 1
                frames.append(_frame(root_descriptor, name, name, 1))
                try:
                    while frames:
                        current = frames[-1]
                        try:
                            entry = next(current.entries)
                        except StopIteration:
                            frames.pop().resources.close()
                            continue
                        visited += 1
                        if visited > MAX_CAPTURE_ENTRIES:
                            raise _OgSnapshotReadError(
                                "bounds_exceeded", "OG topology entry limit exceeded"
                            )
                        metadata = entry.stat(follow_symlinks=False)
                        logical_path = f"{current.logical_path}/{entry.name}"
                        logical_path.encode("utf-8")
                        if "\\" in entry.name:
                            raise _OgSnapshotReadError(
                                "source_rejected", "OG topology source rejected"
                            )
                        if stat.S_ISDIR(metadata.st_mode):
                            depth = current.depth + 1
                            if depth > MAX_CAPTURE_DEPTH or directories >= MAX_CAPTURE_DIRECTORIES:
                                raise _OgSnapshotReadError(
                                    "bounds_exceeded", "OG topology walk limit exceeded"
                                )
                            directories += 1
                            frames.append(
                                _frame(current.descriptor, entry.name, logical_path, depth)
                            )
                        else:
                            _require_regular_source(metadata)
                            if not entry.name.endswith(".md"):
                                continue
                            if len(pages) >= MAX_CAPTURE_FILES:
                                raise _OgSnapshotReadError(
                                    "bounds_exceeded", "OG topology page limit exceeded"
                                )
                            page = _capture_page(
                                current.descriptor,
                                entry.name,
                                logical_path,
                                MAX_CAPTURE_BYTES - total_bytes,
                            )
                            total_bytes += len(page.content)
                            pages.append(page)
                finally:
                    _close_frames(frames)
    except _OgSnapshotReadError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise _OgSnapshotReadError("source_rejected", "OG topology capture rejected") from exc
    pages.sort(key=lambda page: page.logical_path.encode("utf-8"))
    revision = hashlib.sha256()
    for page in pages:
        logical_bytes = page.logical_path.encode("utf-8")
        revision.update(len(logical_bytes).to_bytes(4, "big"))
        revision.update(logical_bytes)
        revision.update(len(page.content).to_bytes(8, "big"))
        revision.update(page.content)
    return OgTopologyCapture(tuple(pages), revision.hexdigest())


def verify_og_topology_capture(root: Path, capture: OgTopologyCapture) -> None:
    """Reject observed set/byte changes; double capture cannot detect ABA or ensure atomicity."""
    try:
        current = capture_og_topology(root)
    except _OgSnapshotReadError as exc:
        raise _OgSnapshotReadError("source_changed", "OG topology source changed") from exc
    if current != capture:
        raise _OgSnapshotReadError("source_changed", "OG topology source changed")
