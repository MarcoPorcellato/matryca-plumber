## Problem Description

Full pytest run emits:

```text
StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.
```

Source: `fastapi/testclient.py` via Sovereign UI server tests (`tests/test_ui_server.py`).

## Proposed Architectural Solution

Add `httpx2` dev dependency or upgrade FastAPI/Starlette to a combination that eliminates the warning. Target: `uv run pytest tests/test_ui_server.py -q -W error::DeprecationWarning` passes in CI.

## Estimated Impact

Basso — CI signal hygiene; no runtime behavior change.

## Files Involved

- `pyproject.toml` / `uv.lock`
- `tests/test_ui_server.py` (if import path changes)

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
