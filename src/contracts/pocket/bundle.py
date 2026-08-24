from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal, Never, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .canonical import JsonValue, PocketContractError, canonical_json_bytes, canonical_json_sha256
from .models import DocumentV1, EvidenceV1, PackManifestV1

MAX_FILES: Final[int] = 4_096
MAX_FILE_BYTES: Final[int] = 32 * 1024 * 1024
MAX_TOTAL_BYTES: Final[int] = 256 * 1024 * 1024
MAX_PATH_BYTES: Final[int] = 4_096
MAX_DIRECTORY_ENTRIES: Final[int] = 32_768
_OPEN_SUPPORTS_DIR_FD: Final[bool] = os.open in os.supports_dir_fd
_SCANDIR_SUPPORTS_FD: Final[bool] = os.scandir in os.supports_fd
_STAT_SUPPORTS_FOLLOW_SYMLINKS: Final[bool] = os.stat in os.supports_follow_symlinks
_MUTATIONS_SUPPORT_DIR_FD: Final[bool] = all(
    function in os.supports_dir_fd
    for function in (os.mkdir, os.rename, os.stat, os.unlink, os.rmdir)
)
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
    try:
        encoded_length = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise PocketContractError("unsafe_bundle_path") from None
    if (
        not unicodedata.is_normalized("NFC", value)
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\\" in value
        or any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
        or encoded_length > MAX_PATH_BYTES
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


@dataclass(frozen=True, slots=True)
class _TreeEntry:
    path: str
    mode: int
    size_bytes: int
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _PublishTransaction:
    output_existed: bool
    backup_name: str | None


def _safe_open_flags(*, directory: bool) -> int:
    if (
        not hasattr(os, "O_NOFOLLOW")
        or (directory and not hasattr(os, "O_DIRECTORY"))
        or not _OPEN_SUPPORTS_DIR_FD
        or not _SCANDIR_SUPPORTS_FD
        or not _STAT_SUPPORTS_FOLLOW_SYMLINKS
        or not _MUTATIONS_SUPPORT_DIR_FD
    ):
        raise PocketContractError("safe_open_unsupported")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    if directory:
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _close_descriptor(descriptor: int, *, code: str) -> None:
    try:
        os.close(descriptor)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)


def _handoff_descriptor(current: int, next_descriptor: int, *, code: str) -> int:
    try:
        os.close(current)
    except (OSError, NotImplementedError) as error:
        with suppress(OSError, NotImplementedError):
            os.close(next_descriptor)
        _raise_filesystem_error(error, code=code)
    return next_descriptor


def _raise_filesystem_error(error: BaseException, *, code: str) -> Never:
    if isinstance(error, NotImplementedError):
        raise PocketContractError("safe_open_unsupported") from None
    raise PocketContractError(code) from None


def _reject_symlink_ancestors(path: Path, *, allow_missing_leaf: bool, code: str) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for index, part in enumerate(parts):
        if part in {"", ".", ".."}:
            raise PocketContractError(code)
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if allow_missing_leaf and index == len(parts) - 1:
                return
            raise PocketContractError(code) from None
        except NotImplementedError:
            raise PocketContractError("safe_open_unsupported") from None
        except (PermissionError, OSError):
            raise PocketContractError(code) from None
        if stat.S_ISLNK(mode):
            raise PocketContractError(code)


def _open_root(path: Path, *, code: str) -> int:
    _reject_symlink_ancestors(path, allow_missing_leaf=False, code=code)
    try:
        expected = path.lstat()
        if stat.S_ISLNK(expected.st_mode) or not stat.S_ISDIR(expected.st_mode):
            raise PocketContractError(code)
        descriptor = os.open(path, _safe_open_flags(directory=True))
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            expected.st_dev,
            expected.st_ino,
        ):
            raise PocketContractError(code)
    except PocketContractError:
        _close_descriptor(descriptor, code=code)
        raise
    except (OSError, NotImplementedError) as error:
        _close_descriptor(descriptor, code=code)
        _raise_filesystem_error(error, code=code)
    return descriptor


