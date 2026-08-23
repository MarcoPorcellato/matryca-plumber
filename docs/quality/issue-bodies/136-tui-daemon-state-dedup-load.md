---
type: Document
---
## Problem Description

`src/cli/tui_dashboard.py` `collect_snapshot_safe` calls `collect_snapshot`, which already loads daemon state via `_try_load_daemon_state`. On success, `collect_snapshot_safe` calls `load_daemon_state(root)` **again** (L236–238).

The TUI polls every ~5 seconds. For large vaults, `.matryca_daemon_state.json` can be multi-MB — redundant full JSON parse and disk I/O every tick.

[#102](https://github.com/MarcoPorcellato/matryca-plumber/issues/102) fixed **logging** on load failures; [#125](https://github.com/MarcoPorcellato/matryca-plumber/issues/125)–[#127](https://github.com/MarcoPorcellato/matryca-plumber/issues/127) are observability slices — none deduplicate the success-path double load.

## Proposed Architectural Solution

Introduce `DashboardStateCache` (or reuse snapshot's loaded state):

- Track `state_path.stat().st_mtime` (or `st_mtime_ns`).
- Reload only when mtime changes or cache invalidated.
- Return cached `DaemonState` from `collect_snapshot_safe` without second parse.

Preserve `last_good_state` fallback behavior from #102.

## Estimated Impact

**Medio** — reduced CPU and I/O on long-running TUI sessions over large vaults.

## Files Involved

- `src/cli/tui_dashboard.py`
- `tests/test_tui_dashboard.py`

---
**Expert Audit 2026-06** · Distinct from #125–#127 · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
