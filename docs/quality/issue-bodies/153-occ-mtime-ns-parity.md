---
type: Document
---
## Problem Description

Page-level OCC in `src/graph/markdown_blocks.py` snapshots and compares `st_mtime` as a `float` (`read_file_mtime`, `file_mtime_drifted`).

Master catalog and bootstrap harvest already use `st_mtime_ns` for finer-grained invalidation (`master_catalog.py`, `bootstrap_harvest.py`). On coarse-grained filesystems (FAT32/exFAT) or when two Plumber writers commit in the same wall-clock second with an identical OCC snapshot, mtime-second granularity is a theoretical lost-update edge — mitigated today by `page_rmw_lock` during commit, but not by OCC alone.

Clean Architecture Audit 2026-06 triage: [`docs/quality/CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md`](../CLEAN_ARCH_AUDIT_TRIAGE_2026-06.md).

Content-hash CAS (SHA-256) is explicitly **out of scope** for this slice — tracked under [#17](https://github.com/MarcoPorcellato/matryca-plumber/issues/17) `GraphRepository`.

## Proposed Architectural Solution

1. Add `read_file_mtime_ns` / `occ_snapshot_ns` alongside existing float API (or migrate internally to ns with `math.isclose` parity tests).
2. Thread nanosecond baseline through `atomic_write_bytes_if_unchanged` and daemon/MCP write paths.
3. Regression tests: sub-second drift detection; backward compatibility with existing ledger fields where seconds are stored.

## Estimated Impact

Basso–Medio — tightens OCC on edge filesystems; no API break for MCP/CLI when snapshot is internal.

## Files Involved

- `src/graph/markdown_blocks.py`
- `src/agent/maintenance_daemon.py` (`apply_semantic_page_result`, Phase 2 cycle)
- `src/agent/graph_dispatch.py` (write paths)
- `tests/test_maintenance_daemon.py`, `tests/test_link_verification.py`

---

**Milestone:** v1.9.12 — Code Perfection & Tech Debt · **GitHub:** [#153](https://github.com/MarcoPorcellato/matryca-plumber/issues/153) · **Related:** #17 (content-hash CAS v2) · #38

_Closes when merged with tests green (`make check`) and CHANGELOG updated per `06-auto-changelog.mdc`._