def _validate_output_root(output_dir: Path) -> None:
    _reject_symlink_ancestors(output_dir, allow_missing_leaf=True, code="unsafe_output_parent")
    parent = output_dir.parent
    try:
        parent_mode = parent.lstat().st_mode
        if stat.S_ISLNK(parent_mode) or not stat.S_ISDIR(parent_mode):
            raise PocketContractError("unsafe_output_parent")
        mode = output_dir.lstat().st_mode
    except FileNotFoundError:
        return
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="unsafe_output_root")
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise PocketContractError("unsafe_output_root")
    try:
        if any(output_dir.iterdir()):
            raise PocketContractError("output_not_empty")
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="unsafe_output_root")


def _assert_root_identity(path: Path, descriptor: int, *, code: str) -> None:
    try:
        expected = path.lstat()
        opened = os.fstat(descriptor)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    if (
        not stat.S_ISDIR(expected.st_mode)
        or stat.S_ISLNK(expected.st_mode)
        or (expected.st_dev, expected.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        raise PocketContractError(code)


def _validate_output_entry_at(parent_descriptor: int, output_name: str) -> None:
    try:
        mode = os.stat(output_name, dir_fd=parent_descriptor, follow_symlinks=False).st_mode
    except FileNotFoundError:
        return
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="unsafe_output_root")
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise PocketContractError("unsafe_output_root")
    try:
        descriptor = os.open(
            output_name,
            _safe_open_flags(directory=True),
            dir_fd=parent_descriptor,
        )
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="unsafe_output_root")
    try:
        try:
            with os.scandir(descriptor) as entries:
                if next(entries, None) is not None:
                    raise PocketContractError("output_not_empty")
        except PocketContractError:
            raise
        except (OSError, NotImplementedError) as error:
            _raise_filesystem_error(error, code="unsafe_output_root")
    finally:
        _close_descriptor(descriptor, code="unsafe_output_root")


def _read_regular_file(path: Path, *, expected_size: int, source: bool) -> bytes:
    code = "source_changed" if source else "bundle_digest_mismatch"
    try:
        descriptor = os.open(path, _safe_open_flags(directory=False))
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise PocketContractError(
                "nonregular_source_file" if source else "nonregular_bundle_file"
            )
        if opened.st_size != expected_size:
            raise PocketContractError(code)
        data = bytearray()
        while len(data) <= MAX_FILE_BYTES:
            block = os.read(descriptor, min(64 * 1024, MAX_FILE_BYTES + 1 - len(data)))
            if not block:
                break
            data.extend(block)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    finally:
        _close_descriptor(descriptor, code=code)
    if len(data) > MAX_FILE_BYTES:
        raise PocketContractError("bundle_file_too_large")
    if len(data) != expected_size:
        raise PocketContractError(code)
    return bytes(data)


def _open_relative_directory(root_descriptor: int, parts: tuple[str, ...], *, code: str) -> int:
    try:
        descriptor: int | None = os.dup(root_descriptor)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    try:
        for part in parts:
            assert descriptor is not None
            next_descriptor = os.open(
                part,
                _safe_open_flags(directory=True),
                dir_fd=descriptor,
            )
            current_descriptor = descriptor
            descriptor = None
            descriptor = _handoff_descriptor(
                current_descriptor,
                next_descriptor,
                code=code,
            )
    except PocketContractError:
        if descriptor is not None:
            _close_descriptor(descriptor, code=code)
        raise
    except (OSError, NotImplementedError) as error:
        if descriptor is not None:
            _close_descriptor(descriptor, code=code)
        _raise_filesystem_error(error, code=code)
    assert descriptor is not None
    return descriptor


