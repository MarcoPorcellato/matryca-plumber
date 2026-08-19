#!/usr/bin/env python3
"""Run the deterministic, content-free interoperability TCK admission check."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST: Final[Path] = ROOT / "tests/compatibility/manifest.json"
MAX_MANIFEST_BYTES: Final[int] = 1_048_576
MAX_CATALOG_ENTRIES: Final[int] = 256
MAX_STRING_LENGTH: Final[int] = 512
ALLOWED_FIXTURE_ROOT: Final[PurePosixPath] = PurePosixPath("tests/fixtures")
CapabilityLevel = Literal[
    "read",
    "safe-derived-cache",
    "closed-writer",
    "concurrent-writer-not-supported",
]
DeclaredExpectedResult = Literal[
    "pass",
    "partial",
    "unsupported",
    "rejected",
    "no-serve",
    "fixture-available",
    "error",
]


class CatalogEntry(BaseModel):
    """One bounded manifest admission record."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    fixture_path: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    category: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    capability_level: CapabilityLevel
    expected_result: DeclaredExpectedResult
    source_authority: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    notes: str | None = Field(default=None, max_length=MAX_STRING_LENGTH)


class CompatibilityManifest(BaseModel):
    """Bounded manifest envelope; it contains no fixture content."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["matryca-interop-tck.v1"]
    status: str = Field(min_length=1, max_length=MAX_STRING_LENGTH)
    catalog: list[CatalogEntry] = Field(max_length=MAX_CATALOG_ENTRIES)


class TckError(ValueError):
    """Raised when the manifest or an approved fixture cannot be admitted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_relative_fixture(entry: CatalogEntry, repository_root: Path) -> tuple[str, Path]:
    relative = PurePosixPath(entry.fixture_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise TckError(f"{entry.id}: fixture_path must not be absolute or traverse")
    if not relative.parts or relative.parts[:2] != ALLOWED_FIXTURE_ROOT.parts:
        raise TckError(f"{entry.id}: fixture_path must be under tests/fixtures")

    candidate = (repository_root / Path(*relative.parts)).resolve(strict=False)
    fixture_root = (repository_root / Path(*ALLOWED_FIXTURE_ROOT.parts)).resolve()
    try:
        candidate.relative_to(fixture_root)
    except ValueError as exc:
        raise TckError(f"{entry.id}: fixture_path escapes tests/fixtures") from exc
    return relative.as_posix(), candidate


def _load_manifest(manifest_path: Path) -> tuple[CompatibilityManifest, bytes]:
    if not manifest_path.is_file():
        raise TckError("manifest is missing or is not a file")
    raw = manifest_path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise TckError("manifest exceeds the bounded size limit")
    try:
        manifest = CompatibilityManifest.model_validate_json(raw)
    except ValidationError as exc:
        raise TckError(f"manifest validation failed: {exc.error_count()} error(s)") from exc
    seen_ids: set[str] = set()
    for entry in manifest.catalog:
        if entry.id in seen_ids:
            raise TckError(f"manifest contains duplicate catalogue entry id: {entry.id}")
        seen_ids.add(entry.id)
    return manifest, raw


def build_receipt(manifest_path: Path, *, repository_root: Path = ROOT) -> dict[str, object]:
    """Build a deterministic receipt without reading fixture data into memory."""
    manifest, raw_manifest = _load_manifest(manifest_path)
    entries: list[dict[str, object]] = []
    for entry in manifest.catalog:
        relative, fixture = _repository_relative_fixture(entry, repository_root)
        if not fixture.is_file():
            raise TckError(f"{entry.id}: fixture is missing or is not a file")
        entries.append(
            {
                "id": entry.id,
                "fixture_path": relative,
                "fixture_size_bytes": fixture.stat().st_size,
                "fixture_sha256": _sha256(fixture),
                "category": entry.category,
                "capability_level": entry.capability_level,
                "source_authority": entry.source_authority,
                "declared_expected_result": entry.expected_result,
            }
        )
    return {
        "runner": "matryca-interop-tck-admission-v1",
        "receipt_kind": "deterministic-fixture-attestation",
        "scope": "manifest-and-fixture-bytes",
        "manifest_schema_version": manifest.schema_version,
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "status": manifest.status,
        "entries": entries,
        "non_goals": [
            "semantic interoperability qualification",
            "Tine qualification",
            "concurrent-write support",
            "graph mutation",
        ],
    }


def run_tck(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    output_path: Path | None = None,
    repository_root: Path = ROOT,
) -> str:
    """Return the receipt, optionally writing it once to an explicit new file."""
    receipt = build_receipt(manifest_path, repository_root=repository_root)
    serialized = (
        json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    )
    if output_path is not None:
        if output_path.exists():
            raise TckError("refusing to overwrite existing output file")
        output_path.write_text(serialized, encoding="utf-8", newline="\n")
    return serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = run_tck(args.manifest, output_path=args.output)
    except (OSError, TckError) as exc:
        print(f"interop TCK admission rejected: {exc}", file=sys.stderr)
        return 2
    if args.output is None:
        print(receipt, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
