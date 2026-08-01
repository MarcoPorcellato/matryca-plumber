"""v2.0-alpha hardening — Axis 1: concurrency & recovery (audit probes).

Read-only failure injection on temporary vault fixtures. Findings feed
tracking issue #261; production code changes only after a minimal reproducer
exists and a child issue is opened.
"""

from __future__ import annotations

import multiprocessing as mp
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.post_write import register_page_written_handler
from src.shadow.bootstrap import (
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
)
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_GENERATION,
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SOURCE_PAGE_COUNT,
    get_meta,
    set_meta,
)
from src.shadow.runtime_state import (
    mark_bootstrapping,
    reset_shadow_runtime_state_for_tests,
)
from src.shadow.sync import (
    reset_shadow_sync_bridge_for_tests,
    sync_page_into_connection,
    sync_page_to_shadow,
)
from src.shadow.writer_lock import shadow_writer_lock, shadow_writer_lock_path


@pytest.fixture(autouse=True)
def _shadow_cache_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path / "operator-cache"))


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()
    reset_shadow_bootstrap_checked_for_tests()
    reset_shadow_sync_bridge_for_tests()


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    return graph


def test_a1_rebuild_injected_failure_preserves_committed_generation(tmp_path: Path) -> None:
    """A1-BOOT-01: failed rebuild must not destroy the last committed generation."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Stable.md",
        "- stable\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        generation_before = get_meta(conn, META_GENERATION)
        page_count_before = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    finally:
        conn.close()

    _write_page(
        graph,
        "pages/Trigger.md",
        "- trigger\n  id:: 22222222-2222-4222-8222-222222222222\n",
    )

    calls = 0
    original = sync_page_into_connection

    def _fail_on_second_page(
        connection: sqlite3.Connection,
        graph_root: Path,
        page_path: Path,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise RuntimeError("injected axis-1 rebuild failure")
        original(connection, graph_root, page_path)

    with (
        patch("src.shadow.sync.sync_page_into_connection", side_effect=_fail_on_second_page),
        pytest.raises(RuntimeError, match="injected axis-1"),
    ):
        rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert get_meta(conn, META_GENERATION) == generation_before
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == page_count_before
        assert (get_meta(conn, META_LAST_SYNC_ERROR) or "").strip() != ""
        assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    finally:
        conn.close()


def test_a1_health_not_ready_when_meta_completed_but_pages_empty(tmp_path: Path) -> None:
    """A1-META-01: meta/pages mismatch must report ``stale`` or ``error``, never ``ready``."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_LAST_FULL_SYNC_COMPLETED, "true")
        set_meta(conn, META_LAST_SYNC_ERROR, "")
        set_meta(conn, META_SOURCE_PAGE_COUNT, "1")
        set_meta(conn, META_INDEXED_PAGE_COUNT, "1")
        conn.execute("DELETE FROM pages")
        conn.commit()
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert int(get_meta(conn, META_SOURCE_PAGE_COUNT) or "0") > 0
        assert int(get_meta(conn, META_INDEXED_PAGE_COUNT) or "0") > 0
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
    finally:
        conn.close()

    health = resolve_shadow_health(graph)
    assert health != ShadowHealthState.READY
    assert health in (ShadowHealthState.STALE, ShadowHealthState.ERROR)


def test_a1_watchdog_delete_during_bootstrap_replays_removal_when_file_gone(
    tmp_path: Path,
) -> None:
    """A1-DEFER-01: deferred delete replays after rebuild when the Markdown file is gone."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Seed.md",
        "- seed\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    rebuild_shadow_from_graph(graph)

    victim = _write_page(
        graph,
        "pages/Victim.md",
        "- victim\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
    )
    sync_page_to_shadow(graph, victim)
    victim_rel = victim.relative_to(graph).as_posix()
    victim.unlink()

    mark_bootstrapping(graph)
    handle_shadow_watchdog_change(graph, graph / victim_rel, "deleted")
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        titles = {row[0] for row in conn.execute("SELECT title FROM pages").fetchall()}
        assert "Seed" in titles
        assert "Victim" not in titles
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()


def test_a1_post_write_during_bootstrap_replays_after_rebuild(tmp_path: Path) -> None:
    """A1-DEFER-02: post_write hook defers until bootstrap completes."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Base.md",
        "- base\n  id:: cccccccc-cccc-4ccc-8ccc-cccccccccccc\n",
    )
    rebuild_shadow_from_graph(graph)

    mark_bootstrapping(graph)
    late = _write_page(
        graph,
        "pages/Late.md",
        "- late\n  id:: dddddddd-dddd-4ddd-8ddd-dddddddddddd\n",
    )
    register_page_written_handler(
        lambda event: sync_page_to_shadow(event.graph_root, event.path),
    )
    sync_page_to_shadow(
        graph,
        late,
    )
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        titles = {row[0] for row in conn.execute("SELECT title FROM pages").fetchall()}
        assert {"Base", "Late"} <= titles
    finally:
        conn.close()


def test_a1_sqlite_writer_lock_blocks_incremental_without_meta_corruption(
    tmp_path: Path,
) -> None:
    """A1-SQLITE-01: writer contention surfaces as SQLite error, not torn meta."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/Lock.md",
        "- lock\n  id:: eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee\n",
    )
    rebuild_shadow_from_graph(graph)

    holder = open_shadow_db(graph)
    holder.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(sqlite3.OperationalError):
            sync_page_to_shadow(graph, page)
    finally:
        holder.rollback()
        holder.close()

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert (get_meta(conn, META_LAST_SYNC_ERROR) or "").strip() == ""
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1
    finally:
        conn.close()


def _multiprocess_rebuild_worker(graph_str: str) -> None:
    import os

    os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    from src.shadow.bootstrap import rebuild_shadow_from_graph

    rebuild_shadow_from_graph(graph_str)


@pytest.mark.slow
def test_a1_cross_process_rebuild_completes_while_sqlite_writer_active(
    tmp_path: Path,
) -> None:
    """A1-PROC-01: rebuild must finish under cross-process contention without SQLite lock errors."""
    graph = _minimal_graph(tmp_path)
    for index in range(4):
        _write_page(
            graph,
            f"pages/P{index}.md",
            f"- p{index}\n  id:: {index:08d}-1111-4111-8111-111111111111\n",
        )
    rebuild_shadow_from_graph(graph)

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1) as pool:
        with shadow_writer_lock(graph):
            holder = open_shadow_db(graph)
            holder.execute("BEGIN IMMEDIATE")
            async_rebuild = pool.apply_async(_multiprocess_rebuild_worker, (str(graph),))
            time.sleep(0.2)
            holder.rollback()
            holder.close()
        async_rebuild.get(timeout=60)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert (get_meta(conn, META_LAST_SYNC_ERROR) or "").strip() == ""
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 4
        assert resolve_shadow_health(graph) == ShadowHealthState.READY
    finally:
        conn.close()


def test_a1_shadow_writer_lock_is_cross_process(tmp_path: Path) -> None:
    """A1-PROC-02: shadow writers share a graph-root flock sidecar under semantic cache."""
    graph = _minimal_graph(tmp_path)
    lock_path = shadow_writer_lock_path(graph)
    assert lock_path.name == "shadow.writer.flock"
    assert not lock_path.parent.is_relative_to(graph.resolve())
