"""Tests for the deterministic interoperability TCK admission runner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_interop_tck import DEFAULT_MANIFEST, run_tck, TckError

ROOT = Path(__file__).resolve().parents[1]


def _manifest(
    tmp_path: Path,
    fixture_path: str,
    *,
    schema_version: str = "matryca-interop-tck.v1",
    expected_result: str = "fixture-available",
) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "status": "proposed",
                "catalog": [
                    {
                        "id": "case",
                        "fixture_path": fixture_path,
                        "category": "test",
                        "capability_level": "read",
                        "expected_result": expected_result,
                        "source_authority": "test",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_happy_manifest_contains_only_manifest_results_and_fixture_attestations() -> None:
    receipt = json.loads(run_tck(DEFAULT_MANIFEST))

    assert len(receipt["entries"]) == 7
    assert {entry["declared_expected_result"] for entry in receipt["entries"]} == {
        "pass",
        "rejected",
        "no-serve",
        "fixture-available",
        "unsupported",
    }
    assert all("content" not in entry for entry in receipt["entries"])
    assert receipt["non_goals"]


def test_unsupported_schema_version_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        "tests/fixtures/tana/minimal_direct.json",
        schema_version="test-v1",
    )

    with pytest.raises(TckError, match="validation failed"):
        run_tck(manifest, repository_root=ROOT)


def test_invalid_declared_result_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        "tests/fixtures/tana/minimal_direct.json",
        expected_result="executed-pass",
    )

    with pytest.raises(TckError, match="validation failed"):
        run_tck(manifest, repository_root=ROOT)


def test_traversal_fixture_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "tests/fixtures/../compatibility/manifest.json")

    with pytest.raises(TckError, match="traverse"):
        run_tck(manifest, repository_root=ROOT)


def test_missing_fixture_is_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "tests/fixtures/does-not-exist.json")

    with pytest.raises(TckError, match="missing"):
        run_tck(manifest, repository_root=ROOT)


def test_receipt_is_deterministic(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "tests/fixtures/tana/minimal_direct.json")

    assert run_tck(manifest, repository_root=ROOT) == run_tck(manifest, repository_root=ROOT)


def test_output_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "receipt.json"
    output.write_text("keep me", encoding="utf-8")

    with pytest.raises(TckError, match="overwrite"):
        run_tck(DEFAULT_MANIFEST, output_path=output)
    assert output.read_text(encoding="utf-8") == "keep me"
