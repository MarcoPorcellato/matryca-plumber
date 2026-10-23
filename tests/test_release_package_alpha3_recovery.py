"""Offline controls for the closed, immutable alpha.3 verifier recovery route."""

from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.util
import os
import shutil
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

SOURCE = "8c30f70e217722e719c5aedc322219ebccb87e68"
TREE = "de80d0473aa281c52d0fed10b4561024dd12d76f"
TAG_OBJECT = "c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24"
PUBLISHER = "39887297548"
VERIFIER = "d" * 40
VERIFIER_TREE = "e" * 40
TOOL_FILES = (
    (".github/workflows/og-public-artifact-qualification.yml", "1" * 64),
    ("scripts/qualify_release_package.py", "2" * 64),
    ("scripts/release_qualification/alpha3_recovery.py", "3" * 64),
)
ROOT = Path(__file__).resolve().parents[1]


def _recovery() -> Any:
    name = "scripts.release_qualification.alpha3_recovery"
    assert importlib.util.find_spec(name) is not None, "Closed alpha.3 recovery is missing."
    return importlib.import_module(name)


def _binding() -> Any:
    return _recovery().RecoveryBinding(VERIFIER, VERIFIER_TREE, TOOL_FILES)


def test_recovery_binding_preserves_original_producer() -> None:
    binding = _binding()
    binding.require_producer(SOURCE, TREE, PUBLISHER)
    record = binding.to_dict()
    assert record["verifier_commit"] == VERIFIER
    assert record["verifier_tree"] == VERIFIER_TREE
    assert record["policy"] == "alpha3-verifier-recovery/v1"


def _public_inputs() -> tuple[Any, dict[str, Any]]:
    from scripts.release_qualification import alpha1_public as public

    from tests.test_release_package_alpha1_public import _inputs

    _, metadata = _inputs()
    metadata["main"]["object"]["sha"] = VERIFIER
    metadata["tag"]["object"]["sha"] = TAG_OBJECT
    metadata["tag_object"]["sha"] = TAG_OBJECT
    metadata["tag_object"]["object"]["sha"] = SOURCE
    metadata["publisher"].update(id=int(PUBLISHER), head_sha=SOURCE)
    metadata["verifier"]["head_sha"] = VERIFIER
    for role in ("publisher", "verifier"):
        metadata[role]["actor"] = {"id": 220745401}
        metadata[role]["triggering_actor"] = {"id": 220745401}
    metadata["verifier_commit"] = {
        "sha": VERIFIER,
        "commit": {
            "tree": {"sha": VERIFIER_TREE},
            "verification": {"verified": True, "reason": "valid"},
        },
    }
    return public.PublicContext(SOURCE, TREE, PUBLISHER, "456", _binding()), metadata


def test_recovery_context_separates_verifier_from_immutable_producer() -> None:
    from scripts.release_qualification import alpha1_public as public

    context, metadata = _public_inputs()
    assert len(public.verify_metadata(context, metadata)) == 6
    assert context.source_commit == SOURCE and context.source_tree == TREE
    assert context.workflow_commit == VERIFIER


