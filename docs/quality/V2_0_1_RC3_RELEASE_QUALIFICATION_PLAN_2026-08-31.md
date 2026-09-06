---
type: release-qualification-plan
title: v2.0.1-rc.3 historical qualification plan
description: Historical RC3 qualification-plan snapshot. RC3 was subsequently published; this plan does not describe the active candidate path.
resource: docs/quality/V2_0_1_RC3_RELEASE_QUALIFICATION_PLAN_2026-08-31.md
tags: [release, qualification, provenance, risk, v2]
last_verified: 2026-09-06
stale_after: 2027-02-27
status: historical
classification: archive
audience: [maintainer, contributor, operator]
owner: release
authority: release-candidate-plan
related:
  - RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - EVIDENCE_INDEX.md
  - ../releases/v2.0.1-rc.2-FAILED-PUBLICATION.md
---

# v2.0.1-rc.3 historical qualification plan

## Purpose and authority boundary

This is the historical proposed qualification contract for `v2.0.1-rc.3` /
`2.0.1rc3`, preserved as it stood before publication. It selects Tier 3 gates under the canonical
[risk-based qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md).
Its original statements below describe preparation status, not current release state.
RC3 was subsequently published; see the
[RC3 publication record](../releases/v2.0.1-rc.3-GITHUB.md). That publication does not
establish stable promotion or qualify RC4.

Coordination remains under milestone
[#22](https://github.com/MarcoPorcellato/matryca-plumber/milestone/22) and issue
[#548](https://github.com/MarcoPorcellato/matryca-plumber/issues/548).

Preparation begins from exact source `f91ba540fdb8c01f2ca5ccb30cedf71b6136b556`.
That preparation base is not the RC3 candidate. The candidate source, signed
annotated `v2.0.1-rc.3` tag, release workflow run, public wheel and sdist, manifest,
and provenance attestations remain unselected until execution under separate
authority.

`v2.0.1-rc.1` remains historical and artifact-bound. `v2.0.1-rc.2` is immutable
terminal failed-publication history: its tag, workflow, and private bundle evidence
are not public artifacts and cannot transfer to RC3, Gate B, or stable promotion. See
the [RC2 failed-publication record](../releases/v2.0.1-rc.2-FAILED-PUBLICATION.md).

## Tier 3 classification

**Classification: Tier 3 — durable or systemic.** RC3 retains these integrity
boundaries:

1. Operator `.env` replacement attempts parent-directory fsync after `os.replace`.
   A successful parent fsync supports a directory-entry durability claim only for its
   recorded attempt. A post-replacement parent-fsync `OSError` must be non-fatal,
   must not roll back the replacement, and cannot make that durability claim.
2. The maintenance robot must preserve Git commit-path isolation: it may commit only
   requested safe Markdown paths and must not absorb unrelated staged changes.
3. The checkout-free publication job must bind GitHub CLI release creation explicitly
   with `--repo "$GITHUB_REPOSITORY"`. The release-workflow contract test must keep
   that binding together with `--verify-tag`; a source assertion is not publication
   evidence.

Required focused controls are
`tests/test_ui_server.py::test_dotenv_atomic_replace_fsyncs_parent_directory`,
`tests/test_ui_server.py::test_dotenv_atomic_replace_tolerates_parent_fsync_failure`,
`tests/test_git_audit.py::test_robot_git_commit_stages_only_target_file`, and the
release-workflow contract coverage in `tests/test_release_workflow_contract.py`.
Their execution must be bound to the selected RC3 source and supported CI environment.
They do not replace release, package, platform, or Gate B evidence.

## Required qualification gates

Every row remains `proposed` until the exact RC3 candidate source and public artifact
exist. A non-terminal, skipped, mismatched, unavailable, or failed row is a hold.

| Gate | Required terminal evidence | Current state and boundary |
| --- | --- | --- |
| Candidate selection | Exact selected source, clean source identity, signed annotated `v2.0.1-rc.3` tag, and tag-to-source binding. | `proposed`; source and tag unselected. |
| Hosted source authority | Required hosted CI terminal green on exact candidate head, with no unexpected skip or base drift. | `proposed`; no RC3 workflow run selected or passed. |
| Targeted integrity controls | Both `.env` fsync paths, robot path-isolation test, and release-workflow contract test, tied to exact candidate source and supported CI. | `proposed`; source assertions do not prove hosted CI, publication, or Gate B. |
| Release authenticity and bundle | GitHub verification of signed tag; exact successful public wheel and sdist; two-file SHA-256 manifest; provenance attestations verified against downloaded subjects; explicit repository-bound release creation. | `proposed`; artifacts and workflow run unselected. |
| Installed-package and parser matrix | Isolated exact-artifact install, metadata and `RECORD` verification, declared-minimum and current parser checks, each bound to exact resolved versions. | `proposed`; no public artifact exists. |
| Supported-platform Shadow lanes | Terminal required macOS and Windows Shadow evidence on exact candidate source and artifact. | `proposed`; one platform cannot infer another. |
| Gate B | Fresh exact-public-artifact campaigns for `default-on` and `read-only-external`, with preserved checkpoints, recovery review, and at least 259,200 valid seconds for each profile. | `proposed` and outside current authorization; setup, preflight, downtime, interruption, and historical time do not count. |
| Terminal release decision | Review exact-source, artifact, platform, profile, integrity, and receipt evidence; preserve failures and limitations. | `proposed`; no qualification PASS recorded. |
| Stable promotion | Separate maintainer decision for `v2.0.1`, then its own signed tag and publication authority. | `proposed`; RC3 preparation never authorizes stable promotion. |

## Execution and stop conditions

Before qualification, obtain explicit authority for the exact source, tag, workflow,
artifact, platform, profile, resources, expected outputs, and stop boundary. Preserve
only public-safe identities, hashes, statuses, counters, bounded timings, and terminal
receipts in public evidence.

Stop on any source, tag, workflow, manifest, attestation, package, parser, platform,
profile, graph-integrity, or receipt mismatch; failed or unexpectedly skipped hosted
CI; targeted-control failure; or unavailable required platform. Preserve partial or
failed evidence. Do not retry, credit interrupted time, or transfer RC1 or RC2
evidence without a new authorized exact-artifact attempt.

Only a later separate stable decision may interpret terminal RC3 evidence. This plan
does not select a candidate, publish RC3, run Gate B, or authorize `v2.0.1`.
