# v2.0 Preparation — Visitor & Maintainer Guide

**North star:** [Epic #20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Milestone:** [v2.0.0 — Stable Shadow Read Path](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3)
**RFC:** [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Matryca Plumber **v2.0.0** adds a daemon-owned **Shadow DB** (`shadow.sqlite`) for fast hierarchical reads (FTS5 + recursive CTEs), a **`GraphRepository`** port for coexistent Markdown and Logseq DB backends, and **Safe-Sync** write rules. **Logseq Markdown on disk remains the system of record** — shadow is a read cache, not a replacement vault.

**Start here if you are new:** this document → Epic #20 → phase tracking issues → slice PRs.

---

## Where we are today (2026-07-22)

| Layer | Shipped | In tree (not fully operational) | Not wired yet |
|-------|---------|----------------------------------|---------------|
| **DDL** | [`src/shadow/schema.py`](../../src/shadow/schema.py) + tests | — | — |
| **Shadow sync** | `open_shadow_db`, per-page `sync_page_to_shadow`, post-write bridge, bootstrap/reconciliation ([#181](https://github.com/MarcoPorcellato/matryca-plumber/issues/181)–[#182](https://github.com/MarcoPorcellato/matryca-plumber/issues/182), [#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248)) | — | — |
| **Shadow query** | `search_blocks_fts` + FTS5 dispatch ([#183](https://github.com/MarcoPorcellato/matryca-plumber/issues/183), [#250](https://github.com/MarcoPorcellato/matryca-plumber/issues/250)) | — | — |
| **Memory algorithms** | — | [`src/memory/decay.py`](../../src/memory/decay.py) | recall, consolidate, MCP `recall` |
| **Repository port** | `GraphReadPort`, `MarkdownGraphRepository`, `ShadowGraphRepository`, subtree CTE routing ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17), [#253](https://github.com/MarcoPorcellato/matryca-plumber/issues/253), [#255](https://github.com/MarcoPorcellato/matryca-plumber/issues/255)) | — | — |
| **Read path** | Default: `master_catalog.json` + in-memory BM25; opt-in shadow FTS5/CTE when `MATRYCA_SHADOW_DB_ENABLED=true` ([#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177)) | — | beta.1 candidate remains default-off; default-on is not considered before RC |
| **Write path (OG)** | OCC + `.md` + `page_rmw_lock` | — | — |
| **Write path (Logseq DB)** | — | — | official CLI/API bridge ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)) |
| **Operator health** | Sovereign UI `/api/state.shadow_db` ([#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185)) | — | — |

Child roadmaps: [`ROADMAP_V2_SHADOW_DB.md`](ROADMAP_V2_SHADOW_DB.md) · [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md) · [`../openspec/biological-memory.md`](../openspec/biological-memory.md).

---

## Five preparation phases

```mermaid
flowchart LR
  P0[Phase0 v1 prereqs]
  P1[Phase1 GraphRepository]
  P2[Phase2 shadow sync]
  P3[Phase3 read routing]
  P4[Phase4 memory SafeSync]

  P0 --> P1 --> P2 --> P3 --> P4
```

| Phase | Name | Definition of done | GitHub |
|-------|------|-------------------|--------|
| **0** | v1.9.12 prerequisites | Daemon/dispatch modular enough for shadow duty cycle; env_parse DRY; documented blockers closed or explicitly tracked | Phase 0 ([#174](https://github.com/MarcoPorcellato/matryca-plumber/issues/174)) **done** · [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) **done** · [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) **done** |
| **1** | GraphRepository ports | `GraphReadPort` + `MarkdownGraphRepository`; `graph_dispatch` delegates at least one read method; parity tests; **default behavior unchanged** | [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Phase 1 ([#175](https://github.com/MarcoPorcellato/matryca-plumber/issues/175)) **done** (subtree + port) |
| **2** | Shadow incremental sync | Bootstrap, reconciliation, runtime gating ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248)) | [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · **done** (closed at `v2.0.0-alpha`) |
| **3** | Read routing (alpha) | `MATRYCA_SHADOW_DB_ENABLED=false` default; FTS5/CTE behind flag; BM25/AST fallback when lag or disabled; Sovereign UI health row | [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177) · **done** |
| **4** | Memory + Logseq DB Safe-Sync (`v2.1+`) | `MATRYCA_MEMORY_GRAPH_ENABLED`; `search_graph(method=recall)`; Logseq DB write via official CLI only | [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) · [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) · Phase 4 issue |

### Phase 0 — v1 prerequisites (blockers)

| Item | Why it blocks v2 | Tracking |
|------|------------------|----------|
| `maintenance_daemon` SRP | Shadow sync hooks into duty cycle | [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) **closed** |
| `graph_dispatch` handler registry | Read routing needs thin router | [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) **closed** — all five mega-tools split into `dispatch_*_handlers.py` |
| Vector RAM at scale | Converges into shadow shard plan | [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) partial |
| Config DI (`env_parse`) | Shadow flags injectable | [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) · Tier F [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168)–[#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173) — **deferred** (not Phase 0–1 scope) |

**Not v2 prep:** good-first observability slices remain v1.9.12 — see [`good_first_issues_blueprints.md`](../../good_first_issues_blueprints.md).

### Phase 1 — GraphRepository (no behavior change)

**Status:** shipped (2026-07-01) — `GraphReadPort`, `MarkdownGraphRepository`, subtree delegate via port; parity tests in `tests/test_graph_repository.py`.

```text
  graph_dispatch.read_*  →  GraphReadPort  →  MarkdownGraphRepository  →  src/graph/* (today)
```

- Introduce `typing.Protocol` for read operations (search, subtree, resolve).
- Single adapter wrapping current `graph/*` + parser paths.
- **Do not** add `domain/ports.py` god-module — follow [`CLEAN_ARCH_AUDIT_TRIAGE`](../quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md): incremental [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17).

**Verify:** `make check`; `tests/test_graph_repository.py` parity fixtures.

### Phase 2 — Shadow sync (read-only on source)

**Status:** shipped ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248), #181–#183).

- Sync listens on [`post_write`](../../src/graph/post_write.py) / file watcher — **never** writes to `pages/*.md` from shadow.
- Path: `<LOGSEQ_GRAPH_PATH>/.matryca_semantic_cache/shadow.sqlite` (see schema).

**Verify:** `uv run pytest tests/test_shadow_schema.py tests/test_shadow_sync.py -q` (sync tests land with slice).

### Phase 3 — Alpha read routing

**Status:** shipped ([#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177) — PR-A/B/C1/C2/D on `main`).

| Surface | v1 default | v2-alpha (`MATRYCA_SHADOW_DB_ENABLED=true`) |
|---------|------------|---------------------------------------------|
| `search_graph(bm25)` | generational BM25 | FTS5 shadow; fallback if stale |
| `read_graph_data(subtree)` | parser + AST | recursive CTE on `blocks` |
| `read_graph_data(page)` | `read_graph_file_text` | unchanged (source of truth) |

Sovereign UI: `GET /api/state` → `shadow_db` row (`state`, `last_full_sync_at`, page counts, `lag_pages`, `last_sync_error`). No `matryca doctor` — see `llms.txt` §2.5–§2.6.

**Published hardening baseline:** [`v2.0.0-alpha.5`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha.5) closes tracker [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261): duplicate UUID diagnostics, writer coordination, health validation, FTS5, CTE, security, and performance probes are green. The locally prepared `v2.0.0-beta.1` / `2.0.0b1` candidate remains unreleased and retains the default-off flag, global fallback, and Markdown system of record.

**Verify:** `uv run pytest tests/test_shadow_fts_routing.py tests/test_shadow_read_port.py tests/test_shadow_state_api.py tests/test_shadow_bootstrap.py tests/test_ui_server.py -q`

### Phase 4 — Biological memory + Safe-Sync DB

- Memory tables in schema — [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md).
- `search_graph(method=recall)` — hybrid recall (semantic + graph walk + recency).
- Logseq DB writes: **official CLI/API only** — never mutate Logseq internal SQLite ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)).

---

## Semver rollout

| Track | Operator impact | Agent / MCP impact |
|-------|-----------------|-------------------|
| **v2.0.0-alpha.5** | Seven-axis hardening baseline | Pin `@2.0.0-alpha.5`; shadow remains opt-in | **published** 2026-07-19 |
| **v2.0.0-beta.1** | First public Shadow read-path beta | Default-off flag, Markdown system of record, fallback mandatory; Phase 4 excluded | **published** 2026-07-30 |
| **v2.0.0-rc.1** | Shadow health in UI; exact public-beta artifact re-qualified | MCP read traffic prefers shadow; explicit `false` remains the opt-out |
| **v2.0.0-stable** | RC observation complete; deprecation notice for in-memory BM25 default | `llms.txt` + `SYSTEM_PROMPT.md` migration per [`llm-os-instructions.md`](../openspec/llm-os-instructions.md) § v2.0 trigger |

**Beta decision record:** [`docs/quality/issue-bodies/v2-beta-readiness.md`](../quality/issue-bodies/v2-beta-readiness.md). Bounded-parse containment, the sanitized soak, installed-wheel upgrade/recovery, full CI, and final code audit all passed with the recorded evidence boundary. Re-qualification against the released source remains required before default-on.

**RC/stable decision record:** [`docs/quality/issue-bodies/v2-rc-stable-readiness.md`](../quality/issue-bodies/v2-rc-stable-readiness.md), tracked by [#343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343). `v2.0.0` is scoped to the stable Shadow read path. Phase 4 biological memory, Logseq DB Safe-Sync writes, content-aware Tana merge, and independent DX tracks move to `v2.1.0` or later.

**Exact-beta re-qualification:** the public `2.0.0b1` wheel passed its fresh
installed-wheel gate and entered a restart-resilient 72-hour soak on 2026-07-30.
The sanitized running record is
[`docs/quality/SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md`](../quality/SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md).
It does not close the RC gate until a terminal result is recorded.

---

## Safe-Sync contract (non-negotiable)

| Path | Rule |
|------|------|
| **READ** | Shadow DB syncs read-only from Markdown (Classic) or Markdown Mirror (Logseq DB) |
| **WRITE (Logseq OG)** | Append to `.md` + OCC — **shipped v1.9.5** |
| **WRITE (Logseq DB)** | Official CLI/API only — **v2 Phase 4** |

Full spec: [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) · [`../openspec/llm-os-instructions.md`](../openspec/llm-os-instructions.md).

---

## How to contribute to v2.0

1. Read this guide and [Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20).
2. Pick a **phase tracking issue** or a **slice issue** (label `v2-prep`, `v2-alpha`, `v2-memory`, or `v2-safesync`).
3. Comment on the issue before opening a PR; reference `Fixes #N` / `Refs #20`.
4. Run **`make check`** — mandatory merge bar.
5. For architecture debate, use [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19).

**Maintainer blueprints:** [`v2_preparation_blueprints.md`](../../v2_preparation_blueprints.md).

**GitHub filters:**

- [All v2.0 labeled issues](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3Av2.0)
- [Milestone v2.0.0](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3)

---

## What NOT to do

- Use SQLite as **system of record** for graph content (violates Phase 4 / [`CONTRIBUTING.md`](../../CONTRIBUTING.md) philosophy).
- Rewrite entire `graph_dispatch` or `maintenance_daemon` in one PR — use slices ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58), [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)).
- Enable shadow reads without BM25/AST **fallback** until v2.0.0-rc.
- Treat `v2.0.0-beta.1` as released, enable Shadow by default, or include Phase 4 memory/Safe-Sync work before its explicit readiness gates are complete.
- Duplicate tracking issues for #17, #24, #25 — extend them or link slice issues underneath.

---

## Related documentation

| Document | Role |
|----------|------|
| [`ROADMAP.md`](../../ROADMAP.md) | Timeline north star |
| [`docs/CLEAN_CODE_ARCHITECTURE.md`](../CLEAN_CODE_ARCHITECTURE.md) | v1 boundaries; v2 deferred items |
| [`docs/PROMPT_ARCHITECTURE.md`](../PROMPT_ARCHITECTURE.md) | semver 2.0 reserved for Shadow DB |
| [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | Engineering contract + layer gaps |
