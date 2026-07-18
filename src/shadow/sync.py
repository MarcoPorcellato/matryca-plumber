"""Incremental Markdown → shadow.sqlite sync (v2 Phase 2).

Read-only on source ``.md`` files. Upserts ``pages`` / ``blocks`` after
successful graph writes via the page-written port.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from logseq_matryca_parser.graph import StackMachineParser
from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage
from loguru import logger

from ..graph.page_path import page_title_from_path
from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from ..graph.post_write import PageWrittenEvent, register_page_written_handler
from .config import shadow_db_enabled
from .connection import open_shadow_db
from .meta import META_LAST_INCREMENTAL_SYNC_AT, set_meta
from .runtime_state import defer_sync_path, is_shadow_bootstrapping

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


def delete_shadow_page_by_file_path(graph_root: Path | str, rel_path: str) -> None:
    """Remove a page row (and blocks) by sandboxed ``file_path``."""
    if not shadow_db_enabled():
        return
    root = resolved_graph_root(graph_root)
    conn = open_shadow_db(root)
    try:
        conn.execute("DELETE FROM pages WHERE file_path = ?", (rel_path,))
        set_meta(conn, META_LAST_INCREMENTAL_SYNC_AT, _utc_now_iso())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def sync_page_into_connection(
    connection: sqlite3.Connection,
    graph_root: Path,
    page_path: Path,
) -> None:
    """Upsert one page into an open shadow connection (caller manages transaction)."""
    root = resolved_graph_root(graph_root)
    path = assert_path_within_graph(page_path, root)
    if path.suffix.lower() != ".md":
        return

    title = page_title_from_path(root, path)
    rel = path.relative_to(root).as_posix()
    if not path.is_file():
        connection.execute("DELETE FROM pages WHERE file_path = ?", (rel,))
        return

    stat = path.stat()
    text = path.read_text(encoding="utf-8")
    page: LogseqPage = StackMachineParser().parse(text, page_title=title)
    synced_at = _utc_now_iso()
    is_journal = 1 if _is_journal_relpath(rel) else 0
    props_json = _props_json(dict(page.properties or {}))

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
    flat = _walk_blocks(list(page.root_nodes or []), parent_uuid=None, sort_base=0)
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


def _on_shadow_page_written(event: PageWrittenEvent) -> None:
    if event.path.suffix.lower() != ".md":
        return
    try:
        sync_page_to_shadow(event.graph_root, event.path)
    except Exception:  # noqa: BLE001 — fail-safe like AST bridge
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
    "reset_shadow_sync_bridge_for_tests",
    "sync_page_into_connection",
    "sync_page_to_shadow",
]
