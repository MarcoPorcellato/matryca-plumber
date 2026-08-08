# v2.1+ — Biological Memory Layer (Nacre-inspired)

**Historical architecture context:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

**Active delivery tracker:** [#178 — Biological memory + Logseq DB Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/178)

**Status:** planned for v2.1+ — schema-only tables exist in [`src/shadow/schema.py`](../../src/shadow/schema.py); decay algorithms are scaffolded in [`src/memory/decay.py`](../../src/memory/decay.py), but no memory read/write path is shipped

**Preparation index:** [`ROADMAP_V2_PREPARATION.md`](ROADMAP_V2_PREPARATION.md) · OpenSpec: [`biological-memory.md`](../openspec/biological-memory.md)  
**Prerequisite:** [`ROADMAP_V2_SHADOW_DB.md`](ROADMAP_V2_SHADOW_DB.md) ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24), [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17))  
**Inspiration:** [Nacre](https://github.com/marcusschimizzi/nacre) by Marcus Sullivan (Apache-2.0) — native Python port, not a Node sidecar  
**RFC:** [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

---

## What the two projects are

| | **Nacre** | **Matryca Plumber** |
|---|---|---|
| **Purpose** | Memory layer for long-lived agents (months) | Local-first daemon for Logseq OG vaults and MCP/CLI agents |
| **Stack** | TypeScript monorepo (`@nacre/core`, parser, visualization, CLI) | Python 3.12 + React Sovereign UI |
| **Storage** | `SqliteStore` (WAL, schema v5, embeddings) | JSON sidecars → **Shadow DB** `shadow.sqlite` |
| **Memory unit** | Typed nodes + typed edges | Logseq blocks/pages + wikilinks + block-level semantic index |
| **License** | Apache-2.0 — Copyright 2026 Marcus Sullivan | Apache-2.0 — Copyright 2026 Marco Porcellato & Matryca.ai |

**Principle:** bring Nacre's biological memory engine *into* the existing Logseq infrastructure without replacing the parser or block model.

---

## Gap analysis: what Nacre provides that Matryca Plumber does not yet have

### 1. Decay and reinforcement (P0)

```
weight(t) = baseWeight × e^(-λt / stability)
stability = 1 + β × ln(reinforcementCount + 1)
```

Nacre source: [`packages/core/src/decay.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/decay.ts)  
Matryca Plumber today: no decay on connections.

### 2. Four-signal hybrid recall (P0)

Semantic + graph walk + recency + importance — [`recall.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/recall.ts).  
Matryca Plumber: BM25 + dual embeddings + link hops, without unified fusion.

### 3. Episodic and procedural memory (P1–P2)

Session episodes + procedures (lesson/preference/skill/…).  
Matryca Plumber: only `store_fact` → `matryca-config.md` and the operational Journey Log.

### 4. Zero-LLM intelligence layer (P1)

Connection suggestions and emerging/fading topics — [`intelligence.ts`](https://github.com/marcusschimizzi/nacre/blob/main/packages/core/src/intelligence.ts).  
Matryca Plumber: partial overlap (`unlinked_mentions`, `entity_consolidation`, `insights_engine`, `semantic_clustering`).

### 5. Sleep/wake consolidation (P0)

Idle post-sync Shadow DB batch → Phase 3 daemon.

### 6. Memory-native MCP

| Nacre | Matryca Plumber today |
|---|---|
| `nacre_recall` | `search_graph` — partial |
| `nacre_brief` | dashboard + Graph Insights — partial |
| `nacre_remember` | `store_fact` — limited |
| `nacre_forget` / `nacre_feedback` / `nacre_lesson` | absent |

---

## What Matryca Plumber already has and must not duplicate

- Logseq outliner paradigm, OCC, and Safe-Sync ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25))
- LLM cognitive lint (MARPA, healer, property hygiene, auto-split, backlink backpropagation)
- L1/L2 Karpathy model ([`l1_memory.py`](../../src/agent/l1_memory.py))
- Atomic ingest + Trust & Safety tiers + dual-embedding applicability

---

## Implementation roadmap

### Phase A — Shadow DB foundations

DDL in [`src/shadow/schema.py`](../../src/shadow/schema.py). Package [`src/memory/`](../../src/memory/):

| Module | Nacre source |
|--------|--------------|
| `decay.py` | `decay.ts` |
| `recall.py` | `recall.ts` |
| `intelligence.py` | `intelligence.ts` |
| `resolve.py` | `resolve.ts` (+ `alias_index.py`) |
| `consolidate.py` | sleep/wake pipeline |

**Logseq-native** entity extraction (not `@nacre/parser`):

- **Structural:** wikilinks, block references, tags, and page properties via `logseq-matryca-parser`
- **Co-occurrence:** within the same block subtree (outliner-aware)
- **Custom:** entity-map YAML in `.matryca/`

Future feature gate: `MATRYCA_MEMORY_GRAPH_ENABLED`. Its public default and
rollout policy remain design decisions for a separately qualified v2.1+ slice.

### Phase B — Hybrid recall

`search_graph(method="recall")` in [`graph_dispatch.py`](../../src/agent/graph_dispatch.py):

```
final = w_sem×semantic + w_graph×graphWalk + w_recency×recency + w_importance×importance
```

### Phase C — Episodes and procedures

SQLite + human-readable mirror in `pages/Matryca Procedures.md`. Extend `store_fact` with `kind=lesson|preference|…`.

### Phase D — Intelligence and alerts

`memory_intelligence.py` → `Matryca Memory Alerts` page + Sovereign UI panel.

### Phase E — Temporal features and visualization (post-MVP)

`memory_snapshots`, `as_of` recall, and a 2D graph in the UI.

### Phase F — Multi-vault hive (optional)

Only if real demand emerges.

---

## Priorities

| Priority | Feature |
|---|---|
| P0 | Decay + sleep consolidation |
| P0 | Unified hybrid recall |
| P1 | Intelligence alerts |
| P1 | Procedural memory |
| P2 | Episodic memory |
| P2 | Temporal snapshots |
| P3 | 2D graph visualization |
| P3 | Hive federation |

---

## Apache-2.0 compliance

Both projects use Apache-2.0. For every merge that ports code from Nacre:

1. Keep [`LICENSE`](../../LICENSE) unchanged.
2. Update [`NOTICE`](../../NOTICE) with attribution to Marcus Sullivan and Nacre.
3. Add SPDX headers to ported `src/memory/*.py` files.
4. Add [`docs/THIRD_PARTY.md`](../THIRD_PARTY.md) with a file-by-file map at the first merge.
5. Add pytest tests proving numerical decay parity against Nacre's half-life table.
6. Do not use “Nacre” as a Matryca Plumber brand; use the name only for attribution in NOTICE/README.

Detailed checklist: “Apache-2.0 compliance” section in the original plan (maintainer reference).

---

## Risks

| Risk | Mitigation |
|---|---|
| Duplicate semantic JSON | Shadow DB becomes the v2 source of truth; deprecate JSON gradually |
| `maintenance_daemon.py` ~3,200 lines | Move Phase 3 into a dedicated module ([#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)) |
| Nacre parser ≠ Logseq | Use only `logseq-matryca-parser` |
| Embedding dimension mismatch | Store metadata in `shadow_meta`; apply the same fix documented in the Nacre roadmap |
| Scope creep | Keep the feature gated pending v2.1+ design and qualification; ship decay + recall before visualization/hive |

---

## Next steps

1. ~~Save the roadmap in the repository~~ (this file)
2. Keep delivery issue #178 linked to historical context #20 and Shadow DB prerequisite #24.
3. Use RFC Discussion #19 to map block UUIDs to memory nodes.
4. Implement `src/memory/decay.py` + Nacre parity tests.
5. Prototype consolidation on 100 pages with `MATRYCA_MEMORY_GRAPH_ENABLED=true`.
6. Add `NOTICE` + `docs/THIRD_PARTY.md` at the first merge of Nacre-derived code.
