# GitHub Bug Backlog — Matryca Plumber

**Hunt date:** 2026-06-23  
**Tools:** GitNexus (`check`, `query`, `clusters`, `detect_changes`, `explain`, `cypher`) + `pytest` (874 passed), `ruff`, `mypy --strict`  
**Companion:** [`BUG_HUNT_2026-06-23.md`](BUG_HUNT_2026-06-23.md)

This document is the **maintainer-ready registry** for filing or triaging GitHub issues. It deduplicates against the **42 open issues** on `MarcoPorcellato/matryca-plumber` as of this hunt.

---

## Hunt verdict

| Gate | Result |
|------|--------|
| `pytest -q` | **874 passed**, 2 skipped |
| Coverage `src/` | **81.13%** (gate 70%) |
| Ruff | Clean |
| Mypy strict | Clean |
| Runtime regressions found | **0** (no failing tests) |
| Confirmed code defects / debt | **Yes** — mostly observability, concurrency precision, performance, architecture |

**Conclusion:** The codebase is **test-green** but not **bug-free**. Most actionable work already lives in GitHub **#38–#105** (v1.9.x audit). GitNexus hunt filed **#113–#119** on GitHub (2026-06-23); records **2 fixes already merged locally**.

---

## Fixed locally (do not re-file)

| Item | Resolution | Evidence |
|------|------------|----------|
| Flaky semantic clustering perf test | Moved to `tests/slow/`, `@pytest.mark.slow`, 15s ceiling | Intermittent 9.09s fail under full suite |
| `alias_index` ↔ `generational_cache` import cycle | DI: `is_journal_page_title_in_index` in domain; cached facade in `generational_cache` | `import src.graph.alias_index` does not load `generational_cache` |

**Follow-up for #71:** Partially addressed — journal detection now has a pure domain API + injected `AliasIndex`. Consider commenting on [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) when closing the import-cycle slice.

**Follow-up for GitNexus:** Re-run `./scripts/gitnexus-analyze-embeddings.sh` so `check --cycles` drops the stale `alias_index` edge.

---

## Existing open issues — priority map

### P0 — Concurrency / data integrity (file first)

