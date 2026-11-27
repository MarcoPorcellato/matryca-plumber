"""Admit a signed first-stable aggregate only after independent terminal GitHub evidence."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import stat
import tomllib
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.release_qualification.alpha1_matrix import canonical, document, read_document
from scripts.release_qualification.bundle import BundleBinding
from scripts.release_qualification.first_stable_aggregate import require_build_upload
from scripts.release_qualification.first_stable_evidence import FirstStableRun
from scripts.release_qualification.first_stable_inventory import (
    WORKFLOW_PATH,
    require_workflow_row_links,
)
from scripts.release_qualification.first_stable_matrix import (
    FIRST_STABLE_ROWS,
    first_stable_release_route,
)
from scripts.release_qualification.first_stable_release_selection import Selection

_SHA = re.compile(r"[0-9a-f]{64}")
_MAX_ARCHIVE = 65_536
_MAX_REPORT = 131_072


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _report(raw: bytes, sha: str) -> dict[str, Any]:
    _require(
        0 < len(raw) <= _MAX_ARCHIVE and hashlib.sha256(raw).hexdigest() == sha,
        "Qualification ZIP bytes do not match the signed SHA-256.",
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        _require(archive.namelist() == ["aggregate.json"], "Unexpected qualification ZIP members.")
        info = archive.infolist()[0]
        _require(
            info.orig_filename == "aggregate.json"
            and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG)
            and not info.flag_bits & 1
            and info.compress_type in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED)
            and 0 < info.file_size <= _MAX_REPORT,
            "Invalid or oversized qualification report.",
        )
        with archive.open(info) as member:
            return document(member.read(_MAX_REPORT + 1))


def _terminal_jobs(jobs: dict[str, Any], expected: FirstStableRun) -> None:
    outcomes = {
        "Admit first-stable selection": "success",
        "Build original first-stable artifacts": "success",
        "Verify first-stable exact-attempt receipts": "success",
        "Native Linux runtime startup (diagnostic)": "skipped",
        **{f"Install first-stable ({row.key})": "success" for row in FIRST_STABLE_ROWS},
    }
    items = jobs["jobs"]
    _require(
        len(items) == len(outcomes) and {j["name"] for j in items} == set(outcomes),
        "Incomplete, duplicate or unexpected qualification jobs.",
    )
    _require(
        all(
            j.get("status") == "completed"
            and j.get("conclusion") == outcomes[j["name"]]
            and j.get("head_sha") == expected.source_commit
            and type(j.get("run_id")) is int
            and j["run_id"] == expected.run_id
            and type(j.get("run_attempt")) is int
            and j["run_attempt"] == expected.attempt
            for j in items
        ),
        "Qualification job is not terminal on the selected attempt.",
    )


def verify(
    tag: str,
    version: str,
    commit: str,
    tree: str,
    repository_id: int,
    selection: Selection,
    metadata: dict[str, Any],
    raw: bytes,
) -> None:
    """Compare signed ZIP bytes and all sixteen links with the exact run's REST records."""
    first_stable_release_route(tag, version)
    run_id, attempt, artifact_id, sha = selection
    expected = FirstStableRun(
        repository_id=repository_id, run_id=run_id, attempt=attempt, source_commit=commit
    )
    workflow, run, jobs, artifacts = (metadata[k] for k in ("workflow", "run", "jobs", "artifacts"))
    _require(
        workflow.get("path") == WORKFLOW_PATH
        and workflow.get("state") == "active"
        and run.get("status") == "completed"
        and run.get("conclusion") == "success",
        "Qualification workflow is not the active workflow with a terminal successful run.",
    )
    aggregate_name = f"first-stable-aggregate-{run_id}-{attempt}"
    matches = [a for a in artifacts["artifacts"] if a.get("name") == aggregate_name]
    _require(len(matches) == 1, "Missing or duplicate selected aggregate artifact.")
    artifact = matches[0]
    origin = artifact.get("workflow_run")
    _require(
        type(artifact.get("id")) is int
        and artifact["id"] == artifact_id
        and artifact.get("expired") is False
        and type(artifact.get("size_in_bytes")) is int
        and artifact["size_in_bytes"] == len(raw)
        and artifact.get("digest") == f"sha256:{sha}"
        and isinstance(origin, dict)
        and origin.get("head_sha") == commit
        and origin.get("head_branch") == "main"
        and all(
            type(origin.get(k)) is int and origin[k] == v
            for k, v in (
                ("id", run_id),
                ("repository_id", repository_id),
                ("head_repository_id", repository_id),
            )
        ),
        "Aggregate artifact identity, digest, size, or freshness mismatch.",
    )
    report = _report(raw, sha)
    identity = {
        "schema_version": 1,
        "repository_id": repository_id,
        "run_id": run_id,
        "attempt": attempt,
        "source_commit": commit,
        "source_tree": tree,
        "version": version,
        "terminal_workflow_success_proved": False,
    }
    _require(
        set(report) == {*identity, "binding", "rows", "build_artifact_id", "build_artifact_sha256"}
        and all(canonical(report[k]) == canonical(v) for k, v in identity.items()),
        "Aggregate does not bind this source commit, tree, version, and attempt.",
    )
    binding = BundleBinding.from_json(
        canonical(report["binding"]).decode("ascii"), policy="og-alpha3"
    )
    _require(
        (binding.source_commit, binding.source_tree, binding.version) == (commit, tree, version),
        "Original distribution binding does not match the release candidate.",
    )
    build_id, build_sha = report["build_artifact_id"], report["build_artifact_sha256"]
    _require(
        type(build_id) is int
        and build_id > 0
        and isinstance(build_sha, str)
        and _SHA.fullmatch(build_sha) is not None,
        "Invalid qualification build reference.",
    )
    require_build_upload(
        expected, {"artifact-id": str(build_id), "artifact-sha256": build_sha}, jobs, artifacts
    )
    rows = report["rows"]
    _require(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
        "Invalid qualification receipt list.",
    )
    uploads = [{k: row[k] for k in ("row_key", "artifact_id", "sha256")} for row in rows]
    links = require_workflow_row_links(
        expected,
        expected_workflow_id=workflow["id"],
        workflow_run=run,
        uploads=uploads,
        jobs=jobs,
        artifacts=artifacts,
    )
    _terminal_jobs(jobs, expected)
    by_key = {row["row_key"]: row for row in rows}
    for link in links:
        actual = dict(by_key[link.row_key])
        report_sha = actual.pop("report_sha256", None)
        _require(
            isinstance(report_sha, str)
            and _SHA.fullmatch(report_sha) is not None
            and canonical(actual) == canonical(asdict(link)),
            "Aggregate row receipt differs from its independently observed job or artifact.",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("tree")
    args = parser.parse_args()
    _require(
        os.environ["GITHUB_REPOSITORY"] == "MarcoPorcellato/matryca-plumber"
        and os.environ["GITHUB_REPOSITORY_ID"] == "1241185104",
        "Unexpected release repository.",
    )
    with Path("pyproject.toml").open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    metadata = {
        key: read_document(args.root / f"{key}.json")
        for key in ("workflow", "run", "jobs", "artifacts")
    }
    with (args.root / "aggregate.zip").open("rb") as archive:
        raw = archive.read(_MAX_ARCHIVE + 1)
    selection = (
        int(os.environ["QUAL_RUN"]),
        int(os.environ["QUAL_ATTEMPT"]),
        int(os.environ["QUAL_ARTIFACT"]),
        os.environ["QUAL_DIGEST"],
    )
    verify(
        os.environ["GITHUB_REF_NAME"],
        version,
        os.environ["GITHUB_SHA"],
        args.tree,
        int(os.environ["GITHUB_REPOSITORY_ID"]),
        selection,
        metadata,
        raw,
    )
    print(
        f"Verified all 16 installed-package receipts for {version} at {os.environ['GITHUB_SHA']} "
        f"(qualification {selection[0]}/{selection[1]})."
    )


if __name__ == "__main__":
    main()
