# Biological memory layer — OpenSpec (planned v2.1+)

**Status:** planned for v2.1+ — algorithms partially scaffolded in [`src/memory/`](../../src/memory/); schema-only tables exist in [`src/shadow/schema.py`](../../src/shadow/schema.py), but no memory read/write path is shipped

**Historical architecture context:** [#20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

**Active delivery tracker:** [#178 — Biological memory + Logseq DB Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/178)

**Maintainer roadmap:** [`docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md)  
**Preparation index:** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](../roadmaps/ROADMAP_V2_PREPARATION.md) § Phase 4

Nacre-inspired decay, recall, and consolidation **inside** Matryca's Logseq-native stack — not a replacement for outliner blocks or OCC writes.

---

## Future feature gate

| Variable | Contract status | Role |
|----------|-----------------|------|
| `MATRYCA_MEMORY_GRAPH_ENABLED` | Not yet a public configuration contract | Future feature gate for memory graph reads and writes in `shadow.sqlite`; its default and rollout policy require a separately qualified v2.1+ design slice |

When implemented, document the complete contract in [`.env.example`](../../.env.example)
under **Advanced / high impact** per
[`07-env-example.mdc`](../../.cursor/rules/07-env-example.mdc). Current Shadow DB
behavior and defaults remain owned by the
[v2 operator contract](../knowledge/architecture/shadow-db.md).

---

## MCP / CLI surface (planned)

| Existing surface | Planned memory extension |
|------------------|--------------------------|
| `search_graph(method=bm25\|semantic\|…)` | Add `method=recall` in the v2.1+ Phase 4 work |
| `store_fact` | Episodic / procedural memory nodes (extends identity plane) |
| — | `nacre_forget` / feedback analogues — TBD in Phase 4 issues |

The target version and rollout policy belong to the separately qualified v2.1+
implementation slice. Update [`llms.txt`](../../llms.txt) in the same PR only if
that slice changes the external agent contract.

---

## Safe-Sync

- Memory nodes and edges live in **daemon-owned `shadow.sqlite`** — not in Logseq's internal DB.
- Graph content mutations remain **Markdown + OCC** for Logseq OG ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) partial).
- Logseq DB vault writes: official CLI/API only — never native SQLite mutation.

---

## Implementation phases

See [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md):

1. **Phase A** — decay + schema tables (`memory_nodes`, `memory_edges`, …)
2. **Phase B** — `search_graph(method=recall)` + consolidation idle batch
3. **Phase C** — MCP memory-native tools

**Shipped scaffold:** `src/memory/decay.py` (decay formulas + tests).

---

## Verification (when wired)

```bash
uv run pytest tests/test_memory_decay.py tests/test_shadow_schema.py -q
make check
```
