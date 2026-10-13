from __future__ import annotations

import ast
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CI_WORKFLOW = WORKFLOWS / "ci.yml"
CODEQL_WORKFLOW = WORKFLOWS / "codeql.yml"
MAKEFILE = ROOT / "Makefile"

REQUIRED_NEEDS = {
    "dependency-review",
    "python-312-quality",
    "frontend-quality",
    "python-313-compatibility",
    "shadow-cross-platform",
}
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


def test_required_ci_always_reports_for_pr_push_and_merge_queue() -> None:
    workflow = _load_workflow(CI_WORKFLOW)
    triggers = workflow["on"]
    assert triggers["pull_request"] == {}
    assert triggers["push"]["branches"] == ["main"]
    assert triggers["merge_group"]["types"] == ["checks_requested"]
    assert "paths" not in triggers
    assert "paths-ignore" not in triggers
    assert workflow["concurrency"] == {
        "group": "ci-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": "true",
    }


def test_ironclad_gatekeeper_aggregates_every_blocking_lane() -> None:
    jobs = _load_workflow(CI_WORKFLOW)["jobs"]
    assert jobs["dependency-review"]["if"] == "github.event_name == 'pull_request'"
    gate = jobs["ironclad-gatekeeper"]
    assert gate["name"] == "Ironclad Gatekeeper"
    assert set(gate["needs"]) == REQUIRED_NEEDS
    assert gate["if"] == "always()"
    assert "continue-on-error" not in gate
    assert "${{ needs.python-313-compatibility.result }}" in gate["steps"][0]["env"].values()
    assert "${{ needs.shadow-cross-platform.result }}" in gate["steps"][0]["env"].values()


def test_python_313_and_shadow_contract_are_blocking() -> None:
    jobs = _load_workflow(CI_WORKFLOW)["jobs"]
    python_313 = jobs["python-313-compatibility"]
    assert "continue-on-error" not in python_313
    assert "if" not in python_313
    assert python_313["timeout-minutes"] == "15"
    shadow = jobs["shadow-cross-platform"]
    assert shadow["strategy"]["matrix"]["os"] == ["macos-latest", "windows-latest"]
    assert "continue-on-error" not in shadow


def test_codeql_supports_exact_merge_group_event() -> None:
    workflow = _load_workflow(CODEQL_WORKFLOW)
    assert workflow["on"]["merge_group"]["types"] == ["checks_requested"]
    assert workflow["permissions"] == {"contents": "read", "security-events": "write"}


def test_all_external_actions_are_full_sha_pinned() -> None:
    references: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        references.extend(_external_uses(_load_workflow(path)))
    assert references
    assert all(PINNED_ACTION.fullmatch(reference) for reference in references)


def test_local_receipt_control_plane_is_absent() -> None:
    assert not (ROOT / ".commit-ci-preflight.toml").exists()
    assert not (ROOT / ".commit-ci-policy.toml").exists()
    assert not (WORKFLOWS / "receipt-gate.yml").exists()
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "ccp-" not in makefile
    assert "commit-ci-preflight" not in makefile
    assert all(
        "pull_request_target" not in path.read_text(encoding="utf-8")
        for path in WORKFLOWS.glob("*.yml")
    )


