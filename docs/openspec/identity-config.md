# In-graph identity (Telos & AI Constraints)

**Roadmap:** Master architecture RFC — Phase 1 (persona layer)  
**Implementation:** `src/daemon/config_layer.py`, `src/agent/memory_tools.py`  
**Agent contract:** [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) (Identity + `store_fact`)  
**Related:** [`l1-l2-routing.md`](l1-l2-routing.md), [`runtime-bootstrap.md`](runtime-bootstrap.md), [`ingest.md`](ingest.md) (external Markdown capture)

Matryca Plumber can load **operator role and durable rules** from a Logseq page inside the vault (L2), inject them into **daemon LLM system prompts** and **MCP tool output**, and append new preferences via the **`store_fact`** MCP tool.

This is complementary to **L1** (`matryca-l1/*.md`): L1 holds session/deploy notes outside the wiki index; the identity page holds **graph-native persona** that travels with the vault and refreshes when you edit it in Logseq.

---

## Config page format

Create one of these pages (bulleted Logseq headings, not bare ATX in the body):

| Semantic title | On-disk file (typical) |
|----------------|----------------------|
| `matryca/config` | `pages/matryca___config.md` |
| `matryca-config` (fallback) | `pages/matryca-config.md` |

Required top-level sections (bullets):

```markdown
- # Telos
  - Your role or mission (e.g. researcher, lawyer, SRE)
- # AI Constraints
  - Formatting and behavior rules the daemon and MCP agents must follow
  - Additional bullets are children of this heading
```

**Parsing rules** (`logseq_matryca_parser`):

- Headings are bullets whose text is `# Telos` or `# AI Constraints` (parser sets `heading_level` on the node).
- **Telos** and **Constraints** body text is the concatenation of **child bullet** text (recursive), not the heading line itself.
- `id::` lines are ignored during text extraction.
- Per-section cap: **8 KiB**; combined cap: **16 KiB** (aligned with L1 memory guardrails).

---

## Read vs write resolution

| Operation | Page chosen |
|-----------|-------------|
| **Read** (injection, `IdentityConfigStore`) | 1. `MATRYCA_IDENTITY_CONFIG_PAGE` if set and resolvable · 2. `matryca/config` · 3. `matryca-config` |
| **Write** (`store_fact` only) | Always **`matryca-config`** → `pages/matryca-config.md` (created with skeleton headings when missing) |

Rationale: namespaced `matryca/config` is the preferred read source for operators who already use Logseq namespaces; **`store_fact`** uses a single stable write target so MCP-learned preferences accumulate in one file.

**Not indexed:** `matryca-config.md` at the **vault root** (outside `pages/`) is invisible to `LogseqGraph.load_directory`. Use `pages/matryca-config.md` only.

---

## Runtime behavior

### In-memory store

`IdentityConfigStore` (singleton per `LOGSEQ_GRAPH_PATH`):

- Loads via `get_graph_ast_cache(graph_root).get_graph()` and `graph.pages[title]`.
- Invalidates when the resolved config file **`st_mtime_ns`** changes (`reload_if_stale`, optional `force=True`).

### Refresh triggers

| Trigger | Location |
|---------|----------|
| Startup | `prepare_matryca_runtime()` → `get_identity_store(...).reload_if_stale(force=True)` |
| Human edits in Logseq | `GraphFileWatcher` → `maintenance_daemon._on_watchdog_change` → `refresh_identity_config` |
| Plumber atomic writes | `emit_post_write_commit` → registered post-write hook → `refresh_identity_config` |
| MCP / CLI without watcher | `reload_if_stale()` on every `get()` / injection (`st_mtime_ns` check) |

### LLM injection

`inject_identity_into_system_prompt()` appends a block when non-empty:

```text
[MATRYCA IDENTITY — Telos]
…

[MATRYCA IDENTITY — AI Constraints]
…
```

Applied at **`InstructorLLMClient._completion_messages`** and the context-compression system path (`src/agent/llm_client.py`). Skips re-append if `[MATRYCA IDENTITY —` is already present.

### MCP injection

`append_identity_to_mcp_payload()` adds the same block (plus `<!-- matryca_identity: present -->`) to successful **string** or **dict** tool responses.

**Exception:** `store_fact` responses are **not** wrapped (avoids redundant noise right after a write).

---

## `store_fact` MCP tool

**Signature:** `store_fact(fact: str) -> dict`

**Description for hosts:** *Use this tool to permanently remember a user preference, rule, or fact across sessions.*

**Flow:**

1. Resolve `LOGSEQ_GRAPH_PATH`; ensure `pages/matryca-config.md` exists (seed skeleton if empty).
2. Parse graph; locate **AI Constraints** heading node.
3. Append `fact` as a child bullet via `_headless_append_child` (OCC + `page_rmw_lock`).
4. `atomic_write_bytes` / `atomic_write_bytes_if_unchanged` → **`emit_post_write_commit`** → AST cache delta + optional **robot git commit** (`MATRYCA_GIT_ROBOT_COMMIT`).
5. Refresh identity store.

Optional property on stored bullets: `stored:: matryca-plumber`.

---

## Environment

| Variable | Role |
|----------|------|
| `MATRYCA_IDENTITY_CONFIG_PAGE` | Override Logseq page title for **read** path only (optional). Documented in `.env.example`. |
| `LOGSEQ_GRAPH_PATH` | Required for identity load and `store_fact`. |
| `MATRYCA_WATCH_DEBOUNCE_MS` | Debounce before watchdog refresh of AST + identity (default 750 ms). |
| `MATRYCA_GIT_ROBOT_COMMIT` | Post-write surgical commits after `store_fact` (default on in git repos). |

---

## Module map

| Module | Responsibility |
|--------|----------------|
| `src/daemon/config_layer.py` | Parse, store, inject, path helpers |
| `src/daemon/ast_cache.py` | `LogseqGraph` RAM index |
| `src/daemon/file_watcher.py` | Debounced `pages/` / `journals/` observer |
| `src/daemon/post_write_hooks.py` | `emit_post_write_commit` fan-out |
| `src/agent/memory_tools.py` | `dispatch_store_fact` |
| `src/agent/mcp_server.py` | Registers `store_fact` |
| `src/agent/mcp_tool_guard.py` | MCP footer injection |

**Tests:** `tests/test_identity_config.py`
