## Problem Description

Phase 1 requires a stable read contract before shadow adapters plug in. No `GraphReadPort` exists today.

## Proposed Architectural Solution

1. Add `typing.Protocol` `GraphReadPort` with 2–3 read methods (e.g. `search_bm25`, `read_subtree_markdown`).
2. Implement `MarkdownGraphRepository` delegating to existing `src/graph/*` + parser helpers.
3. Factory: `get_graph_read_port(graph_root) -> GraphReadPort` returning Markdown adapter only.
4. Parity tests on `tmp_path` graph — compare port output to current direct calls.

**No** `graph_dispatch` changes in this slice — port + tests only.

## Estimated Impact

**Medio** — structural; zero runtime change until dispatch delegate slice lands.

## Files Involved

- New: `src/graph/repository.py` (or `src/graph/ports/read.py`)
- `tests/test_graph_repository.py`

---
**Parent:** [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Phase 1 tracking issue · **Label:** `v2-prep`
