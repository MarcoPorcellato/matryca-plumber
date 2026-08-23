---
type: Document
---
# Agent Experience (AX) robustness — lenient resolution & safe writes (v1.9.7+)

**Milestone:** v1.9.7 — AX Robustness & Lenient Resolution · v1.9.8 — documentation harmonization · v1.9.9 — Security & Sandbox (complements MCP title normalization; see [`security-sandbox.md`](security-sandbox.md))  
**Modules:** [`src/agent/page_input_normalizer.py`](../../src/agent/page_input_normalizer.py), [`src/agent/graph_dispatch.py`](../../src/agent/graph_dispatch.py) (`_resolve_write_parent_target`, `_headless_write_outline_empty_page`), [`src/agent/outline_models.py`](../../src/agent/outline_models.py) (`heading_level` coercion)  
**Tests:** [`tests/test_agent_experience_robustness.py`](../../tests/test_agent_experience_robustness.py)

Local LLM agents (Qwen, Hermes, small instruct models) often hallucinate page titles, namespace separators, or block UUIDs. Matryca Plumber hardens the **MCP / CLI dispatch layer** without modifying the upstream `logseq-matryca-parser` package.

---

## Architectural boundary

| Layer | Responsibility |
|-------|----------------|
| **`matryca-plumber`** (`page_path.py`, `page_input_normalizer.py`, `graph_dispatch.py`) | Page title ↔ filename mapping, lenient input normalization, safe write fallbacks |
| **`logseq-matryca-parser`** | AST parse, `LogseqGraph` registry, atomic block splice after a disk path is resolved |

All normalization runs **before** parser calls. The parser never sees raw agent page strings.

---

## Lenient page resolution

`normalize_page_ref(graph_root, raw)` → `NormalizedPageRef | None`

| Agent input mistake | Plumber behavior |
|---------------------|------------------|
| `progetti___Lancio` vs `progetti/Lancio` | Bidirectional `/` ↔ `___` |
| `pages/Foo.md`, trailing `.md`, inline `.md` segments | Stripped / normalized |
| `progetti///Lancio` | Repeated `/` collapsed |
| `PROGETTI/foo` | Case-insensitive match to on-disk canonical title |
| `../../etc/passwd`, `foo/../../bar` | **Rejected** — `ValueError` with clear message (no crash) |
| Blank / whitespace-only | `None` (page not found) |

**Entrypoints wired:**

- `read_graph_data` — `target_type=page`, `xray_page`
- `read_block_ast_markdown`, `read_subtree_markdown`, `read_xray_page_markdown`
- `mutate_graph` — `edit_property` (`Page Title|block`)
- `refactor_blocks` — page titles in `target_uuid`

**Agent feedback:** resolution notes append to Markdown read responses (`**Page resolution notes:**` footer) or `warnings: string[]` on JSON mutate/refactor responses. Same notes are logged to stderr via Loguru.

---

## Safe fallback append (`write_outline`)

`mutate_graph` / `action=write_outline` accepts:

| `target` form | Semantics |
|---------------|-----------|
| `parent-block-uuid` | Direct parent (or X-Ray `[n]` after `xray_page`) |
| `Page Title\|block-uuid` | Page context + block reference (recommended for local LLMs) |
| `Page Title\|[n]` | Pipe + session alias |

When the **page exists** but the block UUID or `[n]` alias is invalid:

1. Plumber logs a stderr warning.
2. Appends the outline under the **last top-level block** on that page, or at **EOF** when the page is empty/blockless.
3. Returns `ok: true` with `warnings` including: `Block ID invalid. Performed a safe append to the page instead.`

When **no page context** is provided (bare unknown `[42]` or random string), the tool returns `ok: false` with an actionable error — same as pre-v1.9.7 behavior.

`inject_query` **does not** empty-page fallback — it requires a real parent block and returns a clear error if the page has no outline blocks.

---

## `OutlineNode` / `heading_level` (v1.9.6–1.9.7)

Local models often echo parser metadata as `heading_level: 3` (int) in JSON. `OutlineNode` coerces int → str and **strips** `heading_level` / `heading_level::` before disk write so Logseq never receives orphan `heading_level::` properties.

---

## Operator checklist

| Scenario | Expected MCP outcome |
|----------|------------------------|
| Read page with wrong namespace | Content returned + resolution notes |
| Path traversal in page title | Text error / `ok: false`; session survives |
| `write_outline` with bad UUID + `Page\|…` | Content appended + `warnings` |
| Empty page file + bad block ref | First outline block created at EOF |
| `write_outline` with `[99]` alone (no pipe) | `ok: false` |

---

## Related reading

- [`agent-onboarding.md`](agent-onboarding.md) — `llms.txt`, PyPI `uvx`
- [`agent-dx.md`](agent-dx.md) — CLI `--json`, `context load`, Journey Log
- [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) — full MCP agent law
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) — dispatch plane diagram
