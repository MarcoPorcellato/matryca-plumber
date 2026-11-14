"""The release generator updates identity links without changing profile semantics."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


def _fixture(root: Path) -> Path:
    resources = root / "matryca_plumber/graph_gateway/resources/og-v1"
    resources.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname="matryca-plumber"\nversion="2.1.0a4"\n')
    (root / "uv.lock").write_bytes(b"new locked source\n")
    profile = (
        b'{"project":{"name":"matryca-plumber","version":"2.1.0a3"},'
        b'"lock_source":"uv.lock","lock_sha256":"old",'
        b'"qualification":"unqualified","parser":{"version":"1.9.0"}}\n'
    )
    (resources / "dependency-profile.json").write_bytes(profile)
    manifest = json.dumps(
        {"files": {"dependency-profile.json": hashlib.sha256(profile).hexdigest(), "other": "keep"}}
    ).encode()
    (resources / "manifest.json").write_bytes(manifest)
    (resources / "descriptor.json").write_text(
        json.dumps(
            {
                "qualification": "unqualified",
                "resource_digests": {
                    "dependency_profile": hashlib.sha256(profile).hexdigest(),
                    "manifest": hashlib.sha256(manifest).hexdigest(),
                    "golden": "keep",
                },
            }
        )
    )
    (resources / "requirements.txt").write_bytes(b"unchanged requirements\n")
    return resources


def _generator() -> Any:
    return importlib.import_module("scripts.regenerate_og_resource_chain").regenerate


def test_regeneration_updates_identity_and_chain_without_promoting_qualification(
    tmp_path: Path,
) -> None:
    resources = _fixture(tmp_path)
    result = _generator()(tmp_path)
    profile = json.loads((resources / "dependency-profile.json").read_bytes())
    manifest = json.loads((resources / "manifest.json").read_bytes())
    descriptor = json.loads((resources / "descriptor.json").read_bytes())
    assert profile["project"] == {"name": "matryca-plumber", "version": "2.1.0a4"}
    assert profile["lock_sha256"] == hashlib.sha256(b"new locked source\n").hexdigest()
    assert profile["qualification"] == descriptor["qualification"] == "unqualified"
    assert profile["parser"] == {"version": "1.9.0"}
    assert manifest["files"]["other"] == descriptor["resource_digests"]["golden"] == "keep"
    assert manifest["files"]["dependency-profile.json"] == result["dependency_profile"]
    assert descriptor["resource_digests"]["manifest"] == result["manifest"]
    assert (resources / "requirements.txt").read_bytes() == b"unchanged requirements\n"
    before = {p.name: p.read_bytes() for p in resources.iterdir()}
    assert _generator()(tmp_path) == result
    assert before == {p.name: p.read_bytes() for p in resources.iterdir()}


@pytest.mark.parametrize(
    "name", ["uv.lock", "dependency-profile.json", "manifest.json", "descriptor.json"]
)
def test_regeneration_rejects_symlink_inputs_without_writes(tmp_path: Path, name: str) -> None:
    resources = _fixture(tmp_path)
    target = tmp_path / name if name == "uv.lock" else resources / name
    outside = tmp_path / "retained-original"
    target.rename(outside)
    target.symlink_to(outside)
    before = {p.name: p.read_bytes() for p in resources.iterdir()}
    with pytest.raises(ValueError):
        _generator()(tmp_path)
    assert before == {p.name: p.read_bytes() for p in resources.iterdir()}


def test_regeneration_rejects_incomplete_old_chain_without_repair(tmp_path: Path) -> None:
    resources = _fixture(tmp_path)
    (resources / "dependency-profile.json").write_bytes(b'{"unreviewed":true}\n')
    before = {p.name: p.read_bytes() for p in resources.iterdir()}
    with pytest.raises(ValueError):
        _generator()(tmp_path)
    assert before == {p.name: p.read_bytes() for p in resources.iterdir()}
