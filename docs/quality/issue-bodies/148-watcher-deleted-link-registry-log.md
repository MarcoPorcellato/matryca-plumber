---
type: Document
---
## Problem Description

`_on_watchdog_change` in `src/agent/maintenance_daemon.py` (~L2117–2119) calls `register_page_links_from_path` when the file watcher reports a **deleted** `.md` page and link verification is enabled. Failures are swallowed via `contextlib.suppress(OSError)`.

Stale or broken link-registry entries after deletes are hard to diagnose without an ops-log breadcrumb.

## Proposed Architectural Solution

Replace `suppress(OSError)` with `try/except OSError` + `logger.exception(...)`. Preserve wake-the-cycle behavior on success and failure.

Add a test in `tests/test_file_watcher.py` or `tests/test_maintenance_daemon.py`.

## Estimated Impact

Basso — link hygiene observability.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_file_watcher.py` or `tests/test_maintenance_daemon.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