@pytest.mark.parametrize(
    "mutation",
    [
        "main",
        "tag",
        "producer",
        "verifier",
        "tree",
        "signature",
        "publisher",
        "attempt",
        "actor",
        "triggering_actor",
        "workflow",
        "bytes",
    ],
)
def test_recovery_metadata_rejects_wrong_or_conflated_identities(mutation: str) -> None:
    from scripts.release_qualification import alpha1_public as public

    context, metadata = _public_inputs()
    if mutation == "main":
        metadata["main"]["object"]["sha"] = SOURCE
    elif mutation == "tag":
        metadata["tag"]["object"]["sha"] = "f" * 40
        metadata["tag_object"]["sha"] = "f" * 40
    elif mutation == "producer":
        metadata["publisher"]["head_sha"] = VERIFIER
    elif mutation == "verifier":
        metadata["verifier"]["head_sha"] = SOURCE
    elif mutation == "tree":
        metadata["verifier_commit"]["commit"]["tree"]["sha"] = TREE
    elif mutation == "signature":
        metadata["verifier_commit"]["commit"]["verification"]["verified"] = False
    elif mutation == "publisher":
        metadata["publisher"]["id"] = 999
    elif mutation == "attempt":
        metadata["verifier"]["run_attempt"] = 2
    elif mutation in ("actor", "triggering_actor"):
        metadata["verifier"][mutation]["id"] = 1
    elif mutation == "workflow":
        metadata["verifier"]["path"] += "@" + SOURCE
    else:
        metadata["pypi"]["urls"][0]["digests"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        public.verify_metadata(context, metadata)


@pytest.mark.parametrize(
    "commit,tree", [(SOURCE, VERIFIER_TREE), (VERIFIER, TREE), ("x", VERIFIER_TREE)]
)
def test_recovery_binding_is_not_an_arbitrary_same_source_override(commit: str, tree: str) -> None:
    with pytest.raises(ValueError):
        _recovery().RecoveryBinding(commit, tree, TOOL_FILES)


@pytest.mark.parametrize("field", ["source", "tree", "publisher", "failed-Q"])
def test_recovery_refuses_a_different_producer_or_consumed_qualification(field: str) -> None:
    from scripts.release_qualification import alpha1_public as public

    source, tree, publisher, verifier = SOURCE, TREE, PUBLISHER, "456"
    if field == "source":
        source = "a" * 40
    elif field == "tree":
        tree = "b" * 40
    elif field == "publisher":
        publisher = "789"
    else:
        verifier = "39888823938"
    with pytest.raises(ValueError):
        public.PublicContext(source, tree, publisher, verifier, _binding())


def test_legacy_context_digest_remains_byte_compatible() -> None:
    from scripts.release_qualification import alpha1_matrix as matrix

    from tests.test_release_package_alpha1_matrix import _inputs

    context, *_ = _inputs()
    value = asdict(context)
    value.pop("recovery", None)
    assert context.inputs_sha256 == matrix.digest(value)


def test_recovery_matrix_uses_actual_verifier_job_heads_without_rewriting_producer() -> None:
    from scripts.release_qualification import alpha1_matrix as matrix

    from tests.test_release_package_alpha1_matrix import _inputs

    original, *_ = _inputs(run_attempt=1)
    context, rows, jobs, source, windows = _inputs(
        run_attempt=1,
        binding_override=replace(original.binding, source_commit=SOURCE, source_tree=TREE),
        recovery=_binding(),
    )
    jobs[0]["name"] = "Admit public OG alpha"
    for job in jobs:
        job["head_sha"] = VERIFIER
    report = matrix.verify_matrix(context, rows, jobs, source, windows, public_input=True)
    assert report["source_commit"] == SOURCE
    assert report["recovery"] == _binding().to_dict()
    wrong = copy.deepcopy(jobs)
    wrong[0]["head_sha"] = SOURCE
    with pytest.raises(ValueError):
        matrix.verify_matrix(context, rows, wrong, source, windows, public_input=True)
    with pytest.raises(ValueError):
        matrix.verify_matrix(context, rows, jobs, source, windows)


def test_recovery_artifacts_require_verifier_head_and_independent_digest() -> None:
    from scripts.release_qualification import alpha1_matrix as matrix

    from tests.test_release_package_alpha1_matrix import _inputs

    original, *_ = _inputs(run_attempt=1)
    context, *_ = _inputs(
        run_attempt=1,
        binding_override=replace(original.binding, source_commit=SOURCE, source_tree=TREE),
        recovery=_binding(),
    )
    keys = ("admission", *matrix.ARTIFACT_KEYS[1:])
    expected = {key: {"id": str(i + 1), "sha256": "a" * 64} for i, key in enumerate(keys)}
    artifacts: list[dict[str, Any]] = [
        {
            "id": i + 1,
            "name": "og-public-123-1-" + key,
            "digest": "sha256:" + "a" * 64,
            "expired": False,
            "workflow_run": {"id": 123, "head_sha": VERIFIER},
        }
        for i, key in enumerate(keys)
    ]
    assert len(matrix.verify_artifacts(context, expected, artifacts, public_input=True)) == 7
    for field, value in (("head_sha", SOURCE), ("id", 999)):
        wrong = copy.deepcopy(artifacts)
        wrong[0]["workflow_run"][field] = value
        with pytest.raises(ValueError):
            matrix.verify_artifacts(context, expected, wrong, public_input=True)
    wrong = copy.deepcopy(artifacts)
    wrong[0]["digest"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError):
        matrix.verify_artifacts(context, expected, wrong, public_input=True)


@pytest.mark.parametrize("kind", ["same", "nested", "symlink"])
def test_recovery_checkout_rejects_overlap_before_git(tmp_path: Path, kind: str) -> None:
    root = tmp_path / "root"
    root.mkdir()
    producer = root
    if kind == "nested":
        producer = root / "producer"
        producer.mkdir()
    elif kind == "symlink":
        producer = tmp_path / "alias"
        producer.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        _recovery().checkout_binding(producer, root, VERIFIER, VERIFIER_TREE)


@pytest.mark.parametrize("wrong", ["file", "spec"])
def test_recovery_rejects_wrong_loaded_tool_origin(tmp_path: Path, wrong: str) -> None:
    verifier, producer = tmp_path / "verifier", tmp_path / "producer"
    verifier.mkdir()
    producer.mkdir()
    good = verifier / "module.py"
    bad = producer / "module.py"
    good.write_text("pass\n")
    bad.write_text("pass\n")
    module = SimpleNamespace(
        __file__=str(bad if wrong == "file" else good),
        __spec__=SimpleNamespace(origin=str(bad if wrong == "spec" else good)),
    )
    with pytest.raises(ValueError):
        _recovery().verify_tool_origins(verifier, {"scripts.qualify_release_package": module}, {})


@pytest.mark.parametrize("failure", [None, "missing", "changed", "dirty", "commit", "tree"])
def test_recovery_checkout_binds_committed_tools_and_both_git_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    recovery = _recovery()
    producer = tmp_path / "producer"
    producer.mkdir()
    catalog = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in recovery.REQUIRED_TOOLS
    }
    if failure == "missing":
        catalog.pop("scripts/qualify_release_package.py")
    elif failure == "changed":
        catalog["scripts/qualify_release_package.py"] = "0" * 64

    def git_value(root: Path, arg: str) -> str:
        if root == producer:
            return SOURCE if arg == "HEAD" else TREE
        if failure == "commit" and arg == "HEAD":
            return SOURCE
        if failure == "tree" and arg != "HEAD":
            return TREE
        return VERIFIER if arg == "HEAD" else VERIFIER_TREE

    monkeypatch.setattr(recovery.bundle, "_git_value", git_value)
    monkeypatch.setattr(
        recovery.installed, "_git_value", lambda *_args: "dirty" if failure == "dirty" else ""
    )
    monkeypatch.setattr(recovery.bundle, "_git_tree_file_digests", lambda _root: catalog)
    monkeypatch.setattr(
        recovery,
        "sys",
        SimpleNamespace(modules={"scripts.release_qualification.alpha3_recovery": recovery}),
    )
    if failure:
        with pytest.raises(ValueError):
            recovery.checkout_binding(producer, ROOT, VERIFIER, VERIFIER_TREE)
    else:
        binding = recovery.checkout_binding(producer, ROOT, VERIFIER, VERIFIER_TREE)
        assert binding.verifier_commit == VERIFIER
        assert dict(binding.tool_files) == catalog


