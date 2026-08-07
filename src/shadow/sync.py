"""Incremental Markdown → shadow.sqlite sync (v2 Phase 2).

Read-only on source ``.md`` files. Upserts ``pages`` / ``blocks`` after
successful graph writes via the page-written port.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from loguru import logger

from ..graph.bounded_ast_graph import parse_graph_page_bounded
from ..graph.page_path import page_title_from_path
from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from ..graph.post_write import PageWrittenEvent, register_page_written_handler
from .config import shadow_db_enabled, shadow_quarantine_enabled
from .connection import open_shadow_db
from .errors import (
    ShadowPageParseError,
    ShadowSyncError,
    format_bounded_page_parse_error,
    format_duplicate_block_uuid_error,
)
from .meta import (
    META_LAST_INCREMENTAL_SYNC_AT,
    META_LAST_SYNC_ERROR,
    ensure_meta_defaults,
    set_meta,
)
from .quarantine import (
    clear_quarantined_page,
    normalize_quarantine_reason,
    record_quarantined_page,
)
from .runtime_state import (
    defer_sync_path,
    is_shadow_bootstrapping,
)
from .sync_failure import SHADOW_SYNC_FAILURE_REASON, mark_shadow_sync_failed
from .writer_lock import shadow_writer_lock

_bridge_lock = threading.Lock()
_bridge_registered = False


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _block_uuid(node: LogseqNode) -> str:
    props = node.properties or {}
    explicit = props.get("id")
    if explicit:
        return str(explicit).strip()
    if node.source_uuid:
        return str(node.source_uuid).strip()
    return str(node.uuid).strip()


def _props_json(props: dict[str, Any] | None) -> str:
    return json.dumps(props or {}, ensure_ascii=False, sort_keys=True)


def _is_journal_relpath(rel: str) -> bool:
    return rel.startswith("journals/") or "/journals/" in rel


def _walk_blocks(
    nodes: list[LogseqNode],
    *,
    parent_uuid: str | None,
    sort_base: int,
) -> list[tuple[str, str | None, int, int, str, dict[str, Any]]]:
    """Flatten outline to ``(uuid, parent_uuid, sort_order, indent, content, props)``."""
    rows: list[tuple[str, str | None, int, int, str, dict[str, Any]]] = []
    for index, node in enumerate(nodes):
        uuid = _block_uuid(node)
        rows.append(
            (
                uuid,
                parent_uuid,
                sort_base + index,
                int(node.indent_level),
                node.content or "",
                dict(node.properties or {}),
            )
        )
        rows.extend(
            _walk_blocks(
                list(node.children or []),
                parent_uuid=uuid,
                sort_base=0,
            )
        )
    return rows


def _preflight_block_uuids(
    connection: sqlite3.Connection,
    graph_root: Path,
    flat: list[tuple[str, str | None, int, int, str, dict[str, Any]]],
    current_rel: str,
) -> None:
    """Reject duplicate ``block_uuid`` values before insert (no silent dedup).

    When a UUID is owned by another ``file_path`` whose Markdown file no longer
    exists (typical rename), drop the stale shadow page in the same transaction.
    """
    if not flat:
        return

    seen_on_page: set[str] = set()
    for block_uuid, *_rest in flat:
        if block_uuid in seen_on_page:
            raise ShadowSyncError(format_duplicate_block_uuid_error(block_uuid, [current_rel]))
        seen_on_page.add(block_uuid)

    placeholders = ",".join("?" * len(seen_on_page))
    rows = connection.execute(
        f"""
        SELECT b.block_uuid, p.file_path
        FROM blocks b
        JOIN pages p ON b.page_id = p.page_id
        WHERE b.block_uuid IN ({placeholders})
        """,
        tuple(seen_on_page),
    ).fetchall()
    stale_paths: set[str] = set()
    for block_uuid, other_path in rows:
        other_rel = str(other_path)
        if other_rel == current_rel:
            continue
        if (graph_root / other_rel).is_file():
            paths = sorted({current_rel, other_rel})
            raise ShadowSyncError(format_duplicate_block_uuid_error(block_uuid, paths))
        stale_paths.add(other_rel)
    for stale_rel in sorted(stale_paths):
        connection.execute("DELETE FROM pages WHERE file_path = ?", (stale_rel,))


def delete_shadow_page_by_file_path(graph_root: Path | str, rel_path: str) -> None:
    """Remove a page row (and blocks) by sandboxed ``file_path``."""
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    try:
        with shadow_writer_lock(root):
            conn = open_shadow_db(root)
            try:
                conn.execute("DELETE FROM pages WHERE file_path = ?", (rel_path,))
                clear_quarantined_page(conn, rel_path)
                set_meta(conn, META_LAST_INCREMENTAL_SYNC_AT, _utc_now_iso())
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    except Exception:
        record_shadow_sync_failure(root)
        raise


def sync_page_into_connection(
    connection: sqlite3.Connection,
    graph_root: Path,
    page_path: Path,
) -> bool:
    """Upsert one page into an open shadow connection (caller manages transaction).

    Returns whether the page is now present in ``pages``. ``False`` means the page is
    absent by design — non-Markdown, deleted, or quarantined — and reads for it must
    route to Markdown. Callers counting indexed pages must not count a ``False``.
    """
    root = resolved_graph_root(graph_root)
    path = assert_path_within_graph(page_path, root)
    if path.suffix.lower() != ".md":
        return False

    title = page_title_from_path(root, path)
    rel = path.relative_to(root).as_posix()
    if not path.is_file():
        connection.execute("DELETE FROM pages WHERE file_path = ?", (rel,))
        clear_quarantined_page(connection, rel)
        return False

    stat = path.stat()
    parse_result = parse_graph_page_bounded(path, root)
    if not parse_result.ok or not isinstance(parse_result.page, LogseqPage):
        failure = parse_result.failure
        if shadow_quarantine_enabled():
            # Park this page instead of failing the caller. It is removed from `pages`
            # so reads route to Markdown, and the caller keeps indexing the rest of the
            # graph — one pathological page must not disable the cache for all of it.
            connection.execute("DELETE FROM pages WHERE file_path = ?", (rel,))
            record_quarantined_page(
                connection,
                rel,
                reason=normalize_quarantine_reason(failure.error if failure else None),
                byte_count=failure.byte_count if failure else 0,
                line_count=failure.line_count if failure else 0,
                now=_utc_now_iso(),
            )
            return False
        raise ShadowPageParseError(
            format_bounded_page_parse_error(
                category=failure.error if failure else "parse_error",
                content_hash=failure.content_hash if failure else "",
                byte_count=failure.byte_count if failure else 0,
                line_count=failure.line_count if failure else 0,
                mode="stack",
            )
        )
    page = parse_result.page
    # A page that parses again is released: quarantine is a state, not a verdict.
    clear_quarantined_page(connection, rel)
    synced_at = _utc_now_iso()
    is_journal = 1 if _is_journal_relpath(rel) else 0
    props_json = _props_json(dict(page.properties or {}))

    flat = _walk_blocks(list(page.root_nodes or []), parent_uuid=None, sort_base=0)
    _preflight_block_uuids(connection, root, flat, rel)

    connection.execute(
        "DELETE FROM pages WHERE file_path = ? OR title = ?",
        (rel, title),
    )
    cur = connection.execute(
        """
        INSERT INTO pages (
            title, file_path, file_mtime_ns, file_size,
            is_journal, properties_json, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            rel,
            int(stat.st_mtime_ns),
            int(stat.st_size),
            is_journal,
            props_json,
            synced_at,
        ),
    )
    page_id = int(cur.lastrowid or 0)
    if page_id <= 0:
        raise RuntimeError("shadow pages insert returned no page_id")
    uuid_to_rowid: dict[str, int] = {}
    for block_uuid, parent_uuid, sort_order, indent, content, props in flat:
        parent_rowid = uuid_to_rowid.get(parent_uuid) if parent_uuid else None
        block_cur = connection.execute(
            """
            INSERT INTO blocks (
                block_uuid, page_id, parent_rowid, sort_order,
                indent_level, content, properties_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block_uuid,
                page_id,
                parent_rowid,
                sort_order,
                indent,
                content,
                _props_json(props),
                synced_at,
            ),
        )
        rowid = int(block_cur.lastrowid or 0)
        if rowid <= 0:
            raise RuntimeError(f"shadow blocks insert returned no rowid for {block_uuid}")
        uuid_to_rowid[block_uuid] = rowid
    return True


def sync_page_to_shadow(graph_root: Path | str, page_path: Path | str) -> None:
    """Parse ``page_path`` and upsert its rows into ``shadow.sqlite``.

    If the file is missing, remove the corresponding ``pages`` row by ``file_path``.
    """
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    path = assert_path_within_graph(page_path, root)
    if path.suffix.lower() != ".md":
        return
    rel = path.relative_to(root).as_posix()
    if is_shadow_bootstrapping(root):
        defer_sync_path(root, rel)
        return

    try:
        with shadow_writer_lock(root):
            conn = open_shadow_db(root)
            try:
                sync_page_into_connection(conn, root, path)
                set_meta(conn, META_LAST_INCREMENTAL_SYNC_AT, _utc_now_iso())
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    except ShadowPageParseError as exc:
        record_shadow_sync_failure(root, str(exc))
        raise
    except Exception:
        record_shadow_sync_failure(root)
        raise


def record_shadow_sync_failure(
    graph_root: Path,
    message: str = SHADOW_SYNC_FAILURE_REASON,
) -> None:
    """Invalidate reads and best-effort persist one bounded failure reason."""
    mark_shadow_sync_failed(graph_root)
    try:
        conn = open_shadow_db(graph_root)
    except Exception:  # noqa: BLE001 - runtime latch still fails reads closed
        logger.warning("Failed to open Shadow DB while persisting sync failure")
        return
    try:
        try:
            ensure_meta_defaults(conn)
            set_meta(conn, META_LAST_SYNC_ERROR, message)
            conn.commit()
        except Exception:  # noqa: BLE001 - runtime latch still fails reads closed
            with suppress(Exception):
                conn.rollback()
            logger.warning("Failed to persist bounded Shadow sync failure")
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - runtime latch remains authoritative
            logger.warning("Failed to close Shadow DB after sync-failure persistence")


def _on_shadow_page_written(event: PageWrittenEvent) -> None:
    if event.path.suffix.lower() != ".md":
        return
    try:
        sync_page_to_shadow(event.graph_root, event.path)
    except ShadowPageParseError as exc:
        logger.warning("Shadow sync rejected after write: {}", exc)
    except Exception:  # noqa: BLE001 — fail-safe like AST bridge
        record_shadow_sync_failure(event.graph_root)
        logger.exception("Shadow sync failed after write to {}", event.path)


def ensure_shadow_sync_bridge() -> None:
    """Register shadow upsert on the graph-local post-write port (once)."""
    if not shadow_db_enabled():
        return
    global _bridge_registered
    with _bridge_lock:
        if _bridge_registered:
            return
        register_page_written_handler(_on_shadow_page_written)
        _bridge_registered = True


def reset_shadow_sync_bridge_for_tests() -> None:
    """Allow re-registration after ``clear_page_written_handlers`` (tests only)."""
    global _bridge_registered
    with _bridge_lock:
        _bridge_registered = False


__all__ = [
    "delete_shadow_page_by_file_path",
    "ensure_shadow_sync_bridge",
    "record_shadow_sync_failure",
    "reset_shadow_sync_bridge_for_tests",
    "sync_page_into_connection",
    "sync_page_to_shadow",
]
