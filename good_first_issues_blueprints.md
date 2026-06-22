# Good First Issues — Contributor Blueprints

**Updated post-#100 merge (2026-06-22)** — #44 shipped via [#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100) (thanks @gaoflow). Tier C opened [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)–[#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105); [#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) promoted to `good first issue`.

**Active good-first candidates:** #38, #43, #52, #53, #56, #69, #71, #85, [#90](https://github.com/MarcoPorcellato/matryca-plumber/issues/90)–[#92](https://github.com/MarcoPorcellato/matryca-plumber/issues/92), [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101)–[#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105). Welcome comments are on each GitHub thread.

**Before opening a PR:** read [`CONTRIBUTING.md`](CONTRIBUTING.md), run `make check`, and reference the issue number in your PR title (e.g. `fix(daemon): log SIG handler shutdown telemetry (#101)`).

If a maintainer closes an overarching audit issue while your PR is open, **rebase on `main`** and update tests/docs to match the new architecture (see CONTRIBUTING § Pull request workflow).

---

## Shipped — Issue #44 (daemon shutdown save logging)

**Difficulty:** 2/10 · Closed via [#100](https://github.com/MarcoPorcellato/matryca-plumber/pull/100) · contributor @gaoflow

**Summary:** `_finalize_graceful_shutdown` now uses `try/except OSError` + `logger.exception` for final catalog and daemon state saves instead of `contextlib.suppress(Exception)`.

**Regression test:** `test_graceful_shutdown_logs_final_save_errors` in `tests/test_maintenance_daemon.py`.

**Follow-up slices:** [#101](https://github.com/MarcoPorcellato/matryca-plumber/issues/101) (SIG handler token_logger), [#105](https://github.com/MarcoPorcellato/matryca-plumber/issues/105) (cleanup-after-failure test).

---

## Tier C — Post-#100 backlog (#101–#105)

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

## Recently closed (no longer good-first candidates)

| Issue | Shipped in | Summary |
|-------|------------|---------|
| [#44](https://github.com/MarcoPorcellato/matryca-plumber/issues/44) | main (#100, @gaoflow) | Daemon shutdown logs final catalog/state save failures |
| [#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) | v1.9.10 (#38) | Nanosecond OCC tests for link_verification |
| [#67](https://github.com/MarcoPorcellato/matryca-plumber/issues/67) | v1.9.15 | Journal Phase-2 structural settle — no semantic LLM |
| [#68](https://github.com/MarcoPorcellato/matryca-plumber/issues/68) | v1.9.14 | Entity consolidation skips journal/date wikilink pairs |
| [#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) | v1.9.15 | Phase-2 progress denominator excludes `journals/` |
| [#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) prod fix | v1.9.10 (#38) | `file_mtime_drifted()` in link_verification — issue retained for **tests only** |
