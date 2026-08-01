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
from src.shadow.cache_location import resolve_shadow_cache_location
from src.shadow.config import shadow_db_enabled
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.errors import ShadowSyncError
from src.shadow.fts_format import resolve_bm25_search_markdown
from src.shadow.meta import (
    META_GENERATION,
    META_INDEXED_PAGE_COUNT,
    META_LAST_SYNC_ERROR,
    META_SOURCE_PAGE_COUNT,
    get_meta,
    set_meta,
)
from src.shadow.runtime_state import reset_shadow_runtime_state_for_tests
from src.shadow.state_api import resolve_shadow_db_state_for_api
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid
from src.shadow.sync import sync_page_to_shadow
from src.shadow.writer_lock import shadow_writer_lock_path

_UNIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="symlink escape probes require POSIX symlinks",
)


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


@_UNIX_ONLY
def test_a6_path_02_shadow_writer_lock_rejects_cache_symlink_escape(tmp_path: Path) -> None:
    """A6-PATH-02: external cache-root symlink escape is rejected before lock."""
    graph = _minimal_graph(tmp_path)
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    cache_root = resolve_shadow_cache_location(graph).cache_root
    if cache_root.exists():
        if cache_root.is_dir():
            import shutil

            shutil.rmtree(cache_root)
        else:
            cache_root.unlink()
    cache_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathTraversalSecurityError):
        shadow_writer_lock_path(graph)


def test_a6_path_03_shadow_db_path_stays_under_graph(tmp_path: Path) -> None:
    """A6-PATH-03: ``shadow.sqlite`` resolves outside the graph in the external cache."""
    graph = _minimal_graph(tmp_path)
    db_path = shadow_db_path(graph)
    assert not db_path.resolve().is_relative_to(graph.resolve())


@_UNIX_ONLY
def test_a6_path_04_graph_root_symlink_resolves_and_stays_sandboxed(tmp_path: Path) -> None:
    """A6-PATH-04: graph-root symlink is supported; helpers target the resolved root.

    Contract: ``resolved_graph_root`` follows the link. Lock/DB paths must resolve
    to that canonical vault, while cache artifacts remain outside the graph.
    """
    outside = tmp_path / "outside-vault"
    outside.mkdir()
    (outside / "pages").mkdir()
    link = tmp_path / "linked-vault"
    link.symlink_to(outside, target_is_directory=True)

    lock_path = shadow_writer_lock_path(link)
    db_path = shadow_db_path(link)
    outside_location = resolve_shadow_cache_location(outside)
    assert db_path == outside_location.database_path
    assert str(lock_path).startswith(str(outside_location.cache_root))
    conn = open_shadow_db(link)
    try:
        assert shadow_db_path(link).is_file()
    finally:
        conn.close()


@_UNIX_ONLY
def test_a6_path_05_sync_rejects_page_symlink_outside_graph(tmp_path: Path) -> None:
    """A6-PATH-05: Markdown under ``pages/`` that symlinks outside the vault is rejected."""
    graph = _minimal_graph(tmp_path)
    outside = tmp_path / "escape.md"
    outside.write_text("- outside-secret\n", encoding="utf-8")
    linked = graph / "pages" / "Linked.md"
    linked.symlink_to(outside)
    with pytest.raises(PathTraversalSecurityError):
        sync_page_to_shadow(graph, linked)


@_UNIX_ONLY
def test_a6_path_06_open_shadow_db_rejects_sqlite_symlink_escape(tmp_path: Path) -> None:
    """A6-PATH-06: pre-existing ``shadow.sqlite`` symlink to an external file is rejected."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Seed.md",
        "- seed\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    db_path = shadow_db_path(graph)
    db_path.unlink()
    outside = tmp_path / "escape.sqlite"
    outside.write_bytes(b"not-a-real-shadow-db")
    db_path.symlink_to(outside)
    with pytest.raises(PathTraversalSecurityError):
        open_shadow_db(graph)


@_UNIX_ONLY
def test_a6_path_07_writer_lock_rejects_flock_symlink_escape(tmp_path: Path) -> None:
    """A6-PATH-07: pre-existing writer flock symlink to an external file is rejected."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Seed.md",
        "- seed\n  id:: 11111111-1111-4111-8111-111111111111\n",
    )
    rebuild_shadow_from_graph(graph)
    lock_path = shadow_writer_lock_path(graph)
    if lock_path.exists() or lock_path.is_symlink():
        lock_path.unlink()
    outside = tmp_path / "escape.flock"
    outside.write_text("x", encoding="utf-8")
    lock_path.symlink_to(outside)
    with pytest.raises(PathTraversalSecurityError):
        shadow_writer_lock_path(graph)


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
    out = ShadowGraphRepository().read_subtree_markdown(
        graph,
        _subtree_query("Secret", "22222222-2222-4222-8222-222222222222"),
    )
    assert secret not in out
    assert "22222222-2222-4222-8222-222222222222" in out


