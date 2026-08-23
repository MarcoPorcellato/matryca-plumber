---
type: Document
---
## Problem Description

`read_daemon_checkpoint` in `src/daemon/checkpoint.py` (~L64–66) recovers from a corrupt primary checkpoint by reading `.matryca_daemon_state.json.bak`, then restores the primary file via `shutil.copy2(bak_path, path)` inside `contextlib.suppress(OSError)`.

When the copy fails (permissions, disk full), recovery succeeds in-memory but the operator gets **no ops-log breadcrumb** and the primary file stays corrupt.

## Proposed Architectural Solution

Replace `suppress(OSError)` with explicit `try/except OSError` and `logger.exception(...)`. Do not change recovery ordering or return values.

Add a regression test in `tests/test_daemon_checkpoint.py`.

## Estimated Impact

Basso — metadata corruption recovery observability.

## Files Involved

- `src/daemon/checkpoint.py`
- `tests/test_daemon_checkpoint.py`

---

**Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
