"""Closed release identities, separate from the checkout used to verify them."""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass

_NUMBER = r"(0|[1-9][0-9]*)"
_TAG = re.compile(rf"v{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:-(alpha|beta|rc)\.{_NUMBER})?")
_VERSION = re.compile(rf"{_NUMBER}\.{_NUMBER}\.{_NUMBER}(?:(a|b|rc){_NUMBER})?")


@dataclass(frozen=True, slots=True)
class ReleaseRoute:
    """A validated tag selects one route; malformed tags never fall back."""

    tag: str
    version: str
    hardened: bool
    prerelease: bool

    @classmethod
    def from_tag(cls, tag: object) -> ReleaseRoute:
        match = _TAG.fullmatch(tag) if isinstance(tag, str) else None
        if match is None:
            raise ValueError("Invalid release tag.")
        major, minor, patch, stage, sequence = match.groups()
        release = (int(major), int(minor), int(patch))
        suffix = "" if stage is None else {"alpha": "a", "beta": "b", "rc": "rc"}[stage] + sequence
        hardened = release >= (2, 1, 0) and not (
            release == (2, 1, 0) and stage == "alpha" and int(sequence) < 3
        )
        return cls(str(tag), f"{major}.{minor}.{patch}{suffix}", hardened, stage is not None)

    @classmethod
    def from_version(cls, version: object) -> ReleaseRoute:
        match = _VERSION.fullmatch(version) if isinstance(version, str) else None
        if match is None:
            raise ValueError("Invalid normalized release version.")
        major, minor, patch, stage, sequence = match.groups()
        suffix = (
            ""
            if stage is None
            else "-" + {"a": "alpha", "b": "beta", "rc": "rc"}[stage] + "." + sequence
        )
        return cls.from_tag(f"v{major}.{minor}.{patch}{suffix}")

    @property
    def originals(self) -> tuple[str, str]:
        return (
            f"matryca_plumber-{self.version}-py3-none-any.whl",
            f"matryca_plumber-{self.version}.tar.gz",
        )

    @property
    def assets(self) -> tuple[str, ...]:
        return (
            *self.originals,
            "binding.json",
            "content-ledger.json",
            "canonical-build.json",
            "SHA256SUMS",
        )


@dataclass(frozen=True, slots=True)
class ReleaseTarget:
    """An explicit producer expectation, not metadata supplied by an artifact."""

    tag: str
    version: str
    source_commit: str
    source_tree: str
    tag_object: str
    publisher_run: str

    def __post_init__(self) -> None:
        route = ReleaseRoute.from_tag(self.tag)
        if not route.hardened or self.version != route.version:
            raise ValueError("Release target version or hardened route mismatch.")
        if not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)
            for value in (self.source_commit, self.source_tree, self.tag_object)
        ):
            raise ValueError("Release target requires full lowercase Git identities.")
        if (
            not isinstance(self.publisher_run, str)
            or re.fullmatch(r"[1-9][0-9]*", self.publisher_run) is None
        ):
            raise ValueError("Invalid release target publisher run.")

    @property
    def route(self) -> ReleaseRoute:
        return ReleaseRoute.from_tag(self.tag)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: object) -> ReleaseTarget:
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid release target fields.")
        return cls(**value)


# Historical input, never inferred for another producer, tag or publisher.
ALPHA3_TARGET = ReleaseTarget(
    "v2.1.0-alpha.3",
    "2.1.0a3",
    "8c30f70e217722e719c5aedc322219ebccb87e68",
    "de80d0473aa281c52d0fed10b4561024dd12d76f",
    "c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24",
    "39887297548",
)


def selected_target(
    commit: str, tree: str, publisher: str, environment: Mapping[str, str]
) -> ReleaseTarget:
    """Use explicit dispatch expectations; only the original historical tuple defaults."""
    tag = environment.get("PUBLIC_RELEASE_TAG")
    tag_object = environment.get("PUBLIC_RELEASE_TAG_OBJECT")
    expected_tree = environment.get("SELECTED_SOURCE_TREE")
    if tag is None and tag_object is None and expected_tree is None:
        if (commit, tree, publisher) == (
            ALPHA3_TARGET.source_commit,
            ALPHA3_TARGET.source_tree,
            ALPHA3_TARGET.publisher_run,
        ):
            return ALPHA3_TARGET
        raise ValueError("Explicit public release target is required.")
    if expected_tree != tree:
        raise ValueError("Selected producer tree differs from the release target.")
    route = ReleaseRoute.from_tag(tag)
    if not isinstance(tag_object, str):
        raise ValueError("Explicit public tag object is required.")
    return ReleaseTarget(route.tag, route.version, commit, tree, tag_object, publisher)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    route = ReleaseRoute.from_tag(args.tag)
    for key, value in (
        ("version", route.version),
        ("hardened", str(route.hardened).lower()),
        ("prerelease", str(route.prerelease).lower()),
        ("wheel", route.originals[0]),
        ("sdist", route.originals[1]),
    ):
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
