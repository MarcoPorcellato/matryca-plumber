---
type: Document
---
## Problem Description

`scan_existing_tana_ids` in `src/agent/importers/tana/write.py` calls `read_graph_file_text` for every scannable page/journal, materializing full page bodies in RAM to regex-scan `tana-id::` values.

On a 10k-page vault (~50 KB average), peak memory can reach hundreds of MB before the scan completes; only the ID set is retained.

Claude Architectural Audit 2026-06-24: [`docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](../CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md).

Complements [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) (graph-build RAM) — this slice is the **pre-write idempotency gate**.

## Proposed Architectural Solution

Stream line-by-line per file (`path.open` + `_TANA_ID_PATTERN.search(line)`); peak RAM O(longest line), not O(vault size). Preserve `errors="replace"` and skip `OSError` on races.

Add test with multi-page fixture asserting IDs found without full-text mock.

## Estimated Impact

Alto on large vaults before Tana import apply — complements `ijson` parse anti-OOM.

## Files Involved

- `src/agent/importers/tana/write.py`
- `tests/test_tana_write.py`
- `docs/openspec/tana-import.md`

---

**Claude Audit 2026-06-24** · **GitHub:** [#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) · **Milestone:** v1.9.11 — Performance & I/O · **Related:** #154

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
