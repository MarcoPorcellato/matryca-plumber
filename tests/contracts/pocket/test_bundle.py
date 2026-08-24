from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import asdict
from pathlib import Path

import pytest
from src.contracts.pocket import bundle as bundle_module
from src.contracts.pocket.bundle import build_contract_bundle, verify_contract_bundle
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
    with pytest.raises(PocketContractError, match="unsafe_output_root"):
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
