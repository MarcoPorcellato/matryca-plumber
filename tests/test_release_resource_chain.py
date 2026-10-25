"""Digest-chain recomputation must detect incomplete resource updates."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


def checker() -> Any:
    name = "scripts.release_qualification.resource_chain"
    assert importlib.util.find_spec(name) is not None, "Resource-chain check is missing."
    return importlib.import_module(name).check_resource_chain


def write_chain(root: Path, profile: bytes) -> None:
    (root / "dependency-profile.json").write_bytes(profile)
    digest = hashlib.sha256(profile).hexdigest()
    manifest = json.dumps(
        {"schema_version": 1, "files": {"dependency-profile.json": digest}}
    ).encode()
    (root / "manifest.json").write_bytes(manifest)
    (root / "descriptor.json").write_text(
        json.dumps(
            {
                "resource_digests": {
                    "dependency_profile": digest,
                    "manifest": hashlib.sha256(manifest).hexdigest(),
                }
            }
        )
    )


def test_resource_chain_accepts_recomputed_links_without_writing(tmp_path: Path) -> None:
    write_chain(tmp_path, b'{"locked":true}\n')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = checker()(tmp_path)
    assert result["dependency_profile"] == hashlib.sha256(b'{"locked":true}\n').hexdigest()
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("updated_manifest", [False, True])
def test_partial_regeneration_fails_closed(tmp_path: Path, updated_manifest: bool) -> None:
    write_chain(tmp_path, b'{"locked":true}\n')
    profile = b'{"locked":false}\n'
    (tmp_path / "dependency-profile.json").write_bytes(profile)
    if updated_manifest:
        (tmp_path / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "files": {
                        "dependency-profile.json": hashlib.sha256(profile).hexdigest(),
                    },
                }
            )
        )
    with pytest.raises(ValueError, match="chain"):
        checker()(tmp_path)


def test_complete_regeneration_changes_the_bound_descriptor(tmp_path: Path) -> None:
    write_chain(tmp_path, b'{"locked":true}\n')
    before = checker()(tmp_path)
    write_chain(tmp_path, b'{"locked":false}\n')
    after = checker()(tmp_path)
    assert set(before) == {"dependency_profile", "manifest", "descriptor"}
    assert all(before[key] != after[key] for key in before)


def test_resource_chain_rejects_symlink_inputs(tmp_path: Path) -> None:
    root = tmp_path / "resources"
    root.mkdir()
    write_chain(root, b'{"locked":true}\n')
    outside = tmp_path / "outside.json"
    outside.write_bytes((root / "dependency-profile.json").read_bytes())
    (root / "dependency-profile.json").unlink()
    (root / "dependency-profile.json").symlink_to(outside)
    with pytest.raises(ValueError):
        checker()(root)


def test_packaged_source_chain_is_current_without_regenerating_files() -> None:
    root = Path(__file__).resolve().parents[1] / "matryca_plumber/graph_gateway/resources/og-v1"
    observed = checker()(root)
    assert (
        observed["descriptor"]
        == hashlib.sha256((root / "descriptor.json").read_bytes()).hexdigest()
    )
