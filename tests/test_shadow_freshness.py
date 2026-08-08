"""Requested-row freshness invariants when watcher reconciliation is absent."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from src.agent.shadow_graph_repository import ShadowGraphRepository
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.fts_format import resolve_bm25_search_markdown

BLOCK_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_WARM_P95_BUDGET_S = 0.250
_WARM_P99_BUDGET_S = 0.500


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _ready_graph(tmp_path: Path) -> tuple[Path, Path]:
    graph = tmp_path / "graph"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    page = pages / "Port.md"
    page.write_text(
        f"- oldtoken root\n  id:: {BLOCK_UUID}\n  - old child\n",
        encoding="utf-8",
    )
    rebuild_shadow_from_graph(graph)
    return graph, page


def _subtree(page: str = "Port") -> str:
    return json.dumps({"page": page, "block_uuid": BLOCK_UUID})


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    rank = (len(ordered) - 1) * fraction
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def test_subtree_edit_falls_back_to_current_markdown(tmp_path: Path) -> None:
    graph, page = _ready_graph(tmp_path)
    page.write_text(
        f"- newtoken root\n  id:: {BLOCK_UUID}\n  - current child\n",
        encoding="utf-8",
    )

    output = ShadowGraphRepository().read_subtree_markdown(graph, _subtree())

    assert "current child" in output
    assert "old child" not in output
    assert "`source_changed`" in output


def test_subtree_delete_and_rename_fail_closed(tmp_path: Path) -> None:
    graph, page = _ready_graph(tmp_path)
    renamed = page.with_name("Renamed.md")
    page.rename(renamed)

    renamed_output = ShadowGraphRepository().read_subtree_markdown(graph, _subtree("Renamed"))
    assert "old child" in renamed_output
    assert "`page_untracked`" in renamed_output

    renamed.unlink()
    deleted_output = ShadowGraphRepository().read_subtree_markdown(graph, _subtree())
    assert "`source_missing`" in deleted_output


def test_fts_edit_validates_hits_and_unproven_empty_results(tmp_path: Path) -> None:
    graph, page = _ready_graph(tmp_path)
    page.write_text(
        f"- newtoken root\n  id:: {BLOCK_UUID}\n  - current child\n",
        encoding="utf-8",
    )

    old_output = resolve_bm25_search_markdown(graph, "oldtoken")
    new_output = resolve_bm25_search_markdown(graph, "newtoken")

    assert "`source_changed`" in old_output
    assert "block `" not in old_output
    assert "Port.md" in new_output
    assert "`empty_result_unproven`" in new_output


def test_fts_delete_and_rename_return_current_results(tmp_path: Path) -> None:
    graph, page = _ready_graph(tmp_path)
    renamed = page.with_name("Renamed.md")
    page.rename(renamed)

    renamed_output = resolve_bm25_search_markdown(graph, "oldtoken")
    assert "Renamed.md" in renamed_output
    assert "`source_missing`" in renamed_output

    renamed.unlink()
    deleted_output = resolve_bm25_search_markdown(graph, "oldtoken")
    assert "Renamed.md" not in deleted_output
    assert "`source_missing`" in deleted_output


def test_fresh_shadow_hit_does_not_scan_the_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, _page = _ready_graph(tmp_path)
    monkeypatch.setattr(
        Path,
        "rglob",
        lambda *_args, **_kwargs: pytest.fail("freshness must not scan the full graph"),
    )

    output = resolve_bm25_search_markdown(graph, "oldtoken")

    assert "block `" in output
    assert "Shadow fallback" not in output


def test_warm_shadow_reads_keep_freshness_tail_latency_bounded(tmp_path: Path) -> None:
    graph, _page = _ready_graph(tmp_path)
    repository = ShadowGraphRepository()
    query = _subtree()

    for _ in range(10):
        assert "Shadow fallback" not in repository.read_subtree_markdown(graph, query)
        assert "Shadow fallback" not in resolve_bm25_search_markdown(graph, "oldtoken")

    samples: list[float] = []
    for _ in range(80):
        started = time.perf_counter()
        repository.read_subtree_markdown(graph, query)
        samples.append(time.perf_counter() - started)

        started = time.perf_counter()
        resolve_bm25_search_markdown(graph, "oldtoken")
        samples.append(time.perf_counter() - started)

    p95 = _percentile(samples, 0.95)
    p99 = _percentile(samples, 0.99)
    assert p95 < _WARM_P95_BUDGET_S, f"warm Shadow p95={p95:.6f}s"
    assert p99 < _WARM_P99_BUDGET_S, f"warm Shadow p99={p99:.6f}s"
