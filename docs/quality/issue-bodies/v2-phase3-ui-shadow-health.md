---
type: Document
---
## Problem Description

Operators need visibility into shadow sync health without a `matryca doctor` command (`llms.txt` §2.3).

## Proposed Architectural Solution

1. Expose `shadow_meta` fields: last sync timestamp, lag pages count (or equivalent).
2. Extend Sovereign UI state API (`/api/state` or graph analytics payload) with `shadow_db: { enabled, last_sync, lag }`.
3. Frontend: single row in telemetry or Settings — no heavy dashboard.
4. Tests: `tests/test_ui_server.py` asserts JSON shape when shadow disabled (defaults safe).

**Depends on:** sync producing meta keys; may ship with stub meta when sync not merged.

## Estimated Impact

**Basso** — DX / operator trust for alpha.

## Files Involved

- `src/shadow/meta.py` or sync module
- `src/cli/ui_server.py`, `frontend/src/`

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 3 · **Label:** `v2-alpha`, `dx`
