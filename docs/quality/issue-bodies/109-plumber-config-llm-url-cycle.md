## Problem Description

GitNexus `check --cycles` reports:

```text
plumber_config.py → llm_url_policy.py → plumber_config.py
```

Lazy import in `assert_safe_lm_proxy_url` hides the cycle at runtime but complicates static analysis, testing, and future `src/memory/` wiring.

## Proposed Architectural Solution

Extract shared LLM URL resolution into `src/utils/llm_config.py` (or extend `llm_url_policy.py`) with **no** `agent` imports. `plumber_config.resolve_llm_base_url` remains the operator-facing resolver; policy module depends only on utils.

## Estimated Impact

Medio — architecture hygiene before v2.0 memory layer.

## Files Involved

- `src/agent/plumber_config.py`
- `src/utils/llm_url_policy.py`
- `tests/test_llm_url_policy.py`
- `tests/test_plumber_config_env_serialization.py`

---

**Audit metadata**
- Source: GitNexus bug hunt 2026-06-23
- Related: #57 (env parser DRY)
- Milestone: v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
