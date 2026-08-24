from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

import pytest
from src.contracts.pocket import bundle as bundle_module
from src.contracts.pocket.bundle import BundleFileV1, build_contract_bundle, verify_contract_bundle
from src.contracts.pocket.canonical import PocketContractError

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "contracts/pocket/v1"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _copy_source(destination: Path) -> None:
    for path in SOURCE.rglob("*"):
        target = destination / path.relative_to(SOURCE)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def test_two_builds_are_byte_identical_and_self_verifying(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_receipt = build_contract_bundle(SOURCE, first)
    second_receipt = build_contract_bundle(SOURCE, second)

    assert first_receipt == second_receipt
    assert _tree_digest(first) == _tree_digest(second)
    assert verify_contract_bundle(first) == first_receipt
    assert asdict(first_receipt) == {
        "bundle_digest": first_receipt.bundle_digest,
        "content_root": first_receipt.content_root,
        "file_count": first_receipt.file_count,
    }


def test_build_publishes_into_an_existing_empty_destination(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    receipt = build_contract_bundle(SOURCE, destination)

    assert verify_contract_bundle(destination) == receipt


def test_tamper_extra_file_and_nonempty_destination_fail_closed(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_contract_bundle(SOURCE, bundle)
    schema = bundle / "schemas/document.schema.json"
    schema.write_bytes(schema.read_bytes() + b" ")
    with pytest.raises(PocketContractError, match="bundle_digest_mismatch"):
        verify_contract_bundle(bundle)

    extra = tmp_path / "extra"
    build_contract_bundle(SOURCE, extra)
    (extra / "unexpected").write_text("x", encoding="utf-8")
    with pytest.raises(PocketContractError, match="unexpected_bundle_file"):
        verify_contract_bundle(extra)

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep").write_text("keep", encoding="utf-8")
    with pytest.raises(PocketContractError, match="output_not_empty"):
        build_contract_bundle(SOURCE, occupied)
    assert (occupied / "keep").read_text(encoding="utf-8") == "keep"


def test_verifier_rejects_missing_renamed_and_mutated_manifest(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    build_contract_bundle(SOURCE, missing)
    (missing / "schemas/document.schema.json").unlink()
    with pytest.raises(PocketContractError, match="missing_bundle_file"):
        verify_contract_bundle(missing)

    renamed = tmp_path / "renamed"
    build_contract_bundle(SOURCE, renamed)
    (renamed / "schemas/document.schema.json").rename(renamed / "schemas/renamed.json")
    with pytest.raises(PocketContractError, match="unexpected_bundle_file"):
        verify_contract_bundle(renamed)

    manifest = tmp_path / "manifest"
    build_contract_bundle(SOURCE, manifest)
    manifest_path = manifest / "bundle-manifest.json"
    manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
    with pytest.raises(PocketContractError, match="bundle_digest_mismatch"):
        verify_contract_bundle(manifest)

    duplicate = tmp_path / "duplicate"
    build_contract_bundle(SOURCE, duplicate)
    manifest_path = duplicate / "bundle-manifest.json"
    manifest_payload = json.loads(manifest_path.read_bytes())
    manifest_payload["files"].append(manifest_payload["files"][0])
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    with pytest.raises(PocketContractError, match="invalid_bundle_manifest"):
        verify_contract_bundle(duplicate)


def test_build_and_verify_reject_symlink_roots_and_entries(tmp_path: Path) -> None:
    source_link = tmp_path / "source-link"
    source_link.symlink_to(SOURCE, target_is_directory=True)
    with pytest.raises(PocketContractError, match="unsafe_source_root"):
        build_contract_bundle(source_link, tmp_path / "output")

    output_target = tmp_path / "output-target"
    output_target.mkdir()
    output_link = tmp_path / "output-link"
    output_link.symlink_to(output_target, target_is_directory=True)
    with pytest.raises(PocketContractError, match="unsafe_output_(parent|root)"):
        build_contract_bundle(SOURCE, output_link)

    source = tmp_path / "source"
    _copy_source(source)
    (source / "schemas/link.json").symlink_to(source / "schemas/document.schema.json")
    with pytest.raises(PocketContractError, match="nonregular_source_file"):
        build_contract_bundle(source, tmp_path / "bundle")

    bundle = tmp_path / "bundle-verify"
    build_contract_bundle(SOURCE, bundle)
    (bundle / "schemas/link.json").symlink_to(bundle / "schemas/document.schema.json")
    with pytest.raises(PocketContractError, match="nonregular_bundle_file"):
        verify_contract_bundle(bundle)


def test_rejects_ancestor_symlinks_and_overlong_bundle_paths(tmp_path: Path) -> None:
    real_source_parent = tmp_path / "real-source-parent"
    source = real_source_parent / "source"
    _copy_source(source)
    source_parent_link = tmp_path / "source-parent-link"
    source_parent_link.symlink_to(real_source_parent, target_is_directory=True)
    with pytest.raises(PocketContractError, match="unsafe_source_root"):
        build_contract_bundle(source_parent_link / "source", tmp_path / "output")

    real_output_parent = tmp_path / "real-output-parent"
    real_output_parent.mkdir()
    output_parent_link = tmp_path / "output-parent-link"
    output_parent_link.symlink_to(real_output_parent, target_is_directory=True)
    with pytest.raises(PocketContractError, match="unsafe_output_parent"):
        build_contract_bundle(SOURCE, output_parent_link / "nested" / "output")

    with pytest.raises(ValueError, match="unsafe_bundle_path"):
        BundleFileV1(path="x" * 4097, size_bytes=0, sha256="0" * 64)
    BundleFileV1(path="è" * 2048, size_bytes=0, sha256="0" * 64)
    with pytest.raises(ValueError, match="unsafe_bundle_path"):
        BundleFileV1(path="è" * 2049, size_bytes=0, sha256="0" * 64)


def test_rejects_fifo_unsafe_names_and_source_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _copy_source(source)
    fixture_body = "fixture-body-must-not-escape"
    (source / "unsafe\nname").write_text(fixture_body, encoding="utf-8")
    with pytest.raises(PocketContractError, match="unsafe_bundle_path") as captured:
        build_contract_bundle(source, tmp_path / "unsafe")
    assert str(captured.value) == "unsafe_bundle_path"
    assert fixture_body not in str(captured.value)
    assert str(source) not in str(captured.value)

    source = tmp_path / "source-manifest"
    _copy_source(source)
    (source / "bundle-manifest.json").write_bytes(b"{}")
    with pytest.raises(PocketContractError, match="source_bundle_manifest"):
        build_contract_bundle(source, tmp_path / "manifest")

    fifo_source = tmp_path / "fifo-source"
    _copy_source(fifo_source)
    fifo = fifo_source / "named-pipe"
    if not hasattr(os, "mkfifo"):
        pytest.skip("platform has no FIFO creation primitive")
    try:
        os.mkfifo(fifo)
    except OSError as error:
        pytest.skip(f"platform cannot create FIFO: {error.__class__.__name__}")
    assert stat.S_ISFIFO(fifo.lstat().st_mode)
    with pytest.raises(PocketContractError, match="nonregular_source_file"):
        build_contract_bundle(fifo_source, tmp_path / "fifo")

    bundle = tmp_path / "bundle-fifo"
    build_contract_bundle(SOURCE, bundle)
    output_fifo = bundle / "named-pipe"
    os.mkfifo(output_fifo)
    with pytest.raises(PocketContractError, match="nonregular_bundle_file"):
        verify_contract_bundle(bundle)


def test_caps_are_checked_before_reading_with_small_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_bytes(b"x")
    monkeypatch.setattr(bundle_module, "MAX_FILES", 1)
    build_contract_bundle(source, tmp_path / "one-file")
    (source / "two").write_bytes(b"y")
    with pytest.raises(PocketContractError, match="too_many_bundle_files"):
        build_contract_bundle(source, tmp_path / "too-many")
    assert not (tmp_path / "too-many").exists()

    monkeypatch.setattr(bundle_module, "MAX_FILES", 4_096)
    monkeypatch.setattr(bundle_module, "MAX_FILE_BYTES", 1)
    one_byte = tmp_path / "one-byte"
    one_byte.mkdir()
    (one_byte / "file").write_bytes(b"x")
    assert bundle_module._collect_source_files(one_byte)[0].size_bytes == 1
    (one_byte / "file").write_bytes(b"xy")
    with pytest.raises(PocketContractError, match="bundle_file_too_large"):
        bundle_module._collect_source_files(one_byte)

    monkeypatch.setattr(bundle_module, "MAX_FILE_BYTES", 2)
    monkeypatch.setattr(bundle_module, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(PocketContractError, match="bundle_too_large"):
        bundle_module._collect_source_files(one_byte)


def test_interrupted_staging_is_removed_and_destination_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    def _interrupt(*_args: object, **_kwargs: object) -> bytes:
        raise PocketContractError("interrupted_staging")

    monkeypatch.setattr(bundle_module, "_write_bundle_manifest", _interrupt)
    with pytest.raises(PocketContractError, match="interrupted_staging"):
        build_contract_bundle(SOURCE, destination)
    assert list(destination.iterdir()) == []
    assert list(tmp_path.glob(".destination.*")) == []


def test_descriptor_open_rejects_symlink_substitution_without_path_leak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    target = source / "data"
    target.write_bytes(b"safe")
    replacement = tmp_path / "fixture-body-must-not-leak"
    replacement.write_bytes(b"secret")
    original_open = os.open

    def _race(path: str | os.PathLike[str], flags: int, *args: int) -> int:
        if Path(path) == target:
            target.unlink()
            target.symlink_to(replacement)
        return original_open(path, flags, *args)

    monkeypatch.setattr(os, "open", _race)
    with pytest.raises(PocketContractError, match="source_changed") as captured:
        bundle_module._read_regular_file(target, expected_size=4, source=True)
    assert str(tmp_path) not in str(captured.value)
    assert "secret" not in str(captured.value)


def test_build_rejects_ancestor_substitution_between_root_check_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_parent = tmp_path / "selected-parent"
    selected_root = selected_parent / "source"
    selected_root.mkdir(parents=True)
    (selected_root / "data").write_bytes(b"safe")
    substitute_parent = tmp_path / "substitute-parent"
    substitute_root = substitute_parent / "source"
    substitute_root.mkdir(parents=True)
    (substitute_root / "data").write_bytes(b"evil")
    displaced_parent = tmp_path / "displaced-parent"
    original_open = os.open
    substituted = False

    def _substitute_ancestor(
        path: str | os.PathLike[str],
        flags: int,
        *args: int,
        **kwargs: int,
    ) -> int:
        nonlocal substituted
        if Path(path) == selected_root and kwargs.get("dir_fd") is None:
            selected_parent.replace(displaced_parent)
            substitute_parent.replace(selected_parent)
            substituted = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _substitute_ancestor)
    with pytest.raises(PocketContractError, match="unsafe_source_root"):
        build_contract_bundle(selected_root, tmp_path / "output")
    assert substituted
    assert not (tmp_path / "output").exists()


def test_verifier_rejects_ancestor_substitution_between_root_check_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_parent = tmp_path / "selected-parent"
    selected_parent.mkdir()
    selected_bundle = selected_parent / "bundle"
    build_contract_bundle(SOURCE, selected_bundle)
    substitute_source = tmp_path / "substitute-source"
    substitute_source.mkdir()
    (substitute_source / "different").write_bytes(b"evil")
    substitute_parent = tmp_path / "substitute-parent"
    substitute_parent.mkdir()
    substitute_bundle = substitute_parent / "bundle"
    build_contract_bundle(substitute_source, substitute_bundle)
    displaced_parent = tmp_path / "displaced-parent"
    original_open = os.open
    substituted = False

    def _substitute_ancestor(
        path: str | os.PathLike[str],
        flags: int,
        *args: int,
        **kwargs: int,
    ) -> int:
        nonlocal substituted
        if Path(path) == selected_bundle and kwargs.get("dir_fd") is None:
            selected_parent.replace(displaced_parent)
            substitute_parent.replace(selected_parent)
            substituted = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _substitute_ancestor)
    with pytest.raises(PocketContractError, match="unsafe_bundle_root"):
        verify_contract_bundle(selected_bundle)
    assert substituted


def test_build_rejects_output_ancestor_substitution_before_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected_parent = tmp_path / "selected-parent"
    selected_parent.mkdir()
    output = selected_parent / "output"
    substitute_parent = tmp_path / "substitute-parent"
    substitute_parent.mkdir()
    displaced_parent = tmp_path / "displaced-parent"
    original_mkdir = os.mkdir
    substituted = False

    def _substitute_output_parent(
        path: str | os.PathLike[str],
        mode: int = 0o777,
        *args: int,
        **kwargs: int,
    ) -> None:
        nonlocal substituted
        candidate = Path(path)
        if candidate.name.startswith(".output.") and not substituted:
            selected_parent.replace(displaced_parent)
            substitute_parent.replace(selected_parent)
            substituted = True
        original_mkdir(path, mode, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", _substitute_output_parent)
    with pytest.raises(PocketContractError, match="^unsafe_output_parent$"):
        build_contract_bundle(SOURCE, output)
    assert substituted
    assert not output.exists()
    assert not list(displaced_parent.glob(".output.*"))


def test_public_filesystem_errors_are_normalized_and_caps_precede_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_bytes(b"x")
    original_read = bundle_module._read_regular_file
    monkeypatch.setattr(bundle_module, "MAX_FILES", 0)
    monkeypatch.setattr(
        bundle_module, "_read_regular_file", lambda *_args, **_kwargs: pytest.fail("read")
    )
    with pytest.raises(PocketContractError, match="too_many_bundle_files"):
        bundle_module._collect_source_files(source)

    monkeypatch.setattr(bundle_module, "MAX_FILES", 4_096)
    monkeypatch.setattr(bundle_module, "_read_regular_file", original_read)
    monkeypatch.setattr(os, "write", lambda *_args: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PocketContractError, match="bundle_write_failed") as captured:
        build_contract_bundle(SOURCE, tmp_path / "output")
    assert str(tmp_path) not in str(captured.value)


def test_prevalidation_permission_errors_are_content_free_contract_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    original_iterdir = Path.iterdir

    def _deny_output(path: Path) -> Iterator[Path]:
        if path == destination:
            raise PermissionError("private-output-path")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", _deny_output)
    with pytest.raises(PocketContractError, match="^unsafe_output_root$") as captured:
        build_contract_bundle(SOURCE, destination)
    assert captured.value.__cause__ is None
    assert "private-output-path" not in str(captured.value)


def test_all_source_caps_are_enforced_before_any_content_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_bytes(b"x")
    (source / "two").write_bytes(b"y")
    monkeypatch.setattr(os, "read", lambda *_args: pytest.fail("content read"))

    monkeypatch.setattr(bundle_module, "MAX_FILES", 1)
    with pytest.raises(PocketContractError, match="^too_many_bundle_files$"):
        build_contract_bundle(source, tmp_path / "too-many")

    monkeypatch.setattr(bundle_module, "MAX_FILES", 4_096)
    monkeypatch.setattr(bundle_module, "MAX_TOTAL_BYTES", 1)
    with pytest.raises(PocketContractError, match="^bundle_too_large$"):
        build_contract_bundle(source, tmp_path / "too-large")


def test_manifest_byte_and_file_caps_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        json,
        "loads",
        lambda *_args, **_kwargs: pytest.fail("oversized manifest reached parser"),
    )
    with pytest.raises(PocketContractError, match="^bundle_file_too_large$"):
        bundle_module._manifest_from_bytes(b" " * (bundle_module.MAX_FILE_BYTES + 1))

    monkeypatch.undo()
    monkeypatch.setattr(bundle_module, "MAX_FILES", 1)
    manifest_bytes = json.dumps(
        {
            "bundle_version": "matryca-pocket-contract-bundle.v1",
            "content_root": "0" * 64,
            "files": [
                {"path": "one", "sha256": "1" * 64, "size_bytes": 1},
                {"path": "two", "sha256": "2" * 64, "size_bytes": 1},
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with pytest.raises(PocketContractError, match="^too_many_bundle_files$"):
        bundle_module._manifest_from_bytes(manifest_bytes)


def test_manifest_race_and_entry_total_caps_fail_before_parse_or_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    build_contract_bundle(SOURCE, bundle)
    manifest = bundle / "bundle-manifest.json"
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"{}")
    original_open = os.open

    def _race(
        path: str | os.PathLike[str],
        flags: int,
        *args: int,
        **kwargs: int,
    ) -> int:
        if Path(path) == Path(manifest.name) and kwargs.get("dir_fd") is not None:
            manifest.unlink()
            manifest.symlink_to(replacement)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", _race)
    with pytest.raises(PocketContractError, match="bundle_digest_mismatch"):
        verify_contract_bundle(bundle)

    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_bytes(b"xx")
    monkeypatch.setattr(bundle_module, "MAX_TOTAL_BYTES", 1)
    monkeypatch.setattr(
        bundle_module, "_read_regular_file", lambda *_args, **_kwargs: pytest.fail("read")
    )
    with pytest.raises(PocketContractError, match="bundle_too_large"):
        bundle_module._collect_source_files(source)

    monkeypatch.setattr(bundle_module, "MAX_DIRECTORY_ENTRIES", 0)
    with pytest.raises(PocketContractError, match="too_many_bundle_entries"):
        bundle_module._bounded_entries(source, code="source_changed")


def test_publish_rollback_and_cleanup_failure_are_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "file").write_bytes(b"x")
    original_rename = os.rename

    def _fail_publish(
        source: str | os.PathLike[str],
        target: str | os.PathLike[str],
        *args: int,
        **kwargs: int,
    ) -> None:
        if Path(source) == Path(staging.name):
            raise OSError("publish")
        original_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "rename", _fail_publish)
    with pytest.raises(PocketContractError, match="bundle_publish_failed"):
        bundle_module._publish_staging(staging, destination)
    assert destination.exists() and list(destination.iterdir()) == []

    cleanup = tmp_path / "cleanup"
    cleanup.mkdir()
    original_rmdir = os.rmdir

    def _fail_cleanup(
        path: str | os.PathLike[str],
        *args: int,
        **kwargs: int,
    ) -> None:
        if Path(path) == Path(cleanup.name):
            raise OSError("cleanup")
        original_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "rmdir", _fail_cleanup)
    with pytest.raises(PocketContractError, match="staging_cleanup_failed"):
        bundle_module._remove_staging(cleanup)


def test_publish_rollback_failure_uses_distinct_honest_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "file").write_bytes(b"x")
    original_rename = os.rename

    def _fail_publish_and_rollback(
        source: str | os.PathLike[str],
        target: str | os.PathLike[str],
        *args: int,
        **kwargs: int,
    ) -> None:
        source_name = Path(source).name
        if source_name == staging.name or ".destination.backup-" in source_name:
            raise OSError("replace")
        original_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(os, "rename", _fail_publish_and_rollback)
    with pytest.raises(PocketContractError, match="^bundle_publish_rollback_failed$"):
        bundle_module._publish_staging(staging, destination)
    assert not destination.exists()
    assert list(tmp_path.glob(".destination.backup-*"))


def test_post_publish_cleanup_failure_rolls_back_existing_empty_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    original_rmdir = os.rmdir

    def _fail_backup(
        path: str | os.PathLike[str],
        *args: int,
        **kwargs: int,
    ) -> None:
        if ".destination.backup-" in Path(path).name:
            raise OSError("cleanup")
        original_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "rmdir", _fail_backup)
    with pytest.raises(PocketContractError, match="staging_cleanup_failed"):
        build_contract_bundle(SOURCE, destination)
    assert destination.exists() and list(destination.iterdir()) == []
