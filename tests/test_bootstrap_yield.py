"""Tests for cooperative yield during bootstrap."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.plumber_llm import BootstrapSummaryResult
from src.graph.alias_index import page_title_from_path
from src.graph.bootstrap_harvest import harvest_page_into_catalog, run_bootstrap_harvest
from src.graph.bootstrap_stop import BootstrapHarvestStopped
from src.graph.master_catalog import (
    SEMANTIC_INDEX_HEADER,
    clear_master_catalog_cache,
    load_master_catalog,
)


class StubHarvestLLM:
    """Deterministic bootstrap harvest LLM stub."""

    def harvest_page_summary(
        self,
        page_title: str,
        content: str,
        *,
        page_path: Path | None = None,
        graph_root: Path | None = None,
        task_instruction: str | None = None,
    ) -> BootstrapSummaryResult:
        _ = (page_path, graph_root, content, task_instruction)
        return BootstrapSummaryResult(
            summary=f"Harvested summary for {page_title}",
            suggested_tags=["harvest", "test"],
            domain="risorsa",
        )


@pytest.fixture
def graph_root(tmp_path: Path) -> Path:
    clear_master_catalog_cache()
    return tmp_path


def test_bootstrap_harvest_calls_yield_host(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    for i in range(30):
        (pages / f"Page{i}.md").write_text(f"- note {i}\n", encoding="utf-8")
    with patch("src.graph.bootstrap_harvest.yield_host") as mock_yield:
        metrics = run_bootstrap_harvest(tmp_path, llm=None, incremental=False, rebuild_index=False)
    assert metrics.scanned == 30
    assert mock_yield.call_count >= 1
    load_master_catalog(tmp_path, force_reload=True)


def test_harvest_skips_catalog_upsert_when_semantic_index_occ_aborts(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Needs Index.md"
    page.write_text("- type:: risorsa\n- Body content\n", encoding="utf-8")
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)

    monkeypatch.setattr(
        "src.graph.bootstrap_harvest.file_mtime_drifted",
        lambda _path, _baseline: True,
    )

    status, changed, llm_called = harvest_page_into_catalog(
        graph_root,
        catalog,
        page,
        llm=StubHarvestLLM(),
    )

    assert SEMANTIC_INDEX_HEADER not in page.read_text(encoding="utf-8")
    assert catalog.get(title) is None
    assert status == "pending_llm"
    assert changed is False
    assert llm_called is True


def test_harvest_upserts_catalog_when_semantic_index_append_succeeds(graph_root: Path) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Needs Index.md"
    page.write_text("- type:: risorsa\n- Body content\n", encoding="utf-8")
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)

    status, changed, llm_called = harvest_page_into_catalog(
        graph_root,
        catalog,
        page,
        llm=StubHarvestLLM(),
    )

    assert SEMANTIC_INDEX_HEADER in page.read_text(encoding="utf-8")
    entry = catalog.get(title)
    assert entry is not None
    assert entry.summary.startswith("Harvested summary for Needs Index")
    assert entry.last_mtime == page.stat().st_mtime_ns
    assert status == "llm"
    assert changed is True
    assert llm_called is True


def test_harvest_stops_before_llm_and_catalog_mutation(graph_root: Path) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Needs Index.md"
    original = "- type:: risorsa\n- Body content\n"
    page.write_text(original, encoding="utf-8")
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)
    stop_event = threading.Event()
    stop_event.set()

    with pytest.raises(BootstrapHarvestStopped):
        harvest_page_into_catalog(
            graph_root,
            catalog,
            page,
            llm=StubHarvestLLM(),
            stop_event=stop_event,
        )

    assert page.read_text(encoding="utf-8") == original
    assert catalog.get(title) is None


def test_harvest_regex_path_stores_nanosecond_mtime(graph_root: Path) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Indexed.md"
    page.write_text(
        f"- type:: risorsa\n{SEMANTIC_INDEX_HEADER}\n- summary:: Indexed summary\n",
        encoding="utf-8",
    )
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)

    status, changed, llm_called = harvest_page_into_catalog(
        graph_root,
        catalog,
        page,
        llm=None,
    )

    entry = catalog.get(title)
    assert entry is not None
    assert entry.last_mtime == page.stat().st_mtime_ns
    assert status == "regex"
    assert changed is True
    assert llm_called is False


@pytest.mark.parametrize("use_mmap", [False, True])
def test_harvest_regex_read_paths_match(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    use_mmap: bool,
) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Indexed.md"
    page.write_text(
        f"- type:: risorsa\n{SEMANTIC_INDEX_HEADER}\n- summary:: Indexed summary\n",
        encoding="utf-8",
    )
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)
    monkeypatch.setattr(
        "src.graph.markdown_io.graph_read_mmap_enabled",
        lambda: use_mmap,
    )

    result = harvest_page_into_catalog(
        graph_root,
        catalog,
        page,
        llm=None,
        incoming_counts={title: 1},
    )

    entry = catalog.get(title)
    assert entry is not None
    assert entry.last_mtime == page.stat().st_mtime_ns
    assert entry.orphan is False
    assert result == ("regex", True, False)


@pytest.mark.parametrize("use_mmap", [False, True])
def test_harvest_read_error_preserves_status_without_catalog_mutation(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    use_mmap: bool,
) -> None:
    pages = graph_root / "pages"
    pages.mkdir(parents=True)
    page = pages / "Unreadable.md"
    page.write_text("- Body\n", encoding="utf-8")
    title = page_title_from_path(graph_root, page)
    catalog = load_master_catalog(graph_root)
    monkeypatch.setattr(
        "src.graph.markdown_io.graph_read_mmap_enabled",
        lambda: use_mmap,
    )

    def raise_read_error(*_args: object, **_kwargs: object) -> None:
        raise OSError("read failed")

    target = "mmap_graph_page" if use_mmap else "read_graph_page_text"
    monkeypatch.setattr(f"src.graph.bootstrap_harvest.{target}", raise_read_error)

    result = harvest_page_into_catalog(graph_root, catalog, page, llm=None)

    assert result == ("error:read failed", False, False)
    assert catalog.get(title) is None
