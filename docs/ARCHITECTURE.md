# Matryca Plumber — System Architecture

**Version:** 1.12.0 (plan v3 — Tier-1 prompt Clean Architecture + L0 write safety + SYSTEM_PROMPT fragment assembly + AGENTS.md router) · ships on top of 1.11.2 (graph layer boundary + bounded RAM + OCC ns parity)  
**Package:** `matryca-plumber` on PyPI  
**Audience:** maintainers, contributors, and operators integrating Logseq OG with local LLMs

This document is the engineering contract for **Matryca Plumber**: an enterprise-grade, **local-first background AI daemon** that mutates Logseq OG Markdown on disk. It is not a Logseq plugin, not a cloud service, and not dependent on Logseq HTTP JSON-RPC. Humans and the daemon co-edit the same `.md` trees; safety is enforced through **AST parity**, **optimistic concurrency control (OCC)**, **path sandboxing**, and operator-visible **Trust & Safety** tiers.

For the maintainer timeline and crushed bottlenecks, see [`PROJECT_DIARY.md`](PROJECT_DIARY.md). For agent discipline at inference time, see [`SYSTEM_PROMPT.md`](../SYSTEM_PROMPT.md). For **Clean Architecture** boundaries on prompts (Tier-1 / L0 / Tier-2), see [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md). For **repo-wide** Clean Code & Clean Architecture (Uncle Bob, SOLID, layer boundaries), see [`CLEAN_CODE_ARCHITECTURE.md`](CLEAN_CODE_ARCHITECTURE.md).

---

## Clean Architecture map (repo-wide)

Matryca maps Robert C. Martin's concentric rings to Python packages. **Dependencies point inward:** frameworks (FastMCP, FastAPI) → adapters (`graph_dispatch`, `mcp_server`, `cli`) → use cases (`maintenance_daemon`, `plumber_modules`) → domain (`src/graph/`, `safety/validators`, `utils/env_parse`) → entities (Logseq blocks, Pydantic lint models).

| Enforcement | Mechanism |
|-------------|-----------|
| Graph layer isolation | `tests/test_graph_layer_boundary.py` — no `graph` → `agent` / `daemon` imports |
| Prompt domain isolation | `tests/test_daemon_prompts.py` — `*/prompts.py` imports only `prompts/core.py` |
| Fat modules, thin edges | MCP/CLI delegate to `graph_dispatch` / `graph/*` (see [`CONTRIBUTING.md`](../CONTRIBUTING.md)) |

Full contributor SSOT: [`CLEAN_CODE_ARCHITECTURE.md`](CLEAN_CODE_ARCHITECTURE.md). Prompt-specific tiers remain in [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md). **v2 preparation:** [`roadmaps/ROADMAP_V2_PREPARATION.md`](roadmaps/ROADMAP_V2_PREPARATION.md) · [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) · Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20).

---

## Executive summary

Matryca Plumber evolved from an MCP-first bridge into a **three-surface runtime** that shares one headless mutation plane:

| Surface | Technology | Primary role |
|---------|------------|--------------|
| **Maintenance daemon** | Python (`MaintenanceDaemon`) | Autonomous duty-cycle scans, semantic indexing, cognitive lint, ledger checkpoints |
| **Sovereign UI** | React SPA + FastAPI (`ui_server.py`) | Loopback control room: telemetry, Trust & Safety toggles, daemon lifecycle, `.env` hot-swap |
| **MCP sidecar** | FastMCP stdio (`main.py`) | Optional tool host for Claude Desktop, Cursor, **Hermes Agent**, and other MCP clients — **same `graph_dispatch` contract** |

**FastMCP is auxiliary.** The product’s center of gravity is `matryca plumber start` plus the Sovereign UI. MCP attaches the identical read/write path when an external host spawns `matryca-plumber` without CLI-shaped arguments.

```mermaid
flowchart TB
  subgraph clients [Operator and agent surfaces]
    Human[Human operator Logseq desktop]
    UI[Sovereign UI React plus FastAPI]
    Daemon[MaintenanceDaemon background]
    MCP[MCP host Claude Cursor etc]
    CLI[matryca CLI uvx matryca-plumber]
  end

  subgraph plane [Shared headless mutation plane]
    Dispatch[graph_dispatch.py]
    Parser[logseq-matryca-parser]
    Locks[OCC plus page_rmw_lock\nplus platform_lock flock]
  end

  Vault[(LOGSEQ_GRAPH_PATH\npages journals cache ledgers)]

  Human <-->|"co-edit md"| Vault
  UI -->|"start stop config telemetry"| Daemon
  Daemon --> Dispatch
  MCP --> Dispatch
  CLI --> Dispatch
  Dispatch --> Parser
  Dispatch --> Locks
  Locks --> Vault
```

