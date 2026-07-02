"""Parity tests for GraphReadPort / MarkdownGraphRepository (v2 Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port


def test_get_graph_read_port_returns_markdown_adapter(tmp_path: Path) -> None:
    port = get_graph_read_port(tmp_path)
    assert isinstance(port, MarkdownGraphRepository)


def test_read_subtree_markdown_port_matches_direct_helper(tmp_path: Path) -> None:
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Demo.md").write_text(
        f"- Root\n  id:: {block_id}\n  - child\n",
        encoding="utf-8",
    )
    query = json.dumps({"page": "Demo", "block_uuid": block_id})
    repo = MarkdownGraphRepository()
    via_port = repo.read_subtree_markdown(tmp_path, query)
    via_helper = read_subtree_markdown(str(tmp_path), query)
    assert via_port == via_helper
    assert "child" in via_port


@pytest.mark.asyncio
async def test_read_page_spatial_port_delegates_to_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Note.md").write_text("- hello\n", encoding="utf-8")

    async def fake_spatial(title: str, graph_path: str) -> str:
        assert title == "Note"
        assert graph_path == str(tmp_path)
        return "# spatial body"

    monkeypatch.setattr(
        "src.agent.markdown_graph_repository.get_page_spatial_context",
        fake_spatial,
    )
    repo = MarkdownGraphRepository()
    body = await repo.read_page_spatial_markdown(tmp_path, "Note")
    assert body == "# spatial body"
