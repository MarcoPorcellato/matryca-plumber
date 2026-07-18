# v2.0-alpha hardening — tracking issue

## Problem Description

`v2.0.0-alpha.1` ships Axis 1 hardening on the opt-in Shadow DB read cache behind `MATRYCA_SHADOW_DB_ENABLED`. Before `v2.0.0-rc`, we need a structured hardening campaign: reproduce real failures and edge cases with minimal tests, then land **surgical PRs** per confirmed finding — no monolithic audit-fix PR.

**Baseline:** tag [`v2.0.0-alpha.1`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha.1) (release PR pending merge) · prior [`v2.0.0-alpha`](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.0.0-alpha) superseded for new installs.

**Parent epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)

## Proposed Architectural Solution

Seven-axis audit with severity classification **P0–P3**. Each **confirmed** finding gets:

1. A **minimal reproducer test** (fixture vault, failure injection, read-only where possible).
2. A **child issue** linked below.
3. A **surgical PR** — one concern per PR.

### Severity

| Level | Meaning |
|-------|---------|
| **P0** | Data loss/corruption, sandbox bypass, broken fallback to Markdown/BM25 |
| **P1** | Wrong query results, bootstrap stuck, reproducible race |
| **P2** | Diagnostics, performance regression, edge-case contract gap |
| **P3** | Ergonomics, docs-only |

### RC exit criteria

- **No open P0 or P1** findings.
- Every **P2** either fixed or explicitly accepted with rationale in this table.

### Baseline verification commands

```bash
make ci
uvx matryca-plumber@2.0.0-alpha.1 --version   # expect 2.0.0-alpha.1 (PyPI 2.0.0a1)
# vault soak (flag off + flag on) — see Epic #20 distribution comment
```

---

## Seven axes (checklist)

### Axis 1 — Concurrency & recovery

