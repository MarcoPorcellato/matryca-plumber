"""Evaluate deterministic semantic clustering on labelled synthetic catalogs."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import subprocess
import time
from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict

from src.graph.semantic_clustering import compute_semantic_clusters

_SEEDS = (20260802, 20260803, 20260804, 20260805, 20260806)
_TOPICS = 12
_PAGES_PER_TOPIC = 24
_MAX_CLUSTER_SIZE = 32
_BENCHMARK_SCHEMA_VERSION = 2
_FIXTURE_ID = "semantic-clustering-balanced-opaque-v1"


class QualityScores(TypedDict):
    """Deterministic quality measures for one clustering partition."""

    ari: float
    cluster_count: int
    collapse_rate: float
    pair_f1: float
    pair_precision: float
    pair_recall: float
    purity: float


def _opaque_title(seed: int, topic: int, page: int) -> str:
    digest = hashlib.sha256(f"{seed}:{topic}:{page}".encode()).hexdigest()[:12]
    return f"Note-{digest}"


def _catalog(seed: int, scenario: str) -> tuple[dict[str, Any], dict[str, int]]:
    rng = random.Random(seed)
    pages: list[tuple[str, dict[str, Any], int]] = []
    for topic in range(_TOPICS):
        for page in range(_PAGES_PER_TOPIC):
            title = _opaque_title(seed, topic, page)
            lexical = (
                f"subject{topic} concept{topic} pattern{topic} shared noise{rng.randrange(31)}"
            )
            tags = [f"domain-{topic % 3}", f"subject-{topic}"]
            pages.append(
                (
                    title,
                    {
                        "summary": lexical
                        if scenario in {"summary_only", "summary_and_tags"}
                        else "",
                        "domain": f"domain-{topic % 3}",
                        "tags": tags if scenario in {"tags_only", "summary_and_tags"} else [],
                        "last_mtime": page,
                    },
                    topic,
                )
            )
    rng.shuffle(pages)
    return (
        {
            "version": 1,
            "updated_at": f"synthetic-{seed}",
            "pages": {title: record for title, record, _topic in pages},
        },
        {title: topic for title, _record, topic in pages},
    )


def _canonical(clusters: dict[str, list[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(sorted(tuple(sorted(members)) for members in clusters.values()))


def _quality(clusters: dict[str, list[str]], labels: dict[str, int]) -> QualityScores:
    predicted_pairs = 0
    true_positive_pairs = 0
    purity_hits = 0
    for members in clusters.values():
        counts = Counter(labels[title] for title in members)
        purity_hits += max(counts.values(), default=0)
        predicted_pairs += math.comb(len(members), 2)
        true_positive_pairs += sum(math.comb(count, 2) for count in counts.values())
    label_sizes = Counter(labels.values())
    true_pairs = sum(math.comb(size, 2) for size in label_sizes.values())
    precision = true_positive_pairs / predicted_pairs if predicted_pairs else 0.0
    recall = true_positive_pairs / true_pairs if true_pairs else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    cluster_sizes = [len(members) for members in clusters.values()]
    predicted_cluster_pairs = sum(math.comb(size, 2) for size in cluster_sizes)
    label_pairs = sum(math.comb(size, 2) for size in label_sizes.values())
    total_pairs = math.comb(len(labels), 2)
    expected_index = predicted_cluster_pairs * label_pairs / total_pairs if total_pairs else 0.0
    maximum_index = (predicted_cluster_pairs + label_pairs) / 2.0
    ari_denominator = maximum_index - expected_index
    if ari_denominator:
        adjusted_rand = (true_positive_pairs - expected_index) / ari_denominator
    else:
        predicted_partition = _canonical(clusters)
        true_partition = _canonical(
            {
                str(label): [title for title, value in labels.items() if value == label]
                for label in label_sizes
            }
        )
        adjusted_rand = 1.0 if predicted_partition == true_partition else 0.0
    largest_cluster_size = max(cluster_sizes, default=0)
    nominal_cluster_size = len(labels) / len(label_sizes) if label_sizes else 0.0
    collapse_denominator = len(labels) - nominal_cluster_size
    collapse_rate = (
        max(0.0, (largest_cluster_size - nominal_cluster_size) / collapse_denominator)
        if collapse_denominator > 0
        else 0.0
    )
    return {
        "ari": round(adjusted_rand, 4),
        "cluster_count": len(cluster_sizes),
        "collapse_rate": round(collapse_rate, 4),
        "pair_f1": round(f1, 4),
        "pair_precision": round(precision, 4),
        "pair_recall": round(recall, 4),
        "purity": round(purity_hits / len(labels), 4) if labels else 0.0,
    }


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _run_scenario(scenario: str) -> dict[str, Any]:
    runs: list[QualityScores] = []
    latencies: list[float] = []
    deterministic = True
    for seed in _SEEDS:
        catalog, labels = _catalog(seed, scenario)
        started = time.perf_counter()
        clusters = compute_semantic_clusters(catalog, max_cluster_size=_MAX_CLUSTER_SIZE)
        latencies.append(time.perf_counter() - started)
        runs.append(_quality(clusters, labels))

        reversed_catalog = dict(catalog)
        reversed_catalog["pages"] = dict(reversed(list(catalog["pages"].items())))
        replay = compute_semantic_clusters(reversed_catalog, max_cluster_size=_MAX_CLUSTER_SIZE)
        deterministic = deterministic and _canonical(clusters) == _canonical(replay)

    return {
        "deterministic_across_input_order": deterministic,
        "latency_p50_seconds": round(statistics.median(latencies), 6),
        "latency_p95_seconds": round(_percentile(latencies, 0.95), 6),
        "pair_f1_mean": round(statistics.mean(run["pair_f1"] for run in runs), 4),
        "pair_precision_mean": round(statistics.mean(run["pair_precision"] for run in runs), 4),
        "pair_recall_mean": round(statistics.mean(run["pair_recall"] for run in runs), 4),
        "purity_mean": round(statistics.mean(run["purity"] for run in runs), 4),
        "ari_mean": round(statistics.mean(run["ari"] for run in runs), 4),
        "cluster_count_mean": round(statistics.mean(run["cluster_count"] for run in runs), 4),
        "collapse_rate_mean": round(statistics.mean(run["collapse_rate"] for run in runs), 4),
    }


def _parser() -> ArgumentParser:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    return parser


def _source_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("unable to determine benchmark source commit") from exc
    commit = completed.stdout.strip()
    if not commit:
        raise RuntimeError("git rev-parse HEAD returned an empty source commit")
    return commit


def _require_clean_source_tree() -> None:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("unable to determine benchmark source-tree cleanliness") from exc
    if completed.stdout:
        raise RuntimeError("refusing to write benchmark artifact from a dirty source tree")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _require_clean_source_tree()
    scenarios = ("summary_and_tags", "summary_only", "tags_only", "no_features")
    payload = {
        "benchmark_schema_version": _BENCHMARK_SCHEMA_VERSION,
        "source_commit": _source_commit(),
        "fixture": {
            "id": _FIXTURE_ID,
            "kind": "synthetic",
            "provenance": (
                "Generated in-memory by this benchmark from fixed opaque titles and labels."
            ),
            "evidence_boundary": "No vault, model, or remote content is used or represented.",
        },
        "max_cluster_size": _MAX_CLUSTER_SIZE,
        "pages": _TOPICS * _PAGES_PER_TOPIC,
        "pages_per_topic": _PAGES_PER_TOPIC,
        "scenarios": {scenario: _run_scenario(scenario) for scenario in scenarios},
        "seeds": list(_SEEDS),
        "topics": _TOPICS,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
