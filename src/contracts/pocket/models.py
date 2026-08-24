from __future__ import annotations

import re
import unicodedata
import uuid
from collections.abc import Mapping
from datetime import datetime
from pathlib import PurePosixPath
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import JsonValue, PocketContractError, canonical_json_sha256

MAX_ID_LENGTH: Final[int] = 64
MAX_PATH_BYTES: Final[int] = 4_096
MAX_TITLE_CHARACTERS: Final[int] = 1_024
MAX_CITED_TEXT_CHARACTERS: Final[int] = 16_384
MAX_SOURCES: Final[int] = 128
MAX_FILES: Final[int] = 4_096
MAX_RECORDS: Final[int] = 1_000_000
MAX_FILE_BYTES: Final[int] = 2**31

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
_UTC_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _validate_nfc(value: str) -> None:
    if not unicodedata.is_normalized("NFC", value):
        raise PocketContractError("non_nfc_string")


def _validate_identifier(value: str, code: str) -> None:
    _validate_nfc(value)
    if _IDENTIFIER.fullmatch(value) is None:
        raise PocketContractError(code)


def _validate_commit(value: str, code: str) -> None:
    _validate_nfc(value)
    if _GIT_COMMIT.fullmatch(value) is None:
        raise PocketContractError(code)


def _validate_digest(value: str, code: str) -> None:
    _validate_nfc(value)
    if _SHA256.fullmatch(value) is None:
        raise PocketContractError(code)


def _validate_safe_path(value: str, *, payload_only: bool) -> None:
    _validate_nfc(value)
    path = PurePosixPath(value)
    raw_parts = value.split("/")
    if (
        path.is_absolute()
        or len(path.parts) < 2
        or any(part in {"", ".", ".."} for part in raw_parts)
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or len(value.encode("utf-8")) > MAX_PATH_BYTES
        or (payload_only and path.parts[0] != "payload")
    ):
        raise PocketContractError("unsafe_bundle_path")


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    @model_validator(mode="before")
    @classmethod
    def _reject_unexpected_fields(cls, value: object) -> object:
        if isinstance(value, Mapping) and set(value).difference(cls.model_fields):
            raise PocketContractError("unexpected_fields")
        return value


class SourceRevisionV1(_ClosedModel):
    source_id: str = Field(
        max_length=MAX_ID_LENGTH,
        json_schema_extra={"pattern": _IDENTIFIER.pattern},
    )
    repository_slug: str = Field(max_length=200, json_schema_extra={"pattern": _REPOSITORY.pattern})
    source_commit: str = Field(json_schema_extra={"pattern": _GIT_COMMIT.pattern})

    @model_validator(mode="after")
    def _validate_source_revision(self) -> SourceRevisionV1:
        _validate_identifier(self.source_id, "invalid_source_id")
        _validate_nfc(self.repository_slug)
        if _REPOSITORY.fullmatch(self.repository_slug) is None:
            raise PocketContractError("invalid_repository_slug")
        _validate_commit(self.source_commit, "invalid_source_commit")
        return self


class PackFileV1(_ClosedModel):
    path: str
    media_type: str = Field(max_length=127, json_schema_extra={"pattern": _MEDIA_TYPE.pattern})
    size_bytes: int = Field(ge=0, le=MAX_FILE_BYTES)
    sha256: str = Field(json_schema_extra={"pattern": _SHA256.pattern})
    record_count: int = Field(ge=0, le=MAX_RECORDS)

    @model_validator(mode="after")
    def _validate_pack_file(self) -> PackFileV1:
        _validate_safe_path(self.path, payload_only=True)
        _validate_nfc(self.media_type)
        if _MEDIA_TYPE.fullmatch(self.media_type) is None:
            raise PocketContractError("invalid_media_type")
        _validate_digest(self.sha256, "invalid_sha256")
        return self


def payload_content_root(files: tuple[PackFileV1, ...]) -> str:
    payload = {"files": [item.model_dump(mode="json") for item in files]}
    return canonical_json_sha256(cast(JsonValue, payload))


class PackManifestV1(_ClosedModel):
    format_version: Literal["matryca-pocket-pack.v1"]
    contract_version: Literal["matryca-pocket-contract.v1"]
    pack_id: str
    created_at: str = Field(json_schema_extra={"pattern": _UTC_SECOND.pattern})
    generator_id: str = Field(
        max_length=MAX_ID_LENGTH,
        json_schema_extra={"pattern": _IDENTIFIER.pattern},
    )
    generator_commit: str = Field(json_schema_extra={"pattern": _GIT_COMMIT.pattern})
    signature_algorithm: Literal["ed25519"]
    key_id: str = Field(
        max_length=MAX_ID_LENGTH,
        json_schema_extra={"pattern": _IDENTIFIER.pattern},
    )
    sources: tuple[SourceRevisionV1, ...] = Field(
        min_length=1,
        max_length=MAX_SOURCES,
        strict=False,
    )
    files: tuple[PackFileV1, ...] = Field(max_length=MAX_FILES, strict=False)
    content_root: str = Field(json_schema_extra={"pattern": _SHA256.pattern})

    @model_validator(mode="after")
    def _validate_manifest(self) -> PackManifestV1:
        _validate_nfc(self.pack_id)
        try:
            pack_uuid = uuid.UUID(self.pack_id)
        except ValueError as error:
            raise PocketContractError("invalid_pack_id") from error
        if str(pack_uuid) != self.pack_id or pack_uuid.version != 7:
            raise PocketContractError("invalid_pack_id")
        _validate_nfc(self.created_at)
        if _UTC_SECOND.fullmatch(self.created_at) is None:
            raise PocketContractError("invalid_created_at")
        try:
            datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise PocketContractError("invalid_created_at") from error
        _validate_identifier(self.generator_id, "invalid_generator_id")
        _validate_commit(self.generator_commit, "invalid_generator_commit")
        _validate_identifier(self.key_id, "invalid_key_id")
        _validate_digest(self.content_root, "invalid_content_root")
        if tuple(sorted(self.sources, key=lambda item: item.source_id)) != self.sources:
            raise PocketContractError("noncanonical_order")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise PocketContractError("duplicate_source_id")
        if len({(item.repository_slug, item.source_commit) for item in self.sources}) != len(
            self.sources
        ):
            raise PocketContractError("duplicate_source_revision")
        if tuple(sorted(self.files, key=lambda item: item.path)) != self.files:
            raise PocketContractError("noncanonical_order")
        if len({item.path for item in self.files}) != len(self.files):
            raise PocketContractError("duplicate_file_path")
        if payload_content_root(self.files) != self.content_root:
            raise PocketContractError("content_root_mismatch")
        return self
