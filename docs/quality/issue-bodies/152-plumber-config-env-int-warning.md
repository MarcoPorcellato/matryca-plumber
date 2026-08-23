---
type: Document
---
## Problem Description

`_env_int` in `src/agent/plumber_config.py` (~L58–65) returns the Python default when `int(raw)` raises `ValueError`, with **no warning**. Operators who typo `MATRYCA_*` numeric env vars get silent fallback behavior.

Expert Audit P3 and [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) track env-parser DRY; [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90)–[#91](https://github.com/MarcoPorcellato/matryca-plumber/issues/91) cover `_env_bool` dedup slices.

## Proposed Architectural Solution

When `raw` is non-empty and `int(raw)` fails, emit `logger.warning` naming the key and invalid value before returning `default`. Optionally extend `_env_float` the same way in the same PR if trivial.

Add tests in `tests/test_plumber_config.py` (create focused cases if missing).

## Estimated Impact

Basso — contributor/operator config hygiene; no change when env is unset or valid.

## Files Involved

- `src/agent/plumber_config.py`
- `tests/test_plumber_config.py`

---

**Parent:** #57 · **Milestone:** v1.9.12 — Code Perfection & Tech Debt

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
