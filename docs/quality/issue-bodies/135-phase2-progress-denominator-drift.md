---
type: Document
---
## Problem Description

[#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) fixed Phase 2 progress **denominator including journals**. A separate UX gap remains:

`compute_phase2_progress_metrics` scans the live vault; `refresh_phase2_cognitive_totals` updates `state.phase2_cognitive_total` every 10 daemon cycles (and at bootstrap). When the operator **adds pages during Phase 2**, `total` increases while `done` may not — the progress **percent regresses** (e.g. 70% → 65%) until those pages are indexed.

`resolve_control_room_progress` reads persisted `phase2_cognitive_total` / `phase2_cognitive_done` — operators see confusing backward motion in TUI and Sovereign UI.

## Proposed Architectural Solution

Pick one stable semantics (document in ARCHITECTURE):

**Option A — frozen denominator:** set `phase2_vault_total_at_start` when `bootstrap_complete` transitions; progress = `done / frozen_total` until Phase 2 complete.

**Option B — monotonic percent:** never decrease displayed percent; bump denominator only when done catches up.

Prefer Option A for honest "work remaining" with footnote that new pages extend tail work.

## Estimated Impact

**Medio** — operator UX / trust in progress telemetry; no data integrity risk.

## Files Involved

- `src/agent/maintenance_daemon.py` (`compute_phase2_progress_metrics`, `DaemonState`)
- `src/agent/control_room_progress.py`
- `tests/test_control_room_progress.py`

---
**Expert Audit 2026-06** · Related: closed [#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
