from __future__ import annotations

import os
from dataclasses import replace
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import pytest
from src.memory.evidence_archive import EvidenceArchive, EvidenceArchiveError
from src.memory.evidence_location import (
    EvidenceArchiveLocationError,
    resolve_evidence_archive_location,
)
from src.memory.evidence_models import EvidenceEvent, EvidenceRef, MemoryCandidate
from src.shadow.cache_location import resolve_shadow_cache_location

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64


def _graph(tmp_path: Path) -> Path:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    return graph


def _event() -> EvidenceEvent:
    return EvidenceEvent(
        candidate=MemoryCandidate(
            candidate_id=_DIGEST_A,
            candidate_kind="semantic-claim",
            observed_at="2026-08-10T12:00:00Z",
            evidence_refs=(EvidenceRef("benchmark", _DIGEST_B, _DIGEST_C),),
        ),
        recorded_at="2026-08-10T12:01:00Z",
    )


def _append_from_process(graph: str, cache: str, queue: Any) -> None:
    archive = EvidenceArchive.for_graph(graph, env={"MATRYCA_CACHE_PATH": cache})
    result = archive.append(_event())
    queue.put(result.appended)


def test_archive_is_external_private_and_idempotent_in_read_only_mode(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    cache = tmp_path / "external-cache"
    archive = EvidenceArchive.for_graph(
        graph,
        env={"MATRYCA_READ_ONLY": "true", "MATRYCA_CACHE_PATH": str(cache)},
    )

    first = archive.append(_event())
    second = archive.append(_event())

    assert first.appended is True
    assert second == type(second)(event_id=first.event_id, appended=False)
    assert archive.location.events_path.is_relative_to(cache)
    assert not archive.location.events_path.is_relative_to(graph)
    assert archive.events() == (_event(),)
    if os.name == "posix":
        assert archive.location.events_path.stat().st_mode & 0o777 == 0o600
        assert archive.location.archive_dir.stat().st_mode & 0o777 == 0o700


def test_archive_uses_the_same_private_graph_bucket_without_shadow_runtime(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    env = {"MATRYCA_CACHE_PATH": str(tmp_path / "cache")}

    archive_location = resolve_evidence_archive_location(graph, env=env)
    shadow_location = resolve_shadow_cache_location(graph, env=env)

    assert archive_location.graph_id == shadow_location.graph_id
    assert archive_location.archive_dir == shadow_location.shadow_dir.parent / "evidence"


def test_archive_recovers_only_a_torn_final_record(tmp_path: Path) -> None:
    archive = EvidenceArchive.for_graph(
        _graph(tmp_path), env={"MATRYCA_CACHE_PATH": str(tmp_path / "cache")}
    )
    archive.append(_event())
    with archive.location.events_path.open("ab") as handle:
        handle.write(b'{"candidate":')

    assert archive.events() == (_event(),)
    assert archive.append(_event()).appended is False
    assert archive.location.events_path.read_bytes().endswith(b"\n")

    archive.location.events_path.write_bytes(b"not-json\n")
    with pytest.raises(EvidenceArchiveError, match="archive_record_invalid"):
        archive.events()


def test_archive_rejects_unrecoverable_final_corruption_and_oversized_replay(
    tmp_path: Path,
) -> None:
    archive = EvidenceArchive.for_graph(
        _graph(tmp_path), env={"MATRYCA_CACHE_PATH": str(tmp_path / "cache")}
    )
    archive.append(_event())
    with archive.location.events_path.open("ab") as handle:
        handle.write(b"not-a-json-object")

    with pytest.raises(EvidenceArchiveError, match="archive_torn_record_unrecoverable"):
        archive.append(_event())

    archive.location.events_path.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
    with pytest.raises(EvidenceArchiveError, match="archive_size_limit_exceeded"):
        archive.events()


def test_archive_fails_closed_for_graph_local_and_symlink_targets(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    with pytest.raises(EvidenceArchiveLocationError, match="cache_path_inside_graph"):
        resolve_evidence_archive_location(graph, env={"MATRYCA_CACHE_PATH": str(graph / "cache")})

    cache = tmp_path / "cache"
    location = resolve_evidence_archive_location(graph, env={"MATRYCA_CACHE_PATH": str(cache)})
    location.ensure_directory()
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")
    try:
        location.events_path.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(EvidenceArchiveLocationError, match="events_path_symlink"):
        EvidenceArchive(location)


def test_archive_rejects_hand_assembled_location(tmp_path: Path) -> None:
    location = resolve_evidence_archive_location(
        _graph(tmp_path), env={"MATRYCA_CACHE_PATH": str(tmp_path / "cache")}
    )

    with pytest.raises(EvidenceArchiveLocationError, match="archive_location_mismatch"):
        EvidenceArchive(replace(location, events_path=tmp_path / "outside.jsonl"))


def test_archive_serializes_duplicate_appends_across_processes(tmp_path: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX flock contract")
    graph = _graph(tmp_path)
    cache = tmp_path / "cache"
    context = get_context("fork")
    queue = context.Queue()
    processes = [
        context.Process(target=_append_from_process, args=(str(graph), str(cache), queue))
        for _ in range(3)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    appended = [queue.get(timeout=2) for _ in processes]
    archive = EvidenceArchive.for_graph(graph, env={"MATRYCA_CACHE_PATH": str(cache)})
    assert appended.count(True) == 1
    assert archive.events() == (_event(),)
