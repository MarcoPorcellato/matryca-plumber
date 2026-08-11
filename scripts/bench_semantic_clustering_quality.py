"""Evaluate deterministic semantic clustering on labelled synthetic catalogs."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import tempfile
import time
from argparse import ArgumentParser
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Any

from src.graph.semantic_clustering import compute_semantic_clusters

_SEEDS = (20260802, 20260803, 20260804, 20260805, 20260806)
_TOPICS = 12
_PAGES_PER_TOPIC = 24
_MAX_CLUSTER_SIZE = 32
_BOOTSTRAP_ITERATIONS = 2_048
_BOOTSTRAP_SEED = 20260810
_BENCHMARK_SCHEMA_VERSION = 2
_FIXTURE_ID = "semantic-clustering-balanced-opaque-v1"


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


def _adjusted_rand_index(
    clusters: dict[str, list[str]],
    labels: dict[str, int],
) -> float:
    """Return the adjusted Rand index from predicted and reference partitions."""
    predicted_by_title = {
        title: cluster_id for cluster_id, members in clusters.items() for title in members
    }
    if set(predicted_by_title) != set(labels):
        raise ValueError("predicted and reference partitions must cover the same titles")

    contingency: Counter[tuple[int, str]] = Counter(
        (label, predicted_by_title[title]) for title, label in labels.items()
    )
    reference_totals = Counter(labels.values())
    predicted_totals = Counter(predicted_by_title.values())
    pair_count = math.comb(len(labels), 2)
    sum_contingency_pairs = sum(math.comb(count, 2) for count in contingency.values())
    sum_reference_pairs = sum(math.comb(count, 2) for count in reference_totals.values())
    sum_predicted_pairs = sum(math.comb(count, 2) for count in predicted_totals.values())
    if pair_count == 0:
        return 1.0

    expected_index = sum_reference_pairs * sum_predicted_pairs / pair_count
    maximum_index = (sum_reference_pairs + sum_predicted_pairs) / 2.0
    denominator = maximum_index - expected_index
    if denominator == 0.0:
        return 1.0 if sum_contingency_pairs == maximum_index else 0.0
    return (sum_contingency_pairs - expected_index) / denominator


def _quality(
    clusters: dict[str, list[str]],
    labels: dict[str, int],
) -> dict[str, float | int | bool]:
    predicted_pairs = 0
    true_positive_pairs = 0
    purity_hits = 0
    for members in clusters.values():
        counts = Counter(labels[title] for title in members)
        purity_hits += max(counts.values(), default=0)
        predicted_pairs += math.comb(len(members), 2)
        true_positive_pairs += sum(math.comb(count, 2) for count in counts.values())
    true_pairs = sum(math.comb(count, 2) for count in Counter(labels.values()).values())
    precision = true_positive_pairs / predicted_pairs if predicted_pairs else 0.0
    recall = true_positive_pairs / true_pairs if true_pairs else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    largest_cluster_fraction = (
        max((len(members) for members in clusters.values()), default=0) / len(labels)
        if labels
        else 0.0
    )
    label_count = len(set(labels.values()))
    nominal_cluster_size = len(labels) / label_count if label_count else 0.0
    collapse_denominator = len(labels) - nominal_cluster_size
    largest_cluster_size = max((len(members) for members in clusters.values()), default=0)
    collapse_rate = (
        max(0.0, (largest_cluster_size - nominal_cluster_size) / collapse_denominator)
        if collapse_denominator > 0
        else 0.0
    )
    return {
        "pair_f1": round(f1, 4),
        "pair_precision": round(precision, 4),
        "pair_recall": round(recall, 4),
        "purity": round(purity_hits / len(labels), 4) if labels else 1.0,
        "adjusted_rand_index": round(_adjusted_rand_index(clusters, labels), 4),
        "predicted_cluster_count": len(clusters),
        "expected_cluster_count": len(set(labels.values())),
        "largest_cluster_fraction": round(largest_cluster_fraction, 4),
        "collapse_detected": len(clusters) <= 1 and bool(labels),
        "collapse_rate": round(collapse_rate, 4),
    }


def _percentile(samples: list[float], percentile: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _bootstrap_confidence_interval(
    samples: list[float],
    *,
    rng: random.Random,
    iterations: int = _BOOTSTRAP_ITERATIONS,
) -> tuple[float, float]:
    """Return a deterministic percentile bootstrap interval for a sample mean."""
    if not samples:
        raise ValueError("bootstrap confidence intervals require at least one sample")
    if iterations < 1:
        raise ValueError("bootstrap confidence intervals require a positive iteration count")
    means = [statistics.mean(rng.choice(samples) for _ in samples) for _ in range(iterations)]
    return (
        round(_percentile(means, 0.025), 4),
        round(_percentile(means, 0.975), 4),
    )


def _run_scenario(scenario: str) -> dict[str, Any]:
    runs: list[dict[str, float | int | bool]] = []
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

    aggregate_metrics = (
        "pair_f1",
        "pair_precision",
        "pair_recall",
        "purity",
        "adjusted_rand_index",
        "predicted_cluster_count",
        "expected_cluster_count",
        "largest_cluster_fraction",
        "collapse_rate",
    )
    bootstrap_rng = random.Random(_BOOTSTRAP_SEED)
    bootstrap_confidence_intervals = {}
    for metric in aggregate_metrics:
        interval = _bootstrap_confidence_interval(
            [float(run[metric]) for run in runs],
            rng=bootstrap_rng,
        )
        bootstrap_confidence_intervals[metric] = {
            "lower": interval[0],
            "upper": interval[1],
        }

    return {
        "deterministic_across_input_order": deterministic,
        "latency_p50_seconds": round(statistics.median(latencies), 6),
        "latency_p95_seconds": round(_percentile(latencies, 0.95), 6),
        "pair_f1_mean": round(statistics.mean(run["pair_f1"] for run in runs), 4),
        "pair_precision_mean": round(statistics.mean(run["pair_precision"] for run in runs), 4),
        "pair_recall_mean": round(statistics.mean(run["pair_recall"] for run in runs), 4),
        "purity_mean": round(statistics.mean(run["purity"] for run in runs), 4),
        "adjusted_rand_index_mean": round(
            statistics.mean(float(run["adjusted_rand_index"]) for run in runs), 4
        ),
        "predicted_cluster_count_mean": round(
            statistics.mean(float(run["predicted_cluster_count"]) for run in runs), 4
        ),
        "expected_cluster_count": int(runs[0]["expected_cluster_count"]),
        "largest_cluster_fraction_mean": round(
            statistics.mean(float(run["largest_cluster_fraction"]) for run in runs), 4
        ),
        "collapse_rate_mean": round(
            statistics.mean(float(run["collapse_rate"]) for run in runs), 4
        ),
        "collapse_detected": any(bool(run["collapse_detected"]) for run in runs),
        "bootstrap_confidence_intervals": bootstrap_confidence_intervals,
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


def _write_artifact(path: Path, rendered: str) -> None:
    """Publish a complete scorecard without replacing an existing destination."""
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite scorecard artifact: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())

        # A hard-link publication is atomic and fails if another writer won the
        # destination race; unlike os.replace, it cannot overwrite an artifact.
        os.link(temporary_path, path)
        temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            with suppress(FileNotFoundError):
                temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scenarios = ("summary_and_tags", "summary_only", "tags_only", "no_features")
    payload = {
        "max_cluster_size": _MAX_CLUSTER_SIZE,
        "pages": _TOPICS * _PAGES_PER_TOPIC,
        "pages_per_topic": _PAGES_PER_TOPIC,
        "scenarios": {scenario: _run_scenario(scenario) for scenario in scenarios},
        "seeds": list(_SEEDS),
        "topics": _TOPICS,
    }
    if args.output is None:
        print(json.dumps(payload, sort_keys=True))
    else:
        _require_clean_source_tree()
        artifact_payload = {
            **payload,
            "benchmark_schema_version": _BENCHMARK_SCHEMA_VERSION,
            "fixture": {
                "id": _FIXTURE_ID,
                "kind": "synthetic",
                "provenance": (
                    "Generated in-memory by this benchmark from fixed opaque titles and labels."
                ),
                "evidence_boundary": "No vault, model, or remote content is used or represented.",
            },
            "source_commit": _source_commit(),
        }
        _write_artifact(args.output, json.dumps(artifact_payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
