---
type: Document
---
## Problem Description

In `run_cycle`, fast-track skippable files call `register_page_links_from_path` when link verification is enabled (`src/agent/maintenance_daemon.py`, ~L2962–2964). The call is wrapped in `contextlib.suppress(OSError)`.

Fast-track is the high-volume path for unchanged pages — silent registry failures accumulate without ops-log signal.

## Proposed Architectural Solution

Replace `suppress(OSError)` with explicit `try/except OSError` + `logger.exception(...)`. Preserve fast-track throughput — logging only.

Add a regression test mocking registry registration failure during fast-track.

## Estimated Impact

Basso — link registry observability on hot path.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
