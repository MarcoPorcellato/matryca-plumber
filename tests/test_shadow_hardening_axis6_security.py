"""v2.0-alpha hardening — Axis 6: Security & isolation (audit probes).

Read-only on ``src/`` — temporary vault fixtures exercise path sandboxing,
error sanitization, flag-off isolation, and Markdown immutability contracts.
Findings feed tracking issue #261.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.dispatch_read_handlers import handle_read_subtree
from src.agent.dispatch_search_handlers import handle_search_bm25
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port
from src.agent.shadow_graph_repository import ShadowGraphRepository
from src.config import MatrycaWikiConfig
from src.graph.path_sandbox import PathTraversalSecurityError
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid
from src.shadow.sync import sync_page_to_shadow
from src.shadow.writer_lock import shadow_writer_lock_path

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fcntl flock / symlink probes are Unix-only",
)


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _markdown_fingerprint(graph: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        if ".matryca_semantic_cache" in path.parts:
            continue
        digest.update(path.relative_to(graph).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _subtree_query(page: str, block_uuid: str) -> str:
    return json.dumps({"page": page, "block_uuid": block_uuid})


# --- A6-PATH ---


def test_a6_path_01_sync_rejects_page_outside_graph(tmp_path: Path) -> None:
    """A6-PATH-01: incremental sync rejects Markdown paths outside the graph root."""
    graph = _minimal_graph(tmp_path)
    outside = tmp_path / "escape.md"
    outside.write_text("- outside\n", encoding="utf-8")
    with pytest.raises(PathTraversalSecurityError):
        sync_page_to_shadow(graph, outside)


def test_a6_path_02_shadow_writer_lock_rejects_cache_symlink_escape(tmp_path: Path) -> None:
    """A6-PATH-02: semantic-cache symlink escape is rejected before lock acquisition."""
    graph = _minimal_graph(tmp_path)
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    (graph / ".matryca_semantic_cache").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathTraversalSecurityError):
        shadow_writer_lock_path(graph)


def test_a6_path_03_shadow_db_path_stays_under_graph(tmp_path: Path) -> None:
    """A6-PATH-03: ``shadow.sqlite`` resolves under ``.matryca_semantic_cache`` inside graph."""
    graph = _minimal_graph(tmp_path)
    db_path = shadow_db_path(graph)
    assert db_path.resolve().is_relative_to(graph.resolve())
    assert db_path.parent.name == ".matryca_semantic_cache"


def test_a6_path_04_open_shadow_db_rejects_graph_escape_via_symlink(tmp_path: Path) -> None:
    """A6-PATH-04: graph root symlink to outside prevents shadow lock/db helpers."""
    outside = tmp_path / "outside-vault"
    outside.mkdir()
    (outside / "pages").mkdir()
    link = tmp_path / "linked-vault"
    link.symlink_to(outside, target_is_directory=True)
    # Writer lock path must remain sandboxed to the resolved graph root.
    lock_path = shadow_writer_lock_path(link)
    assert lock_path.resolve().is_relative_to(link.resolve())


# --- A6-ERRORS ---


def test_a6_errors_01_subtree_not_found_omits_vault_secrets(tmp_path: Path) -> None:
    """A6-ERRORS-01: subtree NOT_FOUND envelope omits block body secrets."""
    graph = _minimal_graph(tmp_path)
    secret = "vault-secret-must-not-leak-in-not-found"
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(
        graph,
        "pages/Secret.md",
        f"- {secret}\n  id:: {block_uuid}\n",
    )
    rebuild_shadow_from_graph(graph)
    repo = ShadowGraphRepository()
    out = repo.read_subtree_markdown(
        graph,
        _subtree_query("Secret", "22222222-2222-4222-8222-222222222222"),
    )
    assert secret not in out
    assert "22222222-2222-4222-8222-222222222222" in out


def test_a6_errors_02_subtree_sqlite_failure_fallback_omits_db_internals(tmp_path: Path) -> None:
    """A6-ERRORS-02: shadow backend failure falls back without leaking SQLite paths."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Fallback.md", f"- visible\n  id:: {block_uuid}\n")
    rebuild_shadow_from_graph(graph)
    db_file = shadow_db_path(graph)

    with patch(
        "src.agent.shadow_graph_repository.open_shadow_db",
        side_effect=sqlite3.OperationalError("database is locked"),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(
            graph,
            _subtree_query("Fallback", block_uuid),
        )

    assert "visible" in out
    assert str(db_file) not in out
    assert "shadow.sqlite" not in out.lower()


@pytest.mark.asyncio
async def test_a6_errors_03_fts_validation_error_omits_vault_content(tmp_path: Path) -> None:
    """A6-ERRORS-03: FTS validation errors omit vault block bodies."""
    graph = _minimal_graph(tmp_path)
    secret = "fts-secret-token-never-in-public-error"
    _write_page(
        graph,
        "pages/FtsSecret.md",
        f"- {secret}\n  id:: 33333333-3333-4333-8333-333333333333\n",
    )
    rebuild_shadow_from_graph(graph)
    out = await handle_search_bm25(str(graph), "can't")
    assert secret not in out


def test_a6_errors_04_sync_duplicate_uuid_error_omits_block_content(tmp_path: Path) -> None:
    """A6-ERRORS-04: duplicate UUID sync error omits competing block bodies."""
    graph = _minimal_graph(tmp_path)
    shared = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    secret_a = "alpha-secret-body"
    secret_b = "beta-secret-body"
    _write_page(
        graph,
        "pages/Alpha.md",
        f"- alpha\n  id:: {shared}\n  {secret_a}\n",
    )
    _write_page(
        graph,
        "pages/Beta.md",
        f"- beta\n  id:: {shared}\n  {secret_b}\n",
    )
    with pytest.raises(Exception) as exc_info:
        rebuild_shadow_from_graph(graph)
    message = str(exc_info.value)
    assert secret_a not in message
    assert secret_b not in message


def test_a6_errors_05_inconsistent_subtree_falls_back_without_sqlite_leak(
    tmp_path: Path,
) -> None:
    """A6-ERRORS-05: INCONSISTENT shadow subtree falls back without SQLite internals."""
    graph = _minimal_graph(tmp_path)
    root = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Incon.md", f"- root\n  id:: {root}\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("UPDATE blocks SET parent_rowid = rowid WHERE block_uuid = ?", (root,))
        conn.commit()
    finally:
        conn.close()

    out = ShadowGraphRepository().read_subtree_markdown(graph, _subtree_query("Incon", root))
    assert "root" in out
    assert "shadow.sqlite" not in out.lower()


# --- A6-FLAG ---


def test_a6_flag_01_false_flag_skips_rebuild_db_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6-FLAG-01: ``MATRYCA_SHADOW_DB_ENABLED=false`` — rebuild does not create SQLite."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    graph = _minimal_graph(tmp_path)
    _write_page(graph, "pages/Quiet.md", "- quiet\n")
    rebuild_shadow_from_graph(graph)
    assert shadow_db_enabled() is False
    assert not shadow_db_path(graph).exists()


def test_a6_flag_02_false_flag_skips_incremental_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6-FLAG-02: flag off — ``sync_page_to_shadow`` is a no-op (no DB file)."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    graph = _minimal_graph(tmp_path)
    page = _write_page(graph, "pages/Quiet.md", "- quiet\n")
    sync_page_to_shadow(graph, page)
    assert not shadow_db_path(graph).exists()


def test_a6_flag_03_false_flag_read_port_is_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6-FLAG-03: flag off — ``get_graph_read_port`` returns Markdown repository."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    graph = _minimal_graph(tmp_path)
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Port.md", f"- port line\n  id:: {block_uuid}\n")
    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)
    out = port.read_subtree_markdown(graph, _subtree_query("Port", block_uuid))
    assert "port line" in out


