---
type: release-qualification-plan
title: v2.0.1-rc.2 proposed qualification plan
description: Proposed Tier 3 qualification contract for the next v2.0.1 release candidate; no candidate source, artifact, or result is selected.
resource: docs/quality/V2_0_1_RC2_RELEASE_QUALIFICATION_PLAN_2026-08-31.md
tags: [release, qualification, provenance, risk, v2]
last_verified: 2026-08-31
stale_after: 2027-02-27
status: proposed
classification: active
audience: [maintainer, contributor, operator]
owner: release
authority: release-candidate-plan
related:
  - RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - EVIDENCE_INDEX.md
---

# v2.0.1-rc.2 proposed qualification plan

## Purpose and authority boundary

This is the active proposed qualification contract for `v2.0.1-rc.2`, tracked by
milestone [#22](https://github.com/MarcoPorcellato/matryca-plumber/milestone/22)
and issue [#548](https://github.com/MarcoPorcellato/matryca-plumber/issues/548).
It selects gates under the canonical
[risk-based qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md).
It records no successful qualification, public release, package artifact, tag, or
stable-promotion decision.

Preparation began from exact source
`1cb4ca9ddd9d40d91e2c033ba8b816880323889a`. That preparation base is not an RC2
candidate. The candidate source is not yet selected: it becomes only the exact
signed squash-merge commit selected after the preparation pull request is merged.
The candidate tag is not yet selected: it must be a signed annotated
`v2.0.1-rc.2` tag that resolves to that selected source. The artifact identity is
not yet selected: it becomes only the exact successful public RC2 release bundle,
including its wheel, sdist, two-file SHA-256 manifest, and provenance attestations.
No placeholder commit, tag object, workflow run, version digest, or package filename
may stand in for those future identities.

`v2.0.1-rc.1` remains a historical Tier 2 candidate, bound to its own release
commit and public artifacts in
[its historical plan](V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md). Its
publication and partial qualification evidence cannot qualify RC2, its selected
source, or its future artifacts.

## Tier 3 classification

**Classification: Tier 3 — durable or systemic.** The RC2 delta includes both of
the following integrity boundaries:

1. Operator `.env` replacement attempts a parent-directory fsync after `os.replace`.
   A successful parent fsync supports a directory-entry durability claim only for that
   recorded attempt. The shipped best-effort behavior catches a parent-fsync `OSError`
   after replacement: the replacement remains committed, is not rolled back, and makes
   no directory-entry durability claim for that attempt.
2. The maintenance robot must preserve Git commit-path isolation: a robot commit
   may commit only its requested safe Markdown paths and must not absorb unrelated
   staged changes.

Targeted evidence for these controls is required. The preparation diff includes the
`tests/test_ui_server.py::test_dotenv_atomic_replace_fsyncs_parent_directory`, which
checks the successful parent-fsync path, and
`tests/test_ui_server.py::test_dotenv_atomic_replace_tolerates_parent_fsync_failure`,
which must prove that a post-replacement parent-fsync `OSError` is non-fatal and does
not roll back the replaced `.env` file. It must also include
`tests/test_git_audit.py::test_robot_git_commit_stages_only_target_file`. Inclusion in
the preparation diff and local execution do not record exact-candidate hosted CI or
qualification results. Targeted evidence proves only those named paths at the recorded
source and environment. It does not replace the Tier 3 fresh exact-artifact dual-profile
Gate B campaign.

## Required qualification gates

Every row remains `proposed` until the exact candidate source and public artifact
exist. A non-terminal, skipped, mismatched, unavailable, or failed row is a hold;
it is never inferred as a pass.

| Gate | Required terminal evidence | Current state and boundary |
| --- | --- | --- |
| Candidate selection | Exact signed squash-merge commit, clean source identity, selected signed annotated RC2 tag, and exact candidate-to-tag binding. | `proposed`; no source or tag selected. |
| Hosted source authority | Required hosted CI terminal green on exact candidate head, including project release checks and no unexpected skip, review hold, or base drift. | `proposed`; local preparation checks do not prove hosted CI. |
| Targeted integrity controls | Successful parent-fsync test; tolerated-parent-fsync-failure test; and maintenance-robot Git-isolation test above, tied to exact candidate source and supported CI environment. A parent-fsync `OSError` after replacement must remain non-fatal and non-rollback, while making no directory-entry durability claim for that attempt. | `proposed`; the preparation diff includes the tests, but no exact-candidate hosted result is recorded, and targeted evidence is not Gate B. |
| Supported-platform Shadow lanes | Terminal supported-platform Shadow evidence on exact candidate source/artifact, including required macOS and Windows lanes. | `proposed`; one platform cannot infer another. |
| Release authenticity and bundle | GitHub verification of the signed annotated tag; exact successful public RC2 wheel and sdist; exact two-file SHA-256 manifest; and provenance attestations verified against downloaded subjects. | `proposed`; no publication or artifact exists. |
| Installed-package and parser matrix | Isolated exact-artifact installation, metadata and `RECORD` verification, plus declared-minimum and current `logseq-matryca-parser` checks, each bound to exact resolved versions. | `proposed`; no parser result selected or passed. |
| Gate B | Fresh exact-public-artifact campaigns for both `default-on` and `read-only-external` profiles, with preserved checkpoints, integrity/recovery review, and at least 259,200 valid seconds per profile. | `proposed`; setup, preflight, downtime, interruption, and historical time do not count. |
| Terminal release decision | Review all applicable exact-source, artifact, profile, platform, integrity, and receipt evidence; preserve failures and limitations. | `proposed`; no qualification PASS recorded. |
| Stable promotion | Separate maintainer decision for `v2.0.1`, followed by its own signed tag and publication authority. | `proposed`; RC2 preparation never authorizes stable promotion. |

## Execution and stop conditions

Before any expensive qualification activity, obtain an explicit resource-admission
decision and preserve isolated source, graph, cache, environment, evidence, and
profile roots. Public records must contain only public-safe identities, hashes,
statuses, counters, bounded timings, and terminal receipts; they must exclude graph
content, private paths, credentials, secrets, and raw logs.

Stop qualification on any mismatch in source, tag, manifest, attestation, wheel,
sdist, installed metadata, `RECORD`, parser resolution, profile, platform, graph
integrity, or receipt schema. Also stop on failed or unexpectedly skipped hosted CI,
targeted control failure, unexplained Shadow interaction, unexpected graph mutation,
or unavailable required platform. Preserve the failed or partial evidence. Do not
retry a campaign, credit interrupted time, or transfer RC1, historical RC2, or other
artifact evidence without a newly authorized exact-artifact attempt.

A post-replacement parent-fsync `OSError` has a narrower boundary: it is non-fatal to
the shipped `.env` replacement and never authorizes rollback, but the affected attempt
cannot claim directory-entry durability. Preserve that limitation with the attempt
evidence; do not infer a successful parent fsync from replacement success alone.

Only a later separate stable decision may interpret terminal RC2 evidence. This plan
does not select that source, publish RC2, run Gate B, or authorize `v2.0.1`.
