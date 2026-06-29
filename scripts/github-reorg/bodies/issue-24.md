## Problem Description

Replace the v1.9.5 read path (`master_catalog.json` + in-memory Okapi BM25) with a relational **Shadow DB** for <50 ms latency and hierarchical queries.

## Proposed Architectural Solution

Phases 2–3 of [`ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md).

### Current baseline (v1.12 — to be complemented, not removed until v2.0.0-stable)

| Component | Location |
|-----------|----------|
| JSON catalog | `.matryca_semantic_cache/master_catalog.json` — `src/graph/master_catalog.py` |
| BM25 search | `src/graph/generational_cache.py` (`get_cached_bm25_corpus`) |
| Human catalog hub | `pages/Matryca Master Index.md` (retained in v2.0) |

### Tasks

- [x] Scaffold `shadow.sqlite` DDL (`pages`, `blocks`, `block_refs`, FTS5) — `src/shadow/schema.py` + `tests/test_shadow_schema.py`
- [ ] `GraphRepository` routing ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17)) — Phase 1 prerequisite
- [ ] `open_shadow_db(graph_root)` connection helper + WAL pragmas
- [ ] Incremental ingestion from Markdown via `post_write` / watcher (read-only on source `.md`)
- [ ] FTS5 query helpers + recursive CTEs for subtree / thought-chain reads
- [ ] Opt-in env `MATRYCA_SHADOW_DB_ENABLED=false` (v2.0.0-alpha)
- [ ] Sovereign UI shadow sync health (lag, last full sync)
- [ ] Read routing with BM25/AST **fallback** when shadow disabled or stale

### Dependencies

- **Blocked by** [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) (`GraphRepository`) for clean storage routing

## Estimated Impact

**Alto** — core v2 read performance; alpha ships behind flag only.

## Files Involved

- `src/shadow/` (schema shipped; sync + query modules TBD)
- `src/graph/post_write.py` (sync hook)
- `src/agent/graph_dispatch.py` (read routing Phase 3)
- `tests/test_shadow_*.py`

---
**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**SSOT:** [`docs/roadmaps/ROADMAP_V2_SHADOW_DB.md`](docs/roadmaps/ROADMAP_V2_SHADOW_DB.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
