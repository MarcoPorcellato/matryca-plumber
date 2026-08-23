---
type: Document
---
## Problem Description

`page_write_lock._lock_for_key` evicts LRU registry entries when `not old_lock.locked()` before allocating a new `RLock` for a path (`_MAX_PAGE_LOCK_REGISTRY = 4096`).

The Claude 2026-06-24 audit flags a narrow TOCTOU: between `locked()` returning false and `del _page_locks[old_key]`, another thread could acquire the evicted lock, leaving an orphaned holder while a new `RLock` is registered for the same normalized path — theoretical dual in-process exclusivity (cross-process flock remains the backstop).

Current code already rejects blind eviction (Repomix/Clean Arch triage); this slice hardens the guard.

## Proposed Architectural Solution

Replace `locked()` probe with `acquire(blocking=False)` / `release()` on eviction candidate (audit-recommended pattern). If every entry is held, allow registry to exceed cap briefly rather than evict a live lock.

Add concurrency regression test in `tests/test_hardening_final.py`.

## Estimated Impact

Basso — edge-case hardening on 4096+ distinct hot paths; good-first friendly.

## Files Involved

- `src/graph/page_write_lock.py`
- `tests/test_hardening_final.py`
- `docs/ARCHITECTURE.md` (page-lock registry section)

Also consider: reset `@lru_cache` on `_resolved_graph_root_from_env` in `src/daemon/config_layer.py` via existing `clear_identity_env_cache()` — test flake slice bundled or separate PR.

---

**Claude Audit 2026-06-24** · **GitHub:** [#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) · **Milestone:** v1.9.12 — Code Perfection & Tech Debt · **Labels:** good first issue

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
