---
type: Document
---
## Problem Description

`tests/test_graph_layer_boundary.py` forbids `src/graph/` from importing `agent` and `daemon`, enforcing the v1.11.2 layer inversion ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134)).

There is no CI guard preventing `src/graph/` from importing `src/rag/`, which would invert the dependency rule (domain should not depend on retrieval adapters).

## Proposed Architectural Solution

1. Add `test_graph_modules_do_not_import_rag()` mirroring the existing agent/daemon tests.
2. Scan `src/graph/**/*.py` for `from ..rag`, `from src.rag`, or `import rag`.
3. Test-only PR — if any offender exists, fix in a **separate** PR or note in the issue comment; prefer green CI on `main`.

## Estimated Impact

**Basso** — preventive architecture guard; no runtime change if graph is already clean.

## Files Involved

- `tests/test_graph_layer_boundary.py`

---
**Tier F Clean Code** · SSOT: [`docs/CLEAN_CODE_ARCHITECTURE.md`](../../CLEAN_CODE_ARCHITECTURE.md)

_Closes when merged with tests green (`make check`)._
