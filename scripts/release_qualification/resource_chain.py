"""Recompute the dependency-profile/manifest/descriptor chain without rewriting it."""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate resource-chain field.")
        result[key] = value
    return result


def check_resource_chain(root: Path) -> dict[str, str]:
    """Fail on any missing digest propagation; preserve every original source byte."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid resource-chain root.")
    raw: dict[str, bytes] = {}
    for name in ("dependency-profile.json", "manifest.json", "descriptor.json"):
        path = root / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 1_048_576:
            raise ValueError("Invalid resource-chain input.")
        raw[name] = path.read_bytes()
    try:
        json.loads(raw["dependency-profile.json"], object_pairs_hook=_unique_object)
        manifest = json.loads(raw["manifest.json"], object_pairs_hook=_unique_object)
        descriptor = json.loads(raw["descriptor.json"], object_pairs_hook=_unique_object)
        profile = hashlib.sha256(raw["dependency-profile.json"]).hexdigest()
        manifest_digest = hashlib.sha256(raw["manifest.json"]).hexdigest()
        if not (
            manifest["files"]["dependency-profile.json"] == profile
            and descriptor["resource_digests"]["dependency_profile"] == profile
            and descriptor["resource_digests"]["manifest"] == manifest_digest
        ):
            raise ValueError("Resource chain is not completely regenerated.")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Malformed resource chain.") from error
    return {
        "dependency_profile": profile,
        "manifest": manifest_digest,
        "descriptor": hashlib.sha256(raw["descriptor.json"]).hexdigest(),
    }
