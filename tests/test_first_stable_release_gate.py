"""Offline release-side checks. No tags, workflow runs, or package builds."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from scripts.release_qualification.first_stable_matrix import FIRST_STABLE_ROWS

COMMIT = "a" * 40
TREE = "b" * 40
DIGEST = "c" * 64
REPO = 1241185104
PATH = ".github/workflows/package-qualification.yml"
TAG = "v2.1.0-rc.1"
VERSION = "2.1.0rc1"
ROOT = Path(__file__).resolve().parents[1]


def tag_object(trailer: str, *, tag: str = TAG, commit: str = COMMIT) -> bytes:
    return (
        f"object {commit}\ntype commit\ntag {tag}\ntagger Example <test@example.net> 1 +0000"
        f"\n\nRelease candidate\n\n{trailer}\n-----BEGIN PGP SIGNATURE-----\nfixture\n"
    ).encode()


def test_signed_selection_and_unrelated_routes() -> None:
    from scripts.release_qualification.first_stable_release_selection import select

    line = f"Qualification-Aggregate: 77/1/900@sha256:{DIGEST}"
    for tag, version in [(TAG, VERSION), ("v2.1.0", "2.1.0")]:
        assert select(tag, version, COMMIT, tag_object(line, tag=tag)) == (77, 1, 900, DIGEST)
    for tag, version in [("v2.1.0-alpha.4", "2.1.0a4"), ("v2.0.1-rc.4", "2.0.1rc4")]:
        assert select(tag, version, COMMIT, tag_object("", tag=tag)) is None


@pytest.mark.parametrize(
    "defect",
    [
        "missing",
        "duplicate",
        "syntax",
        "post_signature",
        "wrong_object",
        "wrong_tag",
        "misroute",
        "rc_zero",
    ],
)
def test_missing_or_ambiguous_signed_selection_is_not_authority(defect: str) -> None:
    from scripts.release_qualification.first_stable_release_selection import select

    line = f"Qualification-Aggregate: 77/1/900@sha256:{DIGEST}"
    data = {
        "missing": tag_object(""),
        "duplicate": tag_object(f"{line}\n{line}"),
        "syntax": tag_object(line.replace("77/1/900", "77/1/0900")),
        "post_signature": tag_object("") + line.encode(),
        "wrong_object": tag_object(line, commit="d" * 40),
        "wrong_tag": tag_object(line, tag="v2.1.0"),
    }.get(defect, tag_object(line))
    tag = {"misroute": "v2.1.0-alpha.4", "rc_zero": "v2.1.0-rc.0"}.get(defect, TAG)
    with pytest.raises(ValueError):
        select(tag, VERSION, COMMIT, data)


def packed(doc: dict[str, Any], *, member: str = "aggregate.json") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, json.dumps(doc, separators=(",", ":"), sort_keys=True))
    return output.getvalue()


def sample(version: str = VERSION) -> tuple[dict[str, Any], dict[str, Any]]:
    run = {
        "id": 77,
        "run_attempt": 1,
        "workflow_id": 83,
        "path": PATH,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": COMMIT,
        "status": "completed",
        "conclusion": "success",
        "repository": {"id": REPO},
        "head_repository": {"id": REPO},
    }
    origin = {
        "id": 77,
        "repository_id": REPO,
        "head_repository_id": REPO,
        "head_sha": COMMIT,
        "head_branch": "main",
    }
    jobs: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    rows = []

    def job(name: str, jid: int, result: str = "success") -> None:
        jobs.append(
            {
                "name": name,
                "id": jid,
                "status": "completed",
                "conclusion": result,
                "run_id": 77,
                "run_attempt": 1,
                "head_sha": COMMIT,
                "runner_id": jid + 50,
                "runner_name": f"runner-{jid}",
            }
        )

    def artifact(name: str, aid: int) -> None:
        artifacts.append(
            {
                "name": name,
                "id": aid,
                "size_in_bytes": 4500,
                "expired": False,
                "digest": f"sha256:{DIGEST}",
                "workflow_run": dict(origin),
            }
        )

    for i, spec in enumerate(FIRST_STABLE_ROWS, start=1):
        job(f"Install first-stable ({spec.key})", i)
        artifact(f"first-stable-row-77-1-{spec.key}", 100 + i)
        rows.append(
            {
                "row_key": spec.key,
                "job_id": i,
                "runner_id": i + 50,
                "runner_name": f"runner-{i}",
                "artifact_id": 100 + i,
                "archive_size": 4500,
                "sha256": DIGEST,
                "report_sha256": DIGEST,
            }
        )
    job("Admit first-stable selection", 61)
    job("Build original first-stable artifacts", 62)
    job("Verify first-stable exact-attempt receipts", 63)
    job("Native Linux runtime startup (diagnostic)", 64, "skipped")
    artifact("first-stable-inputs-77-1", 800)
    artifact("first-stable-aggregate-77-1", 900)
    binding = {
        "source_commit": COMMIT,
        "source_tree": TREE,
        "version": version,
        "wheel_name": f"matryca_plumber-{version}-py3-none-any.whl",
        "sdist_name": f"matryca_plumber-{version}.tar.gz",
        "wheel_size": 1,
        "sdist_size": 2,
        "wheel_sha256": DIGEST,
        "sdist_sha256": DIGEST,
        "wheel_inventory_sha256": DIGEST,
        "sdist_inventory_sha256": DIGEST,
    }
    report = {
        "schema_version": 1,
        "source_commit": COMMIT,
        "source_tree": TREE,
        "version": version,
        "binding": binding,
        "repository_id": REPO,
        "run_id": 77,
        "attempt": 1,
        "build_artifact_id": 800,
        "build_artifact_sha256": DIGEST,
        "rows": rows,
        "terminal_workflow_success_proved": False,
    }
    return report, {
        "workflow": {"id": 83, "path": PATH, "state": "active"},
        "run": run,
        "jobs": {"total_count": len(jobs), "jobs": jobs},
        "artifacts": {"total_count": len(artifacts), "artifacts": artifacts},
    }


def link_bytes(meta: dict[str, Any], raw: bytes) -> str:
    sha = hashlib.sha256(raw).hexdigest()
    meta["artifacts"]["artifacts"][-1].update(size_in_bytes=len(raw), digest=f"sha256:{sha}")
    return sha


@pytest.mark.parametrize(("tag", "version"), [(TAG, VERSION), ("v2.1.0", "2.1.0")])
def test_exact_original_rc_and_final_aggregate_pass(tag: str, version: str) -> None:
    from scripts.release_qualification.first_stable_release_gate import verify

    report, meta = sample(version)
    raw = packed(report)
    verify(tag, version, COMMIT, TREE, REPO, (77, 1, 900, link_bytes(meta, raw)), meta, raw)


@pytest.mark.parametrize(
    "defect",
    [
        "commit",
        "tree",
        "version",
        "nested_tree",
        "nested_version",
        "aggregate_attempt",
        "schema_bool",
        "self_certification",
        "missing_row",
        "duplicate_row",
        "wrong_row",
        "row_job",
        "row_digest",
        "row_report_digest",
        "row_runner",
        "build_digest",
        "failed_run",
        "active_run",
        "wrong_workflow",
        "fork",
        "stale_attempt",
        "wrong_event",
        "missing_aggregate_job",
        "skipped_aggregate",
        "missed_row_job",
        "truncated_jobs",
        "expired",
        "no_artifact",
        "duplicate_artifact",
        "signed_id",
        "signed_digest",
        "api_digest",
        "corrupt_bytes",
        "zip_layout",
    ],
)
def test_incomplete_or_substituted_evidence_blocks(defect: str) -> None:
    from scripts.release_qualification.first_stable_release_gate import verify

    report, meta = sample()
    rows = report["rows"]
    jobs = meta["jobs"]["jobs"]
    artifacts = meta["artifacts"]["artifacts"]
    direct: dict[str, tuple[dict[str, Any], str, Any]] = {
        "commit": (report, "source_commit", "d" * 40),
        "tree": (report, "source_tree", "e" * 40),
        "version": (report, "version", "2.1.0"),
        "nested_tree": (report["binding"], "source_tree", "d" * 40),
        "nested_version": (report["binding"], "version", "2.1.0"),
        "aggregate_attempt": (report, "attempt", 2),
        "schema_bool": (report, "schema_version", True),
        "self_certification": (report, "terminal_workflow_success_proved", True),
        "wrong_row": (rows[0], "row_key", "experimental"),
        "row_job": (rows[0], "job_id", 69),
        "row_digest": (rows[0], "sha256", "0" * 64),
        "row_report_digest": (rows[0], "report_sha256", ""),
        "row_runner": (rows[0], "runner_name", "another"),
        "build_digest": (report, "build_artifact_sha256", "1" * 64),
        "failed_run": (meta["run"], "conclusion", "failure"),
        "active_run": (meta["run"], "status", "in_progress"),
        "wrong_workflow": (meta["run"], "workflow_id", 84),
        "fork": (meta["run"], "head_repository", {"id": 999}),
        "stale_attempt": (meta["run"], "run_attempt", 2),
        "wrong_event": (meta["run"], "event", "pull_request"),
        "skipped_aggregate": (jobs[-2], "conclusion", "skipped"),
        "missed_row_job": (jobs[0], "conclusion", "skipped"),
        "truncated_jobs": (meta["jobs"], "total_count", 1000),
        "expired": (artifacts[-1], "expired", True),
    }
    if defect in direct:
        obj, key, value = direct[defect]
        obj[key] = value
    elif defect == "missing_row":
        rows.pop()
    elif defect == "duplicate_row":
        rows[-1] = deepcopy(rows[0])
    elif defect == "missing_aggregate_job":
        jobs.pop(-2)
        meta["jobs"]["total_count"] -= 1
    raw = packed(report, member="unexpected.json" if defect == "zip_layout" else "aggregate.json")
    sha = link_bytes(meta, raw)
    if defect == "no_artifact":
        artifacts.pop()
        meta["artifacts"]["total_count"] -= 1
    elif defect == "duplicate_artifact":
        artifacts.append(deepcopy(artifacts[-1]))
        meta["artifacts"]["total_count"] += 1
    elif defect == "api_digest":
        artifacts[-1]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        verify(
            TAG,
            VERSION,
            COMMIT,
            TREE,
            REPO,
            (
                77,
                1,
                901 if defect == "signed_id" else 900,
                "0" * 64 if defect == "signed_digest" else sha,
            ),
            meta,
            raw + b"x" if defect == "corrupt_bytes" else raw,
        )


def test_signed_selection_and_cross_run_reads_block_every_destination() -> None:
    jobs = yaml.load((ROOT / ".github/workflows/release.yml").read_bytes(), Loader=yaml.BaseLoader)[
        "jobs"
    ]
    steps = jobs["verify"]["steps"]
    names = [step["name"] for step in steps]
    selection = steps[names.index("Read qualification reference from the verified tag")]
    gate = steps[names.index("Require the exact first-stable 16-row aggregate")]
    assert names.index("Verify signed tag and protected-main reachability") < names.index(
        selection["name"]
    )
    assert (
        names.index(selection["name"])
        < names.index(gate["name"])
        < names.index("Frontend quality gate")
    )
    assert "if" not in selection and selection["id"] == "qualification"
    assert gate["if"] == "${{ steps.qualification.outputs.required != 'false' }}"
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in selection["run"]
    assert "continue-on-error" not in gate and gate["timeout-minutes"] == "2"
    assert (
        "git cat-file tag" in selection["run"]
        and "first_stable_release_selection" in selection["run"]
    )
    assert "first_stable_release_gate" in gate["run"] and "HEAD^{tree}" in gate["run"]
    for endpoint in (
        "workflows/package-qualification.yml",
        "runs/$QUAL_RUN",
        "attempts/$QUAL_ATTEMPT/jobs?per_page=100",
        "runs/$QUAL_RUN/artifacts?per_page=100",
        "artifacts/$QUAL_ARTIFACT/zip",
    ):
        assert endpoint in gate["run"]
    for field, output in [
        ("QUAL_RUN", "run_id"),
        ("QUAL_ATTEMPT", "attempt"),
        ("QUAL_ARTIFACT", "artifact_id"),
        ("QUAL_DIGEST", "sha256"),
    ]:
        assert gate["env"][field] == "${{ steps.qualification.outputs." + output + " }}"
    assert jobs["verify"]["permissions"]["actions"] == "read"
    assert jobs["destination-preflight"]["needs"] == "verify"
    assert (
        "verify" in jobs["build-release"]["needs"] and "verify" in jobs["publish-release"]["needs"]
    )


def test_release_commands_interoperate_offline(tmp_path: Path) -> None:
    """Exercise both command boundaries without creating a tag or using the network."""
    report, meta = sample()
    raw = packed(report)
    sha = link_bytes(meta, raw)
    for key, value in meta.items():
        (tmp_path / f"{key}.json").write_text(json.dumps(value), encoding="utf-8")
    (tmp_path / "aggregate.zip").write_bytes(raw)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{VERSION}"\n', encoding="ascii"
    )
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT),
        "GITHUB_REPOSITORY": "MarcoPorcellato/matryca-plumber",
        "GITHUB_REPOSITORY_ID": str(REPO),
        "GITHUB_REF_NAME": TAG,
        "GITHUB_SHA": COMMIT,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "scripts.release_qualification.first_stable_release_selection",
            TAG,
            COMMIT,
        ],
        cwd=tmp_path,
        env=env,
        input=tag_object(f"Qualification-Aggregate: 77/1/900@sha256:{sha}"),
        capture_output=True,
        check=True,
        timeout=10,
    )
    outputs = dict(line.split("=", 1) for line in result.stdout.decode("ascii").splitlines())
    assert outputs == {
        "required": "true",
        "run_id": "77",
        "attempt": "1",
        "artifact_id": "900",
        "sha256": sha,
    }
    env.update(
        QUAL_RUN=outputs["run_id"],
        QUAL_ATTEMPT=outputs["attempt"],
        QUAL_ARTIFACT=outputs["artifact_id"],
        QUAL_DIGEST=outputs["sha256"],
    )
    gate = [
        sys.executable,
        "-B",
        "-m",
        "scripts.release_qualification.first_stable_release_gate",
        str(tmp_path),
        TREE,
    ]
    assert (
        subprocess.run(gate, cwd=tmp_path, env=env, capture_output=True, timeout=10).returncode == 0
    )
    (tmp_path / "aggregate.zip").rename(tmp_path / "saved.zip")
    assert (
        subprocess.run(gate, cwd=tmp_path, env=env, capture_output=True, timeout=10).returncode != 0
    )
