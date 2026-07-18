# Serena MCP — tool reference (matryca-plumber)

MCP server: **`serena-matryca-plumber`**.  
Source of truth for schemas: call `GetMcpTools` with `server: user-serena-matryca-plumber`.

Official: https://oraios.github.io/serena/02-usage/040_workflow.html

---

## Retrieval

### `get_symbols_overview`

**First tool for an unfamiliar code file.**

| Param | Notes |
|-------|--------|
| `relative_path` | Required. Repo-relative path. |
| `depth` | `-1` = language default; `1` includes class methods (Java/Kotlin default). |
| `max_answer_chars` | Truncate huge files; avoid unless necessary. |

### `find_symbol`

| Param | Notes |
|-------|--------|
| `name_path_pattern` | Simple name, suffix `class/method`, or absolute `/class/method`. |
| `relative_path` | Optional file or directory scope. |
| `depth` | `1` → children (e.g. class methods). Ignored if `include_body=True`. |
| `include_body` | Full source — use only when editing. |
| `include_info` | Hover-like docstring/signature (slow on C++). |
| `substring_matching` | `Foo/get` matches `getValue`, `getData`. |
| `max_matches` | Use `1` when you want a single unambiguous hit. |

### `find_referencing_symbols`

| Param | Notes |
|-------|--------|
| `name_path` | Symbol to look up (not a pattern). |
| `relative_path` | File containing the symbol. |
| `include_kinds` / `exclude_kinds` | LSP symbol kind filters (integers). |

Returns referencing symbols + short snippet around each use.

### `find_declaration`

Resolve declaration from a **callsite regex** (one capture group).

| Param | Notes |
|-------|--------|
| `relative_path` | File with the callsite. |
| `regex` | e.g. `obj\.(process)\(` — prefer enough context to disambiguate. |
| `containing_symbol_name_path` | Limit search to a parent symbol body. |

### `find_implementations`

Like find_symbol but for implementers of an interface/abstract symbol.

### `search_for_pattern`

Regex across files when you **don't know the symbol name**.

| Param | Notes |
|-------|--------|
| `substring_pattern` | Python `re` syntax. |
| `relative_path` | File or subtree. |
| `paths_include_glob` / `paths_exclude_glob` | e.g. `src/**/*.py`. |
| `restrict_search_to_code_files` | Skip non-code files. |
| `context_lines_before` / `after` | Surrounding lines. |
| `multiline` | Default `true` (DOTALL + MULTILINE). |

Prefer symbolic tools once you know the symbol.

---

## Editing

### `replace_symbol_body`

| Param | Notes |
|-------|--------|
| `name_path` | Target symbol. |
| `relative_path` | File path. |
| `body` | Complete new symbol body (definition only). |

**Requires prior `find_symbol(..., include_body=True)`.**

### `insert_after_symbol` / `insert_before_symbol`

Add new code adjacent to a symbol. Do not use for assignments/constants — use insert_before at file's first symbol for imports.

### `rename_symbol`

| Param | Notes |
|-------|--------|
| `name_path` | Symbol to rename. |
| `relative_path` | Defining file. |
| `new_name` | Local rename (not path). |

Updates all references project-wide.

### `safe_delete_symbol`

Deletes symbol if zero references; otherwise returns reference list.

### `replace_content`

Single-file edit.

| Param | Notes |
|-------|--------|
| `mode` | `literal` or `regex` (MULTILINE + DOTALL). |
| `needle` / `repl` | Search / replacement. |
| `allow_multiple_occurrences` | Default `false` — fails if ambiguous. |

**Regex tip:** `def foo.*?return x` avoids pasting huge old bodies; ambiguous match ⇒ error, refine wildcard.

### `replace_in_files`

Bulk edit — **preferred for repeated small changes across files**.

| Param | Notes |
|-------|--------|
| `dry_run` | `true` → list diffs + `occurrence_ids`, no writes. |
| `occurrence_ids` | Apply subset from dry run. |
| `expected_count` | Guard: abort if match count differs. |
| `relative_path` | Scope file/dir. |
| `paths_include_glob` / `paths_exclude_glob` | Further filter. |

---

## Diagnostics & meta

### `get_diagnostics_for_file`

LSP errors/warnings/hints grouped by symbol. `min_severity`: 1=Error … 4=Hint.  
`start_line` / `end_line` are **0-based**.

### `initial_instructions`

No args. Returns Serena Instructions Manual — **call at task start**.

### `onboarding`

One-time project familiarization; writes memories. Skip if `list_memories` is non-empty.

### `open_dashboard`

Opens Serena web dashboard (memories, language servers).

---

## Memories

| Tool | Purpose |
|------|---------|
| `list_memories` | Optional `topic` filter (`conventions`, `global/…`). |
| `read_memory` | Load `memory_name`. |
| `write_memory` | Create/update markdown memory. |
| `edit_memory` | Regex replace inside memory. |
| `rename_memory` | Rename; rewrites `` `mem:old` `` refs. |
| `delete_memory` | Only when user approves. |

Reference other memories as `` `mem:name` `` in content.

**matryca-plumber seeds:** `conventions`, `core`, `tech_stack`, `suggested_commands`, `task_completion`, `graph_write_safety`, `memory_maintenance`.

---

## Contexts & modes (server startup)

Set in MCP launch args (not per call):

| Context | Use |
|---------|-----|
| `ide` / `ide-assistant` | Cursor, VS Code, Cline — augment IDE tools |
| `agent` | Standalone agent, full toolset |
| `claude-code` | Disables tools Claude Code already has |

| Mode | Effect |
|------|--------|
| `no-onboarding` | Skip first-run onboarding |
| `no-memories` | Disable memory tools |
| `query-projects` | Enable cross-project read |

This repo (`.codex/config.toml`): `--context ide-assistant --project <matryca-plumber>`.

---

## Error handling

- **Too many matches** from `find_symbol` → narrow `relative_path`, use absolute `/path`, or `max_matches=1`.
- **Ambiguous regex** from `replace_content` → tighten wildcards or use symbol tools.
- **`safe_delete_symbol` returns references** → remove or repoint callers first.
- **Timeouts on `get_diagnostics_for_file`** — retry once; fall back to `make typecheck`.

---

## Comparison: Serena vs Cursor native tools

| Need | Serena | Cursor Read/Grep |
|------|--------|------------------|
| Symbol body for edit | `find_symbol` + `replace_symbol_body` | Read full file + StrReplace |
| Who calls `foo`? | `find_referencing_symbols` | Grep (no type awareness) |
| Rename across repo | `rename_symbol` | Error-prone replace_all |
| Find string in logs | — | Grep |
| Read CHANGELOG | — | Read |

Use both: Serena for **Python `src/` and `tests/`** structure; Grep for text and non-code.
