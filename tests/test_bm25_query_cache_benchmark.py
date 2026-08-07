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
