## Problem Description

`src/graph/graph_analytics.py` — `_count_catalog_summaries()` wraps `load_master_catalog()` in a bare `except Exception: return 0` (L121–124).

Any unexpected failure (permissions, flock timeout, schema edge case) makes Sovereign UI analytics report **zero page summaries** with **no log line**. `_safe_graph_analytics` in `ui_server.py` only catches exceptions from the outer `compute_graph_analytics` call, not this inner swallow.

Discovered during GitNexus bug hunt (2026-06-23). See `docs/quality/BUG_HUNT_2026-06-23.md`.

## Proposed Architectural Solution

Catch `CatalogLoadError`, `BoundedJsonError`, and `OSError` explicitly; log with `logger.warning` or `logger.exception`; return 0 only for known-empty catalog states. Align with `ui_server._safe_graph_analytics` logging style.

## Estimated Impact

Medio — operators see wrong telemetry in Sovereign UI without any ops-log breadcrumb.

## Files Involved

- `src/graph/graph_analytics.py`
- `tests/test_graph_analytics.py` (corrupt-catalog / permission-denied case)

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23 (`docs/quality/GITHUB_BUG_BACKLOG.md`)
- Category: Bug
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
