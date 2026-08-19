---
type: Document
---
## Problem Description

`get_cached_bm25_corpus` and `cached_build_alias_index` in `src/graph/generational_cache.py` build the corpus/index, then capture `_signature(...)` **after** the build (`sig_after`), and store `(sig_after, artifact)`.

If a concurrent writer mutates a page during the build (while the generational-cache `_lock` is held for BM25, page writes still proceed via `page_rmw_lock`), the post-build signature can reflect new mtimes while the corpus/index reflects pre-write content. The next lookup can cache-hit on a matching signature with stale text — incorrect BM25 rankings until an unrelated mtime change forces rebuild.

Same pattern on alias index path (L275–277).

Claude Architectural Audit 2026-06-24: [`docs/quality/CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md`](../CLAUDE_ARCH_AUDIT_TRIAGE_2026-06-24.md).

## Proposed Architectural Solution

1. Capture `sig_before = _signature(paths, root)` **before** `build_*`.
2. Build corpus/index.
3. Capture `sig_after` after build; store only when `sig_before == sig_after`, else discard and retry (or return uncached build for this call).
4. Regression test: mock mtime bump mid-build → next call must not serve stale corpus on cache hit.

## Estimated Impact

Alto — silent wrong RAG/BM25 results on concurrent daemon + human co-editing; one-day fix, no new dependencies.

## Files Involved

- `src/graph/generational_cache.py`
- `tests/test_generational_cache.py` (create or extend)
- `tests/test_local_query.py` (BM25 integration if present)

---

**Claude Audit 2026-06-24** · **GitHub:** [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) · **Milestone:** v1.9.10 — Concurrency & Data Integrity

_Closes when merged with tests green (`make check`) and CHANGELOG updated._
