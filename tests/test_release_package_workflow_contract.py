from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release-package-qualification.yml"
JOB_NAMES = {"verify-source", "build-bundle", "platform-qualification", "qualification-gate"}
EXPECTED_RUNNERS = {
    ("ubuntu-24.04", "x64"),
    ("macos-15", "arm64"),
    ("windows-2022", "x64"),
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
PINNED_ACTION = re.compile(r"^[^./][^@]*@[0-9a-f]{40}$")


def _load_workflow() -> dict[str, Any]:
    assert WORKFLOW_PATH.is_file(), "manual package qualification workflow is missing"
    loaded = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
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


def _run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step["run"]) for step in job.get("steps", []) if "run" in step)


def _named_step(job: dict[str, Any], name: str) -> dict[str, Any]:
    steps = job["steps"]
    matches = [step for step in steps if step.get("name") == name]
    assert len(matches) == 1, f"expected one {name!r} step"
    return cast(dict[str, Any], matches[0])


def _assert_gate_contract(gate: dict[str, Any]) -> None:
    assert set(gate["needs"]) == JOB_NAMES - {"qualification-gate"}
    assert gate.get("if") == "always()"
    assert "continue-on-error" not in gate
    run_text = _run_text(gate)
    env = {
        str(key): str(value)
        for step in gate.get("steps", [])
        for key, value in step.get("env", {}).items()
    }
    for dependency in sorted(JOB_NAMES - {"qualification-gate"}):
        result_variables = [
            key for key, value in env.items() if f"needs.{dependency}.result" in value
        ]
        assert result_variables, f"gate does not bind {dependency} result"
        assert any(
            re.search(
                rf"(?:test|\[\[)\s+\"?\$?\{{?{re.escape(variable)}\}}?\"?\s+(?:=|==)\s+success",
                run_text,
            )
            for variable in result_variables
        ), f"gate does not require {dependency} success"
    assert "verify-receipts" in run_text


def _runner_rows(workflow: dict[str, Any]) -> set[tuple[str, str]]:
    rows = workflow["jobs"]["platform-qualification"]["strategy"]["matrix"]["include"]
    return {(str(row["runs-on"]), str(row["architecture"])) for row in rows}


def _assert_requirements_export_contract(step: dict[str, Any]) -> None:
    command = str(step.get("run", ""))
    formats = re.findall(r"--format(?:=|\s+)([^\s]+)", command)
    assert "uv export" in command
    assert formats == ["requirements.txt"]


