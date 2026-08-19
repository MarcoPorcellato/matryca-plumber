---
type: Document
---
# Phase 8 — Ironclad Shield (checklist)

Actionable checklist for global fence scanning, transactional writes, and generational caching.

- [x] **Global fence state machine** — `src/graph/global_fence_scanner.py` with `compute_page_protected_line_indices(file_content: str) -> set[int]` (Markdown ``` fences, HTML `<!-- … -->`, Logseq `#+BEGIN_QUERY` … `#+END_QUERY`).
- [x] **Integrate fence rejection** — `property_line_edit.py`, `tag_unify.py`, `unlinked_mentions.py`; block-level mutators reject spans overlapping protected lines (`split_large_blocks.py`, `reparent_blocks.py`).
- [x] **Transactional atomic file swap** — `atomic_write_bytes` / `atomic_write_file` in `src/graph/markdown_blocks.py` (temp in target dir, flush + `os.fsync`, `os.replace`).
- [x] **Upgrade mutating tools** — Replace ad-hoc temp writes with `atomic_write_bytes` in `property_line_edit.py`, `tag_unify.py`, `reparent_blocks.py`, `split_large_blocks.py`, `journal_task_scan.py` (and aligned helpers in `flashcards.py`, `moc_page.py`).
- [x] **Link registry atomic save (v1.10.0 — #41)** — `_save_registry_unlocked` in `link_verification.py` uses `atomic_write_bytes` under existing `cross_process_json_flock`.
- [x] **Master catalog flock + merge-on-save (v1.10.0 — #35, #36)** — `load_master_catalog` reads under flock; `MasterCatalog.save()` merge-on-save by `last_mtime`.
- [x] **Harvest catalog/page parity (v1.10.0 — #37)** — Bootstrap skips catalog upsert when semantic index append OCC-aborts.
- [x] **Flock sidecar permissions (v1.10.3)** — `json_flock`, page RMW locks, and daemon process lock files created as `0o600` (CodeQL `py/overly-permissive-file`).
- [x] **Generational mtime cache** — `src/graph/generational_cache.py` for `build_alias_index` and BM25/keyword corpus in `local_query.py`; MCP uses cached alias build.
- [x] **Tests** — Fence edges, atomic swap behavior, cache hit/invalidate; `make check` green (90+ tests).
