# Shadow DB page-parse budget — measurement, contradiction, and quarantine design

_Recorded 2026-07-27, during `v2.0.0-beta.1` release-candidate preparation._

This document records a design defect found in the opt-in Shadow DB read cache, the
measurements that characterise it, the TRIZ analysis used to resolve it, and the design
that follows. It is written to be reproducible and to be read by future maintainers and
by AI agents operating on this repository.

The defect is **not fixed** in `v2.0.0-beta.1`. This document is the specification for
the fix and the honest statement of the limitation until then.

---

## 1. Summary

A single Logseq page whose parse exceeds the page-parse budget aborts the **entire**
Shadow DB rebuild. The graph then never reaches health `ready`, and every read falls
back to Markdown/BM25 permanently.

On the maintainer's daily-use vault copy, **25 of 3,378 pages (0.74%)** exceed the
15-second default budget. The Shadow DB therefore delivers **no benefit at all** on that
corpus under default settings, despite 99.26% of pages parsing in under one second.

The failure is **safe** — Markdown remains authoritative, nothing is corrupted, the
daemon still starts — but it is **silent**, surfacing only as a `WARNING` log line.

---

## 2. Evidence

### 2.1 Method

Every Markdown page in a sanitized daily-use vault copy was parsed once through the
product's own bounded page parser (`src/graph/bounded_page_parse.py`,
`parse_page_text_bounded`, `mode="stack"`) with a deliberately generous 115-second
budget, so that the **true** parse cost of each page could be observed rather than
truncated at the default deadline.

Environment: candidate wheel `2.0.0b1`, CPython 3.12.13, macOS arm64, installed in an
isolated virtual environment outside the checkout. Per repository privacy policy, page
titles, vault paths, block UUIDs, and content hashes are deliberately excluded; only
aggregate, content-free measurements are recorded here.

### 2.2 Distribution of parse cost

| Parse time | Pages |
|---|---|
| < 1 s | 3,322 |
| 1–5 s | 31 |
| 5–15 s | **0** |
| 15–40 s | **0** |
| 40–60 s | 25 |
| Total | 3,378 |

No page in the corpus takes between 5 and 40 seconds. The population is **strictly
bimodal**, separated by a 35-second empty band.

- Pages over budget: **25** (0.74%), of **19 distinct contents** (6 are duplicate copies).
- Over-budget range: **41.65 s – 58.33 s**. None failed to complete within 115 s.
- 99th percentile across all pages: **3.06 s**.

### 2.3 Cost concentration

| | Time | Share |
|---|---|---|
| Full-corpus parse | 22.6 min | 100% |
| Attributable to the 25 over-budget pages | 20.4 min | **90.3%** |
| Attributable to the other 3,353 pages | 2.2 min | 9.7% |

**0.74% of pages consume 90.3% of total parse time.**

### 2.4 Size does not predict cost

| | Bytes | Lines | Parse time |
|---|---|---|---|
| Largest over-budget page | 336,263 | 3,495 | ~58 s |
| Largest under-budget page | 650,106 | 6,748 | **0.54 s** |
| Median page in corpus | 3,638 | — | < 1 s |

The largest page in the corpus is **1.9× the bytes** of the worst over-budget page and
parses **~108× faster**. Cost is driven by structure — nesting depth, block-reference
density — not by volume. Any policy keyed on file size or line count is therefore
invalid.

### 2.5 External calibration

No official Logseq documentation specifies a maximum page size, block count, or nesting
depth. The only documented related limit is `:block/content-max-length` in `config.edn`,
which is per-block and user-configurable.

Real-world cases reported in the Logseq issue tracker and forum reach **1,600–2,700
blocks in a single page**, with performance issues still open:

