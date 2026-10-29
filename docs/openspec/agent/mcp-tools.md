---
type: Document
---
## MCP surface (eight tools)

Five **polymorphic mega-tools** plus **`store_fact`**, **`ingest_document`**, and **`import_tana`**. Mega-tools select behavior via a **literal discriminator** (`target_type`, `method`, `action`, `linter_name`).

| Tool | Discriminator | Purpose |
|------|---------------|---------|
| `read_graph_data` | `target_type` | Read pages, exact dated journals, L1 memory, **bootstrap_status**, block excerpts, **subtree** (heading-filtered), structural hops, dashboard, X-Ray aliases |
| `search_graph` | `method` | BM25, optional semantic snapshots, regex, unlinked mentions, journal tasks, entity resolution, gated canonical recall (`recall`) |
| `mutate_graph` | `action` | Write outlines, edit properties, append journal, inject queries |
| `refactor_blocks` | `action` | Split wall bullets, reparent siblings, generate flashcards |
| `run_linter` | `linter_name` | Tag unification preview, block-ref integrity, wiki schema scan |
| `store_fact` | _(none — `fact` string)_ | Persist a user preference under `- # AI Constraints` on `pages/matryca-config.md` |
| `ingest_document` | _(none — `source_name`, `raw_text`)_ | Atomic external markdown ingestion → ingest page + `LOG` + `GLOSSARY` |
| `import_tana` | _(none — `export_path`, `dry_run`)_ | Tana workspace JSON export → `Tana/` pages + journals; **dry-run default** |

**Requires:** `LOGSEQ_GRAPH_PATH` for every operation except `read_graph_data` with
`target_type="memory"` and disabled `search_graph(method="recall")`, which returns its
explicit feature-gate state before graph setup.

`read_graph_data(target_type="bootstrap_status")` reports graph-local catalog and
checkpoint state, with an informational `read_only` boolean. Existing catalog
fields are unchanged; missing-checkpoint 0/0 is not Shadow progress. When
`read_only=true`, the observer cannot create a missing Master Index/catalog:
do not recommend catalog bootstrap or Cloud Indexing. Use only authorized
targeted reads and require explicit authorization before uncatalogued discovery.
Read `target_type="shadow_status"` separately for external-cache readiness; that
content-free status call performs no initialization or migration. Neither status
grants permission, proves graph completeness or resolves dashboard failures.

`search_graph(method="semantic")` selects the separate content-vector backend when
`MATRYCA_EXTERNAL_SEMANTIC_ENABLED=true`. Its maintenance CLI builds an external
snapshot without changing graph files; querying never builds or migrates it. Follow
the returned snapshot compatibility and source freshness state. This is independent
of Shadow and graph-local catalog readiness. External synthetic citation IDs are
not Logseq UUIDs and must never be passed to `block_ast`; cite their source path,
title, block/chunk position and source hash. Fragments retain their original block
properties and parent references. Keep queries within the configured token limit
(plus the independent byte guard) and split longer questions into focused
searches. The legacy dual-vector backend remains separate and requires its own
opt-in. See
[`external-semantic-read-only.md`](docs/openspec/external-semantic-read-only.md).

The `search_graph` prerequisite follows the same mode-aware Soft Gate: inspect
`bootstrap_status` and read the Master Index only when present. With
`read_only=true`, do not recommend catalog-building daemon bootstrap or Cloud
Indexing; check `shadow_status` separately and obtain explicit user authorization
before uncatalogued discovery. A ready cache does not complete the catalog or
grant permission, and graph writes remain blocked. The three writable-mode
fallbacks apply only when `read_only=false`. Disabled `recall` still returns its
feature-gate state before graph setup; this guidance does not enable a search
method or change search execution.

`read_graph_data(target_type="xray_page")` persists its alias map at graph root in normal mode. Under Strict Read Only, it uses the private per-graph external runtime cache so the read remains graph-immutable while aliases stay available to later operations.

`read_graph_data(target_type="journal_day", query="YYYY-MM-DD")` reads exactly the canonical
`journals/YYYY_MM_DD.md` file. For deterministic pagination, use strict JSON
`{"date":"YYYY-MM-DD","cursor":0,"max_chars":25000}`; no extra fields are accepted. Each
call re-reads the canonical file and returns a compact provenance/trust envelope with full source
SHA-256 and character count, exact returned `[start,end)` range, and `next_cursor` (or `null`).
Pages prefer newline boundaries but split an overlong line to guarantee progress. Invalid
dates/queries/cursors, missing/empty files, symlinks, non-regular files, and invalid UTF-8 return
explicit content-free states. It is graph read-only, bypasses Shadow entirely, and never
initializes a cache.

When Shadow is `ready`, subtree and BM25/FTS reads validate requested cached page
rows against authoritative Markdown before returning them. If a row is untracked,
missing, or changed—or an empty FTS result cannot prove freshness—the tool uses the
Markdown/generational BM25 fallback and appends one content-free `Shadow fallback`
code: `page_untracked`, `source_missing`, `source_changed`, or
`empty_result_unproven`. Treat the fallback output as authoritative; do not retry the
cache path.

`search_graph(method="recall")` is an opt-in P0 canonical envelope, not a BM25 alias.
Set `MATRYCA_MEMORY_GRAPH_ENABLED=true`, then pass text or
`{"query":"...", "limit":15, "filters":{}}`. It returns a provider-free,
content-free `RecallBundle` with ordered block UUID/hash references, a generation-bound
fingerprint, and a no-progress signature. It uses only a READY query-only Shadow FTS cache.
When disabled, unavailable, stale, empty-unproven, or given unsupported filters, it returns
an explicit structured state and never falls back, rebuilds Shadow, reads via a model, or
writes the graph.
