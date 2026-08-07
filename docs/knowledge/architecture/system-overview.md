---
type: Architecture
title: System overview
description: Three-surface runtime, shared mutation plane, vault topology, and daemon phase model.
resource: src/
tags: [architecture, daemon, mcp, sovereign-ui, graph-dispatch]
generated: { by: human:marco-porcellato, at: '2026-07-18T00:00:00Z' }
verified: { by: human:marco-porcellato, at: '2026-08-06T00:00:00Z' }
last_verified: 2026-08-06
stale_after: 2027-02-02
status: stable
classification: canonical
canonical_for: architecture.summary
audience: [maintainer, contributor, operator]
owner: core-runtime
supersedes: []
related:
  - /architecture/graph-plane.md
  - /architecture/shadow-db.md
legacy_sources:
  - ../../ARCHITECTURE.md
  - ../../CLEAN_CODE_ARCHITECTURE.md
  - ../../PROMPT_ARCHITECTURE.md
  - ../../openspec/logseq-paradigm.md
---

# System overview

This maintained concept is the canonical progressive-disclosure overview. [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) remains the detailed architecture contract.

Matryca Plumber is a **local-first background AI daemon** that mutates Logseq OG Markdown on disk. It is not a Logseq plugin, not a cloud service, and not dependent on Logseq HTTP JSON-RPC. Humans and the daemon co-edit the same `.md` trees. Safety on the graph plane — AST parity, OCC, path sandboxing — is documented in [Graph plane](graph-plane.md). Operator Trust & Safety tiers remain in the legacy architecture contract.

## Clean Architecture map

Matryca maps Robert C. Martin's concentric rings to Python packages. **Dependencies point inward:** frameworks (FastMCP, FastAPI) → adapters (`graph_dispatch`, `mcp_server`, `cli`) → use cases (`maintenance_daemon`, `plumber_modules`) → domain (`src/graph/`, `safety/validators`, `utils/env_parse`) → entities (Logseq blocks, Pydantic lint models).

| Enforcement | Mechanism |
| --- | --- |
| Graph layer isolation | `tests/test_graph_layer_boundary.py` — no `graph` → `agent` / `daemon` imports |
| Prompt domain isolation | `tests/test_daemon_prompts.py` — `*/prompts.py` imports only `prompts/core.py` |
| Fat modules, thin edges | MCP/CLI delegate to `graph_dispatch` / `graph/*` |

Full contributor SSOT: [`CLEAN_CODE_ARCHITECTURE.md`](../../CLEAN_CODE_ARCHITECTURE.md). Prompt tiers: [`PROMPT_ARCHITECTURE.md`](../../PROMPT_ARCHITECTURE.md).

## Three-surface runtime

Matryca Plumber evolved from an MCP-first bridge into a **three-surface runtime** that shares one headless mutation plane:

| Surface | Technology | Primary role |
| --- | --- | --- |
| **Maintenance daemon** | Python (`MaintenanceDaemon`) | Autonomous duty-cycle scans, semantic indexing, cognitive lint, ledger checkpoints |
| **Sovereign UI** | React SPA + FastAPI (`ui_server.py`) | Loopback control room: telemetry, Trust & Safety toggles, daemon lifecycle, `.env` hot-swap |
| **MCP sidecar** | FastMCP stdio (`main.py`) | Optional tool host for Claude Desktop, Cursor, Hermes Agent, and other MCP clients — **same `graph_dispatch` contract** |

**FastMCP is auxiliary.** The product's center of gravity is `matryca plumber start` plus the Sovereign UI. MCP attaches the identical read/write path when an external host spawns `matryca-plumber` without CLI-shaped arguments.

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

**Quality bar:** Mypy strict on `src` and `tests`, Ruff lint/format clean via `make ci`; maintainer gates include `make agents-check` and `make check-system-prompt`.

## Separation of concerns

| Surface | Entry | Role |
| --- | --- | --- |
| **Maintenance daemon** | `matryca plumber start` → `src/agent/maintenance_daemon.py` | Polls `pages/` and `journals/`, calls a local OpenAI-compatible endpoint, commits through `graph_dispatch.py`, cognitive modules, and OCC |
| **Sovereign UI** | `matryca plumber ui` → `src/cli/ui_server.py` | Monolithic Uvicorn on loopback; REST + static SPA; reads daemon checkpoints — never a second source of truth |
| **MCP sidecar** | `matryca-plumber` with no CLI argv → `src/main.py` | Five polymorphic mega-tools plus `store_fact`, `ingest_document`, `import_tana`; lazy AST bootstrap on large vaults |

The daemon orchestrator delegates to `daemon_*` modules. `graph_dispatch.py` routes through `dispatch_*_handlers.py` and `GraphReadPort` adapters — see [Graph plane](graph-plane.md) for the mutation contract.

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

**Invariant:** one **system of record** — `LOGSEQ_GRAPH_PATH`. No auxiliary database for the default read path, no Logseq Electron dependency, no split-brain HTTP API for background work.

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

Daily fleeting notes under **`journals/`** receive structural indexing only in Phase 2; semantic LLM indexing is skipped for journals. Detail: [`openspec/llm-performance.md`](../../openspec/llm-performance.md).

## Architecture pilots

| Topic | Pilot document |
| --- | --- |
| Graph plane (parser, OCC, sandbox) | [Graph plane](graph-plane.md) |
| Shadow DB read cache (opt-in) | [Shadow DB](shadow-db.md) |

## Legacy deep dives

This pilot omits operational depth available in the legacy architecture contract:

| Topic | Legacy document |
| --- | --- |
| Graph plane (full OCC/sandbox) | [`ARCHITECTURE.md`](../../ARCHITECTURE.md#optimistic-concurrency-control-occ) · [pilot](graph-plane.md) |
| Shadow DB | [`ARCHITECTURE.md`](../../ARCHITECTURE.md) · [pilot](shadow-db.md) |
| Trust & Safety tiers | [`ARCHITECTURE.md`](../../ARCHITECTURE.md#trust--safety-levels) |
| Runtime bootstrap | [`ARCHITECTURE.md`](../../ARCHITECTURE.md#runtime-bootstrap) |
| Sandboxing (normative) | [`openspec/security-sandbox.md`](../../openspec/security-sandbox.md) |
| Release engineering | [`RELEASE_PROCESS.md`](../../RELEASE_PROCESS.md) |
| Maintainer timeline | [`PROJECT_DIARY.md`](../../PROJECT_DIARY.md) |
| Agent runtime law | [`SYSTEM_PROMPT.md`](../../../SYSTEM_PROMPT.md) |
