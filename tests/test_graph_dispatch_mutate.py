"""Tests for dispatch_mutate handler extraction (issue #59 slice)."""

from __future__ import annotations

import asyncio

import pytest
from src.agent.dispatch_mutate_handlers import (
    handle_mutate_append_journal,
    handle_mutate_generate_moc,
    handle_mutate_inject_query,
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


def _write_fixture_page(pages_dir: str) -> None:
    import os

    os.makedirs(pages_dir, exist_ok=True)
    with open(f"{pages_dir}/Project___Alpha.md", "w", encoding="utf-8") as fh:
        fh.write("tags:: \n\n- alpha\n")


@pytest.mark.asyncio
async def test_dispatch_mutate_generate_moc_dry_run(tmp_path: object) -> None:
    graph_root = str(tmp_path)
    pages = f"{graph_root}/pages"
    await asyncio.to_thread(_write_fixture_page, pages)

    out = await handle_mutate_generate_moc(graph_root, "Project", '{"dry_run": true}')
    assert out.get("ok") is True
    assert out.get("dry_run") is True
    assert "markdown_preview" in out


@pytest.mark.asyncio
async def test_handle_mutate_inject_query_dry_run_preserves_validation_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.agent.graph_dispatch._resolve_write_parent_target",
        lambda _graph_path, _target: (object(), None, []),
    )

    valid = await handle_mutate_inject_query(
        "/tmp/graph",
        "parent-uuid",
        '{"query_edn":"{:query [:find ?a]}","dry_run":true}',
    )
    invalid = await handle_mutate_inject_query(
        "/tmp/graph",
        "parent-uuid",
        '{"query_edn":"{:query [(]}","dry_run":true}',
    )

    assert valid["ok"] is True
    assert valid["dry_run"] is True
    assert valid["markdown"] == "#+BEGIN_QUERY\n{:query [:find ?a]}\n#+END_QUERY"
    assert invalid["ok"] is False
    assert "unbalanced brackets" in invalid["error"]
