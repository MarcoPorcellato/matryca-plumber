"""Tests for dispatch_mutate handler extraction (issue #59 slice)."""

from __future__ import annotations

import pytest
from src.agent.dispatch_mutate_handlers import (
    handle_mutate_append_journal,
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
