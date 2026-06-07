# Hermes Agent integration — compatibility report

**Date:** 2026-06-07  
**Status:** Verified working (stdio MCP, 7 tools)  
**Test environment:** OrbStack Linux (`hermes-sandbox`), Hermes Agent v0.16.0, matryca-plumber local venv  
**Vault:** `/mnt/mac/Users/marco1/logseq_test` (~1 106 Markdown files)

This document records a real integration session between **Hermes Agent** and **Matryca Plumber** MCP, root causes of initial failure, the working configuration, and recommended repo/doc changes so future operators do not hit the same pitfalls.

---

## Executive summary

| Layer | Issue | Fix |
|-------|--------|-----|
| **Hermes host** | Python `mcp` SDK not installed (`hermes-agent[mcp]` extra missing) | `uv pip install -e ".[mcp]"` in `~/.hermes/hermes-agent` |
| **Hermes config** | `connect_timeout: 60` too low before lazy bootstrap (legacy) | **60–120 s** suffices for handshake after v1.9.x lazy AST |
| **Hermes config** | Invalid `cwd`, wrong `MATRYCA_L1_PATH` / `MATRYCA_WIKI_CONFIG` overrides | Remove overrides; rely on runtime bootstrap |
| **Matryca Plumber** | Eager AST bootstrap blocked MCP `initialize` on large vaults | **Fixed:** MCP lifespan uses `eager_graph=False`; AST loads on first graph tool call |
| **Operations** | Orphan `uvx matryca-plumber` processes after failed connects | Kill zombies before retry; prefer pinned local binary over `uvx` in dev |

After host-side fixes, Hermes discovered **7 MCP tools**. With **lazy AST bootstrap** (Plumber ≥ current), `tools/list` completes in **&lt; 30 s**; the first graph-mutating tool call pays the vault parse cost (see `mcp-stderr.log` telemetry).

---

## Verified Hermes configuration

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  matryca-plumber:
    # Production / zero-install:
    # command: uvx
    # args: [matryca-plumber]

    # Dev (faster cold start, pinned version):
    command: /path/to/matryca-plumber/.venv/bin/matryca-plumber
    args: []

    env:
      MATRYCA_MCP_ENABLED: "true"
      LOGSEQ_GRAPH_PATH: /absolute/path/to/logseq/vault   # must contain pages/

    enabled: true
    timeout: 300          # per tool call
    connect_timeout: 120  # handshake; first graph tool may take longer on large vaults
