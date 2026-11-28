"""Synthetic installed-record and import-origin checks for S3 probes."""

from __future__ import annotations

import base64
import csv
import hashlib
from pathlib import Path

import pytest
from scripts.release_qualification.first_stable_s3_probe import (
    ProbeError,
    check_module,
    verify_record,
)


def _record_digest(raw: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode("ascii").rstrip("=")
    return f"sha256={digest}"


def _write_record(site: Path, metadata: bytes, extra: tuple[str, str, str] | None = None) -> Path:
    dist_info = site / "matryca_plumber-2.1.0rc1.dist-info"
    dist_info.mkdir(parents=True)
    metadata_path = dist_info / "METADATA"
    metadata_path.write_bytes(metadata)
    record_path = dist_info / "RECORD"
    rows = [
        (
            "matryca_plumber-2.1.0rc1.dist-info/METADATA",
            _record_digest(metadata),
            str(len(metadata)),
        )
    ]
    if extra is not None:
        rows.append(extra)
    rows.append(("matryca_plumber-2.1.0rc1.dist-info/RECORD", "", ""))
    with record_path.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)
    return metadata_path


def test_verify_record_accepts_authenticated_metadata(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    site = prefix / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    metadata = _write_record(site, b"Name: matryca-plumber\nVersion: 2.1.0rc1\n")

    verified, record_digest = verify_record(site, prefix, "matryca-plumber")

    assert verified == {metadata}
    assert len(record_digest) == 64


def test_verify_record_rejects_tampered_metadata(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    site = prefix / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    metadata = _write_record(site, b"Name: matryca-plumber\nVersion: 2.1.0rc1\n")
    metadata.write_bytes(b"Name: matryca-plumber\nVersion: 2.1.0rc2\n")

    with pytest.raises(ProbeError, match="RECORD digest differs"):
        verify_record(site, prefix, "matryca-plumber")


def test_verify_record_rejects_path_escape(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix"
    site = prefix / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside the selected prefix")
    _write_record(
        site,
        b"Name: matryca-plumber\nVersion: 2.1.0rc1\n",
        (
            "../../../../outside.txt",
            _record_digest(outside.read_bytes()),
            str(outside.stat().st_size),
        ),
    )

    with pytest.raises(ProbeError, match="outside its owned root"):
        verify_record(site, prefix, "matryca-plumber")


def test_check_module_rejects_origin_not_in_verified_record(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    package = site / "example_package"
    package.mkdir(parents=True)
    origin = package / "__init__.py"
    origin.write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ProbeError, match="not hashed installed payload"):
        check_module("example_package", site, set())
