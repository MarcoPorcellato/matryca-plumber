# v2.0 — Shadow DB read path (checklist)

**Detailed index:** [`ROADMAP_V2_PREPARATION.md`](ROADMAP_V2_PREPARATION.md) — visitor SSOT for all five v2 phases  
**Status:** Phase 2 **operational** (bootstrap, reconciliation, runtime gating — [#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248)). Phase 3 **read routing shipped** (opt-in flag, FTS5/BM25 + subtree CTE + Sovereign UI health — [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177)).  
**Parent epic:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Trackable issue:** [#24 — Shadow DB read path](https://github.com/MarcoPorcellato/matryca-plumber/issues/24)  
**Prerequisite:** [#17 — GraphRepository abstraction](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Phase 2–3 tracking in [`v2_preparation_blueprints.md`](../../v2_preparation_blueprints.md)  
**RFC:** [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Replace the v1.9.5 read path (`master_catalog.json` + in-memory Okapi BM25) with a daemon-owned **`shadow.sqlite`** for sub-50 ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices.

Logseq Markdown on disk remains the **system of record**. Shadow DB is a read-only cache synced by the daemon.

---

## Current baseline (v1.9.5 — to be replaced)

| Component | Location |
|-----------|----------|
| JSON catalog | `.matryca_semantic_cache/master_catalog.json` — `src/graph/master_catalog.py` |
| BM25 search | `src/graph/generational_cache.py` (`get_cached_bm25_corpus`) |
| Human catalog hub | `pages/Matryca Master Index.md` (retained in v2.0) |

---

## Schema (`shadow.sqlite`)

Canonical DDL: [`src/shadow/schema.py`](../../src/shadow/schema.py)

| Layer | Tables | Purpose |
|-------|--------|---------|
| **Meta** | `shadow_meta` | Schema version, last full sync, embedding provider metadata |
| **Read cache** | `pages`, `blocks`, `block_refs`, `blocks_fts` | Logseq OG mirror for FTS5 + recursive CTE subtree reads |
| **Memory graph** | `memory_nodes`, `memory_edges`, `memory_pending_edges`, `memory_episodes`, `memory_episode_entities`, `memory_procedures`, `memory_snapshots` | Nacre-inspired biological memory — see [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md) |

Default path: `<LOGSEQ_GRAPH_PATH>/.matryca_semantic_cache/shadow.sqlite` (exact path TBD in `GraphRepository`).

---

## Tasks

### Shadow read path (#24)

- [x] Scaffold `shadow.sqlite` DDL (`pages`, `blocks`, `block_refs`, FTS5) — `src/shadow/schema.py`
- [x] Connection helper — `open_shadow_db` / `shadow_db_path` ([#181](https://github.com/MarcoPorcellato/matryca-plumber/issues/181))
- [x] Incremental post-write upsert — `sync_page_to_shadow` ([#182](https://github.com/MarcoPorcellato/matryca-plumber/issues/182))
- [x] FTS5 query helper — `search_blocks_fts` ([#183](https://github.com/MarcoPorcellato/matryca-plumber/issues/183); dispatch wiring [#250](https://github.com/MarcoPorcellato/matryca-plumber/issues/250))
- [x] Full bootstrap / reconciliation / freshness contract ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248))
- [x] `GraphRepository` read routing — `ShadowGraphRepository` + `get_graph_read_port` ([#255](https://github.com/MarcoPorcellato/matryca-plumber/issues/255))
- [x] Recursive CTEs (`query_subtree_by_block_uuid`) ([#253](https://github.com/MarcoPorcellato/matryca-plumber/issues/253))
- [x] Opt-in env flag `MATRYCA_SHADOW_DB_ENABLED` ([#184](https://github.com/MarcoPorcellato/matryca-plumber/issues/184))
- [x] Sovereign UI shadow health (`/api/state.shadow_db`) ([#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185))

### Rollout (Epic #20)

| Track | Target | Status |
|-------|--------|--------|
| v2.0.0-alpha | Experimental `shadow.sqlite` behind opt-in env flag | **ready for tag** (Phase 3 complete; see [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177)) |
| v2.0.0-rc | MCP read traffic routed to Shadow DB by default | planned |
| v2.0.0-stable | Deprecate pure in-memory BM25 as default discovery path | planned |

---

## Safe-Sync reminder

| Path | Rule |
|------|------|
| **READ** | Shadow DB syncs read-only from Markdown (Classic) or Markdown Mirror (Logseq DB) |
| **WRITE (Logseq OG)** | Append to `.md` + OCC — shipped v1.9.5 ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) partial) |
| **WRITE (Logseq DB)** | Official CLI/API only — never native DB mutation |

Full contract: [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) · [`docs/openspec/llm-os-instructions.md`](../openspec/llm-os-instructions.md)

---

## Related roadmaps

- [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md) — memory graph layer (depends on this schema)
- [`ROADMAP.md`](../../ROADMAP.md) — north-star timeline