- [x] Bootstrap vs `post_write` / file watcher (defer + replay) — **A1-DEFER-01/02 pass**
- [x] Two processes on the same vault (daemon + CLI / twin `uvx`) — **A1-PROC-01/02 fixed (#262)**
- [x] SQLite `locked` / writer contention / crash mid-transaction — **A1-SQLITE-01 pass; A1-BOOT-02 accepted**
- [x] `shadow_meta` `ready` coherent with committed page/block generation — **A1-META-01 fixed (#264)**

### Axis 2 — Shadow ↔ Markdown correctness

**Status:** audit probes in progress (`tests/test_shadow_hardening_axis2_parity.py`).

- [ ] Bootstrap parity (pages, blocks, parentage, order) — **A2-PARITY-01 pass**
- [ ] Full rebuild vs incremental equivalent sequence — **A2-PARITY-02/03/05 pass**
- [ ] Shadow never writes Markdown — **A2-PARITY-04 pass**
- [ ] Watcher create/modify/delete — **A2-WATCH-01 pass**
- [ ] Rename on disk — **A2-WATCH-02 P1 open**
- [ ] Modify during bootstrap replay — **A2-WATCH-03 pass**
- [ ] Journals + encoded page titles — **A2-PARSE-01 pass**
- [ ] Unicode, multiline, page properties — **A2-PARSE-02 pass**
- [ ] Empty / minimal Markdown — **A2-PARSE-03 pass**
- [ ] Parser-tolerant malformed outline — **A2-PARSE-04 pass**
- [ ] Intra-page duplicate `block_uuid` rejected — **A2-PARSE-05 pass**
- [ ] Delete + recreate same title — **A2-PARSE-06 pass**

### Axis 3 — Routing & fallback

- [ ] Health changes between port selection and query
- [ ] DB removed/corrupted after `ready`
- [ ] Flag toggled across processes
- [ ] Zero-hit and not-found must **not** trigger Markdown fallback

### Axis 4 — FTS5

- [ ] Special chars, quotes, operators, Unicode
- [ ] Very long queries
- [ ] Limits and deterministic ordering
- [ ] MCP/CLI envelope parity

### Axis 5 — CTE subtree

- [ ] Extreme depth / large sibling sets
- [ ] Artificial cycles and cross-page parents
- [ ] UTF-8 byte truncation
- [ ] Property-based parity vs parser Markdown reads

### Axis 6 — Security & isolation

- [ ] Path traversal and symlink escape
- [ ] Sanitized errors (no vault content leak)
- [ ] Flag `false` must not create/open/mutate SQLite
- [ ] Shadow DB must never write Markdown

### Axis 7 — Performance

- [ ] Bootstrap at 1k / 10k / 50k blocks
- [ ] FTS/CTE latency p50/p95
- [ ] Memory and lock hold duration
- [ ] Watcher cost on file bursts

---

## Findings table

| ID | Axis | Repro | Sev | Minimal test | Child issue | Status |
|----|------|-------|-----|--------------|-------------|--------|
| A1-PROC-01 | 1 | Cross-process rebuild while SQLite writer active | **P1** | `test_a1_cross_process_rebuild_completes_while_sqlite_writer_active` | [#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262) | **fixed** (`v2.0.0-alpha.1`) |
| A1-PROC-02 | 1 | Design review | **P1** | `test_a1_rebuild_lock_is_in_process_only_documented_gap` | [#262](https://github.com/MarcoPorcellato/matryca-plumber/issues/262) | **fixed** (`v2.0.0-alpha.1`) |
| A1-META-01 | 1 | Manual meta corruption on fixture DB | **P2** | `test_a1_health_not_ready_when_meta_completed_but_pages_empty` | [#264](https://github.com/MarcoPorcellato/matryca-plumber/issues/264) | **fixed** (`v2.0.0-alpha.1`) |
| A1-BOOT-02 | 1 | Injected page failure mid-rebuild | **P2** | `test_a1_rebuild_injected_failure_preserves_committed_generation` | — | **accepted** — rollback preserves generation; `last_sync_error` forces `error` health (fallback) |
| A1-DEFER-01 | 1 | Watchdog delete deferred + file removed | — | `test_a1_watchdog_delete_during_bootstrap_replays_removal_when_file_gone` | — | **pass** |
| A1-DEFER-02 | 1 | `post_write` during bootstrap | — | `test_a1_post_write_during_bootstrap_replays_after_rebuild` | — | **pass** |
| A1-SQLITE-01 | 1 | Holder keeps `BEGIN IMMEDIATE` | — | `test_a1_sqlite_writer_lock_blocks_incremental_without_meta_corruption` | — | **pass** |
| A2-WATCH-02 | 2 | Page file rename leaves stale shadow row | **P1** | `test_a2_watch_02_rename_file_path_parity` | [#272](https://github.com/MarcoPorcellato/matryca-plumber/issues/272) | **open** |
| A2-PARITY-01 | 2 | Bootstrap structural snapshot | — | `test_a2_parity_01_bootstrap_pages_blocks_parentage_order` | — | **pass** |
| A2-PARITY-02 | 2 | Full vs incremental create sequence | — | `test_a2_parity_02_full_rebuild_matches_incremental_create_sequence` | — | **pass** |
| A2-PARITY-03 | 2 | Full vs incremental mutations | — | `test_a2_parity_03_full_rebuild_matches_incremental_mutations` | — | **pass** |
| A2-PARITY-04 | 2 | Shadow read-only on Markdown | — | `test_a2_parity_04_shadow_never_writes_markdown` | — | **pass** |
| A2-PARITY-05 | 2 | Permuted incremental schedules | — | `test_a2_parity_05_equivalent_op_permutations_match_full_rebuild` | — | **pass** |
| A2-WATCH-01 | 2 | Watchdog CRUD parity | — | `test_a2_watch_01_watchdog_crud_matches_incremental_sync` | — | **pass** |
| A2-WATCH-03 | 2 | Bootstrap defer replay | — | `test_a2_watch_03_modify_during_bootstrap_replays` | — | **pass** |
| A2-PARSE-01 | 2 | Journal + encoded titles | — | `test_a2_parse_01_journal_and_encoded_page_title` | — | **pass** |
| A2-PARSE-02 | 2 | Unicode / multiline / properties | — | `test_a2_parse_02_unicode_multiline_and_page_properties` | — | **pass** |
| A2-PARSE-03 | 2 | Empty / whitespace pages | — | `test_a2_parse_03_empty_and_minimal_markdown` | — | **pass** |
| A2-PARSE-04 | 2 | Malformed outline tolerance | — | `test_a2_parse_04_malformed_outline_still_parity` | — | **pass** |
| A2-PARSE-05 | 2 | Duplicate block UUID rejection | — | `test_a2_parse_05_duplicate_block_uuid_raises` | — | **pass** |
| A2-PARSE-06 | 2 | Delete + recreate same title | — | `test_a2_parse_06_delete_and_recreate_same_title` | — | **pass** |

---

## Estimated Impact

**Alto** — gates `v2.0.0-rc` confidence for operators enabling `MATRYCA_SHADOW_DB_ENABLED`.

## Files Involved

- `src/shadow/` (bootstrap, sync, meta, health, connection, writer_lock)
- `src/agent/shadow_graph_repository.py`, `src/agent/graph_read_port.py`
- `tests/test_shadow_hardening_axis*.py` (audit reproducers)
- `docs/quality/issue-bodies/v2-alpha-hardening.md` (this body, SSOT for edits)

---
**Epic:** [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20)  
**Milestone:** `v2.0.0 — Shadow DB & Safe-Sync Architecture`

_Closes when RC exit criteria are met and findings table is empty or P2-only with explicit acceptance._
