"""Shadow DB runtime health resolution (v2 PR-0)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root
from .config import shadow_db_enabled
from .connection import open_shadow_db, shadow_db_path
from .meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    get_meta,
)
from .runtime_state import is_shadow_bootstrapping
from .schema import SHADOW_SCHEMA_VERSION


class ShadowHealthState(StrEnum):
    DISABLED = "disabled"
    BOOTSTRAPPING = "bootstrapping"
    READY = "ready"
    STALE = "stale"
    ERROR = "error"


def _parse_meta_page_count(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return max(0, int(text))
    except ValueError:
        return None


def shadow_meta_matches_page_rows(
    *,
    indexed_page_count: str | None,
    source_page_count: str | None,
    actual_page_count: int,
) -> bool:
    """Return whether persisted meta counts match the ``pages`` table row count."""
    indexed = _parse_meta_page_count(indexed_page_count)
    source = _parse_meta_page_count(source_page_count)
    if indexed is not None and indexed != actual_page_count:
        return False
    return source is None or source == actual_page_count


def resolve_shadow_health(graph_root: Path | str) -> ShadowHealthState:
    """Resolve the effective Shadow DB health for this process."""
    if not shadow_db_enabled():
        return ShadowHealthState.DISABLED
    root = resolved_graph_root(graph_root)
    if is_shadow_bootstrapping(root):
        return ShadowHealthState.BOOTSTRAPPING
    if not shadow_db_path(root).is_file():
        return ShadowHealthState.STALE

    conn = open_shadow_db(root)
    try:
        schema_raw = get_meta(conn, META_SCHEMA_VERSION)
        if schema_raw != str(SHADOW_SCHEMA_VERSION):
            return ShadowHealthState.ERROR
        sync_error = (get_meta(conn, META_LAST_SYNC_ERROR) or "").strip()
        if sync_error:
            return ShadowHealthState.ERROR
        completed = (get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) or "").strip().lower()
        if completed == "true":
            actual_pages = int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
            if not shadow_meta_matches_page_rows(
                indexed_page_count=get_meta(conn, META_INDEXED_PAGE_COUNT),
                source_page_count=get_meta(conn, META_SOURCE_PAGE_COUNT),
                actual_page_count=actual_pages,
            ):
                return ShadowHealthState.STALE
            return ShadowHealthState.READY
        return ShadowHealthState.STALE
    finally:
        conn.close()


__all__ = [
    "ShadowHealthState",
    "resolve_shadow_health",
    "shadow_meta_matches_page_rows",
]
