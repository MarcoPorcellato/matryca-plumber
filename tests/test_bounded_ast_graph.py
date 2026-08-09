"""PR2C adapter contract: bounded pages form an atomic complete graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from logseq_matryca_parser import StackMachineParser
from logseq_matryca_parser.graph import LogseqGraph
from src.graph.bounded_ast_graph import (
    BoundedGraphPageResult,
    build_graph_from_bounded_pages,
    parse_graph_page_bounded,
    replace_graph_page_by_source_path,
)


def _write_page(root: Path, name: str, content: str) -> Path:
    pages = root / "pages"
    pages.mkdir(exist_ok=True)
    path = pages / name
    path.write_text(content, encoding="utf-8")
    return path


def _node_source_paths(page: Any) -> list[str]:
    paths: list[str] = []

    def _visit(nodes: list[Any]) -> None:
        for node in nodes:
            paths.append(str(node.source_path))
            _visit(node.children)

    _visit(page.root_nodes)
    return paths


def test_bounded_page_matches_stack_file_metadata_and_recursive_node_paths(tmp_path: Path) -> None:
    path = _write_page(
        tmp_path,
        "Project.md",
        "title:: Project/Canonical\n"
        "- parent\n"
        "  id:: 11111111-1111-1111-1111-111111111111\n"
        "  - child\n"
        "    id:: 22222222-2222-2222-2222-222222222222\n",
    )
    bounded = parse_graph_page_bounded(path, tmp_path, timeout_s=15.0)
    expected = StackMachineParser().parse_page_file(path)

    assert bounded.ok is True
    assert bounded.failure is None
    assert bounded.page is not None
    assert bounded.page.title == expected.title
    assert bounded.page.source_path == expected.source_path
    assert bounded.page.graph_root == expected.graph_root
    assert bounded.page.created_at == expected.created_at
    assert bounded.page.updated_at == expected.updated_at
    assert bounded.page.tab_size == expected.tab_size
    assert _node_source_paths(bounded.page) == _node_source_paths(expected)


def test_bounded_page_preserves_detected_non_default_tab_semantics(tmp_path: Path) -> None:
    path = _write_page(
        tmp_path,
        "Tabs.md",
        "- root\n    - four-space child\n        - grandchild\n",
    )
    bounded = parse_graph_page_bounded(path, tmp_path, timeout_s=15.0)
    expected = StackMachineParser().parse_page_file(path)

    assert bounded.page is not None
    assert bounded.page.tab_size == 4
    assert bounded.page.tab_size == expected.tab_size
    assert [node.indent_level for node in bounded.page.root_nodes] == [
        node.indent_level for node in expected.root_nodes
    ]
    assert bounded.page.root_nodes[0].children[0].indent_level == (
        expected.root_nodes[0].children[0].indent_level
    )


def test_parse_failure_is_content_and_path_free(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = _write_page(tmp_path, "Secret.md", "- secret-body-should-not-leak\n")

    def _failed(*args: object, **kwargs: object) -> Any:
        from src.graph.bounded_page_parse import BoundedParseResult

        return BoundedParseResult(
            ok=False,
            timed_out=True,
            elapsed_s=2.0,
            content_hash="0123456789abcdef",
            byte_count=42,
            line_count=1,
            mode="stack",
            error="timeout",
        )

    monkeypatch.setattr("src.graph.bounded_ast_graph.parse_page_text_bounded", _failed)
    result = parse_graph_page_bounded(path, tmp_path, timeout_s=2.0)

    assert isinstance(result, BoundedGraphPageResult)
    assert result.ok is False
    assert result.page is None
    assert result.failure is not None
    assert result.failure.error == "timeout"
    rendered = repr(result.failure)
    assert "Secret.md" not in rendered
    assert "secret-body-should-not-leak" not in rendered
    assert str(tmp_path) not in rendered


def test_build_matches_external_complete_indexes(tmp_path: Path) -> None:
    alpha = _write_page(
        tmp_path,
        "Alpha.md",
        "alias:: Alpha Alias\n"
        "- alpha #topic [[Beta]]\n"
        "  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    beta = _write_page(
        tmp_path,
        "Beta.md",
        "- beta ((11111111-1111-1111-1111-111111111111))\n"
        "  id:: 22222222-2222-2222-2222-222222222222\n",
    )
    parsed = [parse_graph_page_bounded(path, tmp_path, timeout_s=15.0) for path in (alpha, beta)]
    assert all(result.ok and result.page is not None for result in parsed)
    pages = [result.page for result in parsed if result.page is not None]
    bounded = build_graph_from_bounded_pages(tmp_path, pages)
    expected = LogseqGraph.load_directory(tmp_path)

    assert sorted(bounded.pages) == sorted(expected.pages)
    bounded_alpha = bounded.get_page("ALPHA")
    expected_alpha = expected.get_page("ALPHA")
    assert bounded_alpha is not None
    assert expected_alpha is not None
    assert bounded_alpha.title == expected_alpha.title
    assert bounded.get_node_by_embed_ref("11111111-1111-1111-1111-111111111111") is not None
    assert [node.source_uuid for node in bounded.get_backlinks("beta")] == [
        node.source_uuid for node in expected.get_backlinks("beta")
    ]
    assert [node.source_uuid for node in bounded.get_backlinks("topic")] == [
        node.source_uuid for node in expected.get_backlinks("topic")
    ]


def test_replace_and_remove_return_new_complete_graph_without_mutating_old(tmp_path: Path) -> None:
    first = _write_page(
        tmp_path,
        "First.md",
        "- first\n  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    second = _write_page(
        tmp_path,
        "Second.md",
        "- second\n  id:: 22222222-2222-2222-2222-222222222222\n",
    )
    initial_pages = [
        parse_graph_page_bounded(path, tmp_path, timeout_s=15.0).page for path in (first, second)
    ]
    assert all(page is not None for page in initial_pages)
    original = build_graph_from_bounded_pages(
        tmp_path,
        [page for page in initial_pages if page is not None],
    )

    first.write_text(
        "- refreshed\n  id:: 33333333-3333-3333-3333-333333333333\n",
        encoding="utf-8",
    )
    refreshed = parse_graph_page_bounded(first, tmp_path, timeout_s=15.0)
    assert refreshed.page is not None
    replaced = replace_graph_page_by_source_path(original, first, refreshed.page)

    assert original.get_node_by_embed_ref("11111111-1111-1111-1111-111111111111") is not None
    assert original.get_node_by_embed_ref("33333333-3333-3333-3333-333333333333") is None
    assert replaced.get_node_by_embed_ref("11111111-1111-1111-1111-111111111111") is None
    assert replaced.get_node_by_embed_ref("33333333-3333-3333-3333-333333333333") is not None
    assert replaced.get_node_by_embed_ref("22222222-2222-2222-2222-222222222222") is not None

    removed = replace_graph_page_by_source_path(replaced, second, None)
    assert removed.get_node_by_embed_ref("33333333-3333-3333-3333-333333333333") is not None
    assert removed.get_node_by_embed_ref("22222222-2222-2222-2222-222222222222") is None
