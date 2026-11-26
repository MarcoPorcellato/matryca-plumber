"""Check explicit reviewed runtime admission before ordinary qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path

from scripts.release_qualification.first_stable_host import PINS
from scripts.release_qualification.first_stable_matrix import first_stable_release_route

_SHA256 = re.compile(r"[0-9a-f]{64}")


def require_ordinary_admission(
    tag: str, version: str, material: bytes | None, expected_sha256: str
) -> None:
    """Require maintainer-selected admission, never infer it from a startup probe."""
    first_stable_release_route(tag, version)
    if (
        material is None
        or not 0 < len(material) <= 16_384
        or _SHA256.fullmatch(expected_sha256) is None
        or hashlib.sha256(material).hexdigest() != expected_sha256
    ):
        raise ValueError("Missing or mismatched reviewed runtime admission.")
    value = json.loads(material)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "runtime_inputs"}
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or not isinstance(value["runtime_inputs"], list)
        or len(value["runtime_inputs"]) != len(PINS)
    ):
        raise ValueError("Invalid reviewed runtime admission schema.")
    seen: set[tuple[str, str]] = set()
    for item in value["runtime_inputs"]:
        if not isinstance(item, dict) or set(item) != {
            "platform",
            "python",
            "archive_sha256",
            "build_evidence_sha256",
            "notices_sha256",
        }:
            raise ValueError("Invalid reviewed runtime admission entry.")
        platform, python = item["platform"], item["python"]
        if not isinstance(platform, str) or not isinstance(python, str):
            raise ValueError("Invalid reviewed runtime admission target.")
        key = (platform, python)
        if (
            key not in PINS
            or key in seen
            or item["archive_sha256"] != PINS[key].sha256
            or any(
                not isinstance(item[kind], str) or not _SHA256.fullmatch(item[kind])
                for kind in ("build_evidence_sha256", "notices_sha256")
            )
        ):
            raise ValueError("Runtime admission differs from the exact selected inputs.")
        seen.add(key)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("admission_sha256")
    args = parser.parse_args()
    admission = Path("release-qualification-build/first-stable-runtime-admission.json")
    if admission.is_symlink() or not admission.is_file() or admission.stat().st_size > 16_384:
        raise ValueError("Missing reviewed runtime admission in the selected source.")
    with admission.open("rb") as stream:
        material = stream.read(16_385)
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    require_ordinary_admission(args.tag, version, material, args.admission_sha256)


if __name__ == "__main__":
    main()
