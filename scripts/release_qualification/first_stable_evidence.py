"""Join ordinary first-stable upload outputs to GitHub job and artifact metadata."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from scripts.release_qualification.first_stable_matrix import (
    FIRST_STABLE_ROWS,
    require_exact_row_keys,
)

_PositiveInt = Annotated[int, Field(gt=0)]
_Sha256 = Annotated[str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]+$")]
_Commit = Annotated[str, Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]+$")]


class FirstStableRun(BaseModel):
    """Expectation derived from the selected repository and exact source run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    repository_id: _PositiveInt
    run_id: _PositiveInt
    attempt: _PositiveInt
    source_commit: _Commit


class _RowUpload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    row_key: str
    artifact_id: _PositiveInt
    sha256: _Sha256


@dataclass(frozen=True, slots=True)
class LinkedRow:
    """Metadata to bind a later byte download and installed-result check."""

    row_key: str
    job_id: int
    runner_id: int
    runner_name: str
    artifact_id: int
    archive_size: int
    sha256: str


def _name_index(
    records: Sequence[Mapping[str, object]], expected_names: set[str]
) -> dict[str, Mapping[str, object]]:
    if len(records) != len(expected_names):
        raise ValueError("Missing or extra first-stable job or artifact records.")
    by_name: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("Invalid first-stable job or artifact record.")
        name = record.get("name")
        if not isinstance(name, str) or name not in expected_names or name in by_name:
            raise ValueError("Unexpected or duplicate job or artifact name.")
        by_name[name] = record
    return by_name


def _positive_int(value: object) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Invalid first-stable identifier or byte count.")
    return value


def require_row_links(
    expected: FirstStableRun,
    uploads: Sequence[Mapping[str, object]],
    jobs: Sequence[Mapping[str, object]],
    artifacts: Sequence[Mapping[str, object]],
) -> tuple[LinkedRow, ...]:
    """Link all 16 rows; inputs must come from distinct trusted channels.

    The caller must authenticate the run/workflow, collect complete REST
    listings and pass all row jobs and row artifacts for the expected attempt.
    Upload IDs and hashes come from workflow outputs, never worker reports or
    the REST artifact list itself. Linking does not authenticate archive bytes,
    installed receipts, host/runtime identity, or a qualification result.
    """
    if len(uploads) != len(FIRST_STABLE_ROWS):
        raise ValueError("Missing or extra first-stable upload outputs.")
    parsed = [_RowUpload.model_validate(record) for record in uploads]
    require_exact_row_keys(record.row_key for record in parsed)
    upload_by_row = {record.row_key: record for record in parsed}
    job_names = {row.key: f"Install first-stable ({row.key})" for row in FIRST_STABLE_ROWS}
    archive_prefix = f"first-stable-row-{expected.run_id}-{expected.attempt}-"
    archive_names = {row.key: archive_prefix + row.key for row in FIRST_STABLE_ROWS}
    job_by_name = _name_index(jobs, set(job_names.values()))
    artifact_by_name = _name_index(artifacts, set(archive_names.values()))
    seen_job_ids: set[int] = set()
    seen_artifact_ids: set[int] = set()
    links: list[LinkedRow] = []
    for row in FIRST_STABLE_ROWS:
        upload = upload_by_row[row.key]
        job = job_by_name[job_names[row.key]]
        artifact = artifact_by_name[archive_names[row.key]]
        runner_name = job.get("runner_name")
        if (
            job.get("status") != "completed"
            or job.get("conclusion") != "success"
            or _positive_int(job.get("run_id")) != expected.run_id
            or _positive_int(job.get("run_attempt")) != expected.attempt
            or job.get("head_sha") != expected.source_commit
            or not isinstance(runner_name, str)
            or not runner_name.strip()
        ):
            raise ValueError("First-stable job lacks successful exact-attempt evidence.")
        run = artifact.get("workflow_run")
        artifact_id = _positive_int(artifact.get("id"))
        if (
            artifact_id != upload.artifact_id
            or artifact.get("digest") != f"sha256:{upload.sha256}"
            or artifact.get("expired") is not False
            or not isinstance(run, Mapping)
            or _positive_int(run.get("id")) != expected.run_id
            or _positive_int(run.get("repository_id")) != expected.repository_id
            or _positive_int(run.get("head_repository_id")) != expected.repository_id
            or run.get("head_sha") != expected.source_commit
        ):
            raise ValueError("First-stable artifact does not match the run and upload outputs.")
        job_id = _positive_int(job.get("id"))
        if job_id in seen_job_ids or artifact_id in seen_artifact_ids:
            raise ValueError("A first-stable job or artifact ID was reused.")
        seen_job_ids.add(job_id)
        seen_artifact_ids.add(artifact_id)
        links.append(
            LinkedRow(
                row.key,
                job_id,
                _positive_int(job.get("runner_id")),
                runner_name,
                artifact_id,
                _positive_int(artifact.get("size_in_bytes")),
                upload.sha256,
            )
        )
    return tuple(links)
