"""Bootstrap and reconciliation tests for Shadow DB (#248 / PR-0)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from src.config import MatrycaWikiConfig
from src.shadow.bootstrap import (
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
    shadow_needs_bootstrap,
)
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_GENERATION,
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    get_meta,
)
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.sync import (
    reset_shadow_sync_bridge_for_tests,
    sync_page_to_shadow,
)
from src.utils.runtime_bootstrap import prepare_matryca_runtime


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
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


def test_rebuild_indexes_existing_vault(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    _write_page(
        graph,
        "journals/2026_07_18.md",
        "- journal\n  id:: 22222222-2222-4222-8222-222222222222\n",
    )

    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 2
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert get_meta(conn, META_SOURCE_PAGE_COUNT) == "2"
        assert get_meta(conn, META_INDEXED_PAGE_COUNT) == "2"
        assert get_meta(conn, META_LAST_SYNC_ERROR) == ""
        assert int(get_meta(conn, META_GENERATION) or "0") == 1
    finally:
        conn.close()
    assert resolve_shadow_health(graph) == ShadowHealthState.READY


def test_rebuild_is_idempotent_without_file_changes(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Stable.md",
        "- stable\n  id:: 33333333-3333-4333-8333-333333333333\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        first_gen = get_meta(conn, META_GENERATION)
    finally:
        conn.close()

    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_GENERATION) == str(int(first_gen or "0") + 1)
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1
    finally:
        conn.close()


def test_delete_and_rename_reconcile_by_file_path(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    old = _write_page(
        graph,
        "pages/OldName.md",
        "- old\n  id:: 44444444-4444-4444-8444-444444444444\n",
    )
    rebuild_shadow_from_graph(graph)
    new = graph / "pages" / "NewName.md"
    old.rename(new)
    new.write_text(
        "- renamed\n  id:: 55555555-5555-4555-8555-555555555555\n",
        encoding="utf-8",
    )
    handle_shadow_watchdog_change(graph, old, "deleted")
    handle_shadow_watchdog_change(graph, new, "created")
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        rows = conn.execute("SELECT title, file_path FROM pages").fetchall()
        assert rows == [("NewName", "pages/NewName.md")]
        assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 1
    finally:
        conn.close()


def test_interrupted_rebuild_preserves_prior_generation(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Safe.md",
        "- safe\n  id:: 66666666-6666-4666-8666-666666666666\n",
    )
    rebuild_shadow_from_graph(graph)

    _write_page(
        graph,
        "pages/Broken.md",
        "- broken\n  id:: 77777777-7777-4777-8777-777777777777\n",
    )

    def _boom(
        connection: sqlite3.Connection,
        graph_root: Path,
        page_path: Path,
    ) -> None:
        if page_path.name == "Broken.md":
            raise RuntimeError("simulated rebuild failure")
        from src.shadow.sync import sync_page_into_connection

        sync_page_into_connection(connection, graph_root, page_path)

    with (
        patch("src.shadow.sync.sync_page_into_connection", side_effect=_boom),
        pytest.raises(RuntimeError, match="simulated rebuild failure"),
    ):
        rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "false"
        assert "full rebuild failed" in (get_meta(conn, META_LAST_SYNC_ERROR) or "")
        titles = {row[0] for row in conn.execute("SELECT title FROM pages").fetchall()}
        assert titles == {"Safe"}
        assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    finally:
        conn.close()


def test_incompatible_schema_triggers_bootstrap(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            ("999", META_SCHEMA_VERSION),
        )
        conn.commit()
    finally:
        conn.close()

    assert shadow_needs_bootstrap(graph) is True
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR


def test_concurrent_rebuild_defers_incremental_sync(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Base.md",
        "- base\n  id:: 88888888-8888-4888-8888-888888888888\n",
    )
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _slow_rebuild() -> None:
        conn = open_shadow_db(graph)
        try:
            conn.execute("BEGIN IMMEDIATE")
            barrier.wait(timeout=5)
            conn.execute("DELETE FROM pages")
            conn.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            conn.rollback()
        finally:
            conn.close()

    def _incremental_during_rebuild() -> None:
        barrier.wait(timeout=5)
        sync_page_to_shadow(
            graph,
            _write_page(
                graph,
                "pages/Late.md",
                "- late\n  id:: 99999999-9999-4999-8999-999999999999\n",
            ),
        )

    from src.shadow.runtime_state import mark_bootstrapping

    mark_bootstrapping(graph)
    thread = threading.Thread(target=_slow_rebuild)
    thread.start()
    worker = threading.Thread(target=_incremental_during_rebuild)
    worker.start()
    thread.join(timeout=10)
    worker.join(timeout=10)
    assert not errors

    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        titles = {row[0] for row in conn.execute("SELECT title FROM pages").fetchall()}
        assert "Late" in titles
        assert "Base" in titles
    finally:
        conn.close()


def test_flag_false_skips_db_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/NoDb.md", "- x\n")
    sync_page_to_shadow(graph, graph / "pages" / "NoDb.md")
    assert not shadow_db_path(graph).exists()
    assert shadow_db_enabled() is False


def test_startup_bootstrap_via_prepare_matryca_runtime(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Startup.md",
        "- boot\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())
    conn = open_shadow_db(graph)
    try:
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()
