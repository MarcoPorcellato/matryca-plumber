---
type: release-qualification-disposition
title: v2.0.1-rc.2 terminal failed-publication disposition
description: Historical disposition for the signed v2.0.1-rc.2 tag and workflow that verified and built artifacts but published neither destination.
resource: docs/quality/V2_0_1_RC2_RELEASE_QUALIFICATION_PLAN_2026-08-31.md
tags: [release, qualification, provenance, history, v2]
last_verified: 2026-08-31
stale_after: 2027-02-27
status: historical
classification: historical
audience: [maintainer, contributor, operator]
owner: release
authority: release-candidate-disposition
related:
  - ../releases/v2.0.1-rc.2-FAILED-PUBLICATION.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - EVIDENCE_INDEX.md
---

# v2.0.1-rc.2 terminal failed-publication disposition

## Terminal status

`v2.0.1-rc.2` is no longer an active proposed qualification path. It is a valid
signed annotated tag and a terminal failed-publication attempt. Its authoritative
record is the [failed prerelease publication record](../releases/v2.0.1-rc.2-FAILED-PUBLICATION.md).

It is not a GitHub Release, a PyPI package, a public candidate artifact, a Gate B
result, or stable-promotion credit. Its evidence is immutable and cannot qualify
another release candidate, including RC3.

## Immutable attempt facts

| Fact | Recorded value |
| --- | --- |
| Annotated tag object | `17f7e7e58f3bebcfbcfc64377c9278599c61ad38` |
| Tag target | `11cc2ab897862d853b7e85119e2e1ba1ff738298` |
| Release workflow | `33350501687` |
| Ephemeral bundle artifact ID | `9743491462` |

The workflow passed signed-tag and source verification, destination preflight,
distribution build, provenance attestation, bundle download, digest verification,
and attestation verification. GitHub Release creation then failed because the
checkout-free job invoked `gh release create --verify-tag` without explicit
`--repo`; GitHub CLI attempted local repository discovery where no checkout existed.
PyPI publication was skipped.

## Recovery boundary

Do not rerun or reinterpret this attempt. A later candidate needs its own selected
source, signed annotated tag, destination preflight, build, attestation, artifact
verification, publication authority, qualification evidence, and terminal decision.
The tested workflow correction binds release creation with
`--repo "$GITHUB_REPOSITORY"`; that correction does not turn RC2 into a published
or qualified artifact.

The operator `.env` parent-directory fsync and maintenance-robot Git commit-path
isolation controls that motivated the former RC2 preparation remain candidate-specific
controls. They require fresh exact-source evidence for any later candidate.
