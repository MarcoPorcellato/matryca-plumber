"""Atomic installation of closed evaluation projection bytes."""

from __future__ import annotations

import errno
import os
import secrets
import stat
from contextlib import suppress
from pathlib import Path

_UNSUPPORTED_DIRECTORY_SYNC_ERRNOS = frozenset(
    (errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP))
)
_MAX_TEMPORARY_NAME_ATTEMPTS = 32


class AtomicOutputError(RuntimeError):
    """A stable content-free projection output failure."""

    def __init__(self, code: str, *, installed: bool = False, cleanup_failed: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.installed = installed
        self.cleanup_failed = cleanup_failed


def _normalised_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _identity(status: os.stat_result) -> tuple[int, int]:
    return status.st_dev, status.st_ino


def _directory_flags() -> int:
    directory_flag = getattr(os, "O_DIRECTORY", None)
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(directory_flag, int) or not isinstance(nofollow_flag, int):
        raise AtomicOutputError("output_install_failed")
    return os.O_RDONLY | directory_flag | nofollow_flag


def _temporary_file_flags() -> int:
    nofollow_flag = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(nofollow_flag, int):
        raise AtomicOutputError("output_install_failed")
    return os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow_flag


def _require_relative_directory_apis() -> None:
    _directory_flags()
    _temporary_file_flags()
    supported_dir_fd = getattr(os, "supports_dir_fd", ())
    supported_follow_symlinks = getattr(os, "supports_follow_symlinks", ())
    required_operations = (os.open, os.stat, os.mkdir, os.unlink, os.rmdir, os.link)
    if not all(operation in supported_dir_fd for operation in required_operations) or (
        os.link not in supported_follow_symlinks
    ):
        raise AtomicOutputError("output_install_failed")


def _require_real_parent(destination: Path) -> tuple[Path, tuple[int, int]]:
    parent = _normalised_absolute(destination.parent)
    try:
        resolved_parent = parent.resolve(strict=True)
        status = parent.stat(follow_symlinks=False)
    except OSError:
        raise AtomicOutputError("output_install_failed") from None
    if resolved_parent != parent or not stat.S_ISDIR(status.st_mode):
        raise AtomicOutputError("output_install_failed")
    return parent, _identity(status)


def _open_verified_directory(path: Path, expected_identity: tuple[int, int]) -> int:
    try:
        descriptor = os.open(path, _directory_flags())
    except OSError:
        raise AtomicOutputError("output_install_failed") from None
    try:
        if _identity(os.fstat(descriptor)) != expected_identity:
            raise AtomicOutputError("output_install_failed")
    except OSError:
        with suppress(OSError):
            os.close(descriptor)
        raise AtomicOutputError("output_install_failed") from None
    except AtomicOutputError:
        with suppress(OSError):
            os.close(descriptor)
        raise
    return descriptor


def _destination_status(parent_fd: int, destination_name: str) -> os.stat_result | None:
    try:
        return os.stat(destination_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise AtomicOutputError("output_install_failed") from None


def _require_destination_state(parent_fd: int, destination_name: str, *, overwrite: bool) -> None:
    status = _destination_status(parent_fd, destination_name)
    if status is None:
        return
    if not overwrite:
        raise AtomicOutputError("output_exists")
    if not stat.S_ISREG(status.st_mode):
        raise AtomicOutputError("output_install_failed")


def _new_temporary_name(destination_name: str) -> str:
    return f".{destination_name}.{secrets.token_hex(16)}.tmp"


def _create_private_directory(
    parent_fd: int, destination_name: str
) -> tuple[str, int, tuple[int, int]]:
    for _ in range(_MAX_TEMPORARY_NAME_ATTEMPTS):
        temporary_directory_name = _new_temporary_name(destination_name)
        try:
            os.mkdir(temporary_directory_name, mode=0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue
        except OSError:
            raise AtomicOutputError("output_install_failed") from None

        try:
            expected_identity = _identity(
                os.stat(
                    temporary_directory_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            )
            temporary_directory_fd = os.open(
                temporary_directory_name,
                _directory_flags(),
                dir_fd=parent_fd,
            )
            if _identity(os.fstat(temporary_directory_fd)) != expected_identity:
                with suppress(OSError):
                    os.close(temporary_directory_fd)
                raise AtomicOutputError("output_install_failed")
        except OSError:
            with suppress(OSError):
                os.rmdir(temporary_directory_name, dir_fd=parent_fd)
            raise AtomicOutputError("output_install_failed") from None
        except AtomicOutputError:
            with suppress(OSError):
                os.rmdir(temporary_directory_name, dir_fd=parent_fd)
            raise
        return temporary_directory_name, temporary_directory_fd, expected_identity
    raise AtomicOutputError("output_install_failed")


def _create_temporary_file(temporary_directory_fd: int) -> tuple[str, int]:
    for _ in range(_MAX_TEMPORARY_NAME_ATTEMPTS):
        temporary_name = secrets.token_hex(16)
        try:
            return temporary_name, os.open(
                temporary_name,
                _temporary_file_flags(),
                0o600,
                dir_fd=temporary_directory_fd,
            )
        except FileExistsError:
            continue
        except OSError:
            raise AtomicOutputError("output_install_failed") from None
    raise AtomicOutputError("output_install_failed")


def _write_and_sync(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    try:
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(errno.EIO, "short output write")
            view = view[written:]
        os.fsync(descriptor)
    except OSError:
        raise AtomicOutputError("output_install_failed") from None


def _close_before_install(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        raise AtomicOutputError("output_install_failed") from None


def _fsync_directory(parent_fd: int) -> None:
    try:
        os.fsync(parent_fd)
    except OSError as error:
        if error.errno not in _UNSUPPORTED_DIRECTORY_SYNC_ERRNOS:
            raise AtomicOutputError("output_directory_sync_failed", installed=True) from None


def _cleanup_file(temporary_directory_fd: int, temporary_name: str) -> bool:
    try:
        os.unlink(temporary_name, dir_fd=temporary_directory_fd)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return False


def _close_for_cleanup(descriptor: int) -> bool:
    try:
        os.close(descriptor)
    except OSError:
        return True
    return False


def _cleanup_private_directory(
    parent_fd: int,
    temporary_directory_name: str,
    temporary_directory_identity: tuple[int, int],
) -> bool:
    try:
        status = os.stat(
            temporary_directory_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return False
    except OSError:
        return True
    if not stat.S_ISDIR(status.st_mode) or _identity(status) != temporary_directory_identity:
        return True
    try:
        os.rmdir(temporary_directory_name, dir_fd=parent_fd)
    except OSError:
        return True
    return False


def write_projection_bytes(destination: Path, payload: bytes, *, overwrite: bool = False) -> None:
    """Install ``payload`` through descriptor-pinned, non-destructive output paths."""
    destination = _normalised_absolute(destination)
    _require_relative_directory_apis()
    parent, parent_identity = _require_real_parent(destination)
    parent_fd: int | None = None
    temporary_directory_name: str | None = None
    temporary_directory_fd: int | None = None
    temporary_directory_identity: tuple[int, int] | None = None
    temporary_name: str | None = None
    temporary_file_fd: int | None = None
    installed = False
    primary_error: AtomicOutputError | None = None
    cleanup_failed = False

    try:
        parent_fd = _open_verified_directory(parent, parent_identity)
        _require_destination_state(parent_fd, destination.name, overwrite=overwrite)
        (
            temporary_directory_name,
            temporary_directory_fd,
            temporary_directory_identity,
        ) = _create_private_directory(parent_fd, destination.name)
        temporary_name, temporary_file_fd = _create_temporary_file(temporary_directory_fd)
        _write_and_sync(temporary_file_fd, payload)
        descriptor_to_close = temporary_file_fd
        temporary_file_fd = None
        _close_before_install(descriptor_to_close)

        if overwrite:
            _require_destination_state(parent_fd, destination.name, overwrite=True)
            try:
                os.replace(
                    temporary_name,
                    destination.name,
                    src_dir_fd=temporary_directory_fd,
                    dst_dir_fd=parent_fd,
                )
            except (OSError, TypeError):
                raise AtomicOutputError("output_install_failed") from None
            temporary_name = None
        else:
            try:
                os.link(
                    temporary_name,
                    destination.name,
                    src_dir_fd=temporary_directory_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError:
                raise AtomicOutputError("output_exists") from None
            except (OSError, TypeError):
                raise AtomicOutputError("output_install_failed") from None
            installed = True
            if _cleanup_file(temporary_directory_fd, temporary_name):
                cleanup_failed = True
            else:
                temporary_name = None

        installed = True
        _fsync_directory(parent_fd)
    except AtomicOutputError as error:
        primary_error = error
    finally:
        if temporary_file_fd is not None:
            cleanup_failed = _close_for_cleanup(temporary_file_fd) or cleanup_failed
        if temporary_name is not None and temporary_directory_fd is not None:
            cleanup_failed = _cleanup_file(temporary_directory_fd, temporary_name) or cleanup_failed
        if temporary_directory_fd is not None:
            cleanup_failed = _close_for_cleanup(temporary_directory_fd) or cleanup_failed
        if (
            parent_fd is not None
            and temporary_directory_name is not None
            and temporary_directory_identity is not None
        ):
            cleanup_failed = (
                _cleanup_private_directory(
                    parent_fd,
                    temporary_directory_name,
                    temporary_directory_identity,
                )
                or cleanup_failed
            )
        if parent_fd is not None:
            cleanup_failed = _close_for_cleanup(parent_fd) or cleanup_failed

    if primary_error is not None:
        primary_error.cleanup_failed = cleanup_failed
        raise primary_error
    if cleanup_failed:
        raise AtomicOutputError("output_cleanup_failed", installed=installed, cleanup_failed=True)


__all__ = ["AtomicOutputError", "write_projection_bytes"]
