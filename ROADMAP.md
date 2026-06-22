# Matryca Plumber Roadmap

**North star:** [v2.0.0 — Shadow DB & Safe-Sync Architecture](https://github.com/MarcoPorcellato/matryca-plumber/milestone/3) ([Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20))

Matryca Plumber is local data infrastructure for headless AI agents working with Logseq. **v2.0.0** introduces the **Shadow DB**: a daemon-owned SQLite cache (`shadow.sqlite`) for sub-50ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices. A [`GraphRepository`](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) abstraction will let Markdown (Logseq OG) and Logseq DB backends coexist, while [**Safe-Sync**](https://github.com/MarcoPorcellato/matryca-plumber/issues/25) keeps writes on the correct path — append to `.md` with OCC for OG, official CLI only for Logseq DB.

Architecture debate and RFC: [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19).

*Status as of v1.10.6 — issue numbers link to GitHub; scope may shift as milestones close.*

---

## Short-term (now → v1.9.12 complete)

### Community & onboarding

- README narrative refresh — hook, comparison table, architecture moved below Quick Install
- Agent surface: [`llms.txt`](llms.txt), [`.well-known/llms.txt`](.well-known/llms.txt), [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md)
- Operator workflow in [CONTRIBUTING.md](CONTRIBUTING.md) — Discussions for RFCs, issues for trackable work
- “Test vault first” guidance in README (clone graph before pointing at production)
- Good-first issues live on GitHub — [open `good first issue` label](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) (#38, #43, #52, #53, #56, #69, #71, #85, #90–#92, #101–#105); maintainer blueprints in [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md)

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
- Centralize env parsing; ~~eliminate `type: ignore` suppressions~~ — **done** ([#60](https://github.com/MarcoPorcellato/matryca-plumber/issues/60); zero `# type: ignore` in `src/`)
- ~~Public API on `SessionAliasRegistry`~~ — scoped v1.9.14 helpers in `alias_state.py` (#64 partial); full upstream API deferred to v2.0
- Journal page detection in graph layer ([#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71))

---

## Medium-term (v1.9.x → v2.0-alpha)

| Initiative | Issue | Goal |
|------------|-------|------|
| Shadow DB read path | [#24](https://github.com/MarcoPorcellato/matryca-plumber/issues/24) | `shadow.sqlite`, FTS5, CTEs, background sync from Markdown |
| Biological memory layer | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Nacre-inspired decay/recall in `shadow.sqlite` — [`ROADMAP_V2_BIOLOGICAL_MEMORY.md`](docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md) |
| GraphRepository abstraction | [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) | Coexistent Markdown / SQLite backends |
| Hardware Profiler & LLM Recommender | [#23](https://github.com/MarcoPorcellato/matryca-plumber/issues/23) | Sovereign UI guidance for 16 GB CPU-only laptops |
| **v2.0.0-alpha** | Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) | Experimental `shadow.sqlite` behind opt-in env flag |

Deeper maintainer checklists (completed or in flight):

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
| v1.10.6 | Unified `platform_lock` flock (#40); hub page OCC (#34); contributor backlog hygiene (725+ tests) |
| v1.10.5 | `logseq-matryca-parser` 1.3.1 alignment; root public API imports; AST cache `discover_graph_files` (725+ tests) |
| v1.10.4 | CI Actions toolchain (`checkout@v7`, `dependency-review-action@v5`, `setup-uv@v8.2.0`); Sovereign UI frontend npm bumps; Dependabot weekly groups (725+ tests) |

---

## How to help

- **RFCs & architecture:** [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions)
- **Trackable work:** open [Issues](https://github.com/MarcoPorcellato/matryca-plumber/issues) — link PRs with `Fixes #N`
- **Good first issues:** [GitHub label filter](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) · [CONTRIBUTING.md](CONTRIBUTING.md) · [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) · `make check` before opening a PR
