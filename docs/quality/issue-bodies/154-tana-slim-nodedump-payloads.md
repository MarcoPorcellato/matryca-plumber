---
type: Document
---
## Problem Description

Tana import streams JSON via `ijson` (no `json.load()` DOM). Production orchestration uses `TanaWorkspaceGraph.from_export` — a **single streaming pass** through `StreamingGraphBuilder`.

The builder still retains every `NodeDump` payload in `_nodes: dict[str, NodeDump]` until `build()` returns. For 50k+ node exports this second memory peak can reach hundreds of MB before conversion writes begin.

[#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) shipped single-pass `from_export`; this slice completes the RAM reduction goal in the original issue body.

Clean Architecture Audit 2026-06 triage: [`docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](../CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md).

## Proposed Architectural Solution

During `StreamingGraphBuilder.ingest_node`, retain only fields needed for:

- parent/child graph indexes
- tag definitions and entity heuristics
- conversion-time text/props for nodes that become pages or inline blocks

Drop or slim full `NodeDump` blobs once indexed when conversion does not need the raw export payload. Keep `iter_tana_nodes` + full nodes for unit tests.

## Estimated Impact

Alto on large exports — estimated ~80% RAM reduction for typical vaults; complements `ijson` anti-OOM parse.

## Files Involved

- `src/agent/importers/tana/graph.py` (`StreamingGraphBuilder`)
- `src/agent/importers/tana/convert.py` (consume slim records)
- `tests/test_tana_graph.py`, `tests/test_tana_e2e.py`
- `docs/openspec/tana-import.md`

---

**Parent / extends:** #135 · **GitHub:** [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) · **Milestone:** v1.9.11 — Performance & I/O

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