| Issue | Title | Location (verified) |
|-------|-------|---------------------|
| [#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) | `needs_refresh` truncated seconds vs OCC nanoseconds | `master_catalog.py` |
| [#39](https://github.com/MarcoPorcellato/matryca-plumber/issues/39) | `auto_split` child pages without child path lock | `auto_split.py` |
| [#42](https://github.com/MarcoPorcellato/matryca-plumber/issues/42) | Semantic cache purge / cluster load without flock | `semantic_clustering.py` |
| [#43](https://github.com/MarcoPorcellato/matryca-plumber/issues/43) | Race seeding `matryca-config.md` in `store_fact` | `memory_tools.py` / dispatch |
| [#103](https://github.com/MarcoPorcellato/matryca-plumber/issues/103) | `_sync_catalog_after_page_write` second-precision mtime | `maintenance_daemon.py:2309` — `int(path.stat().st_mtime)` |
| [#104](https://github.com/MarcoPorcellato/matryca-plumber/issues/104) | `load_semantic_clusters` without `cross_process_json_flock` | `semantic_clustering.py:561-570` |

### P1 — Observability / silent failure

| Issue | Title | Location (verified) |
|-------|-------|---------------------|
| [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101) | SIG handler suppresses `token_logger` shutdown | `maintenance_daemon.py:2042` — `contextlib.suppress(Exception)` |
| [#102](https://github.com/MarcoPorcellato/matryca-plumber/issues/102) | TUI suppresses activity / state load failures | `tui_dashboard.py:93,119,129,225` |
| [#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) | Test: shutdown cleanup after save failures | test gap |

### P2 — Performance (v1.9.x audit #20–#30)

| Issue | Title |
|-------|-------|
| [#46](https://github.com/MarcoPorcellato/matryca-plumber/issues/46)–[#56](https://github.com/MarcoPorcellato/matryca-plumber/issues/56) | AST cache, catalog reload, daemon state saves, vault scans, mmap copy, Phase-2 double-read, backlink cache, etc. |
| [#69](https://github.com/MarcoPorcellato/matryca-plumber/issues/69) | Skip cluster-focus for single-page clusters |

### P3 — Tech debt / v2.0

| Issue | Title |
|-------|-------|
| [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)–[#64](https://github.com/MarcoPorcellato/matryca-plumber/issues/64) | env parser DRY, mega-modules, parser coupling |
| [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) | `maintenance_daemon.py` ~3283 LOC |
| [#59](https://github.com/MarcoPorcellato/matryca-plumber/issues/59) | `graph_dispatch.py` handler registry |
| [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) | Centralize journal page detection |
| [#73](https://github.com/MarcoPorcellato/matryca-plumber/issues/73) | Soak tests for daemon memory |
| [#99](https://github.com/MarcoPorcellato/matryca-plumber/issues/99) | Biological memory epic |

---

## NEW — Filed on GitHub (#113–#119, 2026-06-23)

| Issue | Title | Milestone |
|-------|-------|-----------|
| [#113](https://github.com/MarcoPorcellato/matryca-plumber/issues/113) | `_count_catalog_summaries` swallows exceptions | v1.9.12 |
| [#114](https://github.com/MarcoPorcellato/matryca-plumber/issues/114) | Graph Insights LLM silent fallback | v1.9.12 |
| [#115](https://github.com/MarcoPorcellato/matryca-plumber/issues/115) | `memory/config` layer inversion (blocks #99) | v2.0.0 |
| [#116](https://github.com/MarcoPorcellato/matryca-plumber/issues/116) | `plumber_config` ↔ `llm_url_policy` cycle | v1.9.12 |
| [#117](https://github.com/MarcoPorcellato/matryca-plumber/issues/117) | `control_room_progress` ↔ `maintenance_daemon` | v1.9.12 |
| [#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118) | httpx2 / Starlette deprecation in CI | v1.9.12 |
| [#119](https://github.com/MarcoPorcellato/matryca-plumber/issues/119) | GitNexus PDG + `check --cycles` in CI | v1.9.12 |

Issue bodies (maintainer template): `docs/quality/issue-bodies/10{6..2}-*.md`

---

## Archive — draft bodies

_Superseded by #113–#119. Maintainer templates: `docs/quality/issue-bodies/106-*.md` … `112-*.md`._

---

## GitNexus structural findings (reference)

| Finding | Status | GitHub |
|---------|--------|--------|
| Import cycle `alias_index` ↔ `generational_cache` | **Fixed locally** | Comment on [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) |
| Import cycle `plumber_config` ↔ `llm_url_policy` | Open | [#116](https://github.com/MarcoPorcellato/matryca-plumber/issues/116) |
| Import cycle `control_room_progress` ↔ `maintenance_daemon` | Open (lazy) | [#117](https://github.com/MarcoPorcellato/matryca-plumber/issues/117) |
| `html.py` self-cycle | False positive | — |
| Taint PDG | Not indexed | [#119](https://github.com/MarcoPorcellato/matryca-plumber/issues/119) |
| Module cohesion: Daemon 87%, Agent 64% | Informational | [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) |
| `shape_check` API routes | N/A (Python project) | — |

---

## Recommended PR order (milestones)

1. **#113**, **#103**, **#104**, **#38** — data integrity / observability  
2. **#101**, **#102**, **#114** — logging gaps  
3. **#115**, **#116** — prep Epic [#99](https://github.com/MarcoPorcellato/matryca-plumber/issues/99)  
4. Performance batch **#46–#56**  
5. **#117–#119** — architecture / CI hygiene  

---

## Commands for contributors

```bash
make check                    # full gate before PR
make test-fast                # local iteration
uv run pytest tests/test_graph_analytics.py -q   # #113
```

---

*49 open issues as of 2026-06-23 after filing #113–#119.*
