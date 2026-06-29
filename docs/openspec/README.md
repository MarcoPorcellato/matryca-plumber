# Openspec-style notes (Matryca Plumber)

**Matryca Plumber** — developed by Marco Porcellato · [Matryca.ai](https://matryca.ai). Naming rules: [`../BRANDING.md`](../BRANDING.md).

Trimmed behavioral specs aligned with [MehmetGoekce/llm-wiki](https://github.com/MehmetGoekce/llm-wiki) openspec, mapped to this repository.

**Canonical checklists:** [`roadmaps/ROADMAP_LLM_WIKI.md`](../roadmaps/ROADMAP_LLM_WIKI.md), [`roadmaps/ROADMAP_LLM_WIKI_PHASE_3.md`](../roadmaps/ROADMAP_LLM_WIKI_PHASE_3.md).

| Document | Scope |
|----------|--------|
| [`live-telemetry-ui.md`](live-telemetry-ui.md) | v1.9.3 Sovereign UI polling; v1.9.11 graph-analytics cache/timeout/offline handling; v1.10.3 non-blocking config saves. |
| [`agent-onboarding.md`](agent-onboarding.md) | v1.9.2 `llms.txt` / `.well-known/llms.txt`, PyPI `uvx` contract, agent anti-patterns. |
| [`agent/`](agent/) | **`SYSTEM_PROMPT.md` fragments** — `_assembly_order.txt`, paradigm, soft-gate, MCP, formatting (`make build-system-prompt`). |
| [`logseq-paradigm.md`](logseq-paradigm.md) | Logseq OG blocks/properties SSOT for contributor and runtime docs. |
| [`agent-ax-robustness.md`](agent-ax-robustness.md) | v1.9.7+ lenient page resolution, safe `write_outline` fallback, `heading_level` coercion, chaos tests. |
| [`security-sandbox.md`](security-sandbox.md) | v1.9.9 path sandbox reads, bounded JSON checkpoints, CI `sandbox-read-check`; v1.10.0 flock + atomic JSON sidecars ([#35](https://github.com/MarcoPorcellato/matryca-plumber/issues/35)–[#37](https://github.com/MarcoPorcellato/matryca-plumber/issues/37), [#41](https://github.com/MarcoPorcellato/matryca-plumber/issues/41)); v1.10.3 flock sidecar `0o600`. |
| [`../integrations/hermes-agent.md`](../integrations/hermes-agent.md) | v1.9.6 Hermes Agent MCP: lazy AST handshake, `connect_timeout` vs tool `timeout`, verified config. |
| [`llm-os-instructions.md`](llm-os-instructions.md) | Two-tier LLM OS, Master Index Soft Gate, `bootstrap_status`, Safe-Sync, v2.0 SQLite migration trigger. |
| [`link-verification.md`](link-verification.md) | v1.9 zero-LLM URL/asset hygiene, `.matryca_link_registry.json`, `dead-link::` / `missing-asset::`; v1.10.0 atomic registry save (#41). |
| [`agent-dx.md`](agent-dx.md) | v1.9 CLI `--json`, `context load`, `read subtree`, Journey Log (single cumulative bullet per day). |
| [`dual-embedding.md`](dual-embedding.md) | Phase 3 dual vectors (content + applicability) and `search_graph` / `method=semantic`. |
| [`tana-import.md`](tana-import.md) | **`import_tana`** / **`matryca import tana`** — Tana workspace JSON → Logseq OG (`ijson` streaming, journal `config.edn`, depth-split, `tana-id` idempotency, dry-run default). |
| [`ingest.md`](ingest.md) | **`ingest_document`** MCP tool — atomic external Markdown → ingest page + `LOG` / `GLOSSARY` (OS temp parse, OCC writes). |
| [`identity-config.md`](identity-config.md) | In-graph **Telos** / **AI Constraints** and **`store_fact`**. |
| [`lint.md`](lint.md) | On-disk lint: block refs + wiki convention pack. |
| [`l1-l2-routing.md`](l1-l2-routing.md) | L1 memory vs L2 graph routing and MCP hints. |
| [`runtime-bootstrap.md`](runtime-bootstrap.md) | Startup directory/config provisioning (logs, L1, cache, wiki YAML); master catalog flock/merge persistence (v1.10.0). |
| [`llm-performance.md`](llm-performance.md) | v1.8 KV-cache layout, RAM caps, cooperative bootstrap I/O; v1.12 Tier-1 builders + L0 safety; journal Phase-2 semantic bypass. |
| [`../PROMPT_ARCHITECTURE.md`](../PROMPT_ARCHITECTURE.md) | **v1.12** — Clean Architecture map for prompts (plan v3), semver recommendation, mermaid/ASCII flows. |
| [`../roadmaps/ROADMAP_V2_PREPARATION.md`](../roadmaps/ROADMAP_V2_PREPARATION.md) | **v2 visitor SSOT** — five phases, Safe-Sync, contribute guide |
| [`../roadmaps/ROADMAP_V2_SHADOW_DB.md`](../roadmaps/ROADMAP_V2_SHADOW_DB.md) | v2.0 `shadow.sqlite` read cache (FTS5, CTEs, `src/shadow/schema.py`) |
| [`../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md`](../roadmaps/ROADMAP_V2_BIOLOGICAL_MEMORY.md) | Nacre-inspired decay/recall/procedure memory |
| [`biological-memory.md`](biological-memory.md) | Planned env vars, `search_graph(method=recall)`, Safe-Sync contract |
| [`../v1.8-SOFTWARE-EDGE-PLAN.md`](../v1.8-SOFTWARE-EDGE-PLAN.md) | CPU sandbox, frozen KV prefix, adaptive LLM, mmap reads. |
| [`../v1.8-OPTIMIZATION-PLAN.md`](../v1.8-OPTIMIZATION-PLAN.md) | v1.8 operator env vars, verification matrix, load testing. |

Implementation entry points: `src/main.py`, `src/utils/runtime_bootstrap.py`, `src/agent/mcp_server.py`, `src/agent/ingestion.py`, `src/agent/tana_import.py`, `src/config.py`, `src/graph/`, `src/rag/`.
