---
type: Document
---
# Atomic document ingestion (Master RFC — Phase 2)

**Roadmap:** Master architecture RFC — Phase 2 (external markdown → L2 graph)  
**Implementation:** `src/agent/ingestion.py`, `src/agent/mcp_server.py`  
**Agent contract:** [`SYSTEM_PROMPT.md`](../../SYSTEM_PROMPT.md) (§ `ingest_document` + Search → Scan → Update)  
**Related:** [`identity-config.md`](identity-config.md), [`l1-l2-routing.md`](l1-l2-routing.md), [`runtime-bootstrap.md`](runtime-bootstrap.md), [`lint.md`](lint.md) (quality gate)

Matryca Plumber can **atomically ingest** external Markdown (email bodies, exports, agent drafts) into the Logseq graph: parser-first block structure, fresh `id::` UUIDs on every bullet, append to a configurable ingest page, and optional **`LOG`** / **`GLOSSARY`** ledger updates — all via the **`ingest_document`** MCP tool with the same OCC, page lock, AST cache, and robot-git pipeline as other headless writes.

This complements the **Search → Scan → Update** workflow in `SYSTEM_PROMPT.md`: use `ingest_document` when the payload is already outline-shaped Markdown and you want a **single transactional append** (destination + ledgers) instead of hand-planned `mutate_graph` / `write_outline` steps.

