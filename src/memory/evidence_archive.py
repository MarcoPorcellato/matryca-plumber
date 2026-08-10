"""Append-only, idempotent local archive for P0 evidence events.

The archive has no automatic capture path.  Callers must explicitly provide an
already privacy-safe :class:`EvidenceEvent`.  It never writes to the Logseq
graph and never reads, opens, or initializes Shadow DB.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

from ..utils.platform_lock import cross_process_sidecar_lock
from .evidence_location import (
    EvidenceArchiveLocation,
    EvidenceArchiveLocationError,
    resolve_evidence_archive_location,
)
from .evidence_models import EvidenceContractError, EvidenceEvent, canonical_event_bytes

_MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
_MAX_TORN_RECORD_BYTES = 1024 * 1024


class EvidenceArchiveError(ValueError):
    """A content-free archive integrity or persistence failure."""


@dataclass(frozen=True, slots=True)
class EvidenceAppendResult:
    """Idempotent outcome of recording one immutable event."""

    event_id: str
    appended: bool


class EvidenceArchive:
    """One graph-scoped evidence archive with crash-tolerant JSONL replay."""

    def __init__(self, location: EvidenceArchiveLocation) -> None:
        _validate_location(location)
        self._location = location

    @property
    def location(self) -> EvidenceArchiveLocation:
        return self._location

    @classmethod
    def for_graph(
        cls,
        graph_root: Path | str,
        *,
        env: Mapping[str, str] | None = None,
        platform_name: str | None = None,
        home: Path | None = None,
    ) -> EvidenceArchive:
        return cls(
            resolve_evidence_archive_location(
                graph_root,
                env=env,
                platform_name=platform_name,
                home=home,
            )
        )

    def append(self, event: EvidenceEvent) -> EvidenceAppendResult:
        """Append one event once, with fsync under a cross-process writer lock."""
        if not isinstance(event, EvidenceEvent):
            raise EvidenceArchiveError("invalid_event")
        event_id = event.event_id
        payload = canonical_event_bytes(event)
        try:
            self._location.ensure_directory()
            with _writer_lock(self._location.writer_lock_path):
                separator = _prepare_append_tail(self._location.events_path)
                records = tuple(_read_events(self._location.events_path))
                if any(existing.event_id == event_id for existing in records):
                    return EvidenceAppendResult(event_id=event_id, appended=False)
                _append_bytes(self._location.events_path, separator + payload + b"\n")
        except (EvidenceArchiveLocationError, EvidenceContractError) as exc:
            raise EvidenceArchiveError("archive_location_or_contract_invalid") from exc
        except OSError as exc:
            raise EvidenceArchiveError("archive_write_failed") from exc
        return EvidenceAppendResult(event_id=event_id, appended=True)

    def events(self) -> tuple[EvidenceEvent, ...]:
        """Replay complete immutable records; ignore only a torn final line."""
        try:
            return tuple(_read_events(self._location.events_path))
        except (EvidenceArchiveLocationError, EvidenceContractError) as exc:
            raise EvidenceArchiveError("archive_integrity_invalid") from exc
        except OSError as exc:
            raise EvidenceArchiveError("archive_read_failed") from exc


def _append_bytes(path: Path, payload: bytes) -> None:
    with _open_no_follow(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600) as handle:
        if os.name == "posix":
            os.fchmod(handle, 0o600)
        remaining = memoryview(payload)
        while remaining:
            written = os.write(handle, remaining)
            if written <= 0:
                raise OSError("evidence archive short write")
            remaining = remaining[written:]
        os.fsync(handle)


def _prepare_append_tail(path: Path) -> bytes:
    """Repair a torn final record or return the needed record separator.

    This runs only while the archive writer lock is held.  A valid, complete
    record without a trailing newline is retained; an invalid final fragment is
    the only data that may be removed, and the truncation is durably synced
    before a new record is appended.
    """
    if not path.exists():
        return b""
    if path.is_symlink():
        raise EvidenceArchiveLocationError("events_path_symlink")
    raw = path.read_bytes()
    if not raw or raw.endswith(b"\n"):
        return b""
    last_newline = raw.rfind(b"\n")
    tail = raw[last_newline + 1 :]
    try:
        parsed = json.loads(tail)
        if not isinstance(parsed, dict):
            raise EvidenceContractError("invalid_record")
        EvidenceEvent.from_dict(parsed)
    except (UnicodeDecodeError, json.JSONDecodeError, EvidenceContractError):
        if not tail.startswith(b"{") or len(tail) > _MAX_TORN_RECORD_BYTES:
            raise EvidenceArchiveError("archive_torn_record_unrecoverable") from None
        _truncate_to(path, last_newline + 1)
        return b""
    return b"\n"


def _truncate_to(path: Path, size: int) -> None:
    with _open_no_follow(path, os.O_WRONLY) as handle:
        os.ftruncate(handle, size)
        os.fsync(handle)


def _read_events(path: Path) -> Iterable[EvidenceEvent]:
    if not path.exists():
        return ()
    raw = _read_bounded_bytes(path)
    lines = raw.splitlines(keepends=True)
    records: list[EvidenceEvent] = []
    for index, line in enumerate(lines):
        is_final_torn_line = index == len(lines) - 1 and not line.endswith((b"\n", b"\r"))
        try:
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise EvidenceContractError("invalid_record")
            records.append(EvidenceEvent.from_dict(parsed))
        except (UnicodeDecodeError, json.JSONDecodeError, EvidenceContractError) as exc:
            if is_final_torn_line:
                break
            raise EvidenceArchiveError("archive_record_invalid") from exc
    return tuple(records)


def _validate_location(location: EvidenceArchiveLocation) -> None:
    """Reject hand-assembled locations that evade the external-cache policy."""
    expected = resolve_evidence_archive_location(
        location.graph_root,
        env={"MATRYCA_CACHE_PATH": str(location.cache_root)},
    )
    if location != expected:
        raise EvidenceArchiveLocationError("archive_location_mismatch")


@contextmanager
def _writer_lock(lock_path: Path) -> Iterator[None]:
    """Acquire the archive lock without following a substituted lock symlink."""
    if os.name != "posix":
        with cross_process_sidecar_lock(
            lock_path,
            depth_key=str(lock_path.resolve(strict=False)),
            unavailable_label="evidence archive writer lock",
        ):
            yield
        return

    try:
        import fcntl
    except ImportError:  # pragma: no cover - guarded by os.name
        with cross_process_sidecar_lock(
            lock_path,
            depth_key=str(lock_path.resolve(strict=False)),
            unavailable_label="evidence archive writer lock",
        ):
            yield
        return
    with _open_no_follow(lock_path, os.O_RDWR | os.O_CREAT, 0o600) as handle:
        if os.name == "posix":
            os.fchmod(handle, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            with suppress(OSError):
                fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def _open_no_follow(path: Path, flags: int, mode: int = 0o600) -> Iterator[int]:
    """Open a regular archive file without following its final symlink."""
    if path.is_symlink():
        raise EvidenceArchiveLocationError("events_path_symlink")
    try:
        fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), mode)
    except OSError as exc:
        if path.is_symlink():
            raise EvidenceArchiveLocationError("events_path_symlink") from exc
        raise
    try:
        yield fd
    finally:
        os.close(fd)


def _read_bounded_bytes(path: Path) -> bytes:
    try:
        size = path.stat().st_size
    except OSError:
        raise
    if size > _MAX_ARCHIVE_BYTES:
        raise EvidenceArchiveError("archive_size_limit_exceeded")
    with _open_no_follow(path, os.O_RDONLY) as handle:
        chunks: list[bytes] = []
        remaining = _MAX_ARCHIVE_BYTES + 1
        while remaining:
            chunk = os.read(handle, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    if len(raw) > _MAX_ARCHIVE_BYTES:
        raise EvidenceArchiveError("archive_size_limit_exceeded")
    return raw


__all__ = [
    "EvidenceAppendResult",
    "EvidenceArchive",
    "EvidenceArchiveError",
]
