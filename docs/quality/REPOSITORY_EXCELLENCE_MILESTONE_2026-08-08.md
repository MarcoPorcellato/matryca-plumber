---
type: Audit
title: Repository excellence milestone — 34-PR merge programme
description: Verified public record of the 34 pull requests merged through the August 2026 repository excellence programme.
resource: docs/quality/REPOSITORY_EXCELLENCE_MILESTONE_2026-08-08.md
tags: [quality, architecture, documentation, security, maintainability]
timestamp: 2026-08-08T22:21:45Z
status: stable
classification: historical
last_verified: 2026-08-09
audience: [maintainer, contributor, operator]
owner: quality
authority: evidence
source_repository: MarcoPorcellato/matryca-plumber
source_ref: main
source_commit: 7b60ab27b42bc25b4631728435ab92ea8880c547
programme_plan: docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
---

# Repository excellence milestone — 34-PR merge programme

## Executive summary

Between 6 and 8 August 2026, Matryca Plumber completed a coordinated sequence of
**34 pull requests**: [#406](https://github.com/MarcoPorcellato/matryca-plumber/pull/406)
through [#412](https://github.com/MarcoPorcellato/matryca-plumber/pull/412), and
[#414](https://github.com/MarcoPorcellato/matryca-plumber/pull/414) through
[#440](https://github.com/MarcoPorcellato/matryca-plumber/pull/440).

The programme converted the
[repository excellence study](REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md) into a
linear, reviewable delivery chain. It strengthened Strict Read Only and Shadow DB
safety, made runtime state observable, consolidated documentation authority, added
deterministic documentation and dependency controls, and simplified high-risk parsing
and cache code with extensive differential-parity evidence.

This document is a timestamped public record of that milestone. It is not the current
operator contract, a release authorization, or a substitute for live CI and security
state.

## Verified completion record

| Measure | Verified result |
| --- | ---: |
| Pull requests merged | 34 |
| Pull-request range | #406–#412 and #414–#440 |
| Final `main` commit | `7b60ab27b42bc25b4631728435ab92ea8880c547` |
| Cumulative additions reported by GitHub | 7,140 |
| Cumulative deletions reported by GitHub | 834 |
| Cumulative file-change entries | 192 |
| Distinct paths touched | 105 |
| PRs touching production source | 19 |
| PRs touching tests | 23 |
| PRs touching documentation | 28 |
| PRs touching CI | 2 |
| PRs touching dependency state | 2 |
| Linked issues closed as completed | 15 |
| Open Dependabot alerts after the programme | 0 |

The aggregate change counts are the sums of GitHub's per-PR metadata and therefore
include files revisited by later PRs. They describe review volume, not the net diff
between the programme's first and final commits.

The 34 pull requests landed as signed, one-parent squash commits in one strict linear
chain. Each immediate head was revalidated against the current parent before merge;
the required CI checks were evaluated on that exact head.

## What changed at system level

### 1. Read Only became a useful operating mode

Strict Read Only is no longer treated as merely “turn writes off.” The programme made
it an explicit runtime policy that protects the graph while still allowing safe,
external, disposable acceleration:

- startup logging and diagnostic state honor external routing;
- graph-local write surfaces are governed consistently;
- UI secret inputs remain write-only;
- configuration persistence uses locking and optimistic concurrency control;
- Shadow DB reads use query-only SQLite connections;
- validated external Shadow cache writes remain available without weakening graph
  immutability.

The result is a practical default for users who want fast agent reads without granting
graph mutation authority.

### 2. Shadow DB became safer, fresher, and easier to operate

The Shadow read path gained stronger generation invalidation, freshness checks,
query-only access, and passive diagnostics. Operators and tests can now reason about
BM25 state, checkpoint recovery, watcher convergence, and Shadow health without
opening new mutation paths.

The architectural boundary remains unchanged: Logseq Markdown is authoritative;
Shadow is external, derived, disposable state. The
[current operator contract](../knowledge/architecture/shadow-db.md) owns activation,
location, health, fallback, and quarantine semantics.

### 3. Documentation gained an authority model

The programme replaced duplicated mutable claims with explicit ownership:

- one canonical Shadow DB operator path;
- one architecture authority boundary;
- roadmaps clearly separated from current behavior;
- release qualification separated from product documentation;
- generated and machine-readable documentation checks made deterministic;
- repository-local documentation kept authoritative while external knowledge systems
  consume reviewed, provenance-bound projections.

This reduces documentation drift and gives users, contributors, agents, and release
operators a predictable place to find the current answer.

### 4. Supply-chain and governance controls became explicit

The programme added deterministic issue-control and stacked-PR validation records,
introduced a non-blocking Python 3.13 evidence lane, and remediated the Python and
frontend dependency advisories that were open at the time.

The final live check on 9 August 2026 found zero open Dependabot alerts. That number is
a timestamped remote observation, not a permanent guarantee; GitHub's current alert
state remains authoritative.

### 5. Complex code became simpler without changing behavior

Six focused clean-code changes reduced branching and duplication in property-list
parsing, bootstrap harvesting, page-property injection, advanced-query scanning, Tana
date handling, and MARPA bullet extraction.

These were not “cleanup by inspection.” Each refactor carried fixed cases plus large
deterministic or exhaustive parity evidence against the previous implementation. The
campaign preserved public signatures, output ordering, early-return behavior, and
wire-format bytes while making the implementation easier to review and extend.

## Pull-request ledger

### A. Strict Read Only, Shadow DB, and configuration safety

| PR | Delivered result |
| ---: | --- |
| [#406](https://github.com/MarcoPorcellato/matryca-plumber/pull/406) | Routed startup logs externally under Strict Read Only; closed #388. |
| [#407](https://github.com/MarcoPorcellato/matryca-plumber/pull/407) | Routed X-Ray state externally instead of hiding graph-local mutation behind a read contract; closed #393. |
| [#408](https://github.com/MarcoPorcellato/matryca-plumber/pull/408) | Required Shadow readiness to imply freshness and added benchmark evidence; closed #389. |
| [#409](https://github.com/MarcoPorcellato/matryca-plumber/pull/409) | Made Shadow generation invalidation durable across processes and restarts; closed #386. |
| [#410](https://github.com/MarcoPorcellato/matryca-plumber/pull/410) | Applied local API token policy before socket binding; closed #395. |
| [#411](https://github.com/MarcoPorcellato/matryca-plumber/pull/411) | Made API-key settings write-only in the Sovereign UI; closed #390. |
| [#412](https://github.com/MarcoPorcellato/matryca-plumber/pull/412) | Added dotenv locking and optimistic concurrency control; closed #387. |
| [#414](https://github.com/MarcoPorcellato/matryca-plumber/pull/414) | Separated query-only SQLite read connections from schema-capable writers; closed #413. |

PR #408 recorded a 20,000-query benchmark with subtree p95/p99 latency of
9.638/12.579 ms and FTS p95/p99 latency of 9.265/11.343 ms on its stated fixture and
environment. These are PR-specific receipts, not universal performance promises.

### B. Architecture and passive diagnostics

| PR | Delivered result |
| ---: | --- |
| [#415](https://github.com/MarcoPorcellato/matryca-plumber/pull/415) | Enforced additional AST architecture boundaries. |
| [#416](https://github.com/MarcoPorcellato/matryca-plumber/pull/416) | Introduced a typed BM25 diagnostics snapshot. |
| [#417](https://github.com/MarcoPorcellato/matryca-plumber/pull/417) | Exposed scoring and eviction diagnostics without changing cache behavior. |
| [#418](https://github.com/MarcoPorcellato/matryca-plumber/pull/418) | Added checkpoint-recovery observability. |
| [#419](https://github.com/MarcoPorcellato/matryca-plumber/pull/419) | Added a bounded watcher-convergence snapshot. |
| [#420](https://github.com/MarcoPorcellato/matryca-plumber/pull/420) | Added a passive Shadow operational snapshot. |

These diagnostics make the runtime inspectable while preserving layer boundaries and
avoiding new control-plane side effects.

### C. Documentation authority and product scope

| PR | Delivered result |
| ---: | --- |
| [#421](https://github.com/MarcoPorcellato/matryca-plumber/pull/421) | Established the canonical v2 operator documentation path. |
| [#422](https://github.com/MarcoPorcellato/matryca-plumber/pull/422) | Clarified architecture authority and document roles. |
| [#423](https://github.com/MarcoPorcellato/matryca-plumber/pull/423) | Separated roadmap proposals from current runtime truth. |
| [#424](https://github.com/MarcoPorcellato/matryca-plumber/pull/424) | Retired obsolete Shadow migration guidance. |
| [#425](https://github.com/MarcoPorcellato/matryca-plumber/pull/425) | Centralized agent and release-qualification authority. |
| [#426](https://github.com/MarcoPorcellato/matryca-plumber/pull/426) | Scoped biological memory to v2.1; closed #396. |

### D. Documentation validation, CI, security, and governance

| PR | Delivered result |
| ---: | --- |
| [#427](https://github.com/MarcoPorcellato/matryca-plumber/pull/427) | Separated official OKF results from Matryca-specific documentation quality results. |
| [#428](https://github.com/MarcoPorcellato/matryca-plumber/pull/428) | Made JSON documentation validation deterministic and privacy-safe. |
| [#429](https://github.com/MarcoPorcellato/matryca-plumber/pull/429) | Added a non-blocking Python 3.13 evidence lane. |
| [#430](https://github.com/MarcoPorcellato/matryca-plumber/pull/430) | Added an issue-control ledger for programme traceability. |
| [#431](https://github.com/MarcoPorcellato/matryca-plumber/pull/431) | Added explicit stacked-PR validation evidence. |
| [#432](https://github.com/MarcoPorcellato/matryca-plumber/pull/432) | Remediated Python dependency advisories. |
| [#433](https://github.com/MarcoPorcellato/matryca-plumber/pull/433) | Remediated frontend dependency advisories. |
| [#434](https://github.com/MarcoPorcellato/matryca-plumber/pull/434) | Audited shipped contributor issues against implementation evidence. |

The Python dependency slice updated GitPython, aiohttp, and cryptography. The frontend
slice updated PostCSS, Nano ID, and brace-expansion. Exact versions remain governed by
the current lockfiles rather than this historical record.

The Python 3.13 lane is intentionally observational. It kept a real symlink-loop
safety regression visible without weakening the required Python 3.12 gate or turning
an unqualified runtime into a release claim.

### E. Differential-parity clean-code refactors

| PR | Delivered result | Differential evidence recorded by the PR |
| ---: | --- | ---: |
| [#435](https://github.com/MarcoPorcellato/matryca-plumber/pull/435) | Simplified property-list parsing; closed #235. | 119,608 inputs |
| [#436](https://github.com/MarcoPorcellato/matryca-plumber/pull/436) | Simplified bootstrap page harvesting; closed #230. | Focused deterministic parity suite |
| [#437](https://github.com/MarcoPorcellato/matryca-plumber/pull/437) | Simplified page-property injection; closed #236. | 100,000 inputs |
| [#438](https://github.com/MarcoPorcellato/matryca-plumber/pull/438) | Simplified advanced-query bracket scanning; closed #229. | 597,871 exhaustive + 20,000 random inputs |
| [#439](https://github.com/MarcoPorcellato/matryca-plumber/pull/439) | Simplified Tana journal-date recognition; closed #223. | 137,257 patterns + 20,000 dates |
| [#440](https://github.com/MarcoPorcellato/matryca-plumber/pull/440) | Simplified MARPA bullet extraction; closed #227. | 500 seeded graphs |

The evidence counts above are the receipts attached to the individual PRs. They were
reviewed as part of the merge programme but were not re-executed to create this report.

## Test and quality progression

The PR-level CI receipts show the main test suite progressing from approximately
**1,616 passing tests at 83.23% coverage** near the beginning of the chain to
**1,709 passing tests at 83.77% coverage** at the end. The precise count varies by
slice because tests and optional lanes changed during the programme.

These values describe the exact PR heads and CI configurations that produced them.
They must not be used as a permanent badge or as evidence that a later commit is
green. Current GitHub Actions runs remain authoritative for the current branch.

## Issues completed

The programme verified completion of the following linked issues:

`#223`, `#227`, `#229`, `#230`, `#235`, `#236`, `#386`, `#387`, `#388`, `#389`,
`#390`, `#393`, `#395`, `#396`, and `#413`.

Issue closure was based on shipped implementation and validation evidence, not title
similarity. Broader epics and follow-up issues remain independent work.

## Release and evidence boundary

This milestone substantially improved the codebase, but it does not by itself promote
a release.

In particular, any soak result qualifies only the exact installed wheel, manifest,
configuration, and attempt chain that produced it. Runtime or dependency changes after
that artifact was built require a new exact wheel and explicit requalification. A
historical Gate B result cannot be transferred to the final programme commit merely
because all intermediate CI checks passed.

Release mechanics and authorization gates live in
[`docs/RELEASE_PROCESS.md`](../RELEASE_PROCESS.md). The current v2 runtime contract
lives in the [Shadow DB operator document](../knowledge/architecture/shadow-db.md).

## Why this milestone matters

The programme did not chase novelty or a large rewrite. It concentrated on the places
where an agentic memory system earns trust:

1. **Authority is explicit.** Human-readable Markdown remains the durable source of
   truth; acceleration layers are derived and replaceable.
2. **Permission is meaningful.** Read Only is enforced as a system policy and remains
   useful with an external cache.
3. **Failure is contained.** Cache, watcher, configuration, and concurrency failures
   fail closed or fall back without silently corrupting the graph.
4. **Operations are observable.** Typed, passive diagnostics expose state without
   creating new mutation paths.
5. **Documentation has ownership.** Current contracts, plans, historical evidence,
   release mechanics, and version deltas no longer compete for authority.
6. **Simplification is evidence-backed.** Complex paths became easier to maintain
   while differential tests protected behavior.
7. **Delivery is auditable.** Small signed squash commits, exact-head CI, issue links,
   and a linear merge chain preserve a reviewable history.

Together, these changes move Matryca Plumber closer to its defining goal: agentic
memory that is fast enough for machines, understandable and controllable by humans,
and safe enough to trust with a long-lived knowledge graph.

## Evidence limitations

- GitHub counts, alert state, and issue state were verified on 9 August 2026 and may
  change later.
- Aggregate PR additions, deletions, and file-change entries are cumulative metadata,
  not a net repository diff.
- Benchmark and differential-parity counts are supplied PR receipts unless explicitly
  described as re-run in a later qualification record.
- Local green checks do not independently prove remote CI, Windows behavior, package
  contents, or release-artifact qualification.
- This report preserves historical evidence. Current source, canonical operator docs,
  lockfiles, GitHub checks, and release records supersede it for present-state claims.
