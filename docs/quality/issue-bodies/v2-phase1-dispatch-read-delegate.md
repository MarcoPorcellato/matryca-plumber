## Problem Description

`graph_dispatch` imports graph helpers directly — bypassing any repository port introduced in the graph-read-port slice.

## Proposed Architectural Solution

1. Inject or resolve `GraphReadPort` at dispatch boundary (constructor or module-level factory with graph_root).
2. Migrate **one** read method first (recommend `read_subtree` or `search_graph` bm25 path).
3. Keep MCP/CLI response shapes **byte-identical** for the migrated method.
4. Extend tests in `tests/test_graph_dispatch.py` or `tests/test_graph_repository.py`.

**Depends on:** graph-read-port slice merged.

## Estimated Impact

**Medio** — first end-to-end port usage; still default Markdown backend only.

## Files Involved

- `src/agent/graph_dispatch.py`
- `tests/test_graph_dispatch.py`

---
**Parent:** [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Phase 1 · **Label:** `v2-prep`
