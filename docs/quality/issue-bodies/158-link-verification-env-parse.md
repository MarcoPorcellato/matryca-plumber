---
type: Document
---
## Problem Description

`src/graph/link_verification.py` already uses `env_bool` for `MATRYCA_LINK_VERIFY_ENABLED`, but `link_verify_strikes_threshold`, `link_verify_batch_size`, and `link_verify_timeout_seconds` duplicate inline `os.environ.get` + `try/except` parsing (~L73–94).

This scatters config parsing outside the shared helper and bypasses the invalid-value warning contract in `src/utils/env_parse.py`.

## Proposed Architectural Solution

1. Import `env_int` and `env_float` from `src/utils/env_parse.py`.
2. Replace inline parsing with `env_int` / `env_float`, then apply existing clamps at the call site (`max(1, …)`, `min(200, …)`, etc.).
3. Add or extend tests in `tests/test_link_verification.py` asserting clamp behavior for invalid env values.

Do **not** change default values or clamp ranges.

## Estimated Impact

**Basso** — DRY / Dependency Inversion slice; no behavior change when env is unset or valid.

## Files Involved

- `src/graph/link_verification.py`
- `tests/test_link_verification.py`

---
**Parent:** [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) · **Tier F Clean Code** · Triage: [`docs/CLEAN_CODE_ARCHITECTURE.md`](../../CLEAN_CODE_ARCHITECTURE.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
