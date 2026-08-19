---
type: Document
---
## Problem Description

`_finalize_link_and_journey_pass` in `src/agent/maintenance_daemon.py` (~L2884–2891) wraps `upsert_journey_log(...)` in `contextlib.suppress(OSError)` when journey logging is enabled and the cycle has journal activity.

Journey Log writes to today's journal page can fail (OCC abort, sandbox, disk) with **no ops-log line**, while in-memory `journey_day` state still updates and persists.

## Proposed Architectural Solution

Replace `suppress(OSError)` with explicit `try/except OSError` + `logger.exception(...)`. Keep the journey pass non-blocking — do not re-raise.

Add a regression test in `tests/test_maintenance_daemon.py` (or nearest journey-log test module).

## Estimated Impact

Basso — operator-visible Journey Log path.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