def _read_relative_file(
    root_descriptor: int,
    entry: _TreeEntry,
    *,
    source: bool,
) -> bytes:
    code = "source_changed" if source else "bundle_digest_mismatch"
    parts = tuple(PurePosixPath(entry.path).parts)
    parent_descriptor: int | None = _open_relative_directory(root_descriptor, parts[:-1], code=code)
    try:
        assert parent_descriptor is not None
        next_descriptor = os.open(
            parts[-1],
            _safe_open_flags(directory=False),
            dir_fd=parent_descriptor,
        )
        current_descriptor = parent_descriptor
        parent_descriptor = None
        descriptor = _handoff_descriptor(current_descriptor, next_descriptor, code=code)
    except PocketContractError:
        if parent_descriptor is not None:
            _close_descriptor(parent_descriptor, code=code)
        raise
    except (OSError, NotImplementedError) as error:
        if parent_descriptor is not None:
            _close_descriptor(parent_descriptor, code=code)
        _raise_filesystem_error(error, code=code)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise PocketContractError(
                "nonregular_source_file" if source else "nonregular_bundle_file"
            )
        if opened.st_size != entry.size_bytes or (opened.st_dev, opened.st_ino) != (
            entry.device,
            entry.inode,
        ):
            raise PocketContractError(code)
        data = bytearray()
        while len(data) <= MAX_FILE_BYTES:
            block = os.read(descriptor, min(64 * 1024, MAX_FILE_BYTES + 1 - len(data)))
            if not block:
                break
            data.extend(block)
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    finally:
        _close_descriptor(descriptor, code=code)
    if len(data) > MAX_FILE_BYTES:
        raise PocketContractError("bundle_file_too_large")
    if len(data) != entry.size_bytes:
        raise PocketContractError(code)
    return bytes(data)


def _bounded_tree_entries(root_descriptor: int, *, code: str) -> list[_TreeEntry]:
    pending: list[tuple[str, int]] = []
    try:
        pending.append(("", os.dup(root_descriptor)))
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code=code)
    entries: list[_TreeEntry] = []
    try:
        while pending:
            parent_path, directory_descriptor = pending.pop()
            try:
                with os.scandir(directory_descriptor) as scan:
                    children: list[_TreeEntry] = []
                    for entry in scan:
                        if len(entries) + len(children) >= MAX_DIRECTORY_ENTRIES:
                            raise PocketContractError("too_many_bundle_entries")
                        relative_path = f"{parent_path}/{entry.name}" if parent_path else entry.name
                        _validate_bundle_path(relative_path)
                        observed = entry.stat(follow_symlinks=False)
                        children.append(
                            _TreeEntry(
                                path=relative_path,
                                mode=observed.st_mode,
                                size_bytes=observed.st_size,
                                device=observed.st_dev,
                                inode=observed.st_ino,
                            )
                        )
            except PocketContractError:
                raise
            except (OSError, NotImplementedError) as error:
                _raise_filesystem_error(error, code=code)
            finally:
                _close_descriptor(directory_descriptor, code=code)
            for child in reversed(sorted(children, key=lambda item: item.path)):
                if stat.S_ISDIR(child.mode) and not stat.S_ISLNK(child.mode):
                    parts = tuple(PurePosixPath(child.path).parts)
                    child_descriptor = _open_relative_directory(root_descriptor, parts, code=code)
                    try:
                        opened = os.fstat(child_descriptor)
                    except (OSError, NotImplementedError) as error:
                        _close_descriptor(child_descriptor, code=code)
                        _raise_filesystem_error(error, code=code)
                    if (opened.st_dev, opened.st_ino) != (child.device, child.inode):
                        _close_descriptor(child_descriptor, code=code)
                        raise PocketContractError(code)
                    pending.append((child.path, child_descriptor))
            entries.extend(children)
    finally:
        for _path, pending_descriptor in pending:
            with suppress(OSError, NotImplementedError):
                os.close(pending_descriptor)
    return sorted(entries, key=lambda item: item.path)


