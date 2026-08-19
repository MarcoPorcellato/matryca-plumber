---
type: Document
---
## Tool reference and invocation examples

Invoke tools with the discriminator as a **string literal** plus the parameters shown. `payload` and enriched `query` values are JSON **strings** (serialize objects before sending).

### 1. `read_graph_data`

```json
{ "target_type": "page", "query": "My Project" }
```

Logseq **page title**, not a file path. Returns block tree, `synthetic_id`, `source_uuid`, `uuid`. Use before any edit.

```json
{ "target_type": "memory", "query": "" }
```

Loads L1 fast-context Markdown. `query` ignored.

```json
{ "target_type": "block_ast", "query": "My Project|aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" }
```

On-disk bullet subtree for one `id::` block (`Page Title|block-uuid`). Headless; no Logseq HTTP API.

```json
{ "target_type": "subtree", "query": "My Project|aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" }
```

Focused excerpt for one block; optional JSON `heading` to narrow to a single bulleted section (token-saving). Prefer over full `page` when you already know the anchor UUID.

When the Shadow row cannot be proven current, the result comes from Markdown and
ends with a bounded `Shadow fallback` code. If the authoritative page has been
deleted, the result is an explicit subtree-unavailable envelope; stale cached content
is never returned.

```json
{
  "target_type": "subtree",
  "query": "{\"page\":\"My Project\",\"block_uuid\":\"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\",\"heading\":\"Implementation\"}"
}
```

```json
{ "target_type": "structural_hops", "query": "Seed Page A, Seed Page B" }
```

BFS over wikilinks, tags, light `type::` / `domain::` rings. Optional JSON query:

```json
{
  "target_type": "structural_hops",
  "query": "{\"seeds\":\"Seed Page A, Seed Page B\", \"max_depth\": 3, \"max_per_level\": 40}"
}
```

```json
{ "target_type": "bootstrap_status", "query": "" }
```

Phase 1 semaphore: `bootstrap_complete`, `soft_gate_active`, harvest progress. `query` ignored. Call before the Master Index Soft Gate.

```json
{ "target_type": "dashboard", "query": "" }
```

Health snapshot: page counts, `id::` tally, block-ref summary. `query` ignored.

```json
{ "target_type": "xray_page", "query": "My Project" }
```

X-Ray outline with `[n]` aliases; persists `.matryca_xray_state.json` at the graph root in normal mode or in the private per-graph external runtime cache under Strict Read Only. Pass `[n]` into `target` / `target_uuid` on subsequent operations (stateless CLI-safe).

---

### 2. `search_graph`

```json
{ "method": "bm25", "query": "redis cache invalidation" }
```

Okapi BM25 over `pages/**/*.md` remains the default lexical path. Optional **`method=semantic`** uses dual block embeddings when `MATRYCA_DUAL_EMBEDDING_ENABLED=true` (see [`docs/openspec/dual-embedding.md`](docs/openspec/dual-embedding.md)). Optional:

```json
{ "method": "bm25", "query": "{\"keyword\":\"redis cache\", \"limit\": 15}" }
```

Always follow top hits with `read_graph_data` / `target_type="page"`.

Shadow FTS validates each returned page row before serving it. Changed or missing
rows, and empty cached results whose freshness cannot be proved, route to
generational BM25 and append a content-free `Shadow fallback` code. The closed codes
are `page_untracked`, `source_missing`, `source_changed`, and
`empty_result_unproven`.

```json
{ "method": "recall", "query": "redis cache invalidation" }
```

P0 canonical recall is disabled by default. Set `MATRYCA_MEMORY_GRAPH_ENABLED=true` to
receive a structured, provider-free envelope with ordered block UUID/content-hash references,
the Shadow generation, a deterministic fingerprint, and a no-progress signature. It accepts
`{"query":"...", "limit":15, "filters":{}}`; the limit is bounded to 50 per call.
It uses a READY query-only Shadow FTS cache and validates every returned source page. It never
falls back to BM25/semantic, rebuilds Shadow, calls a model, or writes the graph: disabled,
unavailable, stale, empty-unproven, and unsupported-filter cases are explicit states.

```json
{ "method": "regex", "query": "TODO|LATER" }
```

Line scan in `pages/`. Optional:

```json
{ "method": "regex", "query": "{\"pattern\":\"id::\", \"limit\": 50}" }
```

Use for literal tokens, markers, or property-line patterns — not for topical discovery (use `bm25`).

```json
{ "method": "unlinked_mentions", "query": "" }
```

Plain-text mentions of existing page titles → candidate `[[wikilinks]]`. Optional:

```json
{
  "method": "unlinked_mentions",
  "query": "{\"max_hits_per_file\": 80, \"max_titles\": 500}"
}
```

Returns structured `hits` (file, line, column, `suggested`). Review each hit; apply minimal edits via `mutate_graph`.

```json
{ "method": "journal_tasks", "query": "7" }
```

Open `TODO` / `LATER` / `WAITING` in `journals/` for the last N days (default 7, max 90). Optional:

```json
{ "method": "journal_tasks", "query": "{\"days\": 14}" }
```

---

### 3. `mutate_graph`

```json
{
  "action": "write_outline",
  "target": "My Project|parent-block-uuid-or-[0]",
  "payload": "{\"text\":\"New parent bullet\",\"properties\":{\"tags::\":\"[[Topic]]\"},\"children\":[{\"text\":\"Child with evidence\",\"properties\":{\"source::\":\"https://example.com\"}}]}"
}
```

