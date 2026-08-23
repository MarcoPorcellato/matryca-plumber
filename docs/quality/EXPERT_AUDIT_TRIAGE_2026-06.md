---
type: Document
---
# Expert Architectural Audit — Triage (2026-06)

Cross-reference between the **Expert Architectural Audit** (external review) and Matryca Plumber's existing backlog: v1.9.x perfection audit (#01–#38), GitHub issues, ROADMAP, openspec, CHANGELOG.

**Status:** triaged 2026-06-23 · GitHub issues **[#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132)–[#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139)**.

---

## Executive scorecard

| Verdict | Count | Meaning |
|---------|-------|---------|
| Already fixed | 4 | No new issue; document as closed |
| Already tracked | 5 | Existing issue/openspec; extend, don't duplicate |
| Confirmed, new | 7 | GitHub issues created from this triage |
| Partial / audit error | 3 | Corrected framing in docs |

---

## Finding matrix

### P1 — Critical

| Audit finding | Code reality | Existing backlog | Action | GitHub |
|---------------|--------------|------------------|--------|--------|
| Dependency cycles (`graph/` → `daemon/`) | `link_verification` / `master_catalog` **clean**; real coupling: `markdown_blocks` → `post_write_hooks`, `ast_cache`, `load_daemon_state` | Audit #32, #33; Epic #17, #20 | layer inversion | [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) |
| `alias_index` ↔ `generational_cache` cycle | **Fixed** v1.11.0 — injection + `is_journal_page_title_in_index` | CHANGELOG Unreleased | Closed — no issue | — |
| `lock_backoff` overwrites `processed` | **Confirmed** — `_record_page_lock_backoff` ignores prior status | lock-before-LLM shipped; no downgrade bug tracked | bug fix | [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132) |
| `_resolve_write_parent_target` TOCTOU | **Confirmed** — resolve/write split threads | agent-ax-robustness (input only); #34 hub OCC closed | bug fix | [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133) |
| Tana full node materialization | **Confirmed** — `load_tana_nodes_by_id` O(n) dict | openspec says streaming parse only | streaming builder | [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) |
| Journal format cache stale | **Audit error** — no cache; re-reads `config.edn` every call | tana-import spec | Doc clarify only | — |

### P2 — Structural / debt

| Audit finding | Code reality | Existing backlog | Action | GitHub |
|---------------|--------------|------------------|--------|--------|
| Generational cache unbounded multi-vault | **Confirmed** — no LRU across graph roots | page-lock LRU, semantic cache LRU documented | LRU cap | [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) |
| Phase 2 denominator drift | **Partial** — #70 fixed journals; live total refresh every 10 cycles still regresses % | #70 closed | UX fix | [#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137) |
| TUI state over-fetch | **Confirmed** — double `load_daemon_state` on success | #102 logging; #125–#127 observability slices | dedup load | [#138](https://github.com/MarcoPorcellato/matryca-plumber/issues/138) |
| Tana idempotency no content check | **By design v1** — openspec contract | tana-import.md | v2 `--merge` | [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) |

### P3 — Minor / refactor

| Audit finding | Existing backlog | Action |
|---------------|------------------|--------|
| NoRedirect duplication | Audit #36 — **fixed** | Closed |
| `_env_bool` / `_env_int` ×8 | **#57**, slices **#90–#91** (audit #31) | Comment on #57: warn on invalid fallback |
| `BootstrapHarvestStatus` dup | **#85** (audit #36) | No new issue |
| Silent env fallback | Not tracked | Slice of **#57** (comment only) |

### v2.0 Ports & Adapters

Maps to existing north star — **do not duplicate epic:**

- [Epic #20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) Shadow DB & Safe-Sync
- [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) GraphRepository
- [Discussion #19](https://github.com/MarcoPorcellato/matryca-plumber/discussions/19)

Target layout (`domain/` / `adapters/` / `orchestration/`) documented in ROADMAP as aspirational, not immediate refactor.

**Related (Repomix audit):** [`REPOmix_AUDIT_TRIAGE_2026-06.md`](REPOmix_AUDIT_TRIAGE_2026-06.md) · [#140](https://github.com/MarcoPorcellato/matryca-plumber/issues/140)–[#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142)

**Related (Clean Architecture audit):** [`CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md) · [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153)–[#154](https://github.com/MarcoPorcellato/matryca-plumber/issues/154)

**Related (Claude Architectural audit):** [`CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md) · [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155)–[#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157)

---

## GitHub issues from this triage

| GitHub | Local body | Milestone |
|--------|------------|-----------|
| [#132](https://github.com/MarcoPorcellato/matryca-plumber/issues/132) | `130-lock-backoff-downgrades-processed.md` | v1.9.10 — Concurrency & Data Integrity |
| [#133](https://github.com/MarcoPorcellato/matryca-plumber/issues/133) | `131-graph-dispatch-resolve-write-toctou.md` | v1.9.10 — Concurrency & Data Integrity |
| [#134](https://github.com/MarcoPorcellato/matryca-plumber/issues/134) | `132-graph-daemon-post-write-inversion.md` | v1.9.12 — Code Perfection & Tech Debt |
| [#135](https://github.com/MarcoPorcellato/matryca-plumber/issues/135) | `133-tana-streaming-graph-builder.md` | v1.9.11 — Performance & I/O |
| [#136](https://github.com/MarcoPorcellato/matryca-plumber/issues/136) | `134-generational-cache-lru-cap.md` | v1.9.11 — Performance & I/O |
| [#137](https://github.com/MarcoPorcellato/matryca-plumber/issues/137) | `135-phase2-progress-denominator-drift.md` | v1.9.11 — Performance & I/O |
| [#138](https://github.com/MarcoPorcellato/matryca-plumber/issues/138) | `136-tui-daemon-state-dedup-load.md` | v1.9.12 — Code Perfection & Tech Debt |
| [#139](https://github.com/MarcoPorcellato/matryca-plumber/issues/139) | `137-tana-content-aware-reimport-v2.md` | v2.0.0 — Shadow DB & Safe-Sync Architecture |

---

## Issue bodies

Stored under [`docs/quality/issue-bodies/`](issue-bodies/) with numeric prefix matching this triage.

---

## Maintainer notes

- Expert audit overstated `link_verification` / `master_catalog` daemon imports — verify claims against `rg 'from ..daemon'` before opening layer-boundary issues.
- Journal format: problem is repeated I/O, not stale cache — optional future mtime-based cache is a performance tweak, not the audit's stated bug.
- Tana `tana-id` skip is v1 contract; document limits, don't relabel as regression.
