"""Select complete, exact-attempt REST evidence for the ordinary qualification lane."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scripts.release_qualification.first_stable_evidence import (
    FirstStableRun,
    LinkedRow,
    require_row_links,
)

WORKFLOW_PATH = ".github/workflows/package-qualification.yml"
_JOB_PREFIX = "Install first-stable ("
_LIMIT = 100


@dataclass(frozen=True, slots=True)
class RowInventory:
    """Selected row records; not proof that every expected row succeeded."""

    jobs: tuple[Mapping[str, object], ...]
    artifacts: tuple[Mapping[str, object], ...]


def _matches_id(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def _matches_repository(value: object, repository_id: int) -> bool:
    return isinstance(value, Mapping) and _matches_id(value.get("id"), repository_id)


def _named_records(
    payload: Mapping[str, object], key: str
) -> tuple[tuple[str, Mapping[str, object]], ...]:
    count = payload.get("total_count")
    records = payload.get(key)
    if (
        type(count) is not int
        or not 0 <= count <= _LIMIT
        or not isinstance(records, list)
        or len(records) != count
    ):
        raise ValueError("First-stable REST inventory is malformed, incomplete, or too large.")
    named: list[tuple[str, Mapping[str, object]]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("Invalid record in first-stable REST inventory.")
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Missing name in first-stable REST inventory.")
        named.append((name, record))
    return tuple(named)


def select_row_inventory(
    expected: FirstStableRun,
    *,
    expected_workflow_id: int,
    workflow_run: Mapping[str, object],
    jobs: Mapping[str, object],
    artifacts: Mapping[str, object],
) -> RowInventory:
    """Check the authenticated run and pass complete relevant records onward.

    Fetch the run and jobs from the attempt-specific API and artifacts from the
    exact run. The caller obtains the workflow ID independently using its path.
    This function does not fetch/authenticate HTTP responses. It can run during
    an aggregate job; terminal run success is a separate release-side check.
    """
    if (
        type(expected_workflow_id) is not int
        or expected_workflow_id <= 0
        or not _matches_id(workflow_run.get("workflow_id"), expected_workflow_id)
        or workflow_run.get("path") != WORKFLOW_PATH
        or workflow_run.get("event") != "workflow_dispatch"
        or workflow_run.get("head_branch") != "main"
        or not _matches_id(workflow_run.get("id"), expected.run_id)
        or not _matches_id(workflow_run.get("run_attempt"), expected.attempt)
        or workflow_run.get("head_sha") != expected.source_commit
        or not _matches_repository(workflow_run.get("repository"), expected.repository_id)
        or not _matches_repository(workflow_run.get("head_repository"), expected.repository_id)
    ):
        raise ValueError("First-stable workflow run identity differs from expectations.")
    prefix = f"first-stable-row-{expected.run_id}-{expected.attempt}-"
    return RowInventory(
        tuple(
            record for name, record in _named_records(jobs, "jobs") if name.startswith(_JOB_PREFIX)
        ),
        tuple(
            record
            for name, record in _named_records(artifacts, "artifacts")
            if name.startswith(prefix)
        ),
    )


def require_workflow_row_links(
    expected: FirstStableRun,
    *,
    expected_workflow_id: int,
    workflow_run: Mapping[str, object],
    uploads: Sequence[Mapping[str, object]],
    jobs: Mapping[str, object],
    artifacts: Mapping[str, object],
) -> tuple[LinkedRow, ...]:
    """Join the independently captured uploads to the complete REST inventory."""
    inventory = select_row_inventory(
        expected,
        expected_workflow_id=expected_workflow_id,
        workflow_run=workflow_run,
        jobs=jobs,
        artifacts=artifacts,
    )
    return require_row_links(expected, uploads, inventory.jobs, inventory.artifacts)
