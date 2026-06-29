## Problem Description

`src/agent/plumber_config.py` defines a private `_env_int` helper that duplicates `src/utils/env_parse.env_int` (warning on invalid values shipped in [#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152)).

Call sites in `memory_budget.py`, `page_prompt_session.py`, and `process_priority.py` import `_env_int` from `plumber_config`, coupling agent modules to a duplicate parser.

## Proposed Architectural Solution

1. Replace `_env_int` body with a thin re-export of `env_int` from `utils.env_parse`, **or** remove `_env_int` and update call sites to import `env_int` directly.
2. Keep `_map_bool` / `PlumberLintConfig` unchanged in this PR unless trivial.
3. Update `tests/test_plumber_config_env_serialization.py` to target `env_parse.env_int` if assertions move.

Single-module DRY slice — do not migrate every `plumber_config` helper in the same PR.

## Estimated Impact

**Basso** — one parser implementation; operators still get warnings on invalid ints.

## Files Involved

- `src/agent/plumber_config.py`
- `src/agent/memory_budget.py`
- `src/agent/page_prompt_session.py`
- `src/agent/process_priority.py`
- `tests/test_plumber_config_env_serialization.py`

---
**Parent:** [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) · **Tier F Clean Code**

_Closes when merged with tests green (`make check`)._
