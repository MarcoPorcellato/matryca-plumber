---
type: Document
---
## Problem Description

All v2 read routing must pass through a storage abstraction ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17)). Today `graph_dispatch` calls `src/graph/*` directly — no testable port, no shadow adapter slot.

## Proposed Architectural Solution

Implement **Phase 1** per [`ROADMAP_V2_PREPARATION.md`](../../roadmaps/ROADMAP_V2_PREPARATION.md):

1. `GraphReadPort` (`typing.Protocol`) with narrow read methods.
2. `MarkdownGraphRepository` — wraps existing graph/parser code; **parity tests** on `tmp_path` fixtures.
3. Route **one** `graph_dispatch` read path through the port per slice PR.
4. Default runtime: Markdown adapter only — **no behavior change** when all flags off.

Child slice issues: `v2-phase1-graph-read-port.md`, `v2-phase1-dispatch-read-delegate.md`.

## Estimated Impact

**Alto** — foundation for #24 shadow routing; each slice PR stays small.

## Files Involved

- New repository module under `src/graph/` (ports)
- `src/agent/graph_dispatch.py`
- `tests/test_graph_repository.py`

---
**Parent:** [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Label:** `v2-prep`
