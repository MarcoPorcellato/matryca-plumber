"""PR2C: bounded parsing is committed atomically by ``GraphAstCache``."""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from logseq_matryca_parser.graph import LogseqGraph, StackMachineParser
from loguru import logger
from src.graph.ast_cache import GraphAstCache, GraphAstParseError, clear_graph_ast_cache
from src.graph.bounded_ast_graph import (
    BoundedGraphPageResult,
    BoundedGraphParseFailure,
)
from src.graph.bounded_page_parse import get_bounded_page_parse_worker


@pytest.fixture(autouse=True)
def _clean_cache_and_worker() -> Iterator[None]:
    clear_graph_ast_cache()
    yield
    clear_graph_ast_cache()


def _write_page(root: Path, name: str, body: str) -> Path:
    pages = root / "pages"
    pages.mkdir(exist_ok=True)
    path = pages / name
    path.write_text(body, encoding="utf-8")
    return path


def _failure(*, content_hash: str = "0123456789abcdef") -> BoundedGraphPageResult:
    return BoundedGraphPageResult(
        failure=BoundedGraphParseFailure(
            content_hash=content_hash,
            byte_count=321,
            line_count=17,
            timed_out=True,
            elapsed_s=2.0,
            error="timeout",
        )
    )


def test_bootstrap_failure_does_not_publish_partial_graph(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    good = _write_page(
        tmp_path,
        "Alpha.md",
        "- good\n  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    bad = _write_page(tmp_path, "Zulu.md", "- private pathological body\n")

    def _parse(path: Path, graph_root: Path) -> BoundedGraphPageResult:
        del graph_root
        if path == bad:
            return _failure()
        return BoundedGraphPageResult(page=StackMachineParser().parse_page_file(good))

    monkeypatch.setattr("src.graph.ast_cache.parse_graph_page_bounded", _parse)
    monkeypatch.setattr(
        LogseqGraph,
        "load_directory",
        lambda *_args, **_kwargs: pytest.fail("unbounded loader called"),
    )
    cache = GraphAstCache(tmp_path)

    with pytest.raises(GraphAstParseError) as caught:
        cache.bootstrap()

    assert cache._graph is None
    rendered = str(caught.value)
    assert "0123456789abcdef" in rendered
    assert "private pathological body" not in rendered
    assert "Zulu.md" not in rendered
    assert str(tmp_path) not in rendered


def test_incremental_timeout_preserves_exact_last_complete_graph(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page = _write_page(
        tmp_path,
        "Alpha.md",
        "- old\n  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    cache = GraphAstCache(tmp_path)
    original = cache.bootstrap()
    page.write_text("- private pathological replacement\n", encoding="utf-8")

    monkeypatch.setattr(
        "src.graph.ast_cache.parse_graph_page_bounded",
        lambda *_args, **_kwargs: _failure(),
    )
    monkeypatch.setattr(
        LogseqGraph,
        "load_directory",
        lambda *_args, **_kwargs: pytest.fail("unbounded fallback called"),
    )
    cache.apply_file_event(page, "modified")

    assert cache._graph is original
    assert cache.get_block_by_uuid("11111111-1111-1111-1111-111111111111") is not None


def test_incremental_failure_log_is_hash_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret = "vault-secret-marker"
    page = _write_page(tmp_path, "Secret.md", f"- {secret}\n")
    cache = GraphAstCache(tmp_path)
    cache.bootstrap()
    monkeypatch.setattr(
        "src.graph.ast_cache.parse_graph_page_bounded",
        lambda *_args, **_kwargs: _failure(content_hash="fedcba9876543210"),
    )
    output = StringIO()
    sink = logger.add(output, format="{message} {extra}")
    try:
        cache.apply_file_event(page, "modified")
    finally:
        logger.remove(sink)

    rendered = output.getvalue()
    assert "fedcba9876543210" in rendered
    assert "timeout" in rendered
    assert secret not in rendered
    assert "Secret.md" not in rendered
    assert str(tmp_path) not in rendered


def test_bootstrap_recovers_after_bounded_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    page = _write_page(tmp_path, "Alpha.md", "- first attempt\n")
    cache = GraphAstCache(tmp_path)
    calls = 0
    from src.graph.bounded_ast_graph import parse_graph_page_bounded as real_parse

    def _parse(path: Path, graph_root: Path) -> BoundedGraphPageResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _failure()
        return real_parse(path, graph_root, timeout_s=15.0)

    monkeypatch.setattr("src.graph.ast_cache.parse_graph_page_bounded", _parse)
    with pytest.raises(GraphAstParseError):
        cache.bootstrap()

    page.write_text(
        "- recovered\n  id:: 22222222-2222-2222-2222-222222222222\n",
        encoding="utf-8",
    )
    graph = cache.bootstrap()
    assert graph.get_node_by_embed_ref("22222222-2222-2222-2222-222222222222") is not None


def test_clear_cache_releases_worker_and_next_bootstrap_recovers(tmp_path: Path) -> None:
    _write_page(tmp_path, "Alpha.md", "- normal\n")
    GraphAstCache(tmp_path).bootstrap()
    worker = get_bounded_page_parse_worker()
    assert worker.pid is not None

    clear_graph_ast_cache()
    clear_graph_ast_cache()
    assert worker.pid is None

    graph = GraphAstCache(tmp_path).bootstrap()
    assert graph.get_page("Alpha") is not None


def test_incremental_success_and_delete_publish_complete_new_graph(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "Alpha.md",
        "- old\n  id:: 11111111-1111-1111-1111-111111111111\n",
    )
    cache = GraphAstCache(tmp_path)
    original = cache.bootstrap()
    page.write_text(
        "- new #topic\n  id:: 22222222-2222-2222-2222-222222222222\n",
        encoding="utf-8",
    )

    cache.apply_file_event(page, "modified")
    replaced = cache.get_graph()
    assert replaced is not original
    assert replaced.get_node_by_embed_ref("11111111-1111-1111-1111-111111111111") is None
    assert replaced.get_node_by_embed_ref("22222222-2222-2222-2222-222222222222") is not None
    assert len(replaced.get_nodes_by_tag("topic")) == 1

    page.unlink()
    cache.apply_file_event(page, "deleted")
    removed = cache.get_graph()
    assert removed is not replaced
    assert removed.get_node_by_embed_ref("22222222-2222-2222-2222-222222222222") is None
