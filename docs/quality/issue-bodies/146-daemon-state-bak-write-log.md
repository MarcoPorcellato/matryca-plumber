---
type: Document
---
## Problem Description

`save_daemon_state` in `src/agent/maintenance_daemon.py` (~L830–832) atomically writes the primary daemon state, then copies it to `.matryca_daemon_state.json.bak` inside `contextlib.suppress(OSError)`.

When the `.bak` sidecar write fails, the primary commit still succeeds but operators have **no warning** that corruption recovery will be unavailable on the next read failure.

## Proposed Architectural Solution

Log `logger.exception` (or `warning`) on `shutil.copy2` `OSError`. Do not roll back the successful primary write.

Add a regression test mocking `shutil.copy2` to raise.

## Estimated Impact

Basso — backup sidecar observability.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
