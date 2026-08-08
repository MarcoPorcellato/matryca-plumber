# v2.0 — Shadow DB read path (checklist)

**Detailed index:** [`ROADMAP_V2_PREPARATION.md`](ROADMAP_V2_PREPARATION.md) — visitor SSOT for all five v2 phases  
**Milestone history:** Phase 2 bootstrap/reconciliation shipped through [#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176) and [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248); Phase 3 read routing shipped through [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177); `v2.0.0-beta.1` / `2.0.0b1` is the historical default-off, graph-local publication. Current RC runtime behavior: [v2 operator contract](../knowledge/architecture/shadow-db.md). Current qualification: [RC and stable readiness](../quality/issue-bodies/v2-rc-stable-readiness.md).
**Parent epic:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Trackable issue:** [#24 — Shadow DB read path](https://github.com/MarcoPorcellato/matryca-plumber/issues/24)  
**Prerequisite:** [#17 — GraphRepository abstraction](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Phase 2–3 tracking in [`v2_preparation_blueprints.md`](../../v2_preparation_blueprints.md)  
**RFC:** [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Replace the v1.9.5 read path (`master_catalog.json` + in-memory Okapi BM25) with a daemon-owned **`shadow.sqlite`** for sub-50 ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices.

The implementation decision is recorded in
[`v2-external-shadow-cache-read-only.md`](../quality/issue-bodies/v2-external-shadow-cache-read-only.md).
Current authority, cache location, and Read Only behavior are maintained in the
[v2 operator contract](../knowledge/architecture/shadow-db.md).

---

## Legacy fallback baseline (retained through and after v2.0.0)

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
| **Memory graph** | `memory_nodes`, `memory_edges`, `memory_pending_edges`, `memory_episodes`, `memory_episode_entities`, `memory_procedures`, `memory_snapshots` | Schema only — planned Phase 4; no memory read/write path is shipped. See [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md) |

Historical published beta path: `<LOGSEQ_GRAPH_PATH>/.matryca_semantic_cache/shadow.sqlite`
(`shadow_db_path` / `open_shadow_db`). Current RC storage, invalidation, health, and
recovery behavior are maintained in the
[v2 operator contract](../knowledge/architecture/shadow-db.md); implementation issue
[#386](https://github.com/MarcoPorcellato/matryca-plumber/issues/386) records the generic
sync-failure invalidation slice.

---

## Tasks

### Shadow read path (#24)

- [x] Scaffold `shadow.sqlite` DDL (`pages`, `blocks`, `block_refs`, FTS5) — `src/shadow/schema.py`
- [x] Connection helper — `open_shadow_db` / `shadow_db_path` ([#181](https://github.com/MarcoPorcellato/matryca-plumber/issues/181))
- [x] Incremental post-write upsert — `sync_page_to_shadow` ([#182](https://github.com/MarcoPorcellato/matryca-plumber/issues/182))
- [x] FTS5 query helper — `search_blocks_fts` ([#183](https://github.com/MarcoPorcellato/matryca-plumber/issues/183); dispatch wiring [#250](https://github.com/MarcoPorcellato/matryca-plumber/issues/250))
- [x] Full bootstrap / reconciliation / freshness contract ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248))
- [x] Fail-closed generic sync invalidation and deterministic full-rebuild recovery ([#386](https://github.com/MarcoPorcellato/matryca-plumber/issues/386))
- [x] `GraphRepository` read routing — `ShadowGraphRepository` + `get_graph_read_port` ([#255](https://github.com/MarcoPorcellato/matryca-plumber/issues/255))
- [x] Recursive CTEs (`query_subtree_by_block_uuid`) ([#253](https://github.com/MarcoPorcellato/matryca-plumber/issues/253))
- [x] Opt-in env flag `MATRYCA_SHADOW_DB_ENABLED` ([#184](https://github.com/MarcoPorcellato/matryca-plumber/issues/184))
- [x] Sovereign UI shadow health (`/api/state.shadow_db`) ([#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185))

- [x] Duplicate block UUID pre-insert diagnostics ([#251](https://github.com/MarcoPorcellato/matryca-plumber/issues/251))

### RC external-cache prerequisite

- [x] Typed platform cache-root and versioned graph-identity resolver
- [x] Shadow connection, WAL/SHM, and writer lock routed through one external location
- [x] Read-only bootstrap split: no graph writes, external Shadow maintenance allowed
- [x] Beta graph-local cache ignored and rebuilt externally without automatic deletion
- [x] Independent Sovereign UI Read Only and Shadow controls
- [x] Deterministic source-tree E2E graph immutability qualification across CLI, MCP, UI,
  daemon, Shadow, hidden files, Git metadata, and symlink cases
- Current exact-wheel qualification status:
  [v2.0.0 RC and stable readiness](../quality/issue-bodies/v2-rc-stable-readiness.md)

The checked source-tree gate is recorded in
[`READ_ONLY_IMMUTABILITY_E2E.md`](../quality/READ_ONLY_IMMUTABILITY_E2E.md). It does
not replace the unchecked installed-wheel qualification row.

### Rollout (Epic #20)

| Track | Target | Status |
|-------|--------|--------|
| v2.0.0-alpha.1 | Axis 1 hardening (#262, #264) | **superseded** |
| v2.0.0-alpha.5 | Seven-axis hardening campaign close | **published** |
| v2.0.0-beta.1 | First public Shadow read-path beta; opt-in flag remains default-off | **published** |
| v2.0.0-rc.1 | See the [current runtime and operator contract](../knowledge/architecture/shadow-db.md) | See [current RC and stable qualification status](../quality/issue-bodies/v2-rc-stable-readiness.md) |
| v2.0.0-stable | Deprecate pure in-memory BM25 as default discovery path after RC observation | planned |

### Explicit read freshness after the RC

Issue [#389](https://github.com/MarcoPorcellato/matryca-plumber/issues/389)
separates aggregate Shadow health from row-level read eligibility. Before a cached
subtree or FTS row is returned, Matryca validates its sandboxed source path,
nanosecond mtime, and size against current Markdown. Untracked, missing, changed, and
unproven-empty reads fail over with a closed content-free reason; the check is bounded
to the requested page or returned result rows and never scans the full graph.

This is a post-`2.0.0rc1` read-path correction. The public-RC soak remains valid only
as evidence for those exact published bytes. Because both Gate B profiles exercise
FTS and subtree routing, an exact stable candidate containing #389 must repeat the
focused watcher-disabled edit/delete/rename matrix and both candidate-bound Gate B
profiles before `v2.0.0` promotion.

The beta excludes Phase 4 biological memory and Logseq DB Safe-Sync. Its completed gates and accepted evidence boundary are recorded in [`docs/quality/issue-bodies/v2-beta-readiness.md`](../quality/issue-bodies/v2-beta-readiness.md).
The RC and stable exit criteria are fail-closed in [`docs/quality/issue-bodies/v2-rc-stable-readiness.md`](../quality/issue-bodies/v2-rc-stable-readiness.md) and tracked by [#343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343). Biological memory, Logseq DB Safe-Sync, Tana merge, and independent DX tracks are deferred to `v2.1.0` or later.
The exact public-beta wheel passed its fresh installed-wheel gate on 2026-07-30
and completed the required 72-hour real-vault qualification with a terminal
`PASS` on 2026-08-03. See the sanitized
[`terminal evidence record`](../quality/SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md);
it closes only the exact-beta real-vault readiness row and does not qualify the RC.
Current RC status is maintained in the
[readiness record](../quality/issue-bodies/v2-rc-stable-readiness.md).

---

## Safe-Sync reminder

| Path | Rule |
|------|------|
| **READ** | Shadow DB syncs read-only from Markdown (Classic) or Markdown Mirror (Logseq DB) |
| **CACHE** | Current derived-cache and Read Only behavior: [v2 operator contract](../knowledge/architecture/shadow-db.md) |
| **WRITE (Logseq OG)** | Append to `.md` + OCC — shipped v1.9.5 ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) partial) |
| **WRITE (Logseq DB)** | Official CLI/API only — never native DB mutation |

Full contract: [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) · [`docs/openspec/llm-os-instructions.md`](../openspec/llm-os-instructions.md)

---

## Related roadmaps

- [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md) — memory graph layer (depends on this schema)
- [`ROADMAP.md`](../../ROADMAP.md) — north-star timeline
