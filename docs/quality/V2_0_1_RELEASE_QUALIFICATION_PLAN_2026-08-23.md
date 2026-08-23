---
type: release-qualification-plan
title: v2.0.1 release qualification plan
description: Candidate-first, artifact-bound release plan for the bounded journal-day maintenance patch.
resource: docs/quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md
tags: [release, qualification, provenance, soak, v2]
last_verified: 2026-08-23
stale_after: 2026-11-21
status: draft
classification: active
canonical_for: release.v2.0.1-qualification
owner: release
authority: release-candidate-plan
---

# v2.0.1 release qualification plan

## Decision

Proceed with `v2.0.1-rc.1` as a **new patch candidate**, not as a re-publication of
`v2.0.0` and not as an immediate stable release. The candidate is necessary because
`main` contains a public read-surface change after `v2.0.0`: bounded canonical
`journal_day` retrieval. Its package and operational evidence must be collected
against the exact public candidate artifact.

This plan is a preparation and qualification contract. It records no publication,
package, CI, soak, security, or stable-promotion result in advance.

Public tracking is in [issue #531](https://github.com/MarcoPorcellato/matryca-plumber/issues/531).

## Candidate scope

Included:

- `read_graph_data(target_type="journal_day")` and its CLI route: one ISO-dated,
  canonical Logseq journal; strict path and regular-file checks; bounded
  digest-bound pagination; explicit status/provenance; no graph mutation and no
  Shadow initialization or dependency.
- Provider-free graph-outcome, interoperability, corrupt-derived-state, governance,
  and adaptive-retrieval evidence work already merged after `v2.0.0`.
- Documentation and release mechanics needed to make those boundaries inspectable.

Excluded:

- Any change to Markdown authority, the default-on external Shadow cache, Strict Read
  Only boundaries, parser baseline, or the parser-aware write plane.
- An enabled graph-native projection, adaptive runtime, external-provider integration,
  concurrent-writer qualification, real-agent benchmark, or new maintenance daemon.
- Any inference that historical `v2.0.0`, RC1, or RC2 evidence qualifies this candidate.

## Version and release records

| Stage | Git tag | Distribution version | Public state | Evidence boundary |
| --- | --- | --- | --- | --- |
| Current stable | `v2.0.0` | `2.0.0` | Published historical baseline | Its own source, package, and qualification records only |
| Candidate | `v2.0.1-rc.1` | `2.0.1rc1` | Not published until the tag workflow succeeds | Exact candidate tag, wheel, sdist, release workflow, runner, and two profiles |
| Stable promotion | `v2.0.1` | `2.0.1` | Not authorized by this plan alone | Candidate terminal evidence plus fresh stable publication proof |

The candidate changelog heading is exactly `[2.0.1-rc.1]`; the project version is
exactly `2.0.1rc1`. These forms are intentionally distinct because package metadata
uses PEP 440 while the public tag and curated changelog use the release tag form.

## Gate sequence

1. **Preparation PR.** Freeze the candidate source in a dedicated preparation PR.
   Verify version metadata, curated changelog extraction, lockfile, agent guide
   byte-identity, documentation inventory, links, and generated views. Required PR
   checks must be terminal green for the exact head.
2. **Candidate publication.** Signed-squash merge the reviewed preparation PR. Create
   and push signed tag `v2.0.1-rc.1` from the exact resulting `main` commit. The tag
   workflow must complete its source verification, package build, GitHub prerelease,
   and PyPI trusted publication.
3. **Artifact verification.** Independently bind the GitHub prerelease and PyPI wheel
   to the tag/source commit, filename, SHA-256, installed package metadata, `RECORD`,
   and `logseq-matryca-parser` 1.7.1. A release page or an installation alone is not
   sufficient evidence.
4. **Fresh Gate B qualification.** Start two independent restart-safe profiles against
   that installed public wheel: `default-on` and `read-only-external`. Freeze each
   runner and manifest outside the repository and vault. Require full source/working
   fingerprints, clean stderr, heartbeat/checkpoint continuity, attempt-chain
   integrity, completed cycles, and at least 259,200 valid seconds per profile. Setup,
   preflight, downtime, and interrupted attempts do not count.
5. **Terminal review.** Validate both terminal result bundles, including exact artifact,
   runner, profile, source/working fingerprint, attempt-chain, and recovery evidence.
   Preserve failed or interrupted attempts; never rewrite them to create continuity.
6. **Stable decision.** Only after all applicable rows are terminal may a separate
   stable-promotion decision prepare `v2.0.1`. It must use the exact stable source and
   publication evidence; this plan never grants an automatic stable tag.

## Operational safeguards

- Before any expensive local build, qualification, or recovery work, obtain an
  `Admit` decision from the current local resource-admission coordinator with no active
  or queued conflicting run. `Unknown` and `Deny` are holds.
- Keep the two profiles isolated by source copy, working copy, cache root, evidence
  root, virtual environment, and service label. Do not point a qualifier at a live
  graph.
- A host restart, service stop, disk-pressure hold, stale lease, or malformed
  checkpoint must fail closed, preserve all evidence, and resume only from a validated
  checkpoint. Never credit downtime.
- Store only public-safe hashes, counters, statuses, bounded timings, and digests in
  public records. Keep private paths, vault content, secrets, and raw logs out of the
  repository.

## Completion criteria

`v2.0.1-rc.1` is a qualified candidate only when its preparation PR, tag workflow,
GitHub prerelease, PyPI package, independent artifact verification, and both fresh
Gate B profiles meet the applicable gate definitions in the
[release qualification gate map](RELEASE_QUALIFICATION_GATE_MAP.md).

`v2.0.1` remains blocked until a later, explicit stable-promotion decision cites those
terminal candidate receipts and the exact stable publication evidence. Historical
`v2.0.0` records remain immutable context, never transferable proof.

## Related records

- [Public release and soak evidence policy](PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md)
- [Release qualification gate map](RELEASE_QUALIFICATION_GATE_MAP.md)
- [Gate B public-RC soak runbook](GATE_B_RC_SOAK_RUNBOOK.md)
- [v2.0.0 release record](../releases/v2.0.0-GITHUB.md)
- [Release process](../RELEASE_PROCESS.md)
