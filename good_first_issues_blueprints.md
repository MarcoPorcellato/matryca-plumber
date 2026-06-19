# Good First Issues — Contributor Blueprints

**Updated v1.10.5 backlog hygiene** — five open issues tagged [`good first issue`](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22good+first+issue%22) + [`help wanted`](https://github.com/MarcoPorcellato/matryca-plumber/issues?q=is%3Aopen+label%3A%22help+wanted%22) on GitHub (#53, #56, #69, #71, [#85](https://github.com/MarcoPorcellato/matryca-plumber/issues/85)). Welcome comments are already posted on each issue thread.

**Shipped (remove from backlog):** [#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) — `file_mtime_drifted()` in link verification (bundled with nanosecond OCC #38).

**Before opening a PR:** read [`CONTRIBUTING.md`](CONTRIBUTING.md), run `make check`, and reference the issue number in your PR title (e.g. `perf(daemon): dedup page read in cognitive lint (#53)`).

---

## Issue #45 — [Bug] link_verification compares mtime with `!=` instead of `file_mtime_drifted` — SHIPPED

**Status:** Fixed in nanosecond OCC parity ([#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38)) — `link_verification.py` now calls `file_mtime_drifted()` inside the `page_rmw_lock` block. Close [#45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45) when the PR merges.

<details>
<summary>Original contributor guide (archived)</summary>

**Difficulty:** 2/10 · [GitHub #45](https://github.com/MarcoPorcellato/matryca-plumber/issues/45)

**Exact Contribution Guide Comment:**

> Hi! Thanks for your interest in contributing to Matryca Plumber — we'd love your help on this one.
>
> **What to fix:** Inside `src/graph/link_verification.py`, the function that verifies a block before rewriting it compares file modification time with a raw `!=` check (`read_file_mtime(page_path) != baseline_mtime` around line 560). The rest of the codebase uses `file_mtime_drifted()` from `src/graph/markdown_blocks.py` to avoid float representation edge cases.
>
> **Steps:**
> 1. Open `src/graph/link_verification.py` and locate the `page_rmw_lock` block where `read_file_mtime(page_path) != baseline_mtime` appears.
> 2. Import `file_mtime_drifted` from `src/graph/markdown_blocks.py` (or reuse an existing import if already present).
> 3. Replace the `!=` comparison with `file_mtime_drifted(page_path, baseline_mtime)`.
> 4. Skim `file_mtime_drifted` in `markdown_blocks.py` to confirm the guard semantics match other OCC call sites.
>
> **Verify your fix:**
> ```bash
> uv run pytest tests/test_link_verification.py -q
> make check
> ```
>
> A one-line surgical change is perfect — no drive-by refactors needed. Comment here when you pick this up so we don't duplicate effort. Welcome aboard!

</details>

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
| [#67](https://github.com/MarcoPorcellato/matryca-plumber/issues/67) | v1.9.15 | Journal Phase-2 structural settle — no semantic LLM |
| [#68](https://github.com/MarcoPorcellato/matryca-plumber/issues/68) | v1.9.14 | Entity consolidation skips journal/date wikilink pairs |
| [#70](https://github.com/MarcoPorcellato/matryca-plumber/issues/70) | v1.9.15 | Phase-2 progress denominator excludes `journals/` |