def test_recovery_cli_requires_explicit_verifier_arguments() -> None:
    from scripts.qualify_release_package import _parser

    command = [
        "alpha3-recovery-public-admit",
        "--source-root",
        "/producer",
        "--output",
        "/out",
        "--publication-run",
        PUBLISHER,
    ]
    with pytest.raises(SystemExit):
        _parser().parse_args(command)
    args = _parser().parse_args(
        command
        + [
            "--verifier-root",
            "/verifier",
            "--verifier-commit",
            VERIFIER,
            "--verifier-tree",
            VERIFIER_TREE,
        ]
    )
    assert args.alpha3_recovery is True
    legacy = _parser().parse_args(["alpha-public-admit", *command[1:]])
    assert not getattr(legacy, "alpha3_recovery", False)
    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "alpha-public-admit",
                *command[1:],
                "--verifier-root",
                "/verifier",
                "--verifier-commit",
                VERIFIER,
                "--verifier-tree",
                VERIFIER_TREE,
            ]
        )


def test_recovery_workflow_is_explicit_and_preserves_default_route() -> None:
    value = yaml.load(
        (ROOT / ".github/workflows/og-public-artifact-qualification.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    inputs = value["on"]["workflow_dispatch"]["inputs"]
    assert inputs["alpha3_recovery"]["default"] == "false"
    assert inputs["verifier_sha"]["default"] == inputs["verifier_tree"]["default"] == ""
    assert set(value["on"]) == {"workflow_dispatch"}
    assert set(value["permissions"]) == set()
    for job in value["jobs"].values():
        checkouts = [
            step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
        ]
        assert len(checkouts) == 3
        assert "!inputs.alpha3_recovery" in checkouts[0]["if"]
        assert checkouts[1]["with"]["ref"] == "${{ inputs.verifier_sha }}"
        assert checkouts[1]["with"]["path"] == "verifier"
        assert checkouts[2]["with"]["path"] == "producer"
        assert checkouts[1]["env"]["GIT_CONFIG_VALUE_0"] == "false"
        for step in job["steps"]:
            if "run" in step:
                assert step["working-directory"] == "${{ env.QUALIFICATION_TOOL_ROOT }}"


def test_public_workflow_scripts_parse_offline_without_execution() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/og-public-artifact-qualification.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    bash = shutil.which("bash")
    assert bash is not None
    environment = dict(os.environ)
    environment.pop("BASH_ENV", None)
    environment.pop("ENV", None)
    count = 0
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" not in step:
                continue
            script = step["run"].encode()
            assert len(script) <= 32768
            result = subprocess.run(
                [bash, "--noprofile", "--norc", "-n"],
                input=script,
                capture_output=True,
                timeout=5,
                env=environment,
                check=False,
            )
            assert len(result.stdout) <= 4096 and len(result.stderr) <= 4096
            assert result.returncode == 0, (
                step.get("name"),
                result.stderr.decode(errors="replace"),
            )
            count += 1
    assert count == 53


@pytest.mark.parametrize(
    "kind", ["valid", "top-valid", "uncatalogued", "sourceless", "top-package", "namespace"]
)
def test_recovery_checkout_requires_catalogued_loaded_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    recovery = _recovery()
    verifier, producer = tmp_path / "verifier", tmp_path / "producer"
    verifier.mkdir()
    producer.mkdir()
    catalog = {}
    for name in recovery.REQUIRED_TOOLS:
        path = verifier / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic committed tooling\n")
        catalog[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    filename = verifier / "scripts/release_qualification/alpha3_recovery.py"
    name = "scripts.release_qualification.alpha3_recovery"
    if kind in ("uncatalogued", "sourceless"):
        filename = verifier / ("ignored.pyc" if kind == "sourceless" else "ignored.py")
        filename.write_bytes(b"not committed; never executed\n")
    elif kind == "top-package":
        name = "scripts"
        filename = producer / "__init__.py"
        filename.write_bytes(b"not verifier tooling; never executed\n")
    elif kind == "top-valid":
        name = "scripts"
        filename = verifier / "scripts/__init__.py"
        filename.write_bytes(b"committed package; never executed\n")
        catalog["scripts/__init__.py"] = hashlib.sha256(filename.read_bytes()).hexdigest()
    module = SimpleNamespace(__file__=str(filename), __spec__=SimpleNamespace(origin=str(filename)))
    if kind == "namespace":
        module = SimpleNamespace(
            __file__=None,
            __spec__=SimpleNamespace(submodule_search_locations=[str(verifier)]),
        )
    namespace = SimpleNamespace(
        __file__=None,
        __spec__=SimpleNamespace(submodule_search_locations=[str(verifier / "scripts")]),
    )
    modules = {"scripts": namespace, name: module}
    monkeypatch.setattr(recovery, "sys", SimpleNamespace(modules=modules))
    monkeypatch.setattr(
        recovery, "__file__", str(verifier / "scripts/release_qualification/alpha3_recovery.py")
    )
    monkeypatch.setattr(
        recovery.bundle,
        "_git_value",
        lambda root, arg: (
            (SOURCE if arg == "HEAD" else TREE)
            if root == producer
            else (VERIFIER if arg == "HEAD" else VERIFIER_TREE)
        ),
    )
    monkeypatch.setattr(recovery.installed, "_git_value", lambda *_args: "")
    monkeypatch.setattr(recovery.bundle, "_git_tree_file_digests", lambda _root: catalog)
    if kind in ("valid", "top-valid"):
        assert (
            dict(recovery.checkout_binding(producer, verifier, VERIFIER, VERIFIER_TREE).tool_files)
            == catalog
        )
    else:
        with pytest.raises(ValueError):
            recovery.checkout_binding(producer, verifier, VERIFIER, VERIFIER_TREE)
