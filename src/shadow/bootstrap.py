"""Full-graph bootstrap and external-change reconciliation for Shadow DB (v2 PR-0)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from ..daemon.file_watcher import FileEventKind
from ..graph.alias_index import iter_alias_source_paths
from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from .config import shadow_db_enabled
from .connection import open_shadow_db, shadow_db_path
from .meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_AT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SOURCE_PAGE_COUNT,
    bump_generation,
    ensure_meta_defaults,
    set_meta,
)
from .runtime_state import (
    clear_bootstrapping,
    is_shadow_bootstrapping,
    mark_bootstrapping,
    pop_deferred_sync_paths,
    rebuild_lock_for,
)
from .schema import SHADOW_SCHEMA_VERSION
from .sync import delete_shadow_page_by_file_path, sync_page_to_shadow

_BOOTSTRAP_CHECKED: set[str] = set()


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def shadow_needs_bootstrap(graph_root: Path | str) -> bool:
    """Return whether a compatible full sync generation is missing."""
    root = resolved_graph_root(graph_root)
    if not shadow_db_path(root).is_file():
        return True
    conn = open_shadow_db(root)
    try:
        from .meta import get_meta

        schema_raw = get_meta(conn, "schema_version")
        if schema_raw != str(SHADOW_SCHEMA_VERSION):
            return True
        completed = (get_meta(conn, "last_full_sync_completed") or "").strip().lower()
        return completed != "true"
    finally:
        conn.close()


def rebuild_shadow_from_graph(graph_root: Path | str) -> None:
    """Scan ``pages/`` + ``journals/`` and rebuild ``shadow.sqlite`` atomically."""
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    with rebuild_lock_for(root):
        mark_bootstrapping(root)
        conn = open_shadow_db(root)
        try:
            source_paths = iter_alias_source_paths(root)
            source_count = len(source_paths)
            synced_at = _utc_now_iso()
            conn.execute("BEGIN IMMEDIATE")
            try:
                ensure_meta_defaults(conn)
                set_meta(conn, META_LAST_FULL_SYNC_COMPLETED, "false")
                set_meta(conn, META_LAST_SYNC_ERROR, "")
                conn.execute("DELETE FROM pages")

                indexed = 0
                for path in source_paths:
                    from .sync import sync_page_into_connection

                    sync_page_into_connection(conn, root, path)
                    indexed += 1

                bump_generation(conn)
                set_meta(conn, META_LAST_FULL_SYNC_AT, synced_at)
                set_meta(conn, META_LAST_FULL_SYNC_COMPLETED, "true")
                set_meta(conn, META_SOURCE_PAGE_COUNT, str(source_count))
                set_meta(conn, META_INDEXED_PAGE_COUNT, str(indexed))
                set_meta(conn, META_LAST_SYNC_ERROR, "")
                conn.commit()
            except Exception:
                conn.rollback()
                _record_rebuild_error(root, "full rebuild failed")
                raise
        finally:
            conn.close()
            clear_bootstrapping(root)
            _replay_deferred_syncs(root)


def _record_rebuild_error(graph_root: Path, message: str) -> None:
    conn = open_shadow_db(graph_root)
    try:
        ensure_meta_defaults(conn)
        set_meta(conn, META_LAST_FULL_SYNC_COMPLETED, "false")
        set_meta(conn, META_LAST_SYNC_ERROR, message)
        conn.commit()
    except Exception:  # noqa: BLE001 — best-effort error meta
        logger.exception("Failed to persist shadow rebuild error for {}", graph_root)
    finally:
        conn.close()


def _replay_deferred_syncs(graph_root: Path) -> None:
    for rel in pop_deferred_sync_paths(graph_root):
        try:
            sync_page_to_shadow(graph_root, graph_root / rel)
        except Exception:  # noqa: BLE001
            logger.exception("Deferred shadow sync failed for {}", rel)


def ensure_shadow_runtime_at_startup(graph_root: Path | str) -> None:
    """Activate shadow sync bridge and run bootstrap when the flag is enabled."""
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    from .sync import ensure_shadow_sync_bridge

    ensure_shadow_sync_bridge()
    key = str(root)
    if key in _BOOTSTRAP_CHECKED and not shadow_needs_bootstrap(root):
        return
    if shadow_needs_bootstrap(root):
        rebuild_shadow_from_graph(root)
    _BOOTSTRAP_CHECKED.add(key)


def reset_shadow_bootstrap_checked_for_tests() -> None:
    _BOOTSTRAP_CHECKED.clear()


def handle_shadow_watchdog_change(
    graph_root: Path | str,
    path: Path | str,
    kind: FileEventKind,
) -> None:
    """Sync or delete shadow rows after debounced external vault edits."""
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    safe = assert_path_within_graph(path, root)
    if safe.suffix.lower() != ".md":
        return
    rel = safe.relative_to(root).as_posix()
    if is_shadow_bootstrapping(root):
        from .runtime_state import defer_sync_path

        defer_sync_path(root, rel)
        return
    if kind == "deleted":
        delete_shadow_page_by_file_path(root, rel)
        return
    sync_page_to_shadow(root, safe)


__all__ = [
    "ensure_shadow_runtime_at_startup",
    "handle_shadow_watchdog_change",
    "rebuild_shadow_from_graph",
    "reset_shadow_bootstrap_checked_for_tests",
    "shadow_needs_bootstrap",
]
