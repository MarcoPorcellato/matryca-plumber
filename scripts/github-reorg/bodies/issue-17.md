### Problem / motivation

Logseq is transitioning from flat Markdown files to a structured SQLite database (Logseq DB). Matryca Plumber is still wired to read and mutate raw `.md` strings via file-system I/O, mmap lookups, and AST serialization (`src/graph/markdown_io.py`, `src/graph/page_write_lock.py`).

We need both backends concurrently without breaking MCP/CLI contracts for external agents.

### Proposed solution

Apply the **Repository Pattern** to isolate cognitive/hygiene engines from storage:

| Component | Role |
|-----------|------|
| `GraphRepository` (protocol) | `get_block_by_uuid()`, `merge_tags()`, `write_page_properties()`, … |
| `MarkdownRepository` | Absorb current v1.9.x engine (mmap, `fcntl.flock`, OCC) |
| `DatabaseRepository` | Logseq DB: read-only SQLite for bootstrap harvest; writes via Logseq Local HTTP API |

Runtime selection: `MATRYCA_STORAGE_MODE=markdown|database` (with folder auto-detection).

**Baseline to refactor (v1.9.5):** inline I/O in `markdown_io.py`, `master_catalog.py`, `graph_dispatch.py` — no protocol yet.

### Paradigm alignment

- **Logseq OG:** graph content remains Markdown on disk; Matryca is the mutation plane.
- **Shadow DB (v2.0):** `shadow.sqlite` is a **daemon-owned read cache**, not a system of record — see Epic #20 and [`docs/openspec/llm-os-instructions.md`](docs/openspec/llm-os-instructions.md) § v2.0 migration trigger.
- **Block-shaped thinking:** outliner blocks, nesting, `id::` — not flat blobs.
- **Strict OCC:** Phase-1 `st_mtime_ns` snapshot + Phase-2 verify for all mutators.

### Sub-tasks

- [ ] Define `GraphRepository` protocol (`typing.Protocol`)
- [ ] Extract `MarkdownRepository` from current graph I/O
- [ ] Implement `DatabaseRepository` (HTTP API writes + read-only SQLite reads)
- [ ] Wire `MATRYCA_STORAGE_MODE` + auto-detection
- [ ] E2E tests with Logseq DB alpha/beta graphs

### Related

- Parent epic: #20
- Blocks: #24 (Shadow DB read path needs storage abstraction)
