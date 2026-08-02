"""Evaluate deterministic semantic clustering on labelled synthetic catalogs."""

from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter
from typing import Any

from src.graph.semantic_clustering import compute_semantic_clusters

_SEEDS = (20260802, 20260803, 20260804, 20260805, 20260806)
_TOPICS = 12
_PAGES_PER_TOPIC = 24
_MAX_CLUSTER_SIZE = 32


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


def _quality(clusters: dict[str, list[str]], labels: dict[str, int]) -> dict[str, float]:
    predicted_pairs = 0
    true_positive_pairs = 0
    purity_hits = 0
    for members in clusters.values():
        counts = Counter(labels[title] for title in members)
        purity_hits += max(counts.values(), default=0)
        predicted_pairs += math.comb(len(members), 2)
        true_positive_pairs += sum(math.comb(count, 2) for count in counts.values())
    true_pairs = _TOPICS * math.comb(_PAGES_PER_TOPIC, 2)
    precision = true_positive_pairs / predicted_pairs if predicted_pairs else 0.0
    recall = true_positive_pairs / true_pairs if true_pairs else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "pair_f1": round(f1, 4),
        "pair_precision": round(precision, 4),
        "pair_recall": round(recall, 4),
        "purity": round(purity_hits / len(labels), 4),
    }


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _run_scenario(scenario: str) -> dict[str, Any]:
    runs: list[dict[str, float]] = []
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
    }


def main() -> None:
    scenarios = ("summary_and_tags", "summary_only", "tags_only", "no_features")
    payload = {
        "max_cluster_size": _MAX_CLUSTER_SIZE,
        "pages": _TOPICS * _PAGES_PER_TOPIC,
        "pages_per_topic": _PAGES_PER_TOPIC,
        "scenarios": {scenario: _run_scenario(scenario) for scenario in scenarios},
        "seeds": list(_SEEDS),
        "topics": _TOPICS,
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
