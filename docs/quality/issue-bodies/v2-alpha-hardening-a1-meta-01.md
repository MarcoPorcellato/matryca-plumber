## Problem Description

`resolve_shadow_health` returns **`ready`** when `last_full_sync_completed=true` and `last_sync_error` is empty, **without validating** that `shadow_meta` row counts match the actual `pages` table.

Reproducer (Axis 1 audit, tracking [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261)):

| Signal | Value |
|--------|-------|
| `last_full_sync_completed` | `true` |
| `source_page_count` | `> 0` |
| `indexed_page_count` | `> 0` |
| `pages` row count | **0** (or diverges from meta) |
| **Current health** | **`ready`** (incorrect) |
| **Expected health** | **`stale`** or **`error`** — never `ready` |

FTS/CTE routing then serves empty or partial results instead of falling back to `MarkdownGraphRepository` / generational BM25.

**Minimal test (already in tree):** `tests/test_shadow_hardening_axis1_concurrency.py::test_a1_health_not_ready_when_meta_completed_but_pages_empty` (`pytest.mark.xfail(strict=True)` until fixed).

## Proposed Architectural Solution

Add a **lightweight consistency check** in `resolve_shadow_health` / `resolve_shadow_db_state_for_api` before reporting `ready` — e.g. compare `indexed_page_count` (and optionally `source_page_count`) to `SELECT COUNT(*) FROM pages`. On mismatch, return `stale` or `error` and route reads through Markdown fallback.

**Scope:** health validation only — **no automatic rebuild** in this fix.

## Estimated Impact

**P2** — unlikely without manual DB corruption or partial crash, but breaks the operator contract that `ready` implies a usable shadow index.

## Files Involved

- `src/shadow/health.py`
- `src/shadow/state_api.py`
- `tests/test_shadow_hardening_axis1_concurrency.py` (remove `xfail` when fixed)
- `tests/test_shadow_state_api.py` (regression)

---
**Parent tracker:** [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) · **Epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

_Closes when merged with tests green (`make ci`) and CHANGELOG updated._
