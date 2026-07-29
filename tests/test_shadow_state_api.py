"""Unit tests for Shadow DB ``/api/state`` snapshot builder (#185)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_AT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    set_meta,
)
from src.shadow.runtime_state import mark_bootstrapping, reset_shadow_runtime_state_for_tests
from src.shadow.schema import SHADOW_SCHEMA_VERSION
from src.shadow.state_api import ShadowDbStateResponse, resolve_shadow_db_state_for_api

DISABLED_SHADOW_DB = {
    "enabled": False,
    "state": "disabled",
    "last_full_sync_at": None,
    "source_page_count": None,
    "indexed_page_count": None,
    "lag_pages": None,
    "last_sync_error": None,
    "not_ready_reason": None,
    "quarantined_page_count": 0,
}


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_shadow_runtime_state_for_tests()


def _graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> None:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def test_resolve_shadow_db_state_disabled_when_flag_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.model_dump() == DISABLED_SHADOW_DB
    assert not shadow_db_path(graph).exists()


def test_resolve_shadow_db_state_bootstrapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    mark_bootstrapping(graph)

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.enabled is True
    assert snapshot.state == "bootstrapping"
    assert snapshot.last_full_sync_at is None
    assert snapshot.source_page_count is None
    assert snapshot.indexed_page_count is None
    assert snapshot.lag_pages is None
    assert snapshot.last_sync_error is None


def test_resolve_shadow_db_state_stale_without_db_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.enabled is True
    assert snapshot.state == "stale"
    assert not shadow_db_path(graph).exists()


def test_resolve_shadow_db_state_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "ready"
    assert snapshot.enabled is True
    assert snapshot.last_sync_error is None
    assert snapshot.source_page_count == 1
    assert snapshot.indexed_page_count == 1
    assert snapshot.lag_pages == 0


def test_resolve_shadow_db_state_error_with_bounded_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_LAST_SYNC_ERROR, "sync failed on pages/Alpha.md")
        conn.commit()
    finally:
        conn.close()

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "error"
    assert snapshot.last_sync_error == "sync failed on pages/Alpha.md"


def test_resolve_shadow_db_state_schema_mismatch_is_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_SCHEMA_VERSION, str(SHADOW_SCHEMA_VERSION + 1))
        conn.commit()
    finally:
        conn.close()

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "error"
    assert snapshot.last_sync_error == "Shadow schema version mismatch"


def test_resolve_shadow_db_state_reports_lag_and_last_full_sync_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    _write_page(
        graph,
        "pages/Alpha.md",
        "- alpha\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_SOURCE_PAGE_COUNT, "5")
        set_meta(conn, META_INDEXED_PAGE_COUNT, "2")
        set_meta(conn, META_LAST_FULL_SYNC_AT, "2026-07-18T10:00:00+00:00")
        set_meta(conn, META_LAST_FULL_SYNC_COMPLETED, "false")
        conn.commit()
    finally:
        conn.close()

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "stale"
    assert snapshot.lag_pages == 3
    assert snapshot.source_page_count == 5
    assert snapshot.indexed_page_count == 2
    assert snapshot.last_full_sync_at == "2026-07-18T10:00:00+00:00"


def test_resolve_shadow_db_state_sqlite_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    db_path = shadow_db_path(graph)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(b"not-a-sqlite-db")

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "error"
    assert snapshot.last_sync_error is not None
    assert len(snapshot.last_sync_error) <= 200


def test_resolve_shadow_db_state_stale_when_meta_completed_but_pages_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
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
    finally:
        conn.close()

    snapshot = resolve_shadow_db_state_for_api(graph)

    assert snapshot.state == "stale"
    assert snapshot.last_sync_error is None


def test_shadow_db_response_model_has_stable_keys() -> None:
    payload = ShadowDbStateResponse().model_dump()
    assert set(payload.keys()) == set(DISABLED_SHADOW_DB.keys())
