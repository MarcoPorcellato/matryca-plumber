## Problem Description

`src/memory/config.py` calls `_env_bool` from `src/agent/plumber_config.py`. The biological memory layer (`src/memory/`, Epic #99) must not depend on the agent package — Clean Architecture: domain/config depends inward on `utils` only.

## Proposed Architectural Solution

Move `_env_bool` / `_env_int` to `src/utils/env_parse.py` (coordinate with #57) or read `MATRYCA_MEMORY_GRAPH_ENABLED` directly in `memory/config.py` via a shared utils helper with no `agent` imports.

## Estimated Impact

Medio — blocks clean integration of Epic #99 and Shadow DB write path without import cycles.

## Files Involved

- `src/memory/config.py`
- `src/utils/env_parse.py` (new or extend)
- `tests/test_env_example_coverage.py`
- `tests/test_decay.py`

---

**Epic link:** #99 Biological Memory Layer

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