def _bounded_entries(root: Path, *, code: str) -> list[Path]:
    root_descriptor = _open_root(root, code=code)
    try:
        return [
            root / PurePosixPath(entry.path)
            for entry in _bounded_tree_entries(root_descriptor, code=code)
        ]
    finally:
        _close_descriptor(root_descriptor, code=code)


def _source_regular_entries(root_descriptor: int) -> tuple[_TreeEntry, ...]:
    entries = _bounded_tree_entries(root_descriptor, code="source_changed")
    regular_entries: list[_TreeEntry] = []
    total_size = 0
    for entry in entries:
        _validate_bundle_path(entry.path)
        if stat.S_ISLNK(entry.mode):
            raise PocketContractError("nonregular_source_file")
        if stat.S_ISDIR(entry.mode):
            continue
        if not stat.S_ISREG(entry.mode):
            raise PocketContractError("nonregular_source_file")
        if entry.path == _BUNDLE_MANIFEST:
            raise PocketContractError("source_bundle_manifest")
        if entry.size_bytes > MAX_FILE_BYTES:
            raise PocketContractError("bundle_file_too_large")
        if len(regular_entries) >= MAX_FILES:
            raise PocketContractError("too_many_bundle_files")
        total_size += entry.size_bytes
        if total_size > MAX_TOTAL_BYTES:
            raise PocketContractError("bundle_too_large")
        regular_entries.append(entry)
    return tuple(regular_entries)


def _collect_source_files_from_root(root_descriptor: int) -> tuple[BundleFileV1, ...]:
    files: list[BundleFileV1] = []
    for entry in _source_regular_entries(root_descriptor):
        data = _read_relative_file(root_descriptor, entry, source=True)
        files.append(
            BundleFileV1(
                path=entry.path,
                size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
        )
    return tuple(files)


def _collect_source_files(source_root: Path) -> tuple[BundleFileV1, ...]:
    root_descriptor = _open_root(source_root, code="unsafe_source_root")
    try:
        return _collect_source_files_from_root(root_descriptor)
    finally:
        _close_descriptor(root_descriptor, code="source_changed")


def _write_bundle_manifest(files: tuple[BundleFileV1, ...]) -> bytes:
    manifest = ContractBundleManifestV1(
        bundle_version="matryca-pocket-contract-bundle.v1",
        files=files,
        content_root=_content_root(files),
    )
    payload = cast(JsonValue, manifest.model_dump(mode="json"))
    return canonical_json_bytes(payload)


def _manifest_from_bytes(data: bytes) -> ContractBundleManifestV1:
    if len(data) > MAX_FILE_BYTES:
        raise PocketContractError("bundle_file_too_large")
    try:
        value = json.loads(data)
        if isinstance(value, dict):
            files_value = value.get("files")
            if isinstance(files_value, list) and len(files_value) > MAX_FILES:
                raise PocketContractError("too_many_bundle_files")
        manifest = ContractBundleManifestV1.model_validate(value)
    except PocketContractError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        raise PocketContractError("invalid_bundle_manifest") from None
    if _write_bundle_manifest(manifest.files) != data:
        raise PocketContractError("bundle_digest_mismatch")
    return manifest


def _receipt(manifest: ContractBundleManifestV1, manifest_bytes: bytes) -> BundleReceipt:
    return BundleReceipt(
        bundle_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        content_root=manifest.content_root,
        file_count=len(manifest.files),
    )


def _verify_bundle_from_root(
    root_descriptor: int,
) -> tuple[ContractBundleManifestV1, bytes]:
    entries = _bounded_tree_entries(root_descriptor, code="bundle_changed")
    observed: dict[str, _TreeEntry] = {}
    for entry in entries:
        if stat.S_ISLNK(entry.mode):
            raise PocketContractError("nonregular_bundle_file")
        if stat.S_ISDIR(entry.mode):
            continue
        if not stat.S_ISREG(entry.mode):
            raise PocketContractError("nonregular_bundle_file")
        if entry.size_bytes > MAX_FILE_BYTES:
            raise PocketContractError("bundle_file_too_large")
        if entry.path in observed:
            raise PocketContractError("duplicate_bundle_file")
        observed[entry.path] = entry
    manifest_entry = observed.pop(_BUNDLE_MANIFEST, None)
    if manifest_entry is None:
        raise PocketContractError("missing_bundle_manifest")
    manifest_bytes = _read_relative_file(root_descriptor, manifest_entry, source=False)
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
        entry = observed[path_name]
        if entry.size_bytes != item.size_bytes:
            raise PocketContractError("bundle_digest_mismatch")
        total_size += entry.size_bytes
        if total_size > MAX_TOTAL_BYTES:
            raise PocketContractError("bundle_too_large")
        data = _read_relative_file(root_descriptor, entry, source=False)
        if hashlib.sha256(data).hexdigest() != item.sha256:
            raise PocketContractError("bundle_digest_mismatch")
    return manifest, manifest_bytes


def _verify_bundle_root(bundle_dir: Path) -> tuple[ContractBundleManifestV1, bytes]:
    root_descriptor = _open_root(bundle_dir, code="unsafe_bundle_root")
    try:
        return _verify_bundle_from_root(root_descriptor)
    finally:
        _close_descriptor(root_descriptor, code="bundle_changed")


def _entry_exists_at(parent_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="bundle_publish_failed")
    return True


def _remove_tree_at(parent_descriptor: int, name: str) -> None:
    try:
        observed = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="staging_cleanup_failed")
    try:
        if stat.S_ISDIR(observed.st_mode) and not stat.S_ISLNK(observed.st_mode):
            descriptor = os.open(
                name,
                _safe_open_flags(directory=True),
                dir_fd=parent_descriptor,
            )
            try:
                with os.scandir(descriptor) as scan:
                    children = [(entry.name, entry.stat(follow_symlinks=False)) for entry in scan]
                for child_name, child in children:
                    if stat.S_ISDIR(child.st_mode) and not stat.S_ISLNK(child.st_mode):
                        _remove_tree_at(descriptor, child_name)
                    else:
                        os.unlink(child_name, dir_fd=descriptor)
            finally:
                _close_descriptor(descriptor, code="staging_cleanup_failed")
            os.rmdir(name, dir_fd=parent_descriptor)
        else:
            os.unlink(name, dir_fd=parent_descriptor)
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="staging_cleanup_failed")


