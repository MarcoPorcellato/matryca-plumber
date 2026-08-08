# LLM OS instructions — two-tier agent contract

**Artifacts:** [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) (Tier-2 cognitive law), [`llms.txt`](../../llms.txt) / [`.well-known/llms.txt`](../../.well-known/llms.txt) (distribution pointer), optional `matryca-l1/llm-os-rules.md` (operator overlay)

Matryca Plumber implements a **dual-LLM** stack:

| Tier | Runtime | Role |
|------|---------|------|
| **Tier 1 — Gardener** | `MaintenanceDaemon` Phase 1 | Catalog harvest → `master_catalog.json` + `[[Matryca Master Index]]` |
| **Tier 2 — Cognitive Agent** | MCP / CLI agents | User-facing reads/writes via `graph_dispatch` |

Repo **L1 memory** (`matryca-l1/*.md`) is session deploy rules — not the Gardener.

---

## Master Index Soft Gate (Human-in-the-Loop)

Tier-2 agents **must not** blind-search the vault without checking index availability.

**Session open sequence:**

1. `read_graph_data` / `memory`
2. `read_graph_data` / `bootstrap_status`
3. `read_graph_data` / `page` / `Matryca Master Index`

**When `soft_gate_active` is true:** pause and present three options (Local Daemon / Blind Search / Cloud Indexing). Wait for explicit authorization before B or C.

Full prose: `SYSTEM_PROMPT.md` § "LLM OS".

---

## `bootstrap_status` read target

| Field | Meaning |
|-------|---------|
| `bootstrap_complete` | Effective green gate (catalog + daemon checkpoint) |
| `soft_gate_active` | Agent should pause and offer Soft Gate options |
| `phase1_in_progress` | `bootstrap_scanned < bootstrap_total` |
| `master_index_present` | `pages/Matryca Master Index.md` exists |
| `catalog_complete` | `is_bootstrap_catalog_complete()` |
| `catalog_stale` | Daemon marked complete but on-disk catalog drifted |

**Module:** [`src/graph/bootstrap_status.py`](../../src/graph/bootstrap_status.py)

**CLI:**

```bash
uvx matryca-plumber --json read bootstrap_status
```

---

## Safe-Sync

- **READ:** `pages/` + `journals/` via Matryca tools only. Never Logseq app internal DB.
- **WRITE (v1.9.5 / Logseq OG):** `mutate_graph`, `refactor_blocks`, `ingest_document`, `import_tana`, `store_fact` on `.md` with OCC. Default `dry_run: true` on mutators and **`import_tana`**.
- **WRITE (future Logseq DB):** official CLI/API only (e.g. `qmd`) — never native DB mutation.

---

## Maintainer checklist

When changing agent contracts:

1. Edit the source fragments under [`agent/`](agent/) and regenerate
   **`SYSTEM_PROMPT.md`** with `make build-system-prompt`; never edit the generated
   output directly.
2. Update **`llms.txt`** + **`.well-known/llms.txt`** together only when the external
   agent contract changes; the two files must remain byte-identical.
3. Sync MCP docstrings in [`src/agent/mcp_server.py`](../../src/agent/mcp_server.py)
   only when the MCP tool contract changes.
4. Cross-check [`agent-onboarding.md`](agent-onboarding.md) and
   [`agent-dx.md`](agent-dx.md) if CLI discriminators change.
5. Run `make check-system-prompt`, `make agents-check`, and the focused contract tests.

### Shadow DB post-migration ownership

Shadow DB SQLite, FTS5, and recursive CTE reads have shipped as a derived read cache.
They do not replace the Tier-1 Gardener or the human-readable Master Index.

1. Keep current activation, storage, health, and fallback guidance in the
   [canonical Shadow operator contract](../knowledge/architecture/shadow-db.md).
2. Change the assembled Tier-2 law only through [`agent/`](agent/) fragments and the
   prompt builder.
3. Change Tier-1 Gardener prompts only when Gardener behavior changes, not when Shadow
   operator defaults or release status changes.
4. Keep `[[Matryca Master Index]]` as the human-readable hub page.

---

## Related reading

- [`l1-l2-routing.md`](l1-l2-routing.md) — L1 memory vs L2 graph
- [`agent-onboarding.md`](agent-onboarding.md) — `llms.txt` distribution contract
- [`llm-performance.md`](llm-performance.md) — Phase 1 memory teardown, catalog unload
