## Problem Description

Safe-Sync separates **read caches** from **write paths** so Matryca never mutates Logseq's internal stores. The Logseq OG write path shipped in v1.9.5; Logseq DB and write-module abstraction remain open for v2.

## Proposed Architectural Solution

Phase 4 of [`ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md).

### Done (v1.9.5+)

| Task | Evidence |
|------|----------|
| Classic Logseq: append `.md` + OCC (`st_mtime` / `st_mtime_ns`) | `src/graph/markdown_blocks.py`, `src/graph/page_write_lock.py` |
| Mutators only via MCP/CLI graph tools | `graph_dispatch.py` — `mutate_graph`, `ingest_document`, etc. |
| Safe-Sync documented | `SYSTEM_PROMPT.md`, `docs/ARCHITECTURE.md`, `docs/openspec/llm-os-instructions.md` |
| L0 write safety before semantic commits | `src/graph/safety/validators.py` (v1.12) |

### Open (v2.0 Phase 4)

| Task | Notes |
|------|-------|
| Logseq DB write bridge | Route writes through official CLI/API (`qmd`) — **never** direct Logseq internal SQLite |
| `DatabaseRepository` write module | Part of [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) — after `MarkdownGraphRepository` |
| Memory graph writes | `shadow.sqlite` only — see [`docs/openspec/biological-memory.md`](docs/openspec/biological-memory.md) |

### Zero-Interference principle

Logseq remains single source of truth. Matryca never mutates Logseq app-internal stores behind the scenes.

## Estimated Impact

**Alto** — required for Logseq DB coexistence; OG operators unaffected until they opt into DB mode.

## Files Involved

- `src/agent/graph_dispatch.py` (write routing)
- Future `DatabaseRepository` adapter
- `docs/openspec/llm-os-instructions.md` (contract updates)

---
**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Related:** [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17), [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139)

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
