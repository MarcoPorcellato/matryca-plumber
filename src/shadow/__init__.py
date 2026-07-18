"""Shadow DB (`shadow.sqlite`) — daemon-owned read cache and memory graph layer."""

from .bootstrap import (
    ensure_shadow_runtime_at_startup,
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    shadow_needs_bootstrap,
)
from .config import shadow_db_enabled
from .connection import open_shadow_db, shadow_db_path
from .fts_format import (
    FtsQueryValidationError,
    format_shadow_fts_markdown,
    resolve_bm25_search_markdown,
)
from .health import ShadowHealthState, resolve_shadow_health
from .meta import (
    META_GENERATION,
    META_INDEXED_PAGE_COUNT,
    META_LAST_FULL_SYNC_AT,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_INCREMENTAL_SYNC_AT,
    META_LAST_SYNC_ERROR,
    META_SCHEMA_VERSION,
    META_SOURCE_PAGE_COUNT,
    REQUIRED_META_KEYS,
)
from .query import BlockHit, search_blocks_fts
from .schema import (
    MEMORY_GRAPH_DDL,
    SHADOW_DDL,
    SHADOW_META_SEED,
    SHADOW_PRAGMAS,
    SHADOW_READ_DDL,
    SHADOW_SCHEMA_VERSION,
    apply_shadow_schema,
)
from .sync import (
    delete_shadow_page_by_file_path,
    ensure_shadow_sync_bridge,
    sync_page_to_shadow,
)

__all__ = [
    "MEMORY_GRAPH_DDL",
    "SHADOW_DDL",
    "SHADOW_META_SEED",
    "SHADOW_PRAGMAS",
    "SHADOW_READ_DDL",
    "SHADOW_SCHEMA_VERSION",
    "META_GENERATION",
    "META_INDEXED_PAGE_COUNT",
    "META_LAST_FULL_SYNC_AT",
    "META_LAST_FULL_SYNC_COMPLETED",
    "META_LAST_INCREMENTAL_SYNC_AT",
    "META_LAST_SYNC_ERROR",
    "META_SCHEMA_VERSION",
    "META_SOURCE_PAGE_COUNT",
    "REQUIRED_META_KEYS",
    "BlockHit",
    "FtsQueryValidationError",
    "ShadowHealthState",
    "apply_shadow_schema",
    "delete_shadow_page_by_file_path",
    "ensure_shadow_runtime_at_startup",
    "ensure_shadow_sync_bridge",
    "format_shadow_fts_markdown",
    "handle_shadow_watchdog_change",
    "open_shadow_db",
    "rebuild_shadow_from_graph",
    "resolve_bm25_search_markdown",
    "resolve_shadow_health",
    "search_blocks_fts",
    "shadow_db_enabled",
    "shadow_needs_bootstrap",
    "shadow_db_path",
    "sync_page_to_shadow",
]
