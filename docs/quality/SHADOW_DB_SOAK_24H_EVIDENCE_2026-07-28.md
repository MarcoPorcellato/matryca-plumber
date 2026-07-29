# Shadow DB 24-hour soak — evidence record

**Status:** evidence record, 2026-07-28. This is a sanitized quality artifact, not a release note and not a release decision. It reports what one 24-hour soak run observed, including two interruptions and what they do and do not prove. The release decision remains [`issue-bodies/v2-beta-readiness.md`](issue-bodies/v2-beta-readiness.md); the reproducibility analysis that motivated the current harness remains [`BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md`](BETA_EVIDENCE_REPRODUCIBILITY_RCA_2026-07-23.md).

The corpus is a working copy of a daily-use vault. Page titles, paths, block identifiers, and content are deliberately absent from this document; only aggregate counts appear.

## Result

The soak gate recorded `PASS` with `beta_qualified: true`.

| Field | Value |
| --- | --- |
| `status` | `PASS` |
| `beta_qualified` | `true` |
| `duration_target_reached` | `true` |
| `observed_duration_seconds` | 86 465.2 (target 86 400) |
| `cycles_completed` | 144 |
| `attempts_recorded` | 288, all `PASS` |
| `subtree_checks` / `subtree_skipped` | 144 / 0 |
| `synthetic_crud_checks` | 144 |
| `source_count` min / max | 1014 / 1014 |
| `indexed_count` min / max | 1011 / 1011 |
| `page_parse_timeout_seconds` | 15 |
| `candidate_wheel_binding_digest` | `6fa52103489a5c37…` |

The binding digest is the same value the installed-wheel gate recorded, so the artifact that passed the wheel gate is the artifact the soak exercised.

## What each cycle exercised

Every cycle ran the probe twice, once with the Shadow flag on and once with it off, and recorded both phases separately. The on-phase performed, in order: readiness assertion at startup; creation of a synthetic page through the real watchdog path, followed by full-text and subtree assertions; a rename, asserting the old path is gone and the new one present; a delete, asserting removal. Every twelfth cycle additionally forced a sync error, asserted the health state became `ERROR`, rebuilt, and asserted the return to `READY`.

Because the probe generates its own mutations, a static corpus does not weaken the test of change propagation: the create/rename/delete path was exercised 144 times regardless of whether the underlying vault changed.

## Observations

### Count invariants

The post-quarantine invariant is `source == indexed + quarantined`, because a parked page is deliberately absent from `pages` so that existing queries, full-text triggers, and subtree traversals keep their prior meaning.

Across 144 cycles the observed set of `(source_count, indexed_count)` pairs has exactly one element, `(1014, 1011)`, and the observed set of quarantined counts has exactly one element, `{3}`. The invariant held 144 times out of 144, including across twelve full rebuilds.

### Parked pages are a stable set, not a fluctuating one

The working hypothesis before the run was that over-budget pages are load-dependent and would fluctuate with machine load. The run does not support that hypothesis. The parked count was 3 in every cycle, under idle conditions, under heavy interactive use, and across twelve rebuilds. At a 15-second budget the over-budget set on this corpus is reproducible rather than incidental.

One earlier observation that appeared to show fluctuation is now explained differently. A baseline run recorded zero parse timeouts where the candidate parked three pages. The baseline package predates the bounded per-page parse: the commit that introduced it is not an ancestor of the baseline tag. The baseline therefore had no budget to exceed and parsed every page to completion. The two runs were never comparable on this axis.

### Memory

Resident set size for the 132 non-rebuild cycles ranged from 103 888 to 108 080 KiB. Comparing halves of that series gives 104 952 KiB for the first half and 105 298 KiB for the second, a difference of 0.3 per cent. After 24 hours, twelve rebuilds, a checkpoint resume, and a host suspension, consumption does not trend upward.

Rebuild cycles peak higher, between 149 872 and 168 896 KiB, with no trend across the run: the lowest peak is the first and the highest the last, but the sequence rises and falls repeatedly in between. Rebuild *duration* over the same cycles is flat, which is the stronger signal that the peaks reflect host memory pressure rather than accumulation in the process.

### Rebuild cost

Twelve full rebuilds completed. The first, 188.9 s, is the initial cold build and is not comparable. The eleven warm rebuilds: 83.5, 82.8, 100.3, 80.6, 80.2, 80.4, 80.2, 80.5, 80.6, 82.7, 82.0 seconds. Ten of eleven fall within a three-second band. The single outlier at 100.3 s occurred immediately after the checkpoint resume, with the host carrying 17 GB of swap.

Against a 900-second per-probe timeout, the margin is better than tenfold, which is why sustained interactive use of the host during the run could not threaten completion.

### Recovery

Eleven forced-error recovery cycles all succeeded: induced sync error, health state `ERROR`, rebuild, health state `READY`, followed by the full invariant check.

## Interruptions

The run was not 24 continuous hours of wall-clock time. It was 24 hours of accumulated exercise across three segments, separated by two interruptions. Both are recorded here because the machine-readable evidence does not distinguish them: `observed_duration_seconds` alone would suggest an unbroken run.

| # | After cycle | Cause | Duration | How it ended |
| --- | --- | --- | --- | --- |
| 1 | 36 | The soak was a child of a session-scoped background job; the session ended and the process was terminated with it. | ~3 h 25 min | Resumed from checkpoint; relaunched detached from any session. |
| 2 | 112 | The host was suspended. The process remained alive, sleeping in its inter-cycle interval. | ~1 h 19 min | Resumed on its own when the host woke. |

