from __future__ import annotations

import hashlib
import json
import re
import unicodedata

type JsonScalar = str | int | bool
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_INT = 2**63 - 1


class PocketContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _validate_json_value(value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if not 0 <= value <= _MAX_INT:
            raise PocketContractError("integer_out_of_range")
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise PocketContractError("non_utf8_string") from None
        if not unicodedata.is_normalized("NFC", value):
            raise PocketContractError("non_nfc_string")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or _KEY.fullmatch(key) is None:
                raise PocketContractError("invalid_object_key")
            _validate_json_value(item)
        return
    raise PocketContractError("unsupported_json_type")


def canonical_json_bytes(value: JsonValue) -> bytes:
    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_line(value: JsonValue) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def canonical_json_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
