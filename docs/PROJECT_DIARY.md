# Project diary — technical lifecycle log

This document records **architecture decisions**, **phase milestones**, and **real-world defects crushed** during the evolution of **Matryca Plumber** (`matryca-plumber` on PyPI; historical published beta **v2.0.0-beta.1**; Gate-A-qualified release candidate **v2.0.0-rc.1**).

The project began as an MCP-first bridge so external LLM hosts could mutate Logseq Markdown safely. Phases **12–16** completed the pivot to a **fully autonomous background agent** — `MaintenanceDaemon`, Sovereign UI, native AST I/O, OCC, and Zero-Trust cockpit APIs — where **FastMCP is an optional auxiliary surface**, not the product’s center of gravity.

For the engineering contract (modules, diagrams, concurrency), see [`ARCHITECTURE.md`](ARCHITECTURE.md). For **Clean Architecture** on prompts, see [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md). For operator setup, see [`../README.md`](../README.md).

Entries are chronological (**newest first** within each major release block). When a decision is superseded, add a new entry rather than rewriting history.

---

## [2026-08-03] v2.0.0-rc.1 — Gate A qualification

1. **Default-on read contract** — healthy Shadow FTS/subtree reads use a per-user external cache by default; explicit `MATRYCA_SHADOW_DB_ENABLED=false` preserves the Markdown/BM25 opt-out.
2. **Strict Read Only compatibility** — observer-mode bootstrap and watcher reconciliation may update only the validated external cache; deterministic graph-tree tests and exact-wheel probes preserve Markdown and graph-local inventory.
3. **Promotion boundary** — Gate A is complete after exact-beta soak, upgrade/rollback, supported-platform CI, installed-wheel recovery, operator-contract, and defect-disposition evidence. Publishing the RC starts Gate B; it does not authorize stable `v2.0.0`.

---

## [2026-07-22] v2.0.0-beta.1 — local candidate preparation (not published)

1. **Candidate boundary** — prepare source package version `2.0.0-beta.1` / wheel version `2.0.0b1` for the opt-in Shadow DB read path only. The flag remains default-off; Logseq Markdown remains authoritative; every non-ready Shadow state retains Markdown/BM25 fallback.
2. **Evidence boundary** — the installed-wheel upgrade/recovery, sanitized real-vault soak, and final code audit gates remain pending in [`quality/issue-bodies/v2-beta-readiness.md`](quality/issue-bodies/v2-beta-readiness.md). This candidate must not be treated as a release, enabled by default, tagged, or published.
3. **Distribution** — no tag or PyPI publication is associated with this entry. The current published baseline remains `v2.0.0-alpha.5` / `2.0.0a5`.

---

## [2026-07-19] v2.0.0-alpha.5 — Shadow hardening campaign close

### Context

