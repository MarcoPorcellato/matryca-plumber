"""Open ``shadow.sqlite`` under the graph semantic-cache directory (v2 Phase 2)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..graph.path_sandbox import PathTraversalSecurityError, resolved_graph_root
from ..graph.safety.write_policy import guard_graph_mutation
from .cache_location import (
    ShadowCacheLocation,
    ShadowCacheLocationError,
    resolve_shadow_cache_location,
)
from .config import shadow_db_busy_timeout_ms, shadow_db_enabled
from .schema import apply_shadow_schema


def shadow_db_path(graph_root: Path | str) -> Path:
    """Return ``shadow.sqlite`` for this graph's canonical external cache location."""
    root = resolved_graph_root(graph_root)
    return _resolve_shadow_location_for_graph(root).database_path


def _resolve_shadow_location_for_graph(graph_root: Path | str) -> ShadowCacheLocation:
    root = resolved_graph_root(graph_root)
    try:
        location = resolve_shadow_cache_location(root)
    except ShadowCacheLocationError as exc:
        raise PathTraversalSecurityError(str(exc)) from exc
    return location


def open_shadow_db(graph_root: Path | str) -> sqlite3.Connection:
    """Open (or create) ``shadow.sqlite``, apply pragmas + DDL, return connection.

    Caller owns the connection lifetime (``close()``).
    """
    if not shadow_db_enabled():
        raise RuntimeError("Shadow DB disabled via MATRYCA_SHADOW_DB_ENABLED=false")

    root = resolved_graph_root(graph_root)
    location = _resolve_shadow_location_for_graph(root)
    db_path = location.database_path
    guard_graph_mutation(graph_root, db_path, operation="open_shadow_db")
    try:
        location.ensure_directory()
    except ShadowCacheLocationError as exc:
        raise PathTraversalSecurityError(str(exc)) from exc

    # Revalidate database, WAL/SHM, lock, and containment after directory creation.
    location = _resolve_shadow_location_for_graph(root)
    db_path = location.database_path

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


def open_shadow_db_query_only(graph_root: Path | str) -> sqlite3.Connection:
    """Open an existing Shadow DB for queries without creating or migrating it.

    Caller owns the connection lifetime (``close()``).
    """
    if not shadow_db_enabled():
        raise RuntimeError("Shadow DB disabled via MATRYCA_SHADOW_DB_ENABLED=false")

    root = resolved_graph_root(graph_root)
    db_path = _resolve_shadow_location_for_graph(root).database_path
    connection = sqlite3.connect(f"{db_path.as_uri()}?mode=ro", uri=True)
    try:
        busy_timeout_ms = shadow_db_busy_timeout_ms()
        if busy_timeout_ms > 0:
            connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        connection.execute("PRAGMA query_only = ON")
    except Exception:
        connection.close()
        raise
    return connection


__all__ = [
    "open_shadow_db",
    "open_shadow_db_query_only",
    "shadow_db_path",
]
