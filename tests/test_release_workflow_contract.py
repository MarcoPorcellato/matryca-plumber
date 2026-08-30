from __future__ import annotations

from pathlib import Path
from typing import Any, cast

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
    verify_script = _step(
        jobs["verify"], "Verify signed tag and protected-main reachability"
    )["run"]
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


def test_publish_verifies_manifest_and_never_rebuilds() -> None:
    publish = _load_release()["jobs"]["publish-release"]
    assert publish["permissions"] == {
        "attestations": "read",
        "contents": "write",
        "id-token": "write",
    }
    download = _step(publish, "Download verified release bundle")
    assert download["uses"] == "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"
    verify = _step(publish, "Verify downloaded distribution digests")["run"]
    assert "sha256sum --check" in verify
    assert "find dist -maxdepth 1 -type f" in verify
    assert "release-manifest/SHA256SUMS" in verify
    provenance = _step(publish, "Verify downloaded provenance attestations")["run"]
    assert "gh attestation verify" in provenance
    assert "--signer-workflow" in provenance
    assert "dist/*.whl" in provenance
    assert "dist/*.tar.gz" in provenance
    rendered = "\n".join(str(step.get("run", "")) for step in publish["steps"])
    assert "make release-build" not in rendered
