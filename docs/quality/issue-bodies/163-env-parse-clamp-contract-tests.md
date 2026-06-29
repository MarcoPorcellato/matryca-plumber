## Problem Description

After Tier F slices migrate clamped env reads to `env_parse`, the **clamp-after-parse** pattern (e.g. `max(1, min(200, env_int(...)))`) should be documented by tests so contributors do not reintroduce silent inline parsing in `src/graph/`.

`tests/test_env_parse.py` covers raw parser behavior but not the link-verification / generational-cache clamp contracts.

## Proposed Architectural Solution

1. Add parametrized tests documenting clamp contracts for:
   - `MATRYCA_LINK_VERIFY_STRIKES` (min 1)
   - `MATRYCA_LINK_VERIFY_BATCH` (1–200)
   - `MATRYCA_LINK_VERIFY_TIMEOUT` (1.0–60.0 seconds)
   - `MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS` (1–32)
2. Tests may call the public accessor functions in `link_verification` / `generational_cache` with `monkeypatch.setenv` — **test-only PR** if F1/F2 not yet merged; otherwise extend after F1/F2 land.

Pair with [#158](docs/quality/issue-bodies/158-link-verification-env-parse.md) / [#159](docs/quality/issue-bodies/159-generational-cache-env-parse.md) in a separate PR to avoid conflicts.

## Estimated Impact

**Basso** — tests as specification; improves contributor safety.

## Files Involved

- `tests/test_env_parse.py` and/or `tests/test_link_verification.py`, `tests/test_generational_cache.py`

---
**Tier F Clean Code** · Depends on F1/F2 optionally

_Closes when merged with tests green (`make check`)._
