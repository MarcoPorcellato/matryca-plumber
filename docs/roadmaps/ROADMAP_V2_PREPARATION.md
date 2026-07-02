# v2.0 Preparation — Visitor & Maintainer Guide

**North star:** [Epic #20 — v2.0.0 Shadow DB & Safe-Sync](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Milestone:** [v2.0.0 — Shadow DB & Safe-Sync Architecture](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3)  
**RFC:** [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Matryca Plumber **v2.0.0** adds a daemon-owned **Shadow DB** (`shadow.sqlite`) for fast hierarchical reads (FTS5 + recursive CTEs), a **`GraphRepository`** port for coexistent Markdown and Logseq DB backends, and **Safe-Sync** write rules. **Logseq Markdown on disk remains the system of record** — shadow is a read cache, not a replacement vault.

**Start here if you are new:** this document → Epic #20 → phase tracking issues → slice PRs.

---

## Where we are today (v1.12)

| Layer | v1.12 shipped | v2 scaffold (in tree) | Not wired yet |
|-------|-----------------|------------------------|---------------|
| **DDL** | — | [`src/shadow/schema.py`](../../src/shadow/schema.py) + [`tests/test_shadow_schema.py`](../../tests/test_shadow_schema.py) | sync, FTS query helpers |
| **Memory algorithms** | — | [`src/memory/decay.py`](../../src/memory/decay.py) | recall, consolidate, MCP `recall` |
| **Repository port** | — | — | `GraphReadPort` / `MarkdownGraphRepository` |
| **Read path** | `master_catalog.json` + in-memory BM25 | — | shadow routing |
| **Write path (OG)** | OCC + `.md` + `page_rmw_lock` | — | — (done) |
| **Write path (Logseq DB)** | — | — | official CLI/API bridge ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)) |

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
| **2** | Shadow incremental sync | `open_shadow_db`; `post_write` upsert `pages`/`blocks`; integration tests on `tmp_path` graph | [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) · Phase 2 issue |
| **3** | Read routing (alpha) | `MATRYCA_SHADOW_DB_ENABLED=false` default; FTS5/CTE behind flag; BM25/AST fallback when lag or disabled | Phase 3 issue · slices under #24 |
| **4** | Memory + Logseq DB Safe-Sync | `MATRYCA_MEMORY_GRAPH_ENABLED`; `search_graph(method=recall)`; Logseq DB write via official CLI only | [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) · [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) · Phase 4 issue |

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

- Sync listens on [`post_write`](../../src/graph/post_write.py) / file watcher — **never** writes to `pages/*.md` from shadow.
- Path: `<LOGSEQ_GRAPH_PATH>/.matryca_semantic_cache/shadow.sqlite` (see schema).

**Verify:** `uv run pytest tests/test_shadow_schema.py tests/test_shadow_sync.py -q` (sync tests land with slice).

### Phase 3 — Alpha read routing

| Surface | v1 default | v2-alpha (`MATRYCA_SHADOW_DB_ENABLED=true`) |
|---------|------------|---------------------------------------------|
| `search_graph(bm25)` | generational BM25 | FTS5 shadow; fallback if stale |
| `read_graph_data(subtree)` | parser + AST | recursive CTE on `blocks` |
| `read_graph_data(page)` | `read_graph_file_text` | unchanged (source of truth) |

Sovereign UI: shadow sync lag / last full sync (no `matryca doctor` — see `llms.txt` §2.3).

### Phase 4 — Biological memory + Safe-Sync DB

- Memory tables in schema — [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](ROADMAP_V2_BIOLOGICAL_MEMORY.md).
- `search_graph(method=recall)` — hybrid recall (semantic + graph walk + recency).
- Logseq DB writes: **official CLI/API only** — never mutate Logseq internal SQLite ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)).

---

## Semver rollout

| Track | Operator impact | Agent / MCP impact |
|-------|-----------------|-------------------|
| **v2.0.0-alpha** | Opt-in `MATRYCA_SHADOW_DB_ENABLED` | BM25 remains default; shadow experimental |
| **v2.0.0-rc** | Shadow health in UI | MCP read traffic prefers shadow |
| **v2.0.0-stable** | Deprecation notice for in-memory BM25 default | `llms.txt` + `SYSTEM_PROMPT.md` migration per [`llm-os-instructions.md`](../openspec/llm-os-instructions.md) § v2.0 trigger |

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
- Duplicate tracking issues for #17, #24, #25 — extend them or link slice issues underneath.

---

## Related documentation

| Document | Role |
|----------|------|
| [`ROADMAP.md`](../../ROADMAP.md) | Timeline north star |
| [`docs/CLEAN_CODE_ARCHITECTURE.md`](../CLEAN_CODE_ARCHITECTURE.md) | v1 boundaries; v2 deferred items |
| [`docs/PROMPT_ARCHITECTURE.md`](../PROMPT_ARCHITECTURE.md) | semver 2.0 reserved for Shadow DB |
| [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) | Engineering contract + layer gaps |