Neither interruption was a fault in the code under test. The first was a harness-lifetime mistake; the second was ordinary host behavior.

### Why the interruptions did not corrupt the evidence

Three independent checks support this.

**Elapsed time excludes the gaps.** The accumulator advances only between checkpoints inside the active loop, as `elapsed += now - last_checkpoint`. At the first resume it advanced by 101 s, not by the 3 h 25 min of absence; at the second, by 602 s, one ordinary interval. The clock is monotonic and does not advance across host suspension. The run therefore performed the full 86 400 seconds of exercise; the gaps are excluded rather than credited.

**The attempt chain is unbroken.** Each recorded attempt carries its own digest and the digest of its predecessor. Across all 288 attempts there is no link whose `previous_digest` fails to match the preceding `digest`, and the sequence numbers run contiguously from 0 to 287. A resumed segment that had lost or reordered state would break this chain.

**The measurements are indistinguishable across segments.**

| Segment | Non-rebuild cycles | Mean RSS (KiB) | Quarantined | `(source, indexed)` |
| --- | --- | --- | --- | --- |
| Before interruption 1 | 33 | 105 364 | `{3}` | `{(1014, 1011)}` |
| Between the two | 69 | 104 755 | `{3}` | `{(1014, 1011)}` |
| After interruption 2 | 30 | 105 714 | `{3}` | `{(1014, 1011)}` |

The invariant sets are identical in all three segments and the mean RSS varies by under one per cent. Additionally, the resume path re-verified the working-copy fingerprint before continuing, so the corpus is known not to have changed while the process was absent.

What the interruptions do limit: this run does not demonstrate 24 hours of *uninterrupted* process lifetime. It demonstrates 24 hours of accumulated exercise with two verified-clean resumptions. Anyone relying on the former should re-run without interruption.

## Reconciling 25 over-budget files with 3 parked pages

The parse-budget analysis in [`SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md`](SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md) reports 25 over-budget files; this soak parked 3. The two figures are consistent. They are computed over different populations, and neither is wrong.

### The populations differ

`rebuild_shadow_from_graph` enumerates the graph, which is `pages/` and `journals/` only. The budget study enumerated every Markdown file under the vault root, which also sweeps in Logseq's own on-disk history.

| Vault region | Markdown files | In the graph | Over budget at 15 s |
| --- | --- | --- | --- |
| `pages/` | 504 | yes | 3 |
| `journals/` | 510 | yes | 0 |
| `logseq/version-files/` | 2 203 | no | 19 |
| `logseq/bak/` | 131 | no | 3 |
| `logseq/.recycle/` | 30 | no | 0 |
| **Total** | **3 378** | **1 014** | **25** |

The 1 014 graph pages are exactly the soak's `source_count`, and the 3 over-budget pages in `pages/` are exactly the 3 the soak parked — same region, same population, same count. The other 22 over-budget files are version snapshots, backups, and recycle-bin entries that the Shadow DB never reads, because they are not pages.

### The 25 are 19 distinct documents, and only 3 distinct pages

Re-measuring the corpus with the same parser, mode, and 115-second deadline the study used reproduces its headline figures: 25 files over a 15-second budget, of 19 distinct contents. Comparing content digests across regions shows the structure behind that spread: the 3 over-budget graph pages each also appear as over-budget snapshots under `logseq/`, and the remaining 16 distinct over-budget documents exist *only* in the history directories — earlier revisions of pages that no longer parse slowly, or that no longer exist.

So the honest statement of the cost is: **3 pages in the live graph exceed the budget; 25 files on disk do, because Logseq keeps prior revisions of them.** The first number is what quarantine parks and what a user experiences. The second is what a filesystem sweep sees, and it is the right number when reasoning about disk-level tooling — but it overstates the graph by roughly eight to one on this corpus.

### What the re-measurement changes

Two figures in the budget study should be read as load-dependent rather than fixed.

The study recorded an over-budget range of 41.65 s – 58.33 s with every page completing inside 115 s. The re-measurement, on the same corpus and the same host but under ordinary interactive load, recorded 42.74 s – 115.00 s, and one graph page did **not** complete within the 115-second deadline at all.

The *membership* of the over-budget set is reproducible: the same files, the same count, both here and in all 144 soak cycles. The *magnitudes* are not — they scale with host contention, and the tail has no upper bound the corpus can establish. This is direct empirical support for [§3.1 of the study](SHADOW_DB_PARSE_BUDGET_TRIZ_2026-07-27.md), which argues that raising the budget relocates the threshold rather than removing the failure class: a 90-second budget chosen against the study's numbers would still have failed on this corpus, on this machine, on a day with normal load.

## Reproduction

The soak is driven by `scripts/beta_evidence/`, invoked through its CLI with an explicit output directory, candidate interpreter, source vault, working root, duration, cycle cap, interval, and page-parse timeout. This run used a 86 400-second duration, a 145-cycle cap, a 600-second interval, and a 15-second page-parse timeout. The working root must not exist at launch; the harness creates it. Resuming requires every input to match the recorded state, otherwise the harness refuses with `soak_resume_mismatch`.

A defect found and fixed during this work is recorded in commit `cf9fa8f`: the probe's flag-on block still asserted the pre-quarantine equality `source == indexed`, which aborts the run at cycle zero as soon as any page is parked. A code audit of the probe confirmed three count invariants in total, now mutually coherent.
