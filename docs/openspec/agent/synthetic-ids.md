---
type: Document
---
## CRITICAL: synthetic IDs and broken links

`read_graph_data` with `target_type="page"` returns Matryca Parser spatial output per block:

- **`synthetic_id`** — `true` if UUID was generated in memory, not read from disk.
- **`source_uuid`** — UUID from an on-disk `id::` line (safe for `((uuid))`).
- **`uuid`** — parser canonical id; use this value when **persisting** a new `id::`.

**If `synthetic_id: true` and `source_uuid` is absent**, `((uuid))` refs are **broken** until persisted.

**Required workflow:**

1. **Read** — `read_graph_data` / `target_type="page"` (or `subtree` / `block_ast` for a focused excerpt).
2. **Persist** — `mutate_graph` / `action="edit_property"` inject `id:: <uuid>` into the source block. Always `dry_run: true` first, then `dry_run: false`.
3. **Reference** — Only after `id::` exists on disk, emit `((that-uuid))` in new content.

Re-run `run_linter` / `linter_name="block_refs"` after bulk ref edits.

---
