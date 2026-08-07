"""v2.0-alpha hardening — Axis 3: Routing & fallback (audit probes).

Read-only on ``src/`` — temporary vault fixtures exercise shadow read routing,
health gates, and Markdown/BM25 fallback contracts. Findings feed #261.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.dispatch_read_handlers import handle_read_subtree
from src.agent.dispatch_search_handlers import dispatch_search_target, handle_search_bm25
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port
from src.agent.shadow_graph_repository import ShadowGraphRepository
from src.config import MatrycaWikiConfig
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.fts_format import resolve_bm25_search_markdown
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    get_meta,
)
from src.shadow.runtime_state import (
    mark_bootstrapping,
    reset_shadow_runtime_state_for_tests,
)
from src.shadow.subtree import SubtreeQueryResult, SubtreeStatus


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()


@pytest.fixture(autouse=True)
def _shadow_cache_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path / "operator-cache"))


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> None:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _seed_shadow_ready(graph: Path, *, keyword: str = "needle") -> str:
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(
        graph,
        "pages/RouteProbe.md",
        f"- {keyword} shadow token here\n  id:: {block_uuid}\n",
    )
    rebuild_shadow_from_graph(graph)
    return block_uuid


def _subtree_query(block_uuid: str) -> str:
    return json.dumps({"page": "RouteProbe", "block_uuid": block_uuid})


def _extract_excerpt(markdown: str) -> str:
    marker = "```markdown\n"
    start = markdown.find(marker)
    if start == -1:
        return markdown
    start += len(marker)
    end = markdown.find("\n```", start)
    return markdown[start:end] if end != -1 else markdown[start:]


def _inject_sync_error(graph: Path, message: str = "axis-3 injected sync error") -> None:
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            (message, META_LAST_SYNC_ERROR),
        )
        conn.commit()
    finally:
        conn.close()


# --- A3-FLAG ---


def test_a3_flag_01_false_flag_never_creates_shadow_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3-FLAG-01: flag off → BM25 read path must not create ``shadow.sqlite``."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Plain.md", "plain generational needle\n")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    out = resolve_bm25_search_markdown(graph, "needle", limit=10)
    assert "Plain.md" in out
    assert not shadow_db_path(graph).exists()


def test_a3_flag_02_false_flag_subtree_uses_markdown_port(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3-FLAG-02: flag off → subtree reads use Markdown port only."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "22222222-2222-4222-8222-222222222222"
    _write_page(
        graph,
        "pages/Subtree.md",
        f"- root line\n  id:: {block_uuid}\n  - child\n",
    )
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)
    query = json.dumps({"page": "Subtree", "block_uuid": block_uuid})
    out = port.read_subtree_markdown(graph, query)
    assert "root line" in _extract_excerpt(out)
    assert not shadow_db_path(graph).exists()


# --- A3-HEALTH ---


@pytest.mark.asyncio
async def test_a3_health_01_disabled_routes_generational_bm25(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3-HEALTH-01: ``disabled`` health → generational BM25, no shadow block hits."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    out = await handle_search_bm25(str(graph), "needle")
    assert "RouteProbe.md" in out
    assert "block `" not in out


@pytest.mark.asyncio
async def test_a3_health_02_bootstrapping_routes_generational_bm25(
    tmp_path: Path,
) -> None:
    """A3-HEALTH-02: ``bootstrapping`` → no shadow FTS read."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    mark_bootstrapping(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.BOOTSTRAPPING

    out = await handle_search_bm25(str(graph), "needle")
    assert "RouteProbe.md" in out
    assert "block `" not in out


@pytest.mark.asyncio
async def test_a3_health_03_stale_db_removed_routes_generational_bm25(
    tmp_path: Path,
) -> None:
    """A3-HEALTH-03: ``stale`` (DB removed after ready) → generational BM25 fallback."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    shadow_db_path(graph).unlink()
    assert resolve_shadow_health(graph) == ShadowHealthState.STALE

    out = await handle_search_bm25(str(graph), "needle")
    assert "RouteProbe.md" in out
    assert "block `" not in out


@pytest.mark.asyncio
async def test_a3_health_04_error_meta_routes_generational_bm25(
    tmp_path: Path,
) -> None:
    """A3-HEALTH-04: ``error`` health → generational BM25 fallback."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    _inject_sync_error(graph)
    assert resolve_shadow_health(graph) == ShadowHealthState.ERROR

    out = await handle_search_bm25(str(graph), "needle")
    assert "RouteProbe.md" in out
    assert "block `" not in out


