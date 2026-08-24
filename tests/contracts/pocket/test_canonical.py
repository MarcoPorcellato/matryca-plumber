from __future__ import annotations

from typing import cast

import pytest
from src.contracts.pocket.canonical import (
    JsonValue,
    PocketContractError,
    canonical_json_bytes,
    canonical_json_line,
    canonical_json_sha256,
)


def test_canonical_json_has_exact_utf8_bytes_and_digest() -> None:
    value = {
        "title": "Città",
        "contract_version": "matryca-pocket-contract.v1",
    }
    expected = b'{"contract_version":"matryca-pocket-contract.v1","title":"Citt\xc3\xa0"}'

    typed_value = cast(JsonValue, value)
    assert canonical_json_bytes(typed_value) == expected
    assert canonical_json_line(typed_value) == expected + b"\n"
    assert canonical_json_sha256(typed_value) == (
        "5542d7da4dc43e39c1a568dedf22af565304b575c871db738c4a9a2718df75ba"
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ({"title": "Citta\u0300"}, "non_nfc_string"),
        ({"bad-key": "value"}, "invalid_object_key"),
        ({"score": 1.5}, "unsupported_json_type"),
        ({"value": None}, "unsupported_json_type"),
        ({"count": 2**63}, "integer_out_of_range"),
    ],
)
def test_canonical_json_rejects_values_outside_the_profile(
    value: object,
    code: str,
) -> None:
    with pytest.raises(PocketContractError, match=code):
        canonical_json_bytes(cast(JsonValue, value))
