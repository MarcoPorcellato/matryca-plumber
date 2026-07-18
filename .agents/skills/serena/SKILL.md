---
name: serena
description: >-
  Use Serena MCP for semantic code navigation and symbol-level edits in
  matryca-plumber. Prefer over blind grep/read when exploring or changing Python
  symbols. MCP server: serena-matryca-plumber (not global serena).
---

# Serena MCP — matryca-plumber

Serena is an **MCP server** that exposes IDE-like **symbol retrieval and editing** via Language Server Protocol (LSP). It operates at the **symbol level** (classes, functions, methods), not line numbers.

**Official docs:** https://oraios.github.io/serena/  
**Upstream:** https://github.com/oraios/serena

## This repo — critical routing

| Item | Value |
|------|--------|
| **MCP server** | `serena-matryca-plumber` |
| **Do not use** | `user-serena` (bound to Matryca-per-Delineat) |
| **Project root** | matryca-plumber checkout (passed at MCP startup) |
| **Context** | `ide-assistant` (see `.codex/config.toml`) |

One Serena instance = one project. Two repos ⇒ two MCP server entries.

## First action on coding tasks

1. Call **`initial_instructions`** on `serena-matryca-plumber` (Serena Instructions Manual).
2. If memories exist, **`list_memories`** then **`read_memory`** for relevant entries (`mem:conventions`, `mem:task_completion`, `mem:suggested_commands`).
3. Skip **`onboarding`** unless the project has no memories yet.

## When to use Serena (prefer over grep/read)

| Task | Serena tool | Why |
|------|-------------|-----|
| New file / unknown area | `get_symbols_overview` | Compact symbol map without reading whole file |
| Find definition | `find_symbol` | LSP-accurate; supports `depth`, `substring_matching` |
| Blast radius before edit | `find_referencing_symbols` | All references with snippets |
| Rename / delete symbol | `rename_symbol` / `safe_delete_symbol` | Reference-aware, atomic |
| Replace whole function/class | `replace_symbol_body` | After `include_body=True` retrieval |
| Small in-method patch | `replace_content` (regex) | Cheaper than full symbol replace |
| Same edit in N files | `replace_in_files` + `dry_run=True` first | One call, occurrence IDs |
| Unknown symbol location | `search_for_pattern` | Regex; then switch to symbolic tools |
| Post-edit sanity | `get_diagnostics_for_file` | LSP errors on touched files |

## When NOT to use Serena

- **Markdown, YAML, TOML, lockfiles** — use Read/Grep.
- **Whole-file config or docs** — Read is fine.
- **Shell / git / CI** — terminal (`make ci`, `uv run pytest …`).
- **After `replace_symbol_body` / `rename_symbol` succeeds** — do not re-read the file to “confirm”; trust the tool.
- **After `safe_delete_symbol` succeeds** — same.

## Agent-drift guard (official recommendation)

If you make **many consecutive `grep` / `read_file` calls without any Serena tool**, switch to Serena for the next exploration step. Cursor does not ship `serena-hooks remind`; self-enforce the same rule.

## Standard workflow

```
get_symbols_overview(file)     # orient
    ↓
find_symbol(pattern, depth=0|1)  # locate; include_body only when editing
    ↓
find_referencing_symbols       # before non-trivial changes
    ↓
edit (symbol or regex tool)
    ↓
get_diagnostics_for_file       # optional, touched files only
    ↓
make check / make ci             # mem:task_completion
```

### Parallelism (token/cost)

Serena runs tool calls **sequentially** internally, but you should still **batch independent Serena reads** in one turn (overview + find_symbol on different files). Do **not** re-analyze a file with symbolic tools after you already read it fully.

## Name paths (Python)

Within a file, symbols use `/` paths:

| Pattern | Matches |
|---------|---------|
| `prepare_fts_user_query` | Any symbol named that |
| `ShadowGraphRepository/read_subtree_markdown` | Method on class |
| `/MyClass/my_method` | Exact full path in file |
| `Foo/get` + `substring_matching=True` | `getValue`, `getData`, … |
| `MyClass/my_method[1]` | Overloaded index (rare in Python) |

**Line numbers in Serena output are 0-based** (convert mentally to editor 1-based).

## Editing rules

### Symbol-level (preferred for whole definitions)

1. **`find_symbol` with `include_body=True`** on the target first.
2. **`replace_symbol_body`** — pass full new body (signature + implementation per language).
3. **`insert_after_symbol` / `insert_before_symbol`** — new top-level or member definitions.
4. **`rename_symbol`** — never find-and-replace rename across the repo.

### File-level (small patches inside a symbol)

- **`replace_content`** — `mode: regex` with wildcards (`beginning.*?end`) for multi-line spans; ambiguous match ⇒ refine pattern (safe by design).
- **`replace_in_files`** — bulk literal/regex; **always `dry_run=True` first** when risk of collateral edits; then apply by `occurrence_ids`.

### Do not

- `replace_symbol_body` without prior `include_body=True` retrieval.
- Global quote-and-replace renames (use `rename_symbol`).
- Re-run tests only to verify a successful `rename_symbol`.

## Memories (project-specific)

Stored under `.serena/memories/` (if present). Reference as `` `mem:name` ``.

| Memory | Use when |
|--------|----------|
| `mem:conventions` | Style, layers, naming |
| `mem:task_completion` | Definition of done (`make ci`) |
| `mem:suggested_commands` | Makefile / uv commands |
| `mem:core` | Project map entry point |
| `mem:graph_write_safety` | Vault write / sandbox rules |

CLI integrity (human): `serena memories check` from project root.

## matryca-plumber completion gate

After code changes:

```bash
make lint && make typecheck && make test
# or full gate:
make ci
```

See `mem:task_completion`. Complement with GitNexus `impact` / `detect_changes` when changing `src/` symbols (repo policy).

## Tool quick reference

Full parameter detail: [reference.md](reference.md).

| Tool | Purpose |
|------|---------|
| `initial_instructions` | Manual — call once per task |
| `get_symbols_overview` | File symbol index |
| `find_symbol` | Resolve symbols by name path |
| `find_referencing_symbols` | Incoming references |
| `find_declaration` | Jump to declaration via callsite regex |
| `find_implementations` | Implementations of interface/abstract |
| `search_for_pattern` | Regex grep with context |
| `replace_symbol_body` | Replace symbol definition |
| `insert_after_symbol` / `insert_before_symbol` | Add code near symbol |
| `rename_symbol` | Project-wide rename |
| `safe_delete_symbol` | Delete if unreferenced |
| `replace_content` | Single-file regex/literal edit |
| `replace_in_files` | Multi-file regex/literal edit |
| `get_diagnostics_for_file` | LSP diagnostics |
| `list_memories` / `read_memory` / `write_memory` | Project knowledge |
| `open_dashboard` | Web UI for memories (optional) |

## Official concepts (short)

- **Project** — directory Serena indexes (this repo).
- **Context** — `ide` / `ide-assistant` / `agent` / `claude-code`; set at server start, not per message.
- **Modes** — composable flags (`no-onboarding`, `no-memories`, `query-projects`, …).
- **Indexing** — `serena project index` once; LSP updates incrementally. JetBrains plugin uses IDE index instead.

## Related skills

- **GitNexus** — execution-flow / call-graph impact before `src/` edits.
- **`.agents/skills/serena/`** — same content for agent routers that load from `.agents/`.
