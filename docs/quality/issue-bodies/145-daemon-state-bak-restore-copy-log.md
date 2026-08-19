---
type: Document
---
## Problem Description

`load_daemon_state` in `src/agent/maintenance_daemon.py` (~L793–795) mirrors checkpoint recovery: when the primary `.matryca_daemon_state.json` is unreadable, it loads from `.bak` and attempts `shutil.copy2(bak_path, path)` inside `contextlib.suppress(OSError)`.

Copy failures are invisible in `matryca_plumber_ops.log` even though the daemon continues with recovered state.

## Proposed Architectural Solution

Replace `suppress(OSError)` with `try/except OSError` + `logger.exception(...)`. Preserve existing recovery semantics.

Add or extend a test in `tests/test_maintenance_daemon.py`.

## Estimated Impact

Basso — same class as [#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100) shutdown logging.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
