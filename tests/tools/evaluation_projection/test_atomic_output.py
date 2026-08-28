"""Tests for atomic, non-destructive evaluation projection output."""

from __future__ import annotations

import errno
import importlib.util
import os
from pathlib import Path
from typing import Protocol, cast

import pytest
from tools.evaluation_projection.atomic_output import (
    AtomicOutputError,
    write_projection_bytes,
)

from tools.evaluation_projection import atomic_output

type _PathInput = str | bytes | os.PathLike[str] | os.PathLike[bytes]


class _AtomicOutputModule(Protocol):
    AtomicOutputError: type[AtomicOutputError]

    def write_projection_bytes(
        self, destination: Path, payload: bytes, *, overwrite: bool = False
    ) -> None: ...


def _load_atomic_output_platform_variant() -> _AtomicOutputModule:
    module_path = atomic_output.__file__
    assert module_path is not None
    specification = importlib.util.spec_from_file_location(
        "atomic_output_platform_variant", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return cast(_AtomicOutputModule, module)


def _temporary_files(directory: Path) -> tuple[Path, ...]:
    return tuple(directory.glob(".projection.json.*.tmp"))


def _error_code(callable_: object, *args: object, **kwargs: object) -> AtomicOutputError:
    with pytest.raises(AtomicOutputError) as caught:
        assert callable(callable_)
        callable_(*args, **kwargs)
    return caught.value


def _variant_error(
    module: _AtomicOutputModule, destination: Path, payload: bytes
) -> AtomicOutputError:
    with pytest.raises(module.AtomicOutputError) as caught:
        module.write_projection_bytes(destination, payload)
    return caught.value


def test_installs_complete_new_output_without_temporary_state(tmp_path: Path) -> None:
    output = tmp_path / "projection.json"

    write_projection_bytes(output, b"new\n")

    assert output.read_bytes() == b"new\n"
    assert _temporary_files(tmp_path) == ()


def test_refuses_existing_output_without_overwrite_and_preserves_bytes(tmp_path: Path) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_exists"
    assert not error.installed
    assert str(error) == "output_exists"
    assert output.read_bytes() == b"old\n"
    assert _temporary_files(tmp_path) == ()


def test_explicit_overwrite_replaces_only_regular_output(tmp_path: Path) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")

    write_projection_bytes(output, b"new\n", overwrite=True)

    assert output.read_bytes() == b"new\n"
    assert _temporary_files(tmp_path) == ()


@pytest.mark.parametrize("overwrite", (False, True))
def test_rejects_symlink_destination_without_following_target(
    tmp_path: Path, overwrite: bool
) -> None:
    target = tmp_path / "target.json"
    target.write_bytes(b"old\n")
    output = tmp_path / "projection.json"
    output.symlink_to(target)

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=overwrite)

    assert error.code == ("output_install_failed" if overwrite else "output_exists")
    assert not error.installed
    assert output.is_symlink()
    assert target.read_bytes() == b"old\n"
    assert _temporary_files(tmp_path) == ()


