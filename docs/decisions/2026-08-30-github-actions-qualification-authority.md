---
type: Decision
title: GitHub Actions qualification authority
description: Current authority and evidence boundaries for public pull-request qualification.
resource: .github/workflows/ci.yml
tags: [ci, quality, governance, qualification]
verified: { by: human:marco-porcellato, at: '2026-08-30T00:00:00Z' }
last_verified: 2026-08-30
stale_after: 2027-02-26
status: stable
classification: active
audience: [maintainer, contributor, operator]
owner: quality
---

# GitHub Actions qualification authority

## Decision

Standard GitHub-hosted runners are the authority for public pull-request
qualification. `Ironclad Gatekeeper` remains the protected context over the
parallel `Python 3.12 quality`, `Python 3.13 compatibility`, `Frontend quality`,
`Dependency Review`, `Shadow contract (macos-latest)`, and
`Shadow contract (windows-latest)`.

The active tree retires local receipt routing. Git history retains the earlier
hybrid local experiment as historical evidence, but it is not current routing
authority. Ordinary CI remains distinct from package qualification, Gate B,
benchmark, and publication evidence; each requires its own recorded gate.

CodeQL ruleset enforcement remains a separate observed-context mutation. This
decision records the repository workflow authority and does not assert a
ruleset change or replace its independent evidence.
