"""Shadow DB health snapshot for Sovereign UI ``GET /api/state`` (v2 PR-D / #185)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ..graph.path_sandbox import resolved_graph_root
from ..utils.console_sanitize import sanitize_for_console
from .config import shadow_db_enabled
from .connection import shadow_db_path
from .meta import (
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_AT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    get_meta,
)
from .runtime_state import is_shadow_bootstrapping
from .schema import SHADOW_SCHEMA_VERSION

ShadowDbStateValue = Literal["disabled", "bootstrapping", "ready", "stale", "error"]
_SHADOW_ERROR_MAX_LEN = 200


class ShadowDbStateResponse(BaseModel):
    """Stable ``shadow_db`` contract for ``DaemonStateResponse`` (Phase 3)."""

    enabled: bool = False
    state: ShadowDbStateValue = "disabled"
    last_full_sync_at: str | None = None
    source_page_count: int | None = None
    indexed_page_count: int | None = None
    lag_pages: int | None = None
    last_sync_error: str | None = None


def _disabled_snapshot() -> ShadowDbStateResponse:
    return ShadowDbStateResponse()


def _bounded_error_message(raw: str | None) -> str | None:
    cleaned = sanitize_for_console((raw or "").strip())
    if not cleaned:
        return None
    if len(cleaned) <= _SHADOW_ERROR_MAX_LEN:
        return cleaned
    return cleaned[: _SHADOW_ERROR_MAX_LEN - 1] + "…"


def _parse_non_negative_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return max(0, int(text))
    except ValueError:
        return None


def _resolve_lag_pages(source: int | None, indexed: int | None) -> int | None:
    if source is None or indexed is None:
        return None
    return max(0, source - indexed)


def _counts_from_meta(meta: dict[str, str | None]) -> tuple[int | None, int | None, int | None]:
    source = _parse_non_negative_int(meta.get(META_SOURCE_PAGE_COUNT))
    indexed = _parse_non_negative_int(meta.get(META_INDEXED_PAGE_COUNT))
    return source, indexed, _resolve_lag_pages(source, indexed)


def _last_full_sync_at(meta: dict[str, str | None]) -> str | None:
    value = (meta.get(META_LAST_FULL_SYNC_AT) or "").strip()
    return value or None


def _read_meta_readonly(db_path: Path) -> dict[str, str | None]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {
            META_SCHEMA_VERSION: get_meta(connection, META_SCHEMA_VERSION),
            META_LAST_SYNC_ERROR: get_meta(connection, META_LAST_SYNC_ERROR),
            META_LAST_FULL_SYNC_AT: get_meta(connection, META_LAST_FULL_SYNC_AT),
            META_LAST_FULL_SYNC_COMPLETED: get_meta(connection, META_LAST_FULL_SYNC_COMPLETED),
            META_SOURCE_PAGE_COUNT: get_meta(connection, META_SOURCE_PAGE_COUNT),
            META_INDEXED_PAGE_COUNT: get_meta(connection, META_INDEXED_PAGE_COUNT),
        }
    finally:
        connection.close()


def _state_from_meta(meta: dict[str, str | None]) -> ShadowDbStateValue:
    sync_error = (meta.get(META_LAST_SYNC_ERROR) or "").strip()
    if sync_error:
        return "error"
    completed = (meta.get(META_LAST_FULL_SYNC_COMPLETED) or "").strip().lower()
    if completed == "true":
        return "ready"
    return "stale"


def _snapshot_from_meta(
    *,
    state: ShadowDbStateValue,
    meta: dict[str, str | None],
    last_sync_error: str | None = None,
) -> ShadowDbStateResponse:
    source, indexed, lag = _counts_from_meta(meta)
    return ShadowDbStateResponse(
        enabled=True,
        state=state,
        last_full_sync_at=_last_full_sync_at(meta),
        source_page_count=source,
        indexed_page_count=indexed,
        lag_pages=lag,
        last_sync_error=last_sync_error,
    )


def resolve_shadow_db_state_for_api(graph_root: Path | str) -> ShadowDbStateResponse:
    """Build a stable ``shadow_db`` payload without creating a DB when disabled."""
    if not shadow_db_enabled():
        return _disabled_snapshot()

    root = resolved_graph_root(graph_root)
    if is_shadow_bootstrapping(root):
        return ShadowDbStateResponse(enabled=True, state="bootstrapping")

    db_path = shadow_db_path(root)
    if not db_path.is_file():
        return ShadowDbStateResponse(enabled=True, state="stale")

    try:
        meta = _read_meta_readonly(db_path)
    except sqlite3.Error as exc:
        return ShadowDbStateResponse(
            enabled=True,
            state="error",
            last_sync_error=_bounded_error_message(str(exc)),
        )

    schema_raw = (meta.get(META_SCHEMA_VERSION) or "").strip()
    if schema_raw != str(SHADOW_SCHEMA_VERSION):
        return _snapshot_from_meta(
            state="error",
            meta=meta,
            last_sync_error="Shadow schema version mismatch",
        )

    state = _state_from_meta(meta)
    sync_error = (meta.get(META_LAST_SYNC_ERROR) or "").strip()
    error = _bounded_error_message(sync_error) if state == "error" else None
    return _snapshot_from_meta(state=state, meta=meta, last_sync_error=error)


__all__ = [
    "ShadowDbStateResponse",
    "ShadowDbStateValue",
    "resolve_shadow_db_state_for_api",
]
