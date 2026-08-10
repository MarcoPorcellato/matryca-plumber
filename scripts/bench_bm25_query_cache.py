"""Run deterministic, LLM-free BM25 query-cache decision benchmarks."""

from __future__ import annotations

import argparse
import hashlib
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
from typing import Any, Literal, NamedTuple

import src.graph.generational_cache as generational_cache
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from src.graph.generational_cache import (
    Bm25Corpus,
    bm25_diagnostics_snapshot,
    bm25_query_cache_stats,
    score_bm25_query,
)

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
_MANIFEST_SCHEMA_VERSION = 2
_SCORECARD_SCHEMA_VERSION = 3
_DEFAULT_TOP_K = 8
GoldClassification = Literal["update_gold", "superseded_gold"]


class ManifestDocument(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    stale: bool = False

    model_config = ConfigDict(extra="forbid")


class ManifestCase(BaseModel):
    seed: int
    query: str = Field(min_length=1)
    relevant: list[str]
    hard_negatives: list[str] = Field(default_factory=list)
    abstain_when_no_candidates: bool = False
    gold_classification: GoldClassification

    model_config = ConfigDict(extra="forbid")


class ManifestPayload(BaseModel):
    schema_version: int
    dataset_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    documents: list[ManifestDocument]
    cases: list[ManifestCase]
    top_k: int = Field(default=_DEFAULT_TOP_K, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")


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


def _read_manifest(path: Path) -> tuple[ManifestPayload, str]:
    raw = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid manifest JSON in {path}: {error}") from error

    try:
        manifest = ManifestPayload.model_validate(data)
    except ValidationError as error:
        raise ValueError(f"Invalid manifest schema in {path}: {error}") from error

    if manifest.schema_version != _MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported manifest schema_version {manifest.schema_version}; "
            f"expected {_MANIFEST_SCHEMA_VERSION}"
        )
    if len(manifest.cases) < 20:
        raise ValueError(
            f"Manifest {manifest.dataset_id} must include at least 20 "
            f"cases; got {len(manifest.cases)}"
        )

    document_ids = {document.id for document in manifest.documents}
    if len(document_ids) != len(manifest.documents):
        raise ValueError(f"Manifest {manifest.dataset_id} has duplicated document ids")

    seen_seeds: set[int] = set()
    for case in sorted(manifest.cases, key=lambda item: (item.seed, item.query)):
        if case.seed in seen_seeds:
            raise ValueError(
                f"Manifest {manifest.dataset_id} contains duplicate case seed {case.seed}"
            )
        seen_seeds.add(case.seed)
        missing_relevant = set(case.relevant) - document_ids
        missing_hard_negatives = set(case.hard_negatives) - document_ids
        if missing_relevant:
            raise ValueError(
                f"Case seed {case.seed} references missing relevant ids {sorted(missing_relevant)}"
            )
        if missing_hard_negatives:
            raise ValueError(
                f"Case seed {case.seed} references missing "
                f"hard-negative ids {sorted(missing_hard_negatives)}"
            )
        if not set(case.relevant).isdisjoint(case.hard_negatives):
            raise ValueError(
                f"Case seed {case.seed} must not overlap relevant and hard-negative labels"
            )
        if case.abstain_when_no_candidates:
            if case.relevant:
                raise ValueError(
                    f"Case seed {case.seed} abstention mode must not define relevant labels"
                )
            if len(case.hard_negatives) < 2:
                raise ValueError(
                    f"Case seed {case.seed} abstention mode must define at least two hard-negatives"
                )
        elif not case.relevant:
            raise ValueError(f"Case seed {case.seed} must define at least one relevant label")
        elif len(case.hard_negatives) < 2:
            raise ValueError(f"Case seed {case.seed} must define at least two hard-negative labels")

    return manifest, digest


def _to_relation(document_id: str) -> str:
    return f"pages/{document_id}.md"


def _corpus_from_manifest(
    manifest: ManifestPayload,
) -> tuple[Bm25Corpus, set[str]]:
    from src.rag.local_query import tokenize

    rels: list[str] = []
    doc_term_freqs: list[dict[str, int]] = []
    doc_lens: list[int] = []
    df: dict[str, int] = {}
    stale_rels: set[str] = set()

    for document in manifest.documents:
        rel = _to_relation(document.id)
        rels.append(rel)
        tokens = [token for token in tokenize(document.content) if token]
        term_freqs = {token: tokens.count(token) for token in tokens}
        if not term_freqs:
            raise ValueError(f"Manifest document {document.id} contains no indexable content")
        doc_term_freqs.append(term_freqs)
        doc_lens.append(len(tokens))
        for token in term_freqs:
            df[token] = df.get(token, 0) + 1
        if document.stale:
            stale_rels.add(rel)

    document_count = len(doc_term_freqs)
    if document_count == 0:
        raise ValueError(f"Manifest {manifest.dataset_id} has no documents")

    return (
        Bm25Corpus(
            rels=rels,
            doc_term_freqs=doc_term_freqs,
            doc_lens=doc_lens,
            df=df,
            n_docs=document_count,
            avgdl=sum(doc_lens) / document_count,
        ),
        stale_rels,
    )


def _dcg(gains: Sequence[float]) -> float:
    return sum(gain / math.log2(index + 2.0) for index, gain in enumerate(gains))


def _rank_metrics(
    retrieved_rels: list[str],
    relevant_rels: set[str],
    hard_negative_rels: set[str],
    stale_rels: set[str],
    top_k: int,
    *,
    has_reference: bool,
    update_expected: bool = False,
    abstention_expected: bool = False,
) -> dict[str, float | int | bool]:
    top = retrieved_rels[:top_k]
    relevance = [1 if rel in relevant_rels else 0 for rel in top]
    stale_hits = sum(1 for rel in top if rel in stale_rels)
    contradiction_hits = sum(1 for rel in top if rel in hard_negative_rels)
    recall = (
        sum(1 for rel in relevant_rels if rel in top) / len(relevant_rels) if relevant_rels else 0.0
    )
    mrr = 0.0
    if has_reference:
        for position, rel in enumerate(top, start=1):
            if rel in relevant_rels:
                mrr = 1.0 / position
                break
    ideal = _dcg([1] * len(relevant_rels))
    ndcg = _dcg(relevance) / ideal if ideal else 0.0
    return {
        "recall_at_k": round(recall, 4),
        "mrr": round(mrr, 4),
        "ndcg": round(ndcg, 4),
        "stale_hits": stale_hits,
        "contradiction_hits": contradiction_hits,
        "abstained": has_reference is False and len(top) == 0,
        "update_expected": update_expected,
        "update_predicted": bool(relevant_rels.intersection(top)),
        "abstention_expected": abstention_expected,
    }


def _confidence_interval(
    values: Sequence[float], *, seed: int, samples: int = 1_000
) -> dict[str, Any]:
    """Return a deterministic percentile-bootstrap interval for a mean metric."""
    if not values:
        return {"confidence_level": 0.95, "high": 0.0, "low": 0.0, "samples": 0}

    rng = random.Random(seed)
    count = len(values)
    bootstrap_means = sorted(
        sum(rng.choice(values) for _ in range(count)) / count for _ in range(samples)
    )
    return {
        "confidence_level": 0.95,
        "low": round(_percentile(bootstrap_means, 0.025), 4),
        "high": round(_percentile(bootstrap_means, 0.975), 4),
        "samples": samples,
    }


def _aggregate_rank_metrics(
    case_metrics: Sequence[dict[str, float | int | bool]],
    *,
    top_k: int,
    bootstrap_seed: int,
    abstention_expected: int,
    abstention_passed: int,
) -> dict[str, Any]:
    query_count = max(1, len(case_metrics))
    recalls = [float(metrics["recall_at_k"]) for metrics in case_metrics]
    mrrs = [float(metrics["mrr"]) for metrics in case_metrics]
    ndcgs = [float(metrics["ndcg"]) for metrics in case_metrics]
    stale_hits = sum(int(metrics["stale_hits"]) for metrics in case_metrics)
    contradiction_hits = sum(int(metrics["contradiction_hits"]) for metrics in case_metrics)
    stale_queries = sum(1 for metrics in case_metrics if metrics["stale_hits"])
    contradiction_queries = sum(1 for metrics in case_metrics if metrics["contradiction_hits"])

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 6) if denominator else 0.0

    def confusion(expected: Sequence[bool], predicted: Sequence[bool]) -> dict[str, int]:
        return {
            "true_positive": sum(
                actual and guess for actual, guess in zip(expected, predicted, strict=True)
            ),
            "true_negative": sum(
                not actual and not guess for actual, guess in zip(expected, predicted, strict=True)
            ),
            "false_positive": sum(
                not actual and guess for actual, guess in zip(expected, predicted, strict=True)
            ),
            "false_negative": sum(
                actual and not guess for actual, guess in zip(expected, predicted, strict=True)
            ),
        }

    update_cases = [metrics for metrics in case_metrics if metrics["update_expected"]]
    update_predictions = [bool(metrics["update_predicted"]) for metrics in update_cases]
    update_confusion = confusion([True] * len(update_predictions), update_predictions)
    abstention_confusion = confusion(
        [bool(metrics["abstention_expected"]) for metrics in case_metrics],
        [bool(metrics["abstained"]) for metrics in case_metrics],
    )
    return {
        "recall_at_k": round(sum(recalls) / query_count, 4),
        "mrr": round(sum(mrrs) / query_count, 4),
        "ndcg": round(sum(ndcgs) / query_count, 4),
        "confidence_intervals": {
            "mrr": _confidence_interval(mrrs, seed=bootstrap_seed + 1),
            "ndcg": _confidence_interval(ndcgs, seed=bootstrap_seed + 2),
            "recall_at_k": _confidence_interval(recalls, seed=bootstrap_seed),
        },
        "stale": {
            "hits": stale_hits,
            "query_rate": round(stale_queries / query_count, 6),
            "rate_per_query_position": round(stale_hits / (query_count * top_k), 6),
        },
        "contradiction": {
            "hits": contradiction_hits,
            "query_rate": round(contradiction_queries / query_count, 6),
            "rate_per_query_position": round(contradiction_hits / (query_count * top_k), 6),
        },
        "abstention": {
            "enabled_cases": abstention_expected,
            "passed_cases": abstention_passed,
            "rate": round(abstention_passed / abstention_expected, 6)
            if abstention_expected
            else 0.0,
            "precision": ratio(
                abstention_confusion["true_positive"],
                abstention_confusion["true_positive"] + abstention_confusion["false_positive"],
            ),
            "recall": ratio(
                abstention_confusion["true_positive"],
                abstention_confusion["true_positive"] + abstention_confusion["false_negative"],
            ),
            "confusion": abstention_confusion,
        },
        "update": {
            "cases": len(update_cases),
            "accuracy": ratio(
                update_confusion["true_positive"] + update_confusion["true_negative"],
                sum(update_confusion.values()),
            ),
            "confusion": update_confusion,
            "by_class": {
                "update_gold": {
                    "cases": len(update_cases),
                    "accuracy": ratio(
                        update_confusion["true_positive"] + update_confusion["true_negative"],
                        sum(update_confusion.values()),
                    ),
                    "confusion": update_confusion,
                },
                "superseded_gold": {
                    "cases": len(case_metrics) - len(update_cases),
                },
            },
        },
    }


