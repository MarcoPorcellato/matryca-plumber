from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

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
