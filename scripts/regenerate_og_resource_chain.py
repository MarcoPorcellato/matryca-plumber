"""Regenerate only the packaged OG release identity and its dependent digests.

Run from the repository root with ``python -m scripts.regenerate_og_resource_chain``.
This maintainer operation does not qualify a profile or resolve dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import tomllib
from pathlib import Path
from typing import Any

from scripts.release_qualification.resource_chain import check_resource_chain

RESOURCE_PATH = Path("matryca_plumber/graph_gateway/resources/og-v1")


def _read(root: Path, relative: Path) -> bytes:
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("Symlink in release input path.")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 16_777_216:
        raise ValueError("Invalid release input.")
    return path.read_bytes()


def _encode(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def regenerate(root: Path) -> dict[str, str]:
    """Update three resources after version-only changes; reject broken old chains."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid source root.")
    project = tomllib.loads(_read(root, Path("pyproject.toml")).decode("utf-8"))["project"]
    lock = _read(root, Path("uv.lock"))
    names = ("dependency-profile.json", "manifest.json", "descriptor.json")
    raw = {name: _read(root, RESOURCE_PATH / name) for name in names}
    check_resource_chain(root / RESOURCE_PATH)
    documents = {name: json.loads(data) for name, data in raw.items()}
    profile = documents["dependency-profile.json"]
    if (
        project.get("name") != "matryca-plumber"
        or not isinstance(project.get("version"), str)
        or not project["version"]
        or profile.get("project", {}).get("name") != project["name"]
        or profile.get("lock_source") != "uv.lock"
    ):
        raise ValueError("Unexpected source/profile identity.")
    profile["project"]["version"] = project["version"]
    profile["lock_sha256"] = hashlib.sha256(lock).hexdigest()
    updated = {"dependency-profile.json": _encode(profile)}
    profile_digest = hashlib.sha256(updated["dependency-profile.json"]).hexdigest()
    documents["manifest.json"]["files"]["dependency-profile.json"] = profile_digest
    updated["manifest.json"] = _encode(documents["manifest.json"])
    descriptor = documents["descriptor.json"]
    descriptor["resource_digests"]["dependency_profile"] = profile_digest
    descriptor["resource_digests"]["manifest"] = hashlib.sha256(
        updated["manifest.json"]
    ).hexdigest()
    updated["descriptor.json"] = _encode(descriptor)
    # Preserve every other resource and semantic value, including qualification labels.
    for name, data in updated.items():
        if data != raw[name]:
            (root / RESOURCE_PATH / name).write_bytes(data)
    return check_resource_chain(root / RESOURCE_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(regenerate(args.source_root), sort_keys=True))


if __name__ == "__main__":
    main()
