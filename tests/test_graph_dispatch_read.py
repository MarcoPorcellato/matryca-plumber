"""Tests for dispatch_read handler extraction (issue #59 slice)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.agent.dispatch_read_handlers import (
    dispatch_read_target,
    handle_read_subtree,
)
from src.agent.graph_dispatch import dispatch_read
from src.config import MatrycaWikiConfig


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
