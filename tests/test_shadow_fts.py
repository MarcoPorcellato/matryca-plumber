"""Tests for shadow FTS5 query module (#183)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.shadow.connection import open_shadow_db
from src.shadow.query import search_blocks_fts
from src.shadow.sync import sync_page_to_shadow


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _seed(tmp_path: Path) -> Path:
    page = tmp_path / "pages" / "FtsDemo.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "- alpha shadow needle here\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        "- unrelated beta content\n"
        "  id:: 22222222-2222-4222-8222-222222222222\n",
        encoding="utf-8",
    )
    sync_page_to_shadow(tmp_path, page)
    return page


def test_search_blocks_fts_matches_uuid(tmp_path: Path) -> None:
    _seed(tmp_path)
    conn = open_shadow_db(tmp_path)
    try:
        hits = search_blocks_fts(conn, "shadow")
        assert len(hits) == 1
        assert hits[0].block_uuid == "11111111-1111-4111-8111-111111111111"
        assert "needle" in hits[0].content
    finally:
        conn.close()


def test_search_blocks_fts_empty_query(tmp_path: Path) -> None:
    _seed(tmp_path)
    conn = open_shadow_db(tmp_path)
    try:
        assert search_blocks_fts(conn, "   ") == []
    finally:
        conn.close()


def test_search_blocks_fts_respects_limit(tmp_path: Path) -> None:
    page = tmp_path / "pages" / "Many.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"- token shared word {i}\n  id:: {i:08x}-1111-4111-8111-111111111111\n" for i in range(5)
    ]
    page.write_text("".join(lines), encoding="utf-8")
    sync_page_to_shadow(tmp_path, page)

    conn = open_shadow_db(tmp_path)
    try:
        hits = search_blocks_fts(conn, "shared", limit=2)
        assert len(hits) == 2
    finally:
        conn.close()
