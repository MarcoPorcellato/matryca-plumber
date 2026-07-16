# Good First Issues — Contributor Blueprints

**Updated 2026-07-16 (Tier G added)** — pass 4 closed #97 (OCC filesystem docs); pass 3 closed #38, #113; pass 2 closed #42, #91, #92; pass 1 closed 33 audit issues ([`docs/quality/ISSUE_TRIAGE_2026-07-01.md`](docs/quality/ISSUE_TRIAGE_2026-07-01.md)). **Tier D** [#125](https://github.com/MarcoPorcellato/matryca-plumber/issues/125)–[#129](https://github.com/MarcoPorcellato/matryca-plumber/issues/129). **Tier F** [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168)–[#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173). **Tier G** (complexity slices, 2026-07-16 deep audit) [#220](https://github.com/MarcoPorcellato/matryca-plumber/issues/220)–[#239](https://github.com/MarcoPorcellato/matryca-plumber/issues/239). F10 dead-symbol check from the same audit closed with no removal needed (#206, duplicate #217).

**Active good-first candidates:** #43, #52, [#114](https://github.com/MarcoPorcellato/matryca-plumber/issues/114), [#125](https://github.com/MarcoPorcellato/matryca-plumber/issues/125)–[#129](https://github.com/MarcoPorcellato/matryca-plumber/issues/129), **Tier F** [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168)–[#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173), **Tier G** [#220](https://github.com/MarcoPorcellato/matryca-plumber/issues/220)–[#239](https://github.com/MarcoPorcellato/matryca-plumber/issues/239). Start with [`docs/FIRST_CONTRIBUTION.md`](docs/FIRST_CONTRIBUTION.md); welcome comments on each GitHub thread.