# --- A3-FTS ---


@pytest.mark.asyncio
async def test_a3_fts_01_zero_hits_no_generational_fallback(tmp_path: Path) -> None:
    """A3-FTS-01: zero FTS hits cannot prove freshness and fall back."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)

    out = await handle_search_bm25(str(graph), "zzznomatchzz")
    assert "- **Matches:** 0" in out
    assert "_No lexical overlap" in out
    assert "block `" not in out
    assert "`empty_result_unproven`" in out


@pytest.mark.asyncio
async def test_a3_fts_02_invalid_query_no_generational_fallback(tmp_path: Path) -> None:
    """A3-FTS-02: invalid FTS syntax → validation error, no BM25 fallback."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)

    out = await handle_search_bm25(str(graph), '"unclosed')
    assert "Invalid FTS query" in out
    assert "## Ranked pages (BM25)" not in out


@pytest.mark.asyncio
async def test_a3_fts_03_backend_failure_falls_back_to_generational_bm25(
    tmp_path: Path,
) -> None:
    """A3-FTS-03: shadow backend failure while healthy → generational BM25."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Fallback.md", "fallback fallback token\n")
    _seed_shadow_ready(graph, keyword="shadowonly")

    with patch(
        "src.shadow.fts_format.format_shadow_fts_markdown",
        side_effect=sqlite3.OperationalError("database disk image is malformed"),
    ):
        out = await handle_search_bm25(str(graph), "fallback")

    assert "Fallback.md" in out
    assert "Invalid FTS query" not in out


@pytest.mark.asyncio
async def test_a3_fts_04_public_errors_do_not_leak_vault_secrets(tmp_path: Path) -> None:
    """A3-FTS-04: validation/backend errors must not leak vault block content."""
    graph = _minimal_graph(tmp_path)
    secret = "vault-secret-must-not-appear-in-public-error"
    _write_page(
        graph,
        "pages/Secret.md",
        f"- {secret}\n  id:: 33333333-3333-4333-8333-333333333333\n",
    )
    _seed_shadow_ready(graph, keyword="shadowonly")

    invalid_out = await handle_search_bm25(str(graph), '"bad')
    assert secret not in invalid_out

    with patch(
        "src.shadow.fts_format.format_shadow_fts_markdown",
        side_effect=sqlite3.OperationalError("fts backend exploded"),
    ):
        backend_out = await handle_search_bm25(str(graph), "shadowonly")

    assert secret not in backend_out
    assert "fts backend exploded" not in backend_out


# --- A3-SUBTREE ---


def test_a3_subtree_01_missing_uuid_not_found_no_markdown_fallback(tmp_path: Path) -> None:
    """A3-SUBTREE-01: missing UUID → NOT_FOUND envelope, no Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    missing = "00000000-0000-4000-8000-000000000099"
    query = _subtree_query(missing)

    with patch.object(MarkdownGraphRepository, "read_subtree_markdown") as markdown_read:
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)
        markdown_read.assert_not_called()

    assert f"Block `{missing}` not found on page `RouteProbe`" in out
    assert block_uuid not in out


def test_a3_subtree_02_inconsistent_shadow_falls_back_to_markdown(tmp_path: Path) -> None:
    """A3-SUBTREE-02: inconsistent shadow graph → Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    query = _subtree_query(block_uuid)
    inconsistent = SubtreeQueryResult(
        status=SubtreeStatus.INCONSISTENT,
        anchor_uuid=block_uuid,
        page_id=1,
        nodes=(),
        excerpt_markdown="",
        detail="injected inconsistency",
    )

    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        return_value=inconsistent,
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)

    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


def test_a3_subtree_03_sqlite_error_falls_back_to_markdown(tmp_path: Path) -> None:
    """A3-SUBTREE-03: SQLite/backend failure → Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    query = _subtree_query(block_uuid)

    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        side_effect=sqlite3.OperationalError("database disk image is malformed"),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)

    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


