# Clean Architecture Audit — Triage (2026-06)

Third external audit (simulated Staff Engineer review against hexagonal / ports-and-adapters patterns). Cross-reference with [Expert Audit triage](EXPERT_AUDIT_TRIAGE_2026-06.md), [Repomix triage](REPOmix_AUDIT_TRIAGE_2026-06.md), and GitHub [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142).

**Status:** triaged 2026-06-24 · verified against current `src/` and tests.

---

## Executive scorecard

| Verdict | Count | Meaning |
|---------|-------|---------|
| Already fixed / by design | 3 | No new issue; document as closed |
| Already tracked | 4 | Existing issue/openspec; extend, don't duplicate |
| Audit error / obsolete | 3 | Claim predates shipped code |
| Partial / refinement | 2 | Doc note or optional follow-up issue |
| New issues filed | 2 | [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153), [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) |

**No new P1 bugs.** The proposed `domain/ports.py` + `PageRepository` SHA-256 CAS refactor maps to v2 [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) / Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) — not an immediate v1 split.

---

## Finding matrix

### P1 — Critical

| # | Audit finding | Code reality | Backlog | Action |
|---|---------------|--------------|---------|--------|
| 1 | `page_rmw_lock` is pessimistic locking masquerading as OCC; mtime CAS insufficient; lock leak on exception | **Two-layer model is intentional** — flock serializes RMW; `st_mtime` detects lost updates ([`ARCHITECTURE.md`](../ARCHITECTURE.md#optimistic-concurrency-control-occ)). `atomic_write_bytes` already does temp + `fsync` + `os.replace`. Lock uses `try/finally` + context managers — **no leak** ([`page_write_lock.py`](../../src/graph/page_write_lock.py)). | #40 shipped; Repomix P1.3 rejected | **Reframed** — not a naming bug. **Partial:** page OCC uses `st_mtime` float; catalog/bootstrap use `st_mtime_ns` — [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153). Content-hash CAS → comment on #17 |
| 2 | Tana `json.load()` OOM | **`ijson` streaming shipped** — [`load.py`](../../src/agent/importers/tana/load.py) forbids full DOM. Production path [`tana_import.py`](../../src/agent/tana_import.py) uses `TanaWorkspaceGraph.from_export` (single pass). | [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) | **Audit error** on parse. **Partial:** `StreamingGraphBuilder` still retains full `NodeDump` per id — [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) |

**Call-graph note:** `page_rmw_lock` is a hub symbol (~26 direct upstream callers): daemon Phase 2, `graph_dispatch`, Tana write, hub compile, cognitive modules. Central by design — not evidence of a concurrency violation.

---

### P2 — Structural / debt

| # | Audit finding | Code reality | Backlog | Action |
|---|---------------|--------------|---------|--------|
| 3 | MCP schemas coupled to Logseq AST; need ACL at transport boundary | [`outline_models.py`](../../src/agent/outline_models.py) — transport DTOs. [`mcp_server.py`](../../src/agent/mcp_server.py) thin-routes to `graph_dispatch`. Handler registry shipped ([#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)); write runtime remains in `graph_dispatch.py`. | ~~#59~~ closed, [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) closed, [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) | **Tracked** — no MCP-specific ACL issue |
| 4 | BM25 generational cache corrupt on partial failure; need SQLite transactional outbox | [`generational_cache.py`](../../src/graph/generational_cache.py) — **in-process** mtime-signature cache, not a persistent BM25 state file. Vector persistence [`semantic/store.py`](../../src/semantic/store.py) `apply_page_block_vector_updates`: streaming merge → `.json.tmp` → `replace` under `cross_process_json_flock`; errors unlink tmp, original intact. | [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) fixed; [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) / [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) for store v2 | **Rejected** — misunderstood module (Repomix P3.3) |

---

### P3 — Minor / refactor

| # | Audit finding | Code reality | Backlog | Action |
|---|---------------|--------------|---------|--------|
| 5 | Config parsing side-effects at import time; need DI `Settings` at composition root | [`plumber_config.py`](../../src/agent/plumber_config.py) — `PlumberLintConfig` + `load_plumber_lint_config_from_environ(env)` testable. Some modules still read `os.environ` at call time (e.g. `generational_cache`). Invalid int warnings — **fixed** [#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152). | [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57), [#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142) | **Partially addressed** — no urgent `domain/` Settings injection |
| 6 | Lock granularity — need `PageId` value object; `page/Journal` vs `journal.md` races | `normalize_page_lock_key` → resolved absolute path. `graph_safe_page_path` normalizes `pages/`, `.md`, `page_title_to_filename`. Case fold via `resolve_existing_page_title` at read time. | — | **Rejected as regression** — doc-only edge case on case-sensitive FS |

---

## Rejected claims (do not re-file)

| Claim | Why rejected |
|-------|----------------|
| OCC lock leak on exception | `try/finally` + flock context managers (Repomix P1.3) |
| Tana uses `json.load()` | `ijson` in `load.py` since v1.11 |
| BM25 cache needs SQLite outbox | In-process mtime cache; vectors use atomic tmp+replace | **Claude 2026-06-24:** separate bug — build then `sig_after` pairs stale corpus with fresh signature → [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) |
| MCP lacks transport isolation | DTO layer + handler registry shipped; v2 port #17 |
| Immediate `domain/ports.py` split | Aspirational v2 — ROADMAP + #17 |

---

| Optional follow-up issues | Local body | GitHub | Priority |
|------------|-------|--------|----------|
| OCC `st_mtime_ns` parity | [`153-occ-mtime-ns-parity.md`](issue-bodies/153-occ-mtime-ns-parity.md) | [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) | P3 |
| Tana slim `NodeDump` payloads | [`154-tana-slim-nodedump-payloads.md`](issue-bodies/154-tana-slim-nodedump-payloads.md) | [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) | P2 (extends #135) |

---

## Cross-audit overlap

| Clean Arch theme | Existing tracking |
|------------------|-------------------|
| Tana memory | #135 (partial), #139 (v2 idempotency) |
| Hexagonal / repositories | #17, #20, Discussion #19 |
| `graph_dispatch` coupling | ~~#59~~ shipped, #133 (fixed), #134 (fixed) |
| Vector / RAG persistence | #51, #24 |
| Env / config DI | #57, #142 (fixed) |

---

## Maintainer notes

- Audit was **simulated** without cloning — several P1 claims match pre-v1.11 documentation snapshots, not current code.
- `page_rmw_lock` + OCC mtime is the **documented v1 contract**; SHA-256 content CAS belongs in `MarkdownRepository` ([#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17)), not a parallel `domain/ports.py` in v1.
- Tana: streaming parse ✓, single-pass `from_export` ✓, full `NodeDump` retention = remaining #135 work.
