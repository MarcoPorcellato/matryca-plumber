# Matryca Plumber Roadmap

**North star:** [v2.0.0 — Stable Shadow Read Path](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3) ([Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20))

Matryca Plumber is local data infrastructure for headless AI agents working with Logseq. **v2.0.0** introduces the **Shadow DB**: a daemon-owned SQLite cache (`shadow.sqlite`) for sub-50ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices. A [`GraphRepository`](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) abstraction will let Markdown (Logseq OG) and Logseq DB backends coexist, while [**Safe-Sync**](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) keeps writes on the correct path — append to `.md` with OCC for OG, official CLI only for Logseq DB.

Architecture debate and RFC: [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19).

*Status as of **2026-08-02** — `v2.0.0-beta.1` is the current public prerelease; the unreleased RC-target source now contains the default-on external Shadow/read-only architecture and retrieval hardening described below. Issue numbers link to GitHub; implementation does not imply release qualification.*

---

## v2.0.0-beta.1 — First public Shadow read-path beta

`v2.0.0-beta.1` is the first public beta of the **opt-in Shadow read path only**, published on PyPI as `2.0.0b1`. `MATRYCA_SHADOW_DB_ENABLED` remains default-off, Logseq Markdown remains the system of record, and every non-ready Shadow state falls back to the existing Markdown/BM25 paths. Biological memory and the Logseq DB Safe-Sync bridge remain Phase 4 work and are excluded.