def _remove_empty_directory_at(parent_descriptor: int, name: str) -> None:
    try:
        os.rmdir(name, dir_fd=parent_descriptor)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="staging_cleanup_failed")


def _remove_staging(path: Path) -> None:
    parent_descriptor = _open_root(path.parent, code="staging_cleanup_failed")
    try:
        _remove_tree_at(parent_descriptor, path.name)
    finally:
        _close_descriptor(parent_descriptor, code="staging_cleanup_failed")


def _create_staging_at(parent_descriptor: int, output_name: str) -> tuple[str, int]:
    for _attempt in range(16):
        staging_name = f".{output_name}.{uuid.uuid4().hex}"
        try:
            os.mkdir(staging_name, 0o700, dir_fd=parent_descriptor)
        except FileExistsError:
            continue
        except (OSError, NotImplementedError) as error:
            _raise_filesystem_error(error, code="bundle_write_failed")
        try:
            descriptor = os.open(
                staging_name,
                _safe_open_flags(directory=True),
                dir_fd=parent_descriptor,
            )
        except PocketContractError:
            with suppress(OSError, NotImplementedError):
                os.rmdir(staging_name, dir_fd=parent_descriptor)
            raise
        except (OSError, NotImplementedError) as error:
            with suppress(OSError, NotImplementedError):
                os.rmdir(staging_name, dir_fd=parent_descriptor)
            _raise_filesystem_error(error, code="bundle_write_failed")
        return staging_name, descriptor
    raise PocketContractError("bundle_write_failed")