- [logseq/logseq#5132](https://github.com/logseq/logseq/issues/5132) — 2,700+ blocks in one page
- [logseq/logseq#8137](https://github.com/logseq/logseq/issues/8137) — "massive pages", open
- [discuss.logseq.com/t/4442](https://discuss.logseq.com/t/slow-performance-issues-with-large-page-bible-import-from-roam/4442) — ~1,600 blocks, deep nesting plus block references
- [discuss.logseq.com/t/21256](https://discuss.logseq.com/t/logseq-unusable-for-long-form-pages/21256) — long-form pages reported unusable

Those reports describe **Logseq's own UI responsiveness**, not this project's parser.
They are cited as evidence of *how large real pages get*, not as parse-time measurements.
Journal pages accumulating `LOGBOOK`/`CLOCK` entries
([logseq/logseq#5689](https://github.com/logseq/logseq/issues/5689)) grow this way over
time without any deliberate user action.

**The absence of a documented upper bound is the load-bearing finding**: no fixed timeout
can be correct, because no maximum page complexity exists to calibrate against.

---

## 3. Root cause

Three code facts combine into the defect.

1. **`src/graph/bounded_page_parse.py`** — default budget `_DEFAULT_TIMEOUT_S = 15.0`,
   clamped to 2–120 s via `MATRYCA_PAGE_PARSE_TIMEOUT_S`.
2. **`src/shadow/sync.py`, `sync_page_into_connection`** — on a non-`ok` parse result it
   raises `ShadowPageParseError`.
3. **`src/shadow/bootstrap.py`, `rebuild_shadow_from_graph`** — iterates every page
   inside a single `BEGIN IMMEDIATE` transaction. The raise propagates, the transaction
   rolls back, the rebuild error is recorded, and **no page is indexed**.

`ensure_shadow_runtime_at_startup` then catches `ShadowPageParseError` and logs a
warning, which is why the daemon still starts and nothing is corrupted.

The reason this cannot be fixed by simply skipping the page is
**`src/shadow/health.py`**. `READY` requires:

```
indexed_page_count == source_page_count == actual_page_count
```

Skipping one page makes `indexed < source`, so health degrades to `STALE` — which is
also a total fallback. **In the current data model there is no way to express "this page
is deliberately absent and the cache is still sound."** That missing concept, not the
timeout value, is the defect.

### 3.1 Why raising the timeout is the wrong fix

Setting the budget to 90 s does index the 25 pages, at a cost of **22.6 minutes per full
rebuild**, of which 20.4 minutes are spent on 0.74% of the corpus. It also does not
remove the failure class — it moves the threshold, on a distribution with no documented
upper bound. The next user with a heavier page is in exactly the same position.

### 3.2 Why a bare `try/except` is the wrong fix

Wrapping `sync_page_into_connection` in an exception handler and continuing would produce
a Shadow DB that is **silently incomplete while reporting itself healthy**. Reads would
return missing results with no signal. That converts a safe, loud failure into an unsafe,
silent one — strictly worse than the present behaviour.

---

## 4. TRIZ analysis

### 4.1 The contradiction

**Physical contradiction:**

> The rebuild **must** be complete — otherwise reads are silently incorrect — and **must
> not** be complete — otherwise one pathological page denies the service to all others.

**Technical contradiction:** improving *Reliability* (a cache that is provably whole)
degrades *Loss of Time* and *Loss of Substance* (the whole cache is forfeited, and 22.6
minutes are spent, because of 0.74% of the input).

### 4.2 Separation principle

The contradiction is resolved by **separation in time and in scale**:

- *In scale* — completeness is asserted over the **graph**, atomicity is enforced per
  **page**. The two requirements stop competing once they apply to different units.
- *In time* — the strict budget applies to the **interactive** path; a generous budget
  applies to a **background** rehabilitation path. The same page can be both "too
  expensive now" and "affordable later".

### 4.3 Inventive principles applied

| # | Principle | Application here |
|---|---|---|
| 1 | **Segmentation** | The unit of atomicity moves from *whole graph* to *page*. The corpus is already segmented in nature: two populations separated by a 35-second empty band (§2.2). The design recognises a split the data already shows. |
| 2 | **Taking out** | Extract the harmful property, not the object. The harmful thing is the *parse cost*, not the page. The page keeps a row — path, mtime, state — while its blocks are absent. |
| 10 | **Preliminary action** | Classify a page as at-risk *before* paying the cost, so the critical path never burns 58 s. Note §2.4: the predictor must be structural (nesting depth, reference density), never byte or line count. |
| 11 | **Beforehand cushioning** | Quarantine *is* the cushion. An over-budget page is parked, not lost, and retried under a larger budget off the critical path. |
| 15 | **Dynamics** | The budget stops being one constant and becomes two: strict interactive, generous background. This is the move that dissolves the contradiction. |
| 24 | **Intermediary** | A quarantined page is still served — by the Markdown/AST path that already exists and already works. |
| 25 | **Self-service** | Rehabilitation is automatic: retry on `mtime` change, with backoff, using the machinery already present in the daemon. |

### 4.4 Why the measurement made the design safe

The bimodality in §2.2 is what turns Segmentation from a guess into a warranted choice.
With a 35-second empty band, **every threshold between 5 s and 40 s yields the identical
classification**. There are no borderline pages, so a page cannot oscillate between
quarantined and indexed as machine load varies. The classifier is stable by construction.

This also vindicates the existing 15-second default: it was never mis-calibrated. The
defect is in what the system *does* at the threshold, not where the threshold sits.

---

## 5. Design: explicit quarantine with per-page degradation

1. **Schema (additive)** — a content-free record of the parked page: reason category
   only (`parse_timeout`, `parse_error`), size counters, and an attempt counter.
   Default value must reproduce current behaviour exactly.

   *As implemented*, this became a **separate `quarantined_pages` table** rather than a
   state column on `pages`, which is a deliberate departure from the sketch above. A
   status column would have left a row in `pages` for a page that has no blocks, so
   every existing `pages` query, FTS trigger, and subtree CTE would have had to learn to
   exclude it — a change to fifteen call sites, each one a chance to conflate *"not in
   shadow"* with *"in shadow and empty"*, which point 3 identifies as the correctness
   crux. With a separate table the quarantined page is simply **absent** from `pages`,
   so every one of those queries keeps its exact prior meaning and the crux is resolved
   by construction instead of by fifteen correct edits. The table uses
   `CREATE TABLE IF NOT EXISTS`, so existing databases migrate on open with no schema
   version bump.
2. **Health invariant** — becomes `indexed + quarantined == source == actual`. A graph
   with quarantined pages stays **`READY`** while exposing `quarantined_page_count`.
   Structurally honest: sound *and* declaredly incomplete.
3. **Per-page routing** — reads targeting a quarantined page use the existing
   Markdown/AST path. A subtree query on a quarantined block must answer *"not in
   shadow"*, never *"empty"*. This distinction is the correctness crux.
4. **Two budgets** — `MATRYCA_PAGE_PARSE_TIMEOUT_S` (15 s) stays for the interactive
   path; a separate, larger background budget serves a low-priority rehabilitation pass.
   **Deferred**, and not shipped in `v2.0.0-beta.1`. A page is instead released
   automatically the next time it parses within the single existing budget, which covers
   the common case (the page was edited or split) without adding a second scheduler to a
   daemon-core change that already carries CRITICAL risk.
5. **Preflight** — structural pre-classification so a rebuild does not pay the cost
   before quarantining. Deferred; not required for correctness.

Expected effect on the measured corpus: full rebuild drops from **22.6 min to ~2.2 min**
(~10×), and 3,353 of 3,378 pages gain accelerated reads instead of none.

### 5.1 Implementation constraints

A code audit of the four load-bearing symbols returned **HIGH or CRITICAL** risk on all
of them, with exact (not inferred) call-graph edges:

| Symbol | Risk | Impacted | Processes |
|---|---|---|---|
| `rebuild_shadow_from_graph` (`src/shadow/bootstrap.py`) | **CRITICAL** | 15 | 7 |
| `shadow_meta_matches_page_rows` (`src/shadow/health.py`) | HIGH | 13 | 4 |
| `resolve_shadow_health` (`src/shadow/health.py`) | HIGH | 12 | 4 |
| `sync_page_into_connection` (`src/shadow/sync.py`) | HIGH | 10 | 4 |

`rebuild_shadow_from_graph` reaches `run_forever`, `start_daemon_foreground`,
`run_plumber_cluster`, and `run_plumber_audit` — an error there does not degrade an
opt-in feature, it prevents the daemon from starting. **There is no low-risk version of
this change**: the defect lives precisely in these symbols.

Mandatory constraints for the implementation:

- Schema changes strictly additive; an existing `2.0.0b1` database must stay readable.
- `shadow_meta_matches_page_rows` takes the new count as an **optional parameter
  defaulting to 0**, reproducing today's semantics exactly. The existing tests must pass
  **unmodified** — if a test needs changing, the semantics were broken.
- Quarantine behind its own flag nested inside `MATRYCA_SHADOW_DB_ENABLED`, so the
  default execution path is unchanged byte-for-byte.
- `rebuild_shadow_from_graph` is modified **last**, only after health and sync are green.
- Full change-scope audit before every commit.
- A real soak after the change. A two-hour soak on a daemon-core modification would be
  weaker evidence than what exists today.

---

## 6. Status and operator guidance

**Fixed in `v2.0.0-beta.1`.** Per-page quarantine ships enabled by default (nested inside
the still-default-off `MATRYCA_SHADOW_DB_ENABLED`, so a default install is unaffected).

- A page that exceeds the parse budget is parked in `quarantined_pages` and left out of
  the cache. The rest of the graph is indexed, and health stays **`READY`** under the
  widened invariant `indexed + quarantined == source == actual`.
- Reads for a parked page route to Markdown, which remains the system of record. Nothing
  is lost or corrupted; those pages simply get no FTS or subtree acceleration.
- A parked page is released automatically as soon as it parses within budget, and a full
  rebuild clears all prior verdicts so an edited or split page gets another chance.
- `GET /api/state` reports `shadow_db.quarantined_page_count`, rendered by the Sovereign
  UI. Parked pages are excluded from `lag_pages`: they are a settled decision, not
  pending work, and counting them would leave a fully synced graph reporting a backlog it
  will never clear.
- `MATRYCA_SHADOW_QUARANTINE_ENABLED=false` restores the strict pre-2.0 behaviour where
  any over-budget page aborts the whole rebuild. The characterization tests for that mode
  are retained in full, so the kill switch is a supported path rather than dead code.
- Raising `MATRYCA_PAGE_PARSE_TIMEOUT_S` (clamped 2–120 s) parks fewer pages at the cost
  of substantially slower rebuilds. It remains a trade, not a remedy — see §3.1.

**What quarantine does *not* do.** It does not make a pathological page parse faster. The
25 measured pages still cannot be represented in the cache; the change is that their cost
is now paid by those 25 pages instead of by all 3,378. Structural preflight (§5, point 5)
and a second background budget (point 4) remain unimplemented.

### 6.1 Observability, shipped alongside

`GET /api/state` also returns `shadow_db.not_ready_reason`, a closed vocabulary of
content-free codes (`not_bootstrapped`, `bootstrap_in_progress`, `database_unreadable`,
`schema_version_mismatch`, `sync_error`, `full_sync_incomplete`, `page_count_mismatch`),
rendered as a plain-language sentence in the Sovereign UI Shadow DB row.

This was designed while the defect was still unfixed, to make it **visible**: an operator
otherwise saw a cache that silently never accelerated anything, with no way to distinguish
that from a slow first sync without reading daemon logs. It is retained now that
quarantine has landed, because the remaining non-ready states — an unreadable file, a
schema mismatch, an aborted first bootstrap — are exactly the cases where the operator
still has nothing else to go on. Observability was never a substitute for quarantine, but
shipping a known limitation without a way to see it is the worse failure: a silent
non-remedy invites the operator to conclude the feature is broken, or worse, to start
editing their own pages to appease it.

---

## 7. Reproducing the measurement

The measurement is a single-file script run against a **copy** of a vault, never the
live one, using the product's own parser. It records only aggregate, content-free
figures. Raw per-page output, page titles, paths, and content hashes must not be
committed to this repository — see the privacy boundary in
[`V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md`](V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md).

Procedure: install the candidate wheel into an isolated virtual environment; iterate all
`*.md` files under the vault copy; call `parse_page_text_bounded(text, mode="stack",
timeout_s=115.0)` per page under a `__main__` guard (the parser uses `spawn`
multiprocessing); record elapsed time, byte count, and line count; reset the worker after
any non-`ok` result; report only the aggregate distribution.

---

## 8. Related

- [`issue-bodies/shadow-page-parse-quarantine.md`](issue-bodies/shadow-page-parse-quarantine.md) — implementation issue
- [`V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md`](V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md) — evidence ledger and privacy boundary
- [`issue-bodies/v2-beta-readiness.md`](issue-bodies/v2-beta-readiness.md) — beta readiness gates
- [`BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md`](BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md) — evidence reproducibility remediation
- Epic [#20](https://github.com/MarcoPorcellato/matryca-plumber/issues/20) — Shadow DB
- [#297](https://github.com/MarcoPorcellato/matryca-plumber/issues/297) — bounded page parse containment
