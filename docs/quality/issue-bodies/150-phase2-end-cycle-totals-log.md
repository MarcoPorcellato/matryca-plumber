---
type: Document
---
## Problem Description

At **cycle start**, `run_cycle` already logs `refresh_phase2_cognitive_totals` failures (`logger.warning`, ~L2919–2922). At **cycle end** (~L3043–3045), the same refresh runs inside `contextlib.suppress(OSError)` every 10 vault refresh ticks.

TUI Phase-2 progress can drift without a matching end-of-cycle log line — related to [#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137).

## Proposed Architectural Solution

Mirror the cycle-start pattern: `try/except OSError` + `logger.warning`. No change to refresh cadence or state fields.

Add a regression test if not already covered.

## Estimated Impact

Basso — TUI/daemon progress observability.

## Files Involved

- `src/agent/maintenance_daemon.py`
- `tests/test_maintenance_daemon.py` or `tests/test_tui_dashboard.py`

---

**Parent:** #137 · **Milestone:** v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
