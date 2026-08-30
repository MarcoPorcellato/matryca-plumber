from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _load_release() -> dict[str, Any]:
    loaded = yaml.load(RELEASE_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def _step(job: dict[str, Any], name: str) -> dict[str, Any]:
    steps = job["steps"]
    selected = next(item for item in steps if item.get("name") == name)
    return cast(dict[str, Any], selected)


def test_release_is_serial_per_tag_and_never_cancels_publication() -> None:
    workflow = _load_release()
    assert workflow["on"]["push"]["tags"] == ["v*"]
    assert workflow["concurrency"] == {
        "group": "release-${{ github.ref }}",
        "cancel-in-progress": "false",
    }


def test_release_job_graph_builds_once_then_promotes() -> None:
    workflow = _load_release()
    jobs = workflow["jobs"]
    assert set(jobs) == {"verify", "destination-preflight", "build-release", "publish-release"}
    assert jobs["destination-preflight"]["needs"] == "verify"
    assert jobs["build-release"]["needs"] == "destination-preflight"
    assert jobs["publish-release"]["needs"] == "build-release"
    rendered = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    assert rendered.count("make release-build") == 1


def test_tag_identity_and_empty_destinations_are_blocking() -> None:
    jobs = _load_release()["jobs"]
    assert jobs["verify"]["permissions"] == {"checks": "read", "contents": "read"}
    verify_script = _step(jobs["verify"], "Verify signed tag and protected-main reachability")[
        "run"
    ]
    assert "verification.verified" in verify_script
    assert "git verify-tag --raw" in verify_script
    assert "FDF72C53A848EBA83AEFA0294F2221BBB930513B" in verify_script
    assert ".github/release-signing-key.asc" in verify_script
    assert "git merge-base --is-ancestor" in verify_script
    assert "GITHUB_SHA" in verify_script
    assert "check-runs" in verify_script
    assert "Ironclad Gatekeeper" in verify_script
    assert "15368" in verify_script
    preflight = _step(jobs["destination-preflight"], "Require empty release destinations")["run"]
    assert 'test "$GITHUB_STATUS" = 404' in preflight
    assert 'test "$PYPI_STATUS" = 404' in preflight


def test_destination_preflight_encodes_dynamic_path_components() -> None:
    jobs = _load_release()["jobs"]
    preflight = _step(jobs["destination-preflight"], "Require empty release destinations")["run"]
    assert "from urllib.parse import quote" in preflight
    assert 'quote(sys.argv[1], safe="")' in preflight
    assert "releases/tags/${TAG_PATH}" in preflight
    assert "matryca-plumber/${VERSION_PATH}/json" in preflight
    assert "releases/tags/${GITHUB_REF_NAME}" not in preflight
    assert "matryca-plumber/${VERSION}/json" not in preflight


def test_build_writes_manifest_attests_and_uploads_one_day_artifact() -> None:
    build = _load_release()["jobs"]["build-release"]
    assert build["permissions"] == {
        "attestations": "write",
        "contents": "read",
        "id-token": "write",
    }
    manifest = _step(build, "Create distribution digest manifest")["run"]
    assert "sha256sum" in manifest
    assert "release-manifest/SHA256SUMS" in manifest
    attest = _step(build, "Attest release distributions")
    assert attest["uses"] == "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
    upload = _step(build, "Upload verified release bundle")
    assert upload["uses"] == "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
    assert upload["with"]["retention-days"] == "1"
    assert upload["with"]["if-no-files-found"] == "error"


def _assert_publish_release_contract(publish: dict[str, Any]) -> None:
    assert publish["needs"] == "build-release"
    assert publish["runs-on"] == "ubuntu-latest"
    assert publish["timeout-minutes"] == "15"
    assert "environment" not in publish
    run_steps = [
        (str(step["name"]), str(step["run"])) for step in publish["steps"] if "run" in step
    ]
    assert len(run_steps) == 3, "unexpected publish run topology"
    assert [name for name, _ in run_steps] == [
        "Verify downloaded distribution digests",
        "Verify downloaded provenance attestations",
        "Create GitHub Release",
    ], "unexpected publish run topology"
    assert publish["permissions"] == {
        "attestations": "read",
        "contents": "write",
        "id-token": "write",
    }
    download = _step(publish, "Download verified release bundle")
    assert download["uses"] == "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"
    assert download["with"] == {"name": "release-bundle"}
    verify = _step(publish, "Verify downloaded distribution digests")["run"]
    assert "test \"$(find dist -maxdepth 1 -type f | wc -l | tr -d ' ')\" = 2" in verify
    assert (
        "test \"$(find dist -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')\" = 1" in verify
    )
    assert (
        "test \"$(find dist -maxdepth 1 -type f -name '*.tar.gz' | wc -l | tr -d ' ')\" = 1"
        in verify
    )
    assert "test \"$(wc -l < release-manifest/SHA256SUMS | tr -d ' ')\" = 2" in verify
    assert "cd dist" in verify
    assert "sha256sum --check ../release-manifest/SHA256SUMS" in verify
    assert verify.strip().splitlines() == [
        "set -euo pipefail",
        "test \"$(find dist -maxdepth 1 -type f | wc -l | tr -d ' ')\" = 2",
        "test \"$(find dist -maxdepth 1 -type f -name '*.whl' | wc -l | tr -d ' ')\" = 1",
        "test \"$(find dist -maxdepth 1 -type f -name '*.tar.gz' | wc -l | tr -d ' ')\" = 1",
        "test \"$(wc -l < release-manifest/SHA256SUMS | tr -d ' ')\" = 2",
        "cd dist",
        "sha256sum --check ../release-manifest/SHA256SUMS",
    ], "unexpected publish commands"

    provenance_step = _step(publish, "Verify downloaded provenance attestations")
    assert provenance_step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    provenance = provenance_step["run"]
    assert provenance.count("gh attestation verify") == 2
    assert "gh attestation verify dist/*.whl" in provenance
    assert "gh attestation verify dist/*.tar.gz" in provenance
    assert '--repo "$GITHUB_REPOSITORY"' in provenance
    assert '--signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/release.yml"' in provenance
    assert provenance.strip().splitlines() == [
        "set -euo pipefail",
        "gh attestation verify dist/*.whl \\",
        '  --repo "$GITHUB_REPOSITORY" \\',
        '  --signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/release.yml"',
        "gh attestation verify dist/*.tar.gz \\",
        '  --repo "$GITHUB_REPOSITORY" \\',
        '  --signer-workflow "${GITHUB_REPOSITORY}/.github/workflows/release.yml"',
    ], "unexpected publish commands"

    release_step = _step(publish, "Create GitHub Release")
    assert release_step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    release = release_step["run"]
    assert "gh release create" in release
    assert "--verify-tag" in release, "missing --verify-tag"
    assert "dist/*.whl" in release
    assert "dist/*.tar.gz" in release
    assert "--notes-file release-manifest/release_notes.md" in release
    assert 'if [[ "${GITHUB_REF_NAME}" == *-* ]]; then' in release
    assert "release_args+=(--prerelease)" in release
    assert '"${release_args[@]}"' in release
    assert release.strip().splitlines() == [
        "release_args=()",
        'if [[ "${GITHUB_REF_NAME}" == *-* ]]; then',
        "  release_args+=(--prerelease)",
        "fi",
        "gh release create \\",
        "  --verify-tag \\",
        '  "${GITHUB_REF_NAME}" \\',
        "  dist/*.whl \\",
        "  dist/*.tar.gz \\",
        "  --notes-file release-manifest/release_notes.md \\",
        '  "${release_args[@]}"',
    ], "unexpected publish commands"

    pypi = _step(publish, "Publish package to PyPI")
    assert pypi["uses"] == "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
    assert pypi["with"] == {"packages-dir": "dist/"}, "missing PyPI packages-dir"

    uses = "\n".join(str(step.get("uses", "")) for step in publish["steps"])
    assert "actions/checkout@" not in uses
    assert "setup-" not in uses


def test_publish_verifies_manifest_and_never_rebuilds() -> None:
    publish = _load_release()["jobs"]["publish-release"]
    _assert_publish_release_contract(publish)

    missing_tag = deepcopy(publish)
    release = _step(missing_tag, "Create GitHub Release")
    release["run"] = release["run"].replace("--verify-tag", "")
    with pytest.raises(AssertionError, match="missing --verify-tag"):
        _assert_publish_release_contract(missing_tag)

    missing_pypi_path = deepcopy(publish)
    _step(missing_pypi_path, "Publish package to PyPI")["with"].pop("packages-dir")
    with pytest.raises(AssertionError, match="missing PyPI packages-dir"):
        _assert_publish_release_contract(missing_pypi_path)

    npm_ci = deepcopy(publish)
    _step(npm_ci, "Verify downloaded distribution digests")["run"] += "\nnpm ci"
    with pytest.raises(AssertionError, match="unexpected publish commands"):
        _assert_publish_release_contract(npm_ci)

    duplicate_name = deepcopy(publish)
    duplicate_name["steps"].insert(
        2,
        {"name": "Verify downloaded distribution digests", "run": "npm ci"},
    )
    with pytest.raises(AssertionError, match="unexpected publish run topology"):
        _assert_publish_release_contract(duplicate_name)
