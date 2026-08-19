---
type: Document
---
# L1 / L2 routing (Matryca Plumber)

**Roadmap:** [`ROADMAP_LLM_WIKI.md`](../../ROADMAP_LLM_WIKI.md)  
**Bootstrap:** [`runtime-bootstrap.md`](runtime-bootstrap.md) (directory creation, `README.md` vs content files)

## Layers

- **L1** — `MATRYCA_L1_PATH`, `matryca-wiki.yml` `memory_path`, or `<graph-parent>/matryca-l1/*.md`. Loaded via `read_graph_data` / `target_type="memory"` (`read_l1_memory` internally). Default folder is a **sibling** of the vault (not under `pages/`) so deploy/session rules stay outside the wiki corpus (L2) and can be shared across vaults on the same machine; set `MATRYCA_L1_PATH` to `<vault>/matryca-l1` to keep L1 inside the graph root instead.
- **In-graph identity** — Telos and AI Constraints on `matryca/config` or `matryca-config` (`pages/matryca___config.md` or `pages/matryca-config.md`). Injected into daemon LLM system prompts and MCP tool output; updated with `store_fact`. See [`identity-config.md`](identity-config.md).
- **L2 ingest capture** — External Markdown appended via **`ingest_document`** to an ingest page (`Ingest/YYYY-MM-DD` or `MATRYCA_INGEST_PAGE`) with `LOG` / `GLOSSARY` ledgers. See [`ingest.md`](ingest.md).
- **L2** — Logseq graph on disk under `LOGSEQ_GRAPH_PATH` and headless writes.

## Files loaded into L1 context

- All `*.md` in the resolved L1 directory (non-recursive), sorted by name.
- **`README.md` is excluded** — it documents the folder for humans only.
- Starter **`session-rules.md`** is included when bootstrap creates it (replace with your real session rules).

## Hints in tool output

Successful reads may end with `<!-- matryca_routing: hint=L1_candidate|L2_default -->`.  
`mutate_graph` / `write_outline` and **`ingest_document`** return JSON with `routing_hint` (e.g. `L2_graph_append` for ingestion).

MCP responses (except `store_fact`) may also include `[MATRYCA IDENTITY — …]` blocks and `<!-- matryca_identity: present -->` when a config page is configured (`src/daemon/config_layer.py`).

See `SYSTEM_PROMPT.md`, `src/agent/routing_hint.py`, [`identity-config.md`](identity-config.md), and [`ingest.md`](ingest.md).
