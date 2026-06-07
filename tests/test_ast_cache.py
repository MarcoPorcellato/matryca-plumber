"""Tests for in-memory LogseqGraph AST cache."""

from __future__ import annotations

from pathlib import Path

from src.daemon.ast_cache import (
    clear_graph_ast_cache,
    count_graph_markdown_files,
    get_graph_ast_cache,
)


def _write_page(pages: Path, name: str, body: str) -> Path:
    path = pages / name
    path.write_text(body, encoding="utf-8")
    return path


def test_count_graph_markdown_files(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    journals = tmp_path / "journals"
    pages.mkdir()
    journals.mkdir()
    (pages / "a.md").write_text("- a\n", encoding="utf-8")
    (journals / "2026_06_07.md").write_text("- j\n", encoding="utf-8")
    assert count_graph_markdown_files(tmp_path) == 2


def test_ast_cache_delta_reload_updates_uuid_lookup(tmp_path: Path) -> None:
    clear_graph_ast_cache()
    pages = tmp_path / "pages"
    pages.mkdir()
    path = _write_page(
        pages,
        "note.md",
        "- block one\n  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    cache = get_graph_ast_cache(tmp_path)
    cache.bootstrap()
    node = cache.get_block_by_uuid("11111111-1111-1111-1111-111111111111")
    assert node is not None

    path.write_text(
        "- block one\n  id:: 11111111-1111-1111-1111-111111111111\n"
        "- block two\n  id:: 22222222-2222-2222-2222-222222222222\n",
        encoding="utf-8",
    )
    cache.apply_file_event(path, "modified")
    assert cache.get_block_by_uuid("22222222-2222-2222-2222-222222222222") is not None
