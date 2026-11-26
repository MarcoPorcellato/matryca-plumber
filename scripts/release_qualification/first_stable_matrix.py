"""Closed identity policy for the ordinary Linux/macOS first-stable lane.

This module checks versions and row coverage only. It does not authenticate
receipts, admit runtime or dependency inputs, or grant qualification.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import product
from typing import NamedTuple

from scripts.release_qualification.release_target import ReleaseRoute

_VERSION = re.compile(r"2\.1\.0(?:rc[1-9][0-9]*)?")


class FirstStableRow(NamedTuple):
    """One expected slot; the profile role must later bind an exact closure."""

    profile: str
    platform: str
    python: str
    distribution: str

    @property
    def key(self) -> str:
        return f"{self.profile}-{self.platform}-cpython-{self.python}-{self.distribution}"


FIRST_STABLE_ROWS = tuple(
    FirstStableRow(profile, platform, python, distribution)
    for profile, platform, python, distribution in product(
        ("minimum", "current"),
        ("linux-x86_64", "macos-arm64"),
        ("3.12.16", "3.13.18"),
        ("wheel", "sdist"),
    )
)
_EXPECTED_KEYS = frozenset(row.key for row in FIRST_STABLE_ROWS)


def first_stable_release_route(tag: object, version: object) -> ReleaseRoute:
    """Require a canonical first-stable RC/final version and matching Git tag."""
    if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
        raise ValueError("Invalid first-stable package version.")
    route = ReleaseRoute.from_version(version)
    if not isinstance(tag, str) or tag != route.tag:
        raise ValueError("First-stable tag does not match the package version.")
    return route


def require_exact_row_keys(keys: Iterable[object]) -> None:
    """Reject any coverage other than one observation per expected row."""
    seen: set[str] = set()
    for key in keys:
        if not isinstance(key, str) or key not in _EXPECTED_KEYS:
            raise ValueError("Unexpected first-stable row key.")
        if key in seen:
            raise ValueError("Duplicate first-stable row key.")
        seen.add(key)
    if seen != _EXPECTED_KEYS:
        raise ValueError("Missing first-stable row keys.")
