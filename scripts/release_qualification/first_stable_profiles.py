"""Resolve the source-locked runtime export for one ordinary native profile."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from scripts.release_qualification.sdist_build import _reject_unbound_marker

_PARSER = {
    "minimum": ("1.9.0", "d9e67b493439b44aa233beb0a783ca8cb07b394ac10eaafe7ae4eab9c0242fe6"),
    "current": ("1.11.4", "7c62c5690cc7f11e35b365d5659eecec743e30da389c5306fef12c1883491f39"),
}
_PLATFORMS = {
    "macos-arm64": ("darwin", "Darwin", "arm64"),
    "linux-x86_64": ("linux", "Linux", "x86_64"),
}
_HASH = re.compile(r"sha256:[0-9a-f]{64}")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127}")


@dataclass(frozen=True, slots=True)
class RuntimeProfile:
    """Expected native package inventory and hash-bearing installer input."""

    packages: tuple[tuple[str, str], ...]
    requirements: str


def resolve_profile(locked_export: str, profile: str, platform: str, python: str) -> RuntimeProfile:
    """Resolve a trusted locked export without running an index or resolver.

    Obtain the export from the exact candidate root lock using the admitted
    installer, omitting development groups, the project, and Parser. Install
    from the returned text using require-hashes, only-binary and no-deps.
    No native wheel download or installed-inventory claim follows from this
    normalization alone.
    """
    target = _PLATFORMS.get(platform)
    parser = _PARSER.get(profile)
    if target is None or parser is None or python not in {"3.12.16", "3.13.18"}:
        raise ValueError("Invalid first-stable profile, platform or Python.")
    if not 0 < len(locked_export) <= 1024 * 1024 or not locked_export.isascii():
        raise ValueError("Dependency export is missing, oversized or non-ASCII.")
    system, marker_system, machine = target
    environment = cast(dict[str, str], default_environment())
    environment.update(
        implementation_name="cpython",
        implementation_version=python,
        os_name="posix",
        platform_machine=machine,
        platform_python_implementation="CPython",
        platform_system=marker_system,
        python_full_version=python,
        python_version=python.rsplit(".", 1)[0],
        sys_platform=system,
    )
    pinned: dict[str, tuple[str, tuple[str, ...]]] = {}
    for line in locked_export.replace("\\\n", " ").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        base, *raw_hashes = re.split(r"[ \t]+--hash=", line.strip())
        hashes = tuple(sorted(set(digest.strip() for digest in raw_hashes)))
        if not hashes or any(_HASH.fullmatch(digest) is None for digest in hashes):
            raise ValueError("Dependency export is missing exact SHA-256 hashes.")
        requirement = Requirement(base)
        _reject_unbound_marker(base)
        pins = list(requirement.specifier)
        if (
            requirement.url is not None
            or requirement.extras
            or len(pins) != 1
            or pins[0].operator != "=="
            or _VERSION.fullmatch(pins[0].version) is None
        ):
            raise ValueError("Dependency export contains a non-exact requirement.")
        name = canonicalize_name(requirement.name)
        if name in {"logseq-matryca-parser", "matryca-plumber", "pip"}:
            raise ValueError("Unselected project, resolver or Parser in the common closure.")
        if requirement.marker is not None and not requirement.marker.evaluate(environment):
            continue
        if name in pinned:
            raise ValueError("Duplicate dependency in the applicable locked closure.")
        pinned[name] = (pins[0].version, hashes)
    if not pinned:
        raise ValueError("Applicable locked dependency closure is empty.")
    version, digest = parser
    pinned["logseq-matryca-parser"] = (version, (f"sha256:{digest}",))
    packages = tuple((name, package[0]) for name, package in sorted(pinned.items()))
    requirements = "".join(
        f"{name}=={version} " + " ".join(f"--hash={digest}" for digest in pinned[name][1]) + "\n"
        for name, version in packages
    )
    return RuntimeProfile(packages, requirements)
