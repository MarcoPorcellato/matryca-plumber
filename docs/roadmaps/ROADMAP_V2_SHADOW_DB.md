# v2.0 — Shadow DB read path (checklist)

**Detailed index:** [`ROADMAP_V2_PREPARATION.md`](ROADMAP_V2_PREPARATION.md) — visitor SSOT for all five v2 phases  
**Status:** DDL scaffold **shipped** — [`src/shadow/schema.py`](../../src/shadow/schema.py) + [`tests/test_shadow_schema.py`](../../tests/test_shadow_schema.py); sync and routing **not wired**  
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
- [ ] `GraphRepository` routing ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17))
- [ ] Async ingestion from Markdown (Classic Logseq or DB Markdown Mirror)
- [ ] FTS5 query helpers + incremental sync triggers
- [ ] Recursive CTEs (`WITH RECURSIVE`) for sub-tree / thought-chain extraction
- [ ] Background sync daemon (read-only on source `.md` files)
- [ ] Opt-in env flag `MATRYCA_SHADOW_DB_ENABLED` (v2.0.0-alpha)
- [ ] Preflight / Sovereign UI health surface (no `matryca doctor` — see `llms.txt` §2.3)

### Rollout (Epic #20)

| Track | Target |
|-------|--------|
| v2.0.0-alpha | Experimental `shadow.sqlite` behind opt-in env flag |
| v2.0.0-rc | MCP read traffic routed to Shadow DB by default |
| v2.0.0-stable | Deprecate pure in-memory BM25 as default discovery path |

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
