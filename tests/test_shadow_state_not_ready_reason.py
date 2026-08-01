"""Contract tests for the ``shadow_db.not_ready_reason`` state field.

The field explains *why* the read cache is not serving accelerated reads, so an
operator does not have to infer it from daemon logs. It must stay content-free:
no page titles, vault paths, or block identifiers may ever reach it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    set_meta,
)
from src.shadow.schema import SHADOW_SCHEMA_VERSION, apply_shadow_schema
from src.shadow.state_api import (
    ShadowDbNotReadyReason,
    _not_ready_reason_from_meta,
    resolve_shadow_db_state_for_api,
)


@pytest.fixture
def graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "graph"
    (root / "pages").mkdir(parents=True)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    return root


def _meta(**overrides: str | None) -> dict[str, str | None]:
    base: dict[str, str | None] = {
        META_LAST_SYNC_ERROR: None,
        META_LAST_FULL_SYNC_COMPLETED: "true",
        META_INDEXED_PAGE_COUNT: "3",
        META_SOURCE_PAGE_COUNT: "3",
    }
    base.update(overrides)
    return base


def test_ready_meta_yields_no_reason() -> None:
    assert _not_ready_reason_from_meta(_meta(), actual_page_count=3) is None


def test_aborted_bootstrap_reports_full_sync_incomplete() -> None:
    """The page-parse budget abort rolls back the rebuild, leaving completed=false."""
    reason = _not_ready_reason_from_meta(
        _meta(**{META_LAST_FULL_SYNC_COMPLETED: "false"}), actual_page_count=0
    )
    assert reason == "full_sync_incomplete"


def test_sync_error_takes_precedence_over_incomplete() -> None:
    reason = _not_ready_reason_from_meta(
        _meta(**{META_LAST_SYNC_ERROR: "boom", META_LAST_FULL_SYNC_COMPLETED: "false"}),
        actual_page_count=0,
    )
    assert reason == "sync_error"


def test_count_disagreement_reports_page_count_mismatch() -> None:
    reason = _not_ready_reason_from_meta(_meta(), actual_page_count=2)
    assert reason == "page_count_mismatch"


def test_missing_database_reports_not_bootstrapped(graph: Path) -> None:
    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.state == "stale"
    assert snap.not_ready_reason == "not_bootstrapped"


def test_disabled_flag_reports_no_reason(graph: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Flag-off is a deliberate choice, not a failure: it needs no explanation."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.state == "disabled"
    assert snap.not_ready_reason is None


def test_schema_mismatch_reports_schema_version_mismatch(graph: Path) -> None:
    from src.shadow.connection import shadow_db_path

    db_path = shadow_db_path(graph)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        apply_shadow_schema(conn)
        set_meta(conn, META_SCHEMA_VERSION, str(SHADOW_SCHEMA_VERSION + 1))
        conn.commit()
    finally:
        conn.close()

    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.state == "error"
    assert snap.not_ready_reason == "schema_version_mismatch"


def test_every_reason_code_is_content_free() -> None:
    """Reason codes are a closed vocabulary; none may interpolate runtime data."""
    codes = set(ShadowDbNotReadyReason.__args__)  # type: ignore[attr-defined]
    assert codes == {
        "not_bootstrapped",
        "bootstrap_in_progress",
        "database_unreadable",
        "schema_version_mismatch",
        "sync_error",
        "full_sync_incomplete",
        "page_count_mismatch",
        "cache_unavailable",
    }
    for code in codes:
        assert code.islower()
        assert "/" not in code and "\\" not in code
