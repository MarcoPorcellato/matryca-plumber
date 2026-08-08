"""Tests for shadow.sqlite connection helper (#181)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.connection import open_shadow_db, open_shadow_db_query_only, shadow_db_path
from src.shadow.schema import SHADOW_SCHEMA_VERSION


@pytest.fixture(autouse=True)
def _cache_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cache_root = tmp_path.parent / f"{tmp_path.name}-operator-cache"
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache_root))
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    return cache_root


def test_shadow_db_path_under_cache(tmp_path: Path, _cache_root: Path) -> None:
    expected = resolve_shadow_cache_location(
        tmp_path,
        env={"MATRYCA_CACHE_PATH": str(_cache_root)},
    )
    path = shadow_db_path(tmp_path)
    assert path == expected.database_path
    assert path == expected.shadow_dir / "shadow.sqlite"
    assert not path.is_relative_to(tmp_path.resolve())


def test_open_shadow_db_creates_schema_version(tmp_path: Path) -> None:
    conn = open_shadow_db(tmp_path)
    try:
        row = conn.execute(
            "SELECT value FROM shadow_meta WHERE key = 'schema_version'",
        ).fetchone()
        assert row is not None
        assert row[0] == str(SHADOW_SCHEMA_VERSION)
        assert shadow_db_path(tmp_path).is_file()
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


def test_open_shadow_db_query_only_requires_existing_database(
    tmp_path: Path,
    _cache_root: Path,
) -> None:
    location = resolve_shadow_cache_location(
        tmp_path,
        env={"MATRYCA_CACHE_PATH": str(_cache_root)},
    )

    with pytest.raises(sqlite3.OperationalError):
        open_shadow_db_query_only(tmp_path)

    assert not location.shadow_dir.exists()
    assert not location.database_path.exists()
    assert not location.shadow_db_wal_path.exists()
    assert not location.shadow_db_shm_path.exists()


def test_open_shadow_db_query_only_cannot_write_application_data(tmp_path: Path) -> None:
    writer = open_shadow_db(tmp_path)
    writer.close()
    location = resolve_shadow_cache_location(tmp_path)
    before = {path.name for path in location.shadow_dir.iterdir()}

    reader = open_shadow_db_query_only(tmp_path)
    try:
        assert reader.execute("PRAGMA query_only").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("CREATE TABLE query_path_must_not_write (id INTEGER)")
        schema = reader.execute(
            "SELECT value FROM shadow_meta WHERE key = 'schema_version'"
        ).fetchone()
        assert schema == (str(SHADOW_SCHEMA_VERSION),)
    finally:
        reader.close()

    after = {path.name for path in location.shadow_dir.iterdir()}
    assert after - before <= {"shadow.sqlite-wal", "shadow.sqlite-shm"}


def test_open_shadow_db_uses_only_external_cache_in_read_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _cache_root: Path,
) -> None:
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    connection = open_shadow_db(tmp_path)
    connection.close()

    location = resolve_shadow_cache_location(
        tmp_path,
        env={"MATRYCA_CACHE_PATH": str(_cache_root)},
    )
    assert location.database_path.is_file()
    assert sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*")) == before


def test_open_shadow_db_rejects_disabled_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _cache_root: Path,
) -> None:
    """Explicit disable flag prevents opening or creating the external cache DB."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    with pytest.raises(RuntimeError):
        open_shadow_db(tmp_path)

    assert not resolve_shadow_cache_location(
        tmp_path,
        env={"MATRYCA_CACHE_PATH": str(_cache_root)},
    ).shadow_dir.exists()


def test_shadow_db_path_resolves_outside_graph(tmp_path: Path) -> None:
    path = shadow_db_path(tmp_path)
    assert not path.resolve().is_relative_to(tmp_path.resolve())