Expert Audit 2026-06 triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md) · issues [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132)–[#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139). Repomix audit: [`docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md`](docs/quality/REPOmix_AUDIT_TRIAGE_2026-06.md) · [#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142). Clean Architecture audit (simulated): [`docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md) · [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153)–[#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154). Claude Architectural audit (2026-06-24): [`docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md) · [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155)–[#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157). **Tier F Clean Code:** [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md) · `scripts/populate_gfi_tier_f.sh`.

**Before opening a PR:** read [`CONTRIBUTING.md`](CONTRIBUTING.md), run `make check`, and reference the issue number in your PR title (e.g. `fix(daemon): log SIG handler shutdown telemetry (#101)`).

If a maintainer closes an overarching audit issue while your PR is open, **rebase on `main`** and update tests/docs to match the new architecture (see CONTRIBUTING § Pull request workflow).

---

## Shipped — Issue #44 (daemon shutdown save logging)

**Difficulty:** 2/10 · Closed via [#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100) · contributor @gaoflow

**Summary:** `_finalize_graceful_shutdown` now uses `try/except OSError` + `logger.exception` for final catalog and daemon state saves instead of `contextlib.suppress(Exception)`.

**Regression test:** `test_graceful_shutdown_logs_final_save_errors` in `tests/test_maintenance_daemon.py`.

**Follow-up slices:** [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101) (SIG handler token_logger), [#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) (cleanup-after-failure test).

---

## Shipped — Tier C (#101–#105, @gaoflow)

**Difficulty:** 2–3/10 · Closed via [#108](https://github.com/MarcoPorcellato/matryca-plumber/pull/108)–[#112](https://github.com/MarcoPorcellato/matryca-plumber/pull/112) · contributor @gaoflow

| Issue | Summary |
|-------|---------|
| [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101) | SIG handler logs `token_logger.log_daemon_shutdown` failures |
| [#102](https://github.com/MarcoPorcellato/matryca-plumber/issues/102) | TUI dashboard logs activity tail / state load failures |
| [#103](https://github.com/MarcoPorcellato/matryca-plumber/issues/103) | `_sync_catalog_after_page_write` uses `st_mtime_ns` |
| [#104](https://github.com/MarcoPorcellato/matryca-plumber/issues/104) | `load_semantic_clusters` reads under `cross_process_json_flock` |
| [#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) | Test: shutdown cleanup continues after save failures |

---

## Shipped — Issue #118 (httpx2 dev dependency, CI warnings)

**Difficulty:** 2/10 · Integrated via [#122](https://github.com/MarcoPorcellato/matryca-plumber/pull/122) · contributor @blackwolf225 · landed on `main` in [`b7b9cdf`](https://github.com/MarcoPorcellato/matryca-plumber/commit/b7b9cdf5d8877a069da84ae423414333ef339c88) (PR **closed**, not GitHub-merged — maintainer rebase/`uv.lock`; authorship on [`5fea6b1`](https://github.com/MarcoPorcellato/matryca-plumber/commit/5fea6b118ac0dd608bf43a6887ba32ee8a30413a) / [`616b5f0`](https://github.com/MarcoPorcellato/matryca-plumber/commit/616b5f099ba1f9f16c58711447a1493860689ac9))

**Summary:** Added `httpx2>=2.4.0` to `[project.optional-dependencies] dev` so `fastapi/testclient` no longer emits `StarletteDeprecationWarning` during the test suite (`make check` / CI use `--extra dev`).

**Verify:**
```bash
uv run pytest tests/test_ui_server.py -q -W error::DeprecationWarning
make check
```

---

## Tier D — Post-#105 backlog (#125–#129)

| Issue | Summary | Difficulty |
|-------|---------|------------|
| [#125](https://github.com/MarcoPorcellato/matryca-plumber/issues/125) | TUI logs `compute_scan_metrics` / Phase-2 progress failures (slice of #102) | 2/10 |
| [#126](https://github.com/MarcoPorcellato/matryca-plumber/issues/126) | TUI `collect_snapshot_safe` logs outer `collect_snapshot` failures (slice of #102) | 2/10 |
| [#127](https://github.com/MarcoPorcellato/matryca-plumber/issues/127) | TUI `_try_load_daemon_state` logs state load failures (slice of #102) | 2/10 |
| [#128](https://github.com/MarcoPorcellato/matryca-plumber/issues/128) | Journal settle logs link registry merge failures | 2/10 |
| [#129](https://github.com/MarcoPorcellato/matryca-plumber/issues/129) | Test: cognitive module LLM fault logs warning and continues (test-only) | 2/10 |

**Verify (TUI slices #125–#127):**
```bash
uv run pytest tests/test_tui_dashboard.py -q
make check
```

**Verify (#128):**
```bash
uv run pytest tests/test_maintenance_daemon.py -q
make check
```

**Verify (#129):**
```bash
uv run pytest tests/test_plumber_modules.py -q
make check
```

---

## Tier E — Observability slices (#143–#152)

| Issue | Summary | Difficulty |
|-------|---------|------------|
| [#143](https://github.com/MarcoPorcellato/matryca-plumber/issues/143) | Graph analytics logs `load_master_catalog` failures | 2/10 |
| [#144](https://github.com/MarcoPorcellato/matryca-plumber/issues/144) | Checkpoint `.bak` restore copy logs `OSError` | 2/10 |
| [#145](https://github.com/MarcoPorcellato/matryca-plumber/issues/145) | Daemon state `.bak` restore copy logs `OSError` | 2/10 |
| [#146](https://github.com/MarcoPorcellato/matryca-plumber/issues/146) | Daemon state `.bak` sidecar write logs `OSError` | 2/10 |
| [#147](https://github.com/MarcoPorcellato/matryca-plumber/issues/147) | Journey log upsert logs write failures | 2/10 |
| [#148](https://github.com/MarcoPorcellato/matryca-plumber/issues/148) | File watcher deleted-page link registry logs failures | 2/10 |
| [#149](https://github.com/MarcoPorcellato/matryca-plumber/issues/149) | Phase-2 lint link registry merge logs failures (slice of #128) | 2/10 |
| [#150](https://github.com/MarcoPorcellato/matryca-plumber/issues/150) | End-of-cycle Phase-2 totals refresh logs failures (slice of #137) | 2/10 |
| [#151](https://github.com/MarcoPorcellato/matryca-plumber/issues/151) | Fast-track link registry registration logs failures | 2/10 |
| [#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152) | `plumber_config._env_int` warns on invalid fallback (slice of #57) | 2/10 |

**Verify (#143):**
```bash
uv run pytest tests/test_graph_analytics.py -q
make check
```

**Verify (#144):**
```bash
uv run pytest tests/test_daemon_checkpoint.py -q
make check
```

**Verify (#145–#151, daemon slices):**
```bash
uv run pytest tests/test_maintenance_daemon.py -q
make check
```

**Verify (#148, watcher):**
```bash
uv run pytest tests/test_file_watcher.py -q
make check
```

**Verify (#150, TUI progress):**
```bash
uv run pytest tests/test_tui_dashboard.py -q
make check
```

**Verify (#152, config):**
```bash
uv run pytest tests/test_plumber_config.py -q
make check
```

**Conflict note:** Pick **one** `maintenance_daemon.py` slice per PR (#128, #145–#147, #149–#151) to avoid merge conflicts.

---

## Tier C — Post-#100 backlog (#101–#105) — shipped

| Issue | Summary | Difficulty |
|-------|---------|------------|
| [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101) | SIG handler logs `token_logger.log_daemon_shutdown` failures (slice of #44) | 2/10 |
| [#102](https://github.com/MarcoPorcellato/matryca-plumber/issues/102) | TUI dashboard logs activity tail / state load failures | 2/10 |
| [#103](https://github.com/MarcoPorcellato/matryca-plumber/issues/103) | `_sync_catalog_after_page_write` uses `st_mtime_ns` not truncated seconds | 2/10 |
| [#104](https://github.com/MarcoPorcellato/matryca-plumber/issues/104) | `load_semantic_clusters` reads cluster JSON under `cross_process_json_flock` (slice of #42) | 3/10 |
| [#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) | Test: shutdown cleanup continues after save failures (test-only, extends #100) | 2/10 |

Promoted: [#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) — `needs_refresh` nanosecond alignment (3/10).

---

## Issue #101 — SIG handler shutdown telemetry (slice of #44)

**Difficulty:** 2/10 · [GitHub #101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)

**Verify:**
```bash
uv run pytest tests/test_maintenance_daemon.py -q
make check
```

---

## Issue #102 — TUI dashboard suppressed refresh errors

**Difficulty:** 2/10 · [GitHub #102](https://github.com/MarcoPorcellato/matryca-plumber/issues/102)

**Verify:**
```bash
uv run pytest tests/test_tui_dashboard.py -q
make check
```

---

## Issue #103 — `_sync_catalog_after_page_write` nanosecond mtime

**Difficulty:** 2/10 · [GitHub #103](https://github.com/MarcoPorcellato/matryca-plumber/issues/103)

**Verify:**
```bash
uv run pytest tests/test_maintenance_daemon.py tests/test_master_catalog.py -q
make check
```

---

## Issue #104 — semantic cluster JSON flock (slice of #42)

**Difficulty:** 3/10 · [GitHub #104](https://github.com/MarcoPorcellato/matryca-plumber/issues/104)

**Verify:**
```bash
uv run pytest tests/test_semantic_clustering.py -q
make check
```

---

## Issue #105 — shutdown cleanup regression test (test-only)

**Difficulty:** 2/10 · [GitHub #105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105)

**Verify:**
```bash
uv run pytest tests/test_maintenance_daemon.py -q
make check
```

---

## Issue #38 — `needs_refresh` nanosecond alignment

**Difficulty:** 3/10 · [GitHub #38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38)

**Verify:**
```bash
uv run pytest tests/test_master_catalog.py -q
make check
```

---

## In progress — Issue #45 (test-only, nanosecond OCC)

**Difficulty:** 2/10 · [GitHub #45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) — **closed** (tests shipped)

**Title (updated):** `[Test] Add nanosecond OCC regression tests for link_verification`

**Context:** Production fix (`file_mtime_drifted()` in `link_verification.py`) shipped via v1.9.10 nanosecond OCC (#38). Float-based mocks (`1.0`, `1.0 + 5e-7`) are obsolete — `file_mtime_drifted()` compares exact `st_mtime_ns` integers.

**Exact Contribution Guide Comment:**

> Hi! Thanks for your interest in contributing to Matryca Plumber.
>
> **What to add:** Regression tests in `tests/test_link_verification.py` using integer nanosecond mocks. No production changes expected after rebase on current `main`.
>
> **Suggested tests:**
> 1. `test_flag_block_proceeds_when_mtime_unchanged_ns` — baseline == current → write proceeds.
> 2. `test_flag_block_aborts_on_one_nanosecond_mtime_drift` — `1_000_000_000` vs `1_000_000_001` → write aborted.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_link_verification.py -q --no-cov
> make check
> ```
>
> Rebase on latest `main` before opening/updating the PR. Welcome aboard!

---

## Tier A — Promoted audit issues (#52, #43)

Tagged `good first issue` + `help wanted` by `scripts/populate_gfi_backlog.sh`. Full welcome comments are on each GitHub thread.

| Issue | Summary | Difficulty |
|-------|---------|------------|
| [#52](https://github.com/MarcoPorcellato/matryca-plumber/issues/52) | `MmapTextView` avoids full `mmap[:]` copy | 2/10 |
| [#43](https://github.com/MarcoPorcellato/matryca-plumber/issues/43) | `page_rmw_lock` on `matryca-config.md` seed race | 3/10 |

---

## Issue #89 — bootstrap_harvest `st_mtime_ns` (B1)

**Difficulty:** 2/10 · [GitHub #89](https://github.com/MarcoPorcellato/matryca-plumber/issues/89)

**Exact Contribution Guide Comment:**

> Hi! Thanks for your interest — this aligns harvest catalog entries with nanosecond OCC (#38).
>
> **What to fix:** `bootstrap_harvest.py` still uses `int(page_path.stat().st_mtime)` (~lines 207, 274). Replace with `st_mtime_ns` and align with `CatalogEntry.last_mtime`.
>
> **Steps:**
> 1. Read `normalize_stored_mtime_ns()` in `markdown_blocks.py` / `master_catalog.py`.
> 2. Update harvest entry builders to use nanoseconds.
> 3. Extend `tests/test_bootstrap_yield.py`.
>
> **Verify:**
> ```bash
> uv run pytest tests/test_bootstrap_yield.py tests/test_master_catalog.py -q
> make check
> ```

---

## Issue #90 — deduplicate `_env_bool` in link_verification (B2)

**Difficulty:** 2/10 · [GitHub #90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90) · slice of [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)

**Exact Contribution Guide Comment:**

> Hi! Small DRY cleanup — great first PR.
>
> **What to fix:** Remove local `_env_bool` in `src/graph/link_verification.py`; import from `plumber_config`.
>
> **Verify:**
> ```bash
> uv run pytest tests/test_link_verification.py -q
> make check
> ```
>
> Do not migrate other modules in the same PR.

---

## Issue #91 — deduplicate env parsers in markdown_io (B3)

**Difficulty:** 2/10 · [GitHub #91](https://github.com/MarcoPorcellato/matryca-plumber/issues/91) · slice of [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57)

**Exact Contribution Guide Comment:**

> Hi! Pair with B2 in a **separate PR** to avoid conflicts.
>
> **What to fix:** Remove local `_env_bool` / `_env_int` in `src/graph/markdown_io.py`; import from `plumber_config`.
>
> **Verify:**
> ```bash
> uv run pytest tests/test_markdown_io.py -q
> make check
> ```

---

## Issue #92 — harvest semantic-index abort regression test (B5)

**Difficulty:** 2/10 · [GitHub #92](https://github.com/MarcoPorcellato/matryca-plumber/issues/92) · test-only (audit #11 behavior)

**Exact Contribution Guide Comment:**

> Hi! Test-only PR — documents existing OCC-safe behavior.
>
> **What to add:** In `tests/test_bootstrap_yield.py`, mock `_append_minimal_semantic_index` → `False` and assert `catalog.upsert` is not called.
>
> **Verify:**
> ```bash
> uv run pytest tests/test_bootstrap_yield.py -q
> make check
> ```

---

## Issue #93 — purge_expired_semantic_cache without json flock (B6)

**Difficulty:** 3/10 · [GitHub #93](https://github.com/MarcoPorcellato/matryca-plumber/issues/93) · slice of [#42](https://github.com/MarcoPorcellato/matryca-plumber/issues/42)

**Exact Contribution Guide Comment:**

> Hi! Scoped concurrency slice — read one existing flock call site first.
>
> **What to fix:** `purge_expired_semantic_cache` in `semantic_cache_router.py` reads/deletes cache files without `cross_process_json_flock`, while `cache_put` writes under flock.
>
> **Steps:**
> 1. Read `cache_put` for the flock pattern.
> 2. Wrap per-file read/delete in `purge_expired_semantic_cache` with `cross_process_json_flock(path)`.
> 3. Extend `tests/test_semantic_cache_router.py`.
>
> **Verify:**
> ```bash
> uv run pytest tests/test_semantic_cache_router.py -q
> make check
> ```

---

## Issue #85 — Deduplicate `BootstrapHarvestStatus` Literal (slice of #62)

**Difficulty:** 2/10 · [GitHub #85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85) · parent [#62](https://github.com/MarcoPorcellato/matryca-plumber/issues/62)

**Exact Contribution Guide Comment:**

> Hi! This is a small DRY cleanup slice from the broader #62 tech-debt issue — a great first PR.
>
> **What to fix:** The type alias `BootstrapHarvestStatus = Literal["regex", "llm", "skipped", "error"]` is copy-pasted in both `src/graph/bootstrap_harvest.py` (line ~47) and `src/agent/maintenance_daemon.py` (line ~321). The harvest module is the canonical source.
>
> **Steps:**
> 1. Open `src/graph/bootstrap_harvest.py` — confirm `BootstrapHarvestStatus` is defined and exported in `__all__`.
> 2. Open `src/agent/maintenance_daemon.py` — remove the local `BootstrapHarvestStatus = Literal[...]` definition.
> 3. Add `from ..graph.bootstrap_harvest import BootstrapHarvestStatus` (adjust relative import to match existing style in that file).
> 4. Ensure no other references to a local Literal remain.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_maintenance_daemon.py tests/test_bootstrap_yield.py -q
> make check
> ```
>
> Please do **not** tackle the other #62 items (fcntl fallback, `matryca_hooks` format dedup) in the same PR — keep this PR focused. Thanks for helping us prep the repo for v2.0!

---

## Issue #56 — [Performance] harvest_page_into_catalog decodes full mmap after successful regex extract

**Difficulty:** 3/10 · [GitHub #56](https://github.com/MarcoPorcellato/matryca-plumber/issues/56)

**Exact Contribution Guide Comment:**

> Hi! Thanks for considering Matryca Plumber — this is a focused performance win with a clear scope.
>
> **What to fix:** In `src/graph/bootstrap_harvest.py`, function `harvest_page_into_catalog` (around lines 217–220) calls `view.decode_utf8()` on the entire mmap view even when the regex extraction path (`extract_catalog_fields_from_mmap`) already succeeded and no LLM branch is needed.
>
> **Steps:**
> 1. Open `src/graph/bootstrap_harvest.py` and read `harvest_page_into_catalog` end-to-end.
> 2. Trace when `content` is actually required — the LLM fallback branch needs full text, but the early `regex` return path may not.
> 3. Defer `view.decode_utf8(errors="replace")` until the code path that needs full page text (e.g. when `extracted is None` and `llm is not None`).
> 4. Keep the `skipped_empty` guard working — you may still need a lightweight emptiness check without decoding the whole file if possible.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_bootstrap_yield.py -q
> make check
> ```
>
> Add a short comment in the PR explaining which branch now avoids the full decode. Happy harvesting!

---

## Issue #53 — [Performance] Phase-2 reads same page twice per cognitive lint cycle

**Difficulty:** 3/10 · [GitHub #53](https://github.com/MarcoPorcellato/matryca-plumber/issues/53)

**Exact Contribution Guide Comment:**

> Hi! Welcome — this issue is a straightforward I/O dedup inside the maintenance daemon.
>
> **What to fix:** In `src/agent/maintenance_daemon.py`, method `_process_llm_cycle_file` reads the same page twice when cognitive lint is active (two separate `read_graph_file_text` calls around lines 2613 and 2642).
>
> **Steps:**
> 1. Open `src/agent/maintenance_daemon.py` and locate `_process_llm_cycle_file`.
> 2. Find both `read_graph_file_text` calls on the same `path` within one invocation.
> 3. Read once into a local variable (e.g. `page_text`) and reuse it for the secondary lint pass.
> 4. Preserve all existing OCC / mtime guard behavior — only deduplicate the read, don't change write semantics.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_maintenance_daemon.py -q
> make check
> ```
>
> One variable, one read — that's the goal. Let us know in the issue thread when you start. Thanks!

---

## Issue #69 — [Performance] Skip cluster-focus injection for single-page cluster groups

**Difficulty:** 3/10 · [GitHub #69](https://github.com/MarcoPorcellato/matryca-plumber/issues/69)

**Exact Contribution Guide Comment:**

> Hi! Thanks for helping improve token efficiency in Phase 2 clustering — this is a well-scoped change.
>
> **What to fix:** In `src/agent/maintenance_daemon.py`, method `run_cycle` injects a `[CLUSTER FOCUS: NEIGHBORHOOD MAP]` prefix via `_begin_cluster_context()` for every multi-page cluster group. For singleton clusters (`len(cluster_paths) == 1`), the neighborhood map duplicates per-page context already in the batch — pure token waste.
>
> **Steps:**
> 1. Open `src/agent/maintenance_daemon.py` and find the `uses_cluster_focus` guard in `run_cycle` (around line 2977).
> 2. Extend the condition so cluster focus is skipped when `len(cluster_paths) == 1`, similar to how `CLUSTER_IDS_WITHOUT_FOCUS` is handled.
> 3. Ensure `reset_history_after` for single-page groups matches the no-focus path (see the `cluster_id in CLUSTER_IDS_WITHOUT_FOCUS` branch).
> 4. Read `_begin_cluster_context` to confirm you understand what gets skipped.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_maintenance_daemon.py -q
> make check
> ```
>
> Consider adding a focused test asserting `_begin_cluster_context` is not called for a one-file cluster. Welcome to the gardener!

---

## Issue #71 — [Tech Debt] Centralize journal page detection in graph layer

**Difficulty:** 4/10 · [GitHub #71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71)

**Exact Contribution Guide Comment:**

> Hi! This is a small architecture hygiene task — perfect if you enjoy tracing helpers across modules.
>
> **What to fix:** Journal detection is split between `is_journal_page_path()` in `src/agent/plumber_modules/_shared.py` (path-based) and `is_journal_page_title()` in `src/graph/alias_index.py` (title/relpath). Phase 2 clustering imports from both, which invites drift.
>
> **Steps:**
> 1. Read `is_journal_page_path()` in `src/agent/plumber_modules/_shared.py` and `is_journal_page_title()` in `src/graph/alias_index.py`.
> 2. Move `is_journal_page_path()` to `src/graph/page_path.py` or `src/graph/alias_index.py` (pick whichever already has the most journal-related helpers).
> 3. Re-export a thin alias from `plumber_modules/_shared.py` for backward compatibility, **or** update call sites surgically (grep for `is_journal_page_path`).
> 4. Add or extend tests in `tests/test_graph_path_hygiene.py` covering path + title parity for a sample `journals/2026_06_10.md` path.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_graph_path_hygiene.py -q
> make check
> ```
>
> Keep the diff surgical — move + re-export, no behavior change. Comment here when you claim it. Glad to have you on board!

---

## Tier E — Expert Audit 2026-06 slices

Triage: [`docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md`](docs/quality/EXPERT_AUDIT_TRIAGE_2026-06.md)

| Issue | Summary | Difficulty |
|-------|---------|------------|
| [#141](https://github.com/MarcoPorcellato/matryca-plumber/issues/141) | `RoutingHint` enum for L1/L2 MCP hints (Repomix audit) | 2/10 |
| [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85) | `BootstrapHarvestStatus` Literal dedup (unchanged good-first) | 2/10 |
| [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90)–[#91](https://github.com/MarcoPorcellato/matryca-plumber/issues/91) | Env parser DRY slices under [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) (+ invalid fallback warning) | 2/10 |

**Verify (#138):**
```bash
uv run pytest tests/test_tui_dashboard.py -q
make check
```

P1 concurrency fixes ([#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132), [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133)) and larger performance items ([#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135), [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136)) are maintainer-led — not good-first unless explicitly tagged.

---

## Tier F — Clean Code & Clean Architecture slices

**SSOT:** [`docs/CLEAN_CODE_ARCHITECTURE.md`](docs/CLEAN_CODE_ARCHITECTURE.md) · **Script:** `bash scripts/populate_gfi_tier_f.sh` (idempotent) · **Label:** `clean-code`

| Issue body | GitHub | Summary | Difficulty |
|------------|--------|---------|------------|
| [`158-link-verification-env-parse.md`](docs/quality/issue-bodies/158-link-verification-env-parse.md) | [#168](https://github.com/MarcoPorcellato/matryca-plumber/issues/168) | `link_verification`: strikes/batch/timeout → `env_parse` | 2/10 |
| [`159-generational-cache-env-parse.md`](docs/quality/issue-bodies/159-generational-cache-env-parse.md) | [#169](https://github.com/MarcoPorcellato/matryca-plumber/issues/169) | `generational_cache`: `MATRYCA_*` → `env_parse` | 2/10 |
| [`160-plumber-config-env-int-delegate.md`](docs/quality/issue-bodies/160-plumber-config-env-int-delegate.md) | [#170](https://github.com/MarcoPorcellato/matryca-plumber/issues/170) | `plumber_config._env_int` → `utils.env_parse.env_int` | 2/10 |
| [`161-graph-boundary-forbid-rag.md`](docs/quality/issue-bodies/161-graph-boundary-forbid-rag.md) | [#171](https://github.com/MarcoPorcellato/matryca-plumber/issues/171) | CI: graph must not import `rag` | 2/10 |
| [`162-concurrency-probe-env-bool.md`](docs/quality/issue-bodies/162-concurrency-probe-env-bool.md) | [#172](https://github.com/MarcoPorcellato/matryca-plumber/issues/172) | `concurrency_probe`: `env_bool` for flock flag | 1/10 |
| [`163-env-parse-clamp-contract-tests.md`](docs/quality/issue-bodies/163-env-parse-clamp-contract-tests.md) | [#173](https://github.com/MarcoPorcellato/matryca-plumber/issues/173) | Parametrized clamp contract tests | 2/10 |

**Parent tracking:** [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) (env parser DRY) · [#141](https://github.com/MarcoPorcellato/matryca-plumber/issues/141) (`RoutingHint` enum — related Clean Code theme).

**Verify (F1):**
```bash
uv run pytest tests/test_link_verification.py tests/test_env_parse.py -q
make check
```

**Verify (F2):**
```bash
uv run pytest tests/test_generational_cache.py tests/test_env_parse.py -q
make check
```

**Verify (F4):**
```bash
uv run pytest tests/test_graph_layer_boundary.py -q
make check
```

---

## Tier G — Complexity slices from the 2026-07-16 deep audit

**SSOT:** [`docs/AUDIT_REPORT_2026-07-16.md`](docs/AUDIT_REPORT_2026-07-16.md) §4 (104 ruff `C901`/`PLR0912`/`PLR0915` findings) · **Label:** `good first issue`, `tech-debt`

Each issue targets one function flagged over the complexity budget, excluding the three god-modules already tracked as split epics (#212–214) and the highest fan-in hubs (too risky for a first PR). Task is a pure extract-method refactor — no behavior change.

| Issue | Function | File |
|-------|----------|------|
| [#220](https://github.com/MarcoPorcellato/matryca-plumber/issues/220) | `load_agent_context` | `src/agent/context_load.py` |
| [#221](https://github.com/MarcoPorcellato/matryca-plumber/issues/221) | `index_page` | `src/agent/daemon_llm_client.py` |
| [#222](https://github.com/MarcoPorcellato/matryca-plumber/issues/222) | `_format_index_section` | `src/agent/daemon_semantic_write.py` |
| [#223](https://github.com/MarcoPorcellato/matryca-plumber/issues/223) | `format_edn_date_pattern` | `src/agent/importers/tana/journal.py` |
| [#224](https://github.com/MarcoPorcellato/matryca-plumber/issues/224) | `_extract_glossary_candidates` | `src/agent/ingestion.py` |
| [#225](https://github.com/MarcoPorcellato/matryca-plumber/issues/225) | `run_cognitive_lint_pipeline` | `src/agent/plumber_modules/__init__.py` |
| [#226](https://github.com/MarcoPorcellato/matryca-plumber/issues/226) | `_upsert_backlink_in_content` | `src/agent/plumber_modules/backlink_backpropagator.py` |
| [#227](https://github.com/MarcoPorcellato/matryca-plumber/issues/227) | `_scan_ssot_duplication` | `src/agent/plumber_modules/marpa_framework.py` |
| [#228](https://github.com/MarcoPorcellato/matryca-plumber/issues/228) | `robot_git_commit` | `src/daemon/git_audit.py` |
| [#229](https://github.com/MarcoPorcellato/matryca-plumber/issues/229) | `_balanced_brackets` | `src/graph/advanced_query_block.py` |
| [#230](https://github.com/MarcoPorcellato/matryca-plumber/issues/230) | `harvest_page_into_catalog` | `src/graph/bootstrap_harvest.py` |
| [#231](https://github.com/MarcoPorcellato/matryca-plumber/issues/231) | `patch_generational_caches_for_paths` | `src/graph/generational_cache.py` |
| [#232](https://github.com/MarcoPorcellato/matryca-plumber/issues/232) | `mapreduce_harvest_page_summary` | `src/graph/hierarchical_summarization.py` |
| [#233](https://github.com/MarcoPorcellato/matryca-plumber/issues/233) | `bfs_hops` | `src/graph/link_tag_hop.py` |
| [#234](https://github.com/MarcoPorcellato/matryca-plumber/issues/234) | `_mutate_block_hygiene_property` | `src/graph/link_verification.py` |
| [#235](https://github.com/MarcoPorcellato/matryca-plumber/issues/235) | `split_logseq_property_list_values` | `src/graph/mldoc_properties.py` |
| [#236](https://github.com/MarcoPorcellato/matryca-plumber/issues/236) | `inject_page_property` | `src/graph/page_properties.py` |
| [#237](https://github.com/MarcoPorcellato/matryca-plumber/issues/237) | `_apply_pattern` | `src/graph/property_line_edit.py` |
| [#238](https://github.com/MarcoPorcellato/matryca-plumber/issues/238) | `_collect_candidates` | `src/graph/split_large_blocks.py` |
| [#239](https://github.com/MarcoPorcellato/matryca-plumber/issues/239) | `lint_unify_logseq_tags` | `src/graph/tag_unify.py` |

All difficulty 3/10. Each issue body carries its own `Verify` block (targeted test file + `ruff check --select C901,PLR0912,PLR0915` + `make check`).

---

## Recently closed (no longer good-first candidates)

| Issue | Shipped in | Summary |
|-------|------------|---------|
| [#44](https://github.com/MarcoPorcellato/matryca-plumber/issues/44) | main (#100, @gaoflow) | Daemon shutdown logs final catalog/state save failures |
| [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)–[#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) | main (#108–#112, @gaoflow) | Tier C observability, OCC, flock, and shutdown tests |
| [#118](https://github.com/MarcoPorcellato/matryca-plumber/issues/118) | main ([#122](https://github.com/MarcoPorcellato/matryca-plumber/pull/122), @blackwolf225; [`b7b9cdf`](https://github.com/MarcoPorcellato/matryca-plumber/commit/b7b9cdf5d8877a069da84ae423414333ef339c88)) | `httpx2` dev dependency silences Starlette deprecation warnings in tests |
| [#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) | v1.9.10 (#38) | Nanosecond OCC tests for link_verification |
| [#67](https://github.com/MarcoPorcellato/matryca-plumber/issues/67) | v1.9.15 | Journal Phase-2 structural settle — no semantic LLM |
| [#68](https://github.com/MarcoPorcellato/matryca-plumber/issues/68) | v1.9.14 | Entity consolidation skips journal/date wikilink pairs |
| [#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) | v1.9.15 | Phase-2 progress denominator excludes `journals/` |
| [#42](https://github.com/MarcoPorcellato/matryca-plumber/issues/42) | v1.11.x | Semantic cache flock — `purge_expired_semantic_cache` + `load_semantic_clusters` |
| [#91](https://github.com/MarcoPorcellato/matryca-plumber/issues/91) | v1.11.2 | `markdown_io` uses `utils.env_parse` |
| [#92](https://github.com/MarcoPorcellato/matryca-plumber/issues/92) | v1.11.x | `test_harvest_skips_catalog_upsert_when_semantic_index_occ_aborts` |
| [#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) | 2026-07-01 pass 3 | `needs_refresh` nanosecond alignment |
| [#113](https://github.com/MarcoPorcellato/matryca-plumber/issues/113) | 2026-07-01 pass 3 | `_count_catalog_summaries` logs on load failure |
| [#97](https://github.com/MarcoPorcellato/matryca-plumber/issues/97) | 2026-07-01 pass 4 | OCC filesystem resolution constraints in `docs/ARCHITECTURE.md` |
| [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90) | v1.11.2 | `link_verification` env_parse slice |
| Triage pass 1 (33 issues) | 2026-07-01 | [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132)–[#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157), [#143](https://github.com/MarcoPorcellato/matryca-plumber/issues/143)–[#152](https://github.com/MarcoPorcellato/matryca-plumber/issues/152), [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57) / [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85) / [#53](https://github.com/MarcoPorcellato/matryca-plumber/issues/53) / [#56](https://github.com/MarcoPorcellato/matryca-plumber/issues/56) / [#69](https://github.com/MarcoPorcellato/matryca-plumber/issues/69) / [#71](https://github.com/MarcoPorcellato/matryca-plumber/issues/71) — see [`ISSUE_TRIAGE_2026-07-01.md`](docs/quality/ISSUE_TRIAGE_2026-07-01.md) |
