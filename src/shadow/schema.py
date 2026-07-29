"""DDL for ``shadow.sqlite`` — Logseq read cache + biological memory graph (v2.0).

Schema-only scaffold: not wired to sync/write paths until GraphRepository (#17)
and Shadow DB ingestion (#24) land. Memory tables gated by
``MATRYCA_MEMORY_GRAPH_ENABLED``.

Spec: ``docs/roadmaps/ROADMAP_V2_SHADOW_DB.md``,
``docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md``.
"""

from __future__ import annotations

import sqlite3

SHADOW_SCHEMA_VERSION = 1

SHADOW_PRAGMAS: tuple[str, ...] = (
    "PRAGMA foreign_keys = ON;",
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
)

SHADOW_READ_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS shadow_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS pages (
        page_id       INTEGER PRIMARY KEY,
        title         TEXT NOT NULL UNIQUE,
        file_path     TEXT NOT NULL,
        file_mtime_ns INTEGER NOT NULL,
        file_size     INTEGER NOT NULL,
        is_journal    INTEGER NOT NULL DEFAULT 0
            CHECK (is_journal IN (0, 1)),
        properties_json TEXT NOT NULL DEFAULT '{}',
        synced_at     TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pages_file_path ON pages (file_path);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_pages_mtime ON pages (file_mtime_ns);
    """,
    """
    -- Pages deliberately excluded from the read cache because bounded parsing could
    -- not complete within the budget. Kept in a separate table so that every existing
    -- `pages` query, FTS trigger, and subtree CTE keeps its exact prior meaning: a
    -- quarantined page is simply absent from `pages`, and reads for it route to
    -- Markdown. Content-free by construction — only the relative file path (already
    -- present in `pages.file_path`) plus size and timing counters are stored.
    CREATE TABLE IF NOT EXISTS quarantined_pages (
        file_path TEXT PRIMARY KEY,
        reason TEXT NOT NULL CHECK (reason IN ('parse_timeout', 'parse_error')),
        byte_count INTEGER NOT NULL DEFAULT 0,
        line_count INTEGER NOT NULL DEFAULT 0,
        attempt_count INTEGER NOT NULL DEFAULT 1,
        first_quarantined_at TEXT NOT NULL,
        last_attempt_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS blocks (
        rowid           INTEGER PRIMARY KEY,
        block_uuid      TEXT NOT NULL UNIQUE,
        page_id         INTEGER NOT NULL
            REFERENCES pages (page_id) ON DELETE CASCADE,
        parent_rowid    INTEGER
            REFERENCES blocks (rowid) ON DELETE CASCADE,
        sort_order      INTEGER NOT NULL,
        indent_level    INTEGER NOT NULL DEFAULT 0,
        content         TEXT NOT NULL DEFAULT '',
        properties_json TEXT NOT NULL DEFAULT '{}',
        synced_at       TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_blocks_page_id ON blocks (page_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_blocks_parent_rowid ON blocks (parent_rowid);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_blocks_block_uuid ON blocks (block_uuid);
    """,
    """
    CREATE TABLE IF NOT EXISTS block_refs (
        source_block_uuid TEXT NOT NULL,
        target_title      TEXT NOT NULL,
        ref_kind          TEXT NOT NULL
            CHECK (ref_kind IN ('wikilink', 'block_ref', 'tag')),
        PRIMARY KEY (source_block_uuid, target_title, ref_kind)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_block_refs_target
        ON block_refs (target_title);
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
        content,
        content='blocks',
        content_rowid='rowid',
        tokenize='unicode61 remove_diacritics 2'
    );
    """,
    """
    CREATE TRIGGER IF NOT EXISTS blocks_fts_ai AFTER INSERT ON blocks BEGIN
        INSERT INTO blocks_fts (rowid, content) VALUES (new.rowid, new.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS blocks_fts_ad AFTER DELETE ON blocks BEGIN
        INSERT INTO blocks_fts (blocks_fts, rowid, content)
            VALUES ('delete', old.rowid, old.content);
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS blocks_fts_au AFTER UPDATE OF content ON blocks BEGIN
        INSERT INTO blocks_fts (blocks_fts, rowid, content)
            VALUES ('delete', old.rowid, old.content);
        INSERT INTO blocks_fts (rowid, content) VALUES (new.rowid, new.content);
    END;
    """,
)

MEMORY_GRAPH_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS memory_nodes (
        id                  TEXT PRIMARY KEY,
        label               TEXT NOT NULL,
        aliases_json        TEXT NOT NULL DEFAULT '[]',
        entity_type         TEXT NOT NULL,
        block_uuid          TEXT,
        first_seen          TEXT NOT NULL,
        last_reinforced     TEXT NOT NULL,
        mention_count       INTEGER NOT NULL DEFAULT 0,
        reinforcement_count INTEGER NOT NULL DEFAULT 0,
        source_files_json   TEXT NOT NULL DEFAULT '[]',
        excerpts_json       TEXT NOT NULL DEFAULT '[]',
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_nodes_block_uuid
        ON memory_nodes (block_uuid);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_nodes_entity_type
        ON memory_nodes (entity_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_nodes_last_reinforced
        ON memory_nodes (last_reinforced);
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_edges (
        id                  TEXT PRIMARY KEY,
        source_id           TEXT NOT NULL
            REFERENCES memory_nodes (id) ON DELETE CASCADE,
        target_id           TEXT NOT NULL
            REFERENCES memory_nodes (id) ON DELETE CASCADE,
        edge_type           TEXT NOT NULL
            CHECK (edge_type IN ('explicit', 'co-occurrence', 'temporal', 'causal')),
        directed            INTEGER NOT NULL DEFAULT 0
            CHECK (directed IN (0, 1)),
        weight              REAL NOT NULL,
        base_weight         REAL NOT NULL,
        reinforcement_count INTEGER NOT NULL DEFAULT 0,
        first_formed        TEXT NOT NULL,
        last_reinforced     TEXT NOT NULL,
        stability           REAL NOT NULL DEFAULT 1.0,
        evidence_json       TEXT NOT NULL DEFAULT '[]',
        is_dormant          INTEGER NOT NULL DEFAULT 0
            CHECK (is_dormant IN (0, 1)),
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL,
        UNIQUE (source_id, target_id, edge_type)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_edges_source
        ON memory_edges (source_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_edges_target
        ON memory_edges (target_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_edges_weight
        ON memory_edges (weight);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_edges_last_reinforced
        ON memory_edges (last_reinforced);
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_pending_edges (
        source_id           TEXT NOT NULL,
        target_id           TEXT NOT NULL,
        edge_type           TEXT NOT NULL
            CHECK (edge_type IN ('co-occurrence', 'temporal')),
        observation_count   INTEGER NOT NULL DEFAULT 1,
        first_seen          TEXT NOT NULL,
        last_seen           TEXT NOT NULL,
        evidence_json       TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY (source_id, target_id, edge_type),
        CHECK (source_id < target_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_episodes (
        id                  TEXT PRIMARY KEY,
        session_id          TEXT,
        started_at          TEXT NOT NULL,
        ended_at            TEXT,
        summary             TEXT NOT NULL DEFAULT '',
        source_channel      TEXT NOT NULL DEFAULT 'unknown'
            CHECK (source_channel IN ('mcp', 'cli', 'daemon', 'unknown')),
        metadata_json       TEXT NOT NULL DEFAULT '{}',
        created_at          TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_episodes_started_at
        ON memory_episodes (started_at);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_episodes_session_id
        ON memory_episodes (session_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_episode_entities (
        episode_id TEXT NOT NULL
            REFERENCES memory_episodes (id) ON DELETE CASCADE,
        node_id    TEXT NOT NULL
            REFERENCES memory_nodes (id) ON DELETE CASCADE,
        PRIMARY KEY (episode_id, node_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_episode_entities_node
        ON memory_episode_entities (node_id);
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_procedures (
        id                  TEXT PRIMARY KEY,
        statement           TEXT NOT NULL,
        category            TEXT NOT NULL DEFAULT 'insight'
            CHECK (category IN (
                'preference', 'skill', 'antipattern', 'insight', 'heuristic', 'lesson'
            )),
        trigger_keywords_json TEXT NOT NULL DEFAULT '[]',
        trigger_contexts_json TEXT NOT NULL DEFAULT '[]',
        confidence          REAL NOT NULL DEFAULT 0.5,
        applications        INTEGER NOT NULL DEFAULT 0,
        contradictions      INTEGER NOT NULL DEFAULT 0,
        stability           REAL NOT NULL DEFAULT 1.0,
        flagged_for_review  INTEGER NOT NULL DEFAULT 0
            CHECK (flagged_for_review IN (0, 1)),
        linked_node_id      TEXT
            REFERENCES memory_nodes (id) ON DELETE SET NULL,
        block_uuid          TEXT,
        page_title          TEXT,
        source_episodes_json TEXT NOT NULL DEFAULT '[]',
        last_applied        TEXT,
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_procedures_category
        ON memory_procedures (category);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_procedures_block_uuid
        ON memory_procedures (block_uuid);
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_snapshots (
        id          TEXT PRIMARY KEY,
        created_at  TEXT NOT NULL,
        label       TEXT,
        graph_json  TEXT NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_snapshots_created_at
        ON memory_snapshots (created_at);
    """,
)

SHADOW_DDL: tuple[str, ...] = SHADOW_READ_DDL + MEMORY_GRAPH_DDL

SHADOW_META_SEED: tuple[tuple[str, str], ...] = (("schema_version", str(SHADOW_SCHEMA_VERSION)),)


def apply_shadow_schema(connection: sqlite3.Connection) -> None:
    """Execute pragmas and DDL on an open SQLite connection (in-memory or on disk)."""
    for pragma in SHADOW_PRAGMAS:
        connection.execute(pragma)
    for statement in SHADOW_DDL:
        connection.execute(statement)
    for key, value in SHADOW_META_SEED:
        connection.execute(
            "INSERT OR IGNORE INTO shadow_meta (key, value) VALUES (?, ?)",
            (key, value),
        )


__all__ = [
    "MEMORY_GRAPH_DDL",
    "SHADOW_DDL",
    "SHADOW_META_SEED",
    "SHADOW_PRAGMAS",
    "SHADOW_READ_DDL",
    "SHADOW_SCHEMA_VERSION",
    "apply_shadow_schema",
]
