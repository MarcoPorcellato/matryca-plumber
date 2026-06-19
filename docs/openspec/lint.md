# Lint (Matryca Plumber on-disk)

**Roadmap:** [`ROADMAP_LLM_WIKI.md`](../../ROADMAP_LLM_WIKI.md)

## Tools

| MCP tool | Module | Role |
|----------|--------|------|
| `lint_logseq_block_refs` | `src/graph/block_ref_lint.py` | `((uuid))` vs graph-wide `id::` (regex pass). |
| `lint_matryca_wiki_pages` | `src/graph/wiki_lint.py` | Prefixed pages: `type::`, stale knowledge, credentials, wikilinks. |

Block structure for spatial semantics remains in **`logseq-matryca-parser`**; these lints are text/heuristic passes only.

**LLM-heavy cognitive lint** (semantic index, MARPA, property hygiene, bootstrap harvest) shares the v1.8 prompt and memory contracts in [`llm-performance.md`](llm-performance.md). Property hygiene uses `mldoc_properties` matchers that **exclude** `id::` UUID lines; Phase 2 daemon inference does **not** hold `page_rmw_lock` (see [`ARCHITECTURE.md`](../ARCHITECTURE.md#optimistic-concurrency-control-occ)).

**Journal pages:** Files under `journals/` **bypass** the Phase-2 cognitive lint and semantic-index pipeline during daemon duty cycles. They still receive Phase-1 structural settle (AST cache refresh, link registry, OCC `st_mtime_ns` ledger). MARPA, property hygiene, and entity consolidation were already journal-aware in `run_cognitive_lint_pipeline`; the duty-cycle shortcut avoids all LLM work on daily notes. See [`llm-performance.md`](llm-performance.md#journal-pages--phase-2-semantic-bypass).