def _assert_sdist_build_contract(platform: dict[str, Any]) -> None:
    build = _named_step(platform, "Build temporary wheel from authenticated sdist")
    build_run = str(build.get("run", ""))
    build_env = {str(key): str(value) for key, value in build.get("env", {}).items()}
    assert build.get("id") == "sdist-build"
    assert "prepare-sdist-build" in build_run
    for option in (
        "--artifact",
        "--source-root",
        "--python",
        "--uv",
        "--uv-sha256",
        "--wheel-output",
    ):
        assert option in build_run
    assert "EXPECTED_BINDING_JSON" in build_env
    assert "VERIFIED_UV_PATH" in build_env
    assert "VERIFIED_UV_SHA256" in build_env
    assert "sdist-wheel-output" in build_run
    assert "$GITHUB_WORKSPACE/dist" not in build_run
    assert "sdist-build-receipt.json" in build_run
    uv_verification = _named_step(platform, "Verify official uv 0.12.19 runner binary")
    assert uv_verification.get("id") == "verify-uv"
    uv_output = str(uv_verification.get("run", ""))
    assert "uv_path=" in uv_output and "uv_sha256=" in uv_output
    assert "steps.verify-uv.outputs.uv_path" in build_env["VERIFIED_UV_PATH"]
    assert "steps.verify-uv.outputs.uv_sha256" in build_env["VERIFIED_UV_SHA256"]

    install = _named_step(platform, "Install and verify the bound source distribution")
    install_run = str(install.get("run", ""))
    install_env = {str(key): str(value) for key, value in install.get("env", {}).items()}
    assert "SDIST_BUILD_RECEIPT" in install_env
    assert "SDIST_WHEEL_OUTPUT" in install_env
    assert install_env["SDIST_WHEEL_OUTPUT"] == "${{ runner.temp }}/sdist-wheel-output"
    assert "EXPECTED_BINDING_JSON" in install_env
    assert "--no-deps" in install_run
    assert '"$SDIST_TEMP_WHEEL"' in install_run
    assert "--kind sdist" in install_run
    assert '--artifact "$GITHUB_WORKSPACE/$SDIST"' in install_run
    assert (
        'uv pip install --python "$SDIST_PYTHON" --no-deps "$GITHUB_WORKSPACE/$SDIST"'
        not in install_run
    )
    assert "sdist-receipt.json" in install_run
    for evidence_field in (
        'receipt.get("sdist_name")',
        'receipt.get("sdist_size")',
        'receipt.get("sdist_sha256")',
        'receipt.get("source_commit")',
        'receipt.get("source_tree")',
        'receipt.get("binding_sha256")',
        'receipt.get("wheel_size")',
        'receipt.get("wheel_sha256")',
    ):
        assert evidence_field in install_run

    receipt = _named_step(platform, "Write sanitized platform receipt with artifact-digest binding")
    receipt_script = str(receipt.get("run", ""))
    assert '"sdist_build"' in receipt_script
    assert "sdist-build-receipt.json" in receipt_script


def _assert_uv_security_contract(rendered: str) -> None:
    assert "0.12.16" not in rendered
    assert rendered.count("0.12.19") >= 8
    expected_assets = {
        "uv-aarch64-apple-darwin.tar.gz": (
            "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba"
        ),
        "uv-x86_64-pc-windows-msvc.zip": (
            "6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0"
        ),
        "uv-x86_64-unknown-linux-gnu.tar.gz": (
            "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8"
        ),
    }
    for asset, digest in expected_assets.items():
        assert re.search(rf'"{re.escape(asset)}",\s*"{re.escape(digest)}"', rendered)
    assert "https://github.com/astral-sh/uv/releases/tag/0.12.19" in rendered
    assert re.search(
        r"printf '%s  %s\\n' \\\s+"
        r"23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8 \\\s+"
        r'"\$archive" \| shasum -a 256 -c -',
        rendered,
    )


def _assert_aggregate_uv_bootstrap(gate: dict[str, Any]) -> None:
    steps = gate["steps"]
    verifier = _named_step(gate, "Verify official uv 0.12.19 receipt-gate binary")
    sync = _named_step(gate, "Install locked receipt-verifier dependencies")
    verifier_run = str(verifier.get("run", ""))
    sync_run = str(sync.get("run", ""))
    assert steps.index(verifier) + 1 == steps.index(sync)
    assert "0.12.19" in verifier_run
    assert "uv-x86_64-unknown-linux-gnu.tar.gz" in verifier_run
    assert "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8" in verifier_run
    assert "shasum -a 256 -c -" in verifier_run
    assert "tar -xzf" in verifier_run
    assert 'cmp "$verified" "$(command -v uv)"' in verifier_run
    assert "uv sync --locked --extra dev" in sync_run


def _assert_windows_no_go_before_package_work(platform: dict[str, Any]) -> None:
    steps = platform["steps"]
    names = [str(step.get("name", "")) for step in steps]
    verified_uv_index = names.index("Verify official uv 0.12.19 runner binary")
    architecture_index = names.index("Check actual runner operating system and architecture")
    no_go_index = names.index("Enforce Windows launcher NO-GO boundary")
    sync_index = names.index("Install locked qualification dependencies")
    artifact_index = next(
        index
        for index, step in enumerate(steps)
        if "download-artifact@" in str(step.get("uses", ""))
    )
    assert verified_uv_index < architecture_index < no_go_index < sync_index < artifact_index
    for step in steps[:no_go_index]:
        command = str(step.get("run", ""))
        assert "uv sync" not in command
        assert "uv pip install" not in command
        assert "uv venv" not in command
        assert "verify-handoff" not in command
        assert "verify-installed" not in command
        assert "prepare-sdist-build" not in command
        assert "download-artifact@" not in str(step.get("uses", ""))