def _write_file_at(root_descriptor: int, path: str, data: bytes) -> None:
    _validate_bundle_path(path)
    parts = tuple(PurePosixPath(path).parts)
    try:
        parent_descriptor: int | None = os.dup(root_descriptor)
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="bundle_write_failed")
    try:
        for part in parts[:-1]:
            assert parent_descriptor is not None
            with suppress(FileExistsError):
                os.mkdir(part, 0o700, dir_fd=parent_descriptor)
            next_descriptor = os.open(
                part,
                _safe_open_flags(directory=True),
                dir_fd=parent_descriptor,
            )
            current_descriptor = parent_descriptor
            parent_descriptor = None
            parent_descriptor = _handoff_descriptor(
                current_descriptor,
                next_descriptor,
                code="bundle_write_failed",
            )
        assert parent_descriptor is not None
        next_descriptor = os.open(
            parts[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_descriptor,
        )
        current_descriptor = parent_descriptor
        parent_descriptor = None
        descriptor = _handoff_descriptor(
            current_descriptor,
            next_descriptor,
            code="bundle_write_failed",
        )
        try:
            remaining = memoryview(data)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("short write")
                remaining = remaining[written:]
        finally:
            _close_descriptor(descriptor, code="bundle_write_failed")
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="bundle_write_failed")
    finally:
        if parent_descriptor is not None:
            _close_descriptor(parent_descriptor, code="bundle_write_failed")


