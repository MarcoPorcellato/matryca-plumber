"""Tests for shadow.sqlite connection helper (#181)."""

from __future__ import annotations

from pathlib import Path

from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.schema import SHADOW_SCHEMA_VERSION


def test_shadow_db_path_under_cache(tmp_path: Path) -> None:
    path = shadow_db_path(tmp_path)
    assert path == tmp_path / ".matryca_semantic_cache" / "shadow.sqlite"
    assert path.is_relative_to(tmp_path.resolve())


def test_open_shadow_db_creates_schema_version(tmp_path: Path) -> None:
    conn = open_shadow_db(tmp_path)
    try:
        row = conn.execute(
            "SELECT value FROM shadow_meta WHERE key = 'schema_version'",
        ).fetchone()
        assert row is not None
        assert row[0] == str(SHADOW_SCHEMA_VERSION)
        assert (tmp_path / ".matryca_semantic_cache" / "shadow.sqlite").is_file()
    finally:
        conn.close()


def test_open_shadow_db_idempotent(tmp_path: Path) -> None:
    first = open_shadow_db(tmp_path)
    first.close()
    second = open_shadow_db(tmp_path)
    try:
        tables = {
            r[0]
            for r in second.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            )
        }
        assert "pages" in tables
        assert "blocks" in tables
    finally:
        second.close()


def test_shadow_db_path_sandboxed_under_graph(tmp_path: Path) -> None:
    path = shadow_db_path(tmp_path)
    assert path.resolve().is_relative_to(tmp_path.resolve())
