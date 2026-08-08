"""Tests for Phase 1 bootstrap_status read target and Soft Gate semaphore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.agent.graph_dispatch import dispatch_read
from src.agent.maintenance_daemon import save_daemon_state, state_path
from src.config import MatrycaWikiConfig
from src.graph.bootstrap_status import (
    collect_bootstrap_status,
    format_bootstrap_status_markdown,
)
from src.graph.master_catalog import (
    CatalogEntry,
    MasterCatalog,
    write_master_index_page,
)


@pytest.mark.asyncio
async def test_dispatch_read_bootstrap_status_empty_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "pages").mkdir()
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    out = await dispatch_read(MatrycaWikiConfig(), "bootstrap_status", "")
    assert "SOFT GATE ACTIVE" in out
    assert '"soft_gate_active": true' in out


def test_collect_bootstrap_status_phase1_in_progress(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    from src.agent.maintenance_daemon import DaemonState

    state = DaemonState(
        bootstrap_complete=False,
        bootstrap_scanned=3,
        bootstrap_total=10,
        status="running",
    )
    save_daemon_state(tmp_path, state)
    snap = collect_bootstrap_status(tmp_path)
    assert snap.phase1_in_progress is True
    assert snap.soft_gate_active is True
    assert snap.bootstrap_scanned == 3
    assert snap.bootstrap_total == 10
    assert snap.checkpoint_recovery_source == "primary"
    assert snap.checkpoint_reset_event is False


def test_collect_bootstrap_status_green_when_catalog_complete(
    tmp_path: Path,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    page_path = pages / "Alpha.md"
    page_path.write_text(
        "- # Alpha\n- ### Matryca Semantic Index\n- summary:: Alpha page summary\n",
        encoding="utf-8",
    )
    mtime = int(page_path.stat().st_mtime_ns // 1_000_000_000)
    catalog = MasterCatalog(graph_root=tmp_path)
    catalog.upsert(
        "Alpha",
        CatalogEntry(summary="Alpha page summary", domain="risorsa", last_mtime=mtime),
    )
    catalog.save()
    write_master_index_page(tmp_path, catalog)

    from src.agent.maintenance_daemon import DaemonState

    save_daemon_state(
        tmp_path,
        DaemonState(bootstrap_complete=True, bootstrap_scanned=1, bootstrap_total=1),
    )

    snap = collect_bootstrap_status(tmp_path)
    assert snap.master_index_present is True
    assert snap.catalog_complete is True
    assert snap.bootstrap_complete is True
    assert snap.soft_gate_active is False


def test_format_bootstrap_status_markdown_includes_json(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    md = format_bootstrap_status_markdown(tmp_path)
    assert "GREEN" in md or "SOFT GATE ACTIVE" in md
    assert "```json" in md
    # Payload inside fenced block must be valid JSON.
    start = md.index("```json\n") + len("```json\n")
    end = md.index("\n```", start)
    payload = json.loads(md[start:end])
    assert payload["ok"] is True
    assert "graph_root" in payload
    assert payload["checkpoint_recovery_source"] == "missing"
    assert payload["checkpoint_reset_event"] is False


def test_collect_bootstrap_status_projects_checkpoint_reset_event(tmp_path: Path) -> None:
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    (tmp_path / "pages").mkdir()
    (tmp_path / CHECKPOINT_FILENAME).write_text("{not-json", encoding="utf-8")
    (tmp_path / CHECKPOINT_BAK_FILENAME).write_text("[]", encoding="utf-8")

    snapshot = collect_bootstrap_status(tmp_path)

    assert snapshot.checkpoint_recovery_source == "reset"
    assert snapshot.checkpoint_reset_event is True
    assert snapshot.soft_gate_active is True


def test_state_path_written(tmp_path: Path) -> None:
    (tmp_path / "pages").mkdir()
    from src.agent.maintenance_daemon import DaemonState

    save_daemon_state(
        tmp_path,
        DaemonState(bootstrap_failed=True, bootstrap_failed_reason="test"),
    )
    assert state_path(tmp_path).is_file()
