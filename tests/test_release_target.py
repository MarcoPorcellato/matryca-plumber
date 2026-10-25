"""Offline release routing and producer/verifier identity controls."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest


def targets() -> Any:
    name = "scripts.release_qualification.release_target"
    assert importlib.util.find_spec(name) is not None, "Explicit release target is missing."
    return importlib.import_module(name)


@pytest.mark.parametrize(
    ("tag", "version", "hardened", "prerelease"),
    [
        ("v2.0.1-rc.4", "2.0.1rc4", False, True),
        ("v2.1.0-alpha.2", "2.1.0a2", False, True),
        ("v2.1.0-alpha.3", "2.1.0a3", True, True),
        ("v2.1.0-alpha.4", "2.1.0a4", True, True),
        ("v2.1.0-beta.1", "2.1.0b1", True, True),
        ("v2.1.0-rc.1", "2.1.0rc1", True, True),
        ("v2.1.0", "2.1.0", True, False),
        ("v2.1.1", "2.1.1", True, False),
    ],
)
def test_release_route_derives_version_and_keeps_hardened_successors(
    tag: str, version: str, hardened: bool, prerelease: bool
) -> None:
    route = targets().ReleaseRoute.from_tag(tag)
    assert (route.version, route.hardened, route.prerelease) == (version, hardened, prerelease)
    assert route.originals == (
        f"matryca_plumber-{version}-py3-none-any.whl",
        f"matryca_plumber-{version}.tar.gz",
    )


@pytest.mark.parametrize(
    "tag", ["vwat", "v02.1.0", "v2.1.0a4", "v2.1.0-alpha.04", "v2.1.0-alpha.4/x", "v2.1.0\n", True]
)
def test_malformed_tags_never_select_a_legacy_fallback(tag: object) -> None:
    with pytest.raises(ValueError):
        targets().ReleaseRoute.from_tag(tag)


def future_target() -> Any:
    return targets().ReleaseTarget("v2.1.0-alpha.4", "2.1.0a4", "a" * 40, "b" * 40, "c" * 40, "123")


def test_release_target_roundtrip_is_closed_and_filename_safe() -> None:
    target = future_target()
    expected = {
        "tag": "v2.1.0-alpha.4",
        "version": "2.1.0a4",
        "source_commit": "a" * 40,
        "source_tree": "b" * 40,
        "tag_object": "c" * 40,
        "publisher_run": "123",
    }
    assert target.to_dict() == expected
    assert targets().ReleaseTarget.from_dict(expected) == target
    with pytest.raises(ValueError):
        targets().ReleaseTarget.from_dict({**expected, "verifier_commit": "d" * 40})


@pytest.mark.parametrize(
    "changes",
    [
        {"version": "2.1.0a3"},
        {"source_commit": "a" * 7},
        {"tag_object": "C" * 40},
        {"publisher_run": True},
        {"publisher_run": "0"},
        {"publisher_run": "01"},
    ],
)
def test_release_target_rejects_mismatched_or_incomplete_selection(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(future_target(), **changes)


def test_successor_bundle_policy_retains_rc4_defaults() -> None:
    from scripts.release_qualification import bundle

    bundle._validate_version("2.1.0a4", "og-alpha3")
    with pytest.raises(ValueError):
        bundle._validate_version("2.1.0a4", "rc4")
    with pytest.raises(ValueError):
        bundle._validate_version("2.1.0a2", "og-alpha3")


def test_recovery_binds_the_selected_producer_not_a_publisher_constant() -> None:
    from scripts.release_qualification.alpha3_recovery import RecoveryBinding

    target = future_target()
    tools = (
        (".github/workflows/og-public-artifact-qualification.yml", "1" * 64),
        ("scripts/qualify_release_package.py", "2" * 64),
        ("scripts/release_qualification/alpha3_recovery.py", "3" * 64),
    )
    recovery = RecoveryBinding("d" * 40, "e" * 40, tools, target=target)
    recovery.require_producer("a" * 40, "b" * 40, "123")
    with pytest.raises(ValueError):
        recovery.require_producer("a" * 40, "b" * 40, "124")
    with pytest.raises(ValueError):
        RecoveryBinding("a" * 40, "e" * 40, tools, target=target)
    assert recovery.to_dict()["producer_target"] == target.to_dict()
    assert json.loads(json.dumps(recovery.to_dict()))["verifier_commit"] == "d" * 40


def test_selection_requires_all_explicit_successor_identity_inputs() -> None:
    module = targets()
    with pytest.raises(ValueError):
        module.selected_target("a" * 40, "b" * 40, "123", {})
    environment = {
        "PUBLIC_RELEASE_TAG": "v2.1.0-alpha.4",
        "PUBLIC_RELEASE_TAG_OBJECT": "c" * 40,
        "SELECTED_SOURCE_TREE": "b" * 40,
    }
    assert module.selected_target("a" * 40, "b" * 40, "123", environment) == future_target()
    with pytest.raises(ValueError):
        module.selected_target("a" * 40, "f" * 40, "123", environment)


@pytest.mark.parametrize("tag", ["v2.1.0-alpha.4", "malformed"])
def test_workflow_route_command_emits_only_validated_outputs(tmp_path: Path, tag: str) -> None:
    import yaml

    root = Path(__file__).resolve().parents[1]
    workflow = yaml.load(
        (root / ".github/workflows/release.yml").read_text(), Loader=yaml.BaseLoader
    )
    step = next(
        step
        for step in workflow["jobs"]["verify"]["steps"]
        if step.get("name") == "Select fail-closed release route"
    )
    output = tmp_path / "outputs"
    environment = dict(os.environ)
    environment.pop("BASH_ENV", None)
    environment.update({"GITHUB_REF_NAME": tag, "GITHUB_OUTPUT": str(output)})
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-euc", step["run"]],
        cwd=root,
        env=environment,
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert len(result.stdout) < 4096 and len(result.stderr) < 8192
    if tag == "malformed":
        assert result.returncode != 0 and output.read_bytes() == b""
    else:
        assert result.returncode == 0
        assert output.read_text().splitlines() == [
            "version=2.1.0a4",
            "hardened=true",
            "prerelease=true",
            "wheel=matryca_plumber-2.1.0a4-py3-none-any.whl",
            "sdist=matryca_plumber-2.1.0a4.tar.gz",
        ]
