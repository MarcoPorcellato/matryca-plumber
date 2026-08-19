---
type: Document
---
## Problem Description

Tana import v1 idempotency skips subtrees when `tana-id::` already exists in the vault (`src/agent/importers/tana/write.py` `_filter_outline_subtree`). This is **documented intentional** behavior per [`docs/openspec/tana-import.md`](../../openspec/tana-import.md).

Gap for v2: if the operator manually edits an imported page, re-import **silently skips** the subtree even when Tana export content diverges. The daemon cannot distinguish "unchanged duplicate" from "user-modified, needs merge."

## Proposed Architectural Solution

v2 enhancement (not a v1 bug):

1. Content hash or outline hash comparison before skip.
2. `--merge` flag: preserve user edits, append new blocks only, or surface conflict report.
3. Extend `Tana/Import Log` with skip reasons (`unchanged`, `user_modified`, `orphaned_tana_id`).

Defer implementation until Shadow DB / Safe-Sync epic ([#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)).

## Estimated Impact

**Basso in v1** (by design) · **Medio in v2** for operators re-syncing Tana exports into co-edited vaults.

## Files Involved

- `src/agent/importers/tana/write.py`
- `src/agent/tana_import.py`
- `docs/openspec/tana-import.md`

---
**Expert Audit 2026-06** · v2.0 scope · Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](../EXPERT_AUDIT_TRIAGE_2026-06.md)
