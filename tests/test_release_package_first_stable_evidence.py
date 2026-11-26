"""Synthetic tests for exact-attempt GitHub row links, not worker receipts."""

from __future__ import annotations

from typing import Any

import pytest
from scripts.release_qualification.first_stable_evidence import (
    FirstStableRun,
    LinkedRow,
    require_row_links,
)
from scripts.release_qualification.first_stable_matrix import FIRST_STABLE_ROWS

_COMMIT = "a" * 40


def _inputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    uploads: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    for number, row in enumerate(FIRST_STABLE_ROWS, 1):
        sha256 = f"{number:064x}"
        uploads.append({"row_key": row.key, "artifact_id": 100 + number, "sha256": sha256})
        jobs.append(
            {
                "name": f"Install first-stable ({row.key})",
                "id": 200 + number,
                "run_id": 15,
                "run_attempt": 2,
                "head_sha": _COMMIT,
                "status": "completed",
                "conclusion": "success",
                "runner_id": 300 + number,
                "runner_name": f"runner-{number}",
            }
        )
        artifacts.append(
            {
                "name": f"first-stable-row-15-2-{row.key}",
                "id": 100 + number,
                "size_in_bytes": 123,
                "expired": False,
                "digest": f"sha256:{sha256}",
                "workflow_run": {
                    "id": 15,
                    "head_sha": _COMMIT,
                    "repository_id": 99,
                    "head_repository_id": 99,
                },
            }
        )
    return uploads, jobs, artifacts


def _require_links(
    uploads: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> tuple[LinkedRow, ...]:
    return require_row_links(
        FirstStableRun(repository_id=99, run_id=15, attempt=2, source_commit=_COMMIT),
        uploads,
        jobs,
        artifacts,
    )


def test_links_successful_jobs_and_matching_artifacts_by_identity_not_list_position() -> None:
    uploads, jobs, artifacts = _inputs()
    links = _require_links(uploads[::-1], jobs, artifacts[::-1])
    assert len(links) == 16
    assert links[0].row_key == "minimum-linux-x86_64-cpython-3.12.16-wheel"
    assert (links[0].artifact_id, links[0].job_id, links[0].runner_id) == (101, 201, 301)
    assert links[0].archive_size == 123
    assert links[0].sha256 == f"{1:064x}"


@pytest.mark.parametrize(
    ("index", "field", "value"),
    [
        (0, "artifact_id", True),
        (0, "artifact_id", 102),
        (0, "sha256", "b" * 64),
        (0, "status", "pass"),
        (1, "id", 202),
        (1, "run_attempt", 1),
        (1, "head_sha", "b" * 40),
        (1, "status", "in_progress"),
        (1, "conclusion", "skipped"),
        (1, "runner_id", True),
        (1, "runner_name", " "),
        (2, "id", 102),
        (2, "name", "first-stable-row-15-1-minimum-linux-x86_64-cpython-3.12.16-wheel"),
        (2, "expired", True),
        (2, "expired", 0),
        (2, "size_in_bytes", 0),
        (2, "digest", "sha256:" + "b" * 64),
    ],
)
def test_rejects_unbound_or_nonterminal_links(index: int, field: str, value: object) -> None:
    inputs = _inputs()
    inputs[index][0][field] = value
    with pytest.raises(ValueError):
        _require_links(*inputs)


@pytest.mark.parametrize("field", ["id", "repository_id", "head_repository_id", "head_sha"])
def test_rejects_artifact_from_another_run_or_repository(field: str) -> None:
    uploads, jobs, artifacts = _inputs()
    artifacts[0]["workflow_run"][field] = "b" * 40 if field == "head_sha" else 7
    with pytest.raises(ValueError):
        _require_links(uploads, jobs, artifacts)


@pytest.mark.parametrize("index", [0, 1, 2])
@pytest.mark.parametrize("duplicate", [False, True])
def test_rejects_missing_and_extra_records(index: int, duplicate: bool) -> None:
    inputs = _inputs()
    if duplicate:
        inputs[index].append(inputs[index][0])
    else:
        inputs[index].pop()
    with pytest.raises(ValueError):
        _require_links(*inputs)
