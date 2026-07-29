"""Per-page quarantine contract for the Shadow read cache.

The defect being fixed: one page whose bounded parse exceeds the budget used to abort
the entire rebuild, leaving a graph of thousands of pages with no read cache at all.
Quarantine parks that page instead, so the rest of the graph is cached and reads for
the parked page fall back to Markdown — which remains authoritative either way.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.health import (
    ShadowHealthState,
    resolve_shadow_health,
    shadow_meta_matches_page_rows,
)
from src.shadow.meta import META_LAST_SYNC_ERROR, META_QUARANTINED_PAGE_COUNT, get_meta
from src.shadow.quarantine import (
    clear_quarantined_page,
    is_page_quarantined,
    normalize_quarantine_reason,
    quarantined_file_paths,
    quarantined_page_count,
    record_quarantined_page,
)
from src.shadow.schema import apply_shadow_schema
from src.shadow.state_api import resolve_shadow_db_state_for_api

PAGE_BODY = "- alpha\n- beta\n"


@pytest.fixture
def graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "graph"
    (root / "pages").mkdir(parents=True)
    (root / "journals").mkdir(parents=True)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    return root


def _write_pages(root: Path, count: int) -> None:
    for i in range(count):
        (root / "pages" / f"page{i}.md").write_text(PAGE_BODY, encoding="utf-8")


def _fail_parse_for(monkeypatch: pytest.MonkeyPatch, doomed: set[str], error: str) -> None:
    """Make bounded parsing fail for specific page filenames, succeed for the rest."""
    import src.shadow.sync as sync_module

    # Take the real callable from the module that defines it. `sync` imports the name
    # for its own use rather than re-exporting it, so reading it back off `sync` is not
    # a supported access path even though the patch below must target `sync`, which is
    # where the call is resolved.
    from src.graph.bounded_ast_graph import parse_graph_page_bounded as real

    class _Failure:
        error = ""
        content_hash = "deadbeef"
        byte_count = 336260
        line_count = 3494

    def fake(path: Path, root: Path):  # type: ignore[no-untyped-def]
        if path.name in doomed:
            failure = _Failure()
            failure.error = error
            return type("R", (), {"ok": False, "page": None, "failure": failure})()
        return real(path, root)

    monkeypatch.setattr(sync_module, "parse_graph_page_bounded", fake)


# --- unit level -------------------------------------------------------------------


def _conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    apply_shadow_schema(connection)
    return connection


def test_reason_vocabulary_is_closed() -> None:
    assert normalize_quarantine_reason("timeout") == "parse_timeout"
    assert normalize_quarantine_reason("parse_timeout") == "parse_timeout"
    assert normalize_quarantine_reason("something weird") == "parse_error"
    assert normalize_quarantine_reason(None) == "parse_error"


def test_record_then_clear_round_trip() -> None:
    connection = _conn()
    record_quarantined_page(
        connection,
        "pages/big.md",
        reason="parse_timeout",
        byte_count=336260,
        line_count=3494,
        now="2026-07-27T00:00:00Z",
    )
    assert is_page_quarantined(connection, "pages/big.md")
    assert quarantined_page_count(connection) == 1
    assert quarantined_file_paths(connection) == ["pages/big.md"]

    clear_quarantined_page(connection, "pages/big.md")
    assert not is_page_quarantined(connection, "pages/big.md")
    assert quarantined_page_count(connection) == 0


def test_repeated_failure_increments_attempts_without_duplicating() -> None:
    connection = _conn()
    for _ in range(3):
        record_quarantined_page(
            connection,
            "pages/big.md",
            reason="parse_timeout",
            byte_count=1,
            line_count=1,
            now="2026-07-27T00:00:00Z",
        )
    attempts = connection.execute(
        "SELECT attempt_count FROM quarantined_pages WHERE file_path = ?", ("pages/big.md",)
    ).fetchone()[0]
    assert quarantined_page_count(connection) == 1
    assert attempts == 3


def test_health_invariant_counts_quarantined_pages_as_accounted_for() -> None:
    """indexed + quarantined == source is healthy; an unexplained gap is not."""
    assert shadow_meta_matches_page_rows(
        indexed_page_count="8",
        source_page_count="10",
        actual_page_count=8,
        quarantined_page_count=2,
    )
    assert not shadow_meta_matches_page_rows(
        indexed_page_count="8",
        source_page_count="10",
        actual_page_count=8,
        quarantined_page_count=1,
    )


def test_health_invariant_default_preserves_pre_quarantine_behaviour() -> None:
    """A database written before quarantine existed must evaluate exactly as before."""
    assert shadow_meta_matches_page_rows(
        indexed_page_count="10", source_page_count="10", actual_page_count=10
    )
    assert not shadow_meta_matches_page_rows(
        indexed_page_count="8", source_page_count="10", actual_page_count=8
    )


# --- rebuild level ----------------------------------------------------------------


def test_one_over_budget_page_no_longer_disables_the_whole_cache(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression this feature exists for."""
    _write_pages(graph, 10)
    _fail_parse_for(monkeypatch, {"page3.md"}, "timeout")

    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]) == 9
        assert quarantined_file_paths(conn) == ["pages/page3.md"]
        assert get_meta(conn, META_QUARANTINED_PAGE_COUNT) == "1"
    finally:
        conn.close()

    assert resolve_shadow_health(graph) == ShadowHealthState.READY


