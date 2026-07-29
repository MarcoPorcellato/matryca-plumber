# Shadow DB: per-page quarantine for over-budget page parses

## Problem Description

One Logseq page whose parse exceeds the page-parse budget aborts the entire Shadow DB
rebuild, leaving the graph permanently in Markdown/BM25 fallback. On a measured
daily-use vault copy, **25 of 3,378 Markdown files (0.74%)** exceed the 15-second
default, so the opt-in Shadow DB delivers **no acceleration at all** on that corpus —
while 99.26% parse in under one second.

> **Population note (added 2026-07-28).** The 3,378 figure counts every Markdown file
> under the vault root. The cache indexes the graph — `pages/` and `journals/`, 1,014
> pages — of which **3** exceed the budget; the other 22 over-budget files are Logseq
> version history and backups the cache never reads. Either number supports the case
> above (one over-budget page is enough to abort the rebuild), but 3 is the count a user
> sees parked. Reconciliation: `docs/quality/SHADOW_DB_SOAK_24H_EVIDENCE_2026-07-28.md`.

Full measurement, external calibration, and the TRIZ analysis behind the proposed design:
[`../SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md`](../SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md).

Key measured facts:

- Parse cost is **bimodal**: 3,322 pages under 1 s, 31 between 1–5 s, **none between 5 s
  and 40 s**, 25 between 41.65 s and 58.33 s.
- **0.74% of pages consume 90.3%** of total parse time (20.4 min of 22.6 min).
- Size does not predict cost: the largest page in the corpus (650,106 B) parses in
  **0.54 s**, while a 336,263 B page takes ~58 s.
- No official Logseq documentation defines a maximum page size, block count, or nesting
  depth. Real pages of 1,600–2,700 blocks are reported in the Logseq tracker
  ([logseq#5132](https://github.com/logseq/logseq/issues/5132),
  [logseq#8137](https://github.com/logseq/logseq/issues/8137)).

Because no documented upper bound exists, **no fixed timeout can be correct**. Raising
`MATRYCA_PAGE_PARSE_TIMEOUT_S` moves the threshold without removing the failure class,
and costs 22.6 min per full rebuild.

## Root Cause

- `src/graph/bounded_page_parse.py` — default budget 15 s (`_DEFAULT_TIMEOUT_S`).
- `src/shadow/sync.py` `sync_page_into_connection` — raises `ShadowPageParseError` on a
  non-`ok` parse.
- `src/shadow/bootstrap.py` `rebuild_shadow_from_graph` — single `BEGIN IMMEDIATE` over
  all pages; the raise rolls back the whole rebuild.
- `src/shadow/health.py` — `READY` requires
  `indexed_page_count == source_page_count == actual_page_count`, so **skipping a page is
  not representable**: it degrades health to `STALE`, which is also total fallback.

A bare `try/except` around the sync call is explicitly rejected: it would yield a
silently incomplete cache reporting itself healthy, converting a safe loud failure into
an unsafe silent one.

## Architectural Solution

Explicit quarantine with per-page degradation:

1. **Additive schema** — per-row state in `pages` (`indexed` | `quarantined`), a
   content-free `quarantine_reason` (`timeout` | `parse_error`), and an attempt counter.
   Default reproduces current behaviour. An existing `2.0.0b1` database must stay
   readable.
2. **Health invariant** — `indexed + quarantined == source == actual`. A graph with
   quarantined pages stays `READY` and exposes `quarantined_page_count`.
3. **Per-page routing** — reads for a quarantined page use the existing Markdown/AST
   path. A subtree query on a quarantined block must answer *"not in shadow"*, never
   *"empty"*.
4. **Two budgets** — interactive budget stays at `MATRYCA_PAGE_PARSE_TIMEOUT_S`; a larger
   background budget drives a low-priority rehabilitation pass, retried on `mtime` change
   with backoff.
5. **Structural preflight** *(deferred, not required for correctness)* — pre-classify by
   nesting depth and reference density. Must **not** key on byte or line count.

Expected effect on the measured corpus: full rebuild **22.6 min → ~2.2 min**, and 3,353
of 3,378 pages gain accelerated reads instead of none.

## Risk and Implementation Constraints

A code audit returned **HIGH or CRITICAL** on every load-bearing symbol, with exact
call-graph edges:

| Symbol | Risk | Impacted | Processes |
|---|---|---|---|
| `rebuild_shadow_from_graph` | **CRITICAL** | 15 | 7 |
| `shadow_meta_matches_page_rows` | HIGH | 13 | 4 |
| `resolve_shadow_health` | HIGH | 12 | 4 |
| `sync_page_into_connection` | HIGH | 10 | 4 |

`rebuild_shadow_from_graph` reaches `run_forever`, `start_daemon_foreground`,
`run_plumber_cluster`, and `run_plumber_audit`: a defect there prevents daemon startup
rather than degrading an opt-in feature. There is no low-risk variant of this change.

Required constraints:

- [ ] Schema changes strictly additive; existing `2.0.0b1` databases remain readable.
- [ ] `shadow_meta_matches_page_rows` accepts the new count as an optional parameter
      defaulting to 0; **existing tests pass unmodified**.
- [ ] Quarantine behind its own flag nested inside `MATRYCA_SHADOW_DB_ENABLED`; default
      path unchanged.
- [ ] `rebuild_shadow_from_graph` modified last, only after health and sync are green.
- [ ] Full change-scope audit before each commit.
- [ ] Real soak after the change — a two-hour soak on a daemon-core modification is
      weaker evidence than the current baseline.

## Acceptance Criteria

- [ ] A graph containing over-budget pages reaches health `ready` with the rest indexed.
- [ ] `quarantined_page_count` is exposed in the state API; the count is content-free.
- [ ] Reads for a quarantined page return correct results via Markdown fallback; subtree
      queries distinguish *not in shadow* from *empty*.
- [ ] Quarantined pages are retried automatically when their source changes.
- [ ] Flag-off behaviour is byte-for-byte identical to `v2.0.0-beta.1`.
- [ ] Logseq Markdown remains unmodified throughout.

## Files Involved

- `src/shadow/bootstrap.py` — rebuild loop and transaction boundary
- `src/shadow/sync.py` — per-page sync and raise site
- `src/shadow/health.py` — health invariant and meta validation
- `src/shadow/schema.py` — additive schema
- `src/agent/shadow_graph_repository.py` — per-page read routing
- `src/graph/bounded_page_parse.py` — budget selection (interactive vs background)

## Notes

Not a `v2.0.0-beta.1` blocker: the flag is opt-in and default-off, and the failure mode
is safe. It **is** a blocker for enabling Shadow DB by default, and for any claim that
the read cache accelerates real-world graphs.
