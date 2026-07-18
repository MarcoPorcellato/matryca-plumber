"""Read-port selector and shadow subtree adapter tests (#255)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import (
    MarkdownGraphRepository,
    get_graph_read_port,
)
from src.agent.shadow_graph_repository import ShadowGraphRepository
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState
from src.shadow.meta import META_LAST_SYNC_ERROR
from src.shadow.subtree import query_subtree_by_block_uuid


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> None:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _seed_ready(graph: Path, block_id: str) -> None:
    _write_page(
        graph,
        "pages/Port.md",
        f"- Root line\n  id:: {block_id}\n  - child one\n  - child two\n",
    )
    rebuild_shadow_from_graph(graph)


def _query(block_id: str) -> str:
    return json.dumps({"page": "Port", "block_uuid": block_id})


def _extract_excerpt(markdown: str) -> str:
    marker = "```markdown\n"
    start = markdown.find(marker)
    if start == -1:
        return markdown
    start += len(marker)
    end = markdown.find("\n```", start)
    return markdown[start:end] if end != -1 else markdown[start:]


def test_get_graph_read_port_flag_false_returns_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)


def test_get_graph_read_port_not_ready_returns_markdown(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_ready(graph, block_id)
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            ("stale", META_LAST_SYNC_ERROR),
        )
        conn.commit()
    finally:
        conn.close()

    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)


def test_get_graph_read_port_ready_returns_shadow(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_ready(graph, block_id)

    port = get_graph_read_port(graph)
    assert isinstance(port, ShadowGraphRepository)


def test_shadow_subtree_parity_with_markdown_repository(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_ready(graph, block_id)
    query = _query(block_id)

    markdown = read_subtree_markdown(str(graph), query)
    shadow = ShadowGraphRepository().read_subtree_markdown(graph, query)

    assert shadow.startswith("# Subtree excerpt")
    assert _extract_excerpt(shadow).rstrip("\n") == _extract_excerpt(markdown).rstrip("\n")


def test_shadow_subtree_not_found_no_markdown_fallback(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    _seed_ready(graph, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    missing = "00000000-0000-4000-8000-000000000099"
    query = _query(missing)

    with patch.object(MarkdownGraphRepository, "read_subtree_markdown") as markdown_read:
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)
        markdown_read.assert_not_called()

    assert f"Block `{missing}` not found on page `Port`" in out


def test_shadow_subtree_sqlite_error_falls_back_to_markdown(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_ready(graph, block_id)
    query = _query(block_id)

    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        side_effect=sqlite3.OperationalError("database disk image is malformed"),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)

    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


def test_shadow_subtree_truncation_notice_preserved(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(
        graph,
        "pages/Port.md",
        f"- root {'x' * 40}\n  id:: {block_id}\n  - child one padding\n  - child two padding\n",
    )
    rebuild_shadow_from_graph(graph)
    query = _query(block_id)

    original = query_subtree_by_block_uuid

    def _limited(
        conn: sqlite3.Connection,
        uuid: str,
        *,
        max_depth: int = 64,
        max_nodes: int = 500,
        max_output_bytes: int = 256_000,
    ) -> object:
        return original(
            conn,
            uuid,
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_output_bytes=80,
        )

    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        side_effect=_limited,
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)

    assert "[truncated: output byte limit exceeded]" in out
    assert "child two" not in _extract_excerpt(out)


def test_shadow_health_change_between_selection_and_query(tmp_path: Path) -> None:
    graph = _graph(tmp_path)
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _seed_ready(graph, block_id)
    query = _query(block_id)
    calls = 0

    def _health(_root: Path) -> ShadowHealthState:
        nonlocal calls
        calls += 1
        return ShadowHealthState.READY if calls == 1 else ShadowHealthState.ERROR

    with patch(
        "src.agent.shadow_graph_repository.resolve_shadow_health",
        side_effect=_health,
    ):
        port = get_graph_read_port(graph)
        assert isinstance(port, ShadowGraphRepository)
        out = port.read_subtree_markdown(graph, query)

    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


@pytest.mark.asyncio
async def test_shadow_spatial_read_delegates_to_markdown(tmp_path: Path) -> None:
    graph = _graph(tmp_path)

    async def fake_spatial(title: str, graph_path: str) -> str:
        assert title == "Note"
        assert graph_path == str(graph)
        return "# spatial"

    with patch(
        "src.agent.shadow_graph_repository.get_page_spatial_context",
        fake_spatial,
    ):
        body = await ShadowGraphRepository().read_page_spatial_markdown(graph, "Note")

    assert body == "# spatial"
