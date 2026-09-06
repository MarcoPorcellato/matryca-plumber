---
type: evidence-index
title: Public quality evidence index
description: Bootstrap index of bounded, source-backed claims for Matryca Plumber.
resource: docs/quality/
tags: [quality, evidence, release, governance]
last_verified: 2026-08-24
stale_after: 2027-02-20
status: draft
classification: canonical
canonical_for: quality.evidence-index
owner: quality
authority: evidence-index
---

# Public quality evidence index

This is a bootstrap index, not certification, an audit opinion, or an AAIF
submission. It records claims that can be traced to local, versioned source
documents. A `verified` row means that the cited source states and bounds the
claim; it does not extend the source's scope or replace a fresh qualification.

## Claim-record schema

Each record uses the following stable fields:

| Field | Meaning |
| --- | --- |
| Claim ID | Stable public identifier; do not reuse it for a different claim |
| Claim | Plain-language statement with an explicit boundary |
| Scope | Product, version, platform, artifact, or document scope |
| Authority | Maintained source that owns the claim |
| Source evidence | Exact local path, command, workflow, artifact, or digest when available |
| Status | `verified`, `partial`, `proposed`, `historical`, `external gate`, or `blocked` |
| Limitations | What the record does not establish |
| Review date | Date on which the row must be reviewed again |

Receipts must remain public-safe: no credentials, private filesystem paths, raw
user graph content, or unbounded logs.

## Seed records

