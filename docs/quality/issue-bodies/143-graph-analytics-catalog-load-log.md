---
type: Document
---
## Problem Description

`_count_catalog_summaries` in `src/graph/graph_analytics.py` (~L118–124) wraps `load_master_catalog(root)` in bare `except Exception` and returns `0` with **no log line**.

Sovereign UI / analytics tiles that depend on catalog summary counts silently show zero when the master catalog sidecar is corrupt, locked, or unreadable.

## Proposed Architectural Solution

Catch `OSError` and `BoundedJsonError` explicitly (match `load_master_catalog` failure modes). Emit `logger.warning` or `logger.exception` before returning `0`. Preserve the existing `0` fallback — observability only.

Add a regression test in `tests/test_graph_analytics.py` mocking `load_master_catalog` to raise.

## Estimated Impact

Basso — operator visibility; no behavior change when catalog loads succeed.

## Files Involved

- `src/graph/graph_analytics.py`
- `tests/test_graph_analytics.py`

---

**Milestone:** v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
