"""Shadow DB (`shadow.sqlite`) — daemon-owned read cache and memory graph layer."""

from .connection import open_shadow_db, shadow_db_path
from .schema import (
    MEMORY_GRAPH_DDL,
    SHADOW_DDL,
    SHADOW_META_SEED,
    SHADOW_PRAGMAS,
    SHADOW_READ_DDL,
    SHADOW_SCHEMA_VERSION,
    apply_shadow_schema,
)
from .sync import ensure_shadow_sync_bridge, sync_page_to_shadow

__all__ = [
    "MEMORY_GRAPH_DDL",
    "SHADOW_DDL",
    "SHADOW_META_SEED",
    "SHADOW_PRAGMAS",
    "SHADOW_READ_DDL",
    "SHADOW_SCHEMA_VERSION",
    "apply_shadow_schema",
    "ensure_shadow_sync_bridge",
    "open_shadow_db",
    "shadow_db_path",
    "sync_page_to_shadow",
]
