## MCP surface (eight tools)

Five **polymorphic mega-tools** plus **`store_fact`**, **`ingest_document`**, and **`import_tana`**. Mega-tools select behavior via a **literal discriminator** (`target_type`, `method`, `action`, `linter_name`).

| Tool | Discriminator | Purpose |
|------|---------------|---------|
| `read_graph_data` | `target_type` | Read pages, exact dated journals, L1 memory, **bootstrap_status**, block excerpts, **subtree** (heading-filtered), structural hops, dashboard, X-Ray aliases |
| `search_graph` | `method` | BM25, regex, unlinked mentions, journal tasks, entity resolution, gated canonical recall (`recall`) |
| `mutate_graph` | `action` | Write outlines, edit properties, append journal, inject queries |
| `refactor_blocks` | `action` | Split wall bullets, reparent siblings, generate flashcards |
| `run_linter` | `linter_name` | Tag unification preview, block-ref integrity, wiki schema scan |
| `store_fact` | _(none — `fact` string)_ | Persist a user preference under `- # AI Constraints` on `pages/matryca-config.md` |
| `ingest_document` | _(none — `source_name`, `raw_text`)_ | Atomic external markdown ingestion → ingest page + `LOG` + `GLOSSARY` |
| `import_tana` | _(none — `export_path`, `dry_run`)_ | Tana workspace JSON export → `Tana/` pages + journals; **dry-run default** |

**Requires:** `LOGSEQ_GRAPH_PATH` for every operation except `read_graph_data` with
`target_type="memory"` and disabled `search_graph(method="recall")`, which returns its
explicit feature-gate state before graph setup.

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
