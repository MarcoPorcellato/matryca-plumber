"""Synthetic inputs for workflow-run admission and complete inventory selection."""

from __future__ import annotations

from typing import Any

import pytest
from scripts.release_qualification.first_stable_evidence import FirstStableRun
from scripts.release_qualification.first_stable_inventory import (
    RowInventory,
    require_workflow_row_links,
    select_row_inventory,
)

_COMMIT = "a" * 40
_PATH = ".github/workflows/package-qualification.yml"


def _run() -> dict[str, Any]:
    return {
        "id": 77,
        "run_attempt": 2,
        "head_sha": _COMMIT,
        "workflow_id": 124,
        "path": _PATH,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "repository": {"id": 99},
        "head_repository": {"id": 99},
    }


def _select(run: dict[str, Any], jobs: dict[str, Any], artifacts: dict[str, Any]) -> RowInventory:
    return select_row_inventory(
        FirstStableRun(repository_id=99, run_id=77, attempt=2, source_commit=_COMMIT),
        expected_workflow_id=124,
        workflow_run=run,
        jobs=jobs,
        artifacts=artifacts,
    )


def test_selects_only_current_attempt_rows_from_complete_listings() -> None:
    job = {"name": "Install first-stable (minimum-linux-x86_64-cpython-3.12.16-wheel)"}
    artifact = {"name": "first-stable-row-77-2-minimum-linux-x86_64-cpython-3.12.16-wheel"}
    rows = _select(
        _run(),
        {"total_count": 2, "jobs": [job, {"name": "Build first-stable originals"}]},
        {
            "total_count": 3,
            "artifacts": [
                {"name": "canonical-package-bundle"},
                {"name": "first-stable-row-77-1-minimum-linux-x86_64-cpython-3.12.16-wheel"},
                artifact,
            ],
        },
    )
    assert rows.jobs == (job,)
    assert rows.artifacts == (artifact,)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("head_sha", "b" * 40),
        ("run_attempt", 1),
        ("workflow_id", True),
        ("path", ".github/workflows/og-profile-qualification.yml"),
        ("event", "pull_request"),
        ("head_branch", "candidate"),
        ("repository", {"id": 4}),
        ("head_repository", None),
    ],
)
def test_rejects_non_authoritative_run(field: str, value: object) -> None:
    run = _run()
    run[field] = value
    with pytest.raises(ValueError):
        _select(run, {"total_count": 0, "jobs": []}, {"total_count": 0, "artifacts": []})


@pytest.mark.parametrize(("kind", "key"), [(0, "jobs"), (1, "artifacts")])
@pytest.mark.parametrize(
    ("count", "entries"), [(2, [{"name": "partial"}]), (True, [{}]), (1, [None]), (1, "row")]
)
def test_rejects_truncated_or_malformed_listing(
    kind: int, key: str, count: object, entries: object
) -> None:
    listings = [{"total_count": 0, "jobs": []}, {"total_count": 0, "artifacts": []}]
    listings[kind] = {"total_count": count, key: entries}
    with pytest.raises(ValueError):
        _select(_run(), *listings)


def test_complete_empty_listings_do_not_satisfy_qualification_row_linking() -> None:
    with pytest.raises(ValueError, match="Missing or extra first-stable upload outputs"):
        require_workflow_row_links(
            FirstStableRun(repository_id=99, run_id=77, attempt=2, source_commit=_COMMIT),
            expected_workflow_id=124,
            workflow_run=_run(),
            uploads=[],
            jobs={"total_count": 0, "jobs": []},
            artifacts={"total_count": 0, "artifacts": []},
        )
