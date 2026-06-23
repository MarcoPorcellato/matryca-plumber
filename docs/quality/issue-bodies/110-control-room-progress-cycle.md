## Problem Description

`control_room_progress.refresh_phase2_cognitive_totals` lazy-imports `compute_phase2_progress_metrics` from `maintenance_daemon.py`. GitNexus reports a structural cycle (mitigated by `TYPE_CHECKING` + lazy import).

## Proposed Architectural Solution

Introduce a `Protocol` (`Phase2MetricsProvider`) or callback registered at daemon startup. `MaintenanceDaemon` implements metrics; `control_room_progress` depends on the protocol only — no runtime import of `maintenance_daemon`.

## Estimated Impact

Basso — maintainability; enables safer splits of `maintenance_daemon.py` (#58).

## Files Involved

- `src/agent/control_room_progress.py`
- `src/agent/maintenance_daemon.py`
- `tests/test_bootstrap_status.py`

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23
- Related: #58 (split maintenance_daemon)
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
