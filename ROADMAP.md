# Matryca Plumber Roadmap

**North star:** [v2.0.0 — Shadow DB & Safe-Sync Architecture](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3) ([Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20))

Matryca Plumber is local data infrastructure for headless AI agents working with Logseq. **v2.0.0** introduces the **Shadow DB**: a daemon-owned SQLite cache (`shadow.sqlite`) for sub-50ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices. A [`GraphRepository`](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) abstraction will let Markdown (Logseq OG) and Logseq DB backends coexist, while [**Safe-Sync**](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) keeps writes on the correct path — append to `.md` with OCC for OG, official CLI only for Logseq DB.

Architecture debate and RFC: [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19).

*Status as of **v2.0.0-alpha.1** (2026-07-18) — issue numbers link to GitHub; scope may shift as milestones close.*

---

## v2.0.0-alpha.1 — Shadow DB Axis 1 hardening ✓ release PR

| Deliverable | Status |
|-------------|--------|
| Cross-process writer coordination — advisory flock + SQLite `busy_timeout` ([#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262)) | **Done** |
| Meta/pages health validation — mismatch → `stale` ([#264](https://github.com/MarcoPorcellato/matryca-plumber/issues/264)) | **Done** |
| Axis 1 audit probes — zero xfails ([#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261), [#263](https://github.com/MarcoPorcellato/matryca-plumber/pull/263)) | **Done** |
| Maintainer doc sync + release notes | **Done** |

**Tag (after merge):** `v2.0.0-alpha.1` · PyPI `matryca-plumber==2.0.0a1` · **supersedes** [`v2.0.0-alpha`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha) / `2.0.0a0` for new installs (`2.0.0a0` remains on PyPI).

---

## v2.0.0-alpha — Shadow DB read path (opt-in) ✓ tagged

| Deliverable | Status |
|-------------|--------|
| Shadow bootstrap, reconciliation, runtime gating ([#176](https://github.com/MarcoPorcellato/matryca-plumber/issues/176), [#248](https://github.com/MarcoPorcellato/matryca-plumber/issues/248)) | **Done** |
| FTS5 BM25 + recursive CTE read routing behind `MATRYCA_SHADOW_DB_ENABLED` ([#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177)) | **Done** |
| Sovereign UI `/api/state.shadow_db` health row ([#185](https://github.com/MarcoPorcellato/matryca-plumber/issues/185)) | **Done** |
| Duplicate block UUID diagnostics ([#251](https://github.com/MarcoPorcellato/matryca-plumber/issues/251)) | **Done** |
| Operator docs — `llms.txt` §2.6, v2 roadmaps | **Done** |

**Tag:** [`v2.0.0-alpha`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha) · PyPI `matryca-plumber==2.0.0a0` · **superseded by v2.0.0-alpha.1** for new installs.

**Next v2 slice:** Phase 4 biological memory + Logseq DB Safe-Sync ([#178](https://github.com/MarcoPorcellato/matryca-plumber/issues/178), [#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)).

---

## v1.14.0 — Catalog write-safety & Clean Code Tier F closures ✓ on `main`

| Deliverable | Status |
|-------------|--------|
| `MasterCatalog` remove→upsert→save integrity + corrupt quarantine ([#210](https://github.com/MarcoPorcellato/matryca-plumber/issues/210)) | **Done** |
| File watcher `on_moved` + single debounce scheduler | **Done** |
| Leaf-module dependency direction (4/5 import cycles) ([#215](https://github.com/MarcoPorcellato/matryca-plumber/issues/215)) | **Done** |
| Tier F GFI: `#170`/`#171`/`#172`/`#173` (env_parse + boundary + clamps) | **Done** |

**Recommended semver:** **minor 1.14.0** — operator-visible catalog/watcher reliability + architecture hardening; no intentional MCP/CLI break.

---

## v1.13.1 — Logseq Matryca Parser 1.6.0 alignment ✓ on `main`

| Deliverable | Status |
|-------------|--------|
| Parser pin `logseq-matryca-parser>=1.6.0` | **Done** |
| `_headless_append_child` newline parity (parser 1.4.2) | **Done** |
| `load_alias_registry` `SessionAliasRegistryError` mapping | **Done** |

**Recommended semver:** **patch 1.13.1** — dependency alignment + headless write robustness; no MCP/CLI surface change.

---

## v1.13.0 — Daemon & dispatch modularization (v2 Phase 0–1) ✓ on `main`

| Deliverable | Status |
|-------------|--------|
| `maintenance_daemon` SRP — six `daemon_*` modules + orchestrator | **Done** ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58)) |
| `graph_dispatch` handler registry — five `dispatch_*_handlers.py` slices | **Done** ([#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)) |
| `GraphReadPort` + `MarkdownGraphRepository` (v2 Phase 1) | **Done** ([#179](https://github.com/MarcoPorcellato/matryca-plumber/issues/179), [#180](https://github.com/MarcoPorcellato/matryca-plumber/issues/180)) |
| Community onboarding — README, `FIRST_CONTRIBUTION.md`, CoC contact | **Done** |
| Issue triage pass (2026-07-01) | **Done** — log [`docs/quality/ISSUE_TRIAGE_2026-07-01.md`](docs/quality/ISSUE_TRIAGE_2026-07-01.md) |

**Recommended semver:** **minor 1.13.0** — internal modularization + v2 read port; no intentional PyPI CLI/MCP break for vault operators.

**Superseded by:** v2.0.0-alpha shadow read path ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) closed) — see [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md).

---

## v1.12.0 — Prompt Clean Architecture (plan v3) ✓ on `main`

| Deliverable | Status |
|-------------|--------|
| Tier-1 domain builders + `prompts/core.py` DI | **Done** ([#161](https://github.com/MarcoPorcellato/matryca-plumber/pull/161)) |
| L0 `validate_llm_write_diff` before semantic commits | **Done** ([#158](https://github.com/MarcoPorcellato/matryca-plumber/pull/158)) |
| `SYSTEM_PROMPT.md` fragment assembly + CI hash | **Done** ([#163](https://github.com/MarcoPorcellato/matryca-plumber/pull/163)) |
| `AGENTS.md` router + `make agents-check` | **Done** ([#160](https://github.com/MarcoPorcellato/matryca-plumber/pull/160)) |
| Cursor rule `11-prompt-maintainer` | **Done** ([#162](https://github.com/MarcoPorcellato/matryca-plumber/pull/162)) |
| [`docs/PROMPT_ARCHITECTURE.md`](docs/PROMPT_ARCHITECTURE.md) | **Done** (maintainer SSOT) |

**Recommended semver:** **minor 1.12.0** — new maintainer contracts and L0 behavioral gate; no intentional PyPI CLI/MCP break for vault operators.

**v4 backlog (not in v3):**

- **`llms.txt` §2.4 tiering** — reduce external-agent token waste (highest remaining prompt impact).
- **`check_version_consistency.py`** — optional `llms` byte-identity + `agent-onboarding.md` header guard (partially covered by `agents-check`).
- **Cursor rules `00` / `01` / `03` polish** — Karpathy checklist, paradigm SSOT links, HTTP vs headless clarification.

---

## Short-term (now → v1.9.12 complete)

### Community & onboarding

- README narrative refresh — hook, comparison table, architecture moved below Quick Install
- Agent surface: [`llms.txt`](llms.txt), [`.well-known/llms.txt`](.well-known/llms.txt), [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md)
- Operator workflow in [CONTRIBUTING.md](CONTRIBUTING.md) — Discussions for RFCs, issues for trackable work
- “Test vault first” guidance in README (clone graph before pointing at production)
- Good-first issues live on GitHub — [open `good first issue` label](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) (#43, #52, #114, #125–#129, #168–#173); maintainer blueprints in [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md)
- **Tier F Clean Code** — [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168)–[#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173); [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md)
- **v2.0 preparation index** — [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md); phase issues [#174](https://github.com/MarcoPorcellato/matryca-plumber/issues/174)–[#178](https://github.com/MarcoPorcellato/matryca-plumber/issues/178); slices [#179](https://github.com/MarcoPorcellato/matryca-plumber/issues/179)–[#186](https://github.com/MarcoPorcellato/matryca-plumber/issues/186); [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md)
- ~~CI `StarletteDeprecationWarning` in test client~~ — **done (main):** [#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118) via [#122](https://github.com/MarcoPorcellato/matryca-plumber/pull/122) (@blackwolf225)

### Tech debt & integrity (prerequisite for v2.0)

**[v1.9.10 — Concurrency & Data Integrity](https://github.com/MarcoPorcellato/matryca-plumber/milestone/6)** ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34)–[#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45))

- ~~OCC gaps on hub pages, `json_flock` parity with `page_rmw_lock`~~ — **done (v1.10.6):** hub page OCC via `write_generated_hub_page` ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34)); unified `platform_lock` flock ([#40](https://github.com/MarcoPorcellato/matryca-plumber/issues/40))
- ~~Daemon shutdown suppresses final save errors~~ — **done (main):** [#44](https://github.com/MarcoPorcellato/matryca-plumber/issues/44) via [#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100) (@gaoflow)
- ~~Atomic JSON writes for link registry and daemon state~~ — **done (v1.10.0):** link registry `atomic_write_bytes` ([#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)); daemon state already atomic
- ~~Catalog cache coherence under concurrent disk writers~~ — **done (v1.10.0):** master catalog load flock ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)), merge-on-save ([#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)), harvest catalog/page drift guard on OCC abort ([#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37))

**[v1.9.11 — Performance & I/O](https://github.com/MarcoPorcellato/matryca-plumber/milestone/7)** ([#46](https://github.com/MarcoPorcellato/matryca-plumber/issues/46)–[#56](https://github.com/MarcoPorcellato/matryca-plumber/issues/56), [#69](https://github.com/MarcoPorcellato/matryca-plumber/issues/69))

- Incremental AST reload instead of full-vault rescans
- Catalog and alias hot-path optimizations; checkpoint debounce
- ~~Skip Phase 2 LLM work on daily journals~~ — **done (v1.9.15):** [#67](https://github.com/MarcoPorcellato/matryca-plumber/issues/67) closed
- ~~Entity consolidation journal skip~~ — **done (v1.9.14):** [#68](https://github.com/MarcoPorcellato/matryca-plumber/issues/68) closed
- ~~Phase-2 progress denominator excludes journals~~ — **done (v1.9.15):** [#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) closed

**[v1.9.12 — Code Perfection & Tech Debt](https://github.com/MarcoPorcellato/matryca-plumber/milestone/8)** ([#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)–[#64](https://github.com/MarcoPorcellato/matryca-plumber/issues/64), [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71), [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85))

- Split `maintenance_daemon.py`; handler registry for `graph_dispatch.py`
- `BootstrapHarvestStatus` Literal dedup ([#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85), good-first slice of [#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62))
- ~~Centralize env parsing~~ — **done (v1.11.2):** `src/utils/env_parse.py` ([#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62) partial); ~~eliminate `type: ignore` suppressions~~ — **done** ([#60](https://github.com/MarcoPorcellato/matryca-plumber/issues/60); zero `# type: ignore` in `src/`)
- ~~Public API on `SessionAliasRegistry` (plumber)~~ — **done:** [#165](https://github.com/MarcoPorcellato/matryca-plumber/pull/165) closes [#64](https://github.com/MarcoPorcellato/matryca-plumber/issues/64); upstream parser API → [#167](https://github.com/MarcoPorcellato/matryca-plumber/issues/167)
- ~~Journal page detection in graph layer~~ — **done (v1.11.2 partial):** [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) — `is_journal_page_title_in_index()` in `alias_index`; cached wrapper in `generational_cache`

**Expert Architectural Audit 2026-06** — triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md). Four findings were already closed or tracked; eight new issues opened:

| Issue | Area |
|-------|------|
| [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132), [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133) | Concurrency — ~~`lock_backoff` downgrade~~ **done (v1.11.2)**, ~~`graph_dispatch` resolve/write TOCTOU~~ **done (v1.11.2)** |
| [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135)–[#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137) | Performance — Tana RAM peak, ~~generational cache LRU~~ **done (v1.11.2)**, ~~Phase 2 progress UX~~ **done (v1.11.2)** |
| [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134), [#138](https://github.com/MarcoPorcellato/matryca-plumber/issues/138) | Tech debt — ~~graph→daemon post-write inversion~~ **done (v1.11.2)**, ~~TUI state dedup load~~ **done (v1.11.2)** |
| [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) | v2.0 — Tana content-aware re-import (`--merge`) |

**Repomix Architectural Audit 2026-06** — triage: [`docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md`](docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md). Three new issues ([#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142)); vector RAM tracked on existing [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51).

---

## Medium-term (v2.0-alpha → rc)

**Visitor guide:** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md) — five phases, Definition of Done, contribute guide · [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md)

| Initiative | Issue | Goal | Status |
|------------|-------|------|--------|
| Shadow DB read path | [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) | `shadow.sqlite`, FTS5, CTEs, background sync from Markdown | **shipped** (`v2.0.0-alpha`) |
| Biological memory layer | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Nacre-inspired decay/recall in `shadow.sqlite` — [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md) | Phase 4 |
| GraphRepository abstraction | [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) | Coexistent Markdown / SQLite backends | read port **done** |
| Hardware Profiler & LLM Recommender | [#23](https://github.com/MarcoPorcellato/matryca-plumber/issues/23) | Sovereign UI guidance for 16 GB CPU-only laptops | planned |
| **v2.0.0-alpha** | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Experimental `shadow.sqlite` behind opt-in env flag | **tagged** |

Deeper maintainer checklists (completed or in flight):

- [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md) — **v2 visitor SSOT** (five phases, Safe-Sync, semver rollout)
- [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md) — phase/slice issue blueprints + verify commands
- [`docs/roadmaps/ROADMAP_LLM_WIKI.md`](docs/roadmaps/ROADMAP_LLM_WIKI.md) — LLM-Wiki baseline (done)
- [`docs/roadmaps/ROADMAP_IRONCLAD_SHIELD.md`](docs/roadmaps/ROADMAP_IRONCLAD_SHIELD.md) — resilience and safety hardening
- [`docs/roadmaps/ROADMAP_V2_SHADOW_DB.md`](docs/roadmaps/ROADMAP_V2_SHADOW_DB.md) — v2.0 Shadow DB read path ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24))
- [`docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md) — v2.0 biological memory layer (Nacre-inspired, depends on Shadow DB)

---

## Long-term (v2.0 stable)

| Track | Target |
|-------|--------|
| **v2.0.0-rc** | MCP read traffic routed to Shadow DB by default |
| **v2.0.0-stable** | Deprecate pure in-memory BM25 as default discovery path |
| **Safe-Sync** | Logseq DB write path via official CLI only ([#25](https://github.com/MarcoPorcellato/matryca-plumber/issues/25)) |

Safe-Sync contract (read/write decoupling):

| Path | Rule |
|------|------|
| **READ** | Shadow DB syncs read-only from Markdown (Classic) or Markdown Mirror (Logseq DB) |
| **WRITE (Logseq OG)** | Append to `.md` + OCC — shipped in v1.9.5 |
| **WRITE (Logseq DB)** | Official CLI/API only — never native DB mutation |

Full spec: [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) § "LLM OS" / Safe-Sync · [`docs/openspec/llm-os-instructions.md`](docs/openspec/llm-os-instructions.md)

---

## Already delivered in v1.9.x

Not backlog — context for where we are today:

| Release | Deliverable |
|---------|-------------|
| v1.9.2 | `llms.txt` agent-zero-friction distribution |
| v1.9.5 | LLM OS Soft Gate, `bootstrap_status`, Safe-Sync OG write path |
| v1.9.9 | Security & Sandbox milestone |
| v1.9.13 | Enterprise Resilience (704+ tests, sandbox/RAG/automation hardening) |
| v1.9.14 | Contributor readiness (#62/#64 tech debt), journal-aware Phase 2 clustering, good-first issue blueprints (710+ tests) |
| v1.9.15 | Mypy strict `#60` (zero `src/` ignores); journal Phase-2 semantic bypass with Phase-1 AST/OCC preserved (712+ tests) |
| v1.10.0 | Catalog/registry integrity (#35–#37, #41); OSS/GitHub hygiene (PR template, CodeQL, frontend ESLint); `make test-fast` local gate; dependency advisory bumps (720+ tests) |
| v1.10.3 | Sovereign UI non-blocking config saves; strict Pydantic LLM/outline contracts; recursive OpenAI strict JSON Schema; flock sidecars `0o600` (725+ tests) |
| v1.11.2 | **Graph layer boundary refactor** — `post_write` port ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134)); canonical graph modules; generational + block-vector LRU; OCC `st_mtime_ns` page writes; `env_parse`; observability logging (879+ tests) |
| v1.14.0 | Catalog write-safety + watcher `on_moved` + leaf-module cycles + Tier F `#170`–`#173` |
| **v2.0.0-alpha.1** | Shadow DB Axis 1 hardening — writer flock (#262), meta/pages health (#264) |
| **v2.0.0-alpha** | Shadow DB opt-in read cache — FTS5/CTE routing, Sovereign UI health, duplicate UUID diagnostics ([#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24), [#177](https://github.com/MarcoPorcellato/matryca-plumber/issues/177), [#251](https://github.com/MarcoPorcellato/matryca-plumber/issues/251)) |
| v1.13.1 | `logseq-matryca-parser` 1.6.0 alignment — 1.4.2 splice/X-Ray fixes; headless newline parity |
| v1.13.0 | Daemon/dispatch modularization + `GraphReadPort` (v2 Phase 0–1) |
| v1.11.1 | `logseq-matryca-parser` 1.4.0 alignment — canonical page iteration, case-insensitive tag/search, watcher delete/move, SYNAPSE embed safety (879+ tests) |
| v1.11.0 | **Tana workspace JSON import** — `ijson` streaming, hybrid placement, `config.edn` journals, depth-split, `tana-id` idempotent writes, CLI `matryca import tana`, MCP `import_tana` (879+ tests) |
| v1.10.6 | Unified `platform_lock` flock (#40); hub page OCC (#34); contributor backlog hygiene (725+ tests) |
| v1.10.5 | `logseq-matryca-parser` 1.3.1 alignment; root public API imports; AST cache `discover_graph_files` (725+ tests) |
| v1.10.4 | CI Actions toolchain (`checkout@v7`, `dependency-review-action@v5`, `setup-uv@v8.2.0`); Sovereign UI frontend npm bumps; Dependabot weekly groups (725+ tests) |
---

## How to help

- **RFCs & architecture:** [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions)
- **Trackable work:** open [Issues](https://github.com/MarcoPorcellato/matryca-plumber/issues) — link PRs with `Fixes #N`
- **Good first issues:** [GitHub label filter](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) · [CONTRIBUTING.md](CONTRIBUTING.md) · [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) · `make check` before opening a PR
