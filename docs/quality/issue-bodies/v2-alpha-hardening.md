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

- [ ] Rename/delete during bootstrap
- [ ] Duplicate Logseq titles / encoded filenames
- [ ] Missing, intra-page, and cross-page duplicate `block_uuid`
- [ ] Multiline properties, deep blocks, journals, namespaces

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
