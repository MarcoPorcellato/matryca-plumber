---
type: Document
---
## Problem Description

During Phase-2 cognitive lint in `run_cycle` (`src/agent/maintenance_daemon.py`, ~L2636–2638), `merge_page_links_into_registry` runs inside `contextlib.suppress(OSError)` before `run_cognitive_lint_pipeline`.

This is the same silent-failure pattern as journal structural settle ([#128](https://github.com/MarcoPorcellato/matryca-plumber/issues/128)) but on the **Phase-2 LLM path**.

## Proposed Architectural Solution

Replace `suppress(OSError)` with explicit logging. Do not abort the cognitive lint turn on registry failure.

Add a focused regression test mocking `merge_page_links_into_registry` to raise `OSError`.

## Estimated Impact

Basso — extends #128 observability to Phase-2.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py`

---

**Parent:** #128 · **Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
