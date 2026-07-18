"""Open ``shadow.sqlite`` under the graph semantic-cache directory (v2 Phase 2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..graph.path_sandbox import assert_path_within_graph, resolved_graph_root
from .config import shadow_db_busy_timeout_ms
from .schema import apply_shadow_schema

_SHADOW_CACHE_DIRNAME = ".matryca_semantic_cache"
_SHADOW_DB_FILENAME = "shadow.sqlite"


def shadow_db_path(graph_root: Path | str) -> Path:
    """Return ``<graph>/.matryca_semantic_cache/shadow.sqlite`` (sandboxed)."""
    root = resolved_graph_root(graph_root)
    path = root / _SHADOW_CACHE_DIRNAME / _SHADOW_DB_FILENAME
    return assert_path_within_graph(path, root)


def open_shadow_db(graph_root: Path | str) -> sqlite3.Connection:
    """Open (or create) ``shadow.sqlite``, apply pragmas + DDL, return connection.

    Caller owns the connection lifetime (``close()``). Path is always under
    ``graph_root`` via :func:`assert_path_within_graph`.
    """
    db_path = shadow_db_path(graph_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    busy_timeout_ms = shadow_db_busy_timeout_ms()
    if busy_timeout_ms > 0:
        connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    try:
        apply_shadow_schema(connection)
        connection.commit()
    except Exception:
        connection.close()
        raise
    return connection


__all__ = [
    "open_shadow_db",
    "shadow_db_path",
]