def test_og_gateway_bootstrap_diagnostic_is_exact_head_and_supplemental() -> None:
    workflow = _load_workflow(CI_WORKFLOW)
    jobs = workflow["jobs"]
    diagnostic = jobs["og-gateway-bootstrap-diagnostic"]
    assert diagnostic["if"] == (
        "github.event_name == 'pull_request' "
        "&& github.head_ref == 'feat/og-operational-gateway-t2b-20261010'"
    )
    assert diagnostic["runs-on"] == "ubuntu-24.04"
    assert diagnostic["timeout-minutes"] == "10"
    assert diagnostic["permissions"] == {"contents": "read"}
    assert "continue-on-error" not in diagnostic
    assert "needs" not in diagnostic
    assert "og-gateway-bootstrap-diagnostic" not in jobs["ironclad-gatekeeper"]["needs"]
    checkout = diagnostic["steps"][0]
    assert checkout["uses"] == jobs["python-312-quality"]["steps"][0]["uses"]
    assert checkout["with"] == {
        "ref": "${{ github.event.pull_request.head.sha }}",
        "persist-credentials": "false",
    }
    for job in REQUIRED_NEEDS - {"dependency-review"}:
        assert "ref" not in jobs[job]["steps"][0].get("with", {})
    assert diagnostic["steps"][1]["uses"] == jobs["python-312-quality"]["steps"][1]["uses"]
    assert diagnostic["steps"][1]["with"]["python-version"] == "3.12"
    assert diagnostic["steps"][2]["run"] == "uv sync --locked --extra dev"
    focused = diagnostic["steps"][3]
    assert focused["timeout-minutes"] == "3"
    assert "continue-on-error" not in focused
    assert focused["env"]["SELECTED_HEAD"] == "${{ github.event.pull_request.head.sha }}"
    assert focused["env"]["WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
    assert focused["env"]["WORKFLOW_REF"] == "${{ github.workflow_ref }}"
    assert ".venv/bin/python -I -B - <<'PY'" in focused["run"]
    assert "-n" in focused["run"] and '"0"' in focused["run"]
    assert "-o" in focused["run"] and '"addopts="' in focused["run"]
    assert not any("upload-artifact@" in action for action in _external_uses(diagnostic))


def test_og_gateway_bootstrap_diagnostic_rejects_incomplete_evidence() -> None:
    focused = _load_workflow(CI_WORKFLOW)["jobs"]["og-gateway-bootstrap-diagnostic"]["steps"][3]
    source = focused["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    parsed = ast.parse(source)
    inventory = next(
        node.value
        for node in parsed.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "EXPECTED_NODES"
            for target in node.targets
        )
    )
    expected = ast.literal_eval(inventory)
    assert len(expected) == len(set(expected)) == 30
    assert len({node.split("[", 1)[0] for node in expected}) == 12
    functions: list[ast.stmt] = [
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"validate_case_ids", "validate_reports", "validate_origin"}
    ]
    assert len(functions) == 3
    namespace: dict[str, Any] = {"EXPECTED_NODES": expected, "Path": Path}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "<CI diagnostic>", "exec"), namespace)
    namespace["validate_case_ids"](expected)
    for incomplete in (expected[:-1], expected + [expected[0]], list(reversed(expected))):
        with pytest.raises(RuntimeError, match="case inventory"):
            namespace["validate_case_ids"](incomplete)
    passed = [("setup", "passed", False), ("call", "passed", False), ("teardown", "passed", False)]
    reports = {node: list(passed) for node in expected}
    namespace["validate_reports"](reports)
    for phase in ("setup", "call", "teardown"):
        for outcome, wasxfail in (("skipped", False), ("failed", False), ("passed", True)):
            bad = {node: list(passed) for node in expected}
            bad[expected[0]] = [
                (when, outcome, wasxfail) if when == phase else (when, result, xfail)
                for when, result, xfail in passed
            ]
            with pytest.raises(RuntimeError, match="case outcomes"):
                namespace["validate_reports"](bad)
    for bad in ({}, {node: value for node, value in reports.items() if node != expected[0]}):
        with pytest.raises(RuntimeError, match="case outcomes"):
            namespace["validate_reports"](bad)
    origin = ROOT / "src" / "__init__.py"
    module = SimpleNamespace(__file__=str(origin), __spec__=SimpleNamespace(origin=str(origin)))
    namespace["validate_origin"](module, origin)
    for file, spec in (
        (None, str(origin)),
        (str(ROOT / "other.py"), str(origin)),
        (str(origin), None),
        (str(origin), str(ROOT / "other.py")),
    ):
        module = SimpleNamespace(__file__=file, __spec__=SimpleNamespace(origin=spec))
        with pytest.raises(RuntimeError, match="source origin"):
            namespace["validate_origin"](module, origin)
