"""Tests for the deterministic BM25 query-cache benchmark harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.bench_bm25_query_cache as benchmark


@pytest.fixture
def config() -> benchmark.BenchmarkConfig:
    return benchmark.BenchmarkConfig(
        documents=16,
        requests=24,
        repetitions=1,
        warmup=4,
        seed=7,
        capacities=(4, 16),
        multi_corpora=2,
    )


def test_workloads_are_deterministic_and_cover_required_distributions(
    config: benchmark.BenchmarkConfig,
) -> None:
    first = benchmark._workloads(config)
    second = benchmark._workloads(config)

    assert first == second
    assert set(first) == {
        "capacity_pressure",
        "edge_cases",
        "hot_80_20",
        "row_pressure",
        "uniform",
        "zipf",
    }
    assert {request.limit for request in first["capacity_pressure"]} == {1, 8, 32, 100}
    assert any(not request.query.strip() for request in first["edge_cases"])
    assert len(set(first["uniform"])) > config.capacities[0]


def test_default_cli_profile_pressures_the_largest_candidate_capacity() -> None:
    args = benchmark._parser().parse_args([])
    capacities = tuple(int(value) for value in args.capacities.split(","))

    assert args.requests > max(capacities)
    assert args.repetitions >= 3
    assert args.warmup > 0


def test_benchmark_matrix_preserves_parity_and_capacity_bounds(
    config: benchmark.BenchmarkConfig,
) -> None:
    payload = benchmark.run_benchmark(config)

    assert payload["production_default_entries"] == 8_192
    assert payload["config"] == {
        "capacities": (4, 16),
        "documents": 16,
        "multi_corpora": 2,
        "repetitions": 1,
        "requests": 24,
        "seed": 7,
        "warmup": 4,
    }
    for runs in payload["measurements"]["capacity_matrix"].values():
        for run in runs:
            assert run["parity"] is True
            assert run["cache"]["entries"] <= run["cache"]["capacity"]
            assert run["cache"]["result_rows"] <= run["cache"]["result_row_capacity"]
            assert set(run["latency_us"]) == {"median", "p50", "p95", "p99"}
            assert run["peak_rss_bytes"] > 0
            assert run["rss_end_bytes"] > 0

    entry_pressure = payload["measurements"]["capacity_matrix"]["capacity_pressure"]
    assert entry_pressure[0]["entry_pressure_evictions"] > 0
    assert entry_pressure[-1]["cache_hit_ratio"] > entry_pressure[0]["cache_hit_ratio"]

    mutation = payload["measurements"]["mutation_storm"]
    assert mutation["parity"] is True
    assert mutation["cache"]["invalidations"] > 0
    assert mutation["invalidation_latency_us_p99"] >= 0
    assert mutation["rebuild_latency_us_p99"] >= 0

    multi_corpus = payload["measurements"]["multi_corpus"]
    assert multi_corpus["parity"] is True
    assert multi_corpus["corpora"] == config.multi_corpora
    assert multi_corpus["peak_rss_bytes"] > 0
    assert multi_corpus["rss_end_bytes"] > 0


def test_main_writes_machine_readable_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result.json"
    monkeypatch.setattr(benchmark, "_source_commit", lambda: "a" * 40)

    assert (
        benchmark.main(
            [
                "--documents",
                "8",
                "--requests",
                "12",
                "--capacities",
                "4,8",
                "--multi-corpora",
                "2",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["benchmark_schema_version"] == 1
    assert payload["environment"]["source_commit"] == "a" * 40


def test_scorecard_manifest_validates_and_is_deterministic() -> None:
    manifest_path = Path("tests/fixtures/bm25_hard_negative_manifest_v1.json")
    first, first_digest = benchmark._read_manifest(manifest_path)
    second, second_digest = benchmark._read_manifest(manifest_path)

    assert first.schema_version == 2
    assert first.dataset_id == "matryca-bm25-hard-negative-it-v1"
    assert len(first.cases) >= 20
    assert first_digest == second_digest

    first_payload = benchmark._run_scorecard_benchmark(first, top_k=8)
    second_payload = benchmark._run_scorecard_benchmark(first, top_k=8)
    assert first_payload["manifest_schema_version"] == 2
    assert first_payload["manifest_dataset_id"] == "matryca-bm25-hard-negative-it-v1"
    assert first_payload["scorecard_fingerprint"] == second_payload["scorecard_fingerprint"]
    assert first_payload["metrics"]["recall_at_k"] >= 0.0
    assert first_payload["metrics"]["recall_at_k"] <= 1.0
    assert first_payload["metrics"]["mrr"] >= 0.0
    assert first_payload["metrics"]["mrr"] <= 1.0
    assert first_payload["metrics"]["ndcg"] >= 0.0
    assert first_payload["metrics"]["ndcg"] <= 1.0
    assert first_payload["metrics"]["confidence_intervals"]["recall_at_k"]["samples"] == 1_000
    assert (
        first_payload["metrics"]["confidence_intervals"]["recall_at_k"]["low"]
        <= (first_payload["metrics"]["recall_at_k"])
        <= first_payload["metrics"]["confidence_intervals"]["recall_at_k"]["high"]
    )
    assert first_payload["signal_ablations"]["no_retrieval"]["recall_at_k"] == 0.0
    assert first_payload["metrics"]["recall_at_k"] == 0.8333
    assert first_payload["metrics"]["mrr"] == 0.7708
    assert first_payload["metrics"]["ndcg"] == 0.7898
    assert first_payload["metrics"]["stale"] == {
        "hits": 10,
        "query_rate": 0.333333,
        "rate_per_query_position": 0.052083,
    }
    assert first_payload["metrics"]["contradiction"] == {
        "hits": 9,
        "query_rate": 0.375,
        "rate_per_query_position": 0.046875,
    }
    assert first_payload["metrics"]["abstention"] == {
        "enabled_cases": 4,
        "passed_cases": 1,
        "rate": 0.25,
        "precision": 1.0,
        "recall": 0.25,
        "confusion": {
            "true_positive": 1,
            "true_negative": 20,
            "false_positive": 0,
            "false_negative": 3,
        },
    }
    assert first_payload["metrics"]["update"] == {
        "cases": 2,
        "accuracy": 1.0,
        "confusion": {
            "true_positive": 2,
            "true_negative": 0,
            "false_positive": 0,
            "false_negative": 0,
        },
        "by_class": {
            "update_gold": {
                "cases": 2,
                "accuracy": 1.0,
                "confusion": {
                    "true_positive": 2,
                    "true_negative": 0,
                    "false_positive": 0,
                    "false_negative": 0,
                },
            },
            "superseded_gold": {"cases": 22},
        },
    }
    assert first_payload["case_count"] == second_payload["case_count"] == 24
    assert first_payload["case_results"] == second_payload["case_results"]
    assert [case["seed"] for case in first_payload["case_results"]] == sorted(
        case.seed for case in first.cases
    )
    assert set(first_payload["measurements"]).issuperset(
        {
            "cache",
            "cache_hit_ratio",
            "latency_us",
            "peak_rss_bytes",
            "payload_estimate_bytes",
            "rss_end_bytes",
            "requests",
            "top_k",
            "query_cache_row_budget",
        }
    )
    assert first_payload["measurements"]["cache_hit_ratio"] >= 0.0
    assert first_payload["measurements"]["latency_us"]["median"] >= 0.0
    assert first_payload["measurements"]["latency_us"]["p99"] >= 0.0
    assert first_payload["measurements"]["peak_rss_bytes"] >= 0
    assert first_payload["measurements"]["payload_estimate_bytes"] >= 0
    assert first_payload["measurements"]["context_estimate_tokens"] >= 0
    assert first_payload["measurements"]["estimated_model_cost_usd"] == 0.0
    assert first_payload["measurements"]["model_cost_applicability"] == "not_applicable"
    assert first_payload["measurements"]["rss_end_bytes"] >= 0
    assert first_payload["measurements"]["requests"] == len(first.cases)
    assert first_payload["measurements"]["top_k"] == 8
    assert first_payload["measurements"]["query_cache_row_budget"] > 0
    assert first_digest == second_digest


def test_scorecard_main_writes_schema_and_environment_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = Path("tests/fixtures/bm25_hard_negative_manifest_v1.json")
    output = tmp_path / "scorecard.json"
    import hashlib

    expected_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    monkeypatch.setattr(benchmark, "_source_commit", lambda: "b" * 40)

    assert (
        benchmark.main(
            [
                "--manifest-path",
                str(manifest_path),
                "--top-k",
                "6",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["benchmark_schema_version"] == 3
    assert payload["manifest"]["digest"] == expected_digest
    assert payload["manifest"]["schema_version"] == 2
    assert payload["environment"]["manifest_schema_version"] == 2
    assert payload["environment"]["source_commit"] == "b" * 40
    assert payload["metrics"]["abstention"]["enabled_cases"] == 4
    assert payload["metrics"]["abstention"]["rate"] >= 0.0
    assert payload["metrics"]["abstention"]["rate"] <= 1.0
    assert payload["evaluation_scope"] == {
        "end_to_end_answer_evaluated": False,
        "retrieval_only": True,
    }
    assert payload["measurements"]["top_k"] == 6
    assert (
        payload["measurements"]["cache"]["entries"] <= payload["measurements"]["cache"]["capacity"]
    )


def test_scorecard_uses_manifest_top_k_unless_cli_overrides_it() -> None:
    config = benchmark.BenchmarkConfig(
        documents=4,
        requests=1,
        repetitions=1,
        warmup=1,
        seed=1,
        capacities=(4,),
        multi_corpora=1,
    )
    manifest_path = Path("tests/fixtures/bm25_hard_negative_manifest_v1.json")

    default_payload = benchmark.run_benchmark(config, manifest_path=manifest_path)
    overridden_payload = benchmark.run_benchmark(config, manifest_path=manifest_path, top_k=3)

    assert default_payload["measurements"]["top_k"] == 8
    assert overridden_payload["measurements"]["top_k"] == 3


def test_scorecard_metrics_detect_known_relevant_and_hard_negative_hits() -> None:
    manifest = benchmark.ManifestPayload(
        schema_version=2,
        dataset_id="matryca-scorecard-unit-hits-v1",
        description="Synthetic ranking sanity check for known hits",
        top_k=2,
        documents=[
            benchmark.ManifestDocument(
                id="doc_relevant",
                title="Rilevante",
                content="alpha beta gamma",
                stale=False,
            ),
            benchmark.ManifestDocument(
                id="doc_neg",
                title="Negativo",
                content="alpha beta delta",
                stale=False,
            ),
            benchmark.ManifestDocument(
                id="doc_other",
                title="Nessun segnale",
                content="zeta eta theta",
                stale=False,
            ),
        ],
        cases=[
            benchmark.ManifestCase(
                seed=777,
                query="alpha",
                relevant=["doc_relevant"],
                hard_negatives=["doc_neg"],
                gold_classification="update_gold",
            )
        ],
    )
    payload = benchmark._run_scorecard_benchmark(manifest, top_k=2)
    first_case = payload["case_results"][0]
    assert first_case["seed"] == 777
    assert first_case["metrics"]["recall_at_k"] == 1.0
    assert first_case["metrics"]["contradiction_hits"] >= 1
    assert first_case["metrics"]["stale_hits"] == 0


def test_read_manifest_enforces_scorecard_invariants(tmp_path: Path) -> None:
    shared_payload = {
        "schema_version": 2,
        "dataset_id": "matryca-scorecard-invariants-v1",
        "description": "Invariant validation fixture",
        "top_k": 8,
        "documents": [
            {"id": "doc_a", "title": "Doc A", "content": "alpha", "stale": False},
            {"id": "doc_b", "title": "Doc B", "content": "beta", "stale": False},
            {"id": "doc_c", "title": "Doc C", "content": "gamma", "stale": False},
        ],
    }
    base_cases = [
        {
            "seed": 1000 + index,
            "query": f"alpha {index}",
            "relevant": ["doc_a"],
            "hard_negatives": ["doc_b", "doc_c"],
            "gold_classification": "superseded_gold",
        }
        for index in range(20)
    ]

    duplicate_seed_cases = base_cases.copy()
    duplicate_seed_cases[1] = {
        "seed": base_cases[0]["seed"],
        "query": "alpha duplicate",
        "relevant": ["doc_b"],
        "hard_negatives": ["doc_b", "doc_c"],
        "gold_classification": "superseded_gold",
    }
    duplicate_seed_payload = {**shared_payload, "cases": duplicate_seed_cases}

    abstain_with_relevant_cases = base_cases.copy()
    abstain_with_relevant_cases[0] = {
        **base_cases[0],
        "abstain_when_no_candidates": True,
        "relevant": ["doc_a"],
    }
    abstain_with_relevant_payload = {**shared_payload, "cases": abstain_with_relevant_cases}

    overlapping_cases = base_cases.copy()
    overlapping_cases[0] = {**base_cases[0], "hard_negatives": ["doc_a", "doc_b"]}
    overlapping_payload = {**shared_payload, "cases": overlapping_cases}

    too_few_negatives_cases = base_cases.copy()
    too_few_negatives_cases[0] = {**base_cases[0], "hard_negatives": ["doc_b"]}
    too_few_negatives_payload = {**shared_payload, "cases": too_few_negatives_cases}

    unknown_nested_field_cases = base_cases.copy()
    unknown_nested_field_cases[0] = {**base_cases[0], "untracked": True}
    unknown_nested_field_payload = {**shared_payload, "cases": unknown_nested_field_cases}

    missing_classification_cases = base_cases.copy()
    missing_classification_cases[0] = {
        key: value for key, value in base_cases[0].items() if key != "gold_classification"
    }
    missing_classification_payload = {**shared_payload, "cases": missing_classification_cases}

    abstain_min_cases = base_cases.copy()
    abstain_min_cases[0] = {
        **base_cases[0],
        "query": "alpha abstain",
        "relevant": [],
        "hard_negatives": ["doc_b"],
        "abstain_when_no_candidates": True,
    }
    abstain_min_payload = {**shared_payload, "cases": abstain_min_cases}

    duplicate_seed_path = tmp_path / "duplicate.json"
    abstain_with_relevant_path = tmp_path / "abstain_with_relevant.json"
    overlapping_path = tmp_path / "overlap.json"
    too_few_negatives_path = tmp_path / "few_negatives.json"
    unknown_nested_field_path = tmp_path / "unknown_nested_field.json"
    missing_classification_path = tmp_path / "missing_classification.json"
    abstain_min_path = tmp_path / "abstain_min.json"

    duplicate_seed_path.write_text(json.dumps(duplicate_seed_payload), encoding="utf-8")
    abstain_with_relevant_path.write_text(
        json.dumps(abstain_with_relevant_payload), encoding="utf-8"
    )
    overlapping_path.write_text(json.dumps(overlapping_payload), encoding="utf-8")
    too_few_negatives_path.write_text(json.dumps(too_few_negatives_payload), encoding="utf-8")
    unknown_nested_field_path.write_text(json.dumps(unknown_nested_field_payload), encoding="utf-8")
    missing_classification_path.write_text(
        json.dumps(missing_classification_payload), encoding="utf-8"
    )
    abstain_min_path.write_text(json.dumps(abstain_min_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate case seed"):
        benchmark._read_manifest(duplicate_seed_path)
    with pytest.raises(ValueError, match="abstention mode"):
        benchmark._read_manifest(abstain_with_relevant_path)
    with pytest.raises(ValueError, match="must not overlap"):
        benchmark._read_manifest(overlapping_path)
    with pytest.raises(ValueError, match="must define at least two hard-negative labels"):
        benchmark._read_manifest(too_few_negatives_path)
    with pytest.raises(ValueError, match="must define at least two hard-negatives"):
        benchmark._read_manifest(abstain_min_path)
    with pytest.raises(ValueError, match="untracked"):
        benchmark._read_manifest(unknown_nested_field_path)
    with pytest.raises(ValueError, match="gold_classification"):
        benchmark._read_manifest(missing_classification_path)


def test_scorecard_zero_denominators_are_explicit_zero() -> None:
    metrics = benchmark._aggregate_rank_metrics(
        [
            {
                "recall_at_k": 0.0,
                "mrr": 0.0,
                "ndcg": 0.0,
                "stale_hits": 0,
                "contradiction_hits": 0,
                "abstained": False,
                "update_expected": False,
                "update_predicted": False,
                "abstention_expected": False,
            }
        ],
        top_k=8,
        bootstrap_seed=1,
        abstention_expected=0,
        abstention_passed=0,
    )

    assert metrics["abstention"]["precision"] == 0.0
    assert metrics["abstention"]["recall"] == 0.0
    assert metrics["update"]["accuracy"] == 0.0


def test_manifest_mode_does_not_touch_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import socket

    config = benchmark.BenchmarkConfig(
        documents=4,
        requests=1,
        repetitions=1,
        warmup=1,
        seed=1,
        capacities=(4,),
        multi_corpora=1,
    )
    manifest_path = Path("tests/fixtures/bm25_hard_negative_manifest_v1.json")

    def reject_network(*_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("Unexpected network call in scorecard benchmark")

    monkeypatch.setattr(socket, "gethostbyname", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)

    benchmark.run_benchmark(config, manifest_path=manifest_path, top_k=8)
