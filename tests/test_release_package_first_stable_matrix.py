"""Synthetic checks for the first-stable release and row-identity policy."""

from __future__ import annotations

import pytest
from scripts.release_qualification.first_stable_matrix import (
    first_stable_release_route,
    require_exact_row_keys,
)

_KEYS = (
    "minimum-linux-x86_64-cpython-3.12.16-wheel",
    "minimum-linux-x86_64-cpython-3.12.16-sdist",
    "minimum-linux-x86_64-cpython-3.13.18-wheel",
    "minimum-linux-x86_64-cpython-3.13.18-sdist",
    "minimum-macos-arm64-cpython-3.12.16-wheel",
    "minimum-macos-arm64-cpython-3.12.16-sdist",
    "minimum-macos-arm64-cpython-3.13.18-wheel",
    "minimum-macos-arm64-cpython-3.13.18-sdist",
    "current-linux-x86_64-cpython-3.12.16-wheel",
    "current-linux-x86_64-cpython-3.12.16-sdist",
    "current-linux-x86_64-cpython-3.13.18-wheel",
    "current-linux-x86_64-cpython-3.13.18-sdist",
    "current-macos-arm64-cpython-3.12.16-wheel",
    "current-macos-arm64-cpython-3.12.16-sdist",
    "current-macos-arm64-cpython-3.13.18-wheel",
    "current-macos-arm64-cpython-3.13.18-sdist",
)


def test_requires_all_sixteen_canonical_row_keys_regardless_of_input_order() -> None:
    require_exact_row_keys(iter(reversed(_KEYS)))


@pytest.mark.parametrize(
    "keys",
    [
        (),
        _KEYS[:-1],
        (*_KEYS[:-1], _KEYS[0]),
        (*_KEYS, _KEYS[0]),
        (*_KEYS, "current-windows-x86_64-cpython-3.13.18-sdist"),
        (*_KEYS[:-1], "current-macos-x86_64-cpython-3.13.18-sdist"),
        (*_KEYS[:-1], "current-macos-arm64-cpython-3.13.15-sdist"),
        (*_KEYS[:-1], "current-macos-arm64-cpython-3.13.18-sdist\n"),
        (*_KEYS[:-1], True),
    ],
)
def test_rejects_incomplete_duplicate_and_out_of_policy_rows(keys: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        require_exact_row_keys(keys)


@pytest.mark.parametrize(
    ("tag", "version", "prerelease"),
    [
        ("v2.1.0", "2.1.0", False),
        ("v2.1.0-rc.1", "2.1.0rc1", True),
        ("v2.1.0-rc.12", "2.1.0rc12", True),
    ],
)
def test_accepts_only_the_exact_matching_rc_or_final_identity(
    tag: str, version: str, prerelease: bool
) -> None:
    route = first_stable_release_route(tag, version)
    assert (route.tag, route.version, route.prerelease) == (tag, version, prerelease)


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        ("v2.1.0-rc.0", "2.1.0rc0"),
        ("v2.1.0-rc.01", "2.1.0rc01"),
        ("v2.1.0-rc.1", "2.1.0rc2"),
        ("v2.1.0rc1", "2.1.0rc1"),
        ("v2.1.0", "2.1.0rc1"),
        ("v2.1.0-alpha.4", "2.1.0a4"),
        ("v2.1.0-beta.2", "2.1.0b2"),
        ("v2.0.1-rc.4", "2.0.1rc4"),
        ("v2.1.1", "2.1.1"),
        ("v2.1.0", "2.1.0+local"),
        ("v2.1.0", "2.1.0\n"),
        ("v2.1.0", True),
        (True, "2.1.0"),
    ],
)
def test_rejects_neighbor_versions_and_ambiguous_identity(tag: object, version: object) -> None:
    with pytest.raises(ValueError):
        first_stable_release_route(tag, version)
