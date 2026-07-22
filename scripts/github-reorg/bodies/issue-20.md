# [EPIC] v2.0.0 — Shadow DB & Safe-Sync Architecture

## Context

Matryca Plumber is the local data infrastructure for headless AI agents interacting with Logseq. **v2.0.0** introduces the **Shadow DB**: a daemon-owned SQLite cache (`shadow.sqlite`) for sub-50ms hierarchical reads (FTS5 + recursive CTEs), without touching Logseq's internal indices.

**Visitor guide (start here):** [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md)  
**RFC & architecture debate:** [Discussion #19 — Core Architecture Evolution](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)  
**Maintainer blueprints:** [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md)

## Safe-Sync (read/write decoupling)

| Path | Rule |
|------|------|
| **READ** | Shadow DB syncs read-only from Markdown (Classic) or Markdown Mirror (Logseq DB) |
| **WRITE (Logseq OG)** | Append to `.md` + OCC — **done in v1.9.5** → #25 |
| **WRITE (Logseq DB)** | Official CLI/API only (`qmd`) — never native DB mutation |

Full contract: [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) § "LLM OS" / Safe-Sync · [`docs/openspec/llm-os-instructions.md`](docs/openspec/llm-os-instructions.md)

## Five preparation phases

| Phase | Scope | Primary issues |
|-------|--------|----------------|
| **0** | v1.9.12 prerequisites (#58, #59, env_parse) | Phase 0 tracking issue |
| **1** | `GraphRepository` — Markdown adapter, no default behavior change | #17 |
| **2** | Shadow incremental sync (`post_write` → `shadow.sqlite`) | #24 |
| **3** | Read routing behind `MATRYCA_SHADOW_DB_ENABLED` | #24 slices |
| **4** | Biological memory + Logseq DB Safe-Sync bridge | #25, #139 |

Details: [`ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md).

## Delivered in v1.9.x (not part of this epic)

| Release | Deliverable |
|---------|-------------|
| v1.9.2 | `llms.txt` agent-zero-friction |
| v1.9.5 | LLM OS Soft Gate + `bootstrap_status` — milestone **v1.9.6 - Agent UX** (#21, #22 closed) |
| v1.9.5 | Safe-Sync docs + Logseq OG write path — partial #25 |
| v1.11.2+ | Graph layer boundary (`post_write` port), `env_parse`, OCC ns parity |
| v1.12.0 | Prompt Clean Architecture, L0 safety, `AGENTS.md` router |

## v2 scaffold already in tree

| Artifact | Location |
|----------|----------|
| Shadow DDL | `src/shadow/schema.py` + `tests/test_shadow_schema.py` |
| Memory decay | `src/memory/decay.py` |

## Sub-issues (implementation tracking)

| Issue | Scope |
|-------|-------|
| #17 | `GraphRepository` abstraction (Markdown first, then Logseq DB) |
| #24 | Shadow DB read path (`shadow.sqlite`, FTS5, CTEs, background sync) — **closed at v2.0.0-alpha** |
| #25 | Safe-Sync write path (Logseq DB CLI bridge — OG path done) |
| #23 | Hardware profiler & LLM recommender (DX; independent) |
| #139 | Tana content-aware re-import (`--merge`) — v2 scope |

Phase tracking issues and slices: see [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md) (created by `scripts/populate_v2_preparation.sh`).

## Maintainer roadmaps (in-repo)

| Document | Scope |
|----------|-------|
| [`docs/roadmaps/ROADMAP_V2_PREPARATION.md`](docs/roadmaps/ROADMAP_V2_PREPARATION.md) | **Visitor SSOT** — five phases, DoD, contribute guide |
| [`docs/roadmaps/ROADMAP_V2_SHADOW_DB.md`](docs/roadmaps/ROADMAP_V2_SHADOW_DB.md) | Shadow DB schema, FTS5, sync checklist |
| [`docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](docs/roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md) | Nacre-inspired memory graph |
| [`docs/openspec/biological-memory.md`](docs/openspec/biological-memory.md) | Planned env vars + MCP `recall` contract |

## v2.0 rollout

| Track | Target | Status |
|-------|--------|--------|
| v2.0.0-alpha.5 | Experimental `shadow.sqlite` + opt-in env flag | **published** (PyPI `2.0.0a5`); hardening baseline |
| v2.0.0-beta.1 | Shadow read-path candidate only | **not released — readiness-gated**; flag remains default-off |
| v2.0.0-rc | MCP read traffic routed to Shadow DB by default | planned |
| v2.0.0-stable | Deprecate pure in-memory BM25 as default discovery path | planned |

## v2.0.0-beta.1 readiness (candidate only)

`v2.0.0-beta.1` does not expand the v2 scope: it covers the existing Shadow read path only. Logseq Markdown remains the system of record; non-ready Shadow states fall back to the established Markdown/BM25 paths; biological memory and Logseq DB Safe-Sync remain Phase 4 work.

| Gate | Required evidence |
|------|-------------------|
| Bounded parse containment | [#297](https://github.com/MarcoPorcellato/matryca-plumber/issues/297) merged; timeout or parser failure cannot publish a partial AST or Shadow generation; public diagnostics remain sanitized; installed-wheel smoke passes |
| Defect triage | No open P0/P1 issue in beta scope at cut time |
| Real-vault soak | Sanitized evidence for at least 24h, preferably 3–7 days: flag-off/on, restarts, watcher CRUD, recovery, and stable Markdown fingerprints |
| Upgrade and recovery | Installed-wheel `2.0.0a5` → `2.0.0b1` smoke preserves compatible data and fails safely on schema mismatch/recovery injection |
| Release gates | Full CI and final code audit pass against the release candidate |

The local SSOT for this gate is [`docs/quality/issue-bodies/v2-beta-readiness.md`](docs/quality/issue-bodies/v2-beta-readiness.md). No tag, PyPI upload, or default-on routing change is authorized by this section alone.

## Diagnostics note

There is **no** `matryca doctor` subcommand (see `llms.txt` §2.3). Shadow DB health checks will extend **preflight** / Sovereign UI surfaces instead.
