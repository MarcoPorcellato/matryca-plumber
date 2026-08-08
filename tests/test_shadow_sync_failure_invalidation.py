"""Fail-closed Shadow generation invalidation for generic sync failures (#386)."""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.markdown_blocks import atomic_write_bytes
from src.graph.post_write import clear_page_written_handlers
from src.shadow.bootstrap import handle_shadow_watchdog_change, rebuild_shadow_from_graph
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import META_GENERATION, META_LAST_SYNC_ERROR, get_meta
from src.shadow.runtime_state import (
    is_shadow_generation_invalid,
    reset_shadow_runtime_state_for_tests,
)
from src.shadow.state_api import resolve_shadow_db_state_for_api
from src.shadow.sync import (
    ensure_shadow_sync_bridge,
    reset_shadow_sync_bridge_for_tests,
    sync_page_to_shadow,
)
from src.shadow.sync_failure import (
    SHADOW_SYNC_FAILURE_REASON,
    is_shadow_sync_failed,
    mark_shadow_sync_failed,
)


@pytest.fixture(autouse=True)
def _reset_shadow(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    reset_shadow_runtime_state_for_tests()
    clear_page_written_handlers()
    reset_shadow_sync_bridge_for_tests()
    yield
    clear_page_written_handlers()
    reset_shadow_sync_bridge_for_tests()


def _ready_graph(tmp_path: Path) -> tuple[Path, Path, str]:
    graph = tmp_path / "graph"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    page = pages / "Alpha.md"
    page.write_text(
        "- old content\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        generation = get_meta(conn, META_GENERATION) or ""
    finally:
        conn.close()
    page.write_text(
        "- current content\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    return graph, page, generation


def _assert_persisted_failure(graph: Path, generation: str) -> None:
    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_GENERATION) == generation
        assert get_meta(conn, META_LAST_SYNC_ERROR) == SHADOW_SYNC_FAILURE_REASON
    finally:
        conn.close()
    assert is_shadow_generation_invalid(graph)
    assert is_shadow_sync_failed(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    state = resolve_shadow_db_state_for_api(graph)
    assert state.state == "error"
    assert state.not_ready_reason == "sync_error"
    assert state.last_sync_error == SHADOW_SYNC_FAILURE_REASON


@pytest.mark.parametrize(
    "failure",
    [
        sqlite3.DatabaseError("schema failure"),
        sqlite3.OperationalError("database or disk is full"),
        OSError("filesystem failure"),
    ],
    ids=["schema", "disk-full", "filesystem"],
)
def test_generic_transaction_failures_persist_invalidation(
    tmp_path: Path,
    failure: Exception,
) -> None:
    graph, page, generation = _ready_graph(tmp_path)
    with (
        patch("src.shadow.sync.sync_page_into_connection", side_effect=failure),
        pytest.raises(type(failure)),
    ):
        sync_page_to_shadow(graph, page)

    _assert_persisted_failure(graph, generation)


def test_connection_failure_uses_runtime_latch_when_meta_cannot_be_written(
    tmp_path: Path,
) -> None:
    graph, page, _generation = _ready_graph(tmp_path)
    with (
        patch(
            "src.shadow.sync.open_shadow_db",
            side_effect=sqlite3.OperationalError("connection failure"),
        ),
        pytest.raises(sqlite3.OperationalError),
    ):
        sync_page_to_shadow(graph, page)

    assert is_shadow_generation_invalid(graph)
    marker = resolve_shadow_cache_location(graph).shadow_dir / "shadow.sync-invalid"
    assert marker.read_text(encoding="ascii") == SHADOW_SYNC_FAILURE_REASON
    if os.name == "posix":
        assert stat.S_IMODE(marker.stat().st_mode) == 0o600
    reset_shadow_runtime_state_for_tests()
    assert is_shadow_sync_failed(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    state = resolve_shadow_db_state_for_api(graph)
    assert state.not_ready_reason == "sync_error"
    assert state.last_sync_error == SHADOW_SYNC_FAILURE_REASON


@pytest.mark.skipif(os.name == "nt", reason="symlink creation requires privileges on Windows")
def test_failure_marker_rejects_symlink_without_touching_target(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    graph.mkdir()
    location = resolve_shadow_cache_location(graph)
    location.ensure_directory()
    target = tmp_path / "outside.txt"
    target.write_text("unchanged", encoding="utf-8")
    marker = location.shadow_dir / "shadow.sync-invalid"
    marker.symlink_to(target)

    mark_shadow_sync_failed(graph)

    assert marker.is_symlink()
    assert target.read_text(encoding="utf-8") == "unchanged"
    assert is_shadow_sync_failed(graph)


def test_unexpected_marker_object_fails_closed_after_restart(tmp_path: Path) -> None:
    graph = tmp_path / "graph"
    graph.mkdir()
    marker = resolve_shadow_cache_location(graph).shadow_dir / "shadow.sync-invalid"
    marker.mkdir(parents=True)

    reset_shadow_runtime_state_for_tests()

    assert is_shadow_sync_failed(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR


def test_commit_failure_rolls_back_then_persists_invalidation(tmp_path: Path) -> None:
    graph, page, generation = _ready_graph(tmp_path)
    transaction = open_shadow_db(graph)
    recorder = open_shadow_db(graph)

    class _CommitFailureConnection:
        def __getattr__(self, name: str) -> object:
            return getattr(transaction, name)

        def commit(self) -> None:
            raise sqlite3.OperationalError("commit failure")

    with (
        patch(
            "src.shadow.sync.open_shadow_db",
            side_effect=[_CommitFailureConnection(), recorder],
        ),
        pytest.raises(sqlite3.OperationalError, match="commit failure"),
    ):
        sync_page_to_shadow(graph, page)

    _assert_persisted_failure(graph, generation)


def test_post_write_failure_does_not_undo_authoritative_markdown(tmp_path: Path) -> None:
    graph, page, _generation = _ready_graph(tmp_path)
    ensure_shadow_sync_bridge()
    body = b"- authoritative write survives\n"

    with patch(
        "src.shadow.sync.sync_page_to_shadow",
        side_effect=RuntimeError("callback failure"),
    ):
        atomic_write_bytes(page, body, graph_root=graph, robot_commit_summary="test")

    assert page.read_bytes() == body
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    assert resolve_shadow_db_state_for_api(graph).last_sync_error == SHADOW_SYNC_FAILURE_REASON


def test_watchdog_failure_is_contained_and_invalidates_reads(tmp_path: Path) -> None:
    graph, page, _generation = _ready_graph(tmp_path)
    with patch(
        "src.shadow.bootstrap.sync_page_to_shadow",
        side_effect=RuntimeError("watchdog failure"),
    ):
        handle_shadow_watchdog_change(graph, page, "modified")

    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR
    assert resolve_shadow_db_state_for_api(graph).last_sync_error == SHADOW_SYNC_FAILURE_REASON


def test_successful_full_reconciliation_clears_failure_latch(tmp_path: Path) -> None:
    graph, page, generation = _ready_graph(tmp_path)
    with (
        patch(
            "src.shadow.sync.sync_page_into_connection",
            side_effect=sqlite3.OperationalError("generic failure"),
        ),
        pytest.raises(sqlite3.OperationalError),
    ):
        sync_page_to_shadow(graph, page)
    _assert_persisted_failure(graph, generation)

    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_SYNC_ERROR) == ""
        assert int(get_meta(conn, META_GENERATION) or "0") == int(generation) + 1
    finally:
        conn.close()
    assert not is_shadow_generation_invalid(graph)
    assert not is_shadow_sync_failed(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.READY
