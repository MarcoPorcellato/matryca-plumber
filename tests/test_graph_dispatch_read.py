"""Tests for dispatch_read handler extraction (issue #59 slice)."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from contextlib import suppress
from pathlib import Path

import pytest
from src.agent.dispatch_read_handlers import (
    dispatch_read_target,
    handle_read_journal_day,
    handle_read_subtree,
)
from src.agent.graph_dispatch import dispatch_read
from src.config import MatrycaWikiConfig
from src.shadow.connection import shadow_db_path

from tests.test_dashboard_job import _until


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")
async def test_dashboard_cancel_never_abandons_parent_computation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled dashboard must not leave an opaque parent thread computing."""
    from src.agent import dispatch_read_handlers as handlers

    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    owners: list[threading.Thread] = []

    def controlled_compute(*_args: object) -> str:
        owners.append(threading.current_thread())
        entered.set()
        try:
            if not release.wait(3):
                raise RuntimeError("synthetic rescue deadline")
            return "- synthetic dashboard\n"
        finally:
            finished.set()

    monkeypatch.setattr(handlers, "build_dashboard_markdown", controlled_compute)
    (tmp_path / "pages").mkdir()
    pending = asyncio.create_task(
        handlers.handle_read_dashboard(MatrycaWikiConfig(), str(tmp_path), "ignored")
    )
    try:
        await _until(lambda: entered.is_set() or pending.done())
        pending.cancel()
        with suppress(asyncio.CancelledError):
            await pending
        assert not entered.is_set() or finished.is_set(), "cancel abandoned dashboard computation"
    finally:
        release.set()
        await _until(lambda: not owners or finished.is_set())
        assert not owners or finished.is_set(), "synthetic fixture rescue failed"
        # The legacy executor owns this thread; its controlled computation has returned.


@pytest.mark.asyncio
async def test_dashboard_windows_legacy_route_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.agent import dispatch_read_handlers as handlers
    from src.agent.llm_context_payload import cap_llm_payload_chars

    monkeypatch.setattr(sys, "platform", "win32")
    body = "- synthetic" * 3000
    monkeypatch.setattr(handlers, "build_dashboard_markdown", lambda *_args: body)

    async def forbidden(*_args: object) -> str:
        pytest.fail("Windows entered POSIX dashboard path")

    monkeypatch.setattr(handlers, "run_dashboard_read", forbidden)
    assert await handlers.handle_read_dashboard(MatrycaWikiConfig(), "/synthetic", "ignored") == (
        cap_llm_payload_chars(body)
    )


@pytest.mark.asyncio
async def test_dashboard_unadmitted_platform_rejects_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.agent import dispatch_read_handlers as handlers

    monkeypatch.setattr(sys, "platform", "unadmitted")

    async def forbidden(*_args: object) -> str:
        pytest.fail("unadmitted platform launched dashboard")

    monkeypatch.setattr(handlers, "run_dashboard_read", forbidden)
    body = json.loads(await handlers.handle_read_dashboard(MatrycaWikiConfig(), "/synthetic", ""))
    assert body["code"] == "dashboard_platform_unsupported"


@pytest.mark.asyncio
async def test_dispatch_read_missing_graph_path_returns_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGSEQ_GRAPH_PATH", raising=False)
    body = await dispatch_read(MatrycaWikiConfig(), "page", "Any")
    assert "LOGSEQ_GRAPH_PATH is not set" in body


@pytest.mark.asyncio
async def test_dispatch_read_subtree_via_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    block_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Topic.md").write_text(
        f"- block\n  id:: {block_id}\n  - nested\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    query = json.dumps({"page": "Topic", "block_uuid": block_id})
    body = await dispatch_read_target(MatrycaWikiConfig(), "subtree", query)
    assert "nested" in body
    assert "Subtree excerpt" in body


@pytest.mark.asyncio
async def test_handle_read_subtree_empty_query_message() -> None:
    body = await handle_read_subtree(MatrycaWikiConfig(), "/tmp/graph", "  ")
    assert "target_type=subtree" in body


@pytest.mark.asyncio
async def test_dispatch_read_journal_day_reads_exact_canonical_journal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journal = tmp_path / "journals" / "2026_08_13.md"
    journal.parent.mkdir()
    journal.write_text("- TODO qualify daily brief\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))

    body = await dispatch_read_target(MatrycaWikiConfig(), "journal_day", "2026-08-13")

    assert '"shadow":"not_used"' in body
    assert "TODO qualify daily brief" in body


@pytest.mark.asyncio
async def test_handle_read_journal_day_invalid_date_is_explicit() -> None:
    body = await handle_read_journal_day(MatrycaWikiConfig(), "/tmp/graph", "yesterday")
    assert "journal_day_invalid_date" in body


@pytest.mark.asyncio
async def test_dispatch_read_shadow_status_is_content_free_and_does_not_create_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "pages").mkdir()
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    body = await dispatch_read_target(MatrycaWikiConfig(), "shadow_status", "ignored")

    payload = json.loads(body)
    assert payload["state"] == "disabled"
    assert payload["read_profile"]["profile"] == "shadow-read-profile"
    assert payload["read_profile"]["graph_id"] is None
    assert str(tmp_path) not in body
    assert not shadow_db_path(tmp_path).exists()
