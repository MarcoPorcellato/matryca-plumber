"""Tests for Phase 1 bootstrap_status read target and Soft Gate semaphore."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from src.agent.graph_dispatch import dispatch_read
from src.agent.maintenance_daemon import save_daemon_state, state_path
from src.config import MatrycaWikiConfig
from src.graph.bootstrap_status import (
    BootstrapStatusSnapshot,
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


def _forbid_shadow_and_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any Shadow probe/init/rebuild or AST parse fail loudly."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("bootstrap_status must not touch Shadow or the AST parser")

    import logseq_matryca_parser
    import src.graph.bounded_page_parse as bounded_parse
    import src.shadow.bootstrap as shadow_bootstrap
    import src.shadow.connection as shadow_connection
    import src.shadow.state_api as shadow_state_api

    monkeypatch.setattr(shadow_state_api, "resolve_shadow_db_state_for_api", _boom)
    monkeypatch.setattr(shadow_bootstrap, "rebuild_shadow_from_graph", _boom)
    monkeypatch.setattr(shadow_connection, "open_shadow_db", _boom)
    monkeypatch.setattr(shadow_connection, "open_shadow_db_query_only", _boom)
    monkeypatch.setattr(bounded_parse, "parse_page_text_bounded", _boom)
    for name in ("parse", "parse_file", "parse_page_file"):
        monkeypatch.setattr(logseq_matryca_parser.LogosParser, name, _boom)


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
    # Fixture provisioning (external cache) is separate from the status-only call.
    rebuild_shadow_from_graph(tmp_path)
    shadow = resolve_shadow_db_state_for_api(tmp_path)
    assert shadow.state == "ready"
    assert shadow.indexed_page_count == 1
    before = _graph_fingerprint(tmp_path)
    _forbid_shadow_and_parser(monkeypatch)

    output = await dispatch_read(MatrycaWikiConfig(), "bootstrap_status", "")

    payload = json.loads(output.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert payload["read_only"] is True
    assert payload["bootstrap_complete"] is False
    assert payload["bootstrap_scanned"] == payload["bootstrap_total"] == 0
    assert payload["checkpoint_recovery_source"] == "missing"
    assert payload["status_scope"] == "graph_local_catalog"
    assert payload["bootstrap_progress_source"] == "graph_local_daemon_checkpoint"
    assert payload["catalog_gate_reasons"] == ["master_index_missing"]
    assert payload["catalog_bootstrap_action"] == "not_permitted_read_only"
    assert "not external Shadow readiness" in output
    assert _graph_fingerprint(tmp_path) == before


def test_bootstrap_status_refuses_invalid_write_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATRYCA_READ_ONLY", "invalid")
    with pytest.raises(ValueError, match="invalid boolean token"):
        format_bootstrap_status_markdown(tmp_path)


# ---------------------------------------------------------------------------
# Issue #656: explanatory fields. Legacy payload characterization comes first.
# ---------------------------------------------------------------------------

_NEW_KEYS = (
    "status_scope",
    "bootstrap_progress_source",
    "catalog_gate_reasons",
    "catalog_bootstrap_action",
)


def _payload_of(root: Path) -> dict[str, object]:
    md = format_bootstrap_status_markdown(root)
    start = md.index("```json\n") + len("```json\n")
    end = md.index("\n```", start)
    parsed = json.loads(md[start:end])
    assert isinstance(parsed, dict)
    return parsed


def _legacy_view(payload: dict[str, object]) -> dict[str, object]:
    """Drop ONLY the four additive keys; everything else is compared verbatim."""
    view = dict(payload)
    for key in _NEW_KEYS:
        view.pop(key, None)
    return view


def _write_checkpoint(root: Path, **fields: object) -> None:
    from src.daemon.checkpoint import CHECKPOINT_FILENAME

    (root / CHECKPOINT_FILENAME).write_text(json.dumps(fields), encoding="utf-8")


def _write_catalog_page(root: Path, title: str = "Alpha") -> Path:
    page = root / "pages" / f"{title}.md"
    page.write_text(
        f"- ### Matryca Semantic Index\n- summary:: {title} synthetic summary\n",
        encoding="utf-8",
    )
    return page


def _write_master_index(root: Path, page: Path, title: str = "Alpha") -> None:
    catalog = MasterCatalog(graph_root=root)
    catalog.upsert(
        title,
        CatalogEntry(
            summary=f"{title} synthetic summary",
            domain="risorsa",
            last_mtime=int(page.stat().st_mtime_ns // 1_000_000_000),
        ),
    )
    catalog.save()
    write_master_index_page(root, catalog)


def _build_case(root: Path, case: str) -> None:
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    (root / "pages").mkdir()
    if case == "missing":
        return
    if case in {"complete", "complete_no_checkpoint", "stale", "incomplete"}:
        _write_master_index(root, _write_catalog_page(root))
    if case == "complete":
        _write_checkpoint(
            root, bootstrap_complete=True, bootstrap_scanned=1, bootstrap_total=1, status="idle"
        )
    elif case == "incomplete":
        _write_catalog_page(root, "Beta")
    elif case == "stale":
        # Daemon says done, Master Index exists, but a second page is not catalogued.
        _write_catalog_page(root, "Beta")
        _write_checkpoint(
            root, bootstrap_complete=True, bootstrap_scanned=1, bootstrap_total=1, status="idle"
        )
    elif case == "daemon_complete_no_index":
        _write_checkpoint(
            root, bootstrap_complete=True, bootstrap_scanned=1, bootstrap_total=1, status="idle"
        )
    elif case == "failed":
        _write_checkpoint(
            root,
            bootstrap_failed=True,
            bootstrap_failed_reason="synthetic failure",
            bootstrap_scanned=3,
            bootstrap_total=10,
            status="idle",
        )
    elif case == "progressing":
        _write_checkpoint(root, bootstrap_scanned=3, bootstrap_total=10, status="running")
    elif case == "backup":
        (root / CHECKPOINT_FILENAME).write_text("{not-json", encoding="utf-8")
        (root / CHECKPOINT_BAK_FILENAME).write_text(
            json.dumps({"bootstrap_scanned": 2, "bootstrap_total": 5, "status": "running"}),
            encoding="utf-8",
        )
    elif case == "reset":
        (root / CHECKPOINT_FILENAME).write_text("{not-json", encoding="utf-8")
        (root / CHECKPOINT_BAK_FILENAME).write_text("[]", encoding="utf-8")


def _legacy_literal(root: Path, read_only: bool, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bootstrap_complete": False,
        "bootstrap_failed": False,
        "bootstrap_failed_reason": None,
        "bootstrap_scanned": 0,
        "bootstrap_total": 0,
        "master_index_present": False,
        "catalog_complete": False,
        "catalog_stale": False,
        "phase1_in_progress": False,
        "soft_gate_active": True,
        "daemon_status": None,
        "checkpoint_recovery_source": "missing",
        "checkpoint_reset_event": False,
        "read_only": read_only,
        "ok": True,
        "graph_root": str(root.resolve()),
    }
    base.update(overrides)
    return base


# Per-case deltas from the "missing" baseline, written as explicit literals.
_LEGACY_DELTAS: dict[str, dict[str, object]] = {
    "missing": {},
    "complete": {
        "bootstrap_complete": True,
        "bootstrap_scanned": 1,
        "bootstrap_total": 1,
        "master_index_present": True,
        "catalog_complete": True,
        "soft_gate_active": False,
        "daemon_status": "idle",
        "checkpoint_recovery_source": "primary",
    },
    "complete_no_checkpoint": {
        "bootstrap_complete": True,
        "master_index_present": True,
        "catalog_complete": True,
        "soft_gate_active": False,
    },
    "incomplete": {"master_index_present": True},
    "daemon_complete_no_index": {
        # Legacy quirk: daemon-complete without a Master Index is flagged stale.
        "catalog_stale": True,
        "bootstrap_scanned": 1,
        "bootstrap_total": 1,
        "daemon_status": "idle",
        "checkpoint_recovery_source": "primary",
    },
    "stale": {
        "master_index_present": True,
        "catalog_stale": True,
        "bootstrap_scanned": 1,
        "bootstrap_total": 1,
        "daemon_status": "idle",
        "checkpoint_recovery_source": "primary",
    },
    "failed": {
        "bootstrap_failed": True,
        "bootstrap_failed_reason": "synthetic failure",
        "bootstrap_scanned": 3,
        "bootstrap_total": 10,
        "daemon_status": "idle",
        "checkpoint_recovery_source": "primary",
    },
    "progressing": {
        "phase1_in_progress": True,
        "bootstrap_scanned": 3,
        "bootstrap_total": 10,
        "daemon_status": "running",
        "checkpoint_recovery_source": "primary",
    },
    "backup": {
        "phase1_in_progress": True,
        "bootstrap_scanned": 2,
        "bootstrap_total": 5,
        "daemon_status": "running",
        "checkpoint_recovery_source": "backup",
    },
    "reset": {
        "checkpoint_recovery_source": "reset",
        "checkpoint_reset_event": True,
    },
}
_CASES = tuple(_LEGACY_DELTAS)


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("case", _CASES)
def test_bootstrap_status_legacy_payload_is_frozen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    read_only: bool,
) -> None:
    # Fixtures are provisioned writable; the policy under test applies afterwards.
    monkeypatch.setenv("MATRYCA_READ_ONLY", "false")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    _build_case(tmp_path, case)
    monkeypatch.setenv("MATRYCA_READ_ONLY", str(read_only).lower())

    payload = _payload_of(tmp_path)

    expected = _legacy_literal(tmp_path, read_only, **_LEGACY_DELTAS[case])
    assert _legacy_view(payload) == expected
    # Legacy keys keep their relative order, with ok/graph_root last.
    assert list(_legacy_view(payload)) == list(expected)


# ---------------------------------------------------------------------------
# Issue #656: new explanatory fields (expected values are explicit literals).
# ---------------------------------------------------------------------------

_EXPECTED_REASONS: dict[str, list[str]] = {
    "missing": ["master_index_missing"],
    "complete": [],
    "complete_no_checkpoint": [],
    "incomplete": ["catalog_incomplete"],
    "daemon_complete_no_index": ["master_index_missing"],
    "stale": ["catalog_stale"],
    "failed": ["master_index_missing", "bootstrap_failed"],
    "progressing": ["master_index_missing", "phase1_in_progress"],
    "backup": ["master_index_missing", "phase1_in_progress"],
    "reset": ["master_index_missing"],
}


def _new_fields(payload: dict[str, object]) -> dict[str, object]:
    return {key: payload[key] for key in _NEW_KEYS}


def _expected_new_fields(case: str, read_only: bool) -> dict[str, object]:
    reasons = _EXPECTED_REASONS[case]
    if not reasons:
        action = "not_required"
    elif read_only:
        action = "not_permitted_read_only"
    else:
        action = "requires_explicit_authorization"
    return {
        "status_scope": "graph_local_catalog",
        "bootstrap_progress_source": "graph_local_daemon_checkpoint",
        "catalog_gate_reasons": reasons,
        "catalog_bootstrap_action": action,
    }


def _provision(root: Path, case: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_READ_ONLY", "false")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(root))
    _build_case(root, case)


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("case", tuple(_EXPECTED_REASONS))
def test_bootstrap_status_explanatory_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    read_only: bool,
) -> None:
    _provision(tmp_path, case, monkeypatch)
    monkeypatch.setenv("MATRYCA_READ_ONLY", str(read_only).lower())

    payload = _payload_of(tmp_path)

    assert _new_fields(payload) == _expected_new_fields(case, read_only)
    # Additive keys come last, in the documented order.
    assert list(payload)[-4:] == list(_NEW_KEYS)
    assert list(payload)[-6:-4] == ["ok", "graph_root"]


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("case", tuple(_EXPECTED_REASONS))
def test_catalog_gate_reasons_empty_iff_soft_gate_inactive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    read_only: bool,
) -> None:
    _provision(tmp_path, case, monkeypatch)
    monkeypatch.setenv("MATRYCA_READ_ONLY", str(read_only).lower())

    payload = _payload_of(tmp_path)

    assert (payload["catalog_gate_reasons"] == []) is (payload["soft_gate_active"] is False)
    assert (payload["catalog_bootstrap_action"] == "not_required") is (
        payload["soft_gate_active"] is False
    )


def test_missing_index_takes_precedence_over_stale_and_partial_failure_is_not_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _provision(root_a, "daemon_complete_no_index", monkeypatch)
    _provision(root_b, "failed", monkeypatch)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    a = _payload_of(root_a)
    b = _payload_of(root_b)

    assert a["catalog_stale"] is True  # legacy flag unchanged
    assert a["catalog_gate_reasons"] == ["master_index_missing"]
    assert b["bootstrap_scanned"] == 3
    assert b["phase1_in_progress"] is False
    assert b["catalog_gate_reasons"] == ["master_index_missing", "bootstrap_failed"]


def test_complete_catalog_without_checkpoint_has_no_reasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _provision(tmp_path, "complete_no_checkpoint", monkeypatch)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    payload = _payload_of(tmp_path)

    assert payload["checkpoint_recovery_source"] == "missing"
    assert payload["catalog_gate_reasons"] == []
    assert payload["catalog_bootstrap_action"] == "not_required"


def test_read_only_complete_catalog_with_unbuilt_shadow_stays_graph_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_shadow_cache_root: Path,
) -> None:
    _provision(tmp_path, "complete_no_checkpoint", monkeypatch)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    assert not isolated_shadow_cache_root.exists()
    before = _graph_fingerprint(tmp_path)
    _forbid_shadow_and_parser(monkeypatch)

    payload = _payload_of(tmp_path)

    assert payload["catalog_gate_reasons"] == []
    assert payload["catalog_bootstrap_action"] == "not_required"
    assert payload["status_scope"] == "graph_local_catalog"
    assert not isolated_shadow_cache_root.exists()
    assert _graph_fingerprint(tmp_path) == before


def _corrupt_catalog_json(root: Path) -> None:
    from src.graph.master_catalog import clear_master_catalog_cache

    catalog_file = MasterCatalog.catalog_path(root)
    assert catalog_file.is_file()
    catalog_file.write_text("{not-json", encoding="utf-8")
    for sibling in catalog_file.parent.glob("*.bak"):
        sibling.unlink()
    clear_master_catalog_cache(root)


@pytest.mark.parametrize("variant", ["checkpoint", "catalog", "no_index"])
def test_strict_read_only_corruption_does_not_mutate_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
) -> None:
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    case = {"checkpoint": "reset", "catalog": "complete_no_checkpoint", "no_index": "missing"}[
        variant
    ]
    _provision(tmp_path, case, monkeypatch)
    if variant == "checkpoint":
        (tmp_path / CHECKPOINT_FILENAME).write_text("{not-json", encoding="utf-8")
        (tmp_path / CHECKPOINT_BAK_FILENAME).write_text("{also-bad", encoding="utf-8")
    elif variant == "catalog":
        _corrupt_catalog_json(tmp_path)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    before = _graph_fingerprint(tmp_path)
    _forbid_shadow_and_parser(monkeypatch)

    payload = _payload_of(tmp_path)

    assert _graph_fingerprint(tmp_path) == before
    assert payload["status_scope"] == "graph_local_catalog"
    assert payload["bootstrap_progress_source"] == "graph_local_daemon_checkpoint"
    assert payload["catalog_bootstrap_action"] == "not_permitted_read_only"
    expected = {
        "checkpoint": ["master_index_missing"],
        "catalog": ["catalog_incomplete"],
        "no_index": ["master_index_missing"],
    }[variant]
    assert payload["catalog_gate_reasons"] == expected
    if variant == "checkpoint":
        assert payload["checkpoint_recovery_source"] == "reset"
        assert payload["checkpoint_reset_event"] is True


def test_writable_corruption_reports_fields_alongside_existing_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Characterize writable recovery (restore/quarantine); no purity claim is made."""
    from src.daemon.checkpoint import CHECKPOINT_BAK_FILENAME, CHECKPOINT_FILENAME

    cp_root = tmp_path / "cp"
    cat_root = tmp_path / "cat"
    cp_root.mkdir()
    cat_root.mkdir()
    _provision(cp_root, "backup", monkeypatch)
    _provision(cat_root, "complete_no_checkpoint", monkeypatch)
    _corrupt_catalog_json(cat_root)

    cp = _payload_of(cp_root)
    cat = _payload_of(cat_root)

    assert cp["checkpoint_recovery_source"] == "backup"
    assert cp["bootstrap_scanned"] == 2
    assert cp["catalog_gate_reasons"] == ["master_index_missing", "phase1_in_progress"]
    assert cp["catalog_bootstrap_action"] == "requires_explicit_authorization"
    # Existing writable behavior restores the primary from the backup.
    assert (cp_root / CHECKPOINT_FILENAME).read_text(encoding="utf-8") == (
        cp_root / CHECKPOINT_BAK_FILENAME
    ).read_text(encoding="utf-8")
    assert cat["catalog_complete"] is False
    assert cat["catalog_gate_reasons"] == ["catalog_incomplete"]
    assert cat["catalog_bootstrap_action"] == "requires_explicit_authorization"


