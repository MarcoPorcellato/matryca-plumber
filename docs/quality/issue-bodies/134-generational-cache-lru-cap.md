---
type: Document
---
## Problem Description

`src/graph/generational_cache.py` keeps module-level `_alias_cache` and `_bm25_cache` dicts keyed by resolved graph root string. Per-graph mtime invalidation works, but there is **no cap** on the number of concurrent vault caches.

When MCP requests switch `LOGSEQ_GRAPH_PATH` across vaults (or the daemon restarts on a different graph without `release_phase1_memory`), old graph caches remain in RSS. For 10k-page vaults, alias + BM25 caches can reach hundreds of MB each.

Mitigations today: `gc_generational_alias_cache`, `release_bm25_corpus`, `clear_generational_caches` — all require explicit calls; no LRU eviction.

## Proposed Architectural Solution

Add LRU cap (mirror `page_write_lock.py` pattern):

- `OrderedDict` + `_CACHE_MAX_ENTRIES` (e.g. 4 concurrent graphs).
- `_store_cached` / `_get_cached` move-to-end on access; evict oldest on overflow.
- Thread-safe under existing `_lock`.

Document env knob if operators need to tune cap.

## Estimated Impact

**Medio** — prevents unbounded RSS growth across vault switches on shared operator machines.

## Files Involved

- `src/graph/generational_cache.py`
- `tests/test_ironclad_phase8.py` or `tests/test_memory_budget.py` (LRU eviction test)
- `docs/ARCHITECTURE.md`

---
**Expert Audit 2026-06** · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
