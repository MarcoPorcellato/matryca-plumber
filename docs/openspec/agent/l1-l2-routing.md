---
type: Document
---
## L1 vs L2 vs in-graph identity

- **L1 (session-critical):** deploy rules, pointers to secrets (never secrets themselves). Load first via `read_graph_data` / `target_type="memory"`. Sources: `MATRYCA_L1_PATH`, `memory_path` in `matryca-wiki.yml`, or `<parent-of-vault>/matryca-l1/*.md` (sibling of the graph root by default — see `docs/openspec/runtime-bootstrap.md`). `README.md` in that folder is documentation only and is not loaded into context.
- **In-graph identity (Telos / AI Constraints):** role and durable agent rules on `matryca/config` or `matryca-config` — injected automatically into daemon LLM and MCP output; extend with `store_fact` (see [`docs/openspec/identity-config.md`](docs/openspec/identity-config.md)).
- **L2 (durable wiki):** all other graph content under `LOGSEQ_GRAPH_PATH`. Ground truth via `read_graph_data` / `target_type="page"`; writes via `mutate_graph`.

**Rule:** If ignorance before acting risks data loss, security, production failure, or brand harm → L1. Role/formatting that should follow the vault → Telos/Constraints page or `store_fact`. If fixable with a follow-up → L2 on demand.

**Routing hints:** `read_graph_data` (page) and `mutate_graph` (write_outline) responses may end with `<!-- matryca_routing: ... -->`. `L1_candidate` → consider promoting to L1; `L2_*` → normal graph storage.