def test_a3_subtree_04_truncation_notice_preserved(tmp_path: Path) -> None:
    """A3-SUBTREE-04: truncation limits and notice preserved on shadow path."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "44444444-4444-4444-8444-444444444444"
    _write_page(
        graph,
        "pages/Port.md",
        f"- root {'x' * 40}\n  id:: {block_uuid}\n  - child one padding\n  - child two padding\n",
    )
    rebuild_shadow_from_graph(graph)
    query = json.dumps({"page": "Port", "block_uuid": block_uuid})

    truncated = SubtreeQueryResult(
        status=SubtreeStatus.TRUNCATED,
        anchor_uuid=block_uuid,
        page_id=1,
        nodes=(),
        excerpt_markdown="- root\n  - child one\n… [truncated: output byte limit exceeded]\n",
    )
    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        return_value=truncated,
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)

    assert "[truncated: output byte limit exceeded]" in out
    assert "child two" not in _extract_excerpt(out)


# --- A3-SURFACE ---


@pytest.mark.asyncio
async def test_a3_surface_01_bm25_mcp_handler_matches_direct_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A3-SURFACE-01: MCP ``dispatch_search_target(bm25)`` ≡ direct resolver envelope."""
    graph = _minimal_graph(tmp_path)
    _seed_shadow_ready(graph)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))

    direct = resolve_bm25_search_markdown(graph, "needle", limit=10)
    handler = await handle_search_bm25(str(graph), "needle")
    dispatched_raw = await dispatch_search_target("bm25", "needle")
    assert isinstance(dispatched_raw, str)
    dispatched = dispatched_raw

    for out in (direct, handler, dispatched):
        assert out.startswith("# Local page query")
        assert "- **Mode:** `bm25`" in out
        assert "block `11111111-1111-4111-8111-111111111111`" in out
    assert handler == dispatched


@pytest.mark.asyncio
async def test_a3_surface_02_subtree_handler_matches_port_and_selector_is_side_effect_free(
    tmp_path: Path,
) -> None:
    """A3-SURFACE-02: CLI handler ≡ port; selector must not create shadow artifacts."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    query = _subtree_query(block_uuid)

    port_before = get_graph_read_port(graph)
    port_again = get_graph_read_port(graph)
    assert type(port_before) is type(port_again)
    assert isinstance(port_before, ShadowGraphRepository)

    via_port = port_before.read_subtree_markdown(graph, query)
    via_handler = await handle_read_subtree(MatrycaWikiConfig(), str(graph), query)

    assert _extract_excerpt(via_port).rstrip("\n") == _extract_excerpt(via_handler).rstrip("\n")


def test_a3_health_change_between_port_selection_and_subtree_query(
    tmp_path: Path,
) -> None:
    """Axis-3 tracker: health flip after port selection → Markdown fallback on query."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    query = _subtree_query(block_uuid)
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


def _child_bm25_with_flag_false(graph_str: str, keyword: str, queue: mp.Queue[str]) -> None:
    import os

    os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "false"
    from src.shadow.fts_format import resolve_bm25_search_markdown

    queue.put(resolve_bm25_search_markdown(graph_str, keyword, limit=10))


def test_a3_flag_cross_process_false_flag_uses_generational_bm25(
    tmp_path: Path,
) -> None:
    """Axis-3 tracker: per-process flag off must not read parent shadow DB."""
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Cross.md", "cross process needle token\n")
    _seed_shadow_ready(graph, keyword="shadowonly")

    ctx = mp.get_context("spawn")
    queue: mp.Queue[str] = ctx.Queue()
    proc = ctx.Process(
        target=_child_bm25_with_flag_false,
        args=(str(graph), "needle", queue),
    )
    proc.start()
    proc.join(timeout=30)
    assert proc.exitcode == 0
    out = queue.get(timeout=5)
    assert "Cross.md" in out
    assert "block `" not in out


def test_a3_health_meta_pages_mismatch_subtree_falls_back(
    tmp_path: Path,
) -> None:
    """Axis-3 tracker: meta/pages mismatch (``stale``) → Markdown subtree port."""
    graph = _minimal_graph(tmp_path)
    block_uuid = _seed_shadow_ready(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute(
            "UPDATE shadow_meta SET value = ? WHERE key = ?",
            ("999", META_INDEXED_PAGE_COUNT),
        )
        conn.commit()
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
    finally:
        conn.close()
    assert resolve_shadow_health(graph) == ShadowHealthState.STALE

    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)
    query = _subtree_query(block_uuid)
    out = port.read_subtree_markdown(graph, query)
    assert "needle shadow token" in _extract_excerpt(out)
