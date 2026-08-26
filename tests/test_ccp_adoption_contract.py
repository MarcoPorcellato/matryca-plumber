"""Fail-closed contract tests for hybrid Commit CI Preflight adoption."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".commit-ci-preflight.toml"
POLICY_PATH = ROOT / ".commit-ci-policy.toml"
RECEIPT_GATE_PATH = ROOT / ".github" / "workflows" / "receipt-gate.yml"
CI_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"
MAKEFILE_PATH = ROOT / "Makefile"

EXPECTED_IMAGES = {
    "python312": (
        "ghcr.io/astral-sh/uv@sha256:"
        "e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58"
    ),
    "python313": (
        "ghcr.io/astral-sh/uv@sha256:"
        "531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca"
    ),
    "node22": (
        "docker.io/library/node@sha256:"
        "d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436"
    ),
}
EXPECTED_LIMITS = {
    "python312": (4, 6144, 512),
    "python313": (4, 6144, 512),
    "node22": (2, 3072, 256),
}
EXPECTED_CHECKS = {
    "python312-sync": "python312",
    "python312-format": "python312",
    "python312-lint": "python312",
    "python312-types": "python312",
    "python312-sandbox-read": "python312",
    "python312-version": "python312",
    "python312-agents": "python312",
    "python312-public-metrics": "python312",
    "python312-security": "python312",
    "python312-docs": "python312",
    "python312-system-prompt": "python312",
    "python312-tests": "python312",
    "python313-sync": "python313",
    "python313-tests": "python313",
    "node22-install": "node22",
    "node22-lint": "node22",
    "node22-tests": "node22",
    "node22-build": "node22",
}
EXPECTED_CCP_SOURCE_COMMIT = "3fccc197e5055a2759ee7afe51b91133938ec904"
EXPECTED_CACHE_MOUNTS = {
    ".ccp-mounts/coverage",
    ".ccp-mounts/hypothesis",
    ".ccp-mounts/mypy",
    ".ccp-mounts/npm",
    ".ccp-mounts/ruff",
    ".ccp-mounts/uv",
    ".ccp-mounts/venv-py312",
    ".ccp-mounts/venv-py313",
    "frontend/dist",
    "frontend/node_modules",
}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _is_relative_normalized(path: str) -> bool:
    candidate = Path(path)
    return (
        not candidate.is_absolute() and ".." not in candidate.parts and "." not in candidate.parts
    )


def test_multi_runtime_config_is_closed_and_digest_pinned() -> None:
    config = _load_toml(CONFIG_PATH)
    assert config["schema_version"] == "2.0"
    assert config["project"] == "MarcoPorcellato/matryca-plumber"
    assert config["receipt"] == {
        "output": ".ccp/receipt.json",
        "freshness_seconds": 86400,
    }
    assert config.get("environment", {}).get("allow", []) == []

    runtimes = {runtime["id"]: runtime for runtime in config["runtimes"]}
    assert set(runtimes) == set(EXPECTED_IMAGES)
    for runtime_id, runtime in runtimes.items():
        assert runtime["kind"] == "docker_compatible"
        assert runtime["image"] == EXPECTED_IMAGES[runtime_id]
        assert "@sha256:" in runtime["image"]
        assert not runtime["image"].endswith((":latest", ":main"))
        assert (
            runtime["cpu_count"],
            runtime["memory_mib"],
            runtime["pids_limit"],
        ) == EXPECTED_LIMITS[runtime_id]
        assert runtime["network"] is True

    checks = {check["id"]: check for check in config["checks"]}
    assert {check_id: check["runtime_id"] for check_id, check in checks.items()} == EXPECTED_CHECKS
    assert all(check["required"] is True for check in checks.values())
    assert all(isinstance(check["argv"], list) and check["argv"] for check in checks.values())
    assert all(check["argv"][0] != "sh" for check in checks.values())
    assert all("shell" not in check for check in checks.values())
    assert all(check["runtime_id"] in runtimes for check in checks.values())

    mounts = {cache["mount_path"] for cache in config["caches"]}
    assert mounts == EXPECTED_CACHE_MOUNTS
    assert all(_is_relative_normalized(mount) for mount in mounts)
    for left in mounts:
        for right in mounts:
            if left != right:
                assert not right.startswith(f"{left}/")


def test_policy_exactly_binds_config_images_platforms_and_checks() -> None:
    config = _load_toml(CONFIG_PATH)
    policy = _load_toml(POLICY_PATH)
    assert policy["schema_version"] == "2.0"
    assert policy["project"] == config["project"]
    assert policy["max_age_seconds"] == config["receipt"]["freshness_seconds"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", policy["configuration_digest"])

    required = {item["id"]: item["runtime_id"] for item in policy["required_checks"]}
    assert required == EXPECTED_CHECKS

    policy_runtimes = {runtime["id"]: runtime for runtime in policy["runtimes"]}
    assert set(policy_runtimes) == set(EXPECTED_IMAGES)
    for runtime_id, runtime in policy_runtimes.items():
        assert runtime["image_reference"] == EXPECTED_IMAGES[runtime_id]
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", runtime["configuration_digest"])
        assert runtime["platforms"] == [
            {
                "host_os": "macos",
                "host_arch": "aarch64",
                "runtime_kind": "docker_compatible",
            }
        ]


def test_ccp_local_state_is_narrowly_ignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".ccp/receipt.json" in ignored
    assert ".ccp-mounts/" in ignored
    assert ".commit-ci-preflight.toml" not in ignored
    assert ".commit-ci-policy.toml" not in ignored


def test_make_targets_preserve_the_matrix_preflight_hold() -> None:
    makefile = MAKEFILE_PATH.read_text(encoding="utf-8")
    assert "ccp-plan:" in makefile
    assert "ccp-verify:" in makefile
    assert "ccp-savings-check:" in makefile
    assert "ccp-doctor:" not in makefile
    assert "ccp-dry-run:" not in makefile


def test_receipt_gate_is_observation_only_and_trusted() -> None:
    workflow = RECEIPT_GATE_PATH.read_text(encoding="utf-8")
    parsed = yaml.load(workflow, Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    assert parsed["on"]["pull_request_target"]["types"] == [
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
        "labeled",
    ]
    assert parsed["permissions"] == {"contents": "read", "statuses": "write"}
    assert set(parsed["jobs"]) == {"receipt"}
    assert parsed["jobs"]["receipt"]["if"] == (
        "github.event.pull_request.draft == false && "
        "github.event.pull_request.head.repo.full_name == github.repository && "
        "github.event.pull_request.user.login != 'dependabot[bot]' && "
        "contains(github.event.pull_request.labels.*.name, "
        "'ci:observe-local-receipt')"
    )
    required = (
        "pull_request_target:",
        "types: [opened, synchronize, reopened, ready_for_review, labeled]",
        "contents: read",
        "statuses: write",
        "timeout-minutes: 6",
        "github.event.pull_request.head.sha",
        "github.event.pull_request.head.repo.full_name == github.repository",
        "github.event.pull_request.user.login != 'dependabot[bot]'",
        "github.event.pull_request.base.sha",
        f"CCP_SOURCE_COMMIT: {EXPECTED_CCP_SOURCE_COMMIT}",
        "repository: MarcoPorcellato/commit-ci-preflight",
        "ref: ${{ env.CCP_SOURCE_COMMIT }}",
        "ccp-evidence/${{ github.event.pull_request.head.sha }}",
        "trusted-repository/.commit-ci-policy.toml",
        "commit-ci-preflight/receipt",
        "ci:observe-local-receipt",
        "if: always()",
    )
    for token in required:
        assert token in workflow

    checkout_pins = re.findall(r"actions/checkout@([0-9a-f]{40})", workflow)
    assert len(checkout_pins) == 3
    forbidden = (
        "pull_request:\n",
        "pull_request.head.ref",
        "actions/cache",
        "docker run",
        "cargo test",
        "make ",
        "uv run",
        "npm ",
        "secrets.",
        "permissions: write-all",
    )
    for token in forbidden:
        assert token not in workflow

    ci_workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "if: needs.receipt" not in ci_workflow
    assert "make ci" in ci_workflow
