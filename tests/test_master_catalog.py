"""Tests for master catalog, bootstrap harvest, and graph insights engine."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from src.agent.plumber_llm import BootstrapSummaryResult, GraphInsightsLLMResult
from src.graph.bootstrap_harvest import (
    harvest_page_into_catalog,
    run_bootstrap_harvest,
    run_incremental_catalog_refresh,
)
from src.graph.insights_engine import (
    compute_topology_metrics,
    format_graph_insights_markdown,
    run_graph_insights_engine,
)
from src.graph.master_catalog import (
    SEMANTIC_INDEX_HEADER,
    CatalogEntry,
    CatalogLoadError,
    MasterCatalog,
    build_master_index_markdown,
    clear_master_catalog_cache,
    extract_catalog_fields_from_content,
    is_bootstrap_catalog_complete,
    load_master_catalog,
    master_index_page_path,
)
from src.graph.page_write_lock import clear_page_write_locks

BLOCK_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


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


class StubInsightsLLM:
    """Deterministic insights LLM stub."""

    def generate_graph_insights(
        self,
        *,
        metrics_json: str,
        graph_root: Path,
    ) -> GraphInsightsLLMResult:
        _ = (metrics_json, graph_root)
        return GraphInsightsLLMResult(
            ontology_report="The graph reveals a compact test cluster around harvest tags.",
            cleanup_suggestions=[
                "Consider aliasing Alpha and Beta due to semantic overlap.",
            ],
        )


def _write_page(graph_root: Path, title: str, body: str) -> Path:
    pages = graph_root / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    safe = title.replace("/", "___")
    path = pages / f"{safe}.md"
    path.write_text(body, encoding="utf-8")
    return path


def _indexed_body(
    *,
    summary: str = "Existing summary.",
    tags: str = "#alpha #beta",
    domain: str = "risorsa",
) -> str:
    return (
        f"- type:: {domain}\n"
        f"- First bullet\n  id:: {BLOCK_UUID}\n"
        f"\n{SEMANTIC_INDEX_HEADER}\n"
        f"- indexed-at:: 2026-01-01 00:00 UTC\n"
        f"- summary:: {summary}\n"
        f"- suggested-tags:: {tags}\n"
    )


@pytest.fixture
def graph_root(tmp_path: Path) -> Path:
    clear_page_write_locks()
    clear_master_catalog_cache()
    return tmp_path


def test_catalog_entry_roundtrip() -> None:
    entry = CatalogEntry(
        summary="One sentence.",
        domain="area",
        tags=["foo", "bar"],
        last_mtime=123,
        orphan=True,
    )
    payload = entry.to_json()
    restored = CatalogEntry.from_json(payload)
    assert restored.summary == "One sentence."
    assert restored.domain == "area"
    assert restored.tags == ["foo", "bar"]
    assert restored.last_mtime == 123
    assert restored.orphan is True


def test_extract_catalog_fields_from_semantic_index() -> None:
    content = _indexed_body(summary="Parsed summary.", tags="#one #two", domain="progetto")
    extracted = extract_catalog_fields_from_content(content)
    assert extracted is not None
    assert extracted.summary == "Parsed summary."
    assert extracted.tags == ["one", "two"]
    assert extracted.domain == "progetto"


def test_load_master_catalog_self_heals_corrupt_json(graph_root: Path) -> None:
    clear_master_catalog_cache(graph_root)
    path = MasterCatalog.catalog_path(graph_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    catalog = load_master_catalog(graph_root, force_reload=True)
    assert catalog.pages == {}
    assert catalog.persist_allowed is False
    catalog.upsert("Lost", CatalogEntry(summary="x", domain="", tags=[], last_mtime=1))
    catalog.save()
    assert not path.is_file()


def test_load_master_catalog_oserror_raises_without_cache(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_master_catalog_cache(graph_root)
    path = MasterCatalog.catalog_path(graph_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"version": 1, "pages": {}}', encoding="utf-8")
    catalog_key = path.resolve()

    real_open = Path.open

    def _patched_open(self: Path, *args: object, **kwargs: object) -> object:
        if self.resolve() == catalog_key:
            raise OSError("simulated read failure")
        return real_open(self, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(Path, "open", _patched_open)
    with pytest.raises(CatalogLoadError):
        load_master_catalog(graph_root, force_reload=True)


def test_load_master_catalog_oserror_returns_cached_instance(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_master_catalog_cache(graph_root)
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Cached",
        CatalogEntry(summary="cached", domain="", tags=[], last_mtime=1),
    )
    catalog.save()
    _ = load_master_catalog(graph_root, force_reload=True)

    path = MasterCatalog.catalog_path(graph_root)
    catalog_key = path.resolve()
    real_open = Path.open

    def _patched_open(self: Path, *args: object, **kwargs: object) -> object:
        if self.resolve() == catalog_key:
            raise OSError("simulated read failure")
        return real_open(self, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(Path, "open", _patched_open)
    reloaded = load_master_catalog(graph_root, force_reload=True)
    assert reloaded.pages["Cached"].summary == "cached"


def test_load_and_save_master_catalog(graph_root: Path) -> None:
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Demo",
        CatalogEntry(
            summary="Demo page",
            domain="mappa",
            tags=["demo"],
            last_mtime=100,
            orphan=False,
        ),
    )
    catalog.save()

    path = MasterCatalog.catalog_path(graph_root)
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["pages"]["Demo"]["summary"] == "Demo page"

    reloaded = load_master_catalog(graph_root, force_reload=True)
    assert reloaded.pages["Demo"].domain == "mappa"


def test_load_master_catalog_serializes_reads_under_concurrent_save(graph_root: Path) -> None:
    """Concurrent reloads must not observe torn JSON during atomic catalog saves (#35)."""
    baseline = load_master_catalog(graph_root)
    baseline.upsert(
        "Alpha",
        CatalogEntry(
            summary="Alpha baseline",
            domain="risorsa",
            tags=["alpha"],
            last_mtime=1,
            orphan=False,
        ),
    )
    baseline.save()

    parse_errors: list[str] = []
    corrupt_loads: list[bool] = []
    stop_event = threading.Event()

    def reader_loop() -> None:
        while not stop_event.is_set():
            try:
                reloaded = load_master_catalog(graph_root, force_reload=True)
            except CatalogLoadError:
                continue
            if not reloaded.persist_allowed:
                corrupt_loads.append(True)
            catalog_path = MasterCatalog.catalog_path(graph_root)
            try:
                raw = catalog_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if not raw.strip():
                continue
            try:
                json.loads(raw)
            except json.JSONDecodeError:
                parse_errors.append(raw[:120])

    readers = [threading.Thread(target=reader_loop, daemon=True) for _ in range(4)]
    for thread in readers:
        thread.start()

    try:
        for index in range(120):
            writer = load_master_catalog(graph_root)
            writer.upsert(
                f"Page{index % 8}",
                CatalogEntry(
                    summary=f"Summary {index}",
                    domain="risorsa",
                    tags=["concurrent"],
                    last_mtime=index,
                    orphan=False,
                ),
            )
            writer.save()
    finally:
        stop_event.set()
        for thread in readers:
            thread.join(timeout=2.0)

    assert parse_errors == []
    assert corrupt_loads == []
    final = load_master_catalog(graph_root, force_reload=True)
    assert final.persist_allowed is True
    assert len(final.pages) >= 8


def test_save_merges_concurrent_page_deltas_without_clobber(graph_root: Path) -> None:
    """Stale in-process writers must not drop rows saved by another writer (#36)."""
    writer_a = load_master_catalog(graph_root)
    writer_a.upsert(
        "PageA",
        CatalogEntry(
            summary="Alpha v1",
            domain="risorsa",
            tags=["a"],
            last_mtime=10,
            orphan=False,
        ),
    )
    writer_a.save()

    writer_b = load_master_catalog(graph_root, force_reload=True)
    writer_b.upsert(
        "PageB",
        CatalogEntry(
            summary="Beta",
            domain="risorsa",
            tags=["b"],
            last_mtime=20,
            orphan=False,
        ),
    )
    writer_b.save()

    writer_a.upsert(
        "PageA",
        CatalogEntry(
            summary="Alpha v2",
            domain="risorsa",
            tags=["a"],
            last_mtime=30,
            orphan=False,
        ),
    )
    writer_a.save()

    merged = load_master_catalog(graph_root, force_reload=True)
    assert merged.pages["PageA"].summary == "Alpha v2"
    assert merged.pages["PageB"].summary == "Beta"


def test_save_replace_mode_drops_pages_for_prune(graph_root: Path) -> None:
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Keep",
        CatalogEntry(summary="keep", domain="", tags=[], last_mtime=1, orphan=False),
    )
    catalog.upsert(
        "Drop",
        CatalogEntry(summary="drop", domain="", tags=[], last_mtime=1, orphan=False),
    )
    catalog.save()

    catalog.remove("Drop")
    catalog.save(replace=True)

    reloaded = load_master_catalog(graph_root, force_reload=True)
    assert "Keep" in reloaded.pages
    assert "Drop" not in reloaded.pages


