"""Cross-process shadow writer flock and SQLite busy handling (#262)."""

from __future__ import annotations

import multiprocessing as mp
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from src.graph.io_retry import PageLockUnavailableError
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.meta import META_LAST_FULL_SYNC_COMPLETED, get_meta
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.sync import sync_page_to_shadow
from src.shadow.writer_lock import shadow_writer_lock, shadow_writer_lock_path
from src.utils.platform_lock import clear_flock_depths

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fcntl flock is not available on Windows",
)


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()
    clear_flock_depths()


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _multiprocess_rebuild_worker(graph_str: str) -> None:
    os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    from src.shadow.bootstrap import rebuild_shadow_from_graph

    rebuild_shadow_from_graph(graph_str)


def test_shadow_writer_lock_path_under_semantic_cache(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    lock_path = shadow_writer_lock_path(graph)
    assert lock_path.name == "shadow.writer.flock"
    assert lock_path.parent.name == ".matryca_semantic_cache"


def test_concurrent_rebuilds_serialize_across_processes(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    for index in range(3):
        _write_page(
            graph,
            f"pages/P{index}.md",
            f"- p{index}\n  id:: {index:08d}-1111-4111-8111-111111111111\n",
        )
    rebuild_shadow_from_graph(graph)

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        results = [
            pool.apply_async(_multiprocess_rebuild_worker, (str(graph),)),
            pool.apply_async(_multiprocess_rebuild_worker, (str(graph),)),
        ]
        for result in results:
            result.get(timeout=60)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 3
    finally:
        conn.close()


def test_rebuild_and_incremental_sync_serialize(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Base.md",
        "- base\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    rebuild_shadow_from_graph(graph)

    late = _write_page(
        graph,
        "pages/Late.md",
        "- late\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
    )

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1) as pool:
        with shadow_writer_lock(graph):
            async_rebuild = pool.apply_async(_multiprocess_rebuild_worker, (str(graph),))
            time.sleep(0.15)
            sync_page_to_shadow(graph, late)
        async_rebuild.get(timeout=60)

    conn = open_shadow_db(graph)
    try:
        titles = {row[0] for row in conn.execute("SELECT title FROM pages").fetchall()}
        assert {"Base", "Late"} <= titles
    finally:
        conn.close()


def test_different_graph_roots_do_not_block_each_other(tmp_path: Path) -> None:
    graph_a = _minimal_graph(tmp_path / "a")
    graph_b = _minimal_graph(tmp_path / "b")
    _write_page(
        graph_a,
        "pages/A.md",
        "- a\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    _write_page(
        graph_b,
        "pages/B.md",
        "- b\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
    )
    rebuild_shadow_from_graph(graph_a)
    rebuild_shadow_from_graph(graph_b)

    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=2) as pool:
        start = time.monotonic()
        results = [
            pool.apply_async(_multiprocess_rebuild_worker, (str(graph_a),)),
            pool.apply_async(_multiprocess_rebuild_worker, (str(graph_b),)),
        ]
        for result in results:
            result.get(timeout=60)
        elapsed = time.monotonic() - start

    assert elapsed < 8.0


def test_writer_lock_released_after_process_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Seed.md",
        "- seed\n  id:: cccccccc-cccc-4ccc-8ccc-cccccccccccc\n",
    )
    rebuild_shadow_from_graph(graph)

    monkeypatch.setenv("MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S", "1")
    repo_root = Path(__file__).resolve().parents[1]
    ready_file = tmp_path / "holder.ready"
    hold_script = f"""
import os
import time
from pathlib import Path
from src.shadow.writer_lock import shadow_writer_lock

os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "true"
os.environ["MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S"] = "120"
graph = Path({str(graph)!r})
ready = Path({str(ready_file)!r})
with shadow_writer_lock(graph):
    ready.write_text("ok", encoding="utf-8")
    time.sleep(30)
"""
    proc = subprocess.Popen([sys.executable, "-c", hold_script], cwd=str(repo_root))
    try:
        deadline = time.monotonic() + 5.0
        while not ready_file.is_file() and proc.poll() is None:
            if time.monotonic() >= deadline:
                pytest.fail("holder subprocess did not acquire writer lock in time")
            time.sleep(0.05)
        with pytest.raises(PageLockUnavailableError), shadow_writer_lock(graph):
            pass
        proc.kill()
        proc.wait(timeout=5)
        with shadow_writer_lock(graph):
            pass
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_sqlite_busy_surfaces_without_masking_corruption(tmp_path: Path) -> None:
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