**Quality bar:** **974+** pytest targets passing (70% coverage gate on `src`), **Mypy strict** on `src` and `tests` with **zero `# type: ignore` in `src/`** ([#60](https://github.com/MarcoPorcellato/matryca-plumber/issues/60)), Ruff lint/format clean via `make ci`; local iteration via `make test-fast` (`NUM_WORKERS` default `4`, no coverage, skips `tests/slow/`); slow perf tests via `make perf` (`pytest -m slow`). Maintainer gates: `make agents-check`, `make check-system-prompt`.

**v1.8 focus:** Run indefinitely on a **16 GB CPU-only laptop** with **≤10k pages** — KV-cache-aligned prompts, bounded RAM, cooperative bootstrap I/O. See [Edge computing & performance (v1.8)](#edge-computing--performance-v18).

**v1.9 focus:** **Structural graph hygiene** without new LLM cognitive modules — zero-LLM link rot detection, OCC-safe `dead-link::` / `missing-asset::` flags, agent-native CLI (`--json`, `context load`, `read subtree`), and Journey Log visibility in today's journal. See [Structural link verification (v1.9)](#structural-link-verification-v19) and [Agent-centric DX (v1.9)](#agent-centric-dx-v19).

**v1.9.2 focus:** **Agent-zero-friction distribution** — canonical [`llms.txt`](../llms.txt) / [`.well-known/llms.txt`](../.well-known/llms.txt) for external LLM hosts, PyPI `uvx` execution contract, lockfile security refresh (`aiohttp` ≥3.14.0), and Dependabot `uv.lock` auto-sync in CI. See [Agent onboarding (v1.9.2)](#agent-onboarding-v192) and [Release engineering](#release-engineering).

**v1.9.3 focus:** **Live telemetry** for the Sovereign UI — 5s HTTP polling, daemon heartbeat checkpoints under `threading.Lock` + immutable JSON snapshots, API merge of ops-log token totals, `daemon_pid` auto-unfreeze. Spec: [`openspec/live-telemetry-ui.md`](openspec/live-telemetry-ui.md).

**v1.9.4 focus:** **Journey Log consolidation** — one cumulative `- 🤖 Matryca Activity` bullet per calendar day (`DaemonState.journey_day` ledger + `upsert_matryca_activity_block`); idle cycles skip journal writes; legacy `##` sections stripped on first upsert. Spec: [`openspec/agent-dx.md`](openspec/agent-dx.md) §4.

**v1.9.5 focus:** **LLM OS agent contract** — two-tier Gardener vs Cognitive Agent discipline, Master Index **Soft Gate** (Human-in-the-Loop), `read_graph_data` / `bootstrap_status` Phase 1 semaphore, Safe-Sync read/write rules. Spec: [`openspec/llm-os-instructions.md`](openspec/llm-os-instructions.md); cognitive law in [`SYSTEM_PROMPT.md`](../SYSTEM_PROMPT.md) § "LLM OS".

**v1.10.0 focus:** **Catalog & registry integrity** — `master_catalog.json` load/save under `cross_process_json_flock` with merge-on-save ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35), [#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)); bootstrap harvest skips catalog upsert when semantic index append OCC-aborts ([#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37)); link registry persistence via `atomic_write_bytes` ([#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)). **Journal Phase-2 bypass (v1.9.15)** — daily notes under `journals/` receive structural indexing only; semantic LLM indexing and dual embeddings are skipped. **Mypy strictness (#60)** — zero `# type: ignore` in `src/`. See [Journal pages — structural-only indexing](#journal-pages--structural-only-indexing), [JSON sidecar concurrency](#json-sidecar-concurrency-v1100), and [`CONTRIBUTING.md`](../CONTRIBUTING.md#strict-typing-zero-mypy-suppressions-in-src).

**v1.10.3 focus:** **Sovereign UI resilience & LLM contract hardening** — config/graph-path saves offloaded from the FastAPI event loop (`asyncio.to_thread`); rotating Loguru at UI startup; Pydantic `extra="forbid"` on plumber/outline structured models; recursive OpenAI strict JSON Schema generation; adaptive `max_tokens` / `max_completion_tokens`; flock sidecar files created as `0o600`. Spec: [`openspec/live-telemetry-ui.md`](openspec/live-telemetry-ui.md#v1103-non-blocking-config-saves), [`resilience-llm-json-triz.md`](resilience-llm-json-triz.md).

**v1.12.0 focus:** **Prompt Clean Architecture (plan v3)** — Tier-1 domain builders (`src/agent/prompts/core.py`, `*/prompts.py`) with constructor injection on `InstructorLLMClient`; **L0 hard rejection** (`src/graph/safety/validators.py`) before semantic index commits; **`SYSTEM_PROMPT.md` assembly** from `docs/openspec/agent/` with fragment `build-hash` CI and unlisted-fragment guard; **`AGENTS.md`** three-audience router + `make agents-check`. Full design: [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md). **Recommended semver:** minor **1.12.0** (new maintainer contracts + L0 behavioral gate; no intentional PyPI CLI break).

**v1.11.2 focus:** **Graph layer boundary refactor** — canonical graph primitives (`post_write`, `ast_cache`, `daemon_checkpoint`, cooperative yield, harvest runtime, prompt layout/constraints, cognitive LLM protocols) live in `src/graph/` with agent/daemon shims; `tests/test_graph_layer_boundary.py` forbids graph→agent/daemon imports ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) closed). **Bounded RAM** — generational alias/BM25 LRU (`MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS`) and dual-embedding ondemand/resident modes (`MATRYCA_BLOCK_VECTOR_STORE_MODE`, `MATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS`) ([#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136), [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) partial). **OCC nanosecond parity** — page writes use `st_mtime_ns` via `read_file_mtime_ns` ([#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) partial). **Shared env parsing** — `src/utils/env_parse.py`.

**v1.11.1 focus:** **Logseq Matryca Parser 1.4.0 alignment** — minimum dependency `logseq-matryca-parser>=1.4.0`; inherits 1.3.x root public API and graph parity; picks up 1.4.0 robustness (canonical page iteration, case-insensitive tag/search, watcher delete/move, SYNAPSE embed safety, 31 bug-hunt fixes).

**v1.11.0 focus:** **Tana → Logseq OG migration** — streaming `ijson` loader over Tana workspace JSON exports; hybrid entity placement under `Tana/`; `#day` journal routing via `logseq/config.edn`; depth-split at configurable limit; in-flight + catalog wikilink resolution; `tana-id::` idempotent OCC writes; CLI `matryca import tana` and MCP `import_tana` (dry-run default). Spec: [`openspec/tana-import.md`](openspec/tana-import.md).

**v1.10.6 focus:** **Concurrency integrity** — shared cross-process flock in `src/utils/platform_lock.py` unifies page RMW locks and JSON sidecar locks (NB acquire + exponential backoff + blocking fallback + thread-local reentrancy; fixes nested catalog/registry deadlocks, #40); OCC-safe hub page writes via `write_generated_hub_page` for Master Index and Graph Insights compiles (pre-compile mtime snapshot, graceful skip on human edit during compile, #34).

**v1.10.5 focus:** **Logseq Matryca Parser 1.3.1 alignment** — minimum dependency `logseq-matryca-parser>=1.3.1`; root-level public API imports; AST cache bootstrap telemetry via `discover_graph_files`; inherits parser graph parity (YAML frontmatter, case-insensitive page routing, asset extraction, round-trip fixes from 1.2.x).

**v1.10.4 focus:** **Dependency maintenance** — GitHub Actions toolchain refresh (`actions/checkout@v7`, `dependency-review-action@v5`, `astral-sh/setup-uv@v8.2.0`); Sovereign UI frontend npm patch/minor bumps; Dependabot weekly groups for `github-actions` and `frontend-npm`.

---

## Separation of concerns

### 1. Maintenance daemon (Python background engine)

**Entry:** `matryca plumber start` → `src/agent/maintenance_daemon.py`

The daemon polls `pages/` and `journals/` under `LOGSEQ_GRAPH_PATH`, calls a local OpenAI-compatible endpoint (LM Studio, Ollama), and commits structured results through:

- **`graph_dispatch.py`** — headless outline appends via `logseq_matryca_parser.agent_writer.append_child_to_node`
- **Cognitive modules** — `src/agent/plumber_modules/` (env-gated: MARPA, dangling healer, property hygiene, auto-split, …)
- **OCC + `page_rmw_lock`** — lost-update prevention and cross-process serialization per page file

Persistent artifacts at the graph root include `.matryca_daemon_state.json` (checkpoint + AI impact ledger), `.matryca_plumber_daemon.lock` / `.pid`, and `.matryca_semantic_cache/`. **Before** the first harvest or lint cycle, `prepare_matryca_runtime()` (see [Runtime bootstrap](#runtime-bootstrap)) ensures log directories, the sibling `matryca-l1/` folder, cache/templates paths, and an optional seeded `matryca-wiki.yml` exist.

#### Reactive graph stack (daemon)

| Component | Module | Role |
|-----------|--------|------|
| File watcher | `src/daemon/file_watcher.py` | Debounced `watchdog` on `pages/` + `journals/`; wakes duty cycle on external edits |
| AST RAM cache | `src/graph/ast_cache.py` (shim: `src/daemon/ast_cache.py`) | `LogseqGraph` full load + per-page `invalidate_and_reload_page`; auto-registers post-write delta handler |
| Identity store | `src/daemon/config_layer.py` | Telos / AI Constraints from config page; LLM + MCP injection |
| Post-write port | `src/graph/post_write.py` (adapter: `src/daemon/post_write_hooks.py`) | `PageWrittenEvent` pub/sub after atomic markdown writes: cache delta, identity refresh, robot git commit |
| Bootstrap gate (read-only) | `src/graph/daemon_checkpoint.py` | Lightweight `.matryca_daemon_state.json` reader for Soft Gate / MCP — no `maintenance_daemon` import |

Spec: [`docs/openspec/identity-config.md`](openspec/identity-config.md).

#### Graph layer modules (v1.11.2)

Canonical graph primitives moved from agent/daemon orchestration into `src/graph/`. Agent and daemon modules **re-export** for backward compatibility; `tests/test_graph_layer_boundary.py` enforces that graph code never imports `agent` or `daemon` (except the filename `daemon_checkpoint.py`, which reads JSON only).

| Module | Role |
|--------|------|
| `post_write.py` | `PageWrittenEvent` pub/sub port — `emit_page_written` after successful atomic writes |
| `ast_cache.py` | AST RAM cache + post-write page delta handler |
| `daemon_checkpoint.py` | Read-only bootstrap gate fields from `.matryca_daemon_state.json` + `.bak` recovery |
| `cooperative_yield.py` | Bootstrap I/O yielding (`yield_host`, env-driven intervals) |
| `harvest_runtime.py` | MapReduce thresholds + thermal pause (graph-local) |
| `cognitive_llm.py` | `HarvestLLM` / `InsightsLLM` protocols + Pydantic payloads |
| `prompt_constraints.py` | Cross-lingual output constraint + `finalize_system_prompt()` |
| `prompt_layout.py` | KV-cache-aligned prompt layout |
| `page_namespace.py` | `detect_marpa_namespace()` for MARPA path segments |

```mermaid
flowchart TB
  subgraph surfaces [Surfaces]
    Agent[src/agent orchestration]
    Daemon[src/daemon adapters]
    MCP[MCP graph_dispatch]
  end

  subgraph graph [src/graph canonical layer]
    MW[markdown_blocks atomic_write]
    PW[post_write emit_page_written]
    AST[ast_cache delta handler]
    CP[daemon_checkpoint read-only]
    GC[generational_cache LRU]
    Alias[alias_index journal detect]
  end

  subgraph vault [LOGSEQ_GRAPH_PATH]
    MD[pages and journals md]
    State[.matryca_daemon_state.json]
  end

  Agent --> graph
  Daemon --> graph
  MCP --> graph
  MW --> PW
  PW --> AST
  PW --> Daemon
  CP --> State
  MW --> MD
  AST --> MD
```

```mermaid
sequenceDiagram
  participant Writer as markdown_blocks atomic_write
  participant Port as graph.post_write
  participant AST as graph.ast_cache
  participant Adapter as daemon.post_write_hooks
  participant Identity as config_layer
  participant Git as robot git commit

  Writer->>Writer: OCC verify st_mtime_ns
  Writer->>Port: emit_page_written PageWrittenEvent
  Port->>AST: invalidate_and_reload_page
  Port->>Adapter: adapter handler
  Adapter->>Identity: refresh if config page
  Adapter->>Git: optional auto-commit
  Note over Writer,Git: Handler failures logged never propagated
```

#### Layer boundaries & known gaps (v1.11.2)

Honest status after Expert, Repomix, [Clean Architecture Audit 2026-06](quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md), and [Claude Architectural Audit 2026-06-24](quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md) triage:

| Gap | Current behavior | Tracking |
|-----|------------------|----------|
| ~~Graph → daemon coupling~~ | **Shipped v1.11.2:** `markdown_blocks` emits `graph.post_write.emit_page_written`; daemon adapter subscribes | ~~[#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134)~~ closed |
| Tana import memory (index phase) | `ijson` avoids full JSON DOM; `from_export` single-pass shipped; `StreamingGraphBuilder` still retains O(nodes) full `NodeDump` payloads | [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) partial — [#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154) |
| Tana idempotency v1 | Skip on `tana-id::` match only — no content-hash merge (v2 scope) | [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) |
| Dual-embedding `block_vectors.json` in RAM | **Shipped v1.11.2:** ondemand default + page-scoped streaming merge + LRU resident cap; full vault resident still possible with `resident` mode | [#51](https://github.com/MarcoPorcellato/matryca-plumber/issues/51) partial |
| OCC mtime granularity | **Shipped v1.11.2 (page writes):** `st_mtime_ns` via `read_file_mtime_ns`; catalog parity already ns; content-hash CAS → v2 | [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) partial — [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) v2 |
| `auto_split` child page lock | Creates child pages with `is_file()` + `atomic_write_bytes` under parent lock only — no `page_rmw_lock(child)` | [#39](https://github.com/MarcoPorcellato/matryca-plumber/issues/39) |
| Generational BM25/alias cache | Mtime signature invalidation + LRU cap; build-then-`sig_after` mitigated with 3-attempt retry (not full fix) | [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) |
| Tana `tana-id` pre-scan RAM | `scan_existing_tana_ids` loads full page text per file before import | [#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) |
| `maintenance_daemon` SRP | ~3300 lines; scheduling, LLM, telemetry, watcher in one class | [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) |
| `graph_dispatch` SRP | Mega-module; MCP routes through single dispatch plane | [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) |

**Closed in v1.11.2 (Expert Audit 2026-06):** [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132) `lock_backoff`; [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133) resolve/write TOCTOU; [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) post-write inversion; [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) generational cache LRU; [#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137)–[#138](https://github.com/MarcoPorcellato/matryca-plumber/issues/138) progress/TUI; [#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142) identity AST / routing / semantic config; [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) journal detection partial; `alias_index` ↔ `generational_cache` cycle (v1.11.0); NoRedirect DRY; Phase 2 denominator journal exclusion ([#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70)). **Audit correction:** `get_logseq_journal_format()` has no in-process cache — it re-reads `config.edn` each call (repeated I/O, not staleness).

Audit triage index: [`EXPERT_AUDIT_TRIAGE_2026-06.md`](quality/EXPERT_AUDIT_TRIAGE_2026-06.md) · [`REPOmix_AUDIT_TRIAGE_2026-06.md`](quality/REPOmix_AUDIT_TRIAGE_2026-06.md) · [`CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md) · [`CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md). Rejected claims: OCC lock leak; Tana “no streaming” / `json.load()`; BM25 SQLite outbox (distinct from #155 sig_after); identity path hardcoding; immediate hexagonal `domain/ports.py` split.

v2.0 north-star layout (`domain/` / `adapters/` / `orchestration/`) aligns with [Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) and [GraphRepository #17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) — not an immediate monolith split.

#### Atomic ingestion (MCP)

| Component | Module | Role |
|-----------|--------|------|
| Ingest pipeline | `src/agent/ingestion.py` | Parse external Markdown via OS temp file; stamp UUIDs; append ingest / `LOG` / `GLOSSARY` |
| MCP surface | `src/agent/mcp_server.py` | `ingest_document(source_name, raw_text)` |

Destination: daily `Ingest/YYYY-MM-DD` or `MATRYCA_INGEST_PAGE`. Parse scratch files **must not** live under `pages/` (avoids `file_watcher` + AST churn). Spec: [`docs/openspec/ingest.md`](openspec/ingest.md).

```mermaid
sequenceDiagram
  participant Agent as MCP ingest_document
  participant Temp as OS temp .md
  participant Parser as logseq-matryca-parser
  participant Gate as OCC plus page_rmw_lock
  participant Ingest as Ingest/YYYY-MM-DD page
  participant Log as LOG and GLOSSARY pages

  Agent->>Temp: write raw_text never under pages/
  Agent->>Parser: parse stamp fresh id UUIDs
  Parser-->>Agent: outline tree
  Agent->>Gate: append wrapped section
  Gate->>Ingest: atomic write
  Agent->>Gate: append ledger lines
  Gate->>Log: atomic write
  Note over Agent,Log: Secret scan rejects credentials in payload
```

#### Tana workspace import (CLI + MCP)

| Component | Module | Role |
|-----------|--------|------|
| Orchestrator | `src/agent/tana_import.py` | `run_tana_import()` — load → graph → convert → link → write |
| Importer package | `src/agent/importers/tana/` | Streaming parse, hybrid placement, catalog link rewrite, idempotent OCC writes |
| CLI | `src/cli/__init__.py` | `matryca import tana --file … [--apply]` — dry-run default; JSON stdout |
| MCP surface | `src/agent/mcp_server.py` | `import_tana(export_path, dry_run=True)` |

Parse uses **`ijson`** on the export file only — never materializes the full JSON DOM. Production import uses **`TanaWorkspaceGraph.from_export`** (single streaming pass). The builder still retains O(nodes) full `NodeDump` payloads during the index phase ([#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) partial). Writes stamp fresh `id::` UUIDs and `tana-id::` provenance; re-import skips nodes whose `tana-id` already exists in the vault. Spec: [`docs/openspec/tana-import.md`](openspec/tana-import.md).

#### Dual embedding (optional MCP semantic search)

| Component | Module | Role |
|-----------|--------|------|
| Block vectors | `src/semantic/store.py` | `block_vectors.json` — `vec_content` + `vec_applicability` per UUID; **ondemand** (default) streams from disk; **resident** + LRU via `MATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS` |
| Indexer | `src/semantic/indexer.py` | Daemon sidecar after semantic writes when `MATRYCA_DUAL_EMBEDDING_ENABLED`; page-scoped upsert via `apply_page_block_vector_updates()` |
| Retrieval | `src/semantic/search.py` | `search_graph` / `method=semantic` hybrid cosine; lexical pre-filter + disk iteration to avoid full RAM load |
| Config | `src/semantic/config.py` | `SemanticRuntimeConfig.from_env()` — injectable embedding/hybrid settings |

Does not replace BM25 or TF-IDF page clustering. Spec: [`docs/openspec/dual-embedding.md`](openspec/dual-embedding.md).

```mermaid
flowchart LR
  subgraph modes [MATRYCA_BLOCK_VECTOR_STORE_MODE]
    OD[ondemand default]
    RS[resident LRU]
  end

  subgraph pools [Bounded RAM pools v1.11.2]
    GC[generational_cache\nMATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS]
    BV[block_vectors store\nMATRYCA_BLOCK_VECTOR_STORE_MAX_GRAPHS]
  end

  Indexer[indexer page-scoped merge] --> OD
  Indexer --> RS
  OD --> BV
  RS --> BV
  Alias[alias_index BM25] --> GC
```

#### Structural link verification (v1.9)

| Component | Module | Role |
|-----------|--------|------|
| Extract + registry | `src/graph/link_verification.py` | Passive URL/asset harvest → `.matryca_link_registry.json` |
| Verify + flag | same | Async `httpx` HEAD + filesystem checks; OCC property stamps |
| Cycle hook | `MaintenanceDaemon._finalize_link_and_journey_pass` | End-of-cycle batch + Journey Log stats |

Spec: [`docs/openspec/link-verification.md`](openspec/link-verification.md).

#### Agent-centric DX (v1.9)

| Component | Module | Role |
|-----------|--------|------|
| JSON CLI | `src/cli/__init__.py` | Global `--json` stdout envelope |
| Context macro | `src/agent/context_load.py` | `matryca context load` |
| Subtree reads | `src/agent/graph_tool_helpers.py` | `read_subtree_markdown` + MCP `target_type=subtree` |
| Journey Log | `src/agent/journey_log.py` | Upsert one cumulative `- 🤖 Matryca Activity` bullet in today's journal |

Spec: [`docs/openspec/agent-dx.md`](openspec/agent-dx.md).

#### Agent Experience robustness (v1.9.7+)

| Component | Module | Role |
|-----------|--------|------|
| Page input normalizer | `src/agent/page_input_normalizer.py` | Lenient page title resolution at MCP entrypoints (`/` ↔ `___`, casing, traversal guard) |
| Write target resolver | `src/agent/graph_dispatch.py` | `_resolve_write_parent_target` — safe append fallback for invalid block refs |
| Empty-page outline writer | `src/agent/graph_dispatch.py` | `_headless_write_outline_empty_page` — EOF append when page has no blocks |
| Outline validation | `src/agent/outline_models.py` | `heading_level` int→str coercion; strip before disk write |

Spec: [`docs/openspec/agent-ax-robustness.md`](openspec/agent-ax-robustness.md). Tests: `tests/test_agent_experience_robustness.py`.

### 2. Sovereign UI (React + FastAPI control room)

**Entry:** `matryca plumber status` / `matryca plumber ui` → `src/cli/ui_server.py` on `http://127.0.0.1:8500`

These commands start the **control room only** — not the maintenance daemon. Operators launch graph work via **Start Engine** in the UI (`POST /api/daemon/start`) or separately with `matryca plumber start`. Shorthand: `matryca-plumber status` → `plumber status`.

A **monolithic** Uvicorn process serves:

- **REST API** — `/api/state`, `/api/logs`, `/api/config`, daemon control, LM model discovery (SSRF-hardened)
- **Static SPA** — `frontend/dist/` built from Vite; polls on a **5s distributed cycle** via `usePlumberPolling` (`/api/state` every cycle — including a background **5s** poll when `daemon_pid` is live but logs are frozen; `/api/logs` staggered; `/api/graph-analytics` ~every 20s)
- **Zero-Trust auth** — `X-Matryca-Token` on protected routes (`ui_auth.py`)

The UI never becomes a second source of truth: it reads daemon checkpoints and live graph scans; configuration writes go to the repo **`.env`** atomically and are picked up by `reload_plumber_dotenv()` on the next daemon sync cycle.

**Daemon launch (post-v1.9.11):** `POST /api/daemon/start` spawns `plumber start --foreground` in a fresh interpreter (`start_new_session=True`). Success is verified by a **live PID** in `.matryca_plumber_daemon.pid` (`is_plumber_process`), not by the launcher subprocess staying alive. Stale PID files referencing a live non-Plumber process return `foreign_pid`; dead PIDs are removed before retry. The foreground worker publishes its PID immediately after acquiring `.matryca_plumber_daemon.lock`, registers bootstrap `SIGINT`/`SIGTERM` cleanup handlers, and removes PID/lock files on startup failure.

### 3. MCP server sidecar (FastMCP stdio)

**Entry:** `matryca-plumber` with **no** CLI-shaped argv → `src/main.py` (lazy-imported from `plumber_entry.py`)

`register_mcp_tools` exposes five polymorphic mega-tools (`read_graph_data`, `search_graph`, `mutate_graph`, `refactor_blocks`, `run_linter`) plus **`store_fact`** (identity), **`ingest_document`** (atomic external markdown → ingest page + `LOG`/`GLOSSARY`, parse via OS temp files only), and **`import_tana`** (Tana workspace JSON export → `Tana/` pages + journals, dry-run default). **`guard_mcp_tool`** maps domain errors to LLM-safe strings and appends Telos/Constraints context to successful responses (except `store_fact`); **`mcp_telemetry`** bridges Loguru INFO+ lines to `Context.info` during tool calls.

**Lazy AST bootstrap (v1.9.6+):** MCP `app_lifespan` and the **Sovereign UI** FastAPI lifespan call `prepare_matryca_runtime(..., eager_graph=False)` so stdio handshakes and `:8500` bind in seconds on large vaults. **v1.9.11** extends lazy bootstrap to UI `POST /api/config`, graph-path save, L1 provision, and `POST /api/daemon/start` (spawn only — the child `plumber start` process still loads the AST eagerly). The **maintenance daemon** and agent **`matryca read` / `search` / …** paths remain **eager** (`eager_graph=True`). Deferred surfaces load the AST on the first call to `get_graph_ast_cache().get_graph()` (e.g. MCP graph tools, UI `/api/graph-analytics`); stderr logs `AST cache bootstrap started|complete` with `markdown_files`, `duration_s`, `pages_indexed`. See [`integrations/hermes-agent.md`](integrations/hermes-agent.md).

**Routing fix (`plumber_entry.py`):** the `matryca-plumber` console script inspects `sys.argv`. Known CLI commands (`plumber`, `read`, `search`, shorthand `start`/`status`/…) route to `cli.main` **without** importing FastMCP. Bare invocations (typical MCP host stdio spawn) fall through to `main.main()`. This disentangles **operator CLI stdout** from **MCP JSON-RPC on stdio** — a class of integration bugs that plagued single-entrypoint packages.

```mermaid
flowchart TD
  Entry[matryca-plumber console script plumber_entry.py]
  Entry --> HasArgs{known CLI subcommand\nin sys.argv?}

  HasArgs -->|yes| CLI[cli.main\nhuman stdout text or --json]
  HasArgs -->|no| McpEnabled{MATRYCA_MCP_ENABLED true?}

  McpEnabled -->|yes| MCP[main.main FastMCP stdio\nJSON-RPC tool plane]
  McpEnabled -->|no| Help[print help exit]

  CLI --> Dispatch[graph_dispatch.py]
  MCP --> Dispatch
```

---

## System topology

```mermaid
flowchart TB
  subgraph vault [Logseq OG vault LOGSEQ_GRAPH_PATH]
    Pages["pages/ journals/ templates/"]
    Cache[".matryca_semantic_cache/\nmaster_catalog.json clusters"]
    Ledgers[".matryca_daemon_state.json\n.matryca_xray_state.json\n.matryca_link_registry.json"]
    L1["matryca-l1/ session rules\noutside wiki index"]
  end

  subgraph inference [Local inference CPU only]
    LM[LM Studio or Ollama]
    Client[InstructorLLMClient structured JSON]
    LM <--> Client
  end

  subgraph engine [MaintenanceDaemon]
    P1[Phase 1 bootstrap harvest]
    P2[Phase 2 cognitive lint poll]
    P1 -->|"bootstrap_complete"| P2
    P1 --> Client
    P2 --> Client
  end

  subgraph dispatch [graph_dispatch shared by all surfaces]
    GD[read search mutate refactor lint]
    Lock[page_rmw_lock plus OCC mtime]
    GD --> Lock
  end

  subgraph surfaces [External surfaces]
    UI[Sovereign UI :8500]
    MCP[FastMCP stdio optional]
    CLI[matryca CLI --json]
  end

  Pages <-->|"UTF-8 atomic writes"| Lock
  Cache -.->|"catalog read not L2 scrape"| GD
  L1 -.->|"read_graph_data memory"| GD
  engine --> GD
  UI -->|"checkpoint start stop .env"| engine
  MCP --> GD
  CLI --> GD
  Client -.->|"token telemetry"| UI
```

**Invariant:** one **system of record** — `LOGSEQ_GRAPH_PATH`. No auxiliary database, no Logseq Electron dependency, no split-brain HTTP API for background work.

### Daemon lifecycle: Phase 1 → Phase 2

The maintenance daemon enforces **strict phase separation**. Phase 2 cognitive lint and cluster scheduling stay disabled until bootstrap harvest completes and `bootstrap_complete` is persisted.

```mermaid
stateDiagram-v2
  [*] --> Boot: prepare_matryca_runtime
  Boot --> Phase1: run_bootstrap_pipeline

  state Phase1 {
    [*] --> HarvestPage
    HarvestPage --> HarvestPage: per page mmap or LLM summary
    HarvestPage --> WriteCatalog: upsert master_catalog.json
    WriteCatalog --> CompileIndex: write Matryca Master Index.md
  }

  Phase1 --> Teardown: release_phase1_memory
  Teardown --> Phase2: bootstrap_complete true

  state Phase2 {
    [*] --> DutyCycle
    DutyCycle --> FastTrack: mtime changed pages
    DutyCycle --> CognitiveLint: LLM modules env gated
    DutyCycle --> LinkVerify: dead-link missing-asset batch
    DutyCycle --> JourneyLog: upsert daily activity bullet
    FastTrack --> DutyCycle
    CognitiveLint --> DutyCycle
    LinkVerify --> DutyCycle
    JourneyLog --> DutyCycle
  }

  Phase2 --> [*]
```

### Journal pages — structural-only indexing

Daily fleeting notes live under **`journals/`** (Logseq daily pages). The daemon and Journey Log mutate these files frequently; running full Phase-2 cognitive lint and semantic embeddings on every journal edit wastes local LLM tokens and GPU prefill time without improving long-horizon knowledge structure.

| Path | Phase-1 (structural) | Phase-2 (semantic / LLM) |
|------|----------------------|---------------------------|
| **`pages/**/*.md`** | Bootstrap catalog, fast-track structural checks, AST cache on watchdog events | Cognitive lint modules, `index_page`, semantic index append, optional dual embeddings |
| **`journals/**/*.md`** | `_settle_journal_structural_cycle_file`: read content, merge link registry, `get_graph_ast_cache().apply_file_event`, persist `FileState` with current `mtime` | **Skipped** — no `run_cognitive_lint_pipeline`, `index_page`, `apply_semantic_page_result`, or `run_dual_embedding_after_semantic_write` |

**Detection:** `is_journal_page_path(graph_root, page_path)` — first path segment under the graph root is `journals` (`src/agent/plumber_modules/_shared.py`).

**Queue semantics:** `page_needs_phase2_cognitive` returns `true` only while a journal lacks a matching ledger entry or `mtime` drift (structural settle pending). Once settled, journals never re-enter the semantic queue. `compute_phase2_progress_metrics` excludes `journals/` from the Phase-2 vault denominator.

**Preserved:** File watcher AST refresh on external edits; Journey Log upsert still uses `page_rmw_lock` + OCC on today's journal; link verification batch pass unchanged.

Spec detail: [`openspec/llm-performance.md`](openspec/llm-performance.md#journal-pages--phase-2-semantic-bypass).

---

## Headless mutation plane (shared by all surfaces)

### Parser-backed spatial truth

**[logseq-matryca-parser](https://github.com/MarcoPorcellato/logseq-matryca-parser)** (`>=1.4.0`) owns block hierarchy, indentation, and `id::` semantics. From **1.2.0** onward the parser also handles YAML frontmatter page properties, case-insensitive page routing, and multimodal asset extraction; **1.3.0** consolidates the public root API (`LogosParser`, `LogseqGraph`, `discover_graph_files`, …); **1.4.0** adds graph-integrity hardening (canonical page iteration, case-insensitive tag/search, watcher delete/move, SYNAPSE embed safety). **`src/rag/matryca_hooks.py`** adapts `read_logseq_page` for agent consumption.

Disk mutators that perform line surgery (`property_line_edit`, `tag_unify`, `reparent_blocks`, …) combine:

- **`global_fence_scanner.py`** — dead zones (fenced code, HTML comments, Advanced Query blocks)
- **`mldoc_properties.py` / `mldoc_guards.py`** — Logseq-aligned property grammar
- **`path_sandbox.py`** — `is_relative_to(graph_root)` before every read/write
- **`atomic_write_bytes`** — `mkstemp` → write → `fsync` → `os.replace` (+ optional `((uuid))` pre-flight in `logseq_uuid.py`)

### Logseq AST parity (non-negotiable)

| Rule | On-disk shape | Module |
|------|---------------|--------|
| **Page properties** | Raw `key:: value` at **line 0 region**, no `- ` bullet; blank line before first bullet | `page_properties.py` |
| **Block properties** | `id::`, `matryca-plumber::`, … at **+2 spaces** under parent bullet, before children | `mldoc_properties.py`, `property_line_edit.py` |
| **Identity vs metadata** | `id::` is the block UUID anchor — **not** a mutable `key::` target for property hygiene or regex property tools (`parse_logseq_property_line` excludes normalized key `id`) | `mldoc_properties.py` |
| **Namespaces** | Semantic `Domain/Topic` → `Domain___Topic.md` + percent-encoding | `page_path.py` |
| **Authorship** | `made-by:: matryca plumber v{version}` in frontmatter | `stamp_plumber_authored_page()` |

Third-party tools that treat pages as flat CommonMark routinely corrupt Logseq indexes; Plumber’s write paths preserve the outliner contract end-to-end.

### Safe-Sync data paths (v1.9.5)

Tier-2 agents and operators share one contract: **read Markdown through Plumber tools**, **write through atomic mutators**, **never touch Logseq’s internal app database**.

```mermaid
flowchart LR
  subgraph readPlane [READ plane]
    R1[read_graph_data]
    R2[search_graph bm25 semantic]
    R3[context load CLI macro]
    MD[(pages/ journals/ md)]
    R1 --> MD
    R2 --> MD
    R3 --> MD
  end

  subgraph writePlane [WRITE plane Logseq OG]
    W1[mutate_graph refactor_blocks]
    W2[ingest_document OS temp parse]
    W3[store_fact identity page]
    Gate[OCC snapshot verify atomic_write]
    W1 --> Gate
    W2 --> Gate
    W3 --> Gate
    Gate --> MD
  end

  Forbidden["Logseq app SQLite/KV\nNEVER read or write"]
  MD -.->|"not via Plumber"| Forbidden

  subgraph cachePlane [Daemon cache not agent scrape target]
    Cat[master_catalog.json]
    Cat -.->|"Tier-2 reads compiled\nMaster Index page instead"| R1
  end
```

---

## Optimistic concurrency control (OCC)

Local LLM inference is **slow** (seconds to minutes). Logseq users keep editing during that window. OCC prevents **silent overwrites** of human edits without replacing the need for **RMW locks** (which prevent torn writes between concurrent writers).

### Two-layer concurrency model

| Layer | Mechanism | Prevents |
|-------|-----------|----------|
| **Serialization** | `page_rmw_lock(path)` — in-process `threading.Lock` registry + cross-process `fcntl.flock` sidecar | Torn interleaved RMW from daemon + MCP + second daemon |
| **Lost-update detection** | `baseline_mtime` via `st_mtime` — snapshot → work → verify → atomic commit | Stale LLM output overwriting fresher human bytes |

`page_rmw_lock` and OCC mtime checks are **complementary**, not interchangeable: the lock prevents torn RMW interleaving; mtime detects human edits during slow LLM work. External audits sometimes mislabel this as “pessimistic locking masquerading as OCC” — see [Clean Architecture Audit triage](quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md).

### Known limitation — mtime granularity

Matryca Plumber uses 64-bit integer nanosecond precision (`st_mtime_ns`) for catalog invalidation and, since v1.11.2, for page-write OCC via `read_file_mtime_ns`. This bypasses Python's float timestamp truncation for deterministic drift checks.

**Filesystem resolution constraints:** OCC is physically bound by the maximum timestamp resolution of the underlying filesystem.

| Class | Examples | OCC behavior |
|-------|----------|--------------|
| **Modern** | ext4, APFS, ZFS, NTFS | Nanosecond or 100-ns precision — OCC works as designed |
| **Legacy** | FAT32, exFAT, older HFS+ | OS pads sub-second fields with zeros (≈1–2 s effective resolution) — a concurrent human edit in the same wall-clock second as a daemon commit may not be detected by mtime alone |

On legacy drives, **`page_rmw_lock` during commit** remains the serialization backstop when two writers interleave in the same second. When two Plumber writers observe identical second-level mtimes after the same snapshot, OCC alone may not detect a conflict — same mitigation applies.

v1 page-write hardening: [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) (nanosecond parity). **Content-hash compare-and-swap** (SHA-256 of page bytes) is v2 scope under [GraphRepository #17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17).

### OCC lifecycle (canonical order)

1. **`occ_snapshot(page_path)`** — capture `baseline_mtime` **before** reading content or calling the LLM (Phase 1).
2. **Inference / payload assembly** — human may edit in Logseq; `st_mtime` advances.
3. **`occ_verify_before_write(path, baseline_mtime)`** — fast reject **before** acquiring `page_rmw_lock` when already stale.
4. **`with page_rmw_lock(path):`** — enter exclusive RMW scope.
5. **Re-read** page bytes; **`file_mtime_drifted()`** again inside the lock.
6. **`atomic_write_bytes_if_unchanged(..., baseline_mtime=...)`** — final mtime check immediately before `os.replace`; abort with `write_aborted` if conflict.

Cognitive modules (`apply_semantic_page_result`, `property_hygiene`, `auto_split`, `append_page_alias_line`, …) thread `baseline_mtime` through this gate. After Plumber’s **own** intermediate write in the same request, callers may **`OCCSnapshot.refresh_after_own_write()`** to re-baseline multi-step edits.

**Bootstrap harvest (v1.10.0 — #37):** Phase-1 `harvest_page_into_catalog` calls `_append_minimal_semantic_index` after LLM inference. When OCC aborts (mtime drift or failed `atomic_write_bytes_if_unchanged`), the catalog **must not** upsert a summary absent from the `.md` body — the harvest returns `pending_llm` and retries on a later scan. See [`docs/openspec/runtime-bootstrap.md`](openspec/runtime-bootstrap.md#master-catalog-persistence-v1100).

**Phase 2 daemon (`_process_llm_cycle_file`):** For **`pages/`** only (not `journals/`), the maintenance daemon does **not** hold `page_rmw_lock` during cognitive lint or `index_page` LLM inference. It snapshots mtime, reads content, runs modules and the LLM (each cognitive write acquires its own short lock scope), re-checks drift, then commits only inside **`apply_semantic_page_result`** — matching the sequence diagram below. Journal paths delegate to `_settle_journal_structural_cycle_file` before any LLM work. Holding the page lock across multi-minute inference would block Logseq saves and other writers without adding OCC value.

**Semantic index prompts:** `_enumerate_blocks_for_prompt` caps the block UUID catalog at **8000 characters** (aligned with the page body cap in `_build_index_prompt`) so block-rich pages cannot blow the local context window; truncated catalogs include an explicit omission note for the model.

```mermaid
sequenceDiagram
    autonumber
    participant Op as Daemon / MCP / CLI
    participant FS as Page .md
    participant LLM as Local LLM
    participant Lock as page_rmw_lock

    Note over Op,FS: Phase 1 — snapshot BEFORE read / inference
    Op->>FS: occ_snapshot() → baseline_mtime
    Op->>FS: read_text(utf-8)
    Op->>LLM: structured inference (seconds…)
    Note over FS: Human edits in Logseq — mtime changes

    Note over Op,FS: Phase 2 — verify BEFORE lock
    Op->>FS: occ_verify_before_write(baseline_mtime)?
    alt drifted before lock
        Op-->>Op: abort — no data loss
    else still stable
        Op->>Lock: acquire exclusive RMW lock
        Op->>FS: re-read + file_mtime_drifted()?
        alt drifted inside lock
            Op->>Lock: release
            Op-->>Op: abort write_aborted
        else stable under lock
            Op->>FS: atomic_write_bytes_if_unchanged(baseline_mtime)
            alt mtime changed at commit
                Op-->>Op: abort — OCC conflict
            else committed
                Op->>Lock: release
                Op-->>Op: patch_generational_caches
            end
        end
    end
```

**Complement, not duplicate:** `fcntl.flock` stops two writers from corrupting the same file mid-splice; OCC stops one writer from promoting a payload computed on obsolete bytes.

### Unified cross-process flock (`platform_lock`, v1.10.6)

Page RMW locks (`.{page}.matryca.lock`) and JSON sidecar locks (`.{json}.matryca.json.lock`) delegate to **`src/utils/platform_lock.py`**. One implementation prevents semantic drift between markdown writers and catalog/registry writers — the root cause of nested deadlocks when harvest, daemon checkpoint, and link-registry passes interleave ([#40](https://github.com/MarcoPorcellato/matryca-plumber/issues/40)).

| Mechanism | Behavior |
|-----------|----------|
| **Non-blocking acquire** | `LOCK_EX \| LOCK_NB` with exponential backoff (`IO_RETRY_*`) |
| **Blocking fallback** | After NB exhaustion, blocking `flock` with warning log |
| **Reentrancy** | Thread-local depth map keyed by lock identity — same thread may re-enter nested catalog/registry scopes |
| **Degradation** | `MATRYCA_ALLOW_FLOCK_DEGRADATION=true` → thread-only when OS flock unsupported (iCloud/Dropbox) |

```mermaid
flowchart TB
  subgraph callers [Lock consumers]
    PageLock[page_rmw_lock\nmarkdown RMW]
    JsonLock[cross_process_json_flock\nmaster_catalog link_registry daemon_state]
  end

  subgraph platform [src/utils/platform_lock.py]
    NB[NB flock plus exponential backoff]
    Block[Blocking fallback after NB exhaustion]
    Depth[Thread-local reentrancy depth]
    Degrade[MATRYCA_ALLOW_FLOCK_DEGRADATION]
  end

  subgraph sidecars [Sidecar files 0o600]
    PageSidecar[".{page}.matryca.lock"]
    JsonSidecar[".{json}.matryca.json.lock"]
  end

  PageLock --> NB
  JsonLock --> NB
  NB --> Block
  NB --> Depth
  NB --> Degrade
  PageLock --> PageSidecar
  JsonLock --> JsonSidecar
```

### Hub page compile writes (v1.10.6)

Daemon-generated **hub pages** (`Matryca Master Index`, `Matryca Graph Insights`) are expensive to compile (catalog scan + markdown assembly). Holding a page lock across compile would block Logseq saves; writing without OCC would overwrite human edits made during compile.

**`write_generated_hub_page`** (`src/graph/generated_hub_write.py`) captures **`baseline_mtime` before compile**, then under `page_rmw_lock`:

1. Re-check `file_mtime_drifted` — if human edited during compile → **graceful skip** (`written=False`, INFO log).
2. Re-snapshot mtime inside lock.
3. Commit via `atomic_write_bytes_if_unchanged` — final OCC gate at `os.replace`.

Skipped writes are safe: the next daemon cycle recompiles from fresh catalog state ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34)).

```mermaid
sequenceDiagram
    autonumber
    participant D as MaintenanceDaemon
    participant Cat as master_catalog.json
    participant FS as Hub page .md
    participant Hub as write_generated_hub_page
    participant Lock as page_rmw_lock

    D->>FS: occ_snapshot() → baseline_mtime
    D->>Cat: compile markdown (seconds…)
    Note over FS: Human edits hub page in Logseq

    D->>Hub: write_generated_hub_page(baseline_mtime=…)
    Hub->>Lock: acquire exclusive RMW lock
    Hub->>FS: file_mtime_drifted(baseline_mtime)?
    alt drifted during compile
        Hub->>Lock: release
        Hub-->>D: written=False graceful skip
    else still stable
        Hub->>FS: atomic_write_bytes_if_unchanged
        alt OCC abort at commit
            Hub-->>D: written=False
        else committed
            Hub-->>D: written=True
        end
    end
```

---

## Trust & Safety levels

Operators control invasiveness from the Sovereign UI **Settings drawer** (`SettingsDrawer.tsx`). Toggles map to `MATRYCA_LINT_*` / `MATRYCA_PLUMBER_*` keys in `.env`; `reload_plumber_dotenv()` applies them on the next daemon `_sync_runtime_config()` without restart.

```mermaid
graph LR
  subgraph safe["🟢 Safe Mode — read-only prose"]
    S1["Semantic routing cache"]
    S2["Entity consolidation alias::"]
    S3["Property hygiene metadata"]
    S4["MARPA taxonomy labels"]
    S5["Context compression / MapReduce"]
  end

  subgraph aug["🟠 Augmented Mode — side structures"]
    A1["Dangling link healer\nseed pages"]
    A2["Backlink backpropagation\n- ### foldable sections"]
  end

  subgraph surg["🔴 Surgeon Mode — opt-in structure"]
    R1["Inline semantic corrections\n[[WikiLink]] wrapping"]
    R2["Auto-split dense blocks\n{{embed [[Child]]}} stubs"]
  end

  OP["Operator Settings Drawer"] --> safe
  OP --> aug
  OP --> surg
  safe -->|"never edits bullet bodies"| MD["Markdown graph"]
  aug -->|"append-only side blocks"| MD
  surg -->|"inline / subtree surgery"| MD
```

| Tier | Risk | Prose impact |
|------|------|----------------|
| **Safe Mode** | Lowest | Metadata, indexes, `alias::`, routing cache — **no inline bullet rewrites** |
| **Augmented Mode** | Medium | New foldable `- ###` sections and isolated seed pages; original bullets preserved |
| **Surgeon Mode** | Highest | Inline wikilink corrections and embed-based subtree extraction — **strictly opt-in** |

---

## Runtime bootstrap

Every Matryca Plumber surface calls **`prepare_matryca_runtime()`** in `src/utils/runtime_bootstrap.py` after environment load and **before** graph processing. The helper is idempotent. **`eager_graph=True`** (default) loads the AST index immediately — **daemon**, **`matryca read` / `search` / …** via `cli.main`. **`eager_graph=False`** — **MCP stdio** and **Sovereign UI** (lifespan plus config/save/start/L1 API, v1.9.11) — defers `LogseqGraph.load_directory` until the first graph read in that process.

| Provisioned at startup | Location | Motivation |
|------------------------|----------|------------|
| Ops + app log parent dirs | `MATRYCA_*_LOG_PATH` or repo `logs/` | First JSONL / Loguru write must not fail on missing folders |
| L1 memory | Default: `<parent-of-vault>/matryca-l1/` | Session rules outside L2 wiki index; shareable across vaults ([`docs/openspec/l1-l2-routing.md`](openspec/l1-l2-routing.md)) |
| Semantic cache dir | `<vault>/.matryca_semantic_cache/` | `master_catalog.json`, `backlink_counts.json`, `semantic_clusters.json`, per-inference `*.json`; excluded from `pages/` scans |
| Templates dir | `<vault>/templates/` (or YAML `templates_subdir`) | `read_logseq_template` |
| Wiki orchestration | `<vault>/matryca-wiki.yml` | Seeded from `matryca-wiki.example.yml` when missing |
| AST + identity RAM | `get_graph_ast_cache`, `get_identity_store` | **Eager:** daemon + agent CLI. **Lazy:** MCP + Sovereign UI — on first `get_graph()` (identity loads with first graph access) |

**Not** created at bootstrap: repo `.env`, `pages/` / `journals/` (vault must already be valid), identity config page (operator-created or seeded by `store_fact`), ingest / `LOG` / `GLOSSARY` pages (first `ingest_document`), **`Tana/` import tree** (first `import_tana --apply`), daemon/X-Ray JSON ledgers, PID/lock files — those follow first-use or first-checkpoint semantics.

Full behavioral spec: [`docs/openspec/runtime-bootstrap.md`](openspec/runtime-bootstrap.md). Identity page format: [`docs/openspec/identity-config.md`](openspec/identity-config.md).

---

## Sandboxing and safety

### Strict AST parity and Line-0 frontmatter preservation

All page-level metadata mutations route through **`page_properties.py`**, which computes the **frontmatter span** at the top of the file and injects raw `key:: value` lines **without** promoting them to bullets. Block-level surgery uses **`property_line_edit.py`** scoped to subtrees anchored at `id::`, intersecting **`compute_page_protected_line_indices`** so fenced code and query blocks are never touched. Property-line matchers (`is_logseq_block_property_line` / `parse_logseq_property_line`) **exclude** `id::` so hygiene and MCP regex tools never treat Logseq UUID lines as editable metadata keys.

The adapter and writer stack delegate tree shape to **`logseq-matryca-parser`**; Matryca Plumber does not maintain a competing full-file Markdown AST.

### Atomic `.env` writes (Sovereign UI)

Settings persistence uses **`_atomic_write_text`** in `ui_server.py`: `mkstemp` beside the target → UTF-8 write → `flush` + `fsync` → `os.replace`. Partial writes cannot leave the Plumber configuration torn while the React drawer saves thermal delays, lint flags, or `LOGSEQ_GRAPH_PATH`.

### Page-lock registry with LRU eviction

**`page_write_lock.py`** keeps an in-process `OrderedDict` of `threading.RLock` instances keyed by normalized absolute paths (cap **`_MAX_PAGE_LOCK_REGISTRY = 4096`**). When the cap is reached, entries are evicted LRU-style only when `not old_lock.locked()`; a full registry of held locks raises **`PageLockUnavailableError`** rather than evicting an active lock ([#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) optional `acquire(blocking=False)` hardening).

Cross-process exclusivity delegates to **`platform_lock.cross_process_sidecar_lock`** (`.matryca.lock` sidecar beside each page). Same NB/backoff/blocking/reentrancy semantics as JSON sidecar flock (v1.10.6). **`MATRYCA_ALLOW_FLOCK_DEGRADATION=true`** permits thread-only locking on iCloud/Dropbox filesystems that reject `flock` (at operator risk). **`PageLockUnavailableError`** causes the daemon to **skip** the file without marking it processed — no false success, no torn write.

### Thread-safe Loguru → MCP logging bridge

**Problem:** Loguru’s `enqueue=True` sink runs on a worker thread and **pickles** log records. Embedding live FastMCP `Context` objects in `record["extra"]` caused multiprocessing/pickling failures and flaky telemetry.

**Solution (`mcp_telemetry.py`):**

1. On the emitting thread, stamp **`record["extra"]["matryca_mcp_session"] = id(ctx)`** — an integer key only.
2. Store **`(ctx, event_loop)`** in module-level **`_mcp_sessions[id(ctx)]`** for the tool call duration (`mcp_tool_session` context manager).
3. The sink resolves the session, sanitizes the message (`sanitize_log_message`), and schedules `ctx.info` on the correct loop via `call_soon_threadsafe`.
4. Tests await **`await logger.complete()`** instead of brittle `sleep` polling — deterministic drain of the async queue under `pytest-asyncio`.

Unless **`MATRYCA_DEBUG=true`**, UUIDs and payload-like markers are redacted before MCP clients display logs.

### Additional hardening (summary)

| Concern | Implementation |
|---------|----------------|
| Path traversal | `path_sandbox.assert_path_within_graph` |
| Graph UTF-8 reads | `read_graph_file_text()` — CI `sandbox-read-check` blocks raw `Path.read_text()` in graph/agent/rag (v1.9.9) |
| Bounded JSON sidecars | `read_bounded_json()` + `MATRYCA_JSON_MAX_BYTES` on catalog/registry/daemon/cache loaders (v1.9.9) |
| JSON sidecar flock + atomic save | `cross_process_json_flock` via **`platform_lock.py`** (NB + backoff + reentrancy, v1.10.6) + `atomic_write_bytes` on master catalog ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35), [#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)), link registry ([#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)); harvest catalog/page parity on OCC abort ([#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37)) — v1.10.0 |
| Link registry tamper | `link_verification` validates registry `page_relpath` and asset refs before read (v1.9.9) |
| LLM debug NDJSON | `agent_debug_log` path allowlist + secret redaction when `MATRYCA_LLM_DEBUG_*` enabled (v1.9.9) |
| Credential leakage into graph | `quality_gate.outline_security_violations` |
| L1 rules path escape | `l1_memory.py` — reads only under `$HOME` or temp; `README.md` excluded from LLM payload |
| Startup filesystem | `runtime_bootstrap.py` — logs, L1, cache, templates, optional `matryca-wiki.yml` before harvest |
| LLM egress / SSRF | `utils/llm_url_policy.validate_llm_proxy_url` — UI **and** daemon |
| UI graph path hijack | `validate_logseq_graph_path_for_config` + `config_paths.graph_config_allowed_roots` |
| UI loopback exfiltration | SSRF on `/api/lm-models` + `POST /api/config`; `X-Matryca-Token` gate |
| UI abuse / probing | Split rate limits (`MATRYCA_UI_RATE_LIMIT_*`); session route loopback-only |
| MCP stdio exposure | `MATRYCA_MCP_ENABLED` gate in `plumber_entry.py` (default off) |
| MCP error leakage | `mcp_tool_guard._public_tool_error_message` unless `MATRYCA_DEBUG` |
| Daemon exclusivity | `.matryca_plumber_daemon.lock` (POSIX flock / Windows `msvcrt`); PID sidecar published at lock acquisition; CI `# sandbox-read-ok` allowlist for pid/lock reads only |
| Ledger durability | `save_daemon_state` tmp + fsync + replace + `.bak` + `json_flock`; master catalog merge-on-save + flock load (v1.10.0) |

### JSON sidecar concurrency (v1.10.0 → v1.10.6)

Graph-local JSON checkpoints share **`cross_process_json_flock`** sidecars and **`atomic_write_bytes`**. v1.9.9 bounded reads prevent memory DoS; v1.10.0 closes torn-read and last-writer-wins gaps on the hottest sidecars; **v1.10.6** unifies flock semantics with page locks via **`platform_lock.py`** (NB acquire, exponential backoff, blocking fallback, thread-local reentrancy — fixes nested catalog/registry deadlocks under pytest-xdist and concurrent harvest).

| Sidecar | Load | Save |
|---------|------|------|
| **`master_catalog.json`** | `load_master_catalog` under flock ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)) | Merge-on-save by `last_mtime` ([#36](https://github.com/MarcoPorcellato/matryca-plumber/issues/36)); `save(replace=True)` after prune |
| **`.matryca_link_registry.json`** | `_load_registry_unlocked` under flock | `atomic_write_bytes` in `_save_registry_unlocked` ([#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)) |
| **`backlink_counts.json`** | flock + bounded read | flock + atomic write (reference pattern) |

**Bootstrap (#37):** Catalog upsert after LLM harvest only when the semantic index block was written or already on disk; OCC abort → `pending_llm`, no catalog/page drift.

Detail: [`docs/openspec/runtime-bootstrap.md`](openspec/runtime-bootstrap.md#master-catalog-persistence-v1100), [`docs/openspec/link-verification.md`](openspec/link-verification.md), [`docs/openspec/security-sandbox.md`](openspec/security-sandbox.md).

---

## Sovereign UI and telemetry (condensed)

**Live control room (v1.9.3):**

| Layer | Contract |
|-------|----------|
| Daemon | `MATRYCA_TELEMETRY_HEARTBEAT_SECONDS` (default 5) — `_telemetry_heartbeat_scope` during `index_page`, idle sleep between cycles |
| Checkpoint | `save_daemon_state` after immutable snapshot under `_telemetry_lock` |
| API | `GET /api/state` — `max(checkpoint, ops_log)` token totals + `daemon_pid` |
| UI | `POLL_CYCLE_MS = 5000`; auto-unfreeze on PID / `running` / `idle` |

Spec: [`openspec/live-telemetry-ui.md`](openspec/live-telemetry-ui.md).

**Dynamic Human vs Agent metrics** (`graph_analytics.py`):

$$\text{Human} = \max(0,\ \text{Scanned absolute} - \text{AI impact})$$

- **Pages:** live scan minus pages with `made-by:: matryca plumber v*` frontmatter.
- **Links:** absolute wikilink count minus `ai_links_injected` from `.matryca_daemon_state.json`.

No telemetry database — the vault **is** the audit trail.

**Context Acceleration Shield** (TRIZ-driven): `llm_context_payload.py` substitutes Phase 1 summaries for megabyte pages; `prompt_layout.py` places stable content before dynamic task tails so llama.cpp KV-cache prefixes reuse across consecutive lint operations on the same file.

---

## Edge computing & performance (v1.8)

**Goal:** The maintenance daemon must remain **responsive to the host OS** while harvesting and linting vaults up to **~10,000** pages on **16 GB RAM** without a discrete GPU.

**Non-goal:** New cognitive capabilities, clustering algorithms, or Logseq semantic changes.

### Prompt stack (Zero-Prefill + Clean Architecture v1.12)

```mermaid
sequenceDiagram
  participant D as MaintenanceDaemon
  participant B as semantic_lint/prompts.py
  participant S as PagePromptSession
  participant L as Local_LLM
  participant V as safety/validators
  D->>S: build once per page cycle
  Note over S: stable_page_block + capped AliasIndex footer
  D->>B: build_semantic_lint_system_prompt (Tier-1A)
  D->>L: system = builder output
  D->>L: user = stable block + task_index
  D->>L: user = same stable block + task_marpa
  Note over L: llama.cpp reuses KV prefix on stable block
  L-->>D: proposed index body
  D->>V: validate_llm_write_diff (L0)
  alt safe
    D->>D: OCC commit
  else rejected
    D->>D: abort write
  end
```

| Layer | Module | Contract |
|-------|--------|----------|
| **L0 safety** | `graph/safety/validators.py` | Reject `id::` deletion and protected-zone edits before disk |
| System (stable) | `semantic_lint/prompts.py` (re-export: `semantic_lint_prompts.py`) | Tier-1A compiler rules — **no** per-page alias map |
| Builder DI | `prompts/core.py`, domain `*/prompts.py` | Domain modules import **only** `core`; enforced in `test_daemon_prompts` |
| Stable user prefix | `page_prompt_session.py` | One block per file from `prepare_llm_context_payload` + optional alias footer |
| Task tail | `prompt_layout.py` | `build_cache_aligned_prompt` — content first, task last |
| Stateless turns | `InstructorLLMClient` | Injected builders; `stateless=True` for index/harvest/insights |
| Tier-2 law | `docs/openspec/agent/` → `SYSTEM_PROMPT.md` | `make build-system-prompt` / `make check-system-prompt` |
| Compression hygiene | `context_compressor.py`, `llm_client.py` | Ermes history condensation prose is `sanitize_prose_llm_completion()` before append/persist |

Detail: [`PROMPT_ARCHITECTURE.md`](PROMPT_ARCHITECTURE.md).

Bootstrap **Phase 1** and **MapReduce** harvest paths use the same layout (fixing the pre-v1.8 bootstrap prompt that placed page text after the task).

### Memory governance

| Structure | v1.8 policy |
|-----------|-------------|
| **BM25 corpus** | Postings-lite `doc_term_freqs` (not full token lists); `release_bm25_corpus()` after Phase 1; `MATRYCA_BM25_MODE=ondemand` optional |
| **Semantic cache RAM** | LRU cap (`MATRYCA_SEMANTIC_CACHE_MEMORY_ENTRIES`); TTL purge **skips** `master_catalog.json`, `backlink_counts.json`, `semantic_clusters.json` |
| **Master catalog** | `unload_master_catalog()` during `release_phase1_memory()` |
| **Telemetry** | `memory_budget.snapshot()` — RSS vs `MATRYCA_RAM_BUDGET_MB` |

After Phase 1 completes, `run_bootstrap_pipeline` calls `release_phase1_memory()` (generational cache clear, BM25 release, semantic RAM trim, catalog unload, `gc.collect()`), precomputes semantic clusters, then Phase 2 polling continues.

### Software edge (KV integrity, adaptive LLM, mmap)

| Mechanism | Module | Contract |
|-----------|--------|----------|
| **Frozen KV prefix** | `page_prompt_session.py`, `prompt_layout.py` | `FrozenPromptPrefix` + SHA-256 `verify_unchanged()`; ops JSONL `kv_prefix_hash` |
| **Adaptive structured output** | `llm_client.py` | `probe_backend()` → Path A (strict `json_schema`) or Path B (3-try self-correction); `StructuredOutputExhaustedError` on failure |
| **Resilient JSON (TRIZ)** | `json_repair.py`, `llm_client.py` | `max_tokens` cap + first-delimiter balanced extract + string-aware trailing trim + stack-ordered bracket close + Gemma tail sanitizer — see [`resilience-llm-json-triz.md`](resilience-llm-json-triz.md) |
| **mmap Phase 1 reads** | `markdown_io.py`, `master_catalog.py` | `mmap_graph_page()` + `extract_catalog_fields_from_mmap()` when `MATRYCA_GRAPH_READ_MMAP=true` |
| **CPU sandbox** | `process_priority.py` | `apply_cpu_sandbox()` — affinity + idle I/O when `MATRYCA_CPU_SANDBOX=true` and `psutil` installed (`[edge]` extra) |

Detail: [`v1.8-SOFTWARE-EDGE-PLAN.md`](v1.8-SOFTWARE-EDGE-PLAN.md).

### Cooperative I/O

| Mechanism | When | Typical sleep |
|-----------|------|----------------|
| `cooperative_yield.yield_host()` | Every `MATRYCA_BOOTSTRAP_YIELD_EVERY` files during `run_bootstrap_harvest` | `MATRYCA_YIELD_SLEEP_MS` (often 0) |
| `io_batch_pause_seconds()` | Non-LLM harvest steps | ~2 ms (`MATRYCA_BOOTSTRAP_IO_BATCH_PAUSE_MS`) — **not** thermal |
| `load_incoming_backlinks()` | Bootstrap / cache patch | Disk read of `backlink_counts.json` |
| `apply_cpu_sandbox()` / `apply_plumber_priority()` | Daemon foreground start | `nice(19)` + optional ionice |
| **Thermal pauses** | After each bootstrap / cognitive **LLM** turn | ≥ 1 s (`MATRYCA_THERMAL_DELAY_*`) |

Tests that assert thermal behavior filter `time.sleep` with `s >= 1.0` so micro-yields are not false positives.

Full operator and env reference: [`openspec/llm-performance.md`](openspec/llm-performance.md), [`v1.8-OPTIMIZATION-PLAN.md`](v1.8-OPTIMIZATION-PLAN.md).

---

## Structural link verification (v1.9)

**Goal:** Surface **knowledge rot** (dead URLs, missing assets) without LLM cost or blocking the duty-cycle event loop.

```mermaid
sequenceDiagram
  participant D as MaintenanceDaemon
  participant P as pages/*.md
  participant R as .matryca_link_registry.json
  participant NET as httpx HEAD
  participant J as journals/today.md

  Note over D,P: During run_cycle — passive extract
  D->>P: read page (fast-track or LLM path)
  D->>R: merge URL/asset entries keyed by block UUID

  Note over D,NET: End of cycle — verify batch
  D->>R: load pending entries
  D->>NET: HEAD URLs (timeout MATRYCA_LINK_VERIFY_TIMEOUT)
  D->>P: os.path.exists for assets
  alt strikes >= threshold
    D->>P: OCC write dead-link:: / missing-asset::
  end
```

| Property | Meaning |
|----------|---------|
| `dead-link:: true` | External URL failed HEAD or returned ≥400 |
| `missing-asset:: true` | Resolved asset path not on disk |

**Not created at bootstrap:** the registry file appears on first extract. It is **not** indexed as graph content.

---

## Agent-centric DX (v1.9)

**Goal:** Make the headless daemon and CLI **legible to external LLM hosts** while preserving the single `graph_dispatch` mutation plane.

```mermaid
flowchart TB
  subgraph hosts [External LLM hosts]
    Cursor[Cursor Claude Desktop scripts]
  end

  subgraph entry [Distribution surfaces]
    LLMS[llms.txt plus SYSTEM_PROMPT.md]
    UVX[uvx matryca-plumber PyPI wheel]
  end

  subgraph cli [matryca CLI]
    JSON["--json stdout"]
    CTX[context load]
    RST[read subtree]
    BootCLI[read bootstrap_status]
  end

  subgraph mcp [MCP eight tools]
    Read[read_graph_data]
    Search[search_graph]
    Mutate[mutate_graph plus ingest import_tana store_fact]
  end

  subgraph shared [Shared headless plane]
    GD[graph_dispatch.py]
    AST[logseq-matryca-parser plus ast_cache]
    Redact[redact_secrets_in_text]
  end

  Vault[(LOGSEQ_GRAPH_PATH)]

  Cursor --> LLMS
  Cursor --> UVX
  UVX --> cli
  UVX --> mcp
  JSON --> GD
  CTX --> GD
  RST --> GD
  BootCLI --> GD
  Read --> GD
  Search --> GD
  Mutate --> GD
  GD --> AST
  GD --> Redact
  AST --> Vault
```

**Journey Log** closes the operator feedback loop: after each active duty cycle, the daemon upserts **one** top-level bullet in `journals/YYYY_MM_DD.md`:

```markdown
- 🤖 Matryca Activity — indexed 12 page(s); checked 340 link(s); flagged 2 block(s); 47 duty cycle(s)
```

Daily totals live in `DaemonState.journey_day` (`JourneyDayLedger`); the journal line is rewritten in place under `page_rmw_lock`. Idle cycles with no metrics skip the write. Legacy per-cycle `## 🤖 Matryca Activity` sections on today's file are removed on first upsert. Inspired by LogseqBrain-style journal auditing; spec in [`openspec/agent-dx.md`](openspec/agent-dx.md) §4.

---

## Agent onboarding (v1.9.2)

**Goal:** Give autonomous agents a **single, versioned instruction surface** that matches the shipped PyPI wheel — without requiring a git checkout.

| Artifact | Role |
|----------|------|
| [`llms.txt`](../llms.txt) | Repo-root agent guide; linked from README agent callout |
| [`.well-known/llms.txt`](../.well-known/llms.txt) | Canonical path for tools that resolve `.well-known/llms.txt` |
| [`openspec/agent-onboarding.md`](openspec/agent-onboarding.md) | Maintainer contract: discovery paths, anti-patterns, sync checklist |

**Execution rules encoded in `llms.txt`:**

1. Set **`LOGSEQ_GRAPH_PATH`** (no `--graph` flag).
2. Run **`uvx matryca-plumber`** — never `git clone` + editable install unless the user explicitly develops from source.
3. Prefer **`--json`** for structured stdout; CLI applies `redact_secrets_in_text` before emission.
4. Use **`read` / `search` / `context load`** (or MCP on the same `graph_dispatch` plane) — never scrape `pages/*.md` by hand.

When CLI surface changes, update both `llms.txt` files in the same PR and ship a patch release so `uvx` consumers receive accurate commands.

---

## LLM OS agent contract (v1.9.5)

**Goal:** Give Tier-2 MCP/CLI agents a **deterministic Phase 1 gate** and explicit two-tier boundaries — without scraping raw files or impersonating the Gardener daemon.

| Component | Module / artifact | Role |
|-----------|-------------------|------|
| Cognitive law | [`SYSTEM_PROMPT.md`](../SYSTEM_PROMPT.md) § "LLM OS" | Soft Gate, Safe-Sync, tool sequence |
| Distribution pointer | [`llms.txt`](../llms.txt) §6 | PyPI hosts → full contract |
| Maintainer spec | [`openspec/llm-os-instructions.md`](openspec/llm-os-instructions.md) | Single source + v2.0 SQLite migration trigger |
| Phase 1 semaphore | `src/graph/bootstrap_status.py` | `read_graph_data` / `bootstrap_status` and CLI `read bootstrap_status` |
| L1 overlay | `matryca-l1/llm-os-rules.md` | Operator session rules (loaded via `read_graph_data` / `memory`) |

**Tier-2 session open (encoded in prompts):** `memory` → `bootstrap_status` → `Matryca Master Index` (page) → narrow reads. If `soft_gate_active`, pause and offer Local Daemon / Blind Search / Cloud Indexing; wait for explicit authorization before blind `bm25`.

```mermaid
flowchart TB
  subgraph tier1 [Tier 1 Gardener daemon only]
    D[MaintenanceDaemon Phase 1]
    D --> SemanticBlock["### Matryca Semantic Index per page"]
    D --> Catalog[master_catalog.json]
    D --> IndexPage["pages/Matryca Master Index.md"]
    Catalog --> IndexPage
  end

  subgraph tier2 [Tier 2 Cognitive Agent MCP or CLI]
    L1[read_graph_data memory]
    Status[read_graph_data bootstrap_status]
    IndexRead["read_graph_data page Matryca Master Index"]
    Gate{soft_gate_active?}
    Narrow[narrow page subtree xray_page]
    SearchRefine[search_graph bm25 refine only]
    L1 --> Status --> IndexRead --> Gate
    Gate -->|false green| Narrow
    Gate -->|true| Pause[Pause present 3 options]
    Pause --> OptA[Option A Local Daemon recommended]
    Pause --> OptB[Option B Blind Search authorized]
    Pause --> OptC[Option C Cloud Indexing authorized]
    OptB --> SearchRefine
    Narrow --> SearchRefine
  end

  IndexPage --> IndexRead
  Status -.->|"reads .matryca_daemon_state.json\nvia bootstrap_status.py"| Catalog

  tier1 -.->|"NEVER impersonate"| tier2
```

### `bootstrap_status` semaphore

`src/graph/bootstrap_status.py` merges daemon checkpoint fields with `is_bootstrap_catalog_complete()` so Tier-2 agents do not infer Phase 1 state from index existence alone.

```mermaid
sequenceDiagram
  participant Agent as Tier-2 MCP or CLI agent
  participant GD as graph_dispatch
  participant BS as bootstrap_status.py
  participant State as .matryca_daemon_state.json
  participant Disk as Master Index page

  Agent->>GD: read_graph_data bootstrap_status
  GD->>BS: collect_bootstrap_status
  BS->>State: load_daemon_state
  BS->>Disk: master_index present catalog stale?
  BS-->>Agent: JSON soft_gate_active bootstrap_complete progress

  alt soft_gate_active
    Agent-->>Agent: Soft Gate pause offer A B C
  else green gate
    Agent->>GD: read_graph_data page Matryca Master Index
    Agent->>GD: narrow reads then optional bm25 refine
  end
```

---

## Release engineering

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| [`.github/workflows/release.yml`](../.github/workflows/release.yml) | Tag push `v*` | Build frontend + wheel, GitHub Release notes from `CHANGELOG.md`, PyPI publish |
| [`.github/workflows/dependabot-uv-fix.yml`](../.github/workflows/dependabot-uv-fix.yml) | Dependabot PR open/sync | Runs `uv lock` on the PR branch and commits lockfile fixes so CI stays green |

Release notes are extracted with [`scripts/extract_changelog.py`](../scripts/extract_changelog.py) — do not rely on GitHub auto-generated commit summaries. See [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md).

---

## Distribution and entry points

### Zero-install and global install

```bash
uvx --from matryca-plumber matryca-plumber status   # CLI shorthand → plumber status
uv tool install matryca-plumber                      # matryca-plumber on PATH
```

Console scripts (`pyproject.toml`):

| Script | Target | Role |
|--------|--------|------|
| `matryca-plumber` | `plumber_entry:main` | CLI/MCP router |
| `matryca` | `cli:main` | Full `matryca` command tree |
| `matryca-logseq-llm-wiki` | `main:main` | Legacy MCP-only alias |

Background service: `matryca service install` → LaunchAgent / systemd user unit pointing at a **stable** `matryca-plumber` binary (not ephemeral `uvx` cache paths).

### Key modules

| Path | Role |
|------|------|
| `src/plumber_entry.py` | CLI vs MCP stdio disambiguation |
| `src/agent/maintenance_daemon.py` | Autonomous poll loop, ledger, detached spawn |
| `src/agent/page_prompt_session.py` | Per-page stable LLM prefix (v1.8 KV reuse) |
| `src/agent/prompts/core.py` | `SystemPromptBuilder`, Tier-1A/B compile helpers |
| `src/agent/semantic_lint/prompts.py` | Tier-1A semantic lint builder (rules 1–6) |
| `src/agent/semantic_lint_prompts.py` | Deprecated re-export → `semantic_lint.prompts` |
| `src/graph/safety/validators.py` | L0 `validate_llm_write_diff` before semantic commits |
| `scripts/build_system_prompt.py` | Assemble `SYSTEM_PROMPT.md` from agent fragments |
| `docs/PROMPT_ARCHITECTURE.md` | Clean Architecture map for prompts (plan v3) |
| `src/agent/memory_budget.py` | RSS snapshots, Phase 1 memory teardown |
| `src/agent/cooperative_yield.py` | Bootstrap / scan cooperative scheduling |
| `src/agent/llm_client.py` | Adaptive structured output, `InstructorLLMClient`, backend probe |
| `src/agent/process_priority.py` | `apply_cpu_sandbox()`, `nice` / optional ionice |
| `src/graph/backlink_index.py` | Persisted incoming wikilink counts |
| `src/graph/markdown_io.py` | mmap graph page reads (Phase 1 catalog path) |
| `src/cli/ui_server.py` | FastAPI monolith + static SPA + daemon control |
| `src/cli/ui_auth.py` | Bearer token resolution and verification |
| `src/agent/graph_dispatch.py` | Headless writes, OCC-aware block resolution |
| `src/graph/page_write_lock.py` | Per-page RMW lock + LRU registry; delegates OS flock to `platform_lock` |
| `src/utils/platform_lock.py` | Shared cross-process flock: NB + backoff + reentrancy (v1.10.6) |
| `src/graph/generated_hub_write.py` | OCC-safe Master Index / Graph Insights compile writes (v1.10.6) |
| `src/graph/markdown_blocks.py` | `atomic_write_bytes*`, OCC helpers |
| `src/agent/mcp_server.py` | `@mcp.tool()` handlers |
| `src/agent/ingestion.py` | `ingest_document` / `process_ingestion` |
| `src/agent/tana_import.py` | `import_tana` / `run_tana_import` |
| `src/agent/importers/tana/` | Tana JSON streaming import pipeline |
| `src/agent/memory_tools.py` | `store_fact` |
| `src/graph/link_verification.py` | Link rot registry, async verify, hygiene properties |
| `src/agent/journey_log.py` | Journey Log ledger + upsert of cumulative daily activity bullet |
| `src/agent/context_load.py` | `context load` semantic macro |
| `src/semantic/` | Dual block embeddings + hybrid semantic search |
| `src/agent/mcp_telemetry.py` | Loguru bridge, `id(ctx)` session map |
| `src/agent/mcp_tool_guard.py` | Tool error boundary (sanitized client messages) |
| `src/utils/llm_url_policy.py` | Shared SSRF policy for inference base URLs |
| `src/utils/config_paths.py` | Graph/log path allowlists for config writes |
| `src/graph/path_sandbox.py` | Graph-root confinement |
| `src/graph/graph_path_validate.py` | `pages/` validation + config allowlist wrapper |
| `frontend/` | Sovereign UI React sources → `frontend/dist/` |

---

## Phase evolution (mental map)

| Phase | Milestone | Architectural outcome |
|:-----:|-----------|------------------------|
| **1–3** | Headless plane + optional MCP | Parser-backed reads; DFS `write_logseq_outline`; BM25 local query |
| **7–8** | Mldoc + Ironclad Shield | Fence scanner, atomic writes, generational cache |
| **12** | Headless Revolution (v1.4) | Removed Logseq HTTP client; `graph_dispatch` only |
| **14** | Matryca Plumber OS | `MaintenanceDaemon`, Louvain GraphRAG, React cockpit |
| **15** | Logseq-native parity | Namespace encoding, OCC, frontmatter discipline, Trust UI |
| **16** | Enterprise Ironclad | Zero-Trust UI, subprocess daemon, SSRF guards, cross-platform lock |
| **1.5.15** | Ironclad consolidation | `plumber_entry` routing, MCP log bridge pickling fix, OCC ordering, atomic `.env`, UI launch validation, LRU page locks |
| **1.5.17** | Security depth pass | Shared LLM SSRF, graph path allowlist, MCP gate, split UI rate limits, **453** tests |
| **1.7.x** | Zero-Touch onboarding | Sovereign UI pre-flight, decoupled UI state, lock-before-LLM |
| **1.8** | Edge computing & performance | PagePromptSession, adaptive `llm_client`, mmap reads, CPU sandbox, backlink index, BM25 slimming, cooperative harvest, memory teardown |
| **1.8 round 4** | Pre-release audit | Stateless graph insights, compression persist sanitize, 8k block catalog, Phase 2 lock-on-write-only, `id::` excluded from property matchers |
| **1.9** | Structural graph hygiene | Link verification sidecar, Journey Log, CLI `--json`, `context load`, `read subtree` |
| **1.9.9** | Security & Sandbox | `read_graph_file_text()` migration, bounded JSON, link-registry validation, CI `sandbox-read-check`, debug-log allowlist |
| **1.10.0** | Catalog/registry integrity | Master catalog flock load + merge-on-save; link registry atomic save; harvest OCC catalog guard ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)–[#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37), [#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)); OSS CI maturity |
| **1.10.3** | UI/LLM hardening | Non-blocking Sovereign UI config saves; strict Pydantic LLM/outline contracts; recursive OpenAI strict JSON Schema; flock sidecars `0o600` |
| **1.11.2** | Graph layer boundary + bounded RAM | `post_write` port ([#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134)); graph canonical modules; generational + block-vector LRU; OCC `st_mtime_ns` page writes ([#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) partial); `env_parse` shared helpers |
| **1.11.1** | Parser 1.4.0 alignment | `logseq-matryca-parser>=1.4.0`; canonical page iteration; case-insensitive tag/search; watcher delete/move; SYNAPSE embed safety |
| **1.11.0** | Tana → Logseq OG import | `ijson` streaming loader; hybrid placement; `config.edn` journals; depth-split; `tana-id` idempotency; CLI + MCP `import_tana` (879+ tests) |
| **1.10.6** | Concurrency integrity | Unified `platform_lock` flock for page + JSON sidecars ([#40](https://github.com/MarcoPorcellato/matryca-plumber/issues/40)); hub page OCC via `write_generated_hub_page` ([#34](https://github.com/MarcoPorcellato/matryca-plumber/issues/34)); contributor backlog hygiene |
| **1.10.5** | Parser 1.3.1 alignment | `logseq-matryca-parser>=1.3.1`; root public API imports; AST cache `discover_graph_files`; graph parity 1.2.x inherited |
| **1.10.4** | CI/deps maintenance | GitHub Actions toolchain refresh; Sovereign UI frontend npm bumps; Dependabot weekly groups |
| **Unreleased** | Master RFC Phases 1–3 (remaining) | Identity + ingest + optional dual embedding shipped; biological memory decay Phase A in tree |

---

## Related reading

- [`PROJECT_DIARY.md`](PROJECT_DIARY.md) — chronological decisions and release notes
- [`resilience-llm-json-triz.md`](resilience-llm-json-triz.md) — TRIZ / local LLM JSON resilience (Gemma tail, compression hygiene, audit table)
- [`v1.8-OPTIMIZATION-PLAN.md`](v1.8-OPTIMIZATION-PLAN.md) — v1.8 scope, env vars, verification
- [`v1.8-SOFTWARE-EDGE-PLAN.md`](v1.8-SOFTWARE-EDGE-PLAN.md) — CPU sandbox, frozen prefix, adaptive LLM, mmap
- [`openspec/llm-performance.md`](openspec/llm-performance.md) — LLM performance engineering contract
- [`openspec/identity-config.md`](openspec/identity-config.md) — Telos / AI Constraints and `store_fact`
- [`openspec/ingest.md`](openspec/ingest.md) — atomic `ingest_document` pipeline
- [`openspec/tana-import.md`](openspec/tana-import.md) — Tana workspace JSON import (`import_tana`, CLI dry-run)
- [`openspec/link-verification.md`](openspec/link-verification.md) — URL/asset hygiene (v1.9)
- [`openspec/security-sandbox.md`](openspec/security-sandbox.md) — path sandbox, bounded JSON, CI read gate (v1.9.9)
- [`openspec/agent-dx.md`](openspec/agent-dx.md) — CLI JSON, context macro, Journey Log (v1.9)
- [`openspec/agent-onboarding.md`](openspec/agent-onboarding.md) — `llms.txt` / PyPI `uvx` agent contract (v1.9.2)
- [`openspec/llm-os-instructions.md`](openspec/llm-os-instructions.md) — two-tier LLM OS, Soft Gate, `bootstrap_status` (v1.9.5)
- [`openspec/live-telemetry-ui.md`](openspec/live-telemetry-ui.md) — Sovereign UI live telemetry (v1.9.3)
- [`../llms.txt`](../llms.txt) — agent execution guide (mirrored under `.well-known/`)
- [`SYSTEM_PROMPT.md`](../SYSTEM_PROMPT.md) — agent OCC and persist-first `id::` policy
- [`../README.md`](../README.md) — operator quick start
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — `make check`, dev setup
- [`roadmaps/`](roadmaps/) — phased delivery checklists
- [`../SECURITY.md`](../SECURITY.md) — vulnerability reporting
