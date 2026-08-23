---
type: Document
---
## Problem Description

Phase 3 alpha requires an explicit operator opt-in before MCP/CLI prefer shadow reads.

## Proposed Architectural Solution

1. `shadow_db_enabled() -> bool` via `env_bool("MATRYCA_SHADOW_DB_ENABLED", False)` in `src/shadow/config.py`.
2. Document in [`.env.example`](../../../.env.example) — Advanced / high impact section.
3. `tests/test_env_example_coverage.py` allowlist if needed.
4. No routing change until a follow-up slice wires dispatch — this slice is flag + docs + unit test only.

## Estimated Impact

**Basso** — config surface only.

## Files Involved

- `src/shadow/config.py` (new)
- `.env.example`
- `tests/test_shadow_config.py` (new)

---
**Parent:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 3 · **Label:** `v2-alpha`
