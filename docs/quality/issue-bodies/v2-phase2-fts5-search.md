---
type: Document
---
## Problem Description

Shadow FTS5 table `blocks_fts` is created by schema but no query API exists for agent search paths.

## Proposed Architectural Solution

1. `search_blocks_fts(conn, query: str, limit: int) -> list[BlockHit]` — parameterized FTS5 MATCH.
2. Optional: BM25 rank helper for stable ordering.
3. Tests: seed blocks via sync or fixtures; assert MATCH returns expected UUIDs.
4. **Do not** wire to `graph_dispatch` yet — query module only (Phase 3 routing slice).

**Depends on:** post-write-sync slice or test fixtures that insert rows directly.

## Estimated Impact

**Medio** — enables Phase 3 read routing.

## Files Involved

- `src/shadow/query.py` (new)
- `tests/test_shadow_fts.py` (new)

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 2 · **Label:** `v2-alpha`
