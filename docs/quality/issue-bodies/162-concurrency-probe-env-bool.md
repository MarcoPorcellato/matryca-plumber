---
type: Document
---
## Problem Description

`src/graph/concurrency_probe.py` reads `MATRYCA_ALLOW_FLOCK_DEGRADATION` with inline `os.environ.get` and manual truthy-token parsing (~L33).

`src/utils/env_parse.env_bool` already implements the same contract used across graph and agent modules.

## Proposed Architectural Solution

1. Replace inline parsing with `env_bool("MATRYCA_ALLOW_FLOCK_DEGRADATION", default=False)` (verify current default matches code).
2. Add a focused unit test in `tests/test_concurrency_probe.py` or `tests/test_env_parse.py` if missing coverage for this call path.

## Estimated Impact

**Basso** — trivial DRY; no behavior change when env is unset.

## Files Involved

- `src/graph/concurrency_probe.py`
- `tests/` (minimal regression)

---
**Parent:** [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) · **Tier F Clean Code**

_Closes when merged with tests green (`make check`)._
