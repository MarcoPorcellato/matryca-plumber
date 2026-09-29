from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "windows-launcher-qualification.yml"
REQUIRED_CI = WORKFLOWS / "ci.yml"

SOURCE_COMMIT = "bea138450f0e620a4ce5765b0e38cff7b9f0799f"
SOURCE_PATH = "crates/uv-trampoline-builder/trampolines/uv-trampoline-x86_64-console.exe"
SOURCE_BLOB = "c6d3881fc6b7d3ef0c6d3c08d505ab2b4c0ad9c4"
SOURCE_SIZE = 45_056
SOURCE_SHA256 = "0447a4febf43fdd958e4236129d6050b1dad64c124c43355d557542b3229cae8"
PINNED_ACTION = re.compile(r"^[^./][^@]*@[0-9a-f]{40}$")


def _load_workflow(path: Path) -> dict[str, Any]:
    loaded = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _external_uses(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "uses" and isinstance(child, str) and not child.startswith("./"):
                found.append(child)
            found.extend(_external_uses(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_external_uses(child))
    return found


def test_workflow_is_separate_from_required_ci_and_has_unfiltered_triggers() -> None:
    workflow = _load_workflow(WORKFLOW)
    triggers = workflow["on"]

    assert set(triggers) == {"pull_request", "push", "merge_group"}
    assert triggers["pull_request"] == {}
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["merge_group"]["types"] == ["checks_requested"]
    assert all(
        isinstance(event, dict) and "paths" not in event and "paths-ignore" not in event
        for event in triggers.values()
    )

    required_ci = _load_workflow(REQUIRED_CI)
    gate = required_ci["jobs"]["ironclad-gatekeeper"]
    assert set(gate["needs"]) == {
        "dependency-review",
        "python-312-quality",
        "frontend-quality",
        "python-313-compatibility",
        "shadow-cross-platform",
    }
    assert "windows-launcher-qualification" not in str(required_ci)


def test_workflow_has_least_permissions_bounded_job_and_cancellable_concurrency() -> None:
    workflow = _load_workflow(WORKFLOW)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "true"

    jobs = workflow["jobs"]
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert int(job["timeout-minutes"]) <= 15
    assert job["runs-on"] == "windows-latest"


def test_workflow_binds_read_only_upstream_template_and_reconstructs_candidate() -> None:
    workflow = _load_workflow(WORKFLOW)
    rendered = WORKFLOW.read_text(encoding="utf-8")
    assert SOURCE_COMMIT in rendered
    assert SOURCE_PATH in rendered
    assert SOURCE_BLOB in rendered
    assert str(SOURCE_SIZE) in rendered
    assert SOURCE_SHA256 in rendered

    jobs = workflow["jobs"]
    job = next(iter(jobs.values()))
    steps = job["steps"]
    assert any(
        step.get("with", {}).get("ref") == SOURCE_COMMIT
        and step.get("with", {}).get("repository") == "astral-sh/uv"
        and step.get("with", {}).get("sparse-checkout") == SOURCE_PATH
        and step.get("with", {}).get("sparse-checkout-cone-mode") == "false"
        for step in steps
        if isinstance(step, dict)
    )

    script = "\n".join(str(step.get("run", "")) for step in steps if isinstance(step, dict))
    assert "_reconstruct_launcher" in script
    assert "verify_windows_console_launcher" in script
    assert "template_path.read_bytes()" in script
    assert "template_path.write" not in script
    assert "rev-parse" in script
    assert "cat-file" in script
    assert 'source_blob_spec = f"HEAD:{source_relative_path.as_posix()}"' in script
    assert '"rev-parse", source_blob_spec' in script
    assert '"cat-file", "-s", source_blob_spec' in script
    assert "require_template_unchanged(template_before)" in script
    assert script.count("require_template_unchanged(template_before)") == 2
    assert "candidate_path.write_bytes(candidate)" in script
    assert "candidate_on_disk == candidate" in script
    python_source = script.split("@'\n", maxsplit=1)[1].rsplit("\n'@ | uv run", maxsplit=1)[0]
    syntax_tree = ast.parse(python_source)
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(syntax_tree))
    require_function = next(
        (
            node
            for node in syntax_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "require"
        ),
        None,
    )
    assert require_function is not None
    assert any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "SystemExit"
        for node in ast.walk(require_function)
    )

    process_targets: list[str] = []
    for node in ast.walk(syntax_tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        qualified_name = ast.unparse(node.func)
        assert qualified_name not in {"os.system", "os.startfile"}
        assert not qualified_name.startswith(("os.exec", "os.spawn"))
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
            continue
        assert node.func.attr == "run"
        command = node.args[0]
        assert isinstance(command, ast.List)
        first_argument = command.elts[0]
        if isinstance(first_argument, ast.Constant) and first_argument.value == "git":
            continue
        assert isinstance(first_argument, ast.Call)
        assert isinstance(first_argument.func, ast.Name) and first_argument.func.id == "str"
        assert len(first_argument.args) == 1 and isinstance(first_argument.args[0], ast.Name)
        process_targets.append(first_argument.args[0].id)
    assert process_targets == ["candidate_path"]
    assert "timeout=10" in python_source
    assert "PLUMBER_WINDOWS_LAUNCHER_QUALIFICATION_OK" in script
    assert "TemporaryDirectory(" in script


def test_all_external_actions_are_full_sha_pinned() -> None:
    workflow = _load_workflow(WORKFLOW)
    references = _external_uses(workflow)
    assert references
    assert all(PINNED_ACTION.fullmatch(reference) for reference in references)
