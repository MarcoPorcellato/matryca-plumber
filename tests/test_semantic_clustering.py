"""Structural tests for deterministic semantic clustering."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import TracebackType

import pytest
import scripts.bench_semantic_clustering_quality as clustering_benchmark
from src.graph.master_catalog import clear_master_catalog_cache
from src.graph.semantic_clustering import (
    LOUVAIN_MAX_ITERATIONS,
    _louvain_communities,
    _tokenize,
    compute_semantic_clusters,
    format_cluster_neighborhood,
    load_or_compute_semantic_clusters,
    load_semantic_clusters,
    save_semantic_clusters,
    semantic_clusters_path,
)


def _mock_catalog(page_count: int) -> dict[str, object]:
    """Build a synthetic catalog with topical neighborhoods."""
    topics = (
        "machine learning",
        "distributed systems",
        "graph databases",
        "note taking",
        "project management",
        "security engineering",
        "frontend react",
        "backend python",
        "devops kubernetes",
        "data pipelines",
    )
    pages: dict[str, dict[str, object]] = {}
    for index in range(page_count):
        topic = topics[index % len(topics)]
        variant = index // len(topics)
        title = f"{topic.replace(' ', '-').title()} Page {variant:03d}"
        pages[title] = {
            "summary": f"A focused note about {topic} pattern {variant % 7}.",
            "domain": "risorsa",
            "tags": [topic.split()[0], topic.split()[-1], f"batch-{variant % 5}"],
            "last_mtime": 1_700_000_000 + index,
            "orphan": False,
        }
    return {
        "version": 1,
        "updated_at": "2026-05-21T12:00:00+00:00",
        "pages": pages,
    }


def test_compute_semantic_clusters_partitions_catalog() -> None:
    catalog = _mock_catalog(120)
    clusters = compute_semantic_clusters(catalog, max_cluster_size=35)
    titles = [title for page_titles in clusters.values() for title in page_titles]
    assert len(titles) == 120
    assert len(set(titles)) == 120
    assert all(5 <= len(page_titles) <= 35 for page_titles in clusters.values())


def test_quality_scorecard_metrics_cover_perfect_and_collapsed_partitions() -> None:
    labels = {"A": 0, "B": 0, "C": 1, "D": 1}

    perfect = clustering_benchmark._quality(
        {"cluster_1": ["A", "B"], "cluster_2": ["C", "D"]}, labels
    )
    collapsed = clustering_benchmark._quality({"cluster_1": list(labels)}, labels)

    assert perfect["ari"] == 1.0
    assert perfect["cluster_count"] == 2
    assert perfect["collapse_rate"] == 0.0
    assert collapsed["ari"] == 0.0
    assert collapsed["cluster_count"] == 1
    assert collapsed["collapse_rate"] == 1.0


def test_quality_scorecard_metrics_are_stable_for_input_order_and_degenerate_cases() -> None:
    labels = {"A": 0, "B": 0, "C": 1, "D": 1}
    first = clustering_benchmark._quality(
        {"cluster_1": ["A", "B"], "cluster_2": ["C", "D"]}, labels
    )
    reordered = clustering_benchmark._quality(
        {"cluster_2": ["D", "C"], "cluster_1": ["B", "A"]},
        dict(reversed(labels.items())),
    )

    assert first == reordered
    assert clustering_benchmark._quality({"only": ["A"]}, {"A": 0}) == {
        "ari": 1.0,
        "cluster_count": 1,
        "collapse_rate": 0.0,
        "pair_f1": 0.0,
        "pair_precision": 0.0,
        "pair_recall": 0.0,
        "purity": 1.0,
    }
    assert clustering_benchmark._quality({}, {})["ari"] == 1.0


def test_quality_scorecard_metrics_cover_partial_and_crossed_partitions() -> None:
    labels = {"A": 0, "B": 0, "C": 1, "D": 1}
    partial = clustering_benchmark._quality(
        {"cluster_1": ["A", "B", "C"], "cluster_2": ["D"]}, labels
    )
    crossed = clustering_benchmark._quality(
        {"cluster_1": ["A", "C"], "cluster_2": ["B", "D"]}, labels
    )

    assert partial == {
        "ari": 0.0,
        "cluster_count": 2,
        "collapse_rate": 0.5,
        "pair_f1": 0.4,
        "pair_precision": 0.3333,
        "pair_recall": 0.5,
        "purity": 0.75,
    }
    assert crossed["ari"] == -0.5
    assert 0.0 <= partial["collapse_rate"] <= 1.0
    assert 0.0 <= crossed["collapse_rate"] <= 1.0


def test_scorecard_main_writes_schema_versioned_synthetic_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "nested" / "clustering.json"
    monkeypatch.setattr(clustering_benchmark, "_source_commit", lambda: "a" * 40)
    monkeypatch.setattr(clustering_benchmark, "_require_clean_source_tree", lambda: None)

    assert clustering_benchmark.main(["--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["benchmark_schema_version"] == 2
    assert payload["source_commit"] == "a" * 40
    assert payload["fixture"] == {
        "id": "semantic-clustering-balanced-opaque-v1",
        "kind": "synthetic",
        "provenance": "Generated in-memory by this benchmark from fixed opaque titles and labels.",
        "evidence_boundary": "No vault, model, or remote content is used or represented.",
    }
    assert payload["seeds"] == [20260802, 20260803, 20260804, 20260805, 20260806]
    assert set(payload["scenarios"]["summary_and_tags"]) >= {
        "ari_mean",
        "cluster_count_mean",
        "collapse_rate_mean",
    }


def test_scorecard_source_commit_is_resolved_from_the_repository_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="a" * 40)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert clustering_benchmark._source_commit() == "a" * 40
    assert captured["cwd"] == Path(clustering_benchmark.__file__).resolve().parents[1]


def test_scorecard_rejects_a_dirty_source_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout=" M script.py\n")

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(RuntimeError, match="dirty source tree"):
        clustering_benchmark._require_clean_source_tree()


def test_save_and_load_semantic_clusters(tmp_path: Path) -> None:
    clear_master_catalog_cache(tmp_path)
    clusters = {
        "cluster_001": ["Alpha", "Beta"],
        "cluster_002": ["Gamma", "Delta", "Epsilon"],
    }
    save_semantic_clusters(
        tmp_path,
        clusters,
        catalog_updated_at="2026-05-21T12:00:00+00:00",
    )
    path = semantic_clusters_path(tmp_path)
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["clusters"]["cluster_001"] == ["Alpha", "Beta"]
    loaded = load_semantic_clusters(tmp_path)
    assert loaded == clusters


def test_load_semantic_clusters_uses_json_flock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_master_catalog_cache(tmp_path)
    clusters = {"cluster_001": ["Alpha", "Beta"]}
    save_semantic_clusters(tmp_path, clusters)
    locked_paths: list[Path] = []

    class RecordingFlock:
        def __init__(self, path: Path, *, graph_root: Path) -> None:
            assert graph_root == tmp_path
            locked_paths.append(path)

        def __enter__(self) -> None:
            return None

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            _ = (exc_type, exc, traceback)

    monkeypatch.setattr(
        "src.graph.semantic_clustering.cross_process_json_read_flock",
        RecordingFlock,
    )

    loaded = load_semantic_clusters(tmp_path)

    assert loaded == clusters
    assert locked_paths == [semantic_clusters_path(tmp_path)]


def test_semantic_clusters_preserve_graph_in_read_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clusters = {"cluster_001": ["Alpha", "Beta"]}
    path = save_semantic_clusters(tmp_path, clusters)
    before = path.read_bytes()
    flock = path.parent / f".{path.name}.flock"
    flock.unlink(missing_ok=True)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    assert load_semantic_clusters(tmp_path) == clusters
    save_semantic_clusters(tmp_path, {"cluster_002": ["Gamma"]})

    assert path.read_bytes() == before
    assert not flock.exists()


def test_load_or_compute_semantic_clusters_uses_cache(tmp_path: Path) -> None:
    clear_master_catalog_cache(tmp_path)
    catalog = _mock_catalog(40)
    cache_dir = tmp_path / ".matryca_semantic_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "master_catalog.json").write_text(
        json.dumps(catalog, indent=2),
        encoding="utf-8",
    )

    first = load_or_compute_semantic_clusters(tmp_path, max_cluster_size=35)
    second = load_or_compute_semantic_clusters(tmp_path, max_cluster_size=35)
    assert first == second
    assert semantic_clusters_path(tmp_path).is_file()


def test_load_or_compute_force_recompute(tmp_path: Path) -> None:
    clear_master_catalog_cache(tmp_path)
    catalog = _mock_catalog(25)
    pages = catalog["pages"]
    assert isinstance(pages, dict)
    save_semantic_clusters(
        tmp_path,
        {"cluster_001": list(pages.keys())[:25]},
        catalog_updated_at="stale",
    )
    recomputed = load_or_compute_semantic_clusters(
        tmp_path,
        catalog_data=catalog,
        force_recompute=True,
    )
    assert len(recomputed) >= 1
    assert sum(len(titles) for titles in recomputed.values()) == 25


def test_empty_catalog_returns_empty_clusters() -> None:
    assert compute_semantic_clusters({"pages": {}}) == {}


def test_compute_semantic_clusters_excludes_journal_titles(tmp_path: Path) -> None:
    clear_master_catalog_cache(tmp_path)
    pages_dir = tmp_path / "pages"
    journals_dir = tmp_path / "journals"
    pages_dir.mkdir(parents=True)
    journals_dir.mkdir(parents=True)
    (pages_dir / "Redis.md").write_text("- redis note\n", encoding="utf-8")
    (pages_dir / "Caching.md").write_text("- cache note\n", encoding="utf-8")
    (journals_dir / "2026_06_05.md").write_text("- daily\n", encoding="utf-8")
    (journals_dir / "2026_06_06.md").write_text("- daily\n", encoding="utf-8")

    catalog: dict[str, object] = {
        "pages": {
            "Redis": {
                "summary": "Redis architecture overview",
                "tags": ["redis", "cache"],
            },
            "Caching": {
                "summary": "Redis cache eviction policy",
                "tags": ["redis", "cache"],
            },
            "2026_06_05": {
                "summary": "Daily journal for June 5",
                "tags": ["journal"],
            },
            "2026_06_06": {
                "summary": "Daily journal for June 6",
                "tags": ["journal"],
            },
        },
    }
    clusters = compute_semantic_clusters(catalog, graph_root=tmp_path, min_cluster_size=2)
    clustered_titles = {title for titles in clusters.values() for title in titles}
    assert "2026_06_05" not in clustered_titles
    assert "2026_06_06" not in clustered_titles
    assert clustered_titles <= {"Redis", "Caching"}


def test_tokenize_filters_structural_stopwords() -> None:
    tokens = _tokenize("Questa pagina Logseq descrive Redis caching")
    assert "questa" not in tokens
    assert "pagina" not in tokens
    assert "logseq" not in tokens
    assert "redis" in tokens
    assert "caching" in tokens


def test_louvain_communities_respects_iteration_ceiling() -> None:
    adjacency = {
        "a": {"b": 1.0, "c": 1.0},
        "b": {"a": 1.0, "c": 1.0},
        "c": {"a": 1.0, "b": 1.0},
    }
    assignments = _louvain_communities(adjacency, max_iterations=LOUVAIN_MAX_ITERATIONS)
    assert set(assignments) == {"a", "b", "c"}


def test_louvain_communities_zero_weight_graph_returns_flat_assignment() -> None:
    adjacency: dict[str, dict[str, float]] = {"alpha": {}, "beta": {}, "gamma": {}}
    assignments = _louvain_communities(adjacency)
    assert assignments == {"alpha": 0, "beta": 1, "gamma": 2}


def test_format_cluster_neighborhood_marks_hub_anchor() -> None:
    catalog: dict[str, object] = {
        "pages": {
            "Alpha": {
                "summary": "Core redis architecture overview",
                "tags": ["redis", "core"],
            },
            "Beta": {
                "summary": "Redis cache eviction policy",
                "tags": ["redis", "cache"],
            },
            "Gamma": {
                "summary": "Unrelated kubernetes scheduling note",
                "tags": ["kubernetes", "ops"],
            },
        },
    }
    rendered = format_cluster_neighborhood(catalog, ["Alpha", "Beta", "Gamma"])
    assert "[CLUSTER FOCUS ANCHOR NODE]" in rendered
    assert rendered.count("[CLUSTER FOCUS ANCHOR NODE]") == 1


def test_format_cluster_neighborhood_disconnected_cluster_does_not_crash() -> None:
    catalog: dict[str, object] = {
        "pages": {
            "Solo A": {"summary": "Unique topic alpha", "tags": ["alpha"]},
            "Solo B": {"summary": "Unique topic beta", "tags": ["beta"]},
            "Solo C": {"summary": "Unique topic gamma", "tags": ["gamma"]},
        },
    }
    rendered = format_cluster_neighborhood(catalog, ["Solo A", "Solo B", "Solo C"])
    assert "Solo A" in rendered
    assert "Solo B" in rendered
    assert "Solo C" in rendered
    assert rendered.count("[CLUSTER FOCUS ANCHOR NODE]") <= 1