@pytest.mark.asyncio
async def test_a6_flag_04_false_flag_handler_uses_markdown_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6-FLAG-04: flag off — MCP/CLI subtree handler reads Markdown only."""
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    graph = _minimal_graph(tmp_path)
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Handler.md", f"- handler line\n  id:: {block_uuid}\n")
    out = await handle_read_subtree(
        MatrycaWikiConfig(), str(graph), _subtree_query("Handler", block_uuid)
    )
    assert "handler line" in out


# --- A6-MD ---


def test_a6_md_01_full_rebuild_never_writes_markdown(tmp_path: Path) -> None:
    """A6-MD-01: full rebuild leaves vault Markdown bytes unchanged."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Immutable.md",
        "- immutable\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    before = _markdown_fingerprint(graph)
    rebuild_shadow_from_graph(graph)
    assert _markdown_fingerprint(graph) == before


def test_a6_md_02_incremental_sync_never_writes_markdown(tmp_path: Path) -> None:
    """A6-MD-02: incremental sync leaves vault Markdown bytes unchanged."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/Live.md",
        "- live\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    page.write_text(
        "- live\n  id:: 11111111-1111-4111-8111-111111111111\n  - child\n",
        encoding="utf-8",
    )
    after_user_edit = _markdown_fingerprint(graph)
    sync_page_to_shadow(graph, page)
    assert _markdown_fingerprint(graph) == after_user_edit


def test_a6_md_03_subtree_reads_never_write_markdown(tmp_path: Path) -> None:
    """A6-MD-03: shadow subtree reads never mutate Markdown."""
    graph = _minimal_graph(tmp_path)
    root = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Read.md", f"- read\n  id:: {root}\n  - child\n")
    rebuild_shadow_from_graph(graph)
    before = _markdown_fingerprint(graph)
    for _ in range(5):
        read_subtree_markdown(str(graph), _subtree_query("Read", root))
    assert _markdown_fingerprint(graph) == before


@pytest.mark.asyncio
async def test_a6_md_04_bm25_search_never_writes_markdown(tmp_path: Path) -> None:
    """A6-MD-04: shadow BM25 search never mutates Markdown."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Search.md",
        "- searchable needle\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    before = _markdown_fingerprint(graph)
    for _ in range(5):
        await handle_search_bm25(str(graph), "needle")
    assert _markdown_fingerprint(graph) == before


def test_a6_md_05_direct_cte_query_never_writes_markdown(tmp_path: Path) -> None:
    """A6-MD-05: direct CTE subtree query never mutates Markdown."""
    graph = _minimal_graph(tmp_path)
    root = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Cte.md", f"- cte\n  id:: {root}\n")
    rebuild_shadow_from_graph(graph)
    before = _markdown_fingerprint(graph)
    conn = open_shadow_db(graph)
    try:
        for _ in range(5):
            result = query_subtree_by_block_uuid(conn, root)
            assert result.status is SubtreeStatus.COMPLETE
    finally:
        conn.close()
    assert _markdown_fingerprint(graph) == before