def _snapshot(**overrides: Any) -> BootstrapStatusSnapshot:
    base = BootstrapStatusSnapshot(
        bootstrap_complete=False,
        bootstrap_failed=False,
        bootstrap_failed_reason=None,
        bootstrap_scanned=0,
        bootstrap_total=0,
        master_index_present=True,
        catalog_complete=True,
        catalog_stale=False,
        phase1_in_progress=False,
        soft_gate_active=False,
        daemon_status=None,
        checkpoint_recovery_source="missing",
        checkpoint_reset_event=False,
        read_only=False,
    )
    return replace(base, **overrides)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, ()),
        ({"master_index_present": False, "catalog_complete": False}, ("master_index_missing",)),
        (
            {"master_index_present": False, "catalog_complete": False, "catalog_stale": True},
            ("master_index_missing",),
        ),
        ({"catalog_complete": False}, ("catalog_incomplete",)),
        ({"catalog_complete": False, "catalog_stale": True}, ("catalog_stale",)),
        ({"catalog_stale": True}, ()),  # stale flag alone never wins over a complete catalog
        ({"bootstrap_failed": True}, ("bootstrap_failed",)),
        ({"phase1_in_progress": True}, ("phase1_in_progress",)),
        (
            {"bootstrap_failed": True, "phase1_in_progress": True},
            ("bootstrap_failed", "phase1_in_progress"),
        ),
        (
            {
                "master_index_present": False,
                "catalog_complete": False,
                "bootstrap_failed": True,
                "phase1_in_progress": True,
            },
            ("master_index_missing", "bootstrap_failed", "phase1_in_progress"),
        ),
        (
            {
                "catalog_complete": False,
                "catalog_stale": True,
                "bootstrap_failed": True,
                "phase1_in_progress": True,
            },
            ("catalog_stale", "bootstrap_failed", "phase1_in_progress"),
        ),
    ],
)
def test_catalog_gate_reasons_truth_table(
    overrides: dict[str, Any], expected: tuple[str, ...]
) -> None:
    from src.graph.bootstrap_status import _catalog_gate_reasons

    assert _catalog_gate_reasons(_snapshot(**overrides)) == expected


