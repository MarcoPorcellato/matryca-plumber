"""Tests for the deterministic semantic-clustering quality scorecard."""

from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Any

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


def test_quality_reports_partial_and_crossed_partition_metrics() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}

    partial = _quality({"one": ["a", "b", "c"], "two": ["d"]}, labels)
    crossed = _quality({"one": ["a", "c"], "two": ["b", "d"]}, labels)

    assert partial["collapse_rate"] == 0.5
    assert crossed["adjusted_rand_index"] == -0.5


def test_quality_is_deterministic_for_reordered_and_degenerate_inputs() -> None:
    labels = {"a": 0, "b": 0, "c": 1, "d": 1}
    first = _quality({"one": ["a", "b"], "two": ["c", "d"]}, labels)
    reordered = _quality({"two": ["d", "c"], "one": ["b", "a"]}, dict(reversed(labels.items())))

    assert first == reordered
    assert _quality({"only": ["a"]}, {"a": 0})["collapse_rate"] == 0.0
    assert _quality({}, {}) == {
        "pair_f1": 0.0,
        "pair_precision": 0.0,
        "pair_recall": 0.0,
        "purity": 1.0,
        "adjusted_rand_index": 1.0,
        "predicted_cluster_count": 0,
        "expected_cluster_count": 0,
        "largest_cluster_fraction": 0.0,
        "collapse_detected": False,
        "collapse_rate": 0.0,
    }


def test_scorecard_main_writes_versioned_fixture_and_source_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    output = tmp_path / "nested" / "clustering.json"
    monkeypatch.setattr(benchmark, "_source_commit", lambda: "a" * 40)
    monkeypatch.setattr(benchmark, "_require_clean_source_tree", lambda: None)

    assert benchmark.main(["--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["benchmark_schema_version"] == 2
    assert payload["source_commit"] == "a" * 40
    assert payload["fixture"]["id"] == "semantic-clustering-balanced-opaque-v1"
    assert "collapse_rate_mean" in payload["scenarios"]["summary_and_tags"]
    assert set(
        payload["scenarios"]["summary_and_tags"]["bootstrap_confidence_intervals"]["collapse_rate"]
    ) == {"lower", "upper"}
    assert output.read_bytes().endswith(b"\n")
    assert output.read_text(encoding="utf-8") == json.dumps(payload, sort_keys=True) + "\n"


def test_scorecard_stdout_skips_git_helpers_and_keeps_compact_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    def fail_if_called() -> str:
        raise AssertionError("stdout mode must not inspect Git provenance")

    monkeypatch.setattr(benchmark, "_source_commit", fail_if_called)
    monkeypatch.setattr(benchmark, "_require_clean_source_tree", fail_if_called)

    assert benchmark.main([]) == 0

    output = capsys.readouterr().out
    assert output.endswith("\n")
    assert '\n  "' not in output
    payload = json.loads(output)
    assert "benchmark_schema_version" not in payload
    assert "fixture" not in payload
    assert "source_commit" not in payload
    assert "collapse_rate_mean" in payload["scenarios"]["summary_and_tags"]
    assert output == json.dumps(payload, sort_keys=True) + "\n"


def test_scorecard_artifact_preserves_preexisting_destination(tmp_path: Path) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    output = tmp_path / "scorecard.json"
    output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        benchmark._write_artifact(output, "replacement\n")

    assert output.read_text(encoding="utf-8") == "existing\n"


def test_scorecard_artifact_rejects_symlink_destination(tmp_path: Path) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    target = tmp_path / "target.json"
    target.write_text("target\n", encoding="utf-8")
    output = tmp_path / "scorecard.json"
    output.symlink_to(target)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        benchmark._write_artifact(output, "replacement\n")

    assert target.read_text(encoding="utf-8") == "target\n"


def test_scorecard_artifact_cleans_temporary_file_on_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    output = tmp_path / "scorecard.json"

    def fail_link(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated publication failure")

    monkeypatch.setattr(os, "link", fail_link)

    with pytest.raises(OSError, match="simulated publication failure"):
        benchmark._write_artifact(output, "payload\n")

    assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_scorecard_artifact_cleans_temporary_file_on_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    output = tmp_path / "scorecard.json"
    real_named_temporary_file = tempfile.NamedTemporaryFile

    def failing_named_temporary_file(*args: Any, **kwargs: Any) -> Any:
        handle = real_named_temporary_file(*args, **kwargs)

        class FailingWriter:
            name = handle.name

            def __enter__(self) -> FailingWriter:
                handle.__enter__()
                return self

            def __exit__(self, *_exit_args: object) -> None:
                handle.close()

            def write(self, _value: str) -> int:
                raise OSError("simulated write failure")

        return FailingWriter()

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", failing_named_temporary_file)

    with pytest.raises(OSError, match="simulated write failure"):
        benchmark._write_artifact(output, "payload\n")

    assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_scorecard_rejects_dirty_source_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.bench_semantic_clustering_quality as benchmark

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=" M script.py\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="dirty source tree"):
        benchmark._require_clean_source_tree()


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