def _assert_unique_receipt_paths(platform: dict[str, Any], gate: dict[str, Any]) -> None:
    rows = platform["strategy"]["matrix"]["include"]
    writer = _named_step(platform, "Write sanitized platform receipt with artifact-digest binding")
    writer_script = str(writer.get("run", ""))
    assert "PLATFORM_OS" in writer_script
    assert "PLATFORM_ARCHITECTURE" in writer_script
    assert "receipt_path.write_text(" in writer_script

    upload = next(
        step for step in platform["steps"] if "upload-artifact@" in str(step.get("uses", ""))
    )
    path_template = str(upload.get("with", {}).get("path", ""))
    assert path_template == "platform-receipt-${{ matrix.os }}-${{ matrix.architecture }}.json"
    rendered_paths = [
        path_template.replace("${{ matrix.os }}", str(row["os"])).replace(
            "${{ matrix.architecture }}", str(row["architecture"])
        )
        for row in rows
    ]
    expected_paths = [f"platform-receipt-{row['os']}-{row['architecture']}.json" for row in rows]
    assert rendered_paths == expected_paths
    assert len(rendered_paths) == 3
    assert len(set(rendered_paths)) == 3
    assert all(path.endswith(".json") for path in rendered_paths)

    downloader = _named_step(gate, "Download all unique platform receipts")
    assert downloader.get("with", {}).get("merge-multiple") == "true"
    verify_run = _run_text(gate)
    assert "verify-receipts" in verify_run
    assert "--expected-platform-count 3" in verify_run


def test_workflow_is_manual_only_and_requires_an_exact_main_commit() -> None:
    workflow = _load_workflow()
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"expected_commit"}
    assert inputs["expected_commit"]["required"] == "true"
    assert inputs["expected_commit"]["type"] == "string"

    source = workflow["jobs"]["verify-source"]
    script = _run_text(source)
    assert "refs/heads/main" in script
    assert "GITHUB_REF" in script
    assert "GITHUB_SHA" in script
    assert "EXPECTED_COMMIT" in script
    assert FULL_SHA.pattern in script or r"[0-9a-f]{40}" in script
    assert any("EXPECTED_COMMIT" in line and "GITHUB_SHA" in line for line in script.splitlines())
    assert any("GITHUB_REF" in line and "refs/heads/main" in line for line in script.splitlines())
    assert "git rev-parse HEAD" in script
    assert "git status --porcelain" in script
    assert "git write-tree" in script or "git rev-parse HEAD^{tree}" in script
    assert "pyproject.toml" in script


def test_uv_is_pinned_to_security_fixed_release_and_all_official_asset_checksums() -> None:
    rendered = WORKFLOW_PATH.read_text(encoding="utf-8")
    _assert_uv_security_contract(rendered)

    vulnerable = rendered.replace("0.12.19", "0.12.16")
    with pytest.raises(AssertionError):
        _assert_uv_security_contract(vulnerable)

    tampered_digest = rendered.replace(
        "a9a8df1eedeb192f2e47e40e2faabfb387db4b850209118786d42f89dde3e0ba",
        "0" * 64,
    )
    with pytest.raises(AssertionError):
        _assert_uv_security_contract(tampered_digest)