def _run_scorecard_benchmark(manifest: ManifestPayload, *, top_k: int) -> dict[str, Any]:
    corpus, stale_rels = _corpus_from_manifest(manifest)
    latencies_ns: list[int] = []
    case_results: list[dict[str, Any]] = []
    abstention_ok = 0
    abstention_total = 0
    ranked_case_metrics: list[dict[str, float | int | bool]] = []

    sorted_cases = sorted(manifest.cases, key=lambda item: (item.seed, item.query))
    for case in sorted_cases:
        relevant_rels = {_to_relation(doc_id) for doc_id in case.relevant}
        hard_negative_rels = {_to_relation(doc_id) for doc_id in case.hard_negatives}
        started = time.perf_counter_ns()
        results = score_bm25_query(
            corpus,
            case.query,
            limit=max(top_k, max(1, len(case.relevant) or 1)),
        )
        latencies_ns.append(time.perf_counter_ns() - started)
        retrieved = [rel for rel, _score in results]
        metrics = _rank_metrics(
            retrieved,
            relevant_rels=relevant_rels,
            hard_negative_rels=hard_negative_rels,
            stale_rels=stale_rels,
            top_k=top_k,
            has_reference=bool(relevant_rels),
            update_expected=case.gold_classification == "update_gold",
            abstention_expected=case.abstain_when_no_candidates,
        )
        if not relevant_rels and case.abstain_when_no_candidates:
            abstention_total += 1
            if metrics["abstained"]:
                abstention_ok += 1
        ranked_case_metrics.append(metrics)
        case_results.append(
            {
                "seed": case.seed,
                "query": case.query,
                "gold_classification": case.gold_classification,
                "retrieved_relations": retrieved[:top_k],
                "metrics": metrics,
            }
        )

    bootstrap_seed = sum(case.seed for case in sorted_cases)
    metrics_summary = _aggregate_rank_metrics(
        ranked_case_metrics,
        top_k=top_k,
        bootstrap_seed=bootstrap_seed,
        abstention_expected=abstention_total,
        abstention_passed=abstention_ok,
    )
    no_retrieval_metrics = _aggregate_rank_metrics(
        [
            _rank_metrics(
                [],
                relevant_rels={_to_relation(doc_id) for doc_id in case.relevant},
                hard_negative_rels={_to_relation(doc_id) for doc_id in case.hard_negatives},
                stale_rels=stale_rels,
                top_k=top_k,
                has_reference=bool(case.relevant),
                update_expected=case.gold_classification == "update_gold",
                abstention_expected=case.abstain_when_no_candidates,
            )
            for case in sorted_cases
        ],
        top_k=top_k,
        bootstrap_seed=bootstrap_seed + 100,
        abstention_expected=abstention_total,
        abstention_passed=abstention_total,
    )
    cache_stats = bm25_query_cache_stats(corpus)
    diagnostics = bm25_diagnostics_snapshot(corpus).to_dict()
    sorted_latencies = sorted(latencies_ns)
    payload_estimate_bytes = diagnostics["estimated_payload_bytes"]
    scorecard_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "case_count": len(manifest.cases),
                "case_results": case_results,
                "manifest_dataset_id": manifest.dataset_id,
                "manifest_schema_version": manifest.schema_version,
                "metrics": metrics_summary,
                "signal_ablations": {"no_retrieval": no_retrieval_metrics},
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return {
        "manifest_schema_version": manifest.schema_version,
        "case_count": len(manifest.cases),
        "manifest_dataset_id": manifest.dataset_id,
        "scorecard_fingerprint": scorecard_fingerprint,
        "case_results": case_results,
        "evaluation_scope": {
            "end_to_end_answer_evaluated": False,
            "retrieval_only": True,
        },
        "metrics": metrics_summary,
        "signal_ablations": {"no_retrieval": no_retrieval_metrics},
        "measurements": {
            "cache": cache_stats,
            "cache_hit_ratio": round(
                cache_stats["hits"] / (cache_stats["hits"] + cache_stats["misses"]),
                6,
            )
            if cache_stats["hits"] + cache_stats["misses"] > 0
            else 0.0,
            "latency_us": {
                "median": round(median(sorted_latencies) / 1_000, 3),
                "p50": round(_percentile(sorted_latencies, 0.50) / 1_000, 3),
                "p95": round(_percentile(sorted_latencies, 0.95) / 1_000, 3),
                "p99": round(_percentile(sorted_latencies, 0.99) / 1_000, 3),
            },
            "peak_rss_bytes": _peak_rss_bytes(),
            "payload_estimate_bytes": payload_estimate_bytes,
            "context_estimate_tokens": math.ceil(payload_estimate_bytes / 4),
            "context_token_estimator": "ceil(payload_estimate_bytes / 4)",
            "external_model_calls": 0,
            "estimated_model_cost_usd": 0.0,
            "model_cost_applicability": "not_applicable",
            "rss_end_bytes": _current_rss_bytes(),
            "requests": len(manifest.cases),
            "top_k": top_k,
            "query_cache_row_budget": cache_stats["result_row_capacity"],
        },
    }


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


