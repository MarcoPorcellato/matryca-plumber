from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .canonical import JsonValue, PocketContractError, canonical_json_bytes, canonical_json_sha256
from .models import DocumentV1, EvidenceV1, PackManifestV1

MAX_FILES: Final[int] = 4_096
MAX_FILE_BYTES: Final[int] = 32 * 1024 * 1024
MAX_TOTAL_BYTES: Final[int] = 256 * 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BUNDLE_MANIFEST = "bundle-manifest.json"
_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "schemas/document.schema.json": DocumentV1,
    "schemas/evidence.schema.json": EvidenceV1,
    "schemas/pack-manifest.schema.json": PackManifestV1,
}


class _ClosedBundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _schema_artifact_bytes(schema: object) -> bytes:
    return json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def render_schema_files() -> dict[str, bytes]:
    return {
        path: _schema_artifact_bytes(
            model.model_json_schema(
                mode="validation",
                ref_template="#/$defs/{model}",
            )
        )
        for path, model in sorted(_SCHEMA_MODELS.items())
    }


def _validate_bundle_path(value: str) -> None:
    path = PurePosixPath(value)
    raw_parts = value.split("/")
    if (
        not unicodedata.is_normalized("NFC", value)
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise PocketContractError("unsafe_bundle_path")


class BundleFileV1(_ClosedBundleModel):
    path: str
    size_bytes: int = Field(ge=0, le=MAX_FILE_BYTES)
    sha256: str

    @model_validator(mode="after")
    def _validate_file(self) -> BundleFileV1:
        _validate_bundle_path(self.path)
        if _SHA256.fullmatch(self.sha256) is None:
            raise PocketContractError("invalid_sha256")
        return self


def _files_payload(files: tuple[BundleFileV1, ...]) -> list[dict[str, JsonValue]]:
    return [cast(dict[str, JsonValue], item.model_dump(mode="json")) for item in files]


def _content_root(files: tuple[BundleFileV1, ...]) -> str:
    return canonical_json_sha256(cast(JsonValue, {"files": _files_payload(files)}))


class ContractBundleManifestV1(_ClosedBundleModel):
    bundle_version: Literal["matryca-pocket-contract-bundle.v1"]
    files: tuple[BundleFileV1, ...] = Field(max_length=MAX_FILES, strict=False)
    content_root: str

    @model_validator(mode="after")
    def _validate_manifest(self) -> ContractBundleManifestV1:
        if _SHA256.fullmatch(self.content_root) is None:
            raise PocketContractError("invalid_content_root")
        if tuple(sorted(self.files, key=lambda item: item.path)) != self.files:
            raise PocketContractError("noncanonical_order")
        if len({item.path for item in self.files}) != len(self.files):
            raise PocketContractError("duplicate_bundle_file")
        if _content_root(self.files) != self.content_root:
            raise PocketContractError("content_root_mismatch")
        return self


@dataclass(frozen=True, slots=True)
class BundleReceipt:
    bundle_digest: str
    content_root: str
    file_count: int


def _is_link_or_not_directory(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return True
    return stat.S_ISLNK(mode) or not stat.S_ISDIR(mode)


def _validate_source_root(source_root: Path) -> None:
    if _is_link_or_not_directory(source_root):
        raise PocketContractError("unsafe_source_root")


def _validate_output_root(output_dir: Path) -> None:
    parent = output_dir.parent
    if _is_link_or_not_directory(parent):
        raise PocketContractError("unsafe_output_parent")
    try:
        mode = output_dir.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise PocketContractError("unsafe_output_root")
    if any(output_dir.iterdir()):
        raise PocketContractError("output_not_empty")


def _read_regular_file(path: Path, *, expected_size: int, source: bool) -> bytes:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as error:
        raise PocketContractError("source_changed" if source else "missing_bundle_file") from error
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise PocketContractError("nonregular_source_file" if source else "nonregular_bundle_file")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise PocketContractError("bundle_file_too_large")
    if len(data) != expected_size:
        raise PocketContractError("source_changed" if source else "bundle_digest_mismatch")
    return data


def _collect_source_files(source_root: Path) -> tuple[BundleFileV1, ...]:
    _validate_source_root(source_root)
    files: list[BundleFileV1] = []
    total_size = 0
    entries = sorted(
        source_root.rglob("*"), key=lambda item: item.relative_to(source_root).as_posix()
    )
    for path in entries:
        relative_path = path.relative_to(source_root).as_posix()
        _validate_bundle_path(relative_path)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as error:
            raise PocketContractError("source_changed") from error
        if stat.S_ISLNK(mode):
            raise PocketContractError("nonregular_source_file")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise PocketContractError("nonregular_source_file")
        if relative_path == _BUNDLE_MANIFEST:
            raise PocketContractError("source_bundle_manifest")
        size = path.lstat().st_size
        if size > MAX_FILE_BYTES:
            raise PocketContractError("bundle_file_too_large")
        if len(files) >= MAX_FILES:
            raise PocketContractError("too_many_bundle_files")
        total_size += size
        if total_size > MAX_TOTAL_BYTES:
            raise PocketContractError("bundle_too_large")
        data = _read_regular_file(path, expected_size=size, source=True)
        files.append(
            BundleFileV1(
                path=relative_path,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return tuple(files)


def _write_bundle_manifest(files: tuple[BundleFileV1, ...]) -> bytes:
    manifest = ContractBundleManifestV1(
        bundle_version="matryca-pocket-contract-bundle.v1",
        files=files,
        content_root=_content_root(files),
    )
    payload = cast(JsonValue, manifest.model_dump(mode="json"))
    return canonical_json_bytes(payload)


def _manifest_from_bytes(data: bytes) -> ContractBundleManifestV1:
    try:
        value = json.loads(data)
        manifest = ContractBundleManifestV1.model_validate(value)
    except (json.JSONDecodeError, ValidationError, PocketContractError) as error:
        raise PocketContractError("invalid_bundle_manifest") from error
    if _write_bundle_manifest(manifest.files) != data:
        raise PocketContractError("bundle_digest_mismatch")
    return manifest


def _receipt(manifest: ContractBundleManifestV1, manifest_bytes: bytes) -> BundleReceipt:
    return BundleReceipt(
        bundle_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        content_root=manifest.content_root,
        file_count=len(manifest.files),
    )


def _verify_bundle_root(bundle_dir: Path) -> tuple[ContractBundleManifestV1, bytes]:
    if _is_link_or_not_directory(bundle_dir):
        raise PocketContractError("unsafe_bundle_root")
    entries = sorted(
        bundle_dir.rglob("*"), key=lambda item: item.relative_to(bundle_dir).as_posix()
    )
    observed: dict[str, tuple[Path, int]] = {}
    for path in entries:
        relative_path = path.relative_to(bundle_dir).as_posix()
        _validate_bundle_path(relative_path)
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as error:
            raise PocketContractError("bundle_changed") from error
        if stat.S_ISLNK(mode):
            raise PocketContractError("nonregular_bundle_file")
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise PocketContractError("nonregular_bundle_file")
        size = path.lstat().st_size
        if size > MAX_FILE_BYTES:
            raise PocketContractError("bundle_file_too_large")
        if relative_path in observed:
            raise PocketContractError("duplicate_bundle_file")
        observed[relative_path] = (path, size)
    manifest_entry = observed.pop(_BUNDLE_MANIFEST, None)
    if manifest_entry is None:
        raise PocketContractError("missing_bundle_manifest")
    manifest_bytes = _read_regular_file(
        manifest_entry[0], expected_size=manifest_entry[1], source=False
    )
    manifest = _manifest_from_bytes(manifest_bytes)
    expected = {item.path: item for item in manifest.files}
    unexpected = set(observed).difference(expected)
    if unexpected:
        raise PocketContractError("unexpected_bundle_file")
    missing = set(expected).difference(observed)
    if missing:
        raise PocketContractError("missing_bundle_file")
    if len(expected) > MAX_FILES:
        raise PocketContractError("too_many_bundle_files")
    total_size = 0
    for path_name, item in expected.items():
        path, announced_size = observed[path_name]
        if announced_size != item.size_bytes:
            raise PocketContractError("bundle_digest_mismatch")
        total_size += announced_size
        if total_size > MAX_TOTAL_BYTES:
            raise PocketContractError("bundle_too_large")
        data = _read_regular_file(path, expected_size=item.size_bytes, source=False)
        if hashlib.sha256(data).hexdigest() != item.sha256:
            raise PocketContractError("bundle_digest_mismatch")
    return manifest, manifest_bytes


def build_contract_bundle(source_root: Path, output_dir: Path) -> BundleReceipt:
    _validate_output_root(output_dir)
    files = _collect_source_files(source_root)
    staging_path: Path | None = None
    try:
        staging_path = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
        for item in files:
            source_path = source_root / PurePosixPath(item.path)
            data = _read_regular_file(source_path, expected_size=item.size_bytes, source=True)
            if hashlib.sha256(data).hexdigest() != item.sha256:
                raise PocketContractError("source_changed")
            destination_path = staging_path / PurePosixPath(item.path)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(data)
        manifest_bytes = _write_bundle_manifest(files)
        (staging_path / _BUNDLE_MANIFEST).write_bytes(manifest_bytes)
        manifest, verified_bytes = _verify_bundle_root(staging_path)
        receipt = _receipt(manifest, verified_bytes)
        _validate_output_root(output_dir)
        staging_path.replace(output_dir)
        staging_path = None
        return receipt
    finally:
        if staging_path is not None:
            shutil.rmtree(staging_path, ignore_errors=True)


def verify_contract_bundle(bundle_dir: Path) -> BundleReceipt:
    manifest, manifest_bytes = _verify_bundle_root(bundle_dir)
    return _receipt(manifest, manifest_bytes)


__all__ = ["BundleReceipt", "build_contract_bundle", "verify_contract_bundle"]
