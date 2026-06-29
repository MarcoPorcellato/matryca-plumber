## Problem Description

Logseq is transitioning from flat Markdown files to a structured SQLite database (Logseq DB). Matryca Plumber is still wired to read and mutate raw `.md` strings via file-system I/O, mmap lookups, and AST serialization (`src/graph/markdown_blocks.py`, `src/graph/page_write_lock.py`).

We need both backends concurrently without breaking MCP/CLI contracts for external agents.

## Proposed Architectural Solution

Apply the **Repository Pattern** incrementally (Phase 1 of [`ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md)):

| Component | Role |
|-----------|------|
| `GraphReadPort` (`typing.Protocol`) | `search_blocks`, `read_subtree`, `resolve_entity` — read path first |
| `MarkdownGraphRepository` | Wraps current v1.12 `src/graph/*` + parser — **default adapter** |
| `ShadowGraphRepository` | Delegates reads to shadow when enabled (Phase 3) |
| `DatabaseRepository` | Logseq DB: read-only SQLite harvest; writes via Logseq Local HTTP API (Phase 4) |

Runtime selection (later): `MATRYCA_STORAGE_MODE=markdown|database` with folder auto-detection.

**Phase 1 slice order:**

1. Define `GraphReadPort` + `MarkdownGraphRepository` with parity tests.
2. Route one `graph_dispatch` read method through the port (e.g. `search_graph` bm25 or `read_subtree`).
3. Expand coverage method-by-method — no big-bang rewrite.

**Out of scope for first PR:** `DatabaseRepository`, SHA-256 content CAS (v2 content-hash → comment on this issue).

## Estimated Impact

**Alto** — structural milestone for v2; Phase 1 PRs must keep **zero operator-visible behavior change** when shadow flags are off.

## Files Involved

- New: `src/graph/ports/` or `src/domain/repository.py` (per slice PR)
- `src/agent/graph_dispatch.py` (thin delegate)
- `tests/test_graph_repository.py` (parity fixtures)

---
**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) · **Blocks:** [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) Shadow DB routing  
**SSOT:** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md) § Phase 1

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