def test_save_applies_pending_removals_on_merge(graph_root: Path) -> None:
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Stale",
        CatalogEntry(summary="stale", domain="", tags=[], last_mtime=1, orphan=False),
    )
    catalog.upsert(
        "Fresh",
        CatalogEntry(summary="fresh", domain="", tags=[], last_mtime=2, orphan=False),
    )
    catalog.save()

    stale_ref = load_master_catalog(graph_root)
    stale_ref.remove("Stale")
    stale_ref.save()

    reloaded = load_master_catalog(graph_root, force_reload=True)
    assert "Stale" not in reloaded.pages
    assert reloaded.pages["Fresh"].summary == "fresh"


def test_needs_refresh_detects_mtime_drift(graph_root: Path) -> None:
    path = _write_page(graph_root, "Fresh", _indexed_body())
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Fresh",
        CatalogEntry(summary="Old", domain="", tags=[], last_mtime=1, orphan=False),
    )
    assert catalog.needs_refresh("Fresh", path.stat().st_mtime_ns) is True


def test_needs_refresh_accepts_legacy_second_mtime(graph_root: Path) -> None:
    path = _write_page(graph_root, "Fresh", _indexed_body())
    mtime_ns = path.stat().st_mtime_ns
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Fresh",
        CatalogEntry(
            summary="Old",
            domain="",
            tags=[],
            last_mtime=int(mtime_ns // 1_000_000_000),
            orphan=False,
        ),
    )
    assert catalog.needs_refresh("Fresh", mtime_ns) is False


