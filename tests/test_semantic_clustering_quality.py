"""Tests for the deterministic semantic-clustering quality scorecard."""

from __future__ import annotations

import random

import pytest
from scripts.bench_semantic_clustering_quality import (
    _adjusted_rand_index,
    _bootstrap_confidence_interval,
    _quality,
)


def test_adjusted_rand_index_is_one_for_identical_partitions() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}
    clusters = {"cluster_1": ["a", "b"], "cluster_2": ["c", "d"]}

    assert _adjusted_rand_index(clusters, labels) == 1.0


def test_adjusted_rand_index_is_zero_for_total_collapse() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}
    clusters = {"cluster_1": ["a", "b", "c", "d"]}

    assert _adjusted_rand_index(clusters, labels) == 0.0


def test_quality_reports_counts_and_partial_collapse() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}
    clusters = {"cluster_1": ["a", "b", "c"], "cluster_2": ["d"]}

    quality = _quality(clusters, labels)

    assert quality["pair_recall"] == 0.5
    assert quality["predicted_cluster_count"] == 2
    assert quality["expected_cluster_count"] == 2
    assert quality["largest_cluster_fraction"] == 0.75
    assert quality["collapse_detected"] is False


def test_quality_detects_total_collapse() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}
    clusters = {"cluster_1": ["a", "b", "c", "d"]}

    quality = _quality(clusters, labels)

    assert quality["predicted_cluster_count"] == 1
    assert quality["largest_cluster_fraction"] == 1.0
    assert quality["collapse_detected"] is True


def test_bootstrap_confidence_interval_is_reproducible() -> None:
    samples = [0.2, 0.4, 0.6, 0.8, 1.0]

    first = _bootstrap_confidence_interval(
        samples,
        rng=random.Random(20260810),
        iterations=128,
    )
    second = _bootstrap_confidence_interval(
        samples,
        rng=random.Random(20260810),
        iterations=128,
    )

    assert first == second
    assert first[0] <= 0.6 <= first[1]


@pytest.mark.parametrize("samples", [[], [1.0]])
def test_bootstrap_confidence_interval_validates_samples(samples: list[float]) -> None:
    if samples:
        assert _bootstrap_confidence_interval(
            samples,
            rng=random.Random(1),
            iterations=1,
        ) == (1.0, 1.0)
    else:
        with pytest.raises(ValueError, match="at least one sample"):
            _bootstrap_confidence_interval(samples, rng=random.Random(1))
