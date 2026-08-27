"""Tests for atomic, non-destructive evaluation projection output."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from tools.evaluation_projection.atomic_output import (
    AtomicOutputError,
    write_projection_bytes,
)


def _temporary_files(directory: Path) -> tuple[Path, ...]:
    return tuple(directory.glob(".projection.json.*.tmp"))


def _error_code(callable_: object, *args: object, **kwargs: object) -> AtomicOutputError:
    with pytest.raises(AtomicOutputError) as caught:
        assert callable(callable_)
        callable_(*args, **kwargs)
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

    def race(source: Path, destination: Path, *args: object, **kwargs: object) -> None:
        del source, args, kwargs
        destination.write_bytes(b"racer\n")
        raise FileExistsError(errno.EEXIST, "already exists")

    monkeypatch.setattr(os, "link", race)

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