Hardening tracker [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) Axes 5–7 completed after alpha.4. Confirmed P2s: CTE `max_depth≤1` truncation status ([#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289)) and state API absolute-path leak in `last_sync_error` ([#293](https://github.com/MarcoPorcellato/matryca-plumber/issues/293)).

### Decisions

1. **Surgical fixes** — #291 (subtree truncation status) and #294 (path redaction) landed separately from audit PRs #290/#292/#295.
2. **Campaign close** — Axes 1–7 green; no open P0/P1; A1-BOOT-02 remains the only accepted P2 without code change.
3. **Distribution** — tag `v2.0.0-alpha.5`; PyPI `2.0.0a5`; supersedes `v2.0.0-alpha.4` / `2.0.0a4` for new installs. **Not an RC** — post-publish soak before beta/RC (Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)).

### Outcome

| Surface | Note |
|---------|------|
| **pre-release 2.0.0-alpha.5** | Hardening close + #114/#289/#293; no schema migration; default-off flag unchanged |

---

## [2026-07-19] v2.0.0-alpha.4 — Shadow FTS query length bound

### Shipped

1. **FTS query length bound (#279 / #286)** — keywords over **512 Unicode characters** (post-`strip`) rejected before FTS preparation or SQLite `MATCH`; validation in acyclic `fts_validation.py` leaf module.
2. **Axis 4 FTS5 gate complete** — **52 pass, 0 xfail**; A4-QUERY-07 probe corrected (#278 / #287 — invalid `cafe`→`caffè` expectation).
3. **Distribution** — tag `v2.0.0-alpha.4`; PyPI `2.0.0a4`; supersedes `v2.0.0-alpha.3` / `2.0.0a3` for new installs. **Not an RC** — Axes 5–7 open on [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261).

### Semver

| Milestone | Scope |
|-----------|--------|
| **pre-release 2.0.0-alpha.4** | FTS query bound; no schema migration; default-off flag unchanged |
| **pre-release 2.0.0-rc** | Blocked until [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) P0/P1 clear |

---

## [2026-07-19] v2.0.0-alpha.3 — Shadow FTS hyphenated query fix

### Shipped

1. **Hyphenated FTS (#277 / #282)** — natural compounds like `state-of-the-art` quoted before FTS5 `MATCH`; no spurious generational fallback while shadow is `ready`.
2. **Axis 4 FTS5 audit (#280)** — 30 probes; initial snapshot **27 pass + 3 xfail**; alpha.3 gate after #282 **28 pass + 2 xfail**; **#278** (diacritic fold) and **#279** (query length bound) remain open.
3. **Distribution** — tag `v2.0.0-alpha.3`; PyPI `2.0.0a3`; supersedes `v2.0.0-alpha.2` / `2.0.0a2` for new installs. **Not an RC** — Axes 5–7 open on [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261).

### Semver

| Milestone | Scope |
|-----------|--------|
| **pre-release 2.0.0-alpha.3** | FTS hyphen fix; no schema migration; default-off flag unchanged |
| **pre-release 2.0.0-rc** | Blocked until [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) P0/P1 clear |

---

## [2026-07-18] v2.0.0-alpha.2 — Shadow DB rename fix & routing audit

### Shipped

1. **Rename stale-owner (#272 / #274)** — incremental external rename reconciles stale shadow page rows in-transaction; Axis 2 **A2-WATCH-02** probe green.
2. **Axis 3 routing audit (#275)** — 19 probes (flag/health gating, FTS/subtree fallback, MCP/CLI parity); zero confirmed findings.
3. **Knowledge bundle (experimental)** — OKF-inspired pilots Phase 1–2 merged; `docs/ARCHITECTURE.md` remains SSOT ([#271](https://github.com/MarcoPorcellato/matryca-plumber/issues/271) observation gate).
4. **Distribution** — tag `v2.0.0-alpha.2`; PyPI `2.0.0a2`; supersedes `v2.0.0-alpha.1` / `2.0.0a1` for new installs. **Not an RC** — Axes 4–7 open on [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261).

### Semver

| Milestone | Scope |
|-----------|--------|
| **pre-release 2.0.0-alpha.2** | Rename fix + audit probes; no schema migration; default-off flag unchanged |
| **pre-release 2.0.0-rc** | Blocked until [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) P0/P1 clear |

---

## [2026-07-18] v2.0.0-alpha.1 — Shadow DB Axis 1 hardening

### Context

Hardening campaign [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) on the experimental Shadow DB read cache shipped in `v2.0.0-alpha`. Axis 1 concurrency and meta/pages consistency gaps were confirmed by audit probes ([#263](https://github.com/MarcoPorcellato/matryca-plumber/pull/263)) and fixed in surgical PRs.

### Shipped

1. **Cross-process writer coordination (#262)** — per-graph advisory `shadow.writer.flock` serializes rebuild, incremental sync, and delete; split flock timeouts (10s incremental / 120s rebuild) + clamped `PRAGMA busy_timeout`.
2. **Meta/pages health (#264)** — `resolve_shadow_health` and `/api/state` no longer report `ready` when `shadow_meta` page counts diverge from `pages` rows.
3. **Distribution** — tag `v2.0.0-alpha.1`; PyPI `2.0.0a1`; supersedes `v2.0.0-alpha` / `2.0.0a0` for new installs (`2.0.0a0` remains on PyPI).

### Semver

| Decision | Rationale |
|----------|-----------|
| **pre-release 2.0.0-alpha.1** | Axis 1 hardening only; no schema migration; default-off flag unchanged |

**Suite:** `make ci` green · Axis 1 concurrency suite **zero xfails**.

---

## [2026-07-18] v2.0.0-alpha — Shadow DB read path (opt-in)

### Context

Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) Phase 2–3 delivered a daemon-owned **`shadow.sqlite`** read cache with opt-in routing behind `MATRYCA_SHADOW_DB_ENABLED`. Logseq Markdown on disk remains the system of record; generational BM25 and parser subtree reads are unchanged when the flag is unset or shadow health is not `ready`.

### Shipped

1. **Shadow sync + bootstrap** — `open_shadow_db`, `sync_page_to_shadow`, full-graph `rebuild_shadow_from_graph`, watchdog reconciliation, runtime gating ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248), #181–#182).
2. **Read routing** — FTS5 BM25 + recursive CTE subtree via `ShadowGraphRepository` / `get_graph_read_port` with Markdown/BM25 fallback ([#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177), [#250](https://github.com/MarcoPorcellato/matryca-plumber/issues/250), [#253](https://github.com/MarcoPorcellato/matryca-plumber/issues/253), [#255](https://github.com/MarcoPorcellato/matryca-plumber/issues/255)).
3. **Operator health** — Sovereign UI `/api/state.shadow_db` row ([#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185)).
4. **Duplicate UUID diagnostics** — pre-insert guard with bounded `ShadowSyncError`; bootstrap persists `last_sync_error`; read paths fail safe to Markdown/BM25 ([#251](https://github.com/MarcoPorcellato/matryca-plumber/issues/251)).
5. **Distribution** — tag [`v2.0.0-alpha`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha); PyPI `2.0.0a0`; `llms.txt` §2.6.

### Semver

| Decision | Rationale |
|----------|-----------|
| **pre-release 2.0.0-alpha** | First operator-visible v2 read cache; default-off flag preserves v1.14.x agent behavior |

**Suite:** `make ci` green at tag (1117 passed, 2 skipped) · PyPI + vault smoke verified.

---

## [2026-07-16] Deep code audit remediation

### Context

A deep code audit (see [`AUDIT_REPORT_2026-07-16.md`](AUDIT_REPORT_2026-07-16.md)) surfaced 11 findings (F1–F11) spanning catalog write-safety bugs, a file-watcher gap, five deferred-import cycles, three god-modules, dead-symbol candidates, and a CI security gap. Findings were triaged by severity and fixed in two PRs.

### Shipped

1. **Catalog write-safety (F1–F7)** — [#211](https://github.com/MarcoPorcellato/matryca-plumber/pull/211), merged. Fixes the `remove()`→`upsert()` resurrection-deletion bug, stops treating a corrupt catalog as empty during merge (quarantine + warn instead), records `prune_missing_pages()` removals, handles `on_moved` in the file watcher, replaces per-file `threading.Timer` fan-out with a single-thread scheduler, narrows a `BaseException` catch, and caches the casefold index for `get_case_insensitive`.
2. **Leaf-module dependency direction (F8)** — [#216](https://github.com/MarcoPorcellato/matryca-plumber/pull/216), merged. Relocated 4 of 5 deferred-import cycles to their true lowest-layer home (`DaemonState`/`compute_phase2_progress_metrics`, `handle_lint_block_refs`, a new shared `canonicalize_llm_base_url()`, `resolve_existing_page_title`). The `tana/graph.py` ↔ `tana/load.py` cycle stays deferred — a test monkeypatches `load_mod.load_tana_nodes_by_id`, which pins the function to the `load` module.
3. **Not split now (F9)** — three god-module split issues opened ([#212](https://github.com/MarcoPorcellato/matryca-plumber/issues/212), [#213](https://github.com/MarcoPorcellato/matryca-plumber/issues/213), [#214](https://github.com/MarcoPorcellato/matryca-plumber/issues/214)) but deliberately not split this round.
4. **Dead-symbol candidates verified, none removed (F10)** — [#206](https://github.com/MarcoPorcellato/matryca-plumber/issues/206), closed ([#217](https://github.com/MarcoPorcellato/matryca-plumber/issues/217) closed as duplicate). Every named candidate traced back to a real caller (registry dispatch, backward-compat aliasing, a regex closure, or a re-export) — the audit's own no-outgoing-edge heuristic false-positived on all of them.
5. **PDG-enabled CI security gate not wired (F11)** — [#219](https://github.com/MarcoPorcellato/matryca-plumber/issues/219), tracked for a future release.
6. **Two undocumented import cycles found on re-check** — tracked in [#240](https://github.com/MarcoPorcellato/matryca-plumber/issues/240), out of scope for F8's original list.

```mermaid
flowchart LR
    F1_7["F1-F7\ncatalog write-safety"] -->|"#211 merged"| Fixed1["fixed"]
    F8["F8\n5 import cycles"] -->|"#216 merged, 4/5"| Fixed2["fixed"]
    F8 -->|"1 kept + 2 new found"| Tracked1["#240 tracked"]
    F9["F9\n3 god-modules"] -->|"issue-only"| Tracked2["#212-214 open"]
    F10["F10\ndead-symbol candidates"] -->|"all false-positive"| Closed1["#206 closed"]
    F11["F11\nPDG CI gate"] -->|"deferred"| Tracked3["#219 open"]
```

### Semver

| Decision | Rationale |
|----------|-----------|
| **minor 1.14.0** | Operator-visible catalog/watcher reliability + architecture hardening after audit F1–F8; no intentional MCP/CLI surface break |

**Suite:** ruff clean · mypy strict, no issues · targeted pytest (117 tests across touched modules) green.

---

## [2026-07-02] v1.13.1 — Logseq Matryca Parser 1.6.0 alignment

### Context

Plumber shipped **v1.13.0** on `logseq-matryca-parser` **1.4.0**. Parser **1.6.0** (PyPI 2026-07-02) consolidates **1.4.2** headless-write fixes (newline splice #72, X-Ray reload #60, SYNAPSE cyclic embed #65) and **1.6.0** Clean Architecture graph APIs. The mutation plane uses a custom OCC splice (`_headless_append_child`) that must mirror parser newline semantics independently of `append_child_to_node`.

### Shipped

1. **Dependency** — `logseq-matryca-parser>=1.6.0,<2.0.0` in `pyproject.toml` / `uv.lock`.
2. **`_headless_append_child`** — trailing-newline normalization + `tab_size_for_node` (parity with parser 1.4.2).
3. **`load_alias_registry`** — map `SessionAliasRegistryError` to existing corrupt-state `ValueError` contract.

### Semver

| Decision | Rationale |
|----------|-----------|
| **Patch 1.13.1** | Parser alignment + write robustness; no intentional MCP/CLI break |

**Suite:** 987 tests green · parser 1.6.0 locked · mypy strict · ruff clean.

---

## [2026-07-02] v1.13.0 — Daemon & dispatch modularization (v2 Phase 0–1)

### Context

Post–v1.12.x Clean Code guidance, two god modules blocked v2 preparation: `maintenance_daemon.py` (~3,300 lines) and `graph_dispatch.py` (~2,400 lines). Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) Phase 0–1 required SRP splits and a read boundary (`GraphReadPort`) before Shadow DB work.

### Shipped (stacked slices → `main`)

1. **`maintenance_daemon` SRP** — six `daemon_*` modules + ~1,280-line orchestrator with backward-compatible re-exports ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58)).
2. **`graph_dispatch` handler registry** — five `dispatch_*_handlers.py` slices; thin routers in `graph_dispatch.py` (~565 lines write runtime) ([#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)).
3. **`GraphReadPort`** — `src/graph/ports/read.py` protocol + `MarkdownGraphRepository`; subtree reads delegate through port ([#179](https://github.com/MarcoPorcellato/matryca-plumber/issues/179), [#180](https://github.com/MarcoPorcellato/matryca-plumber/issues/180)).
4. **Community onboarding** — README Community section, [`FIRST_CONTRIBUTION.md`](FIRST_CONTRIBUTION.md), CoC enforcement contact.
5. **Issue triage** — four-pass audit closure log [`quality/ISSUE_TRIAGE_2026-07-01.md`](quality/ISSUE_TRIAGE_2026-07-01.md).

### Clean Architecture decisions

| Decision | Rationale |
|----------|-----------|
| Re-exports from `maintenance_daemon` | Avoid breaking CLI/tests that import legacy symbols |
| Lazy import in `dispatch_mutate_handlers` | Break circular dependency with write helpers in `graph_dispatch` |
| `GraphReadPort` in `graph/ports/` not `agent/` | Dependency Rule — graph layer must not import agent |
| **Minor 1.13.0** | Large internal refactor; no intentional operator-facing CLI/MCP break |

**Verify:** `make ci` · `tests/test_graph_dispatch_*.py` · `tests/test_graph_repository.py` · daemon module tests.

**Docs:** [`CLEAN_CODE_ARCHITECTURE.md`](CLEAN_CODE_ARCHITECTURE.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md) · [`roadmaps/ROADMAP_V2_PREPARATION.md`](roadmaps/ROADMAP_V2_PREPARATION.md).

---

## [2026-06-24] v1.12.0 — Prompt Clean Architecture (plan v3)

### Context

Post–v1.11.2 graph boundary work, prompts still violated Uncle Bob’s **Dependency Rule**: inline system strings in `llm_client.py`, no L0 gate on LLM-proposed disk diffs, and `SYSTEM_PROMPT.md` edited by hand. External audits and Karpathy-style agent discipline required explicit tiers (L0 / Tier-1 / Tier-2) with CI enforcement.

### Shipped (five stacked PRs → `main`)

1. **L0 write safety** — `graph/safety/validators.py`; `validate_llm_write_diff` in `apply_semantic_page_result` ([#158](https://github.com/MarcoPorcellato/matryca-plumber/pull/158)).
2. **SYSTEM_PROMPT assembly** — `docs/openspec/agent/` fragments, `build_system_prompt.py`, `make check-system-prompt`, unlisted-fragment guard ([#163](https://github.com/MarcoPorcellato/matryca-plumber/pull/163)).
3. **`AGENTS.md` router** — three-audience map, `check_agents_coherence.py`, `make agents-check` ([#160](https://github.com/MarcoPorcellato/matryca-plumber/pull/160)).
4. **Tier-1 DI** — `prompts/core.py`, domain `*/prompts.py`, hash snapshots, zero inline prompts in `llm_client.py` ([#161](https://github.com/MarcoPorcellato/matryca-plumber/pull/161)).
5. **Cursor rule 11** — on-request maintainer checklist ([#162](https://github.com/MarcoPorcellato/matryca-plumber/pull/162)).

### Clean Architecture decisions

| Decision | Rationale |
|----------|-----------|
| No `DaemonPromptRegistry` god-object | *Clean Code* SRP — one `prompts.py` per domain |
| Domain imports only `prompts/core.py` | Dependency Rule — test-enforced |
| Tier-1A vs Tier-1B templates | JSON/Pydantic vs free-text compression |
| Fragment SHA-256, not assembled-file diff | CI stable across banner/version comments |
| **Minor 1.12.0** recommended | New maintainer contracts + L0 behavioral change; no PyPI CLI break |

**Verify:** `make ci` · `tests/test_daemon_prompts.py` · `tests/test_safety_validators.py` · `tests/test_build_system_prompt.py` · `make agents-check`.

**Docs:** [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md).

---

## [2026-06-24] v1.11.2 — Graph layer boundary refactor

### Context

Expert and Clean Architecture audits flagged inverted dependencies (`graph` → `daemon` post-write calls), unbounded generational/BM25 and block-vector RAM, OCC second-resolution drift on page writes, and scattered env parsing. v1.11.2 ships the first structural correction without a v2.0 monolith split.

### Shipped

1. **Graph layer ports** — `post_write`, `ast_cache`, `daemon_checkpoint`, cooperative yield, harvest runtime, prompt layout/constraints, cognitive LLM protocols, page namespace in `src/graph/`; agent/daemon shims; `tests/test_graph_layer_boundary.py` enforces no graph→agent/daemon imports ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) closed).
2. **Bounded RAM** — `MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS` LRU ([#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136)); dual-embedding ondemand default + `MATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS` ([#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) partial).
3. **OCC nanoseconds** — page writes use `st_mtime_ns` via `read_file_mtime_ns` ([#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) partial).
4. **Shared env parsing** — `src/utils/env_parse.py` ([#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62) partial).
5. **Observability** — daemon checkpoint `.bak` restore, link-registry merges, journey-log upsert, and watcher deletes log exceptions instead of silent suppress.
6. **Docs** — ARCHITECTURE layer-boundary Mermaid diagrams; ROADMAP/CHANGELOG/README/`llms.txt` harmonized for v1.11.2.

**Verify:** `make ci` · `tests/test_graph_layer_boundary.py` · `tests/test_generational_cache.py` · `tests/test_dual_embedding.py` · `tests/test_env_parse.py`.

---

## [2026-06-24] Claude Architectural Audit 2026-06-24 — Staff review triaged

### Context

External Staff-level audit (Repomix snapshot) flagged 13 items: lock registry eviction, generational cache sig_after TOCTOU, bootstrap mtime truncation, `auto_split` child lock, daemon god-object, env leakage, insights triple-scan, catalog per-page save, triple daemon checkpoint, Tana id scan RAM, shutdown logging, `lru_cache` test bleed, O(n²) tag clusters, double Phase-2 read.

### Outcome

**2 new P1/P2 issues filed:** [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) (BM25/alias sig_after), [#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) (Tana id stream scan), [#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) (lock registry hardening, good-first). **9 findings already on GitHub** (#39, #48, #49, #50, #53, #58, #38). **2 obsolete:** bootstrap `st_mtime_ns` shipped; shutdown logging fixed (#44).

Triage: [`docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md).

---

## [2026-06-24] Clean Architecture Audit 2026-06 — simulated Staff review triaged

### Context

External simulated audit proposed hexagonal `PageRepository` + SHA-256 CAS, Tana `json.load()` OOM, MCP↔AST coupling, BM25 SQLite outbox, import-time config globals, and `PageId` lock normalization.

### Outcome

Verified against current `src/` — **no new P1 issues**. Four findings obsolete or rejected (lock leak, `json.load`, BM25 outbox, `PageId` VO). Two follow-ups filed: [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) OCC `st_mtime_ns` parity; [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) Tana slim `NodeDump` payloads (extends #135). Hexagonal ports deferred to [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) / Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20).

Triage: [`docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md). Backlog slice: [`docs/quality/GITHUB_BUG_BACKLOG.md`](quality/GITHUB_BUG_BACKLOG.md).

---

## [2026-06-23] Good-first #118 — httpx2 dev dependency (@blackwolf225)

### Context

`fastapi/testclient` triggered `StarletteDeprecationWarning` on every UI-server test run, polluting CI logs and blocking strict `-W error::DeprecationWarning` gates. Issue [#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118) was scoped as a dependency-only good-first fix.

### Shipped

1. **`httpx2>=2.4.0`** in `[project.optional-dependencies] dev` — aligned with Makefile/CI `--extra dev` (not a separate `[dependency-groups]` block).
2. **Contributor path** — first external contribution from @blackwolf225 ([#122](https://github.com/MarcoPorcellato/matryca-plumber/pull/122)); maintainer rebased `uv.lock` on updated `main` before landing ([`b7b9cdf`](https://github.com/MarcoPorcellato/matryca-plumber/commit/b7b9cdf5d8877a069da84ae423414333ef339c88)). PR closed (not GitHub-merged) with explicit credit comment — git author on [`5fea6b1`](https://github.com/MarcoPorcellato/matryca-plumber/commit/5fea6b118ac0dd608bf43a6887ba32ee8a30413a) / [`616b5f0`](https://github.com/MarcoPorcellato/matryca-plumber/commit/616b5f099ba1f9f16c58711447a1493860689ac9).

**Verify:** `uv run pytest tests/test_ui_server.py -q -W error::DeprecationWarning` · `make check`.

---

## [2026-06-23] v1.11.1 — Logseq Matryca Parser 1.4.0 alignment

### Context

Parser **1.4.0** ships graph-integrity and robustness fixes (31 bug-hunt items, canonical page iteration, case-insensitive tag/search, live watcher delete/move, SYNAPSE embed safety). Plumber raises the minimum pin so Tana import and headless OCC writes inherit the fixes without API churn from 1.3.x.

### Shipped

1. **Dependency** — `logseq-matryca-parser>=1.4.0,<2.0.0` in `pyproject.toml` / `uv.lock`.
2. **CI** — ruff format on four Tana importer modules/tests (`make ci` green).
3. **Docs** — ARCHITECTURE, ROADMAP, CHANGELOG harmonized for v1.11.1.

**Suite:** 879 tests green · parser 1.4.0 locked · mypy strict · ruff clean.

---

## [2026-06-23] v1.11.0 — Tana workspace JSON import

### Context

Operators migrating from Tana Outliner need a **local, offline** path into Logseq OG that respects journal `config.edn`, avoids OOM on large exports, preserves outliner depth limits, and never duplicates nodes on re-import. The pipeline mirrors `ingest_document` OCC semantics but adds Tana-specific schema translation (flat `docs[]`, supertags, field tuples, Library/STASH entities).

### Shipped

1. **Streaming loader** — `ijson` over `docs[]` / `storeData.docs.item`; `json.load()` forbidden on export path.
2. **Hybrid placement** — entities → `Tana/{Supertag}/{Name}` pages; `#day` → `journals/` via EDN format; depth-split at 8 with `Tana/Split/` pages.
3. **Link resolution** — in-flight batch map + `MasterCatalog` title/alias rewrite before write.
4. **Idempotent writes** — vault-wide `tana-id::` pre-scan; skip duplicates; `Tana/Import Log` ledger on apply.
5. **Surfaces** — `run_tana_import()`; CLI `matryca import tana --file … [--apply]` (dry-run warning on stderr); MCP `import_tana(dry_run=True)`.
6. **Docs** — [`docs/openspec/tana-import.md`](openspec/tana-import.md) v1.0; README, `llms.txt`, ARCHITECTURE, CONTRIBUTING harmonized.

**Suite:** 879 tests green · mypy strict · ruff clean · coverage ≥70%.

---

## [2026-06-19] v1.10.6 — Concurrency integrity (unified flock + hub page OCC)

### Context

v1.10.0 closed catalog/registry torn-write gaps with flock + atomic save, but page RMW locks and JSON sidecar locks still used divergent flock implementations — nested harvest + checkpoint + registry passes could deadlock under pytest-xdist and concurrent daemon writers ([#40](https://github.com/MarcoPorcellato/matryca-plumber/issues/40)). Hub pages (Master Index, Graph Insights) compiled expensive markdown without pre-compile OCC, risking overwrite of human edits during multi-second compiles ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34)).

### Shipped

1. **`platform_lock.py`** — shared NB flock + exponential backoff + blocking fallback + thread-local reentrancy; consumed by `page_write_lock` and `json_flock`.
2. **`generated_hub_write.py`** — `write_generated_hub_page`: baseline mtime before compile, graceful skip on drift, `atomic_write_bytes_if_unchanged` at commit.
3. **Tests** — `test_hubs.py` (hub OCC scenarios), expanded `test_json_flock.py`.
4. **Docs** — ARCHITECTURE Mermaid diagrams for unified flock layer and hub compile sequence; README/llms.txt/ROADMAP harmonized.

---

## [2026-06-19] v1.10.5 — Logseq Matryca Parser 1.3.1 alignment

### Context

Matryca Plumber pinned `logseq-matryca-parser` at `>=1.1.1` since early 2026. Parser **1.3.1** consolidates graph parity (1.2.x) and a stable root public API (1.3.0). Plumber import paths and AST bootstrap telemetry were aligned without changing the headless OCC mutation contract.

### Shipped

1. **Dependency** — `logseq-matryca-parser>=1.3.1,<2.0.0` in `pyproject.toml` / `uv.lock`.
2. **Import cleanup** — `LogosParser` from package root in `matryca_hooks`, `ingestion`, `conftest`; `serialize_logseq_page` explicit import.
3. **AST cache** — bootstrap file count via parser `discover_graph_files` (same exclusions as graph load).
4. **Headless splice** — `graph_dispatch` uses parser `_insertion_line_after_node` for line-index parity with 1.3.1.

---

## [2026-06-19] v1.10.4 — Dependency maintenance & CI toolchain

### Context

Eight stale Dependabot PRs (#75–#82) failed CI on an outdated base (`ruff format-check` on `master_catalog.py`), not on the bumps themselves. Consolidated into [#83](https://github.com/MarcoPorcellato/matryca-plumber/pull/83) and shipped as a patch release.

### Shipped

1. **GitHub Actions** — `actions/checkout@v7` across all workflows (metrics-saver from v4); `dependency-review-action@v5`; `astral-sh/setup-uv@v8.2.0`.
2. **Sovereign UI frontend** — npm patch/minor: `react-dom`, Tailwind CSS 4.3.1 stack, `lucide-react`, `eslint-plugin-react-refresh`.
3. **Dependabot groups** — weekly batch PRs for `github-actions` and `frontend-npm` ecosystems.

---

## [2026-06-18] v1.10.3 — Infrastructure hardening & Sovereign UI resilience

### Context

Post–v1.10.0 catalog integrity work exposed operator-facing friction: saving settings in the Sovereign UI blocked the single Uvicorn worker during `.env` writes and `prepare_matryca_runtime()`, freezing the 5s telemetry poll. LLM structured-output schemas for nested outline nodes only enforced `additionalProperties: false` at the top level, and the UI process never registered Loguru’s rotating file sink.

### Shipped

1. **Non-blocking UI config saves** — `POST /api/config` and graph-path endpoints offload persistence + bootstrap via `asyncio.to_thread`.
2. **Strict LLM contracts** — Pydantic `extra="forbid"` on plumber/outline structured models; recursive strict JSON Schema via OpenAI SDK helper; adaptive `max_tokens` / `max_completion_tokens`.
3. **UI observability** — `configure_loguru()` at control-room startup (parity with MCP/daemon).
4. **httpx model discovery** — `GET /api/lm-models` replaces urllib with redirect-refused httpx client.
5. **Flock sidecar permissions** — `json_flock`, page RMW locks, daemon lock files created as `0o600` (CodeQL `py/overly-permissive-file`).
6. **Docs** — README, `llms.txt`, ARCHITECTURE, OpenSpec security/telemetry/resilience notes, GitHub release template.

**Suite:** 725 tests green · mypy strict · ruff clean · coverage ≥70%.

---

## [2026-06-18] v1.10.0 — Catalog integrity & OSS maturity (#35–#37, #41)

### Context

Ship the v1.9.10 **Concurrency & Data Integrity** milestone under semver **1.10.0** (minor bump: closes a multi-issue data-plane milestone plus maintainer-facing OSS hardening). JSON sidecars (`master_catalog.json`, `.matryca_link_registry.json`) had torn reads, last-writer-wins merges, and catalog rows claiming LLM summaries never written to `.md` after OCC abort.

### Shipped

1. **Master catalog load flock (#35)** — `_load_catalog_payload_from_disk` and `.bak` restore read under `cross_process_json_flock`.
2. **Master catalog merge-on-save (#36)** — `MasterCatalog.save()` reloads disk under flock and merges page rows by `last_mtime`; `save(replace=True)` for prune; `remove()` deltas propagate via `_pending_removals`.
3. **Harvest catalog drift guard (#37)** — `_append_minimal_semantic_index` returns `bool`; `harvest_page_into_catalog` skips `catalog.upsert` on OCC abort (`pending_llm`).
4. **Link registry atomic save (#41)** — `_save_registry_unlocked` uses `atomic_write_bytes`.
5. **OSS / GitHub hygiene** — PR template, CODEOWNERS, SUPPORT.md, CodeQL, dependency-review, npm Dependabot, release verify job, version-consistency guard, frontend ESLint in CI, PyPI metadata.
6. **Dependency advisories** — Transitive bumps for Python and frontend toolchain.
7. **Docs** — README, `llms.txt`, ROADMAP, ARCHITECTURE, OpenSpec index harmonized for v1.10.0.
8. **Developer DX** — `make test-fast` (`NUM_WORKERS` default `4`, no coverage, skips `tests/slow/`); `make test-full` for CI coverage gate.

**Suite:** 720+ tests green · mypy strict · ruff clean · frontend ESLint clean · `make test-fast` ~5s on typical dev hardware.

---

## [2026-06-12] v1.9.15 — Mypy strictness (#60) & journal Phase-2 bypass

### Context

Two v1.9.x perfection-track items closed without a parser semver bump: eliminate mypy cheat suppressions in `src/`, and stop burning LLM tokens on daily fleeting notes that the daemon itself mutates heavily.

### Shipped

1. **Mypy strictness (#60)** — Removed all 11 `# type: ignore` comments under `src/`; replaced with `typing.cast()`, `isinstance()` narrowing, `Path()` coercion, a `_FilesystemObserver` Protocol (`file_watcher.py`), and lambda key functions. `uv run mypy src tests` passes with `strict = true` and **zero** production suppressions.
2. **Journal Phase-2 skip** — Files under `journals/` still enter the duty cycle for **Phase-1 structural settle** (AST cache `apply_file_event`, link-registry merge, OCC `mtime` ledger via `_settle_journal_structural_cycle_file`) but **bypass** cognitive lint, `index_page`, semantic index writes, and dual embeddings. `page_needs_phase2_cognitive` never re-queues settled journals for semantic work; vault progress metrics exclude `journals/` from the Phase-2 denominator.

**Suite:** 712+ tests green · mypy strict (no `src/` ignores) · ruff clean.

---

## [2026-06-10] v1.9.14 — Contributor readiness & scoped tech debt

### Context

Pre-v2.0 OSS onboarding sprint: document the open-issue backlog for external contributors, land low-risk DRY fixes, and improve Phase 2 token economics on journal-heavy vaults without a `logseq-matryca-parser` semver bump.

### Shipped

1. **`good_first_issues_blueprints.md`** — six curated audit issues with copy-paste GitHub welcome comments (#45, #53, #56, #69, #71, `#62` Literal slice).
2. **#64 (scoped)** — `safe_update_alias` / `safe_alias_items` in `alias_state.py` centralize upstream `SessionAliasRegistry` private dict access; full public parser API deferred to v2.0 Shadow DB.
3. **#62 (NoRedirect slice)** — shared `NoRedirect` in `src/utils/network.py` for preflight and Sovereign UI `/v1/models` probes.
4. **Journal-aware Phase 2** — daily `journals/` pages excluded from Louvain neighborhood clustering and `[CLUSTER FOCUS]` injection; flat `[journals]` group.
5. **Entity consolidation (#68)** — skip `assess_entity_overlap` when either wikilink is a journal page or Logseq date string.
6. **Docs** — README narrative refresh, root `ROADMAP.md`, `llms.txt` v1.9.14, release notes in `docs/releases/v1.9.14-GITHUB.md`.

**Suite:** 710+ tests green · mypy strict · ruff clean.

---

## [2026-06-10] Post-v1.9.11 — JSON repair hardening & daemon launch reliability

### Context

Runtime probes after v1.9.11 found three latent defects in the LLM JSON salvage path and one in daemon/UI startup coordination.

### Defects crushed

1. **Array root collapsed to first object** — `extract_json_payload_regex()` always preferred `{` before `[`, so `[{...}, {...}]` reparent payloads parsed as a single dict and failed `isinstance(..., list)` in `graph_dispatch`.
2. **Trailing garbage regex inside strings** — `strip_trailing_json_garbage()` matched `}` followed by `{`/`[`/`"` even inside JSON string values (common in code-snippet fields), truncating valid completions.
3. **Wrong bracket close order** — `balance_json_brackets()` appended all `]` then all `}`, producing invalid `]}` for truncated `[{...` slices.
4. **Start Engine false negatives** — PID was published too late in bootstrap; UI launcher subprocess exit was misread as failure; stale foreign PIDs could be overwritten.

### Milestones shipped

1. **String-aware JSON repair** — first-delimiter extract, balanced trailing trim, nesting-stack bracket balance (`json_repair.py`).
2. **Daemon PID contract** — publish at lock acquisition; bootstrap signal handlers; `foreign_pid` guard; UI spawns `plumber start --foreground`.
3. **CI allowlist stability** — `# sandbox-read-ok` inline markers replace hardcoded line numbers in `check_graph_read_sandbox.py`.

### Architectural outcome

The LLM resilience stack now treats **array roots** and **string interiors** as first-class cases — not edge cases discovered only in production reparent calls. Daemon launch success is defined by a **live published PID**, matching the contract documented since v1.9.3 live telemetry.

---

## [2026-06-09] v1.9.9 — Security & Sandbox (milestone closure)

### Context

Pre-v2.0 audit (#27–#33) found path-sandbox gaps in link verification reads, unbounded JSON sidecar loads, symlink exposure in wiki lint, permissive debug-log paths, and scattered raw `Path.read_text()` in graph/agent/rag code.

### Milestones shipped

1. **Path sandbox reads** — `read_graph_file_text()` migration; link-registry `page_relpath` validation; `_resolve_asset_path` sandbox before asset checks.
2. **Bounded JSON** — `read_bounded_json()` + `MATRYCA_JSON_MAX_BYTES` (64 MiB default) on catalog, registry, daemon state, semantic cache.
3. **CI anti-regression** — `scripts/check_graph_read_sandbox.py` wired as `make sandbox-read-check` in `make check` / `make ci`.
4. **Operator defaults** — `.env.example` templates `MATRYCA_UI_REQUIRE_EXPLICIT_TOKEN=true`; debug NDJSON path allowlist + secret redaction.
5. **OpenSpec + agent docs** — [`docs/openspec/security-sandbox.md`](openspec/security-sandbox.md); `llms.txt` §2.4 Security & Sandbox.

### Architectural outcome

Graph I/O is **defense-in-depth**: sandbox validation on every read path, bounded sidecar JSON, and CI enforcement so new bypasses cannot land silently. Closes the v1.9.x **Security & Sandbox** GitHub milestone.

---

## [2026-06-05] v1.9.5 — LLM OS agent contract (Soft Gate + bootstrap_status)

### Context

External MCP agents (Cursor, Claude Desktop, custom hosts) needed a **deterministic Phase 1 gate** beyond inferring bootstrap completion from `[[Matryca Master Index]]` existence alone. Hard-blocking agents when the index was missing created bad UX; operators needed a **Human-in-the-Loop** path (Local Daemon / Blind Search / Cloud Indexing).

### Milestones shipped

1. **`bootstrap_status` read target** — `src/graph/bootstrap_status.py`; MCP `read_graph_data` and CLI `matryca --json read bootstrap_status` expose `soft_gate_active`, harvest progress, and catalog health.
2. **LLM OS prompts** — `SYSTEM_PROMPT.md` § "LLM OS", `llms.txt` §6, MCP docstrings for Soft Gate prerequisites.
3. **OpenSpec** — [`docs/openspec/llm-os-instructions.md`](openspec/llm-os-instructions.md) with v2.0 SQLite Shadow DB migration trigger for maintainers.
4. **L1 seed** — `matryca-l1/llm-os-rules.md` on provision.

### Architectural outcome

Tier-1 Gardener (daemon Phase 1) and Tier-2 Cognitive Agents (MCP/CLI) are **explicitly decoupled** in agent-facing docs. Tier-2 agents prefer catalog-first navigation; when Phase 1 is incomplete they pause and ask — they do not silently `grep pages/` or impersonate harvest.

### Documentation

README, ARCHITECTURE, OpenSpec index, `agent-dx.md`, `agent-onboarding.md`, and release notes aligned for **v1.9.5 — The "LLM OS" Update**.

---

## [2026-06-05] v1.9.4 — Journey Log consolidation (daily journal hygiene)

### Context

Operators reported **journal clutter**: each daemon duty cycle appended `## 🤖 Matryca Activity` plus a child bullet (two Logseq blocks per cycle), including idle polls — easily **50–200+ lines** per day in `journals/YYYY_MM_DD.md`.

### Milestones shipped

1. **`JourneyDayLedger`** — Cumulative daily metrics in `DaemonState.journey_day` (`.matryca_daemon_state.json`); auto-reset on calendar day change.
2. **Single-bullet upsert** — `upsert_matryca_activity_block` replaces one top-level `- 🤖 Matryca Activity — …` line; legacy `##` sections on today's file stripped on first write.
3. **Idle skip** — Cycles with no indexing, fast-track, link checks, or flags do not touch the journal.
4. **OpenSpec / operator docs** — [`docs/openspec/agent-dx.md`](openspec/agent-dx.md) §4 expanded; README and ARCHITECTURE aligned.

### Architectural outcome

Journey Log remains a **view** over daemon activity (Markdown-only system of record). The journal shows **one foldable block per day** for operators; MCP `append_journal` stays append-only for explicit agent notes.

### Documentation

README, ARCHITECTURE, OpenSpec [`agent-dx.md`](openspec/agent-dx.md) §4, `llms.txt`, and release notes aligned for **v1.9.4 — The "Clean Journal" Update**.

---

## [2026-06-05] v1.9.3 — Live Telemetry (Sovereign UI)

### Context

Operators reported a **frozen** control room during long LLM indexing: progress bar, Phase 1/2 pills, and token counters appeared to refresh only on **Stop Engine**. Root cause was a **pull** stack with **coarse daemon checkpoints** and API/UI gaps — not missing WebSockets.

### Milestones shipped

1. **Daemon heartbeat** — `MATRYCA_TELEMETRY_HEARTBEAT_SECONDS` (default 5): cooperative `save_daemon_state` during `index_page` (sidecar thread), idle inter-cycle sleep, and post-bootstrap work. Persistence uses **`threading.Lock`** + **`DaemonState.from_json(to_json())`** snapshots to avoid heartbeat vs main-thread races.
2. **API token overlay** — `GET /api/state` merges session totals from `matryca_plumber_ops.log` (parity with `tui_dashboard.py`) so counters move during inference without per-token checkpoint writes.
3. **Frontend** — `POLL_CYCLE_MS = 5000`; **`daemon_pid`** on state payload; background state poll when frozen but PID live; auto-unfreeze on `running` / `idle` / live PID.
4. **Phase 1 pills** — `MATRYCA_BOOTSTRAP_PILL_CHECKPOINT_EVERY` (default 5) flushes `bootstrap_recent` independently of the full catalog checkpoint interval.

### Documentation

OpenSpec [`openspec/live-telemetry-ui.md`](openspec/live-telemetry-ui.md); README, ARCHITECTURE, CONTRIBUTING, `llms.txt`, and release notes aligned for **v1.9.3 — The "Live Telemetry" Update**.

### Architectural outcome

Telemetry remains **checkpoint + REST pull** (Karpathy/simplicity). Perceived real-time UX is achieved by **more frequent, thread-safe writes** and **smarter readers** — not a second transport.

---

## [2026-06-05] v1.9.2 — Agent-zero-friction & security patch

### Context

Patch release after the v1.9 feature line shipped: external agents increasingly consume Matryca via **`uvx matryca-plumber`**, but README-only guidance was insufficient. Enterprise operators also needed a public signal that transitive **`aiohttp`** CVEs were remediated in the lockfile.

### Milestones shipped

1. **`llms.txt` + `.well-known/llms.txt`** — Imperative agent guide: `LOGSEQ_GRAPH_PATH`, verified CLI/MCP commands, PyPI/`uvx` anti-patterns (no `git clone` hallucinations).
2. **OpenSpec** — [`docs/openspec/agent-onboarding.md`](openspec/agent-onboarding.md); README agent hook and documentation map updated.
3. **Security** — `uv.lock` pins `aiohttp` ≥3.14.0; CLI stdout/CodeQL clear-text logging documented and suppressed where stdout is the intentional channel.
4. **CI** — [`.github/workflows/dependabot-uv-fix.yml`](../.github/workflows/dependabot-uv-fix.yml) auto-syncs `uv.lock` on Dependabot PRs.

### Documentation

Aligned **README**, **ARCHITECTURE**, **CONTRIBUTING**, **SECURITY**, **SYSTEM_PROMPT** (dynamic `made-by::` examples), and **openspec** index with v1.9.2.

### Architectural outcome

Distribution surface for agents is now **first-class** alongside daemon/MCP: the PyPI wheel, `llms.txt`, and OpenSpec stay in sync per patch release.

---

## [2026-06-01] v1.9.0 — Structural graph hygiene + agent DX

### Context

GitHub milestone **v1.9.0** (issues [#15](https://github.com/MarcoPorcellato/matryca-plumber/issues/15), [#16](https://github.com/MarcoPorcellato/matryca-plumber/issues/16)): surface **knowledge rot** and improve **headless agent ergonomics** without new LLM cognitive modules or auxiliary databases.

### Milestones shipped

**#15 — link verification**

1. **`src/graph/link_verification.py`** — Extract → `.matryca_link_registry.json` → async `httpx` HEAD / `os.path.exists` → OCC `dead-link::` / `missing-asset::`.
2. **Daemon integration** — `MaintenanceDaemon._finalize_link_and_journey_pass` at end of each duty cycle; passive extract on page reads.
3. **OpenSpec** — [`docs/openspec/link-verification.md`](openspec/link-verification.md).

**#16 — agent-centric DX**

4. **CLI `--json`** — Global machine-readable envelope on `matryca` (`src/cli/__init__.py`).
5. **`matryca context load`** — Semantic macro (`src/agent/context_load.py`).
6. **`read subtree`** — MCP + CLI target with optional heading filter (`graph_tool_helpers.read_subtree_markdown`).
7. **Journey Log** — `## 🤖 Matryca Activity` append to today's journal (`src/agent/journey_log.py`).
8. **OpenSpec** — [`docs/openspec/agent-dx.md`](openspec/agent-dx.md).

### Documentation

Cross-linked **README**, **ARCHITECTURE** (v1.9 sections + mermaid), **SYSTEM_PROMPT**, **runtime-bootstrap** (registry sidecar), and **openspec/README**.

### Architectural outcome

Plumber remains **Markdown-only** as system of record: the link registry is a queue, Journey Log is a view, and agents get JSON/subtree/context primitives on the same `graph_dispatch` plane as MCP.

---

## [2026-05-31] Unreleased — Telos & Identity (Phase 1) + atomic ingestion (Phase 2)

### Context

Master architecture RFC **Phase 1:** operator **role and durable rules** live on a Logseq config page inside the vault, refresh without daemon restart, and flow into every local LLM call and MCP tool response. **`store_fact`** appends preferences under `- # AI Constraints`.

**Phase 2:** external Markdown (exports, email bodies, agent drafts) enters the vault through a single **`ingest_document`** MCP tool — parser-first, fresh block UUIDs, ledger pages — without polluting `pages/` with parse scratch files (watchdog-safe OS temp paths).

**Phase 3:** optional **dual embeddings** per block (`vec_content` + `vec_applicability`) in `block_vectors.json`, hybrid `search_graph` / `method=semantic`, daemon indexing gated by `MATRYCA_DUAL_EMBEDDING_ENABLED` (no change to BM25 / TF-IDF clustering).

### Milestones shipped

**Phase 1 — persona**

1. **`src/daemon/config_layer.py`** — Parse Telos/Constraints from `LogseqPage.root_nodes`; `IdentityConfigStore` with mtime invalidation; `inject_identity_into_system_prompt` / `append_identity_to_mcp_payload`.
2. **Reactive stack** — `file_watcher.py`, `ast_cache.py`, `post_write_hooks.py`, `git_audit.py` (robot commits per file after Plumber writes).
3. **`store_fact` MCP tool** — `src/agent/memory_tools.py`; writes always target `pages/matryca-config.md`.
4. **OpenSpec** — [`docs/openspec/identity-config.md`](openspec/identity-config.md).

**Phase 2 — atomic ingestion**

5. **`src/agent/ingestion.py`** — `process_ingestion`, `resolve_ingest_destination_page_title`, `MATRYCA_INGEST_PAGE` / daily `Ingest/YYYY-MM-DD`, `LOG` + `GLOSSARY` ledgers, capped UUID audit lines.
6. **`ingest_document` MCP tool** — seventh registered tool; `tempfile` parse + `os.unlink`; write order destination → LOG → GLOSSARY.
7. **OpenSpec** — [`docs/openspec/ingest.md`](openspec/ingest.md); cross-links in `l1-l2-routing.md`, `ARCHITECTURE.md`, `SYSTEM_PROMPT.md`, `README.md`, `.env.example`.

### Architectural outcome

**L1** (sibling `matryca-l1/`) remains session/deploy context; **in-graph identity** is vault-native persona for daemon + MCP (read `matryca/config`, write `matryca-config` via `store_fact`). **Ingestion** is vault-native capture: one append target per call (Option C), with audit trails on `LOG` / `GLOSSARY` instead of ad-hoc journal sprawl. Parse artifacts never touch `pages/`, so Phase 1 reactive indexing stays quiet during ingest-only MCP sessions.

---

## [2026-05-29] v1.8 pre-release — Round 4 read-only audit (operational hardening)

### Context

After TRIZ rounds 1–3 on local JSON degeneration (Gemma tail of death, compression walls, poisoned semantic cache), a final **read-only** audit flagged five items that could still harm vault integrity or host responsiveness on real graphs. These are **not** new cognitive features — they tighten contracts already documented under OCC and LLM resilience.

### Milestones shipped

1. **Stateless graph insights** — `generate_graph_insights` uses `stateless=True` so panoramic ontology reports do not append to Ermes execution history.

2. **Compression persist hygiene** — `_compress_history_via_llm` and `condense_messages` run `sanitize_prose_llm_completion()` on summaries **before** they are injected into consolidated history.

3. **Semantic index block catalog cap** — `_enumerate_blocks_for_prompt` stops at **8000 characters** (same order of magnitude as the indexed page body cap) with an explicit truncation note so the model does not target uncatalogued UUIDs.

4. **Phase 2 lock scope** — `_process_llm_cycle_file` no longer wraps cognitive lint + `index_page` in `page_rmw_lock`; the lock is acquired only in `apply_semantic_page_result` for the atomic write. Multi-minute LLM work must not block Logseq saves.

5. **`id::` identity protection** — `parse_logseq_property_line` excludes normalized key `id` so property hygiene and MCP property-line tools never treat UUID lines as editable metadata.

### Architectural outcome

OCC documentation in [`ARCHITECTURE.md`](ARCHITECTURE.md) now matches runtime: snapshot → read → infer **without** page lock → verify → lock → commit. Resilience and mldoc docs cross-link the new guards. See [`CHANGELOG.md`](../CHANGELOG.md) `[Unreleased]` and [`resilience-llm-json-triz.md`](resilience-llm-json-triz.md) §5.

### Status

**Shipped in `[Unreleased]`** — pending semver tag with the rest of v1.8.x.

---

## [2026-05-27] v1.8 — Edge computing & performance (16 GB / 10k pages)

### Context

Matryca Plumber’s stated operator profile is a **CPU-only 16 GB laptop** with a **local** LLM (LM Studio, Ollama, llama.cpp) and vaults approaching **10,000** Markdown pages. Phase 14d fixed megabyte-page **token** cost via summaries and introduced content-before-task ordering for Phase 2 indexing — but production traces still showed:

1. **Bootstrap harvest** sending `Task` before `Content`, destroying KV-cache reuse on every MapReduce chunk and reduce pass.
2. **Per-page alias maps in the system prompt**, preventing any cross-page system-string reuse on local servers.
3. **RAM creep** — full BM25 token bags, unbounded semantic-cache `_memory`, and a full-graph backlink rebuild at every Phase 1 start.
4. **Host freezes** — synchronous 10k-file loops, daemon checkpoints every five cataloged pages, and `purge_expired_semantic_cache` accidentally deleting `master_catalog.json` alongside inference cache files.

v1.8 is explicitly **performance-only**: zero new semantic or graph-manipulation features.

### Milestones shipped

1. **`PagePromptSession`** (`page_prompt_session.py`) — One stable page block per file per cycle; cognitive modules and semantic index share it; AliasIndex moves to a **capped user footer** (`MATRYCA_ALIAS_PROMPT_MAX_CHARS`).

2. **`build_semantic_lint_system_prompt()`** (`semantic_lint_prompts.py`) — Stable system instructions extracted from `maintenance_daemon.py` to break circular imports and keep the system string constant.

3. **Cache-aligned bootstrap** — `harvest_page_summary` and MapReduce reduce use `build_cache_aligned_prompt`; `stateless=True` on per-page inference paths.

4. **Memory plane** — BM25 postings-lite (`doc_term_freqs`), `release_phase1_memory()` after Phase 1, semantic cache LRU, `unload_master_catalog()`, reserved JSON files during TTL purge.

5. **I/O plane** — `cooperative_yield.yield_host()`, persisted `backlink_counts.json`, `MATRYCA_BOOTSTRAP_CHECKPOINT_EVERY`, `apply_plumber_priority()` (`nice` + optional psutil ionice). Micro-yields (2 ms batch pauses) are distinct from **thermal** sleeps (≥ 1 s, post-LLM only); thermal tests filter `time.sleep` with `s >= 1.0`.

6. **Docs & tests** — [`v1.8-OPTIMIZATION-PLAN.md`](v1.8-OPTIMIZATION-PLAN.md), [`openspec/llm-performance.md`](openspec/llm-performance.md), `scripts/gen_synthetic_graph.py`, `make perf` / `@pytest.mark.slow`.

7. **Software edge** — [`llm_client.py`](../src/agent/llm_client.py) probe-driven Path A/B structured output; `FrozenPromptPrefix` + `kv_prefix_hash`; [`markdown_io.py`](../src/graph/markdown_io.py) mmap Phase 1 reads; [`process_priority.py`](../src/agent/process_priority.py) CPU sandbox (`MATRYCA_CPU_SANDBOX`, `[edge]` extra). Spec: [`v1.8-SOFTWARE-EDGE-PLAN.md`](v1.8-SOFTWARE-EDGE-PLAN.md).

### Architectural outcome

The product can be described as **edge-ready**: the daemon is designed to run **silently for days** on laptop-class hardware when operators enable the v1.8 `.env` profile. The Context Acceleration Shield (Phase 14d) and the v1.8 Zero-Prefill stack are complementary — summaries shrink tokens; stable prefixes maximize **reuse** of whatever tokens remain.

### Status

**Shipped in 1.8.0** — see [`CHANGELOG.md`](../CHANGELOG.md) `[1.8.0]`.

---

## [2026-05-25] Security depth pass (post-audit hardening)

### Context

A full-repository security review identified gaps where **SSRF policy applied only to the Sovereign UI** (not the maintenance daemon’s `InstructorLLMClient`), where **`LOGSEQ_GRAPH_PATH` could be repointed** to any directory with a `pages/` folder via authenticated UI saves, and where **MCP stdio started unconditionally** for any host spawning bare `matryca-plumber`.

### Milestones shipped

1. **`src/utils/llm_url_policy.py`** — Single `validate_llm_proxy_url()` used by `ui_server.assert_safe_lm_proxy_url`, `plumber_config` env load, and `resolve_validated_llm_base_url()` in the daemon LLM client.

2. **Graph config allowlist** — `validate_logseq_graph_path_for_config()` + `graph_config_allowed_roots()` (home, repo, temp, current graph, `MATRYCA_ALLOWED_GRAPH_ROOTS`).

3. **UI rate-limit tiers** — Authenticated vs unauthenticated per-IP budgets; `/api/health` and loopback `/api/auth/session` exempt.

4. **`MATRYCA_MCP_ENABLED`** — Default **off**; `plumber_entry` refuses MCP stdio until explicitly enabled (documented in `.env.example`, `CONTRIBUTING.md`, `SECURITY.md`).

5. **MCP tool error sanitization** — Filesystem paths and raw runtime text hidden from MCP clients unless `MATRYCA_DEBUG=true`.

6. **Test bar** — **453** pytest targets; new coverage in `tests/test_llm_url_policy.py` and security remediation cases.

### Status

**Shipped in 1.7.5**. Operators enabling Claude Desktop should set `MATRYCA_MCP_ENABLED=true` in `.env`. See [`CHANGELOG.md`](../CHANGELOG.md) `[1.7.5]`.

---

## [2026-05-24] v1.5.15 — The Ironclad consolidation sprint (1.5.x era)

### Context

By mid-1.5.x, Matryca Plumber had already shipped Logseq-native parity (Phase 15), enterprise UI security (Phase 16), and the Context Acceleration Shield. Production use on real graphs exposed a **second wave of integration defects**: flaky async tests around Loguru’s queued sink, false-negative daemon launch detection in the Sovereign UI, OCC ordering gaps when cognitive lint performed self-writes mid-request, and stdout pollution when MCP hosts spawned the same wheel as the CLI.

This sprint hardens the **operational glue** between the three runtime surfaces (daemon, UI, MCP) so the system behaves as a single product at **`uvx`** install time — not only when run from a git checkout.

### Milestones shipped

1. **Product identity: Matryca Plumber** — The open-source maintenance daemon, linter, and indexing engine is **Matryca Plumber**. **Matryca Brain** remains reserved for the Nuitka-compiled Pro enterprise tier (Twin Ingestion, Epistemic Guardian). CLI: `matryca plumber {start,status,stop,ui}`; env prefix `MATRYCA_PLUMBER_*`; ops log `logs/matryca_plumber_ops.log`.

2. **`uvx` zero-install workflow** — Operators run `uvx --from matryca-plumber matryca-plumber status` without polluting global site-packages. Documented in README; service installers must still target a **stable** `uv tool install` binary (not ephemeral `uvx` cache paths).

3. **`plumber_entry.py` — CLI vs MCP stdio routing** — The `matryca-plumber` console script normalizes shorthand (`start`, `status`, …) to `matryca plumber` and **lazy-imports** `main.main()` only when argv is not CLI-shaped. FastMCP no longer loads at import time for operator commands — eliminating stdio/stream corruption when the same entrypoint serves both roles.

4. **pytest-asyncio + Loguru MCP telemetry** — Replaced flaky `asyncio.sleep` polling in `tests/test_mcp_telemetry.py` with **`await logger.complete()`** so enqueued sink records drain deterministically. The bridge stores **`id(ctx)`** in `record["extra"]` and maps live `Context` handles in `_mcp_sessions` — fixing **multiprocessing pickling errors** when Loguru’s worker thread forwarded records containing non-picklable MCP objects.

5. **Sovereign UI daemon launch false negative** — `_verify_daemon_launch()` in `ui_server.py` previously treated **exit code 0** from the detached launcher as failure. The worker intentionally exits after spawning the foreground daemon; success is confirmed by a **live PID** in `.matryca_plumber_daemon.pid` (`is_plumber_process`), not by the launcher process staying alive.

6. **OCC ordering refinement** — `occ_snapshot()` is captured **before** page reads and LLM work; `occ_verify_before_write()` runs **before** `page_rmw_lock`; mtime is re-checked **inside** the lock; `atomic_write_bytes_if_unchanged()` guards the final commit. Cognitive lint paths re-baseline after Plumber’s own intermediate writes to avoid false conflicts on multi-step applies.

7. **Atomic `.env` persistence** — Settings drawer saves use `_atomic_write_text` (temp + `fsync` + `os.replace`) so partial writes cannot tear Plumber configuration during 1 Hz operator edits.

8. **Page-lock registry LRU** — At 4096 entries, evict **unlocked** locks LRU-style instead of clearing the entire registry — stable hot-path locking on large vaults.

9. **Codebase hardening bar** — **453** pytest targets passing (was 437 at v1.5.15); **Mypy strict** clean on `src` and `tests`; Ruff lint/format via `make check`.

### Architectural outcome

Matryca Plumber is fairly described as an **enterprise-grade, local-first background daemon** with a Sovereign UI and optional MCP sidecar — not “a Claude Desktop plugin.” The 1.5.x **Ironclad** era closes the gap between architectural intent (documented in Phase 14–16) and day-to-day reliability when installed via **`uvx`**, monitored from the browser cockpit, and stressed under concurrent human editing.

### Status

**Shipped** — v1.5.15. See also [`CHANGELOG.md`](../CHANGELOG.md) `[Unreleased]` for the same defect class.

---

## [2026-05-23] Phase 16: Enterprise security and concurrency (Ironclad)

### Context

Phase 15 delivered Logseq filesystem parity. Phase 16 layered **Zero-Trust** authentication on the Sovereign UI (`X-Matryca-Token`), cross-platform **`subprocess.Popen`** daemon launch (replacing UNIX-only `fork()`), exclusive **`.matryca_plumber_daemon.lock`**, SSRF-hardened LM discovery, paranoia-level ledger commits, and **`MATRYCA_ALLOW_FLOCK_DEGRADATION`** for cloud-sync vaults.

### Outcome

The autonomous daemon graduated from power-user script to **production operator surface** — secure loopback cockpit, Windows-first background ops, ledger survival on power loss.

### Status

Shipped. Superseded for operational polish by **v1.5.15** entries above.

---

## [2026-05-23] Phase 15: Logseq-native parity shield and Windows I/O

### Context

Real graphs exposed bugs generic Markdown tools never see: ghost duplicate pages from namespace drift, page properties prefixed with `- ` falling out of the indexer, orphaned `id::` lines breaking `((uuid))` integrity, `cp1252` corruption on Windows, and **silent overwrites** when users typed during slow local inference.

### Victories shipped

- **OCC** — `occ_snapshot` → inference → `atomic_write_bytes_if_unchanged` with `file_mtime_drifted` aborts.
- **`page_path.py`** — `/` → `___` + percent-encode reserved characters.
- **`page_properties.py`** — true line-0 frontmatter vs +2-indent block properties.
- **Alias index** — case-insensitive resolution; exclude `logseq/bak/`, `.recycle/`, `.git`.
- **Trust & Safety drawer** — Safe / Augmented / Surgeon tiers in `SettingsDrawer.tsx`.
- **UTF-8 / CRLF** — explicit encoding and line-ending normalization on all graph I/O.

### Status

Shipped. Test bar at phase close: **349+** passing (later superseded by 437).

---

## Phase map (condensed)

| Phase | Name | What shipped |
|:-----:|------|--------------|
| **1** | Baseline headless plane | `graph_dispatch`, optional FastMCP, `OutlineNode`, DFS writes |
| **2** | L1 / L2 routing | `read_l1_memory`, `routing_hint` |
| **3** | PKM refinements | BM25 query, property surgery, git snapshots |
| **4–6** | Logseq superpowers + gardener | Queries, journals, flashcards, MOC, split blocks |
| **7–8** | Mldoc + Ironclad Shield | Fence scanner, atomic writes, generational cache |
| **9** | Trust plane | `quality_gate`, synthetic `id::` policy |
| **10** | Delivery | GitHub Actions CI, Dependabot, release workflow |
| **11** | Fortress (v1.3) | `path_sandbox`, `mcp_tool_guard` |
| **12** | Headless Revolution (v1.4) | Removed HTTP client; X-Ray state file |
| **13** | Operational hardening (v1.4.1) | `chdir` sandbox root, MCP telemetry sanitizer, `service install` |
| **14** | Plumber OS | `MaintenanceDaemon`, Louvain GraphRAG, FastAPI + React cockpit |
| **14d** | Context Acceleration | TRIZ payload + prompt prefix alignment + `reload_plumber_dotenv` |
| **1.8** | Edge computing & performance | PagePromptSession, backlink index, BM25 slimming, cooperative harvest, memory teardown |
| **15** | Logseq-native parity | OCC, namespaces, frontmatter, Trust UI |
| **16** | Enterprise Ironclad | Zero-Trust UI, subprocess daemon, SSRF, cross-platform lock |
| **1.5.15** | Ironclad consolidation | `plumber_entry`, MCP log bridge, UI launch fix, OCC ordering, atomic `.env`, LRU locks |
| **1.5.17** | Security depth pass | `llm_url_policy`, graph path allowlist, `MATRYCA_MCP_ENABLED`, UI rate tiers, **453** tests |

Phases **9–14** narrative detail remains in [`ARCHITECTURE.md`](ARCHITECTURE.md) § Phase evolution.

---

## [2026-05-22] Phase 14d: Context Acceleration and TRIZ hardening

### Context

A **5,260-block** production page turned Phase 2 into a sequential GPU prefill bottleneck. Dynamic task instructions preceded page content, destroying llama.cpp KV-cache reuse. Detached daemon children missed repo `.env` when `cwd` was arbitrary.

### Solution

- `llm_context_payload.py` — Phase 1 summary substitution + semantic skeleton fallback.
- `prompt_layout.py` — `[SYSTEM] + [STABLE_PAGE] + [DYNAMIC_TASK]` ordering.
- `reload_plumber_dotenv()` — anchor `.env` to package repo root, re-read each sync cycle.

### Status

Shipped. **`tests/test_llm_context_payload.py`** added; suite grew to **317+** green at the time.

**Evolution (v1.8):** Phase 14d fixed Phase 2 indexing and token volume; v1.8 extends the same `[STABLE_PAGE] + [DYNAMIC_TASK]` contract to **bootstrap harvest**, **MapReduce**, and **multi-module cognitive pipelines** via `PagePromptSession` — see the [2026-05-27 v1.8 entry](#2026-05-27-v18--edge-computing--performance-16-gb--10k-pages) above.

---

## [2026-05-21] Phase 14c: Monolithic Sovereign UI

### Context

Retire fragmented Rich TUI; validate on a graph growing **1,426 → 3,862** connected pages under Phase 1 bootstrap.

### Defects crushed

- **Isolated token logging** — submodule loggers vs shared `TokenLogger` / `_save_cycle_checkpoint`.
- **JSON repair** — `json_repair.py` for local model grammar leakage.
- **Resilient structured output (TRIZ)** — [`resilience-llm-json-triz.md`](resilience-llm-json-triz.md): Gemma “tail of death” (`\n` loops), `MATRYCA_LLM_MAX_COMPLETION_TOKENS`, balanced-brace extraction, sanitization pipeline integrated with Path A/B in `llm_client.py`.
- **Non-atomic daemon state** — `save_daemon_state` tmp + `fsync` + `os.replace`; double-read on load.

### Status

Shipped. `matryca plumber status` → Uvicorn `:8500` + `frontend/dist/`.

---

## [2026-05-21] Phase 14: Engineering consolidation and native GraphRAG

### Context

Phase 1 rolling memory caused **~25 s** prefill per page and orphan-page hallucination loops when generative modules ran before catalog completion.

### Decisions

- **Strict phase separation** — `bootstrap_complete` wall between census and cognitive mutation.
- **Stateless Phase 1** — reset Instructor history per page (~2 s per file).
- **`semantic_clustering.py`** — Louvain communities (5–35 pages) with TF-IDF + Jaccard tags hybrid.

### Status

Shipped. Suite at **317** green (historical).

---

## [2026-05-21] Brand hardening: Matryca Plumber vs Matryca Brain

OSS rename to **Matryca Plumber**; `plumber_config.py`, `plumber_modules/` module plane; Brain reserved for Pro Nuitka binary.

**Status:** Shipped.

---

## [2026-05-21] — Phase 8: Structural quarantine

Malformed `((uuid))` on user pages crashed the daemon. Preflight `find_malformed_block_refs`, quarantine with `### Matryca Structural Lint`, `validate_block_refs=False` for warning-only appends.

**Status:** Shipped.

---

## [2026-05-21] — Matryca Plumber sovereign maintenance daemon

`MaintenanceDaemon`, env-gated `plumber_modules/`, Instructor `JSON_SCHEMA`, Ermes compression at 100k tokens.

**Status:** Shipped.

---

## [2026-05-19] — V1.4.0 Headless Revolution

Removed `LogseqClient` / `httpx`; all writes via `graph_dispatch` + `append_child_to_node`; `.matryca_xray_state.json`.

**Status:** Shipped.

---

## [2026-05-19] — V1.3.0 Fortress

`path_sandbox.py`, MCP lifespan teardown. Sandbox remains mandatory post-headless.

**Status:** Shipped (HTTP client superseded).

---

## [2026-05-19] — V1.0.1: 106k-token MCP stress test

MOC built with **synthetic parser UUIDs** in `((refs))` without persisted `id::`. Led to `synthetic_id` exposure, `assert_valid_block_refs_in_markdown`, and persist-first policy in `SYSTEM_PROMPT.md`.

**Status:** Shipped.

---

## [2026-05-17] — Foundation

Logseq OG as single system of record; FastMCP + Pydantic `OutlineNode`; external `logseq-matryca-parser`; `uv` + Makefile DX.

**Status:** Shipped.

---

## IP separation: open source vs commercial

| Capability | OSS (**Matryca Plumber**) | Commercial (**Matryca Brain**) |
|------------|---------------------------|--------------------------------|
| MARPA taxonomy, dangling healer, property hygiene, semantic routing | ✅ env-gated | ✅ |
| Twin Ingestion, Epistemic Guardian | ❌ | ✅ proprietary |

Enterprise placeholders in `.env.example` for Brain-only features are **not** loaded by `plumber_config.py` in OSS.

---

## Entry template

```markdown
## [YYYY-MM-DD] — Title

### Context
What problem triggered this entry?

### Decisions made
What was decided, rejected, or deferred?

### Status
Shipped | In progress | Superseded by [link]
```