def test_every_checkout_is_bound_to_the_validated_sha_without_credentials() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]
    checkouts: list[dict[str, Any]] = []
    for job in jobs.values():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                checkouts.append(cast(dict[str, Any], step))
    assert len(checkouts) >= 3
    for checkout in checkouts:
        options = checkout.get("with", {})
        assert options.get("ref") in {
            "${{ inputs.expected_commit }}",
            "${{ env.EXPECTED_COMMIT }}",
            "${{ needs.verify-source.outputs.source_sha }}",
        }
        assert options.get("persist-credentials") == "false"
    assert all(
        "git rev-parse HEAD" in _run_text(job)
        for job in jobs.values()
        if any(
            str(step.get("uses", "")).startswith("actions/checkout@")
            for step in job.get("steps", [])
        )
    )


def test_workflow_has_read_only_authority_no_secrets_or_publication_path() -> None:
    workflow = _load_workflow()
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job or job["permissions"] == {"contents": "read"}
    rendered = WORKFLOW_PATH.read_text(encoding="utf-8")
    lowered = rendered.lower()
    forbidden = (
        "secrets.",
        "contents: write",
        "packages: write",
        "id-token: write",
        "attestations: write",
        "gh release create",
        "pypa/gh-action-pypi-publish",
        "twine upload",
        "workflow_dispatch" + "\n  pull_request",
    )
    assert all(value.lower() not in lowered for value in forbidden)
    assert "release.yml" not in rendered


def test_all_external_actions_are_immutable_full_sha_pins() -> None:
    actions = _external_uses(_load_workflow())
    assert actions
    assert all(PINNED_ACTION.fullmatch(action) for action in actions)


def test_only_one_release_pair_is_built_and_uploaded_for_all_platforms() -> None:
    workflow = _load_workflow()
    jobs = workflow["jobs"]
    assert set(jobs) == JOB_NAMES
    build = jobs["build-bundle"]
    assert build["needs"] == "verify-source"
    builder_invocations = [
        line
        for line in _run_text(build).splitlines()
        if "qualify_release_package.py" in line and "build-handoff" in line
    ]
    assert len(builder_invocations) == 1
    assert "--ledger" in _run_text(build)
    outputs = build["outputs"]
    assert {"binding_json", "artifact_id", "artifact_digest"} <= set(outputs)
    build_text = rendered_platform(build)
    assert (
        "binding_json" in build_text
        and "artifact-id" in build_text
        and "artifact-digest" in build_text
    )

    rendered = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert len(re.findall(r"build-handoff", rendered)) == 1
    assert "build_release_artifacts.py" not in rendered
    platform = jobs["platform-qualification"]
    assert platform["needs"] == "build-bundle"
    assert "if" not in platform
    assert platform["strategy"]["fail-fast"] == "false"
    assert _runner_rows(workflow) == EXPECTED_RUNNERS


def test_platform_checks_actual_architecture_and_binds_download_before_install() -> None:
    workflow = _load_workflow()
    platform = workflow["jobs"]["platform-qualification"]
    steps = platform["steps"]
    step_names = [str(step.get("name", "")) for step in steps]
    download_index = next(
        index
        for index, step in enumerate(steps)
        if "download-artifact@" in str(step.get("uses", ""))
    )
    handoff_index = next(
        index for index, step in enumerate(steps) if "verify-handoff" in str(step.get("run", ""))
    )
    install_indices = [
        index for index, step in enumerate(steps) if "verify-installed" in str(step.get("run", ""))
    ]
    assert install_indices and download_index < handoff_index < min(install_indices)

    platform_text = _run_text(platform)
    assert "platform.machine()" in platform_text or "uname -m" in platform_text
    assert "matrix.architecture" in str(platform)
    assert "artifact-id" in rendered_platform(platform).lower()
    assert "artifact-digest" in rendered_platform(platform).lower()
    assert "needs.build-bundle.outputs" in rendered_platform(platform)
    assert step_names


