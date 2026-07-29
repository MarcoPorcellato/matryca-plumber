"""Bounded page parsing contracts for Shadow ingestion (#297 PR2C).

These characterize **strict** mode, where any page that cannot be parsed within the
budget aborts the whole rebuild. Strict mode is no longer the default — see
`test_shadow_quarantine.py` for the default per-page quarantine behaviour — but it
remains supported via `MATRYCA_SHADOW_QUARANTINE_ENABLED=false`, so its containment,
rollback, and privacy guarantees are still asserted here in full.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from loguru import logger
from src.graph.bounded_page_parse import BoundedParseResult, ParseMode, content_hash16
from src.graph.post_write import PageWrittenEvent
from src.shadow.bootstrap import (
    ensure_shadow_runtime_at_startup,
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
    shadow_needs_bootstrap,
)
from src.shadow.connection import open_shadow_db
from src.shadow.errors import ShadowPageParseError
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import META_LAST_SYNC_ERROR, get_meta
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.sync import _on_shadow_page_written, sync_page_into_connection, sync_page_to_shadow

from tests.a_cli_01_generator import generate_pathological_page


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_QUARANTINE_ENABLED", "false")
    reset_shadow_runtime_state_for_tests()
    reset_shadow_bootstrap_checked_for_tests()


def _graph(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "pages").mkdir(parents=True)
    return root


def _write_page(root: Path, name: str, text: str) -> Path:
    path = root / "pages" / name
    path.write_text(text, encoding="utf-8")
    return path


def _failed_parse(text: str, *, category: str = "timeout") -> BoundedParseResult:
    return BoundedParseResult(
        ok=False,
        timed_out=category == "timeout",
        elapsed_s=2.0,
        content_hash=content_hash16(text),
        byte_count=len(text.encode("utf-8")),
        line_count=text.count("\n") + (0 if text.endswith("\n") else 1),
        mode="stack",
        error=category,
    )


def test_shadow_sync_uses_bounded_stack_mode(tmp_path: Path) -> None:
    root = _graph(tmp_path)
    page = _write_page(root, "Alpha.md", "- alpha\n")
    from src.graph.bounded_page_parse import parse_page_text_bounded as real_parse

    seen_modes: list[str] = []

    def _spy(
        text: str,
        *,
        mode: ParseMode = "logos",
        page_title: str = "Page",
        tab_size: int = 2,
        timeout_s: float | None = None,
    ) -> BoundedParseResult:
        seen_modes.append(mode)
        return real_parse(
            text,
            mode=mode,
            page_title=page_title,
            tab_size=tab_size,
            timeout_s=timeout_s,
        )

    conn = open_shadow_db(root)
    try:
        with patch("src.graph.bounded_ast_graph.parse_page_text_bounded", side_effect=_spy):
            sync_page_into_connection(conn, root, page)
        conn.commit()
    finally:
        conn.close()

    assert seen_modes == ["stack"]


def test_full_rebuild_rolls_back_and_records_only_bounded_parse_diagnostic(
    tmp_path: Path,
) -> None:
    root = _graph(tmp_path)
    safe = _write_page(root, "Safe.md", "- safe\n")
    rebuild_shadow_from_graph(root)
    bad_text = "- SECRET-BODY-MUST-NOT-LEAK\n"
    bad = _write_page(root, "PrivateTitle.md", bad_text)
    from src.graph.bounded_page_parse import parse_page_text_bounded as real_parse

    def _parse(
        text: str,
        *,
        mode: ParseMode = "logos",
        page_title: str = "Page",
        tab_size: int = 2,
        timeout_s: float | None = None,
    ) -> BoundedParseResult:
        if text == bad_text:
            return _failed_parse(text, category="RuntimeError: SECRET-BODY-MUST-NOT-LEAK")
        return real_parse(
            text,
            mode=mode,
            page_title=page_title,
            tab_size=tab_size,
            timeout_s=timeout_s,
        )

    with (
        patch("src.graph.bounded_ast_graph.parse_page_text_bounded", side_effect=_parse),
        pytest.raises(ShadowPageParseError),
    ):
        rebuild_shadow_from_graph(root)

    conn = open_shadow_db(root)
    try:
        titles = {str(row[0]) for row in conn.execute("SELECT title FROM pages")}
        error = get_meta(conn, META_LAST_SYNC_ERROR) or ""
    finally:
        conn.close()

    assert titles == {"Safe"}
    assert "category=parse_error" in error
    assert "content_hash=" in error
    assert "byte_count=" in error
    assert "line_count=" in error
    assert "mode=stack" in error
    assert len(error) <= 200
    assert bad.name not in error
    assert "PrivateTitle" not in error
    assert "SECRET-BODY-MUST-NOT-LEAK" not in error
    assert str(root) not in error
    assert resolve_shadow_health(root) is ShadowHealthState.ERROR
    assert safe.is_file()


def test_incremental_parse_failure_preserves_rows_and_marks_global_error(
    tmp_path: Path,
) -> None:
    root = _graph(tmp_path)
    page = _write_page(root, "Alpha.md", "- old content\n")
    rebuild_shadow_from_graph(root)
    page.write_text("- NEW-PRIVATE-CONTENT\n", encoding="utf-8")
    new_text = page.read_text(encoding="utf-8")

    with (
        patch(
            "src.graph.bounded_ast_graph.parse_page_text_bounded",
            return_value=_failed_parse(new_text),
        ),
        pytest.raises(ShadowPageParseError),
    ):
        sync_page_to_shadow(root, page)

    conn = open_shadow_db(root)
    try:
        content = str(conn.execute("SELECT content FROM blocks").fetchone()[0])
        error = get_meta(conn, META_LAST_SYNC_ERROR) or ""
    finally:
        conn.close()

    assert content == "old content"
    assert "NEW-PRIVATE-CONTENT" not in error
    assert "category=timeout" in error
    assert resolve_shadow_health(root) is ShadowHealthState.ERROR
    assert shadow_needs_bootstrap(root) is True

    other = _write_page(root, "Other.md", "- ordinary incremental change\n")
    sync_page_to_shadow(root, other)
    conn = open_shadow_db(root)
    try:
        assert get_meta(conn, META_LAST_SYNC_ERROR) == error
    finally:
        conn.close()


def test_repaired_source_recovers_at_next_startup_rebuild(tmp_path: Path) -> None:
    root = _graph(tmp_path)
    page = _write_page(root, "Alpha.md", "- old content\n")
    rebuild_shadow_from_graph(root)
    page.write_text("- repaired content\n", encoding="utf-8")
    repaired_text = page.read_text(encoding="utf-8")

    with (
        patch(
            "src.graph.bounded_ast_graph.parse_page_text_bounded",
            return_value=_failed_parse(repaired_text),
        ),
        pytest.raises(ShadowPageParseError),
    ):
        sync_page_to_shadow(root, page)

    assert shadow_needs_bootstrap(root) is True
    ensure_shadow_runtime_at_startup(root)

    conn = open_shadow_db(root)
    try:
        error = get_meta(conn, META_LAST_SYNC_ERROR)
        content = str(conn.execute("SELECT content FROM blocks").fetchone()[0])
    finally:
        conn.close()

    assert error == ""
    assert content == "repaired content"
    assert resolve_shadow_health(root) is ShadowHealthState.READY


def test_shadow_source_contains_no_direct_stack_machine_parser_call() -> None:
    shadow_root = Path(__file__).resolve().parents[1] / "src" / "shadow"
    assert "StackMachineParser" not in "\n".join(
        path.read_text(encoding="utf-8") for path in shadow_root.glob("*.py")
    )


def test_real_pathological_page_rolls_back_full_rebuild_with_bounded_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MATRYCA_PAGE_PARSE_TIMEOUT_S", "2")
    root = _graph(tmp_path)
    _write_page(root, "Alpha.md", "- ordinary\n")
    _write_page(root, "Pathological.md", generate_pathological_page())

    with pytest.raises(ShadowPageParseError):
        rebuild_shadow_from_graph(root)

    conn = open_shadow_db(root)
    try:
        assert int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]) == 0
        error = get_meta(conn, META_LAST_SYNC_ERROR) or ""
    finally:
        conn.close()
    assert "category=timeout" in error
    assert "Pathological.md" not in error
    assert str(root) not in error
    assert resolve_shadow_health(root) is ShadowHealthState.ERROR


def test_real_pathological_incremental_keeps_last_good_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MATRYCA_PAGE_PARSE_TIMEOUT_S", "2")
    root = _graph(tmp_path)
    page = _write_page(root, "Alpha.md", "- last good content\n")
    rebuild_shadow_from_graph(root)
    page.write_text(generate_pathological_page(), encoding="utf-8")

    with pytest.raises(ShadowPageParseError):
        sync_page_to_shadow(root, page)

    conn = open_shadow_db(root)
    try:
        content = str(conn.execute("SELECT content FROM blocks").fetchone()[0])
        error = get_meta(conn, META_LAST_SYNC_ERROR) or ""
    finally:
        conn.close()
    assert content == "last good content"
    assert "category=timeout" in error
    assert "Alpha.md" not in error
    assert str(root) not in error
    assert resolve_shadow_health(root) is ShadowHealthState.ERROR


def test_parse_failure_handlers_log_no_vault_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _graph(tmp_path)
    page = _write_page(root, "PrivateTitle.md", "- secret\n")
    safe_error = ShadowPageParseError(
        "bounded page parse failed: category=timeout content_hash=0123456789abcdef"
    )
    monkeypatch.setattr(
        "src.shadow.bootstrap.sync_page_to_shadow", lambda *_args: (_ for _ in ()).throw(safe_error)
    )
    monkeypatch.setattr(
        "src.shadow.sync.sync_page_to_shadow", lambda *_args: (_ for _ in ()).throw(safe_error)
    )
    output = StringIO()
    sink = logger.add(output, format="{message} {extra}")
    try:
        handle_shadow_watchdog_change(root, page, "modified")
        _on_shadow_page_written(PageWrittenEvent(root, page, None))
    finally:
        logger.remove(sink)

    rendered = output.getvalue()
    assert "0123456789abcdef" in rendered
    assert "PrivateTitle.md" not in rendered
    assert str(root) not in rendered
