"""Read the maintainer's qualification reference from an already verified signed tag."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

from scripts.release_qualification.first_stable_matrix import first_stable_release_route
from scripts.release_qualification.release_target import ReleaseRoute

Selection = tuple[int, int, int, str]
_MAX_TAG = 65_536
_REFERENCE = re.compile(
    rb"Qualification-Aggregate: ([1-9][0-9]{0,18})/([1-9][0-9]{0,8})/"
    rb"([1-9][0-9]{0,18})@sha256:([0-9a-f]{64})"
)


def select(tag: str, version: str, commit: str, raw_tag: bytes) -> Selection | None:
    """Scope by both tag and source version so a mislabelled ordinary candidate cannot skip."""
    ReleaseRoute.from_tag(tag)
    if not (
        tag == "v2.1.0"
        or tag.startswith("v2.1.0-rc.")
        or version == "2.1.0"
        or version.startswith("2.1.0rc")
    ):
        return None
    first_stable_release_route(tag, version)
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not 0 < len(raw_tag) <= _MAX_TAG:
        raise ValueError("Invalid tag source or oversized tag object.")
    header, _, message = raw_tag.partition(b"\n\n")
    if header.split(b"\n")[:3] != [
        f"object {commit}".encode(),
        b"type commit",
        f"tag {tag}".encode(),
    ]:
        raise ValueError("The verified annotated tag does not directly name the selected commit.")
    signed, marker, _ = message.partition(b"\n-----BEGIN PGP SIGNATURE-----\n")
    lines = [
        line for line in signed.split(b"\n") if line.lower().startswith(b"qualification-aggregate:")
    ]
    match = _REFERENCE.fullmatch(lines[0]) if marker and len(lines) == 1 else None
    if not match:
        raise ValueError("Expected exactly one signed Qualification-Aggregate reference.")
    run, attempt, artifact, sha = match.groups()
    return int(run), int(attempt), int(artifact), sha.decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("commit")
    args = parser.parse_args()
    with Path("pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    selection = select(args.tag, version, args.commit, sys.stdin.buffer.read(_MAX_TAG + 1))
    print("required=false" if selection is None else "required=true")
    if selection is not None:
        for name, value in zip(
            ("run_id", "attempt", "artifact_id", "sha256"), selection, strict=True
        ):
            print(f"{name}={value}")


if __name__ == "__main__":
    main()
