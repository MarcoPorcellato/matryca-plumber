---
type: Document
---
## Problem Description

`src/graph/generational_cache.py` reads `MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS` and `MATRYCA_BM25_MODE` via inline `os.environ.get` in `_generational_cache_max_graphs()` and `_bm25_mode()` (~L32–72).

`src/utils/env_parse.py` already provides shared parsing with invalid-value warnings ([#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62) partial).

## Proposed Architectural Solution

1. Use `env_int("MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS", _DEFAULT_CACHE_MAX_GRAPHS)` then clamp with `max(1, min(32, value))`.
2. For BM25 mode: read with `env_parse` or a small helper that validates membership in `{"resident", "ondemand"}` — preserve current fallback to `"resident"`.
3. Add tests in `tests/test_generational_cache.py` (or extend existing) for invalid int env and unknown mode string.

## Estimated Impact

**Basso** — config DI hygiene; no change when env is unset or valid.

## Files Involved

- `src/graph/generational_cache.py`
- `tests/test_generational_cache.py`

---
**Parent:** [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) · **Tier F Clean Code**

_Closes when merged with tests green (`make check`)._
