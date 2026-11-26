"""Verify exact-attempt ordinary row reports against independent job outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.release_qualification import bundle, sdist_build
from scripts.release_qualification.alpha1_matrix import (
    MatrixContext,
    _verify_build,
    canonical,
    digest,
    read_document,
)
from scripts.release_qualification.first_stable_evidence import FirstStableRun
from scripts.release_qualification.first_stable_host import PINS
from scripts.release_qualification.first_stable_inventory import require_workflow_row_links
from scripts.release_qualification.first_stable_job import ROWS, _selection, read_export
from scripts.release_qualification.first_stable_profiles import resolve_profile

_HASH = re.compile(r"[0-9a-f]{64}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_build_upload(
    expected: FirstStableRun,
    outputs: dict[str, Any],
    jobs: dict[str, Any],
    artifacts: dict[str, Any],
) -> None:
    """Connect the independent original-pair upload to a successful exact job."""
    expected_name = f"first-stable-inputs-{expected.run_id}-{expected.attempt}"
    builds = [job for job in jobs["jobs"] if job["name"] == "Build original first-stable artifacts"]
    matches = [item for item in artifacts["artifacts"] if item["name"] == expected_name]
    _require(
        len(builds) == len(matches) == 1,
        "Missing or extra independent canonical build evidence.",
    )
    build = builds[0]
    match = matches[0]
    sha256 = outputs["artifact-sha256"].removeprefix("sha256:")
    run = match.get("workflow_run")
    _require(
        build.get("status") == "completed"
        and build.get("conclusion") == "success"
        and build.get("head_sha") == expected.source_commit
        and build.get("run_id") == expected.run_id
        and build.get("run_attempt") == expected.attempt
        and _HASH.fullmatch(sha256) is not None
        and str(match.get("id")) == outputs["artifact-id"]
        and match.get("digest") == f"sha256:{sha256}"
        and match.get("expired") is False
        and isinstance(run, dict)
        and run.get("id") == expected.run_id
        and run.get("repository_id") == expected.repository_id
        and run.get("head_repository_id") == expected.repository_id
        and run.get("head_sha") == expected.source_commit,
        "Canonical build upload is not bound to the selected source and attempt.",
    )


def require_row_document(
    value: dict[str, Any],
    *,
    expected: FirstStableRun,
    row_key: str,
    binding: bundle.BundleBinding,
    candidate_tag: str,
    export: str,
    source: Path,
) -> None:
    """Recheck the report's identity, exact closure and build observations."""
    row = ROWS[row_key]
    profile = resolve_profile(export, row.profile, row.platform, row.python)
    wanted = {
        "schema_version": 1,
        "run_id": expected.run_id,
        "attempt": expected.attempt,
        "binding_sha256": digest(asdict(binding)),
        "locked_export_sha256": hashlib.sha256(export.encode("ascii")).hexdigest(),
        "profile_sha256": hashlib.sha256(profile.requirements.encode("ascii")).hexdigest(),
    }
    _require(
        set(value) == {*wanted, "installed", "runtime", "build"}
        and all(type(value[k]) is type(v) and value[k] == v for k, v in wanted.items()),
        "Row document is not bound to the exact attempt and inputs.",
    )
    runtime = value["runtime"]
    runtime_expected = {
        "implementation": "CPython",
        "platform": row.platform,
        "version": row.python,
        "cleanup": "verified",
        "archive_sha256": PINS[row.platform, row.python].sha256,
    }
    _require(
        isinstance(runtime, dict)
        and set(runtime) == {*runtime_expected, "executable_sha256"}
        and all(runtime[k] == v for k, v in runtime_expected.items())
        and isinstance(runtime["executable_sha256"], str)
        and _HASH.fullmatch(runtime["executable_sha256"]) is not None,
        "Native runtime evidence differs from the expected row.",
    )
    if row.distribution == "wheel":
        name, size, sha = binding.wheel_name, binding.wheel_size, binding.wheel_sha256
        _require(value["build"] is None, "Wheel row contains an unexpected sdist build.")
    else:
        name, size, sha = binding.sdist_name, binding.sdist_size, binding.sdist_sha256
        build = value["build"]
        _require(
            isinstance(build, dict) and set(build) == {"receipt", "descriptor", "provisioning"},
            "Sdist row lacks independent build evidence.",
        )
        lock_sha, recipe_sha = sdist_build._locked_build_identity(source)
        lock = tomllib.loads(
            (source / "release-qualification-build/uv.lock").read_text(encoding="utf-8")
        )
        packages = tuple(
            sorted((p["name"], p["version"]) for p in lock["package"] if "registry" in p["source"])
        )
        context = MatrixContext(
            binding,
            str(expected.run_id),
            expected.attempt,
            {},
            {},
            lock_sha,
            recipe_sha,
            packages,
            (),
        )
        receipt = build["receipt"]
        _require(
            isinstance(receipt, dict) and receipt.get("python_version") == "3.12.16",
            "Sdist build did not use independent CPython 3.12.16.",
        )
        target = ("linux", "x64") if row.platform == "linux-x86_64" else ("macos", "arm64")
        _verify_build(
            context,
            {
                **receipt,
                "instance": row_key,
                "environment_descriptor": build["descriptor"],
                "provisioning_evidence": build["provisioning"],
            },
            row_key,
            *target,
        )
    wrapper = value["installed"]
    wrapper_expected = {
        "schema_version": 1,
        "row_key": row_key,
        "candidate_tag": candidate_tag,
        "source_commit": binding.source_commit,
        "source_tree": binding.source_tree,
        "original_artifact": {"name": name, "size": size, "sha256": sha},
    }
    _require(
        isinstance(wrapper, dict)
        and set(wrapper) == {*wrapper_expected, "installed"}
        and all(canonical(wrapper[k]) == canonical(v) for k, v in wrapper_expected.items()),
        "Installed report does not match the original archive and source.",
    )
    installed = wrapper["installed"]
    host = ("linux", "x86_64") if row.platform == "linux-x86_64" else ("darwin", "arm64")
    installed_expected = {
        "schema_version": 2,
        "kind": row.distribution,
        "version": binding.version,
        "python_version": row.python,
        "operating_system": host[0],
        "architecture": host[1],
        "location_class": "isolated-venv-site-packages",
        "windows_launcher": None,
        "tck_outcomes": ["PASS", "PASS", "PASS"],
        "dependencies": [{"name": n, "version": v} for n, v in profile.packages],
        "dependency_sha256": hashlib.sha256(
            json.dumps(profile.packages, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    _require(
        isinstance(installed, dict)
        and set(installed)
        == {*installed_expected, "record_sha256", "resource_sha256", "build_generator"}
        and all(canonical(installed[k]) == canonical(v) for k, v in installed_expected.items())
        and all(
            isinstance(installed[k], str) and _HASH.fullmatch(installed[k]) is not None
            for k in ("record_sha256", "resource_sha256")
        )
        and installed["build_generator"] == {"name": "setuptools", "version": "84.1.0"},
        "Installed receipt does not meet ordinary verifier expectations.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root
    binding = _selection()
    expected = FirstStableRun(
        repository_id=int(os.environ["GITHUB_REPOSITORY_ID"]),
        run_id=int(os.environ["GITHUB_RUN_ID"]),
        attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
        source_commit=binding.source_commit,
    )
    needs = json.loads(os.environ["NEEDS_JSON"])
    _require(
        isinstance(needs, dict)
        and set(needs) >= {"admit", "build"}
        and len(needs) == len(ROWS) + 2
        and all(job["result"] == "success" for job in needs.values()),
        "Missing, skipped or failed dependency jobs.",
    )
    rows = [
        {
            "row_key": job["outputs"]["row-key"],
            "artifact_id": int(job["outputs"]["artifact-id"]),
            "sha256": job["outputs"]["artifact-sha256"].removeprefix("sha256:"),
        }
        for key, job in needs.items()
        if key not in {"admit", "build"}
    ]
    workflow_metadata = read_document(root / "workflow.json")
    _require(
        workflow_metadata.get("path") == ".github/workflows/package-qualification.yml",
        "Unexpected independent workflow metadata.",
    )
    jobs, artifacts = read_document(root / "jobs.json"), read_document(root / "artifacts.json")
    links = require_workflow_row_links(
        expected,
        expected_workflow_id=workflow_metadata["id"],
        workflow_run=read_document(root / "run.json"),
        uploads=rows,
        jobs=jobs,
        artifacts=artifacts,
    )
    require_build_upload(expected, needs["build"]["outputs"], jobs, artifacts)
    inputs = root / "inputs"
    bundle.verify_handoff(
        inputs / "dist",
        inputs / "dist/SHA256SUMS",
        binding,
        policy="og-alpha3",
    )
    export = read_export(inputs / "runtime-lock.txt", os.environ["EXPECTED_EXPORT_SHA256"])
    receipt_rows = []
    for link in links:
        name = f"first-stable-row-{expected.run_id}-{expected.attempt}-{link.row_key}"
        artifact = root / "rows" / name
        _require(
            artifact.is_dir()
            and not artifact.is_symlink()
            and {file.name for file in artifact.iterdir()} == {"row.json"},
            "Unexpected row artifact payload set.",
        )
        report = read_document(artifact / "row.json")
        require_row_document(
            report,
            expected=expected,
            row_key=link.row_key,
            binding=binding,
            candidate_tag=os.environ["CANDIDATE_TAG"],
            export=export,
            source=Path.cwd(),
        )
        receipt_rows.append({**asdict(link), "report_sha256": digest(report)})
    with (root / "aggregate.json").open("xb") as output:
        output.write(
            canonical(
                {
                    "schema_version": 1,
                    "repository_id": expected.repository_id,
                    "run_id": expected.run_id,
                    "attempt": expected.attempt,
                    "source_commit": binding.source_commit,
                    "source_tree": binding.source_tree,
                    "version": binding.version,
                    "binding": asdict(binding),
                    "build_artifact_id": int(needs["build"]["outputs"]["artifact-id"]),
                    "build_artifact_sha256": needs["build"]["outputs"][
                        "artifact-sha256"
                    ].removeprefix("sha256:"),
                    "rows": receipt_rows,
                    "terminal_workflow_success_proved": False,
                }
            )
        )


if __name__ == "__main__":
    main()
