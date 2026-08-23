---
type: Document
---
## Problem Description

Shadow sync (Phase 2) must be opt-in before v2.0.0-rc. Operators and agents need predictable fallback when shadow is disabled or stale.

## Proposed Architectural Solution

Implement **Phase 3** per [`ROADMAP_V2_PREPARATION.md`](../../roadmaps/ROADMAP_V2_PREPARATION.md):

| Surface | Flag off (default) | Flag on |
|---------|-------------------|---------|
| `search_graph(bm25)` | generational BM25 | FTS5 shadow + fallback |
| `read_graph_data(subtree)` | parser + AST | recursive CTE |
| `read_graph_data(page)` | file read | unchanged |

- `MATRYCA_SHADOW_DB_ENABLED=false` in code + [`.env.example`](../../../.env.example)
- Sovereign UI: sync lag / last full sync row

Child slices: `v2-phase3-shadow-env-flag.md`, `v2-phase3-ui-shadow-health.md`.

## Estimated Impact

**Alto** — first operator-visible v2 alpha feature; must not break `uvx` agents when flag unset.

## Files Involved

- `src/agent/graph_dispatch.py`, `src/shadow/`
- `src/cli/ui_server.py`, `frontend/`
- `llms.txt` — document flag at alpha release only

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Label:** `v2-alpha`
