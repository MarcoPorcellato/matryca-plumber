---
type: Audit
title: Commit CI Preflight GitHub Actions savings baseline
description: Historical pre-activation baseline for measuring hosted Linux compute displaced by Matryca Plumber's future hybrid CCP path.
status: stable
classification: historical
audience: [maintainer, contributor, operator]
owner: quality
last_verified: 2026-08-24
stale_after: 2027-02-20
---

# Commit CI Preflight GitHub Actions Savings Baseline

## Purpose

This document freezes the pre-activation measurement baseline for Matryca
Plumber's hybrid Commit CI Preflight adoption. It is historical evidence, not a
live dashboard, a provider invoice, or proof that any GitHub-hosted job has
already been removed.

The governing design is
[`docs/superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md`](../superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md).

## Capture anchors

| Item | Value |
| --- | --- |
| Capture date | 2026-08-24 |
| Repository | `MarcoPorcellato/matryca-plumber` |
| Planning base | `48eae93b1152c9fe7d1f19d63de3f781b686932e` |
| Candidate hosted jobs | `Ironclad Gatekeeper`; `Python 3.13 evidence (non-blocking)` |
| Candidate verifier source | `MarcoPorcellato/commit-ci-preflight@866db18a571f55ed3d9b481d6c9c9c3bd5e98d55` |
| Collection method | Read-only GitHub CLI workflow/job metadata |

## Comparable hosted cohort

The cohort includes only successful pull-request workflow runs in which both
candidate Linux jobs reached terminal success. Cancelled, failed, and runs with
the Python 3.13 job skipped were observed but excluded from the duration
summary.

| Workflow run | Source SHA | Ironclad | Python 3.13 | Combined |
| --- | --- | ---: | ---: | ---: |
| `32301476065` | `5d2e6cdf74aaf40ea2d6cfed68b121ac32dd395b` | 178 s | 136 s | 314 s |
| `32299548837` | `2d1d289ff7f207f9b464b50405767d6524dec998` | 185 s | 129 s | 314 s |
| `32298799053` | `1030016e48e9de64b51c0fc6caf147f39b389377` | 188 s | 137 s | 325 s |
| `32298430532` | `7c376e21732a3b90329369eea2dae1531633b703` | 187 s | 135 s | 322 s |
| `32297333571` | `eab3c1c648f219e9d9653b01135ee1bbb0fd0551` | 186 s | 130 s | 316 s |
| `32213103036` | `f00d8c1a84a12455364e19ed0cd15526677ad9f9` | 199 s | 140 s | 339 s |

The six combined observations are `314`, `314`, `325`, `322`, `316`, and
`339` seconds:

- median: `319` seconds;
- arithmetic mean: approximately `321.7` seconds;
- minimum: `314` seconds;
- maximum: `339` seconds.

These are elapsed job seconds, not GitHub billing-minute calculations. Parallel
jobs cannot be interpreted as pull-request wall-clock savings without a
separate critical-path analysis.

## Remote verifier observation

The successful CCP receipt-gate workflow run `32330532453` was observed in the
`commit-ci-preflight` repository:

| Step | Elapsed |
| --- | ---: |
| Complete verifier job | 50 s |
| Build pinned trusted Rust verifier | 40 s |

The gate checked trusted base policy, retrieved the exact SHA-derived evidence
branch, built only the pinned verifier, validated the receipt, and published the
final commit status. This sample did not execute Matryca Plumber code and is a
planning proxy until Matryca-specific receipt-gate observations exist.

## Initial estimate

```text
median candidate hosted compute              319 seconds
- observed remote CCP verifier                50 seconds
= estimated net hosted compute avoided       269 seconds per eligible PR
```

The ratio `269 / 319` is approximately `84.3%` of the two candidate Linux-job
seconds. It is not 84.3% of all Matryca Plumber GitHub Actions usage because
Dependency Review, CodeQL, native Shadow checks, release workflows, the full
`main` run, failed attempts, and fallback runs remain hosted.

## Exclusions and limitations

- The cohort is small and comes from one historical activity window.
- Run duration includes runner setup but does not establish provider billing.
- The remote verifier sample belongs to the CCP repository, not Matryca
  Plumber.
- Local CCP execution consumes developer-owned compute and maintenance effort;
  those costs require separate observations.
- The receipt does not prove producer identity.
- No eligible Matryca Plumber PR has yet skipped hosted Linux work under this
  design.
- No monetary saving is claimed.
- Failed, cancelled, skipped, stale, or mismatched runs must remain visible in
  the future ledger even when excluded from the savings numerator.

## Historical preservation rule

Do not rewrite this baseline when the workflow, prices, policy, or runtime
changes. New measurement epochs create new baseline records and link back to
this document. Corrections must identify the original row and preserve the
reason for supersession.