```

### Hermes prerequisites

From [Hermes MCP docs](https://hermes-agent.dev/docs/user-guide/features/mcp):

```bash
cd ~/.hermes/hermes-agent
uv pip install -e ".[mcp]"
```

Restart Hermes or run `/reload-mcp` after config changes.

### OrbStack / Mac filesystem

When the vault lives on the Mac host, mount it in the Hermes container (see `~/.hermes/docker-compose.matryca-plumber.yml` pattern) and use **`/mnt/mac/Users/...`** paths in `LOGSEQ_GRAPH_PATH`, not macOS-only paths invisible from Linux.

---

## What was broken (chronological)

### 1. Missing Hermes MCP client (`failed` in banner)

Hermes banner showed `matryca-plumber (stdio) — failed` because `_MCP_AVAILABLE` was `False` in the Hermes venv:

```
ImportError: MCP server 'matryca-plumber' requires the 'mcp' Python SDK
```

This is **not** a Matryca Plumber bug. The host must install `hermes-agent[mcp]` even when the MCP server subprocess is launched via `uvx`.

### 2. `connect_timeout` vs startup latency (historical + current)

**Before lazy bootstrap:** Matryca Plumber ran **synchronous full-vault AST bootstrap** inside MCP lifespan before yielding to FastMCP. On large vaults (~1 106 files), Hermes `connect_timeout: 60` caused handshake failures.

**Current behavior (lazy AST):** MCP lifespan calls `prepare_matryca_runtime(..., eager_graph=False)` — only light provisioning (L1, wiki YAML, cache dirs). The AST loads on the **first tool call** that needs the graph via `get_graph_ast_cache().get_graph()`. Hermes `initialize` + `tools/list` complete in seconds (`tests/test_hermes_mcp_handshake.py` asserts &lt; 30 s).

Structured stderr telemetry when the graph loads:

```
AST cache bootstrap started    phase=start markdown_files=…
AST cache bootstrap complete   phase=complete duration_s=… pages_indexed=…
```

Check `~/.hermes/logs/mcp-stderr.log` if the **first graph tool** is slow, not the handshake.

### 3. Misconfigured path overrides

Previous config set `MATRYCA_L1_PATH` and `MATRYCA_WIKI_CONFIG` under `Documents/.../LOGSEQ copy test LLM/` — a directory that was **empty** and **outside** the graph-root allowlist relative to `LOGSEQ_GRAPH_PATH`. Plumber logged:

```
MATRYCA_WIKI_CONFIG path is outside allowed roots; ignoring explicit override
```

**Recommendation:** omit these env vars unless paths are under the vault or `$HOME` per `src/utils/config_paths.py`. Runtime bootstrap creates:

- `<vault>/matryca-wiki.yml`
- `<vault>/matryca-l1/` (or sibling — see `docs/openspec/runtime-bootstrap.md`)

### 4. Orphan subprocesses

Each failed Hermes connect left `uvx matryca-plumber` children running (15 observed), each repeating full bootstrap and competing for I/O. Clear orphans before debugging:

```bash
pkill -f "uv tool uvx matryca-plumber"
pkill -f "/matryca-plumber$"
```

---

## Verified tool surface (7 tools)

After successful connect, Hermes registered:

| Tool | Purpose |
|------|---------|
| `read_graph_data` | Pages, subtrees, L1, structural hops, dashboards |
| `search_graph` | bm25 / semantic / regex search |
| `mutate_graph` | OCC-safe graph writes |
| `refactor_blocks` | Block-level refactors |
| `run_linter` | Cognitive lint modules |
| `store_fact` | Append durable constraints / identity facts |
| `ingest_document` | Atomic external Markdown ingestion |

Implementation: `src/agent/mcp_server.py` (`register_mcp_tools`).

---

## Hermes ↔ Plumber contract checklist

| Requirement | Hermes | Matryca Plumber | Notes |
|-------------|--------|-----------------|-------|
| MCP transport | stdio via `mcp` Python SDK | FastMCP `run_stdio_async()` | JSON-RPC on stdin/stdout |
| Enable gate | `MATRYCA_MCP_ENABLED=true` in `env` | `plumber_entry.py` exits with code 2 if unset | Default off (`SECURITY.md`) |
| Graph path | `LOGSEQ_GRAPH_PATH` in `env` | Required; `os.chdir(graph_root)` in lifespan | Vault root with `pages/` |
| CLI disambiguation | bare `matryca-plumber` argv | Routes to MCP when no CLI subcommand | Do not pass `plumber`/`status` args |
| stderr | Hermes redirects to `~/.hermes/logs/mcp-stderr.log` | Loguru + parser warnings OK | **Never write banners to stdout** |
| Loguru on stdio | N/A | `install_loguru_mcp_bridge()` | Prevents corrupting JSON-RPC |
| Handshake time | `connect_timeout` ≥ 60 s (120 s recommended) | Lazy AST — no `load_directory` at lifespan | Seconds |
| First graph tool | `timeout` per tool (default 300 s) | `load_directory` on first `get_graph()` | Vault-size dependent |

---

## Recommendations for matryca-plumber repo

### Documentation (high priority)

1. **Add this file** to README Documentation Map and `docs/openspec/README.md`.
2. **`.env.example`** — add commented Hermes block:
   ```env
   # Hermes Agent (~/.hermes/config.yaml mcp_servers.matryca-plumber.env)
   # MATRYCA_MCP_ENABLED=true
   # LOGSEQ_GRAPH_PATH=/absolute/path/to/vault
   ```
3. **`CONTRIBUTING.md`** — link Hermes as a second MCP host beside Claude Desktop/Cursor.
4. **`SECURITY.md`** — mention Hermes explicitly in MCP trust-boundary section.

### Configuration guidance for operators

**Do not confuse handshake timeout with tool timeout.**

| Setting | What it covers | Recommended |
|---------|----------------|-------------|
| **`connect_timeout`** | Hermes **handshake** only: subprocess spawn, MCP `initialize`, `tools/list` | **60–120 s** (lazy AST — vault size does not affect handshake) |
| **`timeout`** | Each **tool call** after connect | **300 s** default; raise for large vaults on the **first** graph tool (cold AST parse) |

| Scenario | `command` | `connect_timeout` | `timeout` (first graph tool) |
|----------|-----------|---------------------|------------------------------|
| End users / PyPI | `uvx` + `args: [matryca-plumber]` | 120 s | 300 s+; scale with vault |
| Developers | `.venv/bin/matryca-plumber` | 120 s | same |
| Small test vault (<100 pages) | either | 60 s | 120 s often enough |

**Tool-timeout rule of thumb (not `connect_timeout`):** on OrbStack/Mac mounts, budget **`timeout` ≥ (pages + journals) × ~0.2 s** for the first graph-mutating or graph-reading tool after connect. Measure once per vault; subsequent calls reuse the in-memory AST cache.

**No AST required for:** `read_graph_data` / `bootstrap_status`, `read_graph_data` / `memory` — safe to call immediately after handshake.

### Code / architecture (implemented)

1. **Lazy AST bootstrap** — `prepare_matryca_runtime(..., eager_graph=False)` in MCP lifespan; `GraphAstCache.bootstrap()` on first `get_graph()` (thread-safe `RLock`).
2. **Startup telemetry on stderr** — `AST cache bootstrap started|complete` with `markdown_files`, `duration_s`, `pages_indexed`.
3. **Integration test** — `tests/test_hermes_mcp_handshake.py` asserts `tools/list` within 30 s on a tiny fixture graph.

### Anti-patterns to document

- Do **not** set `MATRYCA_L1_PATH` / `MATRYCA_WIKI_CONFIG` to paths outside allowlist.
- Do **not** use `cwd: /opt/data` (or any missing directory) — Hermes MCP reference does not define `cwd` for stdio; it may be ignored.
- Do **not** rely on Hermes standard install including `[mcp]` unless `uv pip install -e ".[all]"` was used.

---

## Test procedure (repeatable)

```bash
# 1. Hermes MCP client
cd ~/.hermes/hermes-agent && uv pip install -e ".[mcp]"

