# LLM OS instructions — two-tier agent contract

**Artifacts:** [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) (Tier-2 cognitive law), [`llms.txt`](../../llms.txt) / [`.well-known/llms.txt`](../../.well-known/llms.txt) (distribution pointer), optional `matryca-l1/llm-os-rules.md` (operator overlay)

Matryca Plumber implements a **dual-LLM** stack:

| Tier | Runtime | Role |
|------|---------|------|
| **Tier 1 — Gardener** | `MaintenanceDaemon` Phase 1 | Catalog harvest → `master_catalog.json` + `[[Matryca Master Index]]` (OCC compile; graceful skip on drift) |
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
- **WRITE (v1.9.5 / Logseq OG):** `mutate_graph`, `refactor_blocks`, `ingest_document`, `store_fact` on `.md` with OCC.
- **WRITE (future Logseq DB):** official CLI/API only (e.g. `qmd`) — never native DB mutation.

---

## Maintainer checklist

When changing agent contracts:

1. Update **`SYSTEM_PROMPT.md`** (full law) and **`llms.txt`** + **`.well-known/llms.txt`** (byte-identical pointer) in the same PR.
2. Sync MCP docstrings in [`src/agent/mcp_server.py`](../../src/agent/mcp_server.py) (`read_graph_data`, `search_graph`).
3. Cross-check [`agent-onboarding.md`](agent-onboarding.md) and [`agent-dx.md`](agent-dx.md) if CLI discriminators change.
4. Run `tests/test_bootstrap_status.py` and `tests/test_mcp_server.py`.

### v2.0 SQLite Shadow DB migration trigger

When Shadow DB SQLite + FTS5 + recursive CTEs ship:

1. Update `SYSTEM_PROMPT.md` § "LLM OS" — replace JSON catalog / BM25 wording with Shadow DB + FTS5 paths.
2. Update Tier-1 Gardener embedded prompts (`semantic_lint_prompts.py`, harvest map-reduce).
3. Document CONTRIBUTING carve-out: Matryca Shadow DB is a daemon cache — not Logseq native storage.
4. Keep `[[Matryca Master Index]]` as the human-readable hub page.

---

## Related reading

- [`l1-l2-routing.md`](l1-l2-routing.md) — L1 memory vs L2 graph
- [`agent-onboarding.md`](agent-onboarding.md) — `llms.txt` distribution contract
- [`llm-performance.md`](llm-performance.md) — Phase 1 memory teardown, catalog unload
