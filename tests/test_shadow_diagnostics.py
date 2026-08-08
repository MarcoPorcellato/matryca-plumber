"""Tests for content-free Shadow operational diagnostics."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from src.shadow.diagnostics import shadow_diagnostics_snapshot
from src.shadow.meta import META_GENERATION, META_LAST_INCREMENTAL_SYNC_AT, set_meta
from src.shadow.quarantine import record_quarantined_page
from src.shadow.schema import apply_shadow_schema


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    apply_shadow_schema(connection)
    return connection


def test_shadow_diagnostics_empty_snapshot_is_deterministic() -> None:
    connection = _connection()
    snapshot = shadow_diagnostics_snapshot(connection, now=datetime(2026, 8, 7, 10, tzinfo=UTC))

    assert snapshot.to_dict() == {
        "schema_version": 1,
        "generation": 0,
        "last_incremental_sync_at": None,
        "quarantined_page_count": 0,
        "quarantine_retry_count": 0,
        "current_timeout_attempt_count": 0,
        "current_error_attempt_count": 0,
        "max_quarantine_attempt_count": 0,
        "oldest_quarantine_age_seconds": None,
    }


def test_shadow_diagnostics_aggregate_quarantine_pressure_without_paths() -> None:
    connection = _connection()
    set_meta(connection, META_GENERATION, "7")
    set_meta(connection, META_LAST_INCREMENTAL_SYNC_AT, "2026-08-07T09:45:00Z")
    record_quarantined_page(
        connection,
        "pages/private.md",
        reason="parse_timeout",
        byte_count=100,
        line_count=5,
        now="2026-08-07T08:00:00+00:00",
    )
    record_quarantined_page(
        connection,
        "pages/private.md",
        reason="parse_timeout",
        byte_count=100,
        line_count=5,
        now="2026-08-07T09:00:00+00:00",
    )
    record_quarantined_page(
        connection,
        "journals/hidden.md",
        reason="parse_error",
        byte_count=200,
        line_count=10,
        now="2026-08-07T09:30:00+00:00",
    )

    before = connection.total_changes
    connection.execute("PRAGMA query_only = ON")
    snapshot = shadow_diagnostics_snapshot(connection, now=datetime(2026, 8, 7, 10, tzinfo=UTC))
    payload = snapshot.to_dict()

    assert snapshot.generation == 7
    assert snapshot.last_incremental_sync_at == "2026-08-07T09:45:00+00:00"
    assert snapshot.quarantined_page_count == 2
    assert snapshot.quarantine_retry_count == 1
    assert snapshot.current_timeout_attempt_count == 2
    assert snapshot.current_error_attempt_count == 1
    assert snapshot.max_quarantine_attempt_count == 2
    assert snapshot.oldest_quarantine_age_seconds == 7200
    assert connection.total_changes == before
    assert not ({"path", "graph_root", "query", "content"} & payload.keys())
    assert "private" not in repr(payload)
    assert "hidden" not in repr(payload)


def test_shadow_diagnostics_reject_naive_now_and_invalid_timestamps() -> None:
    connection = _connection()
    set_meta(connection, META_LAST_INCREMENTAL_SYNC_AT, "not-a-timestamp /private/leak")
    record_quarantined_page(
        connection,
        "pages/private.md",
        reason="parse_error",
        byte_count=0,
        line_count=0,
        now="not-a-timestamp",
    )

    snapshot = shadow_diagnostics_snapshot(connection, now=datetime(2026, 8, 7, 10, tzinfo=UTC))
    assert snapshot.last_incremental_sync_at is None
    assert snapshot.oldest_quarantine_age_seconds is None

    with pytest.raises(ValueError, match="timezone-aware"):
        shadow_diagnostics_snapshot(connection, now=datetime(2026, 8, 7, 10))
