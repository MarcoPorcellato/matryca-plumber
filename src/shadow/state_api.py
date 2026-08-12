"""Shadow DB health snapshot for Sovereign UI ``GET /api/state`` (v2 PR-D / #185)."""

from __future__ import annotations

import re
import sqlite3
from contextlib import suppress
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ..graph.path_sandbox import PathTraversalSecurityError, resolved_graph_root
from ..utils.console_sanitize import sanitize_for_console
from .cache_location import ShadowCacheLocationError, resolve_shadow_cache_location
from .config import shadow_db_enabled
from .connection import open_shadow_db_query_only, shadow_db_path
from .health import shadow_meta_matches_page_rows
from .meta import (
    META_GENERATION,
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
from .sync_failure import SHADOW_SYNC_FAILURE_REASON, is_shadow_sync_failed

ShadowDbStateValue = Literal["disabled", "bootstrapping", "ready", "stale", "error"]
ShadowReadProfileVersion = Literal[1]
ShadowReadProfileCapability = Literal["state"]
_PACKAGE_NAME = "matryca-plumber"

# Content-free classification of why the read cache is not serving accelerated reads.
# These codes never carry page titles, paths, or vault content.
#   not_bootstrapped     - no shadow database file exists yet
#   bootstrap_in_progress- a bootstrap is running in this process
#   database_unreadable  - the file exists but could not be opened or queried
#   schema_version_mismatch - on-disk schema differs from this build
#   sync_error           - a sync error is recorded in metadata
#   full_sync_incomplete - no full sync ever completed; the usual cause is a bootstrap
#                          aborted by the per-page parse budget (see
#                          docs/quality/SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md)
#   page_count_mismatch  - persisted counts disagree with indexed rows
#   cache_unavailable    - external cache location is invalid or unavailable
ShadowDbNotReadyReason = Literal[
    "not_bootstrapped",
    "bootstrap_in_progress",
    "database_unreadable",
    "schema_version_mismatch",
    "sync_error",
    "full_sync_incomplete",
    "page_count_mismatch",
    "cache_unavailable",
]
_SHADOW_ERROR_MAX_LEN = 200
_REDACTED_SYNC_ERROR = "Shadow sync error (path details redacted)"
# Absolute filesystem paths (POSIX or Windows) must never reach the public API.
_ABS_FILESYSTEM_PATH = re.compile(
    r"(?:"
    r"[A-Za-z]:\\[^\s]+|"  # Windows drive path
    r"\\\\[^\s]+|"  # UNC path
    r"/(?:[^/\s]+/)+[^/\s]*"  # POSIX absolute with ≥1 directory segment
    r")"
)


class ShadowDbStateResponse(BaseModel):
    """Stable ``shadow_db`` contract for ``DaemonStateResponse`` (Phase 3)."""

    enabled: bool = False
    state: ShadowDbStateValue = "disabled"
    last_full_sync_at: str | None = None
    source_page_count: int | None = None
    indexed_page_count: int | None = None
    lag_pages: int | None = None
    last_sync_error: str | None = None
    not_ready_reason: ShadowDbNotReadyReason | None = None
    quarantined_page_count: int = 0
    read_profile: ShadowReadProfileResponse | None = None


class ShadowReadProfileResponse(BaseModel):
    """Versioned, content-free producer profile for safe read-side consumers."""

    profile: Literal["shadow-read-profile"] = "shadow-read-profile"
    version: ShadowReadProfileVersion = 1
    producer_version: str
    graph_id: str | None = None
    generation: int | None = None
    state: ShadowDbStateValue
    ready: bool
    schema_compatible: bool | None = None
    capabilities: tuple[ShadowReadProfileCapability, ...] = ("state",)


def _not_ready_reason_from_meta(
    meta: dict[str, str | None], *, actual_page_count: int, quarantined_page_count: int = 0
) -> ShadowDbNotReadyReason | None:
    """Classify why a present Shadow DB is not ``ready``. Content-free by construction."""
    if (meta.get(META_LAST_SYNC_ERROR) or "").strip():
        return "sync_error"
    completed = (meta.get(META_LAST_FULL_SYNC_COMPLETED) or "").strip().lower()
    if completed != "true":
        return "full_sync_incomplete"
    if not shadow_meta_matches_page_rows(
        indexed_page_count=meta.get(META_INDEXED_PAGE_COUNT),
        source_page_count=meta.get(META_SOURCE_PAGE_COUNT),
        actual_page_count=actual_page_count,
        quarantined_page_count=quarantined_page_count,
    ):
        return "page_count_mismatch"
    return None


def _disabled_snapshot() -> ShadowDbStateResponse:
    return _with_read_profile(ShadowDbStateResponse())


@lru_cache(maxsize=1)
def _producer_version() -> str:
    """Return installed package metadata without making version discovery a runtime dependency."""
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


def _with_read_profile(
    snapshot: ShadowDbStateResponse,
    *,
    graph_root: Path | None = None,
    meta: dict[str, str | None] | None = None,
) -> ShadowDbStateResponse:
    """Attach a bounded read profile without opening, creating, or mutating a cache."""
    graph_id: str | None = None
    if graph_root is not None:
        with suppress(OSError, RuntimeError, PathTraversalSecurityError, ShadowCacheLocationError):
            graph_id = resolve_shadow_cache_location(graph_root).graph_id

    schema_raw = (meta or {}).get(META_SCHEMA_VERSION)
    schema_compatible = (
        None if schema_raw is None else schema_raw.strip() == str(SHADOW_SCHEMA_VERSION)
    )
    generation = _parse_non_negative_int((meta or {}).get(META_GENERATION))
    return snapshot.model_copy(
        update={
            "read_profile": ShadowReadProfileResponse(
                producer_version=_producer_version(),
                graph_id=graph_id,
                generation=generation,
                state=snapshot.state,
                ready=snapshot.state == "ready",
                schema_compatible=schema_compatible,
            )
        }
    )


def _bounded_error_message(raw: str | None) -> str | None:
    cleaned = sanitize_for_console((raw or "").strip())
    if not cleaned:
        return None
    if _ABS_FILESYSTEM_PATH.search(cleaned):
        return _REDACTED_SYNC_ERROR
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


def _resolve_lag_pages(source: int | None, indexed: int | None, quarantined: int = 0) -> int | None:
    """Pages still waiting to be indexed.

    Quarantined pages are subtracted: they are not pending work, they are a settled
    decision. Counting them as lag would leave a fully synced graph permanently
    reporting a backlog it will never clear.
    """
    if source is None or indexed is None:
        return None
    return max(0, source - indexed - max(0, quarantined))


def _counts_from_meta(
    meta: dict[str, str | None], quarantined: int = 0
) -> tuple[int | None, int | None, int | None]:
    source = _parse_non_negative_int(meta.get(META_SOURCE_PAGE_COUNT))
    indexed = _parse_non_negative_int(meta.get(META_INDEXED_PAGE_COUNT))
    return source, indexed, _resolve_lag_pages(source, indexed, quarantined)


def _last_full_sync_at(meta: dict[str, str | None]) -> str | None:
    value = (meta.get(META_LAST_FULL_SYNC_AT) or "").strip()
    return value or None


def _read_quarantined_count(connection: sqlite3.Connection) -> int:
    """Count parked pages, tolerating a database written before quarantine existed."""
    try:
        row = connection.execute("SELECT COUNT(*) FROM quarantined_pages").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0]) if row else 0


