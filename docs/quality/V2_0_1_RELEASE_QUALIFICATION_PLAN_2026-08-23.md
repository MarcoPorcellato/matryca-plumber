---
type: release-qualification-plan
title: v2.0.1-rc.1 historical qualification plan
description: Historical, exact-artifact qualification plan for the published bounded journal-day prerelease.
resource: docs/quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md
tags: [release, qualification, provenance, risk, v2]
verified: { by: human:marco-porcellato, at: '2026-08-24T00:00:00Z' }
last_verified: 2026-08-31
stale_after: 2027-02-20
status: stable
classification: historical
audience: [maintainer, contributor, operator]
owner: release
authority: historical-release-candidate-plan
---

# v2.0.1-rc.1 historical qualification plan

## Historical candidate decision

`v2.0.1-rc.1` is a published **patch prerelease** for explicit evaluation. It is not a
re-publication of `v2.0.0`, an automatic stable promotion, or a claim that the
remaining candidate gates have passed.

This plan is frozen to release commit
`48eae93b1152c9fe7d1f19d63de3f781b686932e` and its recorded public artifacts.
The repository later advanced beyond those bytes, including runtime and assurance
changes. This plan therefore cannot authorize or qualify a stable release from a later
`main`; a newly selected candidate requires its own complete delta classification,
artifact binding, and gate decision.

The original plan required fresh 72-hour Gate B evidence for both runtime profiles.
The reviewed scope is now classified under the
[risk-based release qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md):
the source delta adds an isolated bounded read and provider-free evidence tooling
without changing durable or systemic behavior. Independent installation of the public
wheel nevertheless resolved `logseq-matryca-parser` 1.8.0 through the declared
`>=1.7.1,<2.0.0` range. Because parser implementation is common-path runtime code, the
effective candidate is Tier 2 and requires a minimum/current dependency matrix plus a
bounded exact-artifact canary. It does not require a new durability campaign unless
evidence reveals parser/graph-I/O semantic drift or another Tier 3 interaction.

