"""Atomic installation of closed evaluation projection bytes."""

from __future__ import annotations

import errno
import os
import stat
import tempfile
from pathlib import Path

_UNSUPPORTED_DIRECTORY_SYNC_ERRNOS = frozenset(
    (errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP))
)


class AtomicOutputError(RuntimeError):
    """A stable content-free projection output failure."""

    def __init__(self, code: str, *, installed: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.installed = installed


def _normalised_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _require_real_parent(destination: Path) -> Path:
    parent = _normalised_absolute(destination.parent)
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError:
        raise AtomicOutputError("output_install_failed") from None
    if resolved_parent != parent or not resolved_parent.is_dir():
        raise AtomicOutputError("output_install_failed")
    return parent


def _require_absent_destination(destination: Path) -> None:
    try:
        destination.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise AtomicOutputError("output_install_failed") from None
    raise AtomicOutputError("output_exists")


def _require_regular_or_absent_destination(destination: Path) -> None:
    try:
        status = destination.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise AtomicOutputError("output_install_failed") from None
    if not stat.S_ISREG(status.st_mode):
        raise AtomicOutputError("output_install_failed")


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as error:
        if error.errno in _UNSUPPORTED_DIRECTORY_SYNC_ERRNOS:
            return
        raise AtomicOutputError("output_directory_sync_failed", installed=True) from None
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in _UNSUPPORTED_DIRECTORY_SYNC_ERRNOS:
                raise AtomicOutputError(
                    "output_directory_sync_failed", installed=True
                ) from None
    finally:
        os.close(descriptor)


def write_projection_bytes(
    destination: Path, payload: bytes, *, overwrite: bool = False
) -> None:
    """Install ``payload`` atomically without following unsafe output paths."""
    destination = _normalised_absolute(destination)
    parent = _require_real_parent(destination)
    if overwrite:
        _require_regular_or_absent_destination(destination)
    else:
        _require_absent_destination(destination)

    temporary: Path | None = None
    try:
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=str(parent)
            )
        except OSError:
            raise AtomicOutputError("output_install_failed") from None
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            raise AtomicOutputError("output_install_failed") from None

        if overwrite:
            _require_regular_or_absent_destination(destination)
            try:
                os.replace(temporary, destination)
            except OSError:
                raise AtomicOutputError("output_install_failed") from None
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise AtomicOutputError("output_exists") from None
            except OSError:
                raise AtomicOutputError("output_install_failed") from None
            temporary.unlink()

        _fsync_directory(parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


__all__ = ["AtomicOutputError", "write_projection_bytes"]