| Claim ID | Claim | Scope | Authority | Source evidence | Status | Limitations | Review date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `V2-RELEASE-001` | Stable v2.0.0 is the external Shadow read-path release; Markdown remains authoritative and unhealthy Shadow falls back to Markdown-backed BM25 reads. | v2.0.0 stable | `docs/releases/v2.0.0-GITHUB.md`; `docs/knowledge/architecture/shadow-db.md` | Local release record names release commit `987446b8337f7abd308a9efe4abb834ce1acdc1b`; wheel SHA-256 `d3247aa1f4c2ea802c0bd94b180df61fef8d3f1faf62e0f3b920e483f74c4653`. | `verified` | Does not qualify future source changes, universal performance, or external review. | 2026-11-17 |
| `V2-SHADOW-CONTRACT-001` | Logseq Markdown is the source of truth; Shadow is disposable derived state, external to the graph under the current contract, and Strict Read Only blocks graph-local mutation while permitting validated cache maintenance. | Current v2 Shadow operator contract | `docs/knowledge/architecture/shadow-db.md` | Local contract table and health/fallback sections; implementation references `src/shadow/`. | `verified` | Does not prove concurrent-writer safety, a clean cache, or qualification on an unpinned checkout. | 2026-11-17 |
| `DOCS-VALIDATION-001` | The repository has blocking documentation checks for the knowledge bundle and generated inventory, plus agent-path/coherence checks. | Current repository checkout | `Makefile`; `.github/workflows/ci.yml` | `make docs-check` runs `scripts/docs_knowledge_check.py check-bundle`; `make agents-check` runs `scripts/check_agents_coherence.py`; CI invokes both. | `verified` | A passing local check is not proof that every public link, release, or remote workflow is current. | 2026-11-17 |
| `GATE-B-RC2-001` | The recorded RC2 Gate B campaign passed its two named profiles against the exact public RC2 artifact. | Historical v2.0.0 RC2 artifact | `docs/quality/GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`; `docs/quality/GATE_B_RC_SOAK_RUNBOOK.md` | Local terminal evidence and runbook identify exact-artifact binding, two profiles, checkpoint/recovery proof, and 417-cycle evidence. | `historical` | RC evidence does not transfer to stable or later source; each profile and artifact require independent requalification. | 2026-09-19 |
| `V2-STABLE-QUAL-001` | The local stable release record preserves the v2.0.0 readiness and publication evidence pointers, including cross-platform Shadow checks and artifact digests. | v2.0.0 stable publication record | `docs/releases/v2.0.0-GITHUB.md`; `docs/quality/issue-bodies/v2-rc-stable-readiness.md` | Local release record points to the readiness record, release workflow, GitHub release tag, and PyPI artifact. | `partial` | Publication and external service state are independent gates and must be freshly checked for a new release. | 2026-09-19 |
| `PUBLIC-EVIDENCE-POLICY-001` | Public release and soak evidence is classified, redacted, retained, and reviewed by exact source, artifact, runner, profile, and terminal-result boundaries. | Current quality policy | `docs/quality/PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md` | Evidence-class table, public-safe field rules, immutable attempt-chain rules, and retention matrix. | `verified` | The policy does not independently qualify a release, a CI run, a soak, or external review. | 2026-11-17 |
| `RELEASE-RISK-001` | Release gates are selected by the documented change-risk tier while every result remains bound to exact source, artifact, platform, runner, and terminal receipt. | Current release qualification policy | `docs/quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md`; `docs/quality/RELEASE_QUALIFICATION_GATE_MAP.md` | Canonical decision and reusable Tier 0–3 matrix. | `verified` | Does not authorize a release, transfer historical evidence, or make a Tier 1 smoke a durability claim. | 2027-02-20 |
| `V2-0-1-RC1-PUB-001` | `v2.0.1-rc.1` is a public prerelease bound to release commit `48eae93b1152c9fe7d1f19d63de3f781b686932e`; its GitHub and PyPI wheel bytes share SHA-256 `33e3ab646dfb2e442520d866ee3ab77abaf93796961fd7b29c96470319104901`. | Historical v2.0.1-rc.1 publication | `docs/releases/v2.0.1-rc.1-GITHUB.md` | Annotated tag object `5fe88d28aa35c761b45d2affb8e7d45c8ce9444e` with an embedded OpenPGP signature, release workflow `32678905205`, GitHub prerelease, PyPI `2.0.1rc1`, and wheel parity record. | `historical` | At publication GitHub reported signature verification `false` with reason `unknown_key`; since public-key registration on 2026-08-31 it reports `true` with reason `valid` for the unchanged tag object and target. Signature verification, publication, and byte parity do not complete the remaining Tier 2 runtime gates, authorize stable `v2.0.1`, or qualify any later `main`. | 2027-02-20 |
| `V2-0-1-RC1-PKG-001` | The public `v2.0.1-rc.1` wheel passed an independent isolated install and installed-file integrity check. | Historical GitHub Release wheel on Python 3.12.13, checked 2026-08-24 | `docs/releases/v2.0.1-rc.1-GITHUB.md`; `docs/quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md` | Wheel SHA-256 `33e3ab646dfb2e442520d866ee3ab77abaf93796961fd7b29c96470319104901`; installed `2.0.1rc1`; parser `1.8.0`; `RECORD` SHA-256 `a87535f2cef48ddeb0bd23960f72881f1922b6d5e1ab7cbae7384dbe3153bdc9`; 250 hashed files checked with 0 mismatches. | `historical` | Proves package integrity for one isolated environment only; its incomplete parser, platform, and dual-profile gates do not transfer to a later source or artifact. | 2027-02-20 |
| `V2-0-1-RC2-PLAN-001` | RC2 is a terminal failed-publication attempt, not an active candidate plan or a public artifact. | Historical v2.0.1-rc.2 attempt | `docs/quality/V2_0_1_RC2_RELEASE_QUALIFICATION_PLAN_2026-08-31.md`; `docs/releases/v2.0.1-rc.2-FAILED-PUBLICATION.md` | Annotated tag object `17f7e7e58f3bebcfbcfc64377c9278599c61ad38`, target `11cc2ab897862d853b7e85119e2e1ba1ff738298`, workflow `33350501687`, and ephemeral bundle artifact `9743491462`. | `historical` | Source, destination-preflight, build, attestation, and bundle verification passed, but GitHub Release creation failed without explicit `--repo`, PyPI was skipped, and no release, package, Gate B, or stable credit exists. This evidence cannot transfer to RC3. | 2027-02-27 |
| `V2-0-1-RC3-PLAN-001` | The proposed RC3 plan selects Tier 3 qualification for `.env` parent-directory fsync durability, maintenance-robot Git path isolation, and explicit repository binding for checkout-free GitHub Release creation. | Future v2.0.1-rc.3 candidate | `docs/quality/V2_0_1_RC3_RELEASE_QUALIFICATION_PLAN_2026-08-31.md`; `docs/quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md`; `tests/test_release_workflow_contract.py` | Preparation base `f91ba540fdb8c01f2ca5ccb30cedf71b6136b556`; focused control set includes both fsync paths, robot isolation, and release-workflow contract coverage for `--repo "$GITHUB_REPOSITORY"`. | `proposed` | Candidate source, tag, workflow run, public artifact, hosted CI, package matrix, Gate B, publication, and stable decision remain unselected or unrecorded. Gate B requires 259,200 valid seconds per profile and is outside current authorization. RC1 and RC2 evidence is historical and non-transferable. | 2027-02-27 |
| `LOGSEQ-DB-CLI-ARTIFACT-001` | The first exact bundled-CLI attempt stopped before execution because the selected official Logseq nightly macOS arm64 application failed Apple code-signature verification. | Logseq nightly 20260826 ZIP, macOS arm64, observed 2026-09-06 | `docs/quality/LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md` | GitHub asset `530968220`, size `168418244`, GitHub/checksum-list/local SHA-256 `f3cbaff017f2063a68583d9ca885aa1e52f1e324df98ea4fcb24c75fee2c244d`; strict signature verification failed after two extraction methods. | `blocked` | This is artifact-admission evidence only. No Logseq executable, fixture, graph read, transport, Plumber adapter, or DB compatibility claim was exercised. | 2026-12-05 |
| `V2-0-1-RC3-PUB-001` | `v2.0.1-rc.3` is a public historical prerelease. | Historical v2.0.1-rc.3 publication | `docs/releases/v2.0.1-rc.3-GITHUB.md` | Annotated tag target `0506d975fe697646e5165db1505ee93a67041801`; wheel SHA-256 `24ab8c3c00b2e5ad977f5ef606dd412106d1b94554254f73c6f524a05217cf5a`; sdist SHA-256 `347fa232d76fe8bac6a62abd43fbb29d8966cd2aa5250c6c02b9563e92b06b09`. | `historical` | Publication does not qualify current source, RC4, Logseq DB capability, a transport surface, Gate B, or stable `v2.0.1`. | 2027-03-06 |
| `V2-0-1-RC4-PREP-001` | RC4 preparation packages static public contract/TCK bytes and retains the bounded internal OG topology slice. | Proposed v2.0.1-rc.4 preparation | `docs/quality/V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md`; `scripts/build_release_artifacts.py` | Begins at `00b56329ed9b44e6d1e0ab0a2b83afac502b5ba2`; #579; archive gate requires all three contract families and their TCKs. | `proposed` | No candidate, tag, public artifact, runtime DB support, transport, consumer wiring, UI, LENS, Gate B, or stable decision is selected. | 2027-03-06 |

## Review rules

Refresh a row when its source commit, artifact, workflow contract, platform
matrix, or review date changes. Keep historical rows intact and add a new ID
when the claim's scope changes. `partial`, `blocked`, `external gate`, and
`historical` are not release PASS states. This index itself does not certify
AAIF readiness; any AAIF review or decision remains an external gate.
