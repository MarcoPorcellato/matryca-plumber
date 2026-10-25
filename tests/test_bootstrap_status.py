"""Tests for Phase 1 bootstrap_status read target and Soft Gate semaphore."""

from __future__ import annotations

import hashlib
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


def _graph_fingerprint(root: Path) -> dict[str, tuple[int, int, int, str | None]]:
    """Include directory changes as well as every tiny synthetic file's bytes."""
    result: dict[str, tuple[int, int, int, str | None]] = {}
    for path in (root, *sorted(root.rglob("*"))):
        metadata = path.stat()
        result[path.relative_to(root).as_posix()] = (
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("catalog_ready", [False, True])
async def test_bootstrap_guidance_matches_write_policy_without_changing_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    read_only: bool,
    catalog_ready: bool,
) -> None:
    monkeypatch.setenv("MATRYCA_READ_ONLY", "false")
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Alpha.md"
    page.write_text(
        "- ### Matryca Semantic Index\n- summary:: Synthetic summary\n", encoding="utf-8"
    )
    if catalog_ready:
        catalog = MasterCatalog(graph_root=tmp_path)
        catalog.upsert(
            "Alpha",
            CatalogEntry(
                summary="Synthetic summary",
                domain="risorsa",
                last_mtime=int(page.stat().st_mtime),
            ),
        )
        catalog.save()
        write_master_index_page(tmp_path, catalog)
    monkeypatch.setenv("MATRYCA_READ_ONLY", str(read_only).lower())
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    before = _graph_fingerprint(tmp_path)

    output = await dispatch_read(MatrycaWikiConfig(), "bootstrap_status", "")

    payload = json.loads(output.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["read_only"] is read_only
    assert payload["catalog_complete"] is catalog_ready
    assert payload["bootstrap_complete"] is catalog_ready
    assert payload["soft_gate_active"] is not catalog_ready
    if read_only:
        # Writable catalog reads retain their existing backup-refresh behavior.
        assert _graph_fingerprint(tmp_path) == before
        assert "STRICT READ ONLY" in output
        assert "shadow_status" in output
        assert "graph-local" in output
        assert "explicit authorization" in output
        assert "Local Daemon / Blind Search / Cloud Indexing" not in output
        assert "GREEN: proceed" not in output
    elif catalog_ready:
        assert "GREEN: proceed with Master Index scan" in output
    else:
        assert "Local Daemon / Blind Search / Cloud Indexing" in output


@pytest.mark.asyncio
async def test_read_only_catalog_status_does_not_confuse_ready_external_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.shadow.bootstrap import rebuild_shadow_from_graph
    from src.shadow.state_api import resolve_shadow_db_state_for_api

    (tmp_path / "pages").mkdir()
    (tmp_path / "pages/Alpha.md").write_text(
        "- Synthetic\n  id:: 11111111-1111-4111-8111-111111111111\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    before = _graph_fingerprint(tmp_path)
    # Fixture provisioning is separate from the subsequent status-only call.
    rebuild_shadow_from_graph(tmp_path)
    shadow = resolve_shadow_db_state_for_api(tmp_path)
    assert shadow.state == "ready"
    assert shadow.indexed_page_count == 1

    output = await dispatch_read(MatrycaWikiConfig(), "bootstrap_status", "")

    payload = json.loads(output.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["read_only"] is True
    assert payload["bootstrap_complete"] is False
    assert payload["bootstrap_scanned"] == payload["bootstrap_total"] == 0
    assert payload["checkpoint_recovery_source"] == "missing"
    assert "not external Shadow readiness" in output
    assert _graph_fingerprint(tmp_path) == before


def test_bootstrap_status_refuses_invalid_write_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATRYCA_READ_ONLY", "invalid")
    with pytest.raises(ValueError, match="invalid boolean token"):
        format_bootstrap_status_markdown(tmp_path)
