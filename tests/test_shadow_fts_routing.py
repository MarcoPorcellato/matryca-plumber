"""Routing tests for shadow FTS5 in ``search_graph(bm25)`` (#250)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.dispatch_search_handlers import handle_search_bm25
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.fts_format import (
    FtsQueryValidationError,
    format_shadow_fts_markdown,
    resolve_bm25_search_markdown,
    validate_fts_match_query,
)
from src.shadow.meta import META_LAST_FULL_SYNC_COMPLETED, META_LAST_SYNC_ERROR, get_meta


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _seed_shadow_ready(graph: Path) -> None:
    _write_page(
        graph,
        "pages/FtsRoute.md",
        "- alpha shadow needle here\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        "- unrelated beta content\n"
        "  id:: 22222222-2222-4222-8222-222222222222\n",
    )
    rebuild_shadow_from_graph(graph)


def test_bm25_envelope_parity_shadow_vs_generational(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/A.md", "alpha needle token\n")
    _seed_shadow_ready(graph)

    shadow_md = resolve_bm25_search_markdown(graph, "needle", limit=10)
    with patch("src.shadow.fts_format.shadow_db_enabled", return_value=False):
        generational_md = resolve_bm25_search_markdown(graph, "needle", limit=10)

    for md in (shadow_md, generational_md):
        assert md.startswith("# Local page query")
        assert "- **Graph:**" in md
        assert "- **Query:**" in md
        assert "- **Mode:** `bm25`" in md
        assert "- **Matches:**" in md
        assert "## Ranked pages (BM25)" in md
    assert "block `" in shadow_md
    assert "FtsRoute.md" in shadow_md
    assert "block `" not in generational_md


@pytest.mark.asyncio
async def test_handle_search_bm25_uses_shadow_when_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))

    out = await handle_search_bm25(str(graph), "shadow")
    assert "block `11111111-1111-4111-8111-111111111111`" in out
    assert "FtsRoute.md" in out


@pytest.mark.asyncio
async def test_handle_search_bm25_flag_false_uses_generational_bm25(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Banana.md", "banana fruit banana\n")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    out = await handle_search_bm25(str(graph), "banana")
    assert "Banana.md" in out
    assert "block `" not in out


@pytest.mark.asyncio
async def test_handle_search_bm25_shadow_not_ready_falls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Cherry.md", "cherry cherry\n")
    _seed_shadow_ready(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            ("stale marker", META_LAST_SYNC_ERROR),
        )
        conn.commit()
    finally:
        conn.close()

    out = await handle_search_bm25(str(graph), "cherry")
    assert "Cherry.md" in out
    assert "block `" not in out


@pytest.mark.asyncio
async def test_handle_search_bm25_zero_hits_no_fallback(
    tmp_path: Path,
) -> None:
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)

    out = await handle_search_bm25(str(graph), "zzznomatchzz")
    assert "- **Matches:** 0" in out
    assert "_No lexical overlap" in out
    assert "Invalid FTS query" not in out


@pytest.mark.asyncio
async def test_handle_search_bm25_invalid_fts_query_no_fallback(
    tmp_path: Path,
) -> None:
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)

    out = await handle_search_bm25(str(graph), '"unclosed')
    assert "Invalid FTS query" in out
    assert "## Ranked pages (BM25)" not in out


@pytest.mark.asyncio
async def test_handle_search_bm25_backend_failure_falls_back(
    tmp_path: Path,
) -> None:
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Delta.md", "delta delta\n")
    _seed_shadow_ready(graph)

    with patch(
        "src.shadow.fts_format.format_shadow_fts_markdown",
        side_effect=sqlite3.OperationalError("database disk image is malformed"),
    ):
        out = await handle_search_bm25(str(graph), "delta")
    assert "Delta.md" in out
    assert "Invalid FTS query" not in out


@pytest.mark.asyncio
async def test_handle_search_bm25_empty_keyword_validation(
    tmp_path: Path,
) -> None:
    out = await handle_search_bm25(str(tmp_path), "  ")
    assert "method=bm25" in out


def test_format_shadow_fts_markdown_ready_meta(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()

    md = format_shadow_fts_markdown(graph, "shadow")
    assert "needle" in md.lower()


def test_validate_fts_match_query_rejects_unbalanced_quotes() -> None:
    with pytest.raises(FtsQueryValidationError):
        validate_fts_match_query('"bad')