`target` = parent **block UUID**, X-Ray **`[n]`**, or **`Page Title|block-ref`** (pipe form recommended when UUIDs may be hallucinated). `payload` = `OutlineNode` JSON. Append-only discipline: do not silently overwrite human blocks. On invalid block ref with valid page, Plumber may **safe-append** at page bottom and return `warnings`. May auto-git-snapshot when `MATRYCA_GIT_SNAPSHOT_ON_WRITE` is enabled.

```json
{
  "action": "edit_property",
  "target": "My Project|aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "payload": "{\"search\":\"status:: draft\",\"replacement\":\"status:: active\",\"dry_run\": true}"
}
```

Surgical `key::` line edits inside the block span anchored at `id::`. **Always** `dry_run: true` first; inspect `match_count`, `previews`, size fields; then `dry_run: false`. Use dedicated persist flows for new `id::` lines — matchers **exclude** existing `id::` rows (they are UUID anchors, not editable metadata keys). Optional: `use_regex`, `replace_all`, `case_sensitive`.

```json
{
  "action": "append_journal",
  "target": "",
  "payload": "## Capture\n- Bullet for today"
}
```

Appends to today's `journals/YYYY_MM_DD.md`. Or:

```json
{
  "action": "append_journal",
  "target": "",
  "payload": "{\"markdown_body\":\"- Task [[Project]]\", \"dry_run\": true}"
}
```

```json
{
  "action": "inject_query",
  "target": "parent-block-uuid",
  "payload": "{\"query_preset\": \"open_markers\", \"dry_run\": true}"
}
```

Injects Logseq advanced-query block under parent. Supply `query_preset` (`open_markers`, `pages_tagged`, …) and/or `query_edn`. Always preview with `dry_run: true`.

---

### 4. `refactor_blocks`

```json
{
  "action": "split_large",
  "target_uuid": "My Project",
  "payload": "{\"min_chars\": 400, \"max_blocks\": 25, \"dry_run\": true}"
}
```

Splits wall-of-text bullets into children; parent keeps its `id::`. Empty `target_uuid` = all pages. **Always** `dry_run: true` first.

```json
{
  "action": "reparent",
  "target_uuid": "Daily Journal 2026-05-19",
  "payload": "[{\"category\": \"Meetings\", \"block_uuids\": [\"uuid-a\", \"uuid-b\"]}, {\"category\": \"Admin\", \"block_uuids\": [\"uuid-c\"]}]"
}
```

Groups flat siblings under named section headers (same indent, non-overlapping UUIDs). `payload` must be a JSON **array** of group objects (not a single object); Matryca repairs common LLM JSON defects before parse. **Always** `dry_run: true` first. Applying (`dry_run: false`) may git-snapshot when snapshots are enabled.

```json
{
  "action": "generate_flashcards",
  "target_uuid": "Study Notes|source-block-uuid",
  "payload": "{\"max_cards\": 20, \"dry_run\": true}"
}
```

Appends `#card` child bullets with new `id::` per card. Inspect `cards_preview` before `dry_run: false`.

---

### 5. `run_linter`

```json
{ "linter_name": "block_refs" }
```

Markdown report: every `((uuid))` vs the parser's global node index. Run after large refactors and before claiming link integrity.

```json
{ "linter_name": "unify_tags" }
```

Preview-only hashtag clustering (`#AI` vs `#ai`). Apply rewrites only after explicit operator consent (implementation returns preview; vault-wide apply is operator-gated).

```json
{ "linter_name": "full_wiki_scan" }
```

Lint wiki-prefixed pages per `matryca-wiki.yml` (`type::`, stale knowledge, credential patterns, wikilinks).

---

### 6. `store_fact`

```json
{ "fact": "Always respond in Italian for human-readable fields when the source page is Italian." }
```

Appends `fact` as a new bullet **under** `- # AI Constraints` on `pages/matryca-config.md`. Creates the page with Telos/Constraints headings when missing. Returns JSON with `ok`, `block_uuid`, and `path`. Does **not** receive the automatic MCP identity footer (you just updated identity). Post-write hooks refresh the AST cache and may run a robot git commit per file.

Use for durable preferences that should apply to **all future** daemon and MCP sessions — not for one-off page content (use `mutate_graph`).

---

### 7. `ingest_document`

```json
{
  "source_name": "Weekly email digest",
  "raw_text": "- Summary bullet\n  - Detail\n"
}
```

Parses `raw_text` with `logseq-matryca-parser` using a **temporary OS `.md` file** (not under `pages/`). Assigns fresh `id::` UUIDs, appends a wrapped section to the ingest destination (`Ingest/YYYY-MM-DD` or `MATRYCA_INGEST_PAGE`), and appends ledger lines to `LOG` and `GLOSSARY` when applicable. Rejects secret patterns in the payload.

---

### 8. `import_tana`

```json
{
  "export_path": "/absolute/path/to/tana-workspace.json",
  "dry_run": true
}
```

Streams Tana `docs[]` via **`ijson`**, converts entities to `Tana/` pages, routes `#day` nodes using `logseq/config.edn`, resolves wikilinks (in-flight batch + vault catalog), and writes with **`tana-id::` idempotency**. **`dry_run: true` by default** — review JSON counters before setting `dry_run: false`. Spec: [`docs/openspec/tana-import.md`](docs/openspec/tana-import.md).

---