def test_rejects_symlink_parent_and_preserves_existing_target_bytes(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    output = tmp_path / "linked" / "projection.json"
    (tmp_path / "linked").symlink_to(real_parent, target_is_directory=True)
    (real_parent / "projection.json").write_bytes(b"old\n")

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert (real_parent / "projection.json").read_bytes() == b"old\n"
    assert _temporary_files(real_parent) == ()


def test_rejects_symlink_ancestor_and_preserves_existing_target_bytes(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_parent = real_root / "nested"
    real_parent.mkdir(parents=True)
    output = tmp_path / "linked" / "nested" / "projection.json"
    (tmp_path / "linked").symlink_to(real_root, target_is_directory=True)
    (real_parent / "projection.json").write_bytes(b"old\n")

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert (real_parent / "projection.json").read_bytes() == b"old\n"
    assert _temporary_files(real_parent) == ()


def test_rejects_parent_swap_after_validation_without_redirecting_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    protected_parent = tmp_path / "protected"
    protected_parent.mkdir()
    displaced_parent = tmp_path / "displaced"
    output = parent / "projection.json"
    real_resolve = Path.resolve

    def swap_parent_after_validation(path: Path, *, strict: bool = False) -> Path:
        resolved = real_resolve(path, strict=strict)
        if path == parent:
            parent.rename(displaced_parent)
            parent.symlink_to(protected_parent, target_is_directory=True)
        return resolved

    monkeypatch.setattr(Path, "resolve", swap_parent_after_validation)

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not (protected_parent / "projection.json").exists()
    assert not (displaced_parent / "projection.json").exists()


def test_rejects_missing_parent_without_creating_it(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing"
    output = missing_parent / "projection.json"

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not missing_parent.exists()
    assert _temporary_files(tmp_path) == ()


def test_rejects_non_directory_parent_without_temporary_state(tmp_path: Path) -> None:
    parent = tmp_path / "not-a-directory"
    parent.write_bytes(b"old\n")

    error = _error_code(write_projection_bytes, parent / "projection.json", b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert parent.read_bytes() == b"old\n"
    assert _temporary_files(tmp_path) == ()


def test_rejects_ambiguous_destination_type_when_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "projection.json"
    output.mkdir()

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert output.is_dir()
    assert _temporary_files(tmp_path) == ()


def test_write_sync_failure_preserves_old_output_and_removes_owned_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")

    def fail_file_sync(fd: int) -> None:
        raise OSError(errno.EIO, "file sync failed")

    monkeypatch.setattr(os, "fsync", fail_file_sync)

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert output.read_bytes() == b"old\n"
    assert _temporary_files(tmp_path) == ()


def test_no_overwrite_race_preserves_racer_output_and_removes_owned_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    real_open = os.open
    real_write = os.write

    def race(
        source: _PathInput,
        destination: _PathInput,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del source, src_dir_fd, follow_symlinks
        assert dst_dir_fd is not None
        descriptor = real_open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=dst_dir_fd,
        )
        try:
            real_write(descriptor, b"racer\n")
        finally:
            os.close(descriptor)
        raise FileExistsError(errno.EEXIST, "already exists")

    monkeypatch.setattr(os, "link", race)
    monkeypatch.setattr(os, "supports_dir_fd", frozenset((*os.supports_dir_fd, race)))
    monkeypatch.setattr(
        os,
        "supports_follow_symlinks",
        frozenset((*os.supports_follow_symlinks, race)),
    )

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_exists"
    assert not error.installed
    assert output.read_bytes() == b"racer\n"
    assert _temporary_files(tmp_path) == ()


def test_replacement_failure_preserves_old_output_and_removes_owned_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")

    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError(errno.EIO, "replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert output.read_bytes() == b"old\n"
    assert _temporary_files(tmp_path) == ()


def test_directory_sync_failure_keeps_complete_new_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")
    real_fsync = os.fsync
    calls = 0

    def fail_second_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(errno.EIO, "directory sync failed")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_second_fsync)

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_directory_sync_failed"
    assert error.installed
    assert output.read_bytes() == b"new\n"
    assert _temporary_files(tmp_path) == ()


def test_descriptor_close_failure_before_install_is_a_stable_preinstall_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")
    real_close = os.close
    calls = 0

    def fail_first_close(fd: int) -> None:
        nonlocal calls
        calls += 1
        real_close(fd)
        if calls == 1:
            raise OSError(errno.EIO, "close failed")

    monkeypatch.setattr(os, "close", fail_first_close)

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not error.cleanup_failed
    assert output.read_bytes() == b"old\n"


def test_cleanup_failure_after_install_is_reported_without_hiding_new_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    real_unlink = os.unlink
    calls = 0

    def fail_first_unlink(path: _PathInput, *, dir_fd: int | None = None) -> None:
        nonlocal calls
        if dir_fd is None:
            real_unlink(path)
            return
        calls += 1
        if calls == 1:
            raise OSError(errno.EIO, "temporary unlink failed")
        real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "unlink", fail_first_unlink)
    monkeypatch.setattr(
        os,
        "supports_dir_fd",
        frozenset((*os.supports_dir_fd, fail_first_unlink)),
    )

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_cleanup_failed"
    assert error.installed
    assert error.cleanup_failed
    assert output.read_bytes() == b"new\n"


def test_preinstall_primary_error_records_cleanup_failure_without_masking_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")
    real_fsync = os.fsync
    real_unlink = os.unlink
    fsync_calls = 0

    def fail_file_sync(fd: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 1:
            raise OSError(errno.EIO, "file sync failed")
        real_fsync(fd)

    def fail_unlink(path: _PathInput, *, dir_fd: int | None = None) -> None:
        if dir_fd is None:
            real_unlink(path)
            return
        raise OSError(errno.EIO, "temporary unlink failed")

    monkeypatch.setattr(os, "fsync", fail_file_sync)
    monkeypatch.setattr(os, "unlink", fail_unlink)
    monkeypatch.setattr(os, "supports_dir_fd", frozenset((*os.supports_dir_fd, fail_unlink)))

    error = _error_code(write_projection_bytes, output, b"new\n", overwrite=True)

    assert error.code == "output_install_failed"
    assert not error.installed
    assert error.cleanup_failed
    assert output.read_bytes() == b"old\n"


def test_postinstall_directory_sync_error_is_not_masked_by_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    real_fsync = os.fsync
    real_close = os.close
    fsync_calls = 0

    def fail_directory_sync(fd: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 2:
            raise OSError(errno.EIO, "directory sync failed")
        real_fsync(fd)

    def fail_close(fd: int) -> None:
        real_close(fd)
        if fsync_calls >= 2:
            raise OSError(errno.EIO, "close failed")

    monkeypatch.setattr(os, "fsync", fail_directory_sync)
    monkeypatch.setattr(os, "close", fail_close)

    error = _error_code(write_projection_bytes, output, b"new\n")

    assert error.code == "output_directory_sync_failed"
    assert error.installed
    assert error.cleanup_failed
    assert output.read_bytes() == b"new\n"


@pytest.mark.parametrize(
    "unsupported_errno",
    tuple(
        dict.fromkeys(
            (
                errno.EINVAL,
                errno.ENOTSUP,
                getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
            )
        )
    ),
)
def test_unsupported_directory_sync_is_best_effort_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsupported_errno: int
) -> None:
    output = tmp_path / "projection.json"
    real_fsync = os.fsync
    calls = 0

    def fail_second_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(unsupported_errno, "directory sync unsupported")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_second_fsync)

    write_projection_bytes(output, b"new\n")

    assert output.read_bytes() == b"new\n"
    assert _temporary_files(tmp_path) == ()


def test_missing_directory_flag_is_a_stable_install_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"

    with monkeypatch.context() as platform:
        platform.delattr(os, "O_DIRECTORY")
        module = _load_atomic_output_platform_variant()

        error = _variant_error(module, output, b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not output.exists()
    assert _temporary_files(tmp_path) == ()


def test_missing_link_follow_symlink_capability_is_a_stable_install_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    without_link_follow = frozenset(
        operation for operation in os.supports_follow_symlinks if operation is not os.link
    )

    with monkeypatch.context() as platform:
        platform.setattr(os, "supports_follow_symlinks", without_link_follow)
        module = _load_atomic_output_platform_variant()

        error = _variant_error(module, output, b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not output.exists()
    assert _temporary_files(tmp_path) == ()


def test_rejected_link_follow_symlink_keyword_is_a_stable_install_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"

    def reject_link_follow_symlinks(
        source: _PathInput,
        destination: _PathInput,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        del source, destination, src_dir_fd, dst_dir_fd, follow_symlinks
        raise TypeError("follow_symlinks is unsupported")

    with monkeypatch.context() as platform:
        platform.setattr(os, "link", reject_link_follow_symlinks)
        platform.setattr(
            os,
            "supports_dir_fd",
            frozenset((*os.supports_dir_fd, reject_link_follow_symlinks)),
        )
        platform.setattr(
            os,
            "supports_follow_symlinks",
            frozenset((*os.supports_follow_symlinks, reject_link_follow_symlinks)),
        )
        module = _load_atomic_output_platform_variant()

        error = _variant_error(module, output, b"new\n")

    assert error.code == "output_install_failed"
    assert not error.installed
    assert not output.exists()
    assert _temporary_files(tmp_path) == ()
