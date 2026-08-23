---
type: Document
---
## Problem Description

`src/agent/graph_dispatch.py` `_run_write_outline` resolves the write parent in one `asyncio.to_thread` call (`_resolve_write_parent_target`) and performs the write in a second call (`_headless_write_outline` or `_headless_write_outline_empty_page`).

OCC snapshot capture happens inside the write path, not during resolution. Between resolve and write, the graph can change (human edit, daemon concurrent write). The chosen `parent_uuid` or empty-page fallback may be stale — a TOCTOU gap distinct from write-time OCC abort.

Related spec: [`docs/openspec/agent-ax-robustness.md`](../../openspec/agent-ax-robustness.md) covers lenient input, not resolve/write atomicity.

## Proposed Architectural Solution

Hoist OCC snapshot to the resolution phase, or unify resolve + write under a single threaded call with one graph read and one `OCCSnapshot.capture`:

- `_resolve_write_parent_target_with_occ` returns `(parent_uuid, empty_page_title, warnings, occ_snapshot)`.
- Pass `occ_snapshot` into `_headless_write_outline` / `_headless_write_outline_empty_page` for drift check against the same read generation.

Add concurrency regression test (or integration test with controlled mtime drift between resolve and write).

## Estimated Impact

**Alto** — wrong write target (EOF append vs child splice) under concurrent co-editing; silent structural misplacement.

## Files Involved

- `src/agent/graph_dispatch.py` (`_run_write_outline`, `_resolve_write_parent_target`, `_headless_write_outline`, `_headless_write_outline_empty_page`)
- `tests/test_agent_experience_robustness.py` (extend)

---
**Expert Audit 2026-06** · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
