---
type: Document
---
## Problem Description

v2.0 Shadow DB sync and read routing depend on a modular daemon duty cycle and a thin `graph_dispatch` router. Large monoliths ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58), [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)) increase merge risk for shadow hooks.

Config scattered across `os.environ` in graph modules ([#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)) complicates injectable shadow flags.

## Proposed Architectural Solution

Close or land **slices** of v1.9.12 prerequisites before Phase 1 `GraphRepository` work. Track blockers — do not duplicate #58/#59.

| Blocker | Action |
|---------|--------|
| [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) | Split `maintenance_daemon` — extract one duty-cycle helper per PR |
| [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) | `graph_dispatch` handler registry — one tool group per PR |
| [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) / Tier F [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168)–[#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173) | `env_parse` adoption in graph modules |
| [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) | Vector RAM — ondemand default shipped; shadow shard plan documented |

**Phase 0 complete when:** at least one #58 and one #59 slice merged; Tier F env_parse slices on main or explicitly deferred with maintainer comment.

## Estimated Impact

**Medio** — unblocks v2 velocity; no operator-visible v2 feature in this phase.

## Files Involved

- `src/agent/maintenance_daemon.py`, `src/agent/graph_dispatch.py`
- `src/graph/*`, `src/utils/env_parse.py`
- [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md)

---
**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Label:** `v2-prep`  
**SSOT:** [`v2_preparation_blueprints.md`](../../v2_preparation_blueprints.md)

_Tracking issue — close when Phase 0 DoD met; link PRs with `Refs #N`._