def test_a6_errors_02_subtree_sqlite_failure_fallback_omits_injected_path(
    tmp_path: Path,
) -> None:
    """A6-ERRORS-02: backend exception carrying a DB path must not reach the public envelope."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "11111111-1111-4111-8111-111111111111"
    _write_page(graph, "pages/Fallback.md", f"- visible\n  id:: {block_uuid}\n")
    rebuild_shadow_from_graph(graph)
    leak_token = f"SENSITIVE-DB-PATH::{shadow_db_path(graph)}"

    with patch(
        "src.agent.shadow_graph_repository.open_shadow_db",
        side_effect=sqlite3.OperationalError(f"database is locked: {leak_token}"),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(
            graph,
            _subtree_query("Fallback", block_uuid),
        )

    assert "visible" in out
    assert leak_token not in out
    assert "SENSITIVE-DB-PATH" not in out
    assert str(shadow_db_path(graph)) not in out


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
    with pytest.raises(ShadowSyncError) as exc_info:
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


def test_a6_errors_06_fts_backend_fallback_omits_injected_path(tmp_path: Path) -> None:
    """A6-ERRORS-06: FTS backend failure with injected path must not leak into public BM25."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/FtsFall.md",
        "- needle token\n  id:: 44444444-4444-4444-8444-444444444444\n",
    )
    rebuild_shadow_from_graph(graph)
    leak_token = f"SENSITIVE-FTS-PATH::{shadow_db_path(graph)}"

    with patch(
        "src.shadow.fts_format.format_shadow_fts_markdown",
        side_effect=sqlite3.OperationalError(f"fts failed: {leak_token}"),
    ):
        out = resolve_bm25_search_markdown(graph, "needle")

    assert "needle" in out.lower() or "Needle" in out or "token" in out.lower()
    assert leak_token not in out
    assert "SENSITIVE-FTS-PATH" not in out


def test_a6_errors_07_state_api_last_sync_error_omits_injected_path(tmp_path: Path) -> None:
    """A6-ERRORS-07: state API ``last_sync_error`` must not echo vault/DB path tokens."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/State.md",
        "- state\n  id:: 55555555-5555-4555-8555-555555555555\n",
    )
    rebuild_shadow_from_graph(graph)
    leak_token = f"SENSITIVE-META-PATH::{shadow_db_path(graph)}"
    conn = open_shadow_db(graph)
    try:
        set_meta(conn, META_LAST_SYNC_ERROR, f"rebuild failed at {leak_token}")
        conn.commit()
    finally:
        conn.close()

    snap = resolve_shadow_db_state_for_api(graph)
    assert snap.state == "error"
    assert snap.last_sync_error is not None
    assert leak_token not in snap.last_sync_error
    assert "SENSITIVE-META-PATH" not in snap.last_sync_error
    assert str(shadow_db_path(graph)) not in snap.last_sync_error


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


@pytest.mark.asyncio
async def test_a6_flag_05_false_flag_leaves_preexisting_db_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6-FLAG-05: flag off with existing DB — no open/mutate; selectors skip shadow open."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "11111111-1111-4111-8111-111111111111"
    page = _write_page(graph, "pages/Legacy.md", f"- legacy needle\n  id:: {block_uuid}\n")
    rebuild_shadow_from_graph(graph)
    db_path = shadow_db_path(graph)
    before_bytes = db_path.read_bytes()
    before_mtime = db_path.stat().st_mtime_ns
    conn = open_shadow_db(graph)
    try:
        before_generation = get_meta(conn, META_GENERATION)
        before_indexed = get_meta(conn, META_INDEXED_PAGE_COUNT)
        before_source = get_meta(conn, META_SOURCE_PAGE_COUNT)
        before_pages = int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
    finally:
        conn.close()

    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    reset_shadow_runtime_state_for_tests()

    def _forbid_open(*_args: object, **_kwargs: object) -> sqlite3.Connection:
        raise AssertionError("open_shadow_db must not be called when shadow flag is false")

    with (
        patch("src.shadow.connection.open_shadow_db", side_effect=_forbid_open),
        patch("src.agent.shadow_graph_repository.open_shadow_db", side_effect=_forbid_open),
        patch("src.shadow.fts_format.open_shadow_db", side_effect=_forbid_open),
        patch("src.shadow.bootstrap.open_shadow_db", side_effect=_forbid_open),
        patch("src.shadow.sync.open_shadow_db", side_effect=_forbid_open),
    ):
        from src.utils.runtime_bootstrap import prepare_matryca_runtime

        prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())
        port = get_graph_read_port(graph)
        assert isinstance(port, MarkdownGraphRepository)
        subtree = port.read_subtree_markdown(graph, _subtree_query("Legacy", block_uuid))
        bm25 = await handle_search_bm25(str(graph), "needle")
        sync_page_to_shadow(graph, page)
        rebuild_shadow_from_graph(graph)

    assert "legacy" in subtree.lower()
    assert "needle" in bm25.lower() or "legacy" in bm25.lower()
    assert db_path.read_bytes() == before_bytes
    assert db_path.stat().st_mtime_ns == before_mtime

    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    reset_shadow_runtime_state_for_tests()
    verify = open_shadow_db(graph)
    try:
        assert get_meta(verify, META_GENERATION) == before_generation
        assert get_meta(verify, META_INDEXED_PAGE_COUNT) == before_indexed
        assert get_meta(verify, META_SOURCE_PAGE_COUNT) == before_source
        assert int(verify.execute("SELECT COUNT(*) FROM pages").fetchone()[0]) == before_pages
    finally:
        verify.close()


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
    """A6-MD-02: incremental sync leaves vault Markdown bytes unchanged after the user edit."""
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