def _read_meta_readonly(graph_root: Path) -> tuple[dict[str, str | None], int, int]:
    connection = open_shadow_db_query_only(graph_root)
    try:
        meta = {
            META_SCHEMA_VERSION: get_meta(connection, META_SCHEMA_VERSION),
            META_GENERATION: get_meta(connection, META_GENERATION),
            META_LAST_SYNC_ERROR: get_meta(connection, META_LAST_SYNC_ERROR),
            META_LAST_FULL_SYNC_AT: get_meta(connection, META_LAST_FULL_SYNC_AT),
            META_LAST_FULL_SYNC_COMPLETED: get_meta(connection, META_LAST_FULL_SYNC_COMPLETED),
            META_SOURCE_PAGE_COUNT: get_meta(connection, META_SOURCE_PAGE_COUNT),
            META_INDEXED_PAGE_COUNT: get_meta(connection, META_INDEXED_PAGE_COUNT),
        }
        page_count = int(connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
        return meta, page_count, _read_quarantined_count(connection)
    finally:
        connection.close()


def _state_from_meta(
    meta: dict[str, str | None], *, actual_page_count: int, quarantined_page_count: int = 0
) -> ShadowDbStateValue:
    sync_error = (meta.get(META_LAST_SYNC_ERROR) or "").strip()
    if sync_error:
        return "error"
    completed = (meta.get(META_LAST_FULL_SYNC_COMPLETED) or "").strip().lower()
    if completed == "true":
        if not shadow_meta_matches_page_rows(
            indexed_page_count=meta.get(META_INDEXED_PAGE_COUNT),
            source_page_count=meta.get(META_SOURCE_PAGE_COUNT),
            actual_page_count=actual_page_count,
            quarantined_page_count=quarantined_page_count,
        ):
            return "stale"
        return "ready"
    return "stale"


def _snapshot_from_meta(
    *,
    state: ShadowDbStateValue,
    meta: dict[str, str | None],
    last_sync_error: str | None = None,
    not_ready_reason: ShadowDbNotReadyReason | None = None,
    quarantined_page_count: int = 0,
) -> ShadowDbStateResponse:
    source, indexed, lag = _counts_from_meta(meta, quarantined_page_count)
    return ShadowDbStateResponse(
        enabled=True,
        state=state,
        last_full_sync_at=_last_full_sync_at(meta),
        source_page_count=source,
        indexed_page_count=indexed,
        lag_pages=lag,
        last_sync_error=last_sync_error,
        not_ready_reason=not_ready_reason,
        quarantined_page_count=max(0, quarantined_page_count),
    )


def resolve_shadow_db_state_for_api(graph_root: Path | str) -> ShadowDbStateResponse:
    """Build a stable ``shadow_db`` payload without creating a DB when disabled."""
    if not shadow_db_enabled():
        return _disabled_snapshot()

    root = resolved_graph_root(graph_root)
    if is_shadow_bootstrapping(root):
        return _with_read_profile(
            ShadowDbStateResponse(
                enabled=True,
                state="bootstrapping",
                not_ready_reason="bootstrap_in_progress",
            ),
            graph_root=root,
        )
    if is_shadow_sync_failed(root):
        return _with_read_profile(
            ShadowDbStateResponse(
                enabled=True,
                state="error",
                last_sync_error=SHADOW_SYNC_FAILURE_REASON,
                not_ready_reason="sync_error",
            ),
            graph_root=root,
        )

    try:
        db_path = shadow_db_path(root)
    except (OSError, RuntimeError, PathTraversalSecurityError):
        return _with_read_profile(
            ShadowDbStateResponse(
                enabled=True,
                state="error",
                last_sync_error="External Shadow cache unavailable",
                not_ready_reason="cache_unavailable",
            ),
            graph_root=root,
        )
    if not db_path.is_file():
        return _with_read_profile(
            ShadowDbStateResponse(
                enabled=True,
                state="stale",
                not_ready_reason="not_bootstrapped",
            ),
            graph_root=root,
        )

    try:
        meta, page_count, quarantined = _read_meta_readonly(root)
    except sqlite3.Error as exc:
        return _with_read_profile(
            ShadowDbStateResponse(
                enabled=True,
                state="error",
                last_sync_error=_bounded_error_message(str(exc)),
                not_ready_reason="database_unreadable",
            ),
            graph_root=root,
        )

    schema_raw = (meta.get(META_SCHEMA_VERSION) or "").strip()
    if schema_raw != str(SHADOW_SCHEMA_VERSION):
        return _with_read_profile(
            _snapshot_from_meta(
                state="error",
                meta=meta,
                last_sync_error="Shadow schema version mismatch",
                not_ready_reason="schema_version_mismatch",
                quarantined_page_count=quarantined,
            ),
            graph_root=root,
            meta=meta,
        )

    state = _state_from_meta(meta, actual_page_count=page_count, quarantined_page_count=quarantined)
    sync_error = (meta.get(META_LAST_SYNC_ERROR) or "").strip()
    error = _bounded_error_message(sync_error) if state == "error" else None
    return _with_read_profile(
        _snapshot_from_meta(
            state=state,
            meta=meta,
            last_sync_error=error,
            not_ready_reason=_not_ready_reason_from_meta(
                meta, actual_page_count=page_count, quarantined_page_count=quarantined
            ),
            quarantined_page_count=quarantined,
        ),
        graph_root=root,
        meta=meta,
    )


__all__ = [
    "ShadowDbNotReadyReason",
    "ShadowDbStateResponse",
    "ShadowDbStateValue",
    "ShadowReadProfileCapability",
    "ShadowReadProfileResponse",
    "ShadowReadProfileVersion",
    "resolve_shadow_db_state_for_api",
]
