---
type: Decision
title: Risk-based release qualification decision
description: Records why Matryca Plumber selects fresh release gates by change risk instead of requiring a 72-hour soak for every artifact.
resource: docs/quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md
tags: [release, qualification, risk, evidence, soak]
verified: { by: human:marco-porcellato, at: '2026-08-24T00:00:00Z' }
last_verified: 2026-08-24
stale_after: 2027-02-20
status: stable
classification: canonical
canonical_for: release.risk-based-qualification
audience: [maintainer, contributor, operator]
owner: release
authority: release-qualification-applicability
related:
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md
  - V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md
---

# Risk-based release qualification decision

## Decision

Matryca Plumber selects release-qualification gates from the risk introduced by the
delta from the last qualified public artifact. A 72-hour Gate B campaign is not a
universal ritual for every patch. It remains a mandatory fresh gate for releases that
change durable state, data-integrity boundaries, concurrent behavior, parser or graph
I/O semantics, recovery, service lifecycle, migrations, defaults, or comparable
systemic behavior.

Every release still needs fresh evidence for its exact source, required CI, package
artifacts, and publication path. Lower-risk releases use a smaller exact-artifact
qualification envelope and cannot inherit an earlier soak.

The tier classifies behavior introduced or materially affected by the release delta,
not every unchanged subsystem present in the process. Reusing the stable profile's
ordinary Shadow bootstrap does not automatically elevate every new read target to Tier
3. It does require profile-control smoke, and any delta-attributable Shadow behavior or
integrity discrepancy triggers escalation.

## Why this distinction matters

Two questions had previously been compressed into one:

1. **Can evidence for one artifact prove another artifact?** No. Source, CI, package,
   soak, benchmark, and observation results remain bound to their exact bytes,
   platform, runner, profile, and terminal receipt.
2. **Does every new artifact require every possible gate?** No. The release delta and
   its failure modes determine which fresh gates are applicable.

Keeping both rules avoids two unsafe extremes: transferring old reliability evidence
to new bytes, or spending three days re-proving unchanged durability behavior after a
documentation-only or isolated read-only change.

## Qualification tiers

| Tier | Change boundary | Required evidence | Escalation |
| --- | --- | --- | --- |
| 0 — documentation | No shipped behavior or dependency change | Documentation gates, exact-head PR CI, and publication checks if released | Escalate if generated/runtime contracts drift |
| 1 — isolated read-only | Additive, bounded read/API behavior isolated from Shadow, parser semantics, graph I/O, writes, defaults, persistence, recovery, concurrency, and service lifecycle | Exact public package binding; install, metadata, and `RECORD` verification; targeted supported-platform tests; bounded smoke in each affected runtime profile | Escalate on scope mismatch, profile interaction, or any unexplained failure |
| 2 — runtime or dependency | Common-path runtime, dependency, performance, or platform change without durable-state semantics | Tier 1 plus affected-platform, fallback, recovery, security, and bounded canary evidence selected in the version plan | The maintainer records whether full Gate B is required |
| 3 — durable or systemic | Durable state, watcher, recovery, concurrency, external Read Only cache, graph I/O, parser semantics, write plane, service lifecycle, migration, default, security/data integrity, or major release | Full applicable gate map and fresh exact-artifact dual-profile Gate B | No downgrade without a new reviewed decision |

Gate B means at least 259,200 valid seconds per required profile. Setup, preflight,
downtime, interrupted time, and historical campaigns never contribute to that total.

## Historical application: v2.0.1-rc.1

This dated application is bound only to release commit
`48eae93b1152c9fe7d1f19d63de3f781b686932e` and the public artifacts recorded for
that commit. The repository later advanced beyond those bytes. No later `main`,
candidate, or stable release inherits this classification or its incomplete gates;
each requires a fresh exact-source delta review and version-specific plan.

The reviewed source delta adds one bounded, canonical `journal_day` read and
provider-free evidence tooling. The handler itself does not query or initialize
Shadow, mutate the graph, or alter the write plane; ordinary CLI/MCP profile bootstrap
may prepare Shadow before dispatch and remains part of the bounded profile smoke.

The public wheel declares `logseq-matryca-parser>=1.7.1,<2.0.0`. An independent fresh
installation on 2026-08-24 resolved parser 1.8.0 rather than the historical v2.0.0
qualification baseline, 1.7.1. Parser 1.8.0 retains the public parser contract but
changes common-path implementation and adds assurance tooling. The effective RC1 artifact
classification is therefore **Tier 2 — runtime or dependency**, even though the
`journal_day` source delta alone fits Tier 1. A floating compatible dependency must be
classified from the bytes users actually receive, not only from the lockfile used by
the release source checkout.

The RC1 artifact would require fresh exact-wheel provenance and installation checks, a
minimum/current parser matrix covering 1.7.1 and 1.8.0, targeted `journal_day` tests on
supported CI platforms, and a bounded smoke of both the `default-on` and
`read-only-external` profiles. The smoke must complete two consecutive
cycles per profile, with one Shadow-on and one explicit Shadow-off attempt in each
cycle: four passing attempts per profile in total, clean stderr, and preserved
source/working integrity. This bounded result does not claim restart durability or a
72-hour soak.

Any provenance mismatch, failed targeted test, parser-semantic discrepancy,
unexplained profile failure, graph mutation, Shadow interaction, or integrity
discrepancy stops qualification. A failure that reaches a Tier 3 boundary reclassifies
that artifact and requires fresh full Gate B evidence. Parser 1.8.0 resolution alone
does not require Gate B; a demonstrated parser or graph-I/O semantic change does.

## Emergency security exception

When delaying a security fix creates greater user risk, the maintainer may publish
after a smaller fail-closed envelope. The release record must state the exception,
known limitations, and required follow-up observation. The exception does not convert
partial evidence into a pass and does not waive artifact binding.

## Evidence and documentation ownership

- The [gate map](RELEASE_QUALIFICATION_GATE_MAP.md) owns the reusable gate and tier
  matrix.
- The [public evidence policy](PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md) owns
  retention, redaction, correction, and claim boundaries.
- A version-specific qualification plan owns the classification and selected gates
  for one candidate.
- `docs/releases/` owns immutable publication facts.
- Historical records keep their original language and bindings; this decision is not
  retroactively inserted into old campaign evidence.

Matryca Plumber remains the authoritative editing origin. Matryca Knowledge may
project the committed result with exact Git provenance, but it does not become a
second policy authority.
