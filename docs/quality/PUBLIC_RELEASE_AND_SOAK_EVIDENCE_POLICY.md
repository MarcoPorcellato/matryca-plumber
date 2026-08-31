---
type: quality-policy
title: Public release and soak evidence policy
description: Retention, redaction, review, and claim-boundary rules for public release and operational qualification evidence.
resource: docs/quality/PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md
tags: [quality, evidence, release, soak, provenance]
last_verified: 2026-08-24
stale_after: 2027-02-20
status: draft
classification: active
canonical_for: quality.public-release-and-soak-evidence-policy
owner: quality
authority: release-evidence-policy
---

# Public release and soak evidence policy

This policy defines how Matryca Plumber retains and presents public-safe release
and operational qualification evidence. It makes evidence inspectable without
turning a local result, an earlier candidate, or an operational record into a
broader product claim.

It complements the [release qualification gate map](RELEASE_QUALIFICATION_GATE_MAP.md),
the [Gate B soak runbook](GATE_B_RC_SOAK_RUNBOOK.md), and the version-specific
[release records](../releases/). Those documents own release procedures,
campaign mechanics, and individual publication facts respectively. This policy
owns evidence classification, retention, and claim boundaries.

## 1. Evidence classes

| Class | Required binding | Permitted statement | Never infer |
| --- | --- | --- | --- |
| Source check | Exact commit and command result | A named local check passed for those source bytes. | Hosted CI, package, or runtime qualification. |
| CI check | Exact workflow, head SHA, platform, and terminal job result | The named hosted job passed for that head. | Artifact installation, soak, security approval, or publication. |
| Package artifact | Source/tag, distribution filename, and SHA-256 digest | The named package was built or inspected. | Published availability or operational behavior. |
| Soak attempt | Candidate artifact, runner, profile, valid elapsed time, and attempt chain | The named profile reached its recorded terminal outcome. | Qualification of another artifact, source revision, profile, or future release. |
| Release publication | Signed tag, release commit, artifact digest, GitHub Release, and PyPI record | The named version was published through the recorded release path. | Future-release, ecosystem, benchmark, or external-review approval. |
| Post-release observation | Published artifact, observation window, method, and limitations | The bounded observation was recorded for that version. | Universal reliability, adoption, or safety. |

Evidence without every required binding is `partial` or `blocked`; it is never
silently promoted to `verified`.

## 2. Public-safe record contents

Public records may retain only the minimum information needed to reproduce the
claim boundary:

- repository-relative document and workflow references;
- version, tag, commit, artifact filename, digest, runner revision, and named
  profile when applicable;
- schema version, terminal state, valid elapsed time, completed-cycle count,
  and a bounded non-sensitive failure category;
- source and working-copy fingerprints only when they are deliberately designed
  to be non-identifying; and
- the exact limitation and next qualification required for a non-pass or
  historical result.

Records must not disclose credentials, tokens, private graph content, absolute
filesystem paths, raw diagnostics, user identifiers, unbounded logs, or host
telemetry. The [public quality evidence index](EVIDENCE_INDEX.md) is the
discovery surface; it links to retained records rather than duplicating their
claims.

## 3. Immutability and artifact boundaries

Terminal evidence is append-only. Do not edit a completed attempt to make it
look continuous, replace a failed result, or transfer a result to another
wheel, source tree, runner, profile, or release.

An interrupted campaign retains its last valid checkpoint and explicitly
records the interruption. Resume creates a linked attempt in the same chain
only after the runbook's integrity checks pass. Setup, preflight, downtime, and
invalid elapsed time never contribute to qualified runtime.

Historical records remain available with their original dates and bindings. Every
new release creates fresh source, CI, package, and publication evidence. It creates
fresh operational or soak evidence only when the release's documented risk
classification selects those gates. It never relabels, overwrites, or inherits an
earlier record.

This distinction is deliberate: **evidence transferability** answers whether an old
result can prove a new artifact (it cannot), while **gate applicability** answers
which new results the current change risk requires. Artifact binding does not make a
72-hour soak mandatory for every documentation-only or isolated read-only release.
See the [risk-based qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md).

## 4. Retention and review

| Record type | Minimum retention | Review trigger | Owner |
| --- | --- | --- | --- |
| Release record and artifact digest | Indefinite for every published version | Tag, artifact, or publication correction | Release maintainer |
| Terminal soak record | Indefinite for a published or promoted candidate | Candidate, runner, profile, or integrity correction | Quality maintainer |
| Non-terminal and failed attempt record | Until its linked terminal disposition is retained, then at least one release cycle | Root-cause review or retention review | Quality maintainer |
| Local check receipt | Until superseded by an exact-head result or release decision | Source, command, dependency, or platform change | Change owner |
| Post-release observation | At least the stated observation window plus one release cycle | Method, version, or limitation change | Release maintainer |

Every public evidence record needs a review date. A record past its review date
is stale evidence, not a failure and not a current qualification result.

## 5. Publication and correction procedure

1. Bind the record to exact source, artifact, runner, profile, and terminal
   result as required by its evidence class.
2. Redact before publication; preserve richer private diagnostics only in the
   owning incident or secure operational system when one exists.
3. Link the record from the evidence index with a status and limitation that
   matches the record's actual scope.
4. If a fact is corrected, append a dated correction or successor record. Do
   not silently rewrite historical evidence or expand its scope.
5. If the result is `unknown`, `running`, interrupted, skipped unexpectedly, or
   lacks a required binding, publish it only as a hold, investigation, or
   historical record—not as a qualification pass.

## 6. Current v2.0.0 application

The stable v2.0.0 release record and its readiness record are the publication
anchors for that exact version. RC2 Gate B evidence remains retained as
historical, exact-artifact evidence. It supports the history of v2.0.0
qualification but does not qualify later source changes or another artifact.

Future release work must create a new release record and package bindings, then
collect the operational evidence selected by its documented risk tier. This policy
does not authorize a release, certify external interoperability or review, or allow
historical evidence to be rebound to new bytes.