def test_sdist_install_is_built_from_bound_archive_and_emits_build_provenance() -> None:
    workflow = _load_workflow()
    platform = workflow["jobs"]["platform-qualification"]
    steps = platform["steps"]
    names = [str(step.get("name", "")) for step in steps]
    build_index = names.index("Build temporary wheel from authenticated sdist")
    install_index = names.index("Install and verify the bound source distribution")
    environments_index = names.index("Create two isolated installation environments")
    assert environments_index < build_index < install_index

    windows_index = names.index("Enforce Windows launcher NO-GO boundary")
    assert windows_index < build_index < install_index
    _assert_windows_no_go_before_package_work(platform)

    _assert_sdist_build_contract(platform)

    mutated = deepcopy(platform)
    install = _named_step(mutated, "Install and verify the bound source distribution")
    install["env"]["SDIST_WHEEL_OUTPUT"] = "$GITHUB_WORKSPACE/dist"
    with pytest.raises(AssertionError):
        _assert_sdist_build_contract(mutated)


def test_windows_no_go_rejects_package_work_before_qualification_boundary() -> None:
    platform = deepcopy(_load_workflow()["jobs"]["platform-qualification"])
    _assert_windows_no_go_before_package_work(platform)

    mutated = deepcopy(platform)
    steps = mutated["steps"]
    no_go = _named_step(mutated, "Enforce Windows launcher NO-GO boundary")
    sync = _named_step(mutated, "Install locked qualification dependencies")
    no_go_index, sync_index = steps.index(no_go), steps.index(sync)
    steps[no_go_index], steps[sync_index] = steps[sync_index], steps[no_go_index]
    with pytest.raises(AssertionError):
        _assert_windows_no_go_before_package_work(mutated)

    mutated = deepcopy(platform)
    install = _named_step(mutated, "Install and verify the bound source distribution")
    install["run"] = str(install["run"]).replace(
        'digest.hexdigest() != receipt.get("wheel_sha256")', "False"
    )
    with pytest.raises(AssertionError):
        _assert_sdist_build_contract(mutated)

    mutated = deepcopy(platform)
    build = _named_step(mutated, "Build temporary wheel from authenticated sdist")
    build["run"] = str(build["run"]).replace("prepare-sdist-build", "build-handoff")
    with pytest.raises(AssertionError):
        _assert_sdist_build_contract(mutated)

    mutated = deepcopy(platform)
    receipt = _named_step(mutated, "Write sanitized platform receipt with artifact-digest binding")
    receipt["run"] = str(receipt["run"]).replace('"sdist_build"', '"build_provenance"')
    with pytest.raises(AssertionError):
        _assert_sdist_build_contract(mutated)


def test_runtime_requirements_export_uses_uvs_exact_supported_format() -> None:
    platform = _load_workflow()["jobs"]["platform-qualification"]
    export_step = _named_step(platform, "Export locked runtime requirements")
    _assert_requirements_export_contract(export_step)

    invalid_format = deepcopy(export_step)
    invalid_format["run"] = str(invalid_format["run"]).replace(
        "--format requirements.txt", "--format requirements-txt"
    )
    with pytest.raises(AssertionError):
        _assert_requirements_export_contract(invalid_format)


def rendered_platform(platform: dict[str, Any]) -> str:
    return cast(str, yaml.safe_dump(platform, sort_keys=True))


def test_each_platform_emits_a_distinct_complete_receipt_and_gate_is_fail_closed() -> None:
    workflow = _load_workflow()
    platform = workflow["jobs"]["platform-qualification"]
    text = rendered_platform(platform)
    for required_binding in (
        "run_id",
        "source_sha",
        "source_tree",
        "artifact_id",
        "artifact_digest",
        "os",
        "architecture",
        "wheel",
        "sdist",
        "focused",
    ):
        assert required_binding in text
    upload = [step for step in platform["steps"] if "upload-artifact@" in str(step.get("uses", ""))]
    assert len(upload) == 1
    assert "matrix" in rendered_platform(cast(dict[str, Any], upload[0]))
    assert "receipt" in rendered_platform(cast(dict[str, Any], upload[0])).lower()

    gate = workflow["jobs"]["qualification-gate"]
    _assert_aggregate_uv_bootstrap(gate)
    _assert_unique_receipt_paths(platform, gate)
    _assert_gate_contract(gate)
    gate_text = _run_text(gate)
    assert "verify-receipts" in gate_text
    assert "3" in gate_text
    assert "receipt" in gate_text.lower()


