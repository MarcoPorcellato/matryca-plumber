## Problem Description

Biological memory requires a unified recall entry point for agents — beyond separate bm25/semantic/hops calls.

## Proposed Architectural Solution

1. Extend `SearchGraphMethod` Literal with `"recall"` in `graph_tool_helpers.py`.
2. Stub handler in `graph_dispatch`: when `MATRYCA_MEMORY_GRAPH_ENABLED` false → clear error or degrade to semantic search (document choice).
3. When enabled (future): delegate to `src/memory/recall.py` + shadow memory tables.
4. OpenSpec update: [`docs/openspec/biological-memory.md`](../../openspec/biological-memory.md).

**This slice may be stub-only** — wire algorithms in follow-up PRs.

## Estimated Impact

**Medio** — MCP contract extension; ship behind env flag only.

## Files Involved

- `src/agent/graph_tool_helpers.py`
- `src/agent/graph_dispatch.py`
- `docs/openspec/biological-memory.md`

---
**Parent:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · Phase 4 · **Label:** `v2-memory`
