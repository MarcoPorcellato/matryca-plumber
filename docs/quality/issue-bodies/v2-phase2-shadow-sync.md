---
type: Document
---
## Problem Description

Shadow DB DDL exists ([`src/shadow/schema.py`](../../../src/shadow/schema.py)) but no runtime sync populates `pages`/`blocks` from Markdown edits.

## Proposed Architectural Solution

Implement **Phase 2** per [`ROADMAP_V2_PREPARATION.md`](../../roadmaps/ROADMAP_V2_PREPARATION.md):

- `open_shadow_db(graph_root)` with WAL pragmas from schema
- Incremental upsert on `post_write` / file watcher events
- **Read-only** on source `pages/*.md` — never write vault from shadow
- Integration tests: edit page → shadow row updated

Child slices: `v2-phase2-shadow-open-connection.md`, `v2-phase2-post-write-sync.md`, `v2-phase2-fts5-search.md`.

**Depends on:** Phase 1 [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) (routing slot).

## Estimated Impact

**Alto** — enables alpha read path; ships with sync disabled by default until Phase 3 flag.

## Files Involved

- `src/shadow/` (new sync + connection modules)
- `src/graph/post_write.py`
- `tests/test_shadow_sync.py` (new)

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Label:** `v2-alpha`
