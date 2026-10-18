"""Static regression coverage for the admitted frontend source-map security pin."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

_NODE = "node_modules/source-map-js"
_EXPECTED = {
    "version": "1.2.2",
    "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.2.tgz",
    "integrity": (
        "sha512-KGj/8Y43x35aZVDtt+J4mK1hoLGHULMYfSkODJNQjNDC3oW1PqPoxMwo0pLUsWM/"
        "UEGzON/NxeHywEfNXNP3Vw=="
    ),
}


def _assert_patched_source_map(lock: dict[str, Any]) -> None:
    packages = lock["packages"]
    copies = {name for name in packages if name == _NODE or name.endswith("/" + _NODE)}
    if copies != {_NODE}:
        raise ValueError("Expected exactly one source-map-js package record")
    for field, expected in _EXPECTED.items():
        if packages[_NODE].get(field) != expected:
            raise ValueError(f"source-map-js {field} differs from the patched pin")


def _admitted_fixture() -> dict[str, Any]:
    return {
        "lockfileVersion": 3,
        "packages": {
            "node_modules/source-map-js": {
                "version": "1.2.2",
                "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.2.tgz",
                "integrity": (
                    "sha512-KGj/8Y43x35aZVDtt+J4mK1hoLGHULMYfSkODJNQjNDC3oW1PqPoxMwo0pLUsWM/"
                    "UEGzON/NxeHywEfNXNP3Vw=="
                ),
            }
        },
    }


def test_frontend_lock_uses_the_authenticated_patched_source_map() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf-8"))
    _assert_patched_source_map(lock)


def test_source_map_pin_rejects_the_affected_version() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["version"] = "1.2.1"
    with pytest.raises(ValueError, match="source-map-js version"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_wrong_integrity() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["integrity"] = "sha512-not-the-authenticated-artifact"
    with pytest.raises(ValueError, match="source-map-js integrity"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_a_second_affected_nested_copy() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    stale = deepcopy(lock["packages"][_NODE])
    stale.update(
        {
            "version": "1.2.1",
            "resolved": "https://registry.npmjs.org/source-map-js/-/source-map-js-1.2.1.tgz",
            "integrity": (
                "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7"
                "MQc7vIsISBG8VQ8+IDQxpfQA=="
            ),
        }
    )
    lock["packages"]["node_modules/other/node_modules/source-map-js"] = stale
    with pytest.raises(ValueError, match="exactly one source-map-js"):
        _assert_patched_source_map(lock)


def test_source_map_pin_rejects_an_unexpected_artifact_url() -> None:
    lock = _admitted_fixture()
    _assert_patched_source_map(lock)
    lock["packages"][_NODE]["resolved"] = "https://example.invalid/source-map-js-1.2.2.tgz"
    with pytest.raises(ValueError, match="source-map-js resolved"):
        _assert_patched_source_map(lock)
