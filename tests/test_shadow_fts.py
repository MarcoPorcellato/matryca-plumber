"""Tests for shadow FTS5 query module (#183)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.shadow.connection import open_shadow_db
from src.shadow.fts_format import FtsQueryValidationError
from src.shadow.query import prepare_fts_user_query, search_blocks_fts
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


def test_prepare_fts_user_query_quotes_natural_hyphen_compounds() -> None:
    assert prepare_fts_user_query("state-of-the-art") == '"state-of-the-art"'
    assert prepare_fts_user_query("needle state-of-the-art") == 'needle "state-of-the-art"'
    assert prepare_fts_user_query("alpha OR beta") == "alpha OR beta"
    assert prepare_fts_user_query('"state-of-the-art"') == '"state-of-the-art"'


def test_validate_fts_match_query_rejects_overlong_input() -> None:
    from src.shadow.fts_format import MAX_FTS_MATCH_QUERY_CHARS, validate_fts_match_query

    validate_fts_match_query("n" * MAX_FTS_MATCH_QUERY_CHARS)
    with pytest.raises(FtsQueryValidationError, match="exceeds max length"):
        validate_fts_match_query("n" * (MAX_FTS_MATCH_QUERY_CHARS + 1))


def test_search_blocks_fts_hyphenated_user_query(tmp_path: Path) -> None:
    page = tmp_path / "pages" / "Hyphen.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "- state-of-the-art needle\n  id:: 66666666-6666-4666-8666-666666666666\n",
        encoding="utf-8",
    )
    sync_page_to_shadow(tmp_path, page)
    conn = open_shadow_db(tmp_path)
    try:
        hits = search_blocks_fts(conn, "state-of-the-art")
        assert len(hits) == 1
    finally:
        conn.close()
