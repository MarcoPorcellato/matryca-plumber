"""Shadow DB runtime health resolution (v2 PR-0)."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from ..graph.path_sandbox import resolved_graph_root
from .config import shadow_db_enabled
from .connection import open_shadow_db, shadow_db_path
from .meta import (
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
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
            return ShadowHealthState.READY
        return ShadowHealthState.STALE
    finally:
        conn.close()


__all__ = ["ShadowHealthState", "resolve_shadow_health"]
