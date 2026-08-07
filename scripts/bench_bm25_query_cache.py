"""Run deterministic, LLM-free BM25 query-cache decision benchmarks."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, NamedTuple

import src.graph.generational_cache as generational_cache
from src.graph.generational_cache import Bm25Corpus, bm25_query_cache_stats, score_bm25_query

resource_module: Any
try:
    resource_module = importlib.import_module("resource")
except ImportError:  # pragma: no cover - Windows uses the optional edge dependency
    resource_module = None

psutil_module: Any
try:
    psutil_module = importlib.import_module("psutil")
except ImportError:  # pragma: no cover - POSIX falls back to ps(1)
    psutil_module = None

_SEED = 20260802
_CAPACITIES = (512, 2_048, 8_192, 16_384)
_DEFAULT_CAPACITY = 8_192
_RESULT_LIMITS = (1, 8, 32, 100)


class Request(NamedTuple):
    query: str
    limit: int


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    documents: int
    requests: int
    repetitions: int
    warmup: int
    seed: int
    capacities: tuple[int, ...]
    multi_corpora: int


def _corpus(document_count: int, *, namespace: str = "") -> Bm25Corpus:
    rels: list[str] = []
    doc_term_freqs: list[dict[str, int]] = []
    doc_lens: list[int] = []
    df: dict[str, int] = {}
    for index in range(document_count):
        tokens = [
            "shared",
            f"topic{index % 64}",
            f"bucket{index % 29}",
            f"document{index}",
        ]
        term_freqs = {token: tokens.count(token) for token in tokens}
        rels.append(f"{namespace}pages/{index:05d}.md")
        doc_term_freqs.append(term_freqs)
        doc_lens.append(len(tokens))
        for token in term_freqs:
            df[token] = df.get(token, 0) + 1
    return Bm25Corpus(
        rels=rels,
        doc_term_freqs=doc_term_freqs,
        doc_lens=doc_lens,
        df=df,
        n_docs=document_count,
        avgdl=sum(doc_lens) / document_count,
    )


def _workloads(config: BenchmarkConfig) -> dict[str, list[Request]]:
    rng = random.Random(config.seed)
    key_count = max(config.capacities)
    query_keys = tuple(
        f"document{index % config.documents} nonce{index}" for index in range(key_count)
    )
    hot_count = max(1, key_count // 5)
    cold_keys = query_keys[hot_count:] or query_keys
    weights = tuple(1.0 / ((index + 1) ** 1.1) for index in range(key_count))

    uniform = [Request(rng.choice(query_keys), 8) for _ in range(config.requests)]
    hot_80_20 = [
        Request(
            rng.choice(query_keys[:hot_count] if rng.random() < 0.8 else cold_keys),
            8,
        )
        for _ in range(config.requests)
    ]
    zipf = [
        Request(query, 8) for query in rng.choices(query_keys, weights=weights, k=config.requests)
    ]
    capacity_pressure = [
        Request(
            query_keys[index % key_count],
            _RESULT_LIMITS[index % len(_RESULT_LIMITS)],
        )
        for index in range(config.requests)
    ]
    row_pressure = [Request(f"shared absent{index}", 100) for index in range(config.requests)]
    edge_cases = [
        Request("", 8),
        Request("   ", 8),
        Request("shared shared", 1),
        Request("shared shared", 8),
        Request("missing-token", 32),
        Request("topic1 bucket1", 100),
    ]
    return {
        "capacity_pressure": capacity_pressure,
        "edge_cases": edge_cases,
        "hot_80_20": hot_80_20,
        "row_pressure": row_pressure,
        "uniform": uniform,
        "zipf": zipf,
    }


def _percentile(sorted_values: Sequence[int], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _current_rss_bytes() -> int:
    if psutil_module is not None:
        return int(psutil_module.Process().memory_info().rss)
    if os.name != "posix":
        raise RuntimeError("current RSS measurement requires the 'edge' dependency")
    try:
        completed = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(completed.stdout.strip()) * 1_024
    except (OSError, ValueError, subprocess.SubprocessError):
        return _peak_rss_bytes()


def _peak_rss_bytes() -> int:
    if resource_module is None:
        raise RuntimeError("peak RSS measurement requires the 'edge' dependency")
    peak = resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1_024)


def _reset_query_cache(corpus: Bm25Corpus, *, invalidation: bool = False) -> None:
    with corpus._query_lock:
        corpus.query_cache.clear()
        corpus.query_cache_hits = 0
        corpus.query_cache_misses = 0
        corpus.query_cache_result_rows = 0
        if invalidation:
            corpus.query_cache_invalidations += 1


def _expected_results(corpus: Bm25Corpus, requests: Sequence[Request]) -> dict[Request, Any]:
    expected: dict[Request, Any] = {}
    for request in dict.fromkeys(requests):
        expected[request] = score_bm25_query(corpus, request.query, limit=request.limit)
    return expected


def _measure_workload(
    corpus: Bm25Corpus,
    requests: Sequence[Request],
    expected: dict[Request, Any],
    *,
    warmup: int,
) -> dict[str, Any]:
    for request in requests[:warmup]:
        score_bm25_query(corpus, request.query, limit=request.limit)
    _reset_query_cache(corpus)

    latencies_ns: list[int] = []
    entry_pressure_evictions = 0
    row_pressure_evictions = 0
    rss_before = _current_rss_bytes()
    for request in requests:
        before = bm25_query_cache_stats(corpus)
        started = time.perf_counter_ns()
        observed = score_bm25_query(corpus, request.query, limit=request.limit)
        latencies_ns.append(time.perf_counter_ns() - started)
        if observed != expected[request]:
            raise AssertionError(f"BM25 parity failed for {request!r}")
        after = bm25_query_cache_stats(corpus)
        if after["misses"] > before["misses"]:
            if before["entries"] + 1 > before["capacity"]:
                entry_pressure_evictions += 1
            if before["result_rows"] + len(observed) > before["result_row_capacity"]:
                row_pressure_evictions += 1

    stats = bm25_query_cache_stats(corpus)
    sorted_latencies = sorted(latencies_ns)
    cacheable = stats["hits"] + stats["misses"]
    return {
        "cache": stats,
        "cache_hit_ratio": round(stats["hits"] / cacheable, 6) if cacheable else 0.0,
        "entry_pressure_evictions": entry_pressure_evictions,
        "latency_us": {
            "median": round(median(sorted_latencies) / 1_000, 3),
            "p50": round(_percentile(sorted_latencies, 0.50) / 1_000, 3),
            "p95": round(_percentile(sorted_latencies, 0.95) / 1_000, 3),
            "p99": round(_percentile(sorted_latencies, 0.99) / 1_000, 3),
        },
        "parity": True,
        "peak_rss_bytes": _peak_rss_bytes(),
        "requests": len(requests),
        "row_pressure_evictions": row_pressure_evictions,
        "rss_delta_bytes": _current_rss_bytes() - rss_before,
        "rss_end_bytes": _current_rss_bytes(),
        "unique_requests": len(set(requests)),
    }


def _capacity_matrix(config: BenchmarkConfig) -> dict[str, list[dict[str, Any]]]:
    workloads = _workloads(config)
    expected = {
        name: _expected_results(_corpus(config.documents), requests)
        for name, requests in workloads.items()
    }
    matrix: dict[str, list[dict[str, Any]]] = {}
    for name, requests in workloads.items():
        matrix[name] = []
        for capacity in config.capacities:
            for repetition in range(config.repetitions):
                generational_cache._DEFAULT_BM25_QUERY_CACHE_MAX_ENTRIES = capacity
                measured = _measure_workload(
                    _corpus(config.documents),
                    requests,
                    expected[name],
                    warmup=min(config.warmup, len(requests)),
                )
                matrix[name].append(
                    {"capacity": capacity, "repetition": repetition + 1, **measured}
                )
    return matrix


def _mutation_probe(config: BenchmarkConfig) -> dict[str, Any]:
    corpus = _corpus(config.documents)
    requests = _workloads(config)["hot_80_20"]
    expected = _expected_results(_corpus(config.documents), requests)
    latencies_ns: list[int] = []
    rebuild_ns: list[int] = []
    every = max(1, len(requests) // 100)
    for index, request in enumerate(requests):
        if index and index % every == 0:
            started = time.perf_counter_ns()
            _reset_query_cache(corpus, invalidation=True)
            latencies_ns.append(time.perf_counter_ns() - started)
        if index and index % (every * 10) == 0:
            started = time.perf_counter_ns()
            _corpus(config.documents)
            rebuild_ns.append(time.perf_counter_ns() - started)
        if score_bm25_query(corpus, request.query, limit=request.limit) != expected[request]:
            raise AssertionError("BM25 parity failed during mutation probe")
    return {
        "cache": bm25_query_cache_stats(corpus),
        "invalidation_latency_us_p99": round(_percentile(sorted(latencies_ns), 0.99) / 1_000, 3),
        "parity": True,
        "rebuild_latency_us_p99": round(_percentile(sorted(rebuild_ns), 0.99) / 1_000, 3),
    }


def _multi_corpus_probe(config: BenchmarkConfig) -> dict[str, Any]:
    requests = _workloads(config)["uniform"]
    corpora = [
        _corpus(config.documents, namespace=f"graph{index}/")
        for index in range(config.multi_corpora)
    ]
    expected = [
        _expected_results(
            _corpus(config.documents, namespace=f"graph{index}/"),
            requests,
        )
        for index in range(config.multi_corpora)
    ]

    def run(index: int) -> None:
        corpus = corpora[index]
        for request in requests:
            if (
                score_bm25_query(corpus, request.query, limit=request.limit)
                != expected[index][request]
            ):
                raise AssertionError(f"BM25 parity failed for corpus {index}")

    started = time.perf_counter_ns()
    with ThreadPoolExecutor(max_workers=config.multi_corpora) as executor:
        list(executor.map(run, range(config.multi_corpora)))
    return {
        "corpora": config.multi_corpora,
        "parity": True,
        "peak_rss_bytes": _peak_rss_bytes(),
        "requests_per_corpus": len(requests),
        "rss_end_bytes": _current_rss_bytes(),
        "wall_seconds": round((time.perf_counter_ns() - started) / 1_000_000_000, 6),
    }


def _source_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.strip()


def run_benchmark(config: BenchmarkConfig) -> dict[str, Any]:
    original_capacity = generational_cache._DEFAULT_BM25_QUERY_CACHE_MAX_ENTRIES
    try:
        build_started = time.perf_counter_ns()
        _corpus(config.documents)
        build_seconds = (time.perf_counter_ns() - build_started) / 1_000_000_000
        matrix = _capacity_matrix(config)
        generational_cache._DEFAULT_BM25_QUERY_CACHE_MAX_ENTRIES = _DEFAULT_CAPACITY
        mutation = _mutation_probe(config)
        multi_corpus = _multi_corpus_probe(config)
    finally:
        generational_cache._DEFAULT_BM25_QUERY_CACHE_MAX_ENTRIES = original_capacity
    return {
        "benchmark_schema_version": 1,
        "config": asdict(config),
        "corpus_manifest": {
            "benchmark_query_key_cardinality": max(config.capacities),
            "documents": config.documents,
            "terms_per_document": 4,
            "topic_cardinality": 64,
            "bucket_cardinality": 29,
        },
        "environment": {
            "machine": platform.machine(),
            "os": platform.platform(),
            "python": platform.python_version(),
            "source_commit": _source_commit(),
        },
        "measurements": {
            "capacity_matrix": matrix,
            "corpus_build_seconds": round(build_seconds, 6),
            "multi_corpus": multi_corpus,
            "mutation_storm": mutation,
        },
        "production_default_entries": original_capacity,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents", type=int, default=128)
    parser.add_argument("--requests", type=int, default=20_000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=512)
    parser.add_argument("--seed", type=int, default=_SEED)
    parser.add_argument("--capacities", default="512,2048,8192,16384")
    parser.add_argument("--multi-corpora", type=int, default=4)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    capacities = tuple(int(value) for value in args.capacities.split(","))
    if (
        args.documents < 1
        or args.requests < 1
        or args.repetitions < 1
        or args.warmup < 0
        or args.multi_corpora < 1
        or not capacities
        or any(capacity < 1 for capacity in capacities)
    ):
        raise SystemExit("benchmark dimensions and capacities must be positive")
    config = BenchmarkConfig(
        documents=args.documents,
        requests=args.requests,
        repetitions=args.repetitions,
        warmup=args.warmup,
        seed=args.seed,
        capacities=capacities,
        multi_corpora=args.multi_corpora,
    )
    rendered = json.dumps(run_benchmark(config), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
