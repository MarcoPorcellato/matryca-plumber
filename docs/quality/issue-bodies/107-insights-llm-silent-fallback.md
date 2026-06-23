## Problem Description

`src/graph/insights_engine.py` L392–396: when `llm.generate_graph_insights` raises, the code falls back to `_fallback_insights(metrics)` inside `except Exception` **without logging**. Operators cannot distinguish LLM-enriched vs deterministic insights in logs.

Contrast: `ui_server._safe_graph_analytics` logs failures; `post_write_hooks` uses `logger.exception`.

## Proposed Architectural Solution

Add `logger.warning` (or `logger.exception` once) before deterministic fallback. Keep `llm_used=False` semantics unchanged.

## Estimated Impact

Basso — observability only; no graph mutation behavior change.

## Files Involved

- `src/graph/insights_engine.py`
- `tests/` — mock LLM raise, assert log line and `llm_used=False`

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23
- Category: Bug
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
