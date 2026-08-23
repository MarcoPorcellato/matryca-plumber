---
type: Document
---
# Claude Architectural Audit — Triage (2026-06-24)

Staff-level review (Repomix snapshot, June 2026). Cross-reference: [Expert Audit](EXPERT_AUDIT_TRIAGE_2026-06.md), [Repomix](REPOmix_AUDIT_TRIAGE_2026-06.md), [Clean Arch](CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md), v1.9.x perfection audit JSON.

**Status:** triaged 2026-06-24 · verified against current `src/` and open GitHub issues.

---

## Executive scorecard

| Verdict | Count | Meaning |
|---------|-------|---------|
| Already tracked (v1.9.x audit) | 9 | Comment + link — do not duplicate |
| Fixed / obsolete in tree | 2 | Document as closed |
| **New issues filed** | 3 | [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155)–[#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) |
| Partial / hardening | 1 | P1-01 lock registry TOCTOU → #157 |

---

## Finding matrix

### P1 — Critical

| ID | Finding | Code reality | Action | GitHub |
|----|---------|--------------|--------|--------|
| P1-01 | Lock registry eviction bypasses mutual exclusion | [`page_write_lock.py`](../../src/graph/page_write_lock.py) L49–56 evicts only when `not old_lock.locked()`; full registry → `PageLockUnavailableError`. Audit snippet predates `locked()` guard. | **Partial** — optional `acquire(blocking=False)` hardening | [#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) |
| P1-02 | BM25/alias cache: build then `sig_after` → stale corpus + fresh sig | [`generational_cache.py`](../../src/graph/generational_cache.py) L275–277, L359–362 | **Confirmed** — distinct from SQLite-outbox rejection | [#155](https://github.com/MarcoPorcellato/matryca-plumber/issues/155) |
| P1-03 | `bootstrap_harvest` stores second-precision mtime | L207: `st_mtime_ns` already — **fixed** | **Obsolete** for harvest | [#38](https://github.com/MarcoPorcellato/matryca-plumber/issues/38) (`needs_refresh` legacy seconds) |
| P1-04 | `auto_split` child page without `page_rmw_lock` | [`auto_split.py`](../../src/agent/plumber_modules/auto_split.py) L118–129 | **Confirmed** | [#39](https://github.com/MarcoPorcellato/matryca-plumber/issues/39) (Audit #13) |

### P2 — Structural / performance

| ID | Finding | Action | GitHub |
|----|---------|--------|--------|
| P2-01 | `maintenance_daemon.py` god object (~3323 lines) | **Closed** ([#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58)) — six `daemon_*` modules + ~1,280-line orchestrator | [#58](https://github.com/MarcoPorcellato/matryca-plumber/issues/58) (Audit #32) |
| P2-02 | `os.environ` in graph modules | Partial — #57 fixed slices | [#57](https://github.com/MarcoPorcellato/matryca-plumber/issues/57), [#142](https://github.com/MarcoPorcellato/matryca-plumber/issues/142) |
| P2-03 | `compute_topology_metrics` triple vault scan | Tracked | [#50](https://github.com/MarcoPorcellato/matryca-plumber/issues/50) (Audit #24) |
| P2-04 | Full `catalog.save()` per indexed page | Tracked | [#49](https://github.com/MarcoPorcellato/matryca-plumber/issues/49) (Audit #23) |
| P2-05 | 3× daemon state save per LLM cycle | Tracked | [#48](https://github.com/MarcoPorcellato/matryca-plumber/issues/48) (Audit #22) |
| P2-06 | `scan_existing_tana_ids` loads full vault text | **Confirmed** | [#156](https://github.com/MarcoPorcellato/matryca-plumber/issues/156) |

### P3 — Minor

| ID | Finding | Action | GitHub |
|----|---------|--------|--------|
| P3-01 | Shutdown `suppress(Exception)` on final save | **Fixed** — `logger.exception` on `OSError` | [#44](https://github.com/MarcoPorcellato/matryca-plumber/issues/44) closed |
| P3-02 | `@lru_cache` on `_resolved_graph_root_from_env` | **Confirmed** | [#157](https://github.com/MarcoPorcellato/matryca-plumber/issues/157) |
| P3-03 | `_find_tag_clusters` O(n²) | Slice of insights work | [#50](https://github.com/MarcoPorcellato/matryca-plumber/issues/50) |
| P3-04 | Double page read in Phase-2 cognitive lint | Tracked | [#53](https://github.com/MarcoPorcellato/matryca-plumber/issues/53) |

---

## Recommended sprint order (mapped to issues)

1. **#155, #39** — concurrency (generational cache sig, auto_split child lock)
2. **#38** — catalog `needs_refresh` / mtime seconds (related to P1-03 theme)
3. **#50, #156** — performance (topology scan, Tana id pre-scan)
4. **#49, #48** — catalog batch flush + single checkpoint per cycle
5. **#58, #57** — daemon split + config DI
6. **#53, #157** — good-first reads + lock registry hardening

---

## Issue bodies

- [`155-generational-cache-sig-tou.md`](issue-bodies/155-generational-cache-sig-tou.md)
- [`156-tana-id-stream-scan.md`](issue-bodies/156-tana-id-stream-scan.md)
- [`157-lock-registry-acquire-hardening.md`](issue-bodies/157-lock-registry-acquire-hardening.md)

---

## Maintainer notes

- Claude report overlaps heavily with v1.9.x perfection audit — prefer **comment on existing issue** over duplicate.
- P1-02 corrects Clean Arch triage: “SQLite outbox” rejected ≠ “sig_after after build” rejected.
- `bootstrap_harvest` nanosecond mtime shipped; do not re-file P1-03 as harvest bug.
