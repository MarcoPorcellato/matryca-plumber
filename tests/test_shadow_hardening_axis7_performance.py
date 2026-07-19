"""v2.0-alpha hardening — Axis 7: Performance (audit probes).

Read-only on ``src/`` — temporary vault fixtures measure shadow bootstrap,
FTS/CTE latency envelopes, memory growth, lock hold, and watcher burst cost.
Findings feed tracking issue #261.

Soft upper bounds only (not micro-benchmarks). ``@pytest.mark.slow`` covers
10k+ block scales excluded from default CI.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import statistics
import time
import tracemalloc
from pathlib import Path

import pytest
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.fts_format import resolve_bm25_search_markdown
from src.shadow.meta import META_LAST_FULL_SYNC_COMPLETED, get_meta
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid
from src.shadow.sync import sync_page_to_shadow

# Generous CI ceilings — catch pathological regressions, not jitter.
_BOOT_1K_MAX_S = 45.0
_BOOT_10K_MAX_S = 180.0
_BOOT_50K_MAX_S = 600.0
_FTS_P95_MAX_S = 2.0
_CTE_P95_MAX_S = 2.0
_LOCK_HOLD_MAX_S = 5.0
_WATCH_BURST_MAX_S = 30.0
_RSS_GROWTH_MB_MAX = 200.0


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _uuid(slot: int) -> str:
    head = f"{slot:08x}"
    return f"{head}-{head[:4]}-4111-8111-{slot:012x}"


def _seed_block_pages(graph: Path, *, pages: int, blocks_per_page: int) -> list[str]:
    """Write ``pages`` files with ``blocks_per_page`` sibling blocks each; return root UUIDs."""
    roots: list[str] = []
    slot = 1
    for page_idx in range(pages):
        parts: list[str] = []
        root = _uuid(slot)
        slot += 1
        roots.append(root)
        parts.append(f"- root-{page_idx}\n  id:: {root}\n")
        for child_idx in range(blocks_per_page - 1):
            child = _uuid(slot)
            slot += 1
            parts.append(f"  - child-{child_idx}\n    id:: {child}\n")
        # Trailing sibling so deepest id:: indexes (parser quirk).
        tail = _uuid(slot)
        slot += 1
        parts.append(f"  - tail\n    id:: {tail}\n")
        (graph / "pages" / f"Perf{page_idx:04d}.md").write_text("".join(parts), encoding="utf-8")
    return roots


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


# --- A7-BOOT ---


def test_a7_boot_01_rebuild_1k_blocks_within_bound(tmp_path: Path) -> None:
    """A7-BOOT-01: full rebuild of ~1000 blocks completes under a soft ceiling."""
    graph = _minimal_graph(tmp_path)
    # 50 pages × 20 blocks = 1000 (+ tails) ≈ 1050 rows.
    _seed_block_pages(graph, pages=50, blocks_per_page=20)
    started = time.perf_counter()
    rebuild_shadow_from_graph(graph)
    elapsed = time.perf_counter() - started
    conn = open_shadow_db(graph)
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0])
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()
    assert count >= 1000
    assert elapsed < _BOOT_1K_MAX_S, f"1k rebuild took {elapsed:.2f}s (max {_BOOT_1K_MAX_S})"


@pytest.mark.slow
def test_a7_boot_02_rebuild_10k_blocks_within_bound(tmp_path: Path) -> None:
    """A7-BOOT-02: full rebuild of ~10k blocks completes under a soft ceiling."""
    graph = _minimal_graph(tmp_path)
    _seed_block_pages(graph, pages=200, blocks_per_page=50)
    started = time.perf_counter()
    rebuild_shadow_from_graph(graph)
    elapsed = time.perf_counter() - started
    conn = open_shadow_db(graph)
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0])
    finally:
        conn.close()
    assert count >= 10_000
    assert elapsed < _BOOT_10K_MAX_S, f"10k rebuild took {elapsed:.2f}s (max {_BOOT_10K_MAX_S})"


@pytest.mark.slow
def test_a7_boot_03_rebuild_50k_blocks_within_bound(tmp_path: Path) -> None:
    """A7-BOOT-03: full rebuild of ~50k blocks completes under a soft ceiling."""
    graph = _minimal_graph(tmp_path)
    _seed_block_pages(graph, pages=500, blocks_per_page=100)
    started = time.perf_counter()
    rebuild_shadow_from_graph(graph)
    elapsed = time.perf_counter() - started
    conn = open_shadow_db(graph)
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0])
    finally:
        conn.close()
    assert count >= 50_000
    assert elapsed < _BOOT_50K_MAX_S, f"50k rebuild took {elapsed:.2f}s (max {_BOOT_50K_MAX_S})"


# --- A7-FTS / A7-CTE ---


def test_a7_fts_01_query_latency_p50_p95_bounded(tmp_path: Path) -> None:
    """A7-FTS-01: shadow FTS BM25 latency p50/p95 stay under soft ceilings."""
    graph = _minimal_graph(tmp_path)
    roots = _seed_block_pages(graph, pages=20, blocks_per_page=25)
    rebuild_shadow_from_graph(graph)
    samples: list[float] = []
    for index in range(40):
        started = time.perf_counter()
        out = resolve_bm25_search_markdown(graph, f"root-{index % 20}")
        samples.append(time.perf_counter() - started)
        assert isinstance(out, str)
    p50 = _percentile(samples, 50)
    p95 = _percentile(samples, 95)
    assert p50 <= p95
    assert p95 < _FTS_P95_MAX_S, f"FTS p95={p95:.3f}s p50={p50:.3f}s (max {_FTS_P95_MAX_S})"
    _ = roots


def test_a7_cte_01_subtree_latency_p50_p95_bounded(tmp_path: Path) -> None:
    """A7-CTE-01: CTE subtree query latency p50/p95 stay under soft ceilings."""
    graph = _minimal_graph(tmp_path)
    roots = _seed_block_pages(graph, pages=20, blocks_per_page=25)
    rebuild_shadow_from_graph(graph)
    samples: list[float] = []
    conn = open_shadow_db(graph)
    try:
        for index in range(40):
            started = time.perf_counter()
            result = query_subtree_by_block_uuid(conn, roots[index % len(roots)])
            samples.append(time.perf_counter() - started)
            assert result.status in {SubtreeStatus.COMPLETE, SubtreeStatus.TRUNCATED}
            assert result.nodes
    finally:
        conn.close()
    p50 = _percentile(samples, 50)
    p95 = _percentile(samples, 95)
    assert p50 <= p95
    assert p95 < _CTE_P95_MAX_S, f"CTE p95={p95:.3f}s p50={p50:.3f}s (max {_CTE_P95_MAX_S})"


# --- A7-MEM / A7-LOCK / A7-WATCH ---


def test_a7_mem_01_repeated_reads_rss_growth_bounded(tmp_path: Path) -> None:
    """A7-MEM-01: repeated FTS+CTE reads do not grow RSS unboundedly."""
    graph = _minimal_graph(tmp_path)
    roots = _seed_block_pages(graph, pages=10, blocks_per_page=20)
    rebuild_shadow_from_graph(graph)
    tracemalloc.start()
    before_peak = tracemalloc.get_traced_memory()[1]
    conn = open_shadow_db(graph)
    try:
        for index in range(80):
            resolve_bm25_search_markdown(graph, "root")
            query_subtree_by_block_uuid(conn, roots[index % len(roots)])
    finally:
        conn.close()
    after_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    growth_mb = (after_peak - before_peak) / (1024 * 1024)
    assert growth_mb < _RSS_GROWTH_MB_MAX, f"peak growth {growth_mb:.1f} MiB"


def test_a7_lock_01_incremental_sync_lock_hold_bounded(tmp_path: Path) -> None:
    """A7-LOCK-01: incremental sync completes within a soft hold bound."""
    graph = _minimal_graph(tmp_path)
    page = graph / "pages" / "Lock.md"
    page.write_text(
        f"- lock\n  id:: {_uuid(1)}\n  - child\n    id:: {_uuid(2)}\n",
        encoding="utf-8",
    )
    rebuild_shadow_from_graph(graph)
    page.write_text(
        (
            f"- lock\n  id:: {_uuid(1)}\n"
            f"  - child\n    id:: {_uuid(2)}\n"
            f"  - added\n    id:: {_uuid(3)}\n"
            f"  - tail\n    id:: {_uuid(4)}\n"
        ),
        encoding="utf-8",
    )
    started = time.perf_counter()
    sync_page_to_shadow(graph, page)
    elapsed = time.perf_counter() - started
    assert elapsed < _LOCK_HOLD_MAX_S, f"sync took {elapsed:.2f}s (max {_LOCK_HOLD_MAX_S})"


def test_a7_watch_01_file_burst_sync_completes_coherent(tmp_path: Path) -> None:
    """A7-WATCH-01: burst of incremental page syncs finishes under bound with coherent meta."""
    graph = _minimal_graph(tmp_path)
    paths: list[Path] = []
    for index in range(40):
        path = graph / "pages" / f"Burst{index:02d}.md"
        path.write_text(
            (
                f"- burst-{index}\n  id:: {_uuid(1000 + index)}\n"
                f"  - tail\n    id:: {_uuid(2000 + index)}\n"
            ),
            encoding="utf-8",
        )
        paths.append(path)
    rebuild_shadow_from_graph(graph)
    for index, path in enumerate(paths):
        path.write_text(
            (
                f"- burst-{index}\n  id:: {_uuid(1000 + index)}\n"
                f"  - updated\n    id:: {_uuid(3000 + index)}\n"
                f"  - tail\n    id:: {_uuid(2000 + index)}\n"
            ),
            encoding="utf-8",
        )
    started = time.perf_counter()
    for path in paths:
        sync_page_to_shadow(graph, path)
    elapsed = time.perf_counter() - started
    conn = open_shadow_db(graph)
    try:
        page_count = int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()
    assert page_count == 40
    assert elapsed < _WATCH_BURST_MAX_S, (
        f"burst sync took {elapsed:.2f}s (max {_WATCH_BURST_MAX_S})"
    )


def test_a7_stats_01_latency_samples_are_deterministic_ordering(tmp_path: Path) -> None:
    """A7-STATS-01: percentile helper is stable for identical samples (sanity for p50/p95)."""
    samples = [0.01, 0.02, 0.03, 0.04, 0.10]
    assert _percentile(samples, 50) == statistics.median(samples)
    assert _percentile(samples, 95) >= _percentile(samples, 50)
