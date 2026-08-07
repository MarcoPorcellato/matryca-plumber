## Problem Description

Biological memory (Nacre-inspired) and Logseq DB Safe-Sync writes are the long-tail v2 deliverables after shadow read path stabilizes.

## Proposed Architectural Solution

Implement **Phase 4** per [`ROADMAP_V2_PREPARATION.md`](../../roadmaps/ROADMAP_V2_PREPARATION.md) and [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md):

| Track | Deliverable |
|-------|-------------|
| Memory | `MATRYCA_MEMORY_GRAPH_ENABLED`; `search_graph(method=recall)`; consolidation idle batch |
| Safe-Sync DB | Logseq DB writes via official CLI/API only — [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) |
| Import | Content-hash Tana merge — [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) |

OpenSpec: [`docs/openspec/biological-memory.md`](../../openspec/biological-memory.md).

Child slice: `v2-phase4-recall-search-method.md`.

**Depends on:** a stabilized and qualified v2.0 Shadow DB read-path baseline.

## Estimated Impact

**High** — planned v2.1+ deliverables; explicitly excluded from v2.0 stable.

## Files Involved

- `src/memory/`, `src/shadow/`
- `src/agent/graph_dispatch.py`
- Future `DatabaseRepository` ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17))

---
**Parent:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Labels:** `v2-memory`, `v2-safesync`
