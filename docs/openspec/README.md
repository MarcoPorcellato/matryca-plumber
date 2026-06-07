# Openspec-style notes (Matryca Plumber)

**Matryca Plumber** — developed by Marco Porcellato · [Matryca.ai](https://matryca.ai). Naming rules: [`../BRANDING.md`](../BRANDING.md).

Trimmed behavioral specs aligned with [MehmetGoekce/llm-wiki](https://github.com/MehmetGoekce/llm-wiki) openspec, mapped to this repository.

**Canonical checklists:** [`roadmaps/ROADMAP_LLM_WIKI.md`](../roadmaps/ROADMAP_LLM_WIKI.md), [`roadmaps/ROADMAP_LLM_WIKI_PHASE_3.md`](../roadmaps/ROADMAP_LLM_WIKI_PHASE_3.md).

| Document | Scope |
|----------|--------|
| [`live-telemetry-ui.md`](live-telemetry-ui.md) | v1.9.3 Sovereign UI: 5s polling, daemon heartbeat, API token overlay, `daemon_pid` auto-unfreeze. |
| [`agent-onboarding.md`](agent-onboarding.md) | v1.9.2 `llms.txt` / `.well-known/llms.txt`, PyPI `uvx` contract, agent anti-patterns. |
| [`../integrations/hermes-agent.md`](../integrations/hermes-agent.md) | v1.9.6 Hermes Agent MCP: lazy AST handshake, `connect_timeout` vs tool `timeout`, verified config. |
| [`llm-os-instructions.md`](llm-os-instructions.md) | Two-tier LLM OS, Master Index Soft Gate, `bootstrap_status`, Safe-Sync, v2.0 SQLite migration trigger. |
| [`link-verification.md`](link-verification.md) | v1.9 zero-LLM URL/asset hygiene, `.matryca_link_registry.json`, `dead-link::` / `missing-asset::`. |
| [`agent-dx.md`](agent-dx.md) | v1.9 CLI `--json`, `context load`, `read subtree`, Journey Log (single cumulative bullet per day). |
| [`dual-embedding.md`](dual-embedding.md) | Phase 3 dual vectors (content + applicability) and `search_graph` / `method=semantic`. |
| [`ingest.md`](ingest.md) | **`ingest_document`** MCP tool — atomic external Markdown → ingest page + `LOG` / `GLOSSARY` (OS temp parse, OCC writes). |
| [`identity-config.md`](identity-config.md) | In-graph **Telos** / **AI Constraints** and **`store_fact`**. |
| [`lint.md`](lint.md) | On-disk lint: block refs + wiki convention pack. |
| [`l1-l2-routing.md`](l1-l2-routing.md) | L1 memory vs L2 graph routing and MCP hints. |
| [`runtime-bootstrap.md`](runtime-bootstrap.md) | Startup directory/config provisioning (logs, L1, cache, wiki YAML). |
| [`llm-performance.md`](llm-performance.md) | v1.8 KV-cache layout, RAM caps, cooperative bootstrap I/O. |
| [`../v1.8-SOFTWARE-EDGE-PLAN.md`](../v1.8-SOFTWARE-EDGE-PLAN.md) | CPU sandbox, frozen KV prefix, adaptive LLM, mmap reads. |
| [`../v1.8-OPTIMIZATION-PLAN.md`](../v1.8-OPTIMIZATION-PLAN.md) | v1.8 operator env vars, verification matrix, load testing. |

Implementation entry points: `src/main.py`, `src/utils/runtime_bootstrap.py`, `src/agent/mcp_server.py`, `src/agent/ingestion.py`, `src/config.py`, `src/graph/`, `src/rag/`.
