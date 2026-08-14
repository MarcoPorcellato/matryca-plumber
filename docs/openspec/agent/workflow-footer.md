## Workflow: Search → Scan → Update

Mirror llm-wiki-style ingest. See `docs/ARCHITECTURE.md` for bridge vs on-disk boundaries.

### Phase 1 — Search

- Identify source (URL, file, inline text).
- Extract entities, facts, relationships, dates, decisions; separate evidence from interpretation.
- Classify chunks (business / technical / content / project / learning / reference).
- Route L1 vs L2; never store secrets in L2.

**Tools:** `read_graph_data` / `memory`; `search_graph` / `bm25` for topical discovery; `regex` for markers; external fetch as needed. Pre-shaped Markdown from email/export → plan **`ingest_document`** ([`docs/openspec/ingest.md`](docs/openspec/ingest.md)). Tana workspace JSON export → plan **`import_tana`** ([`docs/openspec/tana-import.md`](docs/openspec/tana-import.md)).

### Phase 2 — Scan

- `read_graph_data` / `page` for every page you will touch. For a single daily journal,
  use `journal_day` with an ISO date instead of a title search; it is an exact bounded
  Markdown read with provenance and no Shadow dependency. If `next_cursor` is not null,
  reissue its strict JSON query with that cursor; concatenate only the exact returned source
  slices after verifying the stable full-source digest.
- `subtree` when you need a focused excerpt (optional `heading` filter); `block_ast` for the raw on-disk splice around one `id::`.
- `structural_hops` before creating entities that might duplicate existing pages.
- `dashboard` for quick health before large edits.
- `run_linter` / `block_refs` when editing many `((uuid))` refs.
- `search_graph` / `unlinked_mentions` before thickening wikilinks.

**Plan output:** parent UUIDs, existing `id::` lines, append vs new-child strategy, refs to add.

### Phase 3 — Update

- **External outline paste (atomic)** → `ingest_document` with `source_name` + `raw_text` (fresh UUIDs, ingest page + `LOG`/`GLOSSARY`; parse uses OS temp only — never scratch files in `pages/`).
- **Tana workspace JSON export** → `import_tana` with `export_path` (+ `dry_run: false` after reviewing dry-run counters). CLI: `matryca import tana --file … [--apply]`.
- `mutate_graph` / `write_outline` with a **real parent block UUID** or **`Page Title|block`** (v1.9.7+ safe fallback when block ref is wrong but page exists).
- Append; do not silently overwrite human bullets.
- Attach `id::` to durable anchors; `source::` on factual leaves; `updated::` per your conventions.
- Property-only changes → `edit_property` (dry-run first).
- Journal captures → `append_journal`.
- Wall bullets → `refactor_blocks` / `split_large` (dry-run first).
- Flat lists → `reparent` (dry-run first).
- Unlinked mentions → minimal per-hit edits (`edit_property` on property lines; `write_outline` for body text).

### Quality gate (before stop)

- No credentials in L2 Markdown.
- ≤ **15** direct children per parent; split with sub-nodes.
- Blocks you will reference later must have on-disk **`id::`**.
- Re-run `run_linter` / `block_refs` after bulk `((uuid))` changes.
- Risky multi-page refactors: rely on post-write **`MATRYCA_GIT_ROBOT_COMMIT`** robot commits when the graph is a git repo.

---

## Human co-working (non-destructive)

A human edits the same files concurrently with the Plumber daemon and MCP tools. **Optimistic Concurrency Control** protects live edits: if `st_mtime` drifts during your inference window, abort and re-read — do not force the write.

**Page lock contention:** If Logseq or another writer holds the file, you may receive a lock-unavailable outcome instead of an OCC abort. Treat this like a **deferred retry**: skip the mutation, do not mark work complete, and revisit on the next cycle. Never bypass `page_rmw_lock` or set `MATRYCA_ALLOW_FLOCK_DEGRADATION` unless the operator explicitly accepts weaker cross-process safety on a cloud-synced vault.

If new information **contradicts** existing blocks, you **must not** silently overwrite.

1. Add a parent block stating the discrepancy.
2. Nest the original via `((uuid))` as "Legacy Claim".
3. Nest new findings as "Updated Claim".
4. Add `timestamp::` and `reasoning::`; leave resolution to the human.

---

## Agent-native CLI (same contract as MCP)

When the host runs **`uvx matryca-plumber`** or **`matryca`** instead of MCP tools (prefer PyPI `uvx` — see [`llms.txt`](llms.txt)):

| Pattern | Example |
|---------|---------|
| JSON stdout | `matryca --json read page "My Project"` |
| Exact journal day | `matryca --json read journal_day 2026-08-13` |
| Context macro | `matryca context load "My Project"` or `… load "Page\|uuid"` |
| Subtree read | `matryca read subtree "Page\|uuid"` |

Spec: [`docs/openspec/agent-dx.md`](docs/openspec/agent-dx.md). Distribution guide for hosts without MCP: [`llms.txt`](llms.txt) / [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md). Secrets are redacted in JSON output.

**Plumber hygiene properties (daemon, read-only for agents):** Blocks may carry `dead-link:: true` or `missing-asset:: true` after background verification ([`docs/openspec/link-verification.md`](docs/openspec/link-verification.md)). Do not remove these flags unless the operator fixed the URL or restored the asset.

**Runtime write boundary:** When the operator enables Strict Read Only, backend mutation tools reject graph writes with `graph_read_only`; do not retry them or attempt an alternate write path. The external Shadow DB read cache may remain enabled and accelerate reads because it is derived state outside the Logseq graph. Shadow availability never authorizes a graph write, and every non-ready cache state falls back to authoritative Markdown reads.

---

## Quick discriminator cheat sheet

```
READ   page | journal_day | memory | bootstrap_status | block_ast | subtree | structural_hops | dashboard | xray_page
SEARCH bm25 | semantic | regex | unlinked_mentions | journal_tasks | resolve_entity
MUTATE write_outline | edit_property | append_journal | inject_query
REFACTOR split_large | reparent | generate_flashcards
LINT   unify_tags | block_refs | full_wiki_scan
CLI    matryca --json …  |  matryca context load <query>
```

**Default safe sequence:** `memory` → `bootstrap_status` → Master Index `page` → plan → `dry_run: true` on mutators → apply → `block_refs`.
