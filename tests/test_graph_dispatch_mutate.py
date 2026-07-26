"""Tests for dispatch_mutate handler extraction (issue #59 slice)."""

from __future__ import annotations

import pytest
from src.agent.dispatch_mutate_handlers import (
    handle_mutate_append_journal,
    handle_mutate_generate_moc,
    mutate_error,
)
from src.agent.graph_dispatch import dispatch_mutate


@pytest.mark.asyncio
async def test_dispatch_mutate_missing_graph_path_write_outline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGSEQ_GRAPH_PATH", raising=False)
    out = await dispatch_mutate("write_outline", "parent-uuid", '{"text":"x","children":[]}')
    assert out.get("ok") is False
    assert out.get("code") == "graph_missing"
    assert "LOGSEQ_GRAPH_PATH" in str(out.get("hint", ""))


@pytest.mark.asyncio
async def test_handle_mutate_append_journal_payload_too_large() -> None:
    huge = "x" * 300_000
    out = await handle_mutate_append_journal("/tmp/graph", "", huge)
    assert out.get("ok") is False
    assert out.get("code") == "payload_too_large"


def test_mutate_error_shape() -> None:
    out = mutate_error("boom")
    assert out == {"ok": False, "error": "boom"}


@pytest.mark.asyncio
async def test_handle_mutate_generate_moc_requires_target() -> None:
    out = await handle_mutate_generate_moc("/tmp/graph", "", "")
    assert out.get("ok") is False
    assert "target" in str(out.get("error", ""))


@pytest.mark.asyncio
async def test_dispatch_mutate_generate_moc_dry_run(tmp_path: object) -> None:
    graph_root = str(tmp_path)
    pages = f"{graph_root}/pages"
    import os

    os.makedirs(pages, exist_ok=True)
    with open(f"{pages}/Project___Alpha.md", "w", encoding="utf-8") as fh:
        fh.write("tags:: \n\n- alpha\n")

    out = await handle_mutate_generate_moc(graph_root, "Project", '{"dry_run": true}')
    assert out.get("ok") is True
    assert out.get("dry_run") is True
    assert "markdown_preview" in out
