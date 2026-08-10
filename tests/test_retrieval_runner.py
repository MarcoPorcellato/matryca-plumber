"""Focused tests for the local-only retrieval execution bridge."""

from __future__ import annotations

import hashlib
import socket
from pathlib import Path

import pytest
from src.memory.benchmark_protocol import (
    BENCHMARK_PROTOCOL_SCHEMA_VERSION,
    BenchmarkRunManifest,
    DatasetPin,
    EvaluationBudget,
    RuntimePin,
    SystemPin,
)
from src.memory.evidence_models import EvidenceContractError
from src.memory.retrieval_runner import (
    NoMemoryRetriever,
    RetrievalInputEvidence,
    RetrievalItem,
    RetrievedCandidate,
    run_retrieval,
)

_REVISION = "a" * 40
_DIGEST = "b" * 64


def _manifest() -> BenchmarkRunManifest:
    return BenchmarkRunManifest(
        schema_version=BENCHMARK_PROTOCOL_SCHEMA_VERSION,
        cohort_id="synthetic-retrieval-v1",
        dataset=DatasetPin(
            suite="locomo",
            dataset_id="synthetic-fixture",
            repository_slug="synthetic/fixture",
            dataset_revision=_REVISION,
            license_id="synthetic",
        ),
        input_provenance_digest=_DIGEST,
        evaluation_layer="retrieval",
        system=SystemPin(
            role="matryca_without_semantic_memory",
            system_id="matryca-plumber",
            implementation_revision=_REVISION,
            configuration_digest=_DIGEST,
            open_source=True,
        ),
        answer_model=None,
        judge_model=None,
        budget=EvaluationBudget(
            context_token_budget=1024,
            retrieval_call_budget=4,
            top_k=3,
            timeout_seconds=1,
        ),
        runtime=RuntimePin(
            harness_revision=_REVISION,
            matryca_revision=_REVISION,
            dependency_lock_digest=_DIGEST,
            hardware_class="synthetic",
            os_family="test",
            runtime_version="python-3.12",
            concurrency=1,
            cache_state="cold",
            failure_policy_id="retain-all-terminal-outcomes",
            retry_policy_id="no-retry",
        ),
        evidence_class="synthetic_design_evidence",
    )


def _evidence() -> RetrievalInputEvidence:
    return RetrievalInputEvidence(
        input_provenance_digest=_DIGEST,
        items=(
            RetrievalItem(item_id="a", query="first", relevant_ids=("doc-1",)),
            RetrievalItem(item_id="b", query="excluded", excluded_reason="fixture_missing"),
        ),
    )


class _FixtureRetriever:
    def __init__(self, system: SystemPin) -> None:
        self.system = system

    def retrieve(self, item: RetrievalItem, *, top_k: int) -> tuple[RetrievedCandidate, ...]:
        assert top_k == 3
        return (RetrievedCandidate(candidate_id="doc-1", rank=1),) if item.item_id == "a" else ()


class _FailureRetriever:
    def __init__(self, system: SystemPin) -> None:
        self.system = system

    def retrieve(self, item: RetrievalItem, *, top_k: int) -> tuple[RetrievedCandidate, ...]:
        del top_k
        if item.item_id == "a":
            raise TimeoutError
        return ()


def test_replay_is_deterministic_and_binds_all_artifacts(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    manifest = _manifest()
    first = run_retrieval(
        manifest,
        _evidence(),
        run_root=first_root,
        retriever=_FixtureRetriever(manifest.system),
    )
    second = run_retrieval(
        manifest,
        _evidence(),
        run_root=second_root,
        retriever=_FixtureRetriever(manifest.system),
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert {artifact.kind for artifact in first.artifacts} == {
        "exclusions",
        "failed_runs",
        "item_results",
        "run_metadata",
    }
    for artifact in first.artifacts:
        payload = (first_root / f"{artifact.kind}.jsonl").read_bytes()
        assert artifact.digest == hashlib.sha256(payload).hexdigest()


def test_no_memory_retriever_emits_empty_context_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", fail_network)
    tmp_path.mkdir(exist_ok=True)
    manifest = _manifest()
    report = run_retrieval(
        manifest,
        _evidence().model_copy(update={"items": (_evidence().items[0],)}),
        run_root=tmp_path,
        retriever=NoMemoryRetriever(system=manifest.system),
    )
    assert report.status == "completed"
    assert (tmp_path / "item_results.jsonl").read_text() == (
        '{"hit_count":0,"item_id":"a","relevant_ids":["doc-1"],"retrieved_ids":[]}\n'
    )


def test_failures_and_exclusions_are_retained(tmp_path: Path) -> None:
    manifest = _manifest()
    report = run_retrieval(
        manifest,
        _evidence(),
        run_root=tmp_path,
        retriever=_FailureRetriever(manifest.system),
    )
    assert report.status == "failed"
    assert '"classification":"timeout"' in (tmp_path / "failed_runs.jsonl").read_text()
    assert '"reason":"fixture_missing"' in (tmp_path / "exclusions.jsonl").read_text()


def test_malformed_inputs_and_output_boundaries_fail_closed(tmp_path: Path) -> None:
    manifest = _manifest()
    with pytest.raises(EvidenceContractError, match="retrieval_seam_system_mismatch"):
        run_retrieval(
            manifest,
            _evidence(),
            run_root=tmp_path,
            retriever=NoMemoryRetriever(
                system=manifest.system.model_copy(update={"implementation_revision": "c" * 40})
            ),
        )
    with pytest.raises(EvidenceContractError, match="input_provenance_digest_mismatch"):
        run_retrieval(
            manifest,
            _evidence().model_copy(update={"input_provenance_digest": "c" * 64}),
            run_root=tmp_path,
            retriever=NoMemoryRetriever(system=manifest.system),
        )
    with pytest.raises(EvidenceContractError, match="invalid_result_ordering"):
        run_retrieval(
            manifest,
            _evidence().model_copy(update={"items": (_evidence().items[:1])}),
            run_root=tmp_path,
            retriever=type(
                "BadRetriever",
                (),
                {
                    "system": manifest.system,
                    "retrieve": lambda _self, _item, *, top_k: (
                        RetrievedCandidate(candidate_id="x", rank=2),
                    )
                },
            )(),
        )

    outside = tmp_path.parent / "outside.jsonl"
    outside.write_bytes(b"untouched")
    (tmp_path / "item_results.jsonl").symlink_to(outside)
    with pytest.raises(EvidenceContractError, match="artifact_path_outside_run_root"):
        run_retrieval(
            manifest,
            _evidence(),
            run_root=tmp_path,
            retriever=NoMemoryRetriever(system=manifest.system),
        )
    assert outside.read_bytes() == b"untouched"


def test_non_retrieval_manifest_is_rejected() -> None:
    with pytest.raises(ValueError, match="end_to_end_run_requires_answer_and_judge"):
        BenchmarkRunManifest.model_validate(
            {**_manifest().model_dump(), "evaluation_layer": "end_to_end_answer"}
        )