def test_receipt_path_contract_rejects_collision_under_merged_download() -> None:
    workflow = _load_workflow()
    platform = deepcopy(workflow["jobs"]["platform-qualification"])
    gate = workflow["jobs"]["qualification-gate"]
    _assert_unique_receipt_paths(platform, gate)

    upload = next(
        step for step in platform["steps"] if "upload-artifact@" in str(step.get("uses", ""))
    )
    upload["with"]["path"] = "platform-receipt.json"
    with pytest.raises(AssertionError):
        _assert_unique_receipt_paths(platform, gate)


def test_gate_contract_detects_removed_dependency_skip_and_missing_receipt_check() -> None:
    gate = deepcopy(_load_workflow()["jobs"]["qualification-gate"])
    mutated_dependency = deepcopy(gate)
    mutated_dependency["needs"].remove("build-bundle")
    with pytest.raises(AssertionError):
        _assert_gate_contract(mutated_dependency)

    mutated_skip = deepcopy(gate)
    mutated_skip["needs"].remove("platform-qualification")
    with pytest.raises(AssertionError):
        _assert_gate_contract(mutated_skip)

    platform = deepcopy(_load_workflow()["jobs"]["platform-qualification"])
    platform["strategy"]["matrix"]["include"].pop()
    with pytest.raises(AssertionError):
        assert _runner_rows({"jobs": {"platform-qualification": platform}}) == EXPECTED_RUNNERS

    skipped_platform = deepcopy(_load_workflow()["jobs"]["platform-qualification"])
    skipped_platform["if"] = "false"
    with pytest.raises(AssertionError):
        assert "if" not in skipped_platform

    mutated_receipt = deepcopy(gate)
    mutated_receipt["steps"] = [
        step for step in mutated_receipt["steps"] if "verify-receipts" not in str(step)
    ]
    with pytest.raises(AssertionError):
        _assert_gate_contract(mutated_receipt)


def test_gate_requires_all_dependencies_to_succeed_and_never_ignores_failures() -> None:
    workflow = _load_workflow()
    gate = workflow["jobs"]["qualification-gate"]
    _assert_gate_contract(gate)
    assert "continue-on-error" not in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_aggregate_gate_rejects_unverified_or_mismatched_uv_binary() -> None:
    gate = deepcopy(_load_workflow()["jobs"]["qualification-gate"])
    _assert_aggregate_uv_bootstrap(gate)

    mutated = deepcopy(gate)
    verifier = _named_step(mutated, "Verify official uv 0.12.19 receipt-gate binary")
    verifier["run"] = str(verifier["run"]).replace(
        "23bf5552d220e0842b65c862097b2ebaeba0064b74eda5e565e77fd25969d8c8", "0" * 64
    )
    with pytest.raises(AssertionError):
        _assert_aggregate_uv_bootstrap(mutated)

    mutated = deepcopy(gate)
    verifier = _named_step(mutated, "Verify official uv 0.12.19 receipt-gate binary")
    verifier["run"] = str(verifier["run"]).replace('cmp "$verified" "$(command -v uv)"', "true")
    with pytest.raises(AssertionError):
        _assert_aggregate_uv_bootstrap(mutated)

    mutated = deepcopy(gate)
    verifier = _named_step(mutated, "Verify official uv 0.12.19 receipt-gate binary")
    sync = _named_step(mutated, "Install locked receipt-verifier dependencies")
    verifier_index = mutated["steps"].index(verifier)
    sync_index = mutated["steps"].index(sync)
    mutated["steps"][verifier_index], mutated["steps"][sync_index] = (
        mutated["steps"][sync_index],
        mutated["steps"][verifier_index],
    )
    with pytest.raises(AssertionError):
        _assert_aggregate_uv_bootstrap(mutated)
