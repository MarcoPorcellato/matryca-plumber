---
type: Document
---
## Problem Description

[`src/shadow/schema.py`](../../../src/shadow/schema.py) defines DDL and `apply_shadow_schema()` but no production helper opens `shadow.sqlite` under the graph root with correct pragmas and path sandboxing.

## Proposed Architectural Solution

1. `shadow_db_path(graph_root: Path) -> Path` — under `.matryca_semantic_cache/shadow.sqlite`.
2. `open_shadow_db(graph_root: Path) -> sqlite3.Connection` — apply `SHADOW_PRAGMAS`, `apply_shadow_schema`.
3. Assert path within graph via `path_sandbox` patterns.
4. Unit tests: in-memory + `tmp_path` file DB; schema version row present.

No sync logic in this PR.

## Estimated Impact

**Basso** — infrastructure only; no daemon wiring.

## Files Involved

- `src/shadow/connection.py` (new)
- `tests/test_shadow_connection.py` (new)

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 2 · **Label:** `v2-alpha`
