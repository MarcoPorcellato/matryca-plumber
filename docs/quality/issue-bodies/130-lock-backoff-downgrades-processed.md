---
type: Document
---
## Problem Description

In `src/agent/maintenance_daemon.py`, `_process_llm_cycle_file` sets `status="processed"` after a successful cognitive lint write (L2715–2718), then calls `run_dual_embedding_after_semantic_write`. If that post-write step raises `PageLockUnavailableError`, the handler calls `_record_page_lock_backoff`, which **always** assigns `status="lock_backoff"` — ignoring the prior `processed` record.

This downgrades a page that completed Phase 2 semantic indexing back to a backoff state, delaying re-indexing and misrepresenting vault progress until the backoff timer expires.

Regression path: semantic write succeeds → dual embedding lock fails → ledger shows `lock_backoff` instead of `processed`.

## Proposed Architectural Solution

In `_record_page_lock_backoff`, preserve `prior.status` when the prior record was `processed` and the semantic work already completed (or split post-write embedding into a non-downgrading retry path). At minimum:

- Do not overwrite `processed` with `lock_backoff` when `prior.status == "processed"`.
- Record embedding lock failure as a warning / secondary retry without downgrading the primary cognitive status.

Add regression tests in `tests/test_maintenance_daemon.py` covering: processed → embedding lock failure → status remains `processed`.

## Estimated Impact

**Alto** — incorrect daemon ledger state on concurrent vault edits; progress bar and pending-file scans can misclassify successfully indexed pages.

## Files Involved

- `src/agent/maintenance_daemon.py` (`_record_page_lock_backoff`, `_process_llm_cycle_file`)
- `tests/test_maintenance_daemon.py`

---
**Expert Audit 2026-06** · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