Public tracking is in [issue #531](https://github.com/MarcoPorcellato/matryca-plumber/issues/531).

## Candidate scope and risk classification

Included:

- `read_graph_data(target_type="journal_day")` and its CLI route: one ISO-dated,
  canonical Logseq journal; strict path and regular-file checks; bounded character
  output with source-digest-reported stateless pagination; explicit status
  and provenance; no graph mutation and no Shadow query or initialization inside the
  handler. Ordinary CLI/MCP profile bootstrap may prepare Shadow before dispatch and
  must be measured separately.
- Provider-free graph-outcome, interoperability, corrupt-derived-state, governance,
  and adaptive-retrieval evidence work already merged after `v2.0.0`.
- Documentation and release mechanics needed to make those boundaries inspectable.

Excluded:

- Any change to Markdown authority, the default-on external Shadow cache, Strict Read
  Only boundaries, parser semantics, or the parser-aware write plane.
- An enabled graph-native projection, adaptive runtime, external-provider integration,
  concurrent-writer qualification, real-agent benchmark, or new maintenance daemon.
- Any inference that historical `v2.0.0`, RC1, or RC2 evidence qualifies this
  candidate.

**Classification:** Tier 2 — runtime or dependency. The `journal_day` source delta is
isolated read-only, but the public package's compatible dependency range resolved
parser 1.8.0 on 2026-08-24 rather than the v2.0.0 qualification baseline, 1.7.1. This
classification fails closed and must be raised to Tier 3 if source review, targeted
tests, package inspection, or profile smoke finds parser-semantic, Shadow, graph-I/O,
persistence, recovery, concurrency, lifecycle, default, security, or data-integrity
drift.

## Version and publication record

| Stage | Git tag | Distribution version | Public state | Evidence boundary |
| --- | --- | --- | --- | --- |
| Current stable | `v2.0.0` | `2.0.0` | Published stable baseline | Its own source, package, and qualification records only |
| Historical candidate | `v2.0.1-rc.1` | `2.0.1rc1` | Published prerelease on 2026-08-24 | Exact tag, commit, workflow, public artifacts, and incomplete selected Tier 2 gates |
| Stable promotion | `v2.0.1` | `2.0.1` | Not authorized by this plan | Requires a newly selected exact source, fresh classification, applicable terminal gates, and stable publication proof |

The immutable candidate publication facts are in the
[v2.0.1-rc.1 release record](../releases/v2.0.1-rc.1-GITHUB.md):

- release commit `48eae93b1152c9fe7d1f19d63de3f781b686932e`;
- terminal-success release workflow `32678905205`;
- public wheel `matryca_plumber-2.0.1rc1-py3-none-any.whl`;
- wheel SHA-256 `33e3ab646dfb2e442520d866ee3ab77abaf93796961fd7b29c96470319104901`;
- byte-identical GitHub Release and PyPI wheel evidence.

The curated changelog/tag form is `2.0.1-rc.1`; package metadata uses the PEP 440 form
`2.0.1rc1`.

## Applicable gate sequence

### Completed publication gates

1. **Preparation and exact-head CI.** Candidate source, version metadata, lockfile,
   changelog extraction, agent guide identity, documentation gates, and required PR
   checks were reviewed before publication.
2. **Annotated candidate publication.** The annotated tag contains an OpenPGP
   signature and points to the exact release commit. At publication GitHub reported
   hosted signature verification as `false` with reason `unknown_key`. After the
   existing public key was registered, GitHub verified the unchanged tag object as
   `true` with reason `valid` at `2026-08-31T00:02:20Z`. Tag object
   `5fe88d28aa35c761b45d2affb8e7d45c8ce9444e`, its target commit, and the published
   artifacts did not change. The release workflow built and published the GitHub
   prerelease and PyPI distribution.
3. **Public wheel parity.** The GitHub Release and PyPI wheel bytes have the same
   recorded SHA-256.

These facts prove publication and wheel parity only. They do not close the remaining
runtime gates.

### Independent package verification completed on 2026-08-24

The GitHub Release wheel was downloaded into a fresh temporary root and installed in
an isolated Python 3.12.13 environment. This receipt is deliberately summarized with
public-safe values only:

| Check | Result |
| --- | --- |
| Wheel | `matryca_plumber-2.0.1rc1-py3-none-any.whl` |
| Wheel SHA-256 | `33e3ab646dfb2e442520d866ee3ab77abaf93796961fd7b29c96470319104901` — matches the publication record |
| Installed package | `matryca-plumber==2.0.1rc1` |
| Resolved parser | `logseq-matryca-parser==1.8.0` |
| Installed `RECORD` SHA-256 | `a87535f2cef48ddeb0bd23960f72881f1922b6d5e1ab7cbae7384dbe3153bdc9` |
| `RECORD` verification | 251 rows; 250 hashed files checked; 0 mismatches |

This closes wheel integrity and installed-package binding for that environment only.
It does not prove supported-platform behavior, minimum-dependency compatibility, or
the two runtime profiles.

### Remaining Tier 2 gates

1. **Minimum/current dependency matrix.** Exercise the candidate with parser 1.7.1,
   which is the declared minimum and historical v2.0.0 baseline, and parser 1.8.0,
   which a fresh public-wheel install resolved on 2026-08-24. Bind each result to the
   exact package versions. A future compatible parser requires a new current-version
   row; it cannot inherit the 1.8.0 result.
2. **Supported-platform `journal_day` matrix.** Run the targeted journal reader,
   dispatch, CLI, and Strict Read Only immutability tests on Linux, macOS, and Windows
   for the exact candidate source/package path selected by the receipt. Every job must
   be terminal green; an unavailable platform is `partial`, not an inferred pass.
3. **Bounded dual-profile package canary.** Exercise isolated disposable graphs using
   the exact public wheel in both
   `default-on` and `read-only-external` profiles. Each profile must complete two
   consecutive cycles. Each cycle includes one Shadow-on and one explicit Shadow-off
   attempt, for four passing attempts per profile, plus the candidate `journal_day`
   read. Require clean stderr, no graph mutation, no Shadow activity attributable to
   the handler beyond the profile's measured control startup, and matching
   source/working fingerprints.
4. **Terminal review.** Recheck exact artifact, environment, profile, attempt sequence,
   test results, stderr, graph integrity, and limitations. Preserve failures and
   partial results; do not rewrite evidence to create continuity.
5. **Stable decision.** Only after all applicable rows are terminal may a separate
   maintainer decision prepare `v2.0.1`. The stable tag and publication remain a fresh
   authority gate.

The bounded canary does not claim reboot recovery, restart durability, or 72-hour
operational qualification. Historical v2.0.0 Gate B evidence remains relevant design
history but is never transferred to this candidate.

## Escalation and stop conditions

Stop immediately on any mismatch in source, tag, wheel, digest, metadata, `RECORD`,
profile, parser resolution, graph fingerprint, or receipt schema. Also stop on an
unexpected skip, non-terminal CI result, stderr failure, graph mutation, Shadow side
effect from `journal_day`, or unexplained runtime behavior.

If a failure implicates Shadow persistence, watcher/recovery, concurrency, external
Read Only cache, parser or graph-I/O semantics, write behavior, service lifecycle,
migration, defaults, security, or data integrity, reclassify the candidate as Tier 3
and start fresh exact-artifact Gate B qualification. Do not credit Tier 2 canary time
toward the 259,200-second requirement.

## Operational safeguards

- Before expensive local work, obtain `Admit` from the current local
  resource-admission coordinator with no conflicting active or queued run. `Unknown`
  and `Deny` are holds.
- Keep source copy, disposable graph, cache root, evidence root, virtual environment,
  and profile identity isolated. Never point a qualifier at a live graph.
- Preserve evidence across interruption. Resume only when the receipt and exact
  artifact bindings remain valid; otherwise start a linked fresh attempt.
- Retain only public-safe hashes, counters, statuses, bounded timings, and digests in
  repository records. Exclude private paths, graph content, secrets, and raw logs.

## Completion criteria

`v2.0.1-rc.1` would have become a qualified Tier 2 candidate only if the exact-package,
minimum/current dependency, supported-platform, bounded dual-profile, integrity, and
terminal-review rows above are all terminal `PASS` for their declared scope.

Those gates remain incomplete in this historical plan. A future `v2.0.1` decision must
start from a newly selected exact source and cannot use RC1 evidence to qualify later
bytes. A Tier 2 pass would not create a 72-hour reliability claim; a Tier 3
classification restores the full soak gate.

## Related records

- [Risk-based release qualification decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md)
- [Public release and soak evidence policy](PUBLIC_RELEASE_AND_SOAK_EVIDENCE_POLICY.md)
- [Release qualification gate map](RELEASE_QUALIFICATION_GATE_MAP.md)
- [v2.0.1-rc.1 release record](../releases/v2.0.1-rc.1-GITHUB.md)
- [Gate B public-RC soak runbook](GATE_B_RC_SOAK_RUNBOOK.md)
- [v2.0.0 release record](../releases/v2.0.0-GITHUB.md)
- [Release process](../RELEASE_PROCESS.md)