| Release gate | Status |
|--------------|--------|
| Bounded page-parse containment ([#297](https://github.com/MarcoPorcellato/matryca-plumber/issues/297)) with no partial cache publication and safe fallback | **PASS** |
| No open P0/P1 defects in beta scope | **PASS** |
| Sanitized real-vault soak: at least 24h, preferably 3–7 days; flag-off/on, restart, watcher CRUD, recovery, and Markdown fingerprints | **PASS** — 24 hours, 144 cycles |
| Installed-wheel upgrade `2.0.0a5` → `2.0.0b1`, including schema mismatch and recovery | **PASS** |
| Full CI and final code audit against the release candidate | **PASS with accepted evidence boundary** |

**Decision record:** [`docs/quality/issue-bodies/v2-beta-readiness.md`](docs/quality/issue-bodies/v2-beta-readiness.md). All beta publication gates passed. Re-qualification against the released source remains mandatory before any default-on change.

---

## v2.0.0 RC and stable promotion

The `v2.0.0` stable scope is the Shadow DB read path. The next promotion is
`v2.0.0-rc.1`, where unset configuration prefers health-gated Shadow reads and
explicit `MATRYCA_SHADOW_DB_ENABLED=false` restores the legacy path. Stable
`v2.0.0` follows only after RC observation and deprecates in-memory BM25 as the
default discovery path while retaining it as a mandatory fallback.

Biological memory, Logseq DB Safe-Sync writes, content-aware Tana merge, and
independent DX tracks are deferred to `v2.1.0` or later. The fail-closed
qualification matrix is
[`docs/quality/issue-bodies/v2-rc-stable-readiness.md`](docs/quality/issue-bodies/v2-rc-stable-readiness.md).
The exact public-beta wheel has passed its fresh installed-wheel gate and is in
a restart-resilient 72-hour soak; its sanitized
[`running evidence record`](docs/quality/SHADOW_DB_EXACT_BETA_72H_SOAK_2026-07-30.md)
remains non-terminal.

The unreleased RC-target source has merged Strict Read Only enforcement,
external per-user Shadow cache routing, default-on Shadow with explicit opt-out,
the read-only observer daemon, deterministic graph-immutability qualification,
and the bounded 8,192-entry BM25 result cache (#354–#366). These source changes
do not inherit the beta.1 soak result: the published beta is opt-in and
graph-local, while the next candidate is default-on and external.

Promotion therefore remains deliberately sequential:

1. record terminal `PASS` or `FAIL` for the exact `2.0.0b1` soak;
2. complete every remaining Gate A row on the exact candidate, including
   upgrade/rollback, defect disposition, default-on/read-only installed-wheel
   proof, operator-contract synchronization, and release build/platform checks;
3. publish `v2.0.0-rc.1` so prerelease users can exercise the complete external
   Shadow path;
4. complete Gate B on that published RC, including at least seven days of
   observation and the default-on/read-only soaks;
5. publish stable `v2.0.0` only after every Gate B row passes.

---

## v2.0.0-alpha.5 — Hardening campaign close (#261)

| Deliverable | Status |
|-------------|--------|
| CTE depth-truncation status ([#289](https://github.com/MarcoPorcellato/matryca-plumber/issues/289) / [#291](https://github.com/MarcoPorcellato/matryca-plumber/pull/291)) | **Done** |
| State API path redaction ([#293](https://github.com/MarcoPorcellato/matryca-plumber/issues/293) / [#294](https://github.com/MarcoPorcellato/matryca-plumber/pull/294)) | **Done** |
| Axes 5–7 audit probes ([#290](https://github.com/MarcoPorcellato/matryca-plumber/pull/290), [#292](https://github.com/MarcoPorcellato/matryca-plumber/pull/292), [#295](https://github.com/MarcoPorcellato/matryca-plumber/pull/295)) | **Done** |
| Tracker [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261) closed — no open P0/P1 | **Done** |

**Published:** [`v2.0.0-alpha.5`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha.5) · PyPI `matryca-plumber==2.0.0a5` · superseded by `v2.0.0-beta.1` / `2.0.0b1` for new prerelease installs.

---

## v2.0.0-alpha.4 — Shadow FTS query length bound ✓ tagged

| Deliverable | Status |
|-------------|--------|
| FTS query length bound ([#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279) / [#286](https://github.com/MarcoPorcellato/matryca-plumber/pull/286)) | **Done** |
| Axis 4 FTS5 gate fully green ([#287](https://github.com/MarcoPorcellato/matryca-plumber/pull/287) — #278 probe corrected) | **Done** — **52 pass, 0 xfail** |

**Tag:** `v2.0.0-alpha.4` · PyPI `matryca-plumber==2.0.0a4` · **superseded by v2.0.0-alpha.5** for new installs. Hardening Axes 5–7 completed in alpha.5 ([#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261)).

---

## v2.0.0-alpha.3 — Shadow FTS hyphenated query fix ✓ tagged

| Deliverable | Status |
|-------------|--------|
| Hyphenated FTS user tokens ([#277](https://github.com/MarcoPorcellato/matryca-plumber/issues/277) / [#282](https://github.com/MarcoPorcellato/matryca-plumber/pull/282)) | **Done** |
| Axis 4 FTS5 audit ([#280](https://github.com/MarcoPorcellato/matryca-plumber/pull/280)) — initial **27 pass + 3 xfail**; alpha.3 gate **28 pass + 2 xfail** ([#278](https://github.com/MarcoPorcellato/matryca-plumber/issues/278), [#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279) open) | **Done** (audit + #277 fix) |

**Tag (after merge):** `v2.0.0-alpha.3` · PyPI `matryca-plumber==2.0.0a3` · **superseded by v2.0.0-alpha.4** for new installs. **Not an RC** — Axes 5–7 open on [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261); Axis 4 completed in alpha.4 ([#279](https://github.com/MarcoPorcellato/matryca-plumber/issues/279) fix + [#278](https://github.com/MarcoPorcellato/matryca-plumber/issues/278) probe correction).

---

## v2.0.0-alpha.2 — Shadow DB rename fix & routing audit ✓ tagged

| Deliverable | Status |
|-------------|--------|
| Incremental rename stale-owner fix ([#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272) / [#274](https://github.com/MarcoPorcellato/matryca-plumber/pull/274)) | **Done** |
| Axis 2 parity audit probes ([#275](https://github.com/MarcoPorcellato/matryca-plumber/pull/275) prerequisite: [#274](https://github.com/MarcoPorcellato/matryca-plumber/pull/274)) | **Done** |
| Axis 3 routing & fallback audit — 19 probes, zero findings ([#275](https://github.com/MarcoPorcellato/matryca-plumber/pull/275)) | **Done** |
| OKF knowledge bundle pilots (experimental) ([#268](https://github.com/MarcoPorcellato/matryca-plumber/pull/268), [#270](https://github.com/MarcoPorcellato/matryca-plumber/pull/270)) | **Done** |

**Tag (after merge):** `v2.0.0-alpha.2` · PyPI `matryca-plumber==2.0.0a2` · **superseded by v2.0.0-alpha.3** for new installs (`2.0.0a0`–`2.0.0a2` remain on PyPI). **Not an RC** — Axes 4–7 open on [#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261).

---

## v2.0.0-alpha.1 — Shadow DB Axis 1 hardening ✓ tagged

| Deliverable | Status |
|-------------|--------|
| Cross-process writer coordination — advisory flock + SQLite `busy_timeout` ([#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262)) | **Done** |
| Meta/pages health validation — mismatch → `stale` ([#264](https://github.com/MarcoPorcellato/matryca-plumber/issues/264)) | **Done** |
| Axis 1 audit probes — zero xfails ([#261](https://github.com/MarcoPorcellato/matryca-plumber/issues/261), [#263](https://github.com/MarcoPorcellato/matryca-plumber/pull/263)) | **Done** |
| Maintainer doc sync + release notes | **Done** |

**Tag (after merge):** `v2.0.0-alpha.1` · PyPI `matryca-plumber==2.0.0a1` · **superseded by v2.0.0-alpha.3** for new installs (`2.0.0a0` remains on PyPI).

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
| **v2.0.0-alpha.5** | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Experimental `shadow.sqlite` behind opt-in env flag | **published** |
| **v2.0.0-beta.1** | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | First public Shadow read-path beta; flag remains default-off | **published** |

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
