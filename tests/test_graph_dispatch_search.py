"""Integration tests for ``dispatch_search`` routing."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.dispatch_search_handlers import dispatch_search_target, handle_search_bm25
from src.agent.graph_dispatch import dispatch_search


@pytest.mark.asyncio
async def test_dispatch_search_resolve_entity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Acme Corp.md").write_text("alias:: ACME, Acme Corporation\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))

    out = await dispatch_search("resolve_entity", "ACME")
    assert isinstance(out, dict)
    assert out.get("matched") is True
    assert out.get("canonical_page_title") == "Acme Corp"


@pytest.mark.asyncio
async def test_dispatch_search_missing_graph_path_bm25(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGSEQ_GRAPH_PATH", raising=False)
    out = await dispatch_search("bm25", "keyword")
    assert isinstance(out, str)
    assert "LOGSEQ_GRAPH_PATH" in out


@pytest.mark.asyncio
async def test_handle_search_bm25_empty_keyword(tmp_path: Path) -> None:
    out = await handle_search_bm25(str(tmp_path), "  ")
    assert "method=bm25" in out


@pytest.mark.asyncio
async def test_dispatch_search_target_journal_tasks_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    journals = tmp_path / "journals"
    journals.mkdir()
    (journals / "2026_07_01.md").write_text("- TODO item\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))

    out = await dispatch_search_target("journal_tasks", '{"days": 7}')
    assert isinstance(out, dict)
    assert out.get("ok") is True
    assert "task_review_markdown" in out