def test_needs_refresh_detects_same_second_nanosecond_drift(
    graph_root: Path,
) -> None:
    path = _write_page(graph_root, "Fresh", _indexed_body())
    mtime_ns = path.stat().st_mtime_ns
    same_second_drift = mtime_ns - 1 if mtime_ns % 1_000_000_000 else mtime_ns + 1
    catalog = load_master_catalog(graph_root)
    catalog.upsert(
        "Fresh",
        CatalogEntry(
            summary="Fresh",
            domain="",
            tags=[],
            last_mtime=mtime_ns,
            orphan=False,
        ),
    )
    assert same_second_drift // 1_000_000_000 == mtime_ns // 1_000_000_000
    assert catalog.needs_refresh("Fresh", mtime_ns) is False
    assert catalog.needs_refresh("Fresh", same_second_drift) is True


def test_build_master_index_groups_by_domain_with_collapsed(graph_root: Path) -> None:
    catalog = MasterCatalog(graph_root=graph_root)
    catalog.upsert(
        "Area/Topic",
        CatalogEntry(summary="Operational note.", domain="area", tags=[], last_mtime=1),
    )
    catalog.upsert(
        "Vision",
        CatalogEntry(summary="North star.", domain="mappa", tags=[], last_mtime=1),
    )
    md = build_master_index_markdown(catalog)
    assert "collapsed:: true" in md
    assert "[[Vision]] — North star." in md
    assert "[[Area/Topic]] — Operational note." in md
    assert "Mappa — strategic vision" in md