> **Terminology:** This RFC's **Phase 2** is **external Markdown ingestion** (`ingest_document` → L2 graph append). That is distinct from the maintenance daemon's **Phase 2 cognitive indexing** (`_process_llm_cycle_file`), which applies semantic LLM lint to `pages/` only. Daily notes under `journals/` receive daemon **Phase-1 structural sync** (AST cache, OCC ledger) but **skip** semantic indexing and embeddings — see [`llm-performance.md`](llm-performance.md#journal-pages--phase-2-semantic-bypass).

---

## MCP tool: `ingest_document`

**Signature:** `ingest_document(source_name: str, raw_text: str) -> dict`

| Argument | Description |
|----------|-------------|
| `source_name` | Human label (email subject, URL title, file name). |
| `raw_text` | Markdown / Logseq-style indented bullets to parse. |

**Description for hosts:** *Atomically ingest external markdown into the graph with fresh block UUIDs and ledger updates.*

**Response fields (typical):** `ok`, `source_name`, `destination_page`, `destination_path`, `block_uuids`, `block_count`, `log_path`, `glossary_path`, `files_touched`, `routing_hint` (`<!-- matryca_routing: hint=L2_graph_append -->`).

Successful responses receive the **MCP identity footer** like other tools (except `store_fact`).

---

## Pipeline (`process_ingestion`)

| Step | Behavior |
|------|----------|
| 1. Validate | Non-empty `source_name` and `raw_text`; at least one parsed root bullet. |
| 2. Secret scan | `secret_violations_in_text` — rejects API keys and credential patterns before any write. |
| 3. Parse | `LogosParser().parse_page_file` on an **OS temp** `.md` (`tempfile.NamedTemporaryFile`, `delete=False`, `os.unlink` in `finally`). **Never** write scratch files under `pages/` — the reactive `watchdog` on `pages/` would churn the AST cache and Git audit. |
| 4. UUID stamp | Recursive copy of each `LogseqNode` with new `properties["id"]`, `uuid`, `source_uuid`, `synthetic_id=False` (`model_validate` — no in-place mutation of frozen nodes). |
| 5. Serialize | `logseq_markdown.serialize_logseq_page` → child lines indented +2 spaces under a container bullet. |
| 6. Wrap | `- Ingested: **{source_name}**` with section `id:: {uuid}`. |
| 7. Write (order) | Ingest destination → `LOG` → `GLOSSARY` (if terms found). Each step: `page_rmw_lock` → OCC mtime → `atomic_write_bytes_if_unchanged` → `emit_post_write_commit`. |

New ingest destination pages are stamped with **`made-by:: matryca plumber v…`** via `stamp_plumber_authored_page` when the file is created empty.

---

## Destination (Option C)

| `MATRYCA_INGEST_PAGE` | Logseq title | On-disk file (typical) |
|-----------------------|--------------|-------------------------|
| unset / empty | `Ingest/YYYY-MM-DD` (UTC date of run, overridable in tests via `as_of`) | `pages/Ingest___YYYY-MM-DD.md` |
| set (e.g. `AI_Inbox`) | env value | `pages/AI_Inbox.md` |

Resolution: `resolve_ingest_destination_page_title()` in `src/agent/ingestion.py`. Filename encoding follows `page_title_to_filename` (namespace `/` → `___`).

Documented in `.env.example` as **Advanced** (with identity config).

---

## Ledger pages

Created on **first ingest** if missing (same append helper as destination).

### `LOG`

Appends one bullet per ingest:

```markdown
- [[2026-05-31]] - Ingested: **Weekly sync** - Generated 12 blocks. (UUIDs: uuid-1, uuid-2, … +3 more)
```

UUID list is capped (default **12** shown, remainder as `… +N more`).

### `GLOSSARY`

For each new term (deduped against existing `[[Term]]` lines, case-insensitive):

- **`#tags`** from inline tag regex (same family as `link_tag_hop._extract_inline_tags`)
- **Title-Case** multi-word terms (conservative regex; e.g. `Contract-Law`)

```markdown
- [[legal-tech]] -> {{embed ((block-uuid))}}
```

Terms map to the **first block UUID** whose text contains the tag/term during tree walk; raw-markdown-only tags fall back to the first root block.

MVP: all body blocks land on **one** ingest page; tags do **not** fan out to separate namespace pages.

---

## Concurrency and side effects

| Concern | Handling |
|---------|----------|
| OCC | `OCCSnapshot.capture` before read-modify-write; abort on drift or failed `atomic_write_bytes_if_unchanged`. |
| Page lock | `page_rmw_lock` per target `.md` file. |
| AST cache | Post-write hooks refresh the modified page in `GraphAstCache`. |
| Git | Optional `robot(matryca): ingest …` per file when `MATRYCA_GIT_ROBOT_COMMIT` and repo present. |
| Watchdog | Temp parse path **outside** graph root — no spurious `pages/` events. |

---

## Environment

| Variable | Role |
|----------|------|
| `LOGSEQ_GRAPH_PATH` | Required (via `graph_path_from_env()`). |
| `MATRYCA_INGEST_PAGE` | Optional fixed ingest page title (empty → daily `Ingest/YYYY-MM-DD`). |
| `MATRYCA_GIT_ROBOT_COMMIT` | Post-write surgical commits (default on in git repos). |
| `MATRYCA_WATCH_DEBOUNCE_MS` | Irrelevant to parse temp files; applies only to real graph writes under `pages/`. |

---

## Module map

| Module | Responsibility |
|--------|----------------|
| `src/agent/ingestion.py` | `process_ingestion`, `resolve_ingest_destination_page_title`, `dispatch_ingest_document` |
| `src/agent/mcp_server.py` | Registers `ingest_document` |
| `src/agent/quality_gate.py` / `src/utils/secret_redaction.py` | Secret patterns (ingestion calls `secret_violations_in_text` directly) |
| `src/graph/markdown_blocks.py` | OCC, atomic writes, `graph_safe_page_path` |
| `src/graph/page_properties.py` | `stamp_plumber_authored_page` for new pages |
| `src/graph/link_tag_hop.py` | Inline `#tag` extraction for glossary |
| `src/daemon/post_write_hooks.py` | `emit_post_write_commit` fan-out |

**Tests:** `tests/test_atomic_ingestion.py`, `tests/test_mcp_server.py` (tool registration count).

---

## Search → Scan → Update (llm-wiki workflow)

| Workflow phase | When to use `ingest_document` |
|----------------|--------------------------------|
| **Search** | External source already available as Markdown bullets; classify as L2; run secret check mentally before call. |
| **Scan** | Optional: read ingest destination / `LOG` to avoid duplicate `source_name` on same day. |
| **Update** | **Preferred** for bulk external outline paste; use `mutate_graph` for surgical edits to existing blocks. |

For multi-page routing by tag, namespace, or `page_type`, continue with planned `mutate_graph` / `write_outline` flows — Phase 2 ingestion is intentionally **single destination page** MVP.

For **Tana workspace JSON exports** (flat `docs[]`, supertags, `#day` journals), use **`import_tana`** / **`matryca import tana`** instead — see [`tana-import.md`](tana-import.md).