def _percentile(sorted_values: Sequence[int | float], percentile: float) -> float:
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


def run_benchmark(
    config: BenchmarkConfig,
    *,
    manifest_path: Path | None = None,
    top_k: int | None = None,
) -> dict[str, Any]:
    original_capacity = generational_cache._DEFAULT_BM25_QUERY_CACHE_MAX_ENTRIES
    try:
        if manifest_path is not None:
            manifest, manifest_digest = _read_manifest(manifest_path)
            effective_top_k = manifest.top_k if top_k is None else top_k
            payload = _run_scorecard_benchmark(manifest, top_k=effective_top_k)
            return {
                "benchmark_schema_version": _SCORECARD_SCHEMA_VERSION,
                **payload,
                "manifest": {
                    "digest": manifest_digest,
                    "path": str(manifest_path),
                    "schema_version": manifest.schema_version,
                },
                "config": asdict(config),
                "environment": {
                    "corpus_digest": manifest_digest,
                    "machine": platform.machine(),
                    "manifest_schema_version": manifest.schema_version,
                    "os": platform.platform(),
                    "python": platform.python_version(),
                    "source_commit": _source_commit(),
                },
            }
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
    parser.add_argument("--manifest-path", type=Path)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    capacities = tuple(int(value) for value in args.capacities.split(","))
    if args.top_k is not None and args.top_k < 1:
        raise SystemExit("--top-k must be positive")
    if args.manifest_path is None and (
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
    rendered = json.dumps(
        run_benchmark(
            config,
            manifest_path=args.manifest_path,
            top_k=args.top_k,
        ),
        indent=2,
        sort_keys=True,
    )
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
