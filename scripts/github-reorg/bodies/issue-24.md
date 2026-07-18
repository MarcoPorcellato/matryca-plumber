## Problem Description

Replace the v1.9.5 read path (`master_catalog.json` + in-memory Okapi BM25) with a relational **Shadow DB** for <50 ms latency and hierarchical queries.

## Proposed Architectural Solution

Phases 2–3 of [`ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md).

### Current baseline (v2.0.0-alpha — complementary, not removed until v2.0.0-stable)

| Component | Location |
|-----------|----------|
| JSON catalog | `.matryca_semantic_cache/master_catalog.json` — `src/graph/master_catalog.py` (BM25 fallback) |
| Shadow DB | `.matryca_semantic_cache/shadow.sqlite` — `src/shadow/` (opt-in when healthy) |
| BM25 search | `src/graph/generational_cache.py` (fallback) + `src/shadow/query.py` (FTS5 when enabled) |
| Human catalog hub | `pages/Matryca Master Index.md` (retained in v2.0) |

### Tasks

- [x] Scaffold `shadow.sqlite` DDL (`pages`, `blocks`, `block_refs`, FTS5) — `src/shadow/schema.py` + `tests/test_shadow_schema.py`
- [x] `GraphReadPort` + `MarkdownGraphRepository` / `ShadowGraphRepository` ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17)) — Phase 1
- [x] `open_shadow_db(graph_root)` connection helper + WAL pragmas — `src/shadow/connection.py`
- [x] Incremental ingestion from Markdown via `post_write` / watcher (read-only on source `.md`) — `src/shadow/sync.py`
- [x] FTS5 query helpers + recursive CTEs for subtree / thought-chain reads — `src/shadow/query.py`, `src/shadow/subtree.py`
- [x] Opt-in env `MATRYCA_SHADOW_DB_ENABLED=false` (v2.0.0-alpha) — `src/shadow/config.py`
- [x] Sovereign UI shadow sync health (lag, last full sync) — `/api/state.shadow_db`
- [x] Read routing with BM25/AST **fallback** when shadow disabled or stale — `get_graph_read_port`, dispatch handlers
- [x] Duplicate block UUID pre-insert diagnostics ([#251](https://github.com/MarcoPorcellato/matryca-plumber/issues/251))

### Status

**Closed at `v2.0.0-alpha`** (2026-07-18). Default-off flag preserves v1.14.x operator behavior.

## Estimated Impact

**Alto** — core v2 read performance; alpha ships behind flag only.

## Files Involved

- `src/shadow/` (schema, connection, sync, query, subtree, bootstrap, errors)
- `src/agent/shadow_graph_repository.py`, `src/agent/graph_read_port.py`
- `src/graph/post_write.py` (sync hook)
- `src/agent/dispatch_search_handlers.py`, `src/agent/dispatch_read_handlers.py` (read routing Phase 3)
- `tests/test_shadow_*.py`

---
**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**SSOT:** [`docs/roadmaps/ROADMAP_V2_SHADOW_DB.md`](docs/roadmaps/ROADMAP_V2_SHADOW_DB.md)

_Closed at `v2.0.0-alpha` with tests green (`make ci`) and CHANGELOG updated._
