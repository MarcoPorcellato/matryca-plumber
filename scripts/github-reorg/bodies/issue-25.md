### Safe-Sync write path — split status

## Done (v1.9.5)

| Task | Evidence |
|------|----------|
| Classic Logseq: append `.md` + OCC (`st_mtime_ns`) | `src/graph/markdown_blocks.py` (`OCCSnapshot`), `src/graph/page_write_lock.py` (`fcntl.flock`) |
| Mutators only via MCP/CLI graph tools | `graph_dispatch.py` — `mutate_graph`, `ingest_document`, etc. |
| Safe-Sync documented | `SYSTEM_PROMPT.md` § Safe-Sync, `docs/ARCHITECTURE.md`, `docs/openspec/llm-os-instructions.md`, `README.md` |

## Open (v2.0)

| Task | Notes |
|------|-------|
| Logseq DB write bridge | Route writes through official CLI/API (`qmd`) — **never** direct Logseq internal SQLite |
| Write module abstraction | Part of `DatabaseRepository` in #17 |

### Zero-Interference principle

Logseq remains single source of truth. Matryca never mutates Logseq app-internal stores behind the scenes.

### Related

Parent epic: #20