def _begin_publish_at(
    parent_descriptor: int,
    staging_name: str,
    output_name: str,
) -> _PublishTransaction:
    output_exists = _entry_exists_at(parent_descriptor, output_name)
    if not output_exists:
        try:
            os.rename(
                staging_name,
                output_name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
        except (OSError, NotImplementedError) as error:
            _raise_filesystem_error(error, code="bundle_publish_failed")
        return _PublishTransaction(output_existed=False, backup_name=None)

    backup_name = f".{output_name}.backup-{uuid.uuid4().hex}"
    if _entry_exists_at(parent_descriptor, backup_name):
        raise PocketContractError("bundle_publish_failed")
    try:
        os.rename(
            output_name,
            backup_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        os.rename(
            staging_name,
            output_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
    except (OSError, NotImplementedError) as error:
        try:
            if _entry_exists_at(parent_descriptor, backup_name) and not _entry_exists_at(
                parent_descriptor, output_name
            ):
                os.rename(
                    backup_name,
                    output_name,
                    src_dir_fd=parent_descriptor,
                    dst_dir_fd=parent_descriptor,
                )
        except (OSError, NotImplementedError, PocketContractError):
            raise PocketContractError("bundle_publish_rollback_failed") from None
        _raise_filesystem_error(error, code="bundle_publish_failed")
    return _PublishTransaction(output_existed=True, backup_name=backup_name)


def _rollback_publication_at(
    parent_descriptor: int,
    staging_name: str,
    output_name: str,
    transaction: _PublishTransaction,
) -> None:
    try:
        os.rename(
            output_name,
            staging_name,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        if transaction.output_existed:
            assert transaction.backup_name is not None
            os.rename(
                transaction.backup_name,
                output_name,
                src_dir_fd=parent_descriptor,
                dst_dir_fd=parent_descriptor,
            )
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="bundle_publish_rollback_failed")


def _finalize_publication_at(
    parent_descriptor: int,
    staging_name: str,
    output_name: str,
    transaction: _PublishTransaction,
) -> None:
    if not transaction.output_existed:
        return
    assert transaction.backup_name is not None
    try:
        _remove_empty_directory_at(parent_descriptor, transaction.backup_name)
    except PocketContractError as cleanup_error:
        _rollback_publication_at(
            parent_descriptor,
            staging_name,
            output_name,
            transaction,
        )
        _remove_tree_at(parent_descriptor, staging_name)
        raise cleanup_error from None


def _publish_staging_at(parent_descriptor: int, staging_name: str, output_name: str) -> None:
    transaction = _begin_publish_at(parent_descriptor, staging_name, output_name)
    _finalize_publication_at(
        parent_descriptor,
        staging_name,
        output_name,
        transaction,
    )


def _publish_staging(staging_path: Path, output_dir: Path) -> None:
    if staging_path.parent != output_dir.parent:
        raise PocketContractError("bundle_publish_failed")
    parent_descriptor = _open_root(output_dir.parent, code="bundle_publish_failed")
    try:
        _publish_staging_at(parent_descriptor, staging_path.name, output_dir.name)
    finally:
        _close_descriptor(parent_descriptor, code="bundle_publish_failed")


def build_contract_bundle(source_root: Path, output_dir: Path) -> BundleReceipt:
    output_parent_descriptor = _open_root(output_dir.parent, code="unsafe_output_parent")
    source_descriptor: int | None = None
    staging_name: str | None = None
    staging_descriptor: int | None = None
    transaction_committed = False
    try:
        _validate_output_entry_at(output_parent_descriptor, output_dir.name)
        source_descriptor = _open_root(source_root, code="unsafe_source_root")
        files = _collect_source_files_from_root(source_descriptor)
        staging_name, staging_descriptor = _create_staging_at(
            output_parent_descriptor, output_dir.name
        )
        entries = {entry.path: entry for entry in _source_regular_entries(source_descriptor)}
        if set(entries) != {item.path for item in files}:
            raise PocketContractError("source_changed")
        for item in files:
            entry = entries.get(item.path)
            if entry is None:
                raise PocketContractError("source_changed")
            data = _read_relative_file(source_descriptor, entry, source=True)
            if hashlib.sha256(data).hexdigest() != item.sha256:
                raise PocketContractError("source_changed")
            _write_file_at(staging_descriptor, item.path, data)
        manifest_bytes = _write_bundle_manifest(files)
        _write_file_at(staging_descriptor, _BUNDLE_MANIFEST, manifest_bytes)
        manifest, verified_bytes = _verify_bundle_from_root(staging_descriptor)
        receipt = _receipt(manifest, verified_bytes)
        _close_descriptor(staging_descriptor, code="bundle_write_failed")
        staging_descriptor = None
        _close_descriptor(source_descriptor, code="source_changed")
        source_descriptor = None
        _assert_root_identity(
            output_dir.parent,
            output_parent_descriptor,
            code="unsafe_output_parent",
        )
        _validate_output_entry_at(output_parent_descriptor, output_dir.name)
        transaction = _begin_publish_at(
            output_parent_descriptor,
            staging_name,
            output_dir.name,
        )
        try:
            _assert_root_identity(
                output_dir.parent,
                output_parent_descriptor,
                code="unsafe_output_parent",
            )
        except PocketContractError:
            _rollback_publication_at(
                output_parent_descriptor,
                staging_name,
                output_dir.name,
                transaction,
            )
            raise
        _finalize_publication_at(
            output_parent_descriptor,
            staging_name,
            output_dir.name,
            transaction,
        )
        transaction_committed = True
        staging_name = None
        return receipt
    except PocketContractError:
        raise
    except (OSError, NotImplementedError) as error:
        _raise_filesystem_error(error, code="bundle_write_failed")
    finally:
        try:
            if staging_descriptor is not None:
                _close_descriptor(staging_descriptor, code="staging_cleanup_failed")
            if staging_name is not None:
                _remove_tree_at(output_parent_descriptor, staging_name)
        finally:
            try:
                if source_descriptor is not None:
                    _close_descriptor(source_descriptor, code="source_changed")
            finally:
                if transaction_committed:
                    with suppress(OSError, NotImplementedError):
                        os.close(output_parent_descriptor)
                else:
                    _close_descriptor(output_parent_descriptor, code="unsafe_output_parent")


def verify_contract_bundle(bundle_dir: Path) -> BundleReceipt:
    manifest, manifest_bytes = _verify_bundle_root(bundle_dir)
    return _receipt(manifest, manifest_bytes)


__all__ = ["BundleReceipt", "build_contract_bundle", "verify_contract_bundle"]