def test_quarantined_page_is_absent_from_pages_not_empty_in_it(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reads must be able to tell 'not cached' from 'cached and has no blocks'."""
    _write_pages(graph, 3)
    _fail_parse_for(monkeypatch, {"page1.md"}, "timeout")
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        row = conn.execute(
            "SELECT 1 FROM pages WHERE file_path = ?", ("pages/page1.md",)
        ).fetchone()
        assert row is None, "a quarantined page must not exist as an empty page row"
        assert is_page_quarantined(conn, "pages/page1.md")
    finally:
        conn.close()


def test_state_api_reports_quarantine_while_staying_ready(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pages(graph, 6)
    _fail_parse_for(monkeypatch, {"page0.md", "page5.md"}, "timeout")
    rebuild_shadow_from_graph(graph)

    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.state == "ready"
    assert snap.not_ready_reason is None
    assert snap.quarantined_page_count == 2
    assert snap.lag_pages == 0, "parked pages are a settled decision, not pending work"


def test_page_is_released_when_it_parses_again(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pages(graph, 4)
    _fail_parse_for(monkeypatch, {"page2.md"}, "timeout")
    rebuild_shadow_from_graph(graph)
    assert resolve_shadow_db_state_for_api(graph).quarantined_page_count == 1

    monkeypatch.undo()
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    rebuild_shadow_from_graph(graph)

    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.quarantined_page_count == 0
    assert snap.state == "ready"


def test_disabling_quarantine_restores_strict_rebuild(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kill switch must bring back the previous fail-the-whole-rebuild behaviour."""
    from src.shadow.errors import ShadowPageParseError

    _write_pages(graph, 5)
    _fail_parse_for(monkeypatch, {"page1.md"}, "timeout")
    monkeypatch.setenv("MATRYCA_SHADOW_QUARANTINE_ENABLED", "false")

    with pytest.raises(ShadowPageParseError):
        rebuild_shadow_from_graph(graph)

    assert resolve_shadow_health(graph) != ShadowHealthState.READY


def test_quarantine_leaves_the_global_sync_error_clean(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parking a page is a normal outcome, not a fault of the cache as a whole.

    Writing the per-page diagnostic into the global error slot would flip health to ERROR
    and put the operator back in the situation quarantine exists to end.
    """
    _write_pages(graph, 4)
    _fail_parse_for(monkeypatch, {"page0.md"}, "timeout")
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_SYNC_ERROR) == ""
    finally:
        conn.close()
    assert resolve_shadow_db_state_for_api(graph).last_sync_error is None


def test_quarantine_rows_carry_no_page_content(
    graph: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Privacy contract: only a relative path plus counters may be persisted."""
    (graph / "pages" / "Secret Project Notes.md").write_text(
        "- confidential body text\n", encoding="utf-8"
    )
    _fail_parse_for(monkeypatch, {"Secret Project Notes.md"}, "timeout")
    rebuild_shadow_from_graph(graph)

    conn = sqlite3.connect(shadow_db_path(graph))
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(quarantined_pages)")}
        assert columns == {
            "file_path",
            "reason",
            "byte_count",
            "line_count",
            "attempt_count",
            "first_quarantined_at",
            "last_attempt_at",
        }
        row = conn.execute("SELECT * FROM quarantined_pages").fetchone()
        assert "confidential" not in " ".join(str(value) for value in row)
    finally:
        conn.close()
