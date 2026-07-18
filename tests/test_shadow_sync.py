"""Integration tests for shadow incremental sync (#182)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.graph.markdown_blocks import atomic_write_bytes
from src.graph.post_write import clear_page_written_handlers, emit_page_written
from src.shadow.connection import open_shadow_db
from src.shadow.sync import (
    ensure_shadow_sync_bridge,
    reset_shadow_sync_bridge_for_tests,
    sync_page_to_shadow,
)


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_sync_page_to_shadow_upserts_blocks(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "pages/ShadowSync.md",
        "- parent block\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        "  - child block\n"
        "    id:: 22222222-2222-4222-8222-222222222222\n",
    )
    sync_page_to_shadow(tmp_path, page)

    conn = open_shadow_db(tmp_path)
    try:
        pages = conn.execute("SELECT title, file_path FROM pages").fetchall()
        assert pages == [("ShadowSync", "pages/ShadowSync.md")]
        blocks = conn.execute(
            "SELECT block_uuid, content, parent_rowid IS NOT NULL "
            "FROM blocks ORDER BY sort_order, rowid"
        ).fetchall()
        assert len(blocks) == 2
        uuids = {row[0] for row in blocks}
        assert "11111111-1111-4111-8111-111111111111" in uuids
        assert "22222222-2222-4222-8222-222222222222" in uuids
        child = conn.execute(
            "SELECT content FROM blocks WHERE block_uuid = ?",
            ("22222222-2222-4222-8222-222222222222",),
        ).fetchone()
        assert child is not None
        assert "child block" in child[0]
    finally:
        conn.close()


def test_sync_page_to_shadow_replaces_on_rewrite(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "pages/Rewrite.md",
        "- first\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
    )
    sync_page_to_shadow(tmp_path, page)
    page.write_text(
        "- second\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
        encoding="utf-8",
    )
    sync_page_to_shadow(tmp_path, page)

    conn = open_shadow_db(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1
        rows = conn.execute("SELECT block_uuid, content FROM blocks").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        assert "second" in rows[0][1]
    finally:
        conn.close()


def test_sync_page_to_shadow_deletes_missing_file(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "pages/Gone.md",
        "- gone\n  id:: cccccccc-cccc-4ccc-8ccc-cccccccccccc\n",
    )
    sync_page_to_shadow(tmp_path, page)
    page.unlink()
    sync_page_to_shadow(tmp_path, page)

    conn = open_shadow_db(tmp_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0
    finally:
        conn.close()


def test_post_write_bridge_syncs_via_atomic_write(tmp_path: Path) -> None:
    clear_page_written_handlers()
    reset_shadow_sync_bridge_for_tests()
    ensure_shadow_sync_bridge()
    try:
        target = tmp_path / "pages" / "Bridge.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(
            target,
            b"- bridged\n  id:: dddddddd-dddd-4ddd-8ddd-dddddddddddd\n",
            graph_root=tmp_path,
            robot_commit_summary="shadow sync test",
        )
        conn = open_shadow_db(tmp_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
            assert count == 1
        finally:
            conn.close()
    finally:
        clear_page_written_handlers()
        reset_shadow_sync_bridge_for_tests()


def test_emit_page_written_triggers_shadow_sync(tmp_path: Path) -> None:
    clear_page_written_handlers()
    reset_shadow_sync_bridge_for_tests()
    ensure_shadow_sync_bridge()
    try:
        page = _write_page(
            tmp_path,
            "pages/Emit.md",
            "- emitted\n  id:: eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee\n",
        )
        emit_page_written(graph_root=tmp_path, path=page, summary="emit")
        conn = open_shadow_db(tmp_path)
        try:
            row = conn.execute(
                "SELECT content FROM blocks WHERE block_uuid = ?",
                ("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",),
            ).fetchone()
            assert row is not None
            assert "emitted" in row[0]
        finally:
            conn.close()
    finally:
        clear_page_written_handlers()
        reset_shadow_sync_bridge_for_tests()
