# Matryca Plumber

[![CI](https://github.com/MarcoPorcellato/matryca-plumber/actions/workflows/ci.yml/badge.svg)](https://github.com/MarcoPorcellato/matryca-plumber/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/matryca-plumber.svg)](https://pypi.org/project/matryca-plumber/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/matryca-plumber.svg)](https://pypi.org/project/matryca-plumber/)
[![GitHub release](https://img.shields.io/github/v/release/MarcoPorcellato/matryca-plumber?display_name=tag)](https://github.com/MarcoPorcellato/matryca-plumber/releases)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-blue?logo=python&logoColor=white)](https://github.com/MarcoPorcellato/matryca-plumber/blob/main/pyproject.toml#L10)
[![Tests](https://img.shields.io/badge/tests-1139%2B%20passing-brightgreen)](https://github.com/MarcoPorcellato/matryca-plumber/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-%E2%89%A570%25-brightgreen)](https://github.com/MarcoPorcellato/matryca-plumber/blob/main/pyproject.toml#L138)

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![mypy](https://img.shields.io/badge/mypy-strict-2b6cb0)](https://github.com/MarcoPorcellato/matryca-plumber/blob/main/CONTRIBUTING.md)
[![License](https://img.shields.io/github/license/MarcoPorcellato/matryca-plumber)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#what-it-does)
[![Local-first](https://img.shields.io/badge/local--first-100%25%20offline-2ea44f)](#what-it-does)
[![MCP](https://img.shields.io/badge/MCP-FastMCP%20stdio-6366f1)](#what-it-does)
[![Logseq OG](https://img.shields.io/badge/Logseq-OG%20Markdown-0052CC)](https://github.com/logseq/logseq)
[![Security](https://img.shields.io/badge/security-policy-important)](SECURITY.md)
[![Contributing](https://img.shields.io/badge/contributing-guide-blue)](CONTRIBUTING.md)
[![Code of Conduct](https://img.shields.io/badge/code%20of%20conduct-Contributor%20Covenant-4baaaa)](CODE_OF_CONDUCT.md)
[![Discussions](https://img.shields.io/github/discussions/MarcoPorcellato/matryca-plumber)](https://github.com/MarcoPorcellato/matryca-plumber/discussions)
[![Sponsors](https://img.shields.io/github/sponsors/MarcoPorcellato)](https://github.com/sponsors/MarcoPorcellato)
![Views](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/MarcoPorcellato/matryca-plumber/metrics/metrics/views-badge.json)
![Clones](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/MarcoPorcellato/matryca-plumber/metrics/metrics/clones-badge.json)

> I gave my AI access to my notes. It corrupted them.  
> I built Matryca Plumber so that never happens again.

<p align="center"><strong>CLI · MCP · background daemon · Sovereign UI · Logseq OG · OCC-safe · local-first</strong></p>

<p align="center">
  <a href="#get-started-60-seconds">Install</a> ·
  <a href="#tana--logseq-og-migration">Tana import</a> ·
  <a href="#how-it-works-30-seconds">Architecture</a> ·
  <a href="#how-it-compares">Compare</a> ·
  <a href="llms.txt">Agents</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#community">Community</a> ·
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center"><sub>
  <b>AI agents:</b> read <a href="llms.txt"><code>llms.txt</code></a> — run <code>uvx matryca-plumber --help</code>; do not parse Markdown manually.
</sub></p>

**Matryca Plumber** is the definitive bridge between your trusted AI agent and your **Logseq OG** vault — a **headless CLI** and **MCP server** for safe read/write on Logseq's block tree (no raw Markdown parsing, no Logseq API, no silent overwrites), plus a **background daemon** and **Sovereign UI**. **v1.11.0** adds **Tana → Logseq OG migration**; **v1.11.1** aligned **`logseq-matryca-parser` 1.4.0**; **v1.11.2** refactors the **graph layer boundary**; **v1.12.0** applies **Clean Architecture** to Tier-1 prompts, L0 write safety, and fragment-assembled `SYSTEM_PROMPT.md`; **v1.12.1** adds contributor **Clean Code** docs and a **v2.0 preparation** index; **v1.13.0** ships **daemon/dispatch modularization** ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58), [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59)) and **`GraphReadPort`** (v2 Phase 1); **v1.13.1** pins **`logseq-matryca-parser` 1.6.0** with headless newline parity; **v1.14.0** hardens **`MasterCatalog` write-safety**, the file watcher, and leaf-module dependency direction after the 2026-07-16 audit; **v2.0.0-alpha** ships an **opt-in Shadow DB** read cache (`MATRYCA_SHADOW_DB_ENABLED`, default off) with FTS5 BM25 + recursive CTE subtree reads and Markdown/BM25 fallback; **v2.0.0-alpha.5** closes the seven-axis Shadow hardening campaign while preserving the opt-in default and Markdown/BM25 fallback. Built on [Andrej Karpathy's LLM-Wiki vision](https://karpathy.ai/blog). **Current published prerelease: v2.0.0-alpha.5** — [`CHANGELOG.md`](CHANGELOG.md). **`v2.0.0-beta.1` is a candidate, not a release**; its readiness gates are tracked in [`docs/quality/issue-bodies/v2-beta-readiness.md`](docs/quality/issue-bodies/v2-beta-readiness.md).

**Developed by [Marco Porcellato](https://github.com/MarcoPorcellato) · [Matryca.ai](https://matryca.ai)** — the product name is **Matryca Plumber** (not “Matryca” alone). See [`docs/BRANDING.md`](docs/BRANDING.md).

![Matryca Plumber — Agentic Knowledge Management for Logseq OG](images/matryca-plumber-1-5-10-demo.gif)

## What it does

- **Tana → Logseq OG import** — `matryca import tana --file export.json [--apply]` and MCP **`import_tana`** stream Tana workspace JSON into your vault: `ijson` anti-OOM parsing, `logseq/config.edn` journal routing, depth-split, catalog wikilink resolution, `tana-id` idempotent OCC writes — **dry-run by default** ([`docs/openspec/tana-import.md`](docs/openspec/tana-import.md))
- **Agent CLI** — `matryca --json read`, `context load`, `read subtree` — structured access to pages and block trees without hand-parsing `.md`
- **MCP server** — eight FastMCP stdio tools for Cursor / Claude Desktop; query and mutate the graph headlessly (`MATRYCA_MCP_ENABLED=true` when you trust the host)
- **Logseq-native writes** — `logseq-matryca-parser` AST compliance: line-0 frontmatter, `+2` block properties, namespace encoding — agents stop breaking vaults
- **OCC safety** — `st_mtime` snapshots + page locks; if you edited while the model was thinking, the commit aborts — your typing always wins
- **Background daemon** — semantic summaries, dangling `[[link]]` healing, entity consolidation while you sleep (local LLM via LM Studio / Ollama)
- **Sovereign UI** — browser dashboard at `:8500`; pre-flight checklist, trust tiers, live telemetry — configure everything without terminal env vars
- **Link hygiene** — background URL/asset checks, Journey Log in today's journal — no per-cycle journal spam
- **L0 write safety** — semantic index commits abort when an LLM diff would delete `id::` lines or edit protected zones (`graph/safety/validators.py`)
- **Tier-1 prompt architecture** — domain `*/prompts.py` builders + DI on `InstructorLLMClient`; `SYSTEM_PROMPT.md` assembled from OpenSpec fragments (`make build-system-prompt`)
- **Shadow DB (v2.0.0-alpha.5, opt-in)** — daemon-owned `shadow.sqlite` read cache: FTS5 BM25 + recursive CTE subtree when `MATRYCA_SHADOW_DB_ENABLED=true` and health is `ready`; CTE depth-truncation status (#289); state API path redaction (#293); FTS query length bound (#279); hyphenated FTS query fix (#277); incremental rename stale-owner fix (#272); cross-process writer flock + meta/pages validation; generational BM25 + parser fallback otherwise — see [`llms.txt`](llms.txt) §2.6
- **100% local-first** — vault stays on disk; no cloud API key required

## Tana → Logseq OG migration

Export your Tana workspace as JSON (**Export workspace as JSON** in Tana), then import into a **clone** of your Logseq graph first:

```bash
export LOGSEQ_GRAPH_PATH=/path/to/your/logseq/graph

# Dry-run (default) — JSON report on stdout; stderr warns no writes
matryca import tana --file ~/Downloads/workspace.json | jq '.write'

# Commit after reviewing counters
matryca import tana --file ~/Downloads/workspace.json --apply | jq '.write.pages_created'
```

| Tana concept | Logseq OG destination |
|--------------|----------------------|
| Entity / supertag page | `Tana/{Supertag}/{Name}` under `pages/` |
| `#day` / calendar node | `journals/` (title from your `logseq/config.edn`) |
| Nested children | Indented bullets with fresh `id::` UUIDs |
| Tana node ID | `tana-id::` property (idempotent re-import skip) |

Full pipeline spec: [`docs/openspec/tana-import.md`](docs/openspec/tana-import.md) · MCP: **`import_tana(export_path, dry_run=True)`**

## How it works (30 seconds)

CLI, MCP, daemon, and Sovereign UI converge on **one OCC-protected mutation plane** — same vault on disk, no Logseq HTTP API.

```mermaid
flowchart TB
  subgraph operators [Operators and agents]
    Human[Human · Logseq optional]
    UI[Sovereign UI :8500]
    Daemon[Maintenance daemon]
    CLI[matryca CLI --json]
    MCP[FastMCP stdio optional]
  end

  subgraph plane [Shared headless mutation plane]
    GD[graph_dispatch]
    Lock[OCC + page_rmw_lock\n+ platform_lock flock]
    Parser[logseq-matryca-parser]
    GD --> Lock
    GD --> Parser
  end

  subgraph local [Local inference — 100% offline]
    LLM[LM Studio / Ollama]
  end

  subgraph vault [LOGSEQ_GRAPH_PATH — single source of truth]
    Pages[pages/ · journals/ · templates/]
    Meta[.matryca_* cache & ledgers\nmatryca-l1/ session rules]
  end

  Human <-->|co-edit Markdown| Pages
  UI -->|start · stop · config · telemetry| Daemon
  Daemon -->|Phase 1 harvest · Phase 2 lint| GD
  Daemon <-->|structured JSON| LLM
  CLI --> GD
  MCP --> GD
  Lock -->|atomic UTF-8 writes| Pages
  Meta -.-> GD
```

- **Single mutation plane** — `graph_dispatch` + OCC locks; CLI, MCP, and daemon share the same write contract
- **Phase 1 → Phase 2** — catalog harvest, then cognitive lint against a local LLM
- **Parser-first** — agents never touch raw Markdown; the AST layer handles Logseq quirks
- **One vault path** — `LOGSEQ_GRAPH_PATH` (set in the Sovereign UI or `.env`)

→ [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Get started (60 seconds)

```bash
# 1 — Try instantly (opens Sovereign UI in your browser)
uvx --from matryca-plumber matryca-plumber status

# 2 — Configure in the browser — no terminal env vars needed
#    Pre-flight → Settings (gear) → Logseq Graph Path → local LLM → Start Engine

# 3 — Optional: install globally + background service
uv tool install matryca-plumber
matryca service install
```

The first command opens the **Sovereign UI** at [http://127.0.0.1:8500](http://127.0.0.1:8500). Use the pre-flight wizard to point at your vault, pick a local LLM, and click **Start Engine**. The daemon does not run until you confirm.

| Command | What it starts | Browser / `:8500` | Maintenance daemon |
|---------|----------------|-------------------|----------------------|
| **`matryca plumber status`** (recommended) | Sovereign UI + local API | Yes | No — use **Start Engine** or `plumber start` |
| **`matryca plumber ui`** | Same as `status` | Yes | No |
| **`matryca plumber start`** | Background daemon only | No | Yes |
| **`matryca plumber stop`** | — | — | Stops daemon |

**Common mistake:** `matryca plumber start` does **not** open the dashboard — run `matryca plumber status` (or use **Start Engine** from the UI).

## How it compares

| Feature | Matryca Plumber | Official Logseq AI Plugin | Obsidian LLM Plugins |
|---------|-----------------|----------------------------|----------------------|
| Local-only | Yes — vault stays on disk | Typically cloud-backed | Mixed (local + cloud options) |
| No API Key required | Yes — local LLM endpoint | Usually requires provider API key | Often requires API key |
| OCC Safety (no corruption) | Yes — `st_mtime` + page locks | No comparable write guard | No standard OCC layer |
| MCP Support | Yes — FastMCP stdio tools | No | Varies by plugin |
| Agent CLI (structured graph access) | Yes — `matryca --json` | No | Varies by plugin |
| Tana workspace import | Yes — `import tana` / `import_tana` (dry-run default) | No | No |

*Matryca Plumber targets Logseq OG (Markdown on disk); Obsidian comparisons refer to common community plugins, not a single product.*

## Clone your graph first

Matryca Plumber edits local `.md` files directly. OCC prevents silent data loss, but **test on a clone first** — especially before **`import tana --apply`**:

1. Duplicate your graph folder (e.g. `MyGraph` → `MyGraph_Test`) and add it in Logseq via **Add new graph**.
2. **If you use Logseq Sync:** do *not* enable Sync on the test graph.
3. In the Sovereign UI: **Settings** → **Logseq Graph Path** → point at the clone → Save.

Once comfortable, switch to your main graph in Settings.

## Trust & Safety

You are in control. Nothing mutates your prose unless you explicitly enable it in the UI.

| Mode | Risk | What it allows |
|------|------|----------------|
| 🟢 **Safe Mode** | Read-only | Semantic cache, entity consolidation (`alias::`), property hygiene — **never edits bullet text**. |
| 🟠 **Augmented Mode** | Side-blocks | **Heal Dangling Links**, **Backpropagate Links** — original bullets stay intact. |
| 🔴 **Surgeon Mode** | Inline edits | **Inline Semantic Corrections**, **Auto-Split Dense Blocks** — **strictly opt-in**. |

> "Logseq is building the best local outliner database. But AI Agent memory is at the very bottom of their roadmap. Matryca Plumber gives you that future today, safely bridging your local agents to your Logseq graph without waiting years." — Marco Porcellato, Matryca.ai

<details>
<summary><b>Agent CLI & MCP</b></summary>

Point the vault in the Sovereign UI (or `.env`) — agents inherit `LOGSEQ_GRAPH_PATH`.

```bash
matryca --json read page "My Project"
matryca context load "My Project"
matryca import tana --file ~/Downloads/workspace.json   # dry-run; add --apply to write
```

Eight MCP tools (five mega-tools + **`store_fact`** + **`ingest_document`** + **`import_tana`**) — `MATRYCA_MCP_ENABLED=true` when you trust the host. Spec: [`llms.txt`](llms.txt) · [`docs/openspec/agent-dx.md`](docs/openspec/agent-dx.md) · [`docs/openspec/tana-import.md`](docs/openspec/tana-import.md) · [`docs/openspec/agent-onboarding.md`](docs/openspec/agent-onboarding.md)

</details>

<details>
<summary><b>Sovereign UI, configuration & full capabilities</b></summary>

**UI** (`:8500`) — pre-flight checklist, live telemetry, trust tiers, Bearer auth ([`SECURITY.md`](SECURITY.md)). Recommended LLM: **Gemma 4-E4b Instruct** (`gemma-4-e4b-it`) on 16 GB RAM.

**Daemon** — semantic indexing, dangling links, entity consolidation, auto-split, `ingest_document`, `import_tana`, link verification, LLM OS Soft Gate. OpenSpec: [`docs/openspec/README.md`](docs/openspec/README.md).

**Advanced `.env`** — copy [`.env.example`](.env.example); Tana knobs: `MATRYCA_TANA_IMPORT_NAMESPACE`, `MATRYCA_TANA_DEPTH_LIMIT`; edge profile for large vaults: [`docs/v1.8-OPTIMIZATION-PLAN.md`](docs/v1.8-OPTIMIZATION-PLAN.md). Release history: [`CHANGELOG.md`](CHANGELOG.md).

</details>

## Community

| Channel | Use for |
|---------|---------|
| [GitHub Issues](https://github.com/MarcoPorcellato/matryca-plumber/issues) | Bugs, feature requests, trackable work |
| [GitHub Discussions](https://github.com/MarcoPorcellato/matryca-plumber/discussions) | RFCs, architecture debate ([#19 — v2 Shadow DB](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)) |
| [Good first issues](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) | Scoped starter tasks — see [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) |
| [`SUPPORT.md`](SUPPORT.md) | Where to ask vs where to file bugs |
| [Logseq forum](https://discuss.logseq.com/) | Logseq OG ecosystem questions |
| [Sponsor](https://github.com/sponsors/MarcoPorcellato) | Support ongoing maintenance |

**Code of conduct:** report concerns to marco@matryca.ai — see [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

New contributors: start with [`docs/FIRST_CONTRIBUTION.md`](docs/FIRST_CONTRIBUTION.md), then [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Developer setup

```bash
git clone https://github.com/MarcoPorcellato/matryca-plumber.git && cd matryca-plumber
make install
cd frontend && npm install && npm run build && cd ..
make test-fast    # fast loop (~5s)
make ci           # full CI gate before PR (format-check + lint + types + tests)
```

## Documentation

| Start here | Go deeper |
|------------|-----------|
| [`AGENTS.md`](AGENTS.md) | [`docs/PROMPT_ARCHITECTURE.md`](docs/PROMPT_ARCHITECTURE.md) — Clean Architecture for prompts |
| [`SUPPORT.md`](SUPPORT.md) | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | [`docs/openspec/README.md`](docs/openspec/README.md) |
| [`docs/FIRST_CONTRIBUTION.md`](docs/FIRST_CONTRIBUTION.md) | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| [`llms.txt`](llms.txt) | [`docs/openspec/tana-import.md`](docs/openspec/tana-import.md) |
| [`ROADMAP.md`](ROADMAP.md) | [`CHANGELOG.md`](CHANGELOG.md) |
| [**v2.0 preparation**](docs/roadmaps/ROADMAP_V2_PREPARATION.md) | [v2 issues `label:v2.0`](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3Av2.0) · [`v2_preparation_blueprints.md`](v2_preparation_blueprints.md) |
| [`SYSTEM_PROMPT.md`](SYSTEM_PROMPT.md) | [`docs/integrations/hermes-agent.md`](docs/integrations/hermes-agent.md) |
| [Good first issues](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) | [`good_first_issues_blueprints.md`](good_first_issues_blueprints.md) |
| [`docs/releases/v2.0.0-alpha.5-GITHUB.md`](docs/releases/v2.0.0-alpha.5-GITHUB.md) | GitHub Release body for v2.0.0-alpha.5 (hardening campaign close) |
| [`docs/releases/v2.0.0-alpha.4-GITHUB.md`](docs/releases/v2.0.0-alpha.4-GITHUB.md) | GitHub Release body for v2.0.0-alpha.4 (FTS query bound + Axis 4 green) |
| [`docs/releases/v2.0.0-alpha.3-GITHUB.md`](docs/releases/v2.0.0-alpha.3-GITHUB.md) | GitHub Release body for v2.0.0-alpha.3 (FTS hyphen fix + Axis 4 audit) |
| [`docs/releases/v2.0.0-alpha.2-GITHUB.md`](docs/releases/v2.0.0-alpha.2-GITHUB.md) | GitHub Release body for v2.0.0-alpha.2 (rename fix + routing audit) |
| [`docs/releases/v2.0.0-alpha.1-GITHUB.md`](docs/releases/v2.0.0-alpha.1-GITHUB.md) | GitHub Release body for v2.0.0-alpha.1 (Shadow DB Axis 1 hardening) |
| [`docs/releases/v2.0.0-alpha-GITHUB.md`](docs/releases/v2.0.0-alpha-GITHUB.md) | GitHub Release body for v2.0.0-alpha (Shadow DB opt-in read path; superseded by alpha.1) |
| [`docs/releases/v1.14.0-GITHUB.md`](docs/releases/v1.14.0-GITHUB.md) | Draft GitHub Release body for v1.14.0 (minor, catalog write-safety + Tier F) |
| [`docs/releases/v1.13.1-GITHUB.md`](docs/releases/v1.13.1-GITHUB.md) | Draft GitHub Release body for v1.13.1 (patch, parser 1.6.0 alignment) |
| [`docs/releases/v1.13.0-GITHUB.md`](docs/releases/v1.13.0-GITHUB.md) | Draft GitHub Release body for v1.13.0 (minor, daemon/dispatch refactor + GraphReadPort) |
| [`docs/releases/v1.12.1-GITHUB.md`](docs/releases/v1.12.1-GITHUB.md) | Draft GitHub Release body for v1.12.1 (patch, contributor + v2 index) |
| [`docs/releases/v1.12.0-GITHUB.md`](docs/releases/v1.12.0-GITHUB.md) | GitHub Release body for v1.12.0 (minor, plan v3) |
| [`docs/releases/v1.11.2-GITHUB.md`](docs/releases/v1.11.2-GITHUB.md) | Copy-paste GitHub Release body for v1.11.2 |
| [`docs/releases/v1.11.1-GITHUB.md`](docs/releases/v1.11.1-GITHUB.md) | Copy-paste GitHub Release body for v1.11.1 |

## License

Apache-2.0 — see [LICENSE](LICENSE).

![Matryca Plumber Cover](images/20260519-Logseq-Matryca-LLM-Wiki-copertina-github.jpg)

## Star History

<a href="https://www.star-history.com/?repos=MarcoPorcellato%2Fmatryca-plumber&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=MarcoPorcellato/matryca-plumber&type=date&theme=dark&legend=top-left&sealed_token=L7JFuvfcyM3kFDgnbjboRX3XieIF-HhrqN1r74nO9x01siHlrhFq-4e5Z6wu9l_hl91VwwM_j_mSx5K37NftjyQSV5AX4jQpqsHF-NvXirIrdxGxRjCEyGt0pnnGNYnoXyju4jz4EmLb9KiEhuUNRPR2Wn7irfUYwX9-T_lxqoj8nHBKKPuW8P5iSTiX" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=MarcoPorcellato/matryca-plumber&type=date&legend=top-left&sealed_token=L7JFuvfcyM3kFDgnbjboRX3XieIF-HhrqN1r74nO9x01siHlrhFq-4e5Z6wu9l_hl91VwwM_j_mSx5K37NftjyQSV5AX4jQpqsHF-NvXirIrdxGxRjCEyGt0pnnGNYnoXyju4jz4EmLb9KiEhuUNRPR2Wn7irfUYwX9-T_lxqoj8nHBKKPuW8P5iSTiX" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=MarcoPorcellato/matryca-plumber&type=date&legend=top-left&sealed_token=L7JFuvfcyM3kFDgnbjboRX3XieIF-HhrqN1r74nO9x01siHlrhFq-4e5Z6wu9l_hl91VwwM_j_mSx5K37NftjyQSV5AX4jQpqsHF-NvXirIrdxGxRjCEyGt0pnnGNYnoXyju4jz4EmLb9KiEhuUNRPR2Wn7irfUYwX9-T_lxqoj8nHBKKPuW8P5iSTiX" />
 </picture>
</a>
