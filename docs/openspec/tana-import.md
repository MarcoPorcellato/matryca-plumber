---
type: Document
---
# Tana workspace JSON import (enterprise migration)

**Version:** 1.0  
**Status:** Implemented (v1.11.0)  
**Roadmap:** External graph migration (Tana Outliner → Logseq OG)  
**Orchestrator:** [`src/agent/tana_import.py`](../../src/agent/tana_import.py) — `run_tana_import()`  
**Package:** [`src/agent/importers/tana/`](../../src/agent/importers/tana/)  
**Related:** [`ingest.md`](ingest.md) (OCC write pipeline), [`runtime-bootstrap.md`](runtime-bootstrap.md), [`agent-dx.md`](agent-dx.md) (CLI JSON)

Matryca Plumber **imports a native Tana workspace JSON export** (flat `docs[]` graph dump) into an **active Logseq OG vault** (`LOGSEQ_GRAPH_PATH`). The importer is a **local, offline parser** — not a Tana API/MCP client. Bulk migration uses the file produced by Tana **Export workspace as JSON** ([Tana docs](https://outliner.tana.inc/docs/workspaces)); this is **not** the Tana Intermediate Format (TIF), which is import-only into Tana.

This complements **`ingest_document`**: ingestion accepts outline-shaped Markdown; Tana import accepts the proprietary flat JSON dump and performs schema translation, journal routing, depth splitting, link resolution, and provenance stamping before writing via the same OCC / page-lock / post-write pipeline.

> **Terminology:** Tana **node IDs** are stored as `tana-id::` properties. Logseq **`id::` UUIDs are always freshly generated** on import — never copied from Tana.

---

## CLI / MCP surface

### CLI

```text
matryca import tana --file <export.json> [--apply]
```

| Flag / arg | Description |
|------------|-------------|
| `--file` | Path to Tana workspace JSON export (required). |
| `--apply` | Perform writes (default: **dry-run** only). |

**UX:** Without `--apply`, the CLI prints a visible warning on **stderr**:

```text
DRY-RUN MODE: No files written to disk. Use --apply to commit.
```

**Stdout:** JSON report (`TanaImportResult.to_dict()`) — pipe-friendly:

```bash
export LOGSEQ_GRAPH_PATH=/path/to/vault
matryca import tana --file ~/Downloads/workspace.json | jq '.write'
matryca import tana --file ~/Downloads/workspace.json --apply | jq '.write.pages_created'
```

### MCP

**Signature:** `import_tana(export_path: str, dry_run: bool = True) -> dict`

**Description for hosts:** *Import a Tana workspace JSON export into the Logseq graph with streaming parse, journal format compliance, depth splitting, in-flight + catalog wikilink resolution, and `tana-*` provenance metadata.*

**Default:** `dry_run=True` — safe for autonomous agents; set `dry_run=False` only after operator review.

**Response fields (typical):** `ok`, `export_path`, `apply`, `pages_planned`, `journals_planned`, `depth_splits`, `link_stats` (`in_flight_resolved`, `catalog_title_resolved`, `catalog_alias_resolved`, `unchanged`), `write` (`pages_created`, `pages_appended`, `journals_touched`, `skipped_duplicates`, `blocks_written`, `occ_conflicts`, …), `warnings`, `error`.

---

## Input contract: Tana raw JSON dump

| Aspect | Rule |
|--------|------|
| Source | Tana → Export workspace as JSON |
| Top-level shape | `{ formatVersion, docs: NodeDump[], … }` or wrapped `{ storeData: { docs, … } }` |
| Hierarchy | **Not nested** — parent/child via `children: string[]` ID arrays |
| Re-import into Tana | Unsupported by Tana (export is one-way) |
| Scratch files | **Never** write parse scratch under `pages/` or `journals/` (watchdog / AST cache) |

Reference reverse-engineering (algorithms only; implement fresh in Plumber):

- [supertag-cli `tana-dump.ts`](https://github.com/jcfischer/supertag-cli/blob/main/src/types/tana-dump.ts)
- [tanamigrator `scanner.py`](https://github.com/glibalien/tanamigrator/blob/main/src/core/scanner.py)

---

## Pipeline (`run_tana_import`)

| Phase | Module | Behavior |
|-------|--------|----------|
| 1 | `load.py` + `graph.py` | `ijson` stream over `docs[]`; build indexes; entity heuristics |
| 2a | `logseq_config.py` + `journal.py` | Read `logseq/config.edn`; resolve `:journal/page-title-format` |
| 2b | `convert.py` | Hybrid placement + field/tag mapping + depth limit page-split |
| 3 | `link.py` | In-flight page map + `MasterCatalog.resolve_page_title` / `resolve_alias` |
| 4 | `write.py` | `tana-id` pre-scan gate; OCC + `page_rmw_lock`; dry-run skips disk |

---

## Architectural contract 1 — `ijson` streaming (anti-OOM)

**Requirement:** Phase 1 **must** parse the export with **`ijson`** in streaming mode. **`json.load()` and `ujson.load()` are forbidden** on the Tana export file in production code paths (tests monkeypatch-block `json.load()` on the loader path for parity).

**Rationale:** Tana workspace dumps can exceed hundreds of MB. Loading the full JSON DOM risks fatal OOM on 16 GB laptops.

**Implementation rules:**

1. Open export as `open(path, "rb")`.
2. Detect `storeData` wrapper via stream prefix; select ijson path `storeData.docs.item` or `docs.item`.
3. For each `docs[]` element: deserialize **one** node, validate, insert into indexes, discard raw dict.
4. Memory budget: **O(number of nodes)** for structural indexes, **not** O(file size).

**Dependency:** `ijson` in [`pyproject.toml`](../../pyproject.toml).

---

## Architectural contract 2 — Journal routing via `logseq/config.edn`

**Requirement:** Before routing Tana `#day` / calendar nodes, read `{LOGSEQ_GRAPH_PATH}/logseq/config.edn`, parse EDN, and extract **`:journal/page-title-format`**.

**Rationale:** Hardcoding `journals/YYYY-MM-DD.md` breaks vaults that customize journal titles (e.g. `MMM do, yyyy` → `Jun 22nd, 2026.md`). Wrong filenames are invisible to Logseq and cause calendar duplication.

**Implementation rules:**

1. `format_edn_date_pattern()` — Java/Clojure tokens → Python strftime.
2. `resolve_journal_path()` — on-disk path under `journals/`.
3. Inline journal links `[[…]]` use the **same** formatted title as the journal file.
4. **Fallback** when `config.edn` is missing or malformed: `yyyy-MM-dd` (Logseq default) + **warning** in report — do not abort the full import.
5. Path reads must use graph sandbox helpers (no traversal outside `LOGSEQ_GRAPH_PATH`).

**Modules:** [`src/graph/logseq_config.py`](../../src/graph/logseq_config.py), [`src/agent/importers/tana/journal.py`](../../src/agent/importers/tana/journal.py).

---

## Architectural contract 3 — Depth limit + page-split (anti-freeze UI)

**Requirement:** During AST conversion, enforce a **depth limit** (default **8**, env `MATRYCA_TANA_DEPTH_LIMIT`). When a branch would exceed the limit:

1. Create a dedicated page `Tana/Split/{Label}` for the overflow subtree.
2. Replace the deep subtree in the parent with `[[Tana/Split/{Label}]]` (after link resolution in Phase 3).
3. Stamp **`tana-depth-split:: true`** on the split page frontmatter and on the link bullet.
4. Reset depth to 0 inside the split page; apply recursively.

**Dry-run report:** `depth_splits` count on convert result.

---

## Architectural contract 4 — Hybrid placement

| Tana concept | Logseq destination |
|--------------|-------------------|
| Entity (`_flags % 2 == 1`, Library, page-like supertag) | Page `Tana/{Supertag}/{Name}` or `Tana/{Name}` |
| `#day` / calendar node | `journals/{user format from config.edn}.md` |
| Children of entity | Nested bullets (`- `, +2 spaces per level) on entity page |
| Supertag application | `#tag` inline and/or `type:: TagName` property |
| Field tuple | `field-name:: value` under owning bullet (keys: lowercase, `_` → `-`) |
| Done / checkbox | `TODO` / `DONE` prefix on block line |
| Tana references | `[[Title]]` after in-flight + catalog resolution |

**Excluded v1:** `TRASH`, pure `SYS_*` structural nodes, mega-tuples (>50 children), Tana queries/commands/search nodes (report as `non_portable`).

---

## Architectural contract 5 — Provenance metadata (`tana-*`)

Every imported page and block carries provenance. **Tana node IDs never become Logseq `id::`.**

| Property | Scope | Description |
|----------|-------|-------------|
| `tana-id::` | Page + block | Original Tana node ID |
| `tana-export::` | Page (frontmatter) | ISO-8601 timestamp of import run |
| `tana-export-file::` | Page (frontmatter) | Source filename (basename only) |
| `tana-created::` | Block/page | Tana `props.created` when present (Unix ms) |
| `tana-modified::` | Block/page | Tana `modifiedTs` when present |
| `tana-depth-split::` | Block / page | `true` when depth-split page or link stub |
| `made-by::` | New pages | `matryca plumber v…` via `stamp_plumber_authored_page` |
| `id::` | Every block | **Fresh UUID v4** — same policy as [`ingest.md`](ingest.md) |

**Idempotency (v1):** before write, scan vault for existing `tana-id::` values; if found → **skip** that page or subtree and increment `skipped_duplicates` (no `--merge` in v1). Implementation: `scan_existing_tana_ids` in `write.py` — today loads full page text per file ([#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) targets line-level streaming).

**Idempotency limits (v1):** skip is **ID-only** — if the operator edits imported content in Logseq, a re-import still skips the subtree when `tana-id::` matches, even when Tana export content diverges. Content-hash comparison and `--merge` are v2 scope ([#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139)).

---

## Memory model (parse vs index)

| Stage | Mechanism | RAM |
|-------|-----------|-----|
| JSON parse | `ijson` stream over `docs[]` via `iter_tana_nodes` | O(1) DOM — no `json.load()` |
| Graph build | `TanaWorkspaceGraph.from_export` → `StreamingGraphBuilder` single pass | **O(nodes)** — full `NodeDump` payloads retained in `_nodes` today |
| Legacy helper | `load_tana_nodes_by_id` (tests / direct index API) | Same O(nodes) retention — not used by `tana_import.py` |
| Conversion | `convert_tana_graph` + link rewrite | Additional structures on top of index |

Large enterprise exports (50k+ nodes) can peak at hundreds of MB during the index phase before any write. **Shipped:** single-pass `from_export` ([#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135)). **Open:** slim `NodeDump` payloads ([#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154)). Triage: [`CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](../quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md).

**Journal format:** `get_logseq_journal_format()` in `logseq_config.py` re-reads and re-parses `logseq/config.edn` on each call (no in-process cache). Fixing `config.edn` and re-running import picks up the new format immediately.

---

## Linking to existing vault content

For each proposed `[[Title]]` (block text and string property values):

1. **In-flight map** — titles from pages/journals created in this same import batch (label → `Tana/…` canonical title).
2. `MasterCatalog.resolve_page_title(title)` — case-insensitive page match.
3. Else `MasterCatalog.resolve_alias(title)` — `alias::` frontmatter match.
4. **No match** → leave `[[Proposed Title]]` (orphan page — expected v1 behavior).

---

## Write order and concurrency

| Step | Target |
|------|--------|
| 1 | Entity pages (including depth-split pages) |
| 2 | Journal files (append, user format) |
| 3 | `Tana/Import Log` ledger (apply only) |

Each write: `page_rmw_lock` → `OCCSnapshot.capture` → `atomic_write_bytes_if_unchanged` → post-write hooks.

| Concern | Handling |
|---------|----------|
| OCC conflict | Abort file write; increment `occ_conflicts`; log warning |
| Secret scan | `secret_violations_in_text` before any write |
| Git | Optional `robot(matryca): tana import …` when `MATRYCA_GIT_ROBOT_COMMIT` |
| Watchdog | No scratch files under graph root during parse |

---

## Environment

| Variable | Role |
|----------|------|
| `LOGSEQ_GRAPH_PATH` | Required — target vault |
| `MATRYCA_TANA_IMPORT_NAMESPACE` | Root namespace for imported pages (default `Tana`) |
| `MATRYCA_TANA_DEPTH_LIMIT` | Max nesting depth before page-split (default `8`) |
| `MATRYCA_GIT_ROBOT_COMMIT` | Post-write surgical commits |

Documented in [`.env.example`](../../.env.example).

---

## Module map

| Module | Responsibility |
|--------|----------------|
| `src/agent/importers/tana/load.py` | `ijson` streaming loader — **no** `json.load()` |
| `src/agent/importers/tana/graph.py` | Parent map, entity detection, Library/STASH |
| `src/agent/importers/tana/tags.py` | `tagDef`, `metaNode`, tuple → supertags + fields |
| `src/agent/importers/tana/html.py` | `props.name` HTML → plain keys + ref values |
| `src/agent/importers/tana/journal.py` | ISO date → journal title/path |
| `src/agent/importers/tana/convert.py` | Hybrid placement → `OutlineNode` trees + depth-split |
| `src/agent/importers/tana/link.py` | In-flight map + catalog wikilink rewrite |
| `src/agent/importers/tana/provenance.py` | `tana-*` property builders |
| `src/agent/importers/tana/write.py` | Idempotent OCC writes + `Tana/Import Log` |
| `src/graph/logseq_config.py` | `config.edn` read, journal format |
| `src/agent/tana_import.py` | `run_tana_import`, `dispatch_tana_import` |
| `src/cli/__init__.py` | `import tana` subcommand |
| `src/agent/mcp_server.py` | `import_tana` MCP tool |

**Tests:** `tests/test_tana_load.py`, `test_tana_graph.py`, `test_tana_journal.py`, `test_tana_tags.py`, `test_tana_convert.py`, `test_tana_link.py`, `test_tana_write.py`, `test_tana_e2e.py` · fixtures under `tests/fixtures/tana/`.

---

## Operator guidance

1. **Test vault first** — clone the production graph before `--apply`.
2. **Dry-run default** — review JSON report: `write.pages_created`, `journals_touched`, `depth_splits`, `link_stats`, `skipped_duplicates`.
3. **Re-import** — nodes with matching `tana-id::` are skipped (idempotent v1).
4. **Not supported v1** — Tana Markdown zip, media download, Tana queries/commands, Logseq DB graph backend, `--merge`, CLI `--depth-limit` override (use `MATRYCA_TANA_DEPTH_LIMIT`).

---

## Risks (spec-level)

| Risk | Mitigation |
|------|------------|
| OOM on large dumps | `ijson` streaming parse; **open:** O(nodes) index ([#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135)) |
| Wrong journal filenames | `config.edn` journal format before routing |
| Logseq UI freeze | Depth limit + page-split at 8 |
| Undocumented Tana JSON schema | Permissive Pydantic `props`; fixture from anonymized export |
| Re-import duplication | `tana-id::` pre-scan skip |
| Cross-export orphan links | In-flight map resolves entities within same batch |
