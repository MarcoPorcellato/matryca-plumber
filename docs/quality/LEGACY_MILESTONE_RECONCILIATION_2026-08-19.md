---
type: Audit
title: Legacy milestone reconciliation
description: Current-source disposition plan for the remaining open issues in the pre-v2 performance and technical-debt milestones.
resource: docs/quality/LEGACY_MILESTONE_RECONCILIATION_2026-08-19.md
tags: [quality, governance, github, milestones, issues]
last_verified: 2026-08-19
stale_after: 2026-09-18
status: draft
classification: active
owner: quality
authority: github-reconciliation
---

# Legacy milestone reconciliation

This document records the source review, disposition decision, and completed
remote reconciliation for the two pre-v2 milestones that remained open after
the v2.0.0 stable release. The original review is retained as provenance; the
application record below is the authority for what was changed. Refresh the
GitHub API state before any later amendment.

## Evidence boundary

- **Initial remote source:** public GitHub REST responses read on 2026-08-19
  without authentication; no mutation was made during that initial audit.
- **Application evidence:** authenticated GitHub CLI access was restored, the
  seven open issues and both milestones were revalidated, the documented
  milestone moves were applied, and milestones #7 and #8 were rechecked with
  zero open issues before closure.
- **Source comparison:** local delivery branch from
  `origin/main@2724f7504d943da91e2f4e6a6309cac4d0c9fb30`; a source match does
  not prove a hosted result or a completed issue.
- **Decision rule:** an issue is closed only when its stated acceptance evidence
  is current. A changed implementation detail is not a reason to silently
  close a historical audit item.

## Current milestone state

| Milestone | Open | Closed | Decision |
| --- | ---: | ---: | --- |
| [#7 — v1.9.11 Performance & I/O](https://github.com/MarcoPorcellato/matryca-plumber/milestone/7) | 0 | 16 | Closed at 2026-08-19T20:20:57Z after the four remaining issues were moved. |
| [#8 — v1.9.12 Code Perfection & Tech Debt](https://github.com/MarcoPorcellato/matryca-plumber/milestone/8) | 0 | 38 | Closed at 2026-08-19T20:21:19Z after the three remaining issues were moved. |

The milestone names describe work that was intended as a v2 prerequisite. They
must not remain active merely as a historical bucket after their remaining work
is explicitly re-sequenced.

## Issue-by-issue disposition

| Issue | Current-source observation | Proposed disposition | Proposed target |
| --- | --- | --- | --- |
| [#47](https://github.com/MarcoPorcellato/matryca-plumber/issues/47) | `load_master_catalog()` still calls `catalog.rebuild_alias_index()` after every load. | Keep open; re-estimate with a representative catalog and specify an invalidation-safe cache boundary. | v2.2.0 — Hybrid Recall & Memory Curation |
| [#48](https://github.com/MarcoPorcellato/matryca-plumber/issues/48) | The daemon now has heartbeat/dirty-state helpers, but the original per-Phase-2 persistence claim has not been remeasured against current cycle behavior. | Keep open; replace the stale line-level claim with an exact current persistence-count and recovery acceptance test. | v2.1.0 — Memory & Logseq DB Safe-Sync |
| [#49](https://github.com/MarcoPorcellato/matryca-plumber/issues/49) | `_sync_catalog_after_page_write()` still loads, upserts, and saves the catalog for each page write. | Keep open; profile and design a batch boundary that preserves immediate consistency, locking, and crash recovery. | v2.2.0 — Hybrid Recall & Memory Curation |
| [#54](https://github.com/MarcoPorcellato/matryca-plumber/issues/54) | `patch_backlink_index_for_paths()` still invalidates the cache and removes the disk index for a later full rebuild. | Keep open; define an incremental patch contract with parity and malformed-input cases before implementation. | v2.2.0 — Hybrid Recall & Memory Curation |
| [#61](https://github.com/MarcoPorcellato/matryca-plumber/issues/61) | The named property-edit functions remain substantial mutation paths; the old cyclomatic numbers have not been remeasured. | Keep open; refresh the complexity measurement and split only after an impact review preserves OCC, protected-region, and atomic-write behavior. | v2.1.0 — Memory & Logseq DB Safe-Sync |
| [#63](https://github.com/MarcoPorcellato/matryca-plumber/issues/63) | A private parser import remains, now `_insertion_line_after_node` from `agent_writer`. | Keep open; update the issue's stale symbol reference, then require a public parser seam or a reviewed local replacement with compatibility tests. | v2.1.0 — Memory & Logseq DB Safe-Sync |
| [#73](https://github.com/MarcoPorcellato/matryca-plumber/issues/73) | `tests/slow/test_daemon_memory_soak.py` now provides a bounded 200-page bootstrap memory check, but not the stated sustained daemon/load qualification. | Keep open; narrow the claim to a staged daemon-soak programme with resource admission, bounded fixtures, trend receipts, and no default-CI inflation. | v2.1.0 — Memory & Logseq DB Safe-Sync |

## Completed remote application record

1. Authenticated GitHub CLI access was restored and the two milestones plus all
   seven issues were re-fetched immediately before mutation.
2. Public re-sequencing notes preserved the stale historical context of #63 and
   #73 without altering the issue acceptance scope.
3. Issues #47, #49, and #54 were moved to v2.2.0; #48, #61, #63, and #73 were
   moved to v2.1.0. No issue was closed and historical labels were retained.
4. Both legacy milestones were re-fetched with zero open issues and closed at
   the timestamps recorded in the table above.
5. The authoritative execution ledger records this result and the remaining
   contributor-path exit gate. Future changes require a new live revalidation.

Do not create a new maintenance milestone merely to avoid a decision. The
proposed v2.1/v2.2 targets already express the dependency order. Do not close an
issue because its original milestone became historical.
