---
type: Document
---
## Problem Description

Shadow tables stay empty until Markdown edits flow into `pages`/`blocks` rows. Phase 2 requires incremental sync, not full-vault rescans on every bullet edit.

## Proposed Architectural Solution

1. Register handler on [`post_write`](../../../src/graph/post_write.py) `PageWrittenEvent`.
2. Parse changed page via `logseq-matryca-parser` (or bounded graph helper); upsert shadow rows transactionally.
3. On page delete/move: invalidate shadow rows (coordinate with file watcher if needed).
4. Integration test: write page via `atomic_write_bytes` → query shadow `blocks` count.

**Read-only** on source markdown files.

**Depends on:** shadow-open-connection slice.

## Estimated Impact

**Alto** — core sync path; must be efficient enough for duty-cycle scale.

## Files Involved

- `src/shadow/sync.py` (new)
- `src/graph/post_write.py` (register handler)
- `tests/test_shadow_sync.py` (new)

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 2 · **Label:** `v2-alpha`