def test_bootstrap_harvest_thermal_delay_only_after_llm(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time

    monkeypatch.setenv("MATRYCA_THERMAL_DELAY_BOOTSTRAP", "2.0")
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))

    _write_page(graph_root, "Indexed", _indexed_body(summary="Already indexed."))
    run_bootstrap_harvest(graph_root, llm=StubHarvestLLM(), incremental=False, phase1_strict=True)
    thermal_sleeps = [s for s in sleeps if s >= 1.0]
    assert thermal_sleeps == []

    _write_page(graph_root, "Needs Index", "- type:: risorsa\n- Body content\n")
    sleeps.clear()
    metrics = run_bootstrap_harvest(
        graph_root,
        llm=StubHarvestLLM(),
        incremental=True,
        phase1_strict=True,
    )
    thermal_sleeps = [s for s in sleeps if s >= 1.0]
    assert metrics.llm_harvested >= 1
    assert metrics.llm_harvested == len(thermal_sleeps)
    assert all(delay == 2.0 for delay in thermal_sleeps)


def test_bootstrap_harvest_stops_when_requested(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    _write_page(graph_root, "Alpha", "- type:: risorsa\n- Alpha body\n")
    _write_page(graph_root, "Beta", "- type:: risorsa\n- Beta body\n")
    stop_event = threading.Event()
    stop_event.set()
    metrics = run_bootstrap_harvest(
        graph_root,
        llm=StubHarvestLLM(),
        incremental=False,
        phase1_strict=False,
        stop_event=stop_event,
    )
    assert metrics.scanned == 0
    assert metrics.llm_harvested == 0


def test_bootstrap_harvest_regex_path_without_llm(graph_root: Path) -> None:
    _write_page(graph_root, "Indexed", _indexed_body(summary="Already indexed."))
    metrics = run_bootstrap_harvest(
        graph_root,
        llm=None,
        incremental=False,
        phase1_strict=True,
    )
    assert metrics.regex_harvested == 1
    assert metrics.llm_harvested == 0
    assert metrics.index_rebuilt is True
    assert metrics.files_created == 0

    catalog = load_master_catalog(graph_root, force_reload=True)
    assert catalog.pages["Indexed"].summary == "Already indexed."

    master_index = master_index_page_path(graph_root)
    assert master_index.is_file()
    assert "[[Indexed]]" in master_index.read_text(encoding="utf-8")


def test_is_bootstrap_catalog_complete_requires_master_index_and_rows(
    graph_root: Path,
) -> None:
    assert is_bootstrap_catalog_complete(graph_root) is False
    _write_page(graph_root, "Ready", _indexed_body(summary="Ready summary."))
    run_bootstrap_harvest(graph_root, llm=None, incremental=False, phase1_strict=True)
    assert is_bootstrap_catalog_complete(graph_root) is True


def test_bootstrap_harvest_llm_path_writes_index_and_catalog(graph_root: Path) -> None:
    _write_page(graph_root, "Needs Index", "- type:: risorsa\n- Body content\n")
    metrics = run_bootstrap_harvest(
        graph_root,
        llm=StubHarvestLLM(),
        incremental=False,
        phase1_strict=True,
    )
    assert metrics.llm_harvested == 1
    assert metrics.files_created == 0

    page_path = graph_root / "pages" / "Needs Index.md"
    text = page_path.read_text(encoding="utf-8")
    assert SEMANTIC_INDEX_HEADER in text
    assert "Harvested summary for Needs Index" in text

    catalog = load_master_catalog(graph_root, force_reload=True)
    assert catalog.pages["Needs Index"].summary.startswith("Harvested summary")


def test_incremental_refresh_only_touches_stale_pages(graph_root: Path) -> None:
    indexed = _write_page(graph_root, "Stable", _indexed_body(summary="Stable summary."))
    run_bootstrap_harvest(graph_root, llm=None, incremental=False)

    time.sleep(0.02)
    _write_page(graph_root, "Changed", _indexed_body(summary="Changed summary."))

    metrics = run_incremental_catalog_refresh(graph_root, llm=None)
    assert metrics.scanned >= 1
    catalog = load_master_catalog(graph_root, force_reload=True)
    assert catalog.pages["Changed"].summary == "Changed summary."
    assert catalog.pages["Stable"].summary == "Stable summary."
    assert catalog.pages["Stable"].last_mtime == indexed.stat().st_mtime_ns


def test_compute_topology_metrics_orphans_and_clusters(graph_root: Path) -> None:
    _write_page(
        graph_root,
        "Hub",
        "- Links to [[Orphan A]] and [[Alpha]]\n",
    )
    _write_page(
        graph_root,
        "Alpha",
        _indexed_body(summary="Alpha page.", tags="#cluster #shared", domain="risorsa"),
    )
    _write_page(
        graph_root,
        "Beta",
        _indexed_body(summary="Beta page.", tags="#cluster #shared #extra", domain="risorsa"),
    )
    _write_page(
        graph_root,
        "Orphan A",
        _indexed_body(summary="Lonely page.", tags="#cluster #shared", domain="archivio"),
    )

    catalog = load_master_catalog(graph_root)
    for title in ("Hub", "Alpha", "Beta", "Orphan A"):
        catalog.upsert(
            title,
            CatalogEntry(summary=title, domain="risorsa", tags=["cluster"], last_mtime=1),
        )

    metrics = compute_topology_metrics(graph_root, catalog)
    assert metrics.page_count == 4
    assert "Hub" in metrics.orphan_pages
    assert "Beta" in metrics.orphan_pages
    assert "Orphan A" not in metrics.orphan_pages
    assert metrics.tag_clusters


def test_run_graph_insights_engine_writes_dashboard(graph_root: Path) -> None:
    _write_page(graph_root, "Demo", _indexed_body(summary="Demo summary."))
    run_bootstrap_harvest(graph_root, llm=None, incremental=False)

    result = run_graph_insights_engine(graph_root, llm=StubInsightsLLM())
    assert result.output_path.is_file()
    text = result.output_path.read_text(encoding="utf-8")
    assert "## 🧠 Implicit Ontology Report" in text
    assert "## 🧹 Structural Cleanup Suggestions" in text
    assert "#todo [[Matryca Cleanup Opportunity]]" in text
    assert result.llm_used is True


def test_format_graph_insights_fallback_markdown() -> None:
    from src.graph.insights_engine import TopologyMetrics, _fallback_insights

    metrics = TopologyMetrics(page_count=3, orphan_pages=["Lonely"], catalog_coverage=66.7)
    llm_result = _fallback_insights(metrics)
    md = format_graph_insights_markdown(metrics, llm_result)
    assert "Topology Snapshot" in md
    assert "Lonely" in md or "orphan" in md.lower()


def test_harvest_page_into_catalog_skips_empty_body(graph_root: Path) -> None:
    path = _write_page(graph_root, "Empty", "   \n")
    catalog = load_master_catalog(graph_root)
    status, changed, llm_called = harvest_page_into_catalog(graph_root, catalog, path, llm=None)
    assert status == "skipped_empty"
    assert changed is False
    assert llm_called is False


def test_bootstrap_harvest_reports_incremental_progress(graph_root: Path) -> None:
    for index in range(3):
        _write_page(graph_root, f"Page{index}", _indexed_body(summary=f"Summary {index}."))

    snapshots: list[tuple[int, int]] = []

    def on_progress(
        scanned: int,
        total: int,
        _last: Path | None,
        _harvest: object = None,
    ) -> None:
        snapshots.append((scanned, total))

    metrics = run_bootstrap_harvest(
        graph_root,
        llm=None,
        incremental=False,
        phase1_strict=True,
        progress_interval=1,
        on_progress=on_progress,
    )

    assert metrics.scanned == 3
    assert snapshots[0] == (0, 3)
    assert snapshots[-1] == (3, 3)
