# Biological memory layer — OpenSpec (planned v2.0)

**Status:** planned — algorithms partially scaffolded in [`src/memory/`](../../src/memory/); persistence in [`src/shadow/schema.py`](../../src/shadow/schema.py) memory tables  
**Parent epic:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Maintainer roadmap:** [`docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md)  
**Preparation index:** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](../roadmaps/ROADMAP_V2_PREPARATION.md) § Phase 4

Nacre-inspired decay, recall, and consolidation **inside** Matryca's Logseq-native stack — not a replacement for outliner blocks or OCC writes.

---

## Environment variables (planned)

| Variable | Default (planned) | Role |
|----------|-------------------|------|
| `MATRYCA_MEMORY_GRAPH_ENABLED` | `false` | Opt-in alpha — memory graph read/write in `shadow.sqlite` |
| `MATRYCA_SHADOW_DB_ENABLED` | `false` | **Shipped in v2.0.0-alpha** — prerequisite for memory graph persistence; enables Shadow DB read cache (FTS5/CTE) when healthy |

When implemented, document in [`.env.example`](../../.env.example) under **Advanced / high impact** per [`07-env-example.mdc`](../../.cursor/rules/07-env-example.mdc).

---

## MCP / CLI surface (planned)

| Today (v1.12) | v2 target |
|---------------|-----------|
| `search_graph(method=bm25\|semantic\|…)` | `bm25` prefers shadow FTS5 when `MATRYCA_SHADOW_DB_ENABLED=true` and health is `ready` (**shipped v2.0.0-alpha**); add `method=recall` in Phase 4 |
| `store_fact` | Episodic / procedural memory nodes (extends identity plane) |
| — | `nacre_forget` / feedback analogues — TBD in Phase 4 issues |

Contract changes ship with semver **v2.0.0-alpha.1** minimum; update [`llms.txt`](../../llms.txt) in the same PR.

---

## Safe-Sync

- Memory nodes and edges live in **daemon-owned `shadow.sqlite`** — not in Logseq's internal DB.
- Graph content mutations remain **Markdown + OCC** for Logseq OG ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) partial).
- Logseq DB vault writes: official CLI/API only — never native SQLite mutation.

---

## Implementation phases

See [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md):

1. **Fase A** — decay + schema tables (`memory_nodes`, `memory_edges`, …)
2. **Fase B** — `search_graph(method=recall)` + consolidation idle batch
3. **Fase C** — MCP memory-native tools

**Shipped scaffold:** `src/memory/decay.py` (decay formulas + tests).

---

## Verification (when wired)

```bash
uv run pytest tests/test_memory_decay.py tests/test_shadow_schema.py -q
make check
```
