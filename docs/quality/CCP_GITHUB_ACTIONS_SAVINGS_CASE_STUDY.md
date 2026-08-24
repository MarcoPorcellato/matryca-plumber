---
type: Audit
title: Commit CI Preflight GitHub Actions savings case study
description: Deterministic status generated from immutable Matryca Plumber hybrid-CI observations.
status: draft
classification: active
audience: [maintainer, contributor, operator]
owner: quality
last_verified: 2026-08-24
stale_after: 2027-02-20
---

# Commit CI Preflight GitHub Actions Savings Case Study

This document is generated from the immutable JSON ledger under
`docs/quality/ccp-savings/`. It separates observed elapsed seconds from
provider billing and never converts estimates into monetary claims.

## Current evidence

| Measure | Value |
| --- | ---: |
| Active records | 1 |
| Observed baseline records | 1 |
| Eligible saved-compute observations | 0 |
| Hosted fallbacks | 0 |
| Negative receipt cases | 0 |
| Failed observations | 0 |
| Cancelled observations | 0 |
| Excluded observations | 0 |
| Candidate hosted seconds | 0 |
| Remote verifier seconds | 0 |
| Net estimated hosted seconds saved | 0 |
| Median net seconds saved | Not available |
| Provider-confirmed billed minutes | Not available |
| Provider-confirmed monetary savings | Not available |
| Promotion status | NOT READY |

## Promotion gate

- Eligible observations: `0` / `10`.
- Eligible observation window: `0` / `21` days.
- Hosted fallbacks: `0` / `2`.
- Negative receipt cases: none

## Evidence boundary

The historical baseline is not counted as an activated saving. Failed,
cancelled, fallback, excluded, non-comparable, and superseded records remain
visible but never enter the saved-compute numerator. Local execution cost,
maintenance effort, billing, energy, and money require independent evidence.

Ledger fingerprint: `sha256:2a3ecb3136f7875406e7096bd70aaffc447aeb5903628f0235eabd0a67a2dec6`.