# 2. Kill orphans
pkill -f "matryca-plumber" || true

# 3. Probe (from hermes-agent repo, adjust paths)
.venv/bin/python - <<'PY'
import asyncio, sys, time
sys.path.insert(0, ".")
from tools.mcp_tool import _connect_server, _load_mcp_config, _ensure_mcp_loop, _run_on_mcp_loop, _stop_mcp_loop
cfg = _load_mcp_config()["matryca-plumber"]
async def t():
    t0 = time.time()
    s = await asyncio.wait_for(_connect_server("matryca-plumber", cfg), timeout=cfg["connect_timeout"])
    print(f"OK in {time.time()-t0:.1f}s:", [x.name for x in s._tools])
    await s.shutdown()
_ensure_mcp_loop()
_run_on_mcp_loop(t(), timeout=400)
_stop_mcp_loop()
PY

# 4. Hermes UI — banner should show:
#    matryca-plumber (stdio) — 7 tool(s)
```

---

## Related documents

| Document | Relevance |
|----------|-----------|
| [`docs/openspec/agent-dx.md`](../openspec/agent-dx.md) | Lists Hermes as external agent surface |
| [`docs/openspec/runtime-bootstrap.md`](../openspec/runtime-bootstrap.md) | What runs at MCP lifespan start |
| [`SECURITY.md`](../../SECURITY.md) | `MATRYCA_MCP_ENABLED` gate |
| [`src/plumber_entry.py`](../../src/plumber_entry.py) | CLI vs MCP stdio routing |
| [Hermes MCP guide](https://hermes-agent.dev/docs/guides/use-mcp-with-hermes) | Host-side setup |
| [Hermes MCP config reference](https://hermes-agent.dev/docs/reference/mcp-config-reference) | `connect_timeout`, `env`, `command` |

---

## Changelog entry (suggested)

```markdown
### Integrations
- Document Hermes Agent MCP integration (`docs/integrations/hermes-agent.md`):
  verified 7-tool stdio handshake; require `connect_timeout` ≥ vault bootstrap time
  and `hermes-agent[mcp]` on the host.
```