@pytest.mark.parametrize(
    ("soft_gate_active", "read_only", "expected"),
    [
        (False, False, "not_required"),
        (False, True, "not_required"),
        (True, True, "not_permitted_read_only"),
        (True, False, "requires_explicit_authorization"),
    ],
)
def test_catalog_bootstrap_action_truth_table(
    soft_gate_active: bool, read_only: bool, expected: str
) -> None:
    from src.graph.bootstrap_status import _catalog_bootstrap_action

    snapshot = _snapshot(soft_gate_active=soft_gate_active, read_only=read_only)
    assert _catalog_bootstrap_action(snapshot) == expected


def test_explanatory_fields_helper_serializes_reasons_as_list() -> None:
    from src.graph.bootstrap_status import _explanatory_fields

    fields = _explanatory_fields(
        _snapshot(catalog_complete=False, soft_gate_active=True, read_only=True)
    )

    assert fields == {
        "status_scope": "graph_local_catalog",
        "bootstrap_progress_source": "graph_local_daemon_checkpoint",
        "catalog_gate_reasons": ["catalog_incomplete"],
        "catalog_bootstrap_action": "not_permitted_read_only",
    }
    assert isinstance(fields["catalog_gate_reasons"], list)
    assert list(fields) == list(_NEW_KEYS)
