---
type: Document
---
## Problem Description

`src/agent/importers/tana/load.py` `load_tana_nodes_by_id` streams parse via `ijson` but immediately materializes `{node.id: node for node in iter_tana_nodes(export_path)}` — O(nodes) RAM. For large enterprise exports (50k+ nodes), this can consume hundreds of MB before conversion begins; `convert_tana_graph` then builds additional structures.

OpenSpec [`docs/openspec/tana-import.md`](../../openspec/tana-import.md) documents streaming parse but not this second memory peak.

## Proposed Architectural Solution

Replace full-node dict with incremental indexes during stream:

- `StreamingGraphBuilder.ingest_node(node)` maintains `children_by_parent`, `parent_by_child`, `tag_def_names`, stash/schema root IDs.
- `build()` returns a slim `TanaWorkspaceGraph` without retaining full `NodeDump` payloads where conversion does not need them.
- Keep `iter_tana_nodes` for tests; migrate `tana/graph.py` consumers.

Optional: progress callback every N nodes for CLI feedback.

## Estimated Impact

**Alto** on large exports — estimated ~80% RAM reduction for typical vaults; prevents OOM on 16 GB operator laptops.

## Files Involved

- `src/agent/importers/tana/load.py`
- `src/agent/importers/tana/graph.py`
- `src/agent/tana_import.py`
- `tests/test_tana_load.py`
- `docs/openspec/tana-import.md`

---
**Expert Audit 2026-06** · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
