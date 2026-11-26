"""Bind ordinary installed-package observations to one first-stable row."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.first_stable_matrix import (
    FIRST_STABLE_ROWS,
    first_stable_release_route,
)
from scripts.release_qualification.installed import InstalledReceipt, verify_installed

_ROWS = {row.key: row for row in FIRST_STABLE_ROWS}
_HOSTS = {"macos-arm64": ("darwin", "arm64"), "linux-x86_64": ("linux", "x86_64")}
_PARSER = {"minimum": "1.9.0", "current": "1.11.4"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def write_installed_row(
    output: Path,
    row_key: str,
    candidate_tag: str,
    binding: BundleBinding,
    expected_dependencies: Mapping[str, str],
    receipt: InstalledReceipt,
) -> None:
    """Retain a verifier receipt against independently selected row expectations.

    The caller must authenticate the bundle, pass the original archive to the
    installed verifier, and supply an independently admitted native closure.
    This local report alone does not prove runtime admission or cleanup.
    """
    row = _ROWS.get(row_key)
    if row is None:
        raise ValueError("Unknown first-stable row key.")
    first_stable_release_route(candidate_tag, binding.version)
    # Reuse shared bundle syntax validation without changing legacy route policy.
    BundleBinding.from_json(binding.to_json(), policy="og-alpha3")
    if (
        receipt.kind != row.distribution
        or (receipt.operating_system, receipt.architecture) != _HOSTS[row.platform]
        or receipt.python_version != row.python
        or receipt.version != binding.version
        or receipt.location_class != "isolated-venv-site-packages"
        or receipt.windows_launcher is not None
        or receipt.tck_outcomes != ("PASS", "PASS", "PASS")
    ):
        raise ValueError("Installed receipt does not match the selected first-stable row.")
    expected = tuple(sorted(expected_dependencies.items()))
    if (
        expected_dependencies.get("logseq-matryca-parser") != _PARSER[row.profile]
        or receipt.dependencies != expected
    ):
        raise ValueError("Installed dependency closure differs from the admitted profile.")
    dependency_bytes = json.dumps(expected, separators=(",", ":")).encode()
    if (
        receipt.dependency_sha256 != hashlib.sha256(dependency_bytes).hexdigest()
        or _SHA256.fullmatch(receipt.record_sha256) is None
        or _SHA256.fullmatch(receipt.resource_sha256) is None
    ):
        raise ValueError("Installed receipt digest is invalid.")
    if row.distribution == "wheel":
        name, size, digest = binding.wheel_name, binding.wheel_size, binding.wheel_sha256
    else:
        name, size, digest = binding.sdist_name, binding.sdist_size, binding.sdist_sha256
    payload = {
        "schema_version": 1,
        "row_key": row.key,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "candidate_tag": candidate_tag,
        "original_artifact": {"name": name, "size": size, "sha256": digest},
        "installed": receipt.to_dict(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)


def verify_and_write_installed_row(
    *,
    output: Path,
    row_key: str,
    candidate_tag: str,
    binding: BundleBinding,
    expected_dependencies: Mapping[str, str],
    installed_python: Path,
    source_root: Path,
    originals: Path,
) -> None:
    """Run the installed verifier on the bound original, then retain its report.

    Native runtime, independently locked dependencies, the original pair
    handoff, the task-owned output path and process ownership remain caller
    gates. In particular, an sdist-derived temporary wheel is never sent to
    the verifier as the original sdist or original wheel.
    """
    row = _ROWS.get(row_key)
    if row is None:
        raise ValueError("Unknown first-stable row key.")
    first_stable_release_route(candidate_tag, binding.version)
    BundleBinding.from_json(binding.to_json(), policy="og-alpha3")
    if expected_dependencies.get("logseq-matryca-parser") != _PARSER[row.profile]:
        raise ValueError("Installed dependency closure differs from the admitted profile.")
    kind: Literal["wheel", "sdist"] = "wheel" if row.distribution == "wheel" else "sdist"
    name = binding.wheel_name if kind == "wheel" else binding.sdist_name
    receipt = verify_installed(
        installed_python,
        binding,
        source_root,
        kind,
        artifact=originals / name,
        policy="og-alpha3",
    )
    write_installed_row(output, row_key, candidate_tag, binding, expected_dependencies, receipt)
