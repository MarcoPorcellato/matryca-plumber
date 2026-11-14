---
type: Roadmap
---
# Experimental 2.1.0a4 release qualification plan

Date: 2026-11-14. Status: **preparation only; no final source selected or publication authorized**.

## Authority and outcome

This is the active preparation plan for package `2.1.0a4`, prospective signed tag
`v2.1.0-alpha.4`, and changelog heading `[2.1.0-alpha.4]`. It supersedes the
[alpha.3 plan](V2_1_0A3_RELEASE_QUALIFICATION_PLAN_2026-10-22.md) as active guidance,
without rewriting its evidence or the
[published alpha.3 producer handoff](OG_OPERATIONAL_V1_ALPHA3_PUBLIC_HANDOFF.md).
The [release process](../RELEASE_PROCESS.md),
[risk-based decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md),
[RC4 supersession record](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md) and
[issue #582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582) remain authoritative.

The outcome is an independently verified experimental release and public-byte
handoff, followed by an inventory of the unfinished stable-release obligations.
It is not stable promotion, a large-graph performance claim, DB support, operating
system network isolation, or new Trama admission. Trama remains on its exact
previously admitted alpha.3 synthetic tuple. No user graph is accessed.

## Release delta and preserved boundaries

- PR #659 clarifies read-only bootstrap guidance; PR #663 bounds Linux/macOS
  dashboard/identity work to 1800 seconds plus one five-second cleanup deadline
  with effective cancellation. This contains work; it does not prove the
  historical 1,115-page dashboard timeout is resolved. Windows behavior is unchanged.
- PR #665 explains graph-local catalog scope and checkpoint progress through four
  additive bootstrap fields, without changing legacy keys, Soft Gate, read-only
  policy, catalog truth or external Shadow status. It replaces #664 with identical content.
- PR #666 corrects the three scoped build/test alerts: isolated builder
  `setuptools` 84.1.0 and frontend test closure 5.0.3. Vite, application dependencies
  and frontend compiled bytes remain unchanged. All three alerts must be fixed,
  not dismissed, before tagging. New findings or failed gates are not waived automatically.
- PR #668's signed squash `4fdee5d30006f70caa8a0645101d6b14e70a47c7` (tree
  `c378b160ad3d3de230c0288dfb1316433c4738e8`) corrects alert #107 with
  `minimatch` 11.0.1, its required non-recursive dependency 1.1.0, and `Zod`
  4.6.6 only. Parent package versions, Python/runtime and resource inputs did not change;
  Vite 8.3.3 and Vitest 5.0.3 are unchanged. A seven-asset frontend comparison found identical
  paths, modes and bytes; this is not wheel or sdist evidence. The recorded audit
  returned zero findings, #107 was fixed rather than dismissed at
  2026-11-14T07:00:45Z, and the complete open-alert query was empty on 2026-11-14.
  Recheck alert state before tag selection; these dated observations do not
  authorize another dependency update or qualify alpha.4 artifacts.
- Generic publication/verification tooling and operator documentation already on
  main are included. Historical alpha.1/alpha.2 failures, alpha.3 producer source,
  original wheel/sdist, attestations and evidence remain immutable.
- Packaged schemas, fixture bytes, golden topology, TCK cases and hash-locked
  Parser 1.9.0 requirements stay unchanged. `qualification: unqualified`, matrix
  `planned`, and other static labels are not promoted by external test results.

## M0 — replacement and security prerequisites

Completed source integrations, to be freshly reverified before later actions:
PR #665 signed squash `159160736a4f9a6ea565cb5af90c0a5c307f9244` and PR #666 signed
squash `9d3d9618e3c3cc201a75e296d5755345513001d0`. The latter tree is
`5f5a3c3c1eec28f693d700eb8ee55d4f6b71d369`. Branches and prior evidence are retained.
PR #668 is the later scoped correction recorded above. Alerts #103, #104, #106
and #107 were observed fixed, not dismissed; the complete open-alert query was
empty at the recorded 2026-11-14 observation. Refresh alert state before tag
selection. For exact source `4fdee5d30006f70caa8a0645101d6b14e70a47c7` and
tree `c378b160ad3d3de230c0288dfb1316433c4738e8`, post-merge CI run
`43569039183`, CodeQL run `43569039198`, and Windows run `43569039293` all
completed successfully. These checks do not constitute final alpha.4
qualification or select its final source or public artifact.

## M1 — prepare one release candidate PR

1. Change only project metadata/root-lock version to `2.1.0a4`; retain dependency
   records and verify the lock offline. No opportunistic updates or Parser adoption.
2. Use `python -m scripts.regenerate_og_resource_chain` to refresh the packaged
   project version/root-lock hash, then propagate the dependency-profile digest
   through manifest and descriptor. The command rejects a broken input chain and
   symlink inputs; it is a maintainer operation, not a qualifier.
3. Require explicit public release tag, source tree and tag object at dispatch;
   remove implicit alpha.3 acquisition defaults. Preserve `ALPHA3_TARGET` and the
   exact historical recovery route. Wrong-source/tag negatives remain fail-closed.
4. Update README, mirrored llms surfaces, onboarding, release process, navigation
   and generated prompt. Consolidate Unreleased into the alpha.4 section and leave
   a fresh empty Unreleased section. Do not alter historical changelog sections.
5. Verify focused regressions, formatting, lint, typing, security, documentation,
   inventory, resource chain, tag routing and extracted notes. Full hosted CI is
   authoritative; do not run CCP heavy qualification. Review the frozen diff once
   independently, then sign, push and open the preparation PR.

Every merge requires the maintainer's `merge #N`, fresh exact head/base, terminal
green hosted CI, expected skips, valid signatures, accepted review and exact scope.
No bypass, force-push, branch deletion or automatic merge is permitted.

The resource digests change as follows; verify them again on the final candidate:

| Resource | Prior SHA-256 | Prepared SHA-256 |
| --- | --- | --- |
| dependency-profile | `9064e339a2fa5e58ce2d49e64b896865dd3a80615b8f5dbd5391c404cde83e92` | `03c4e684a4dae32c244fe3c25beba8504d66a91ccd71d5fc857a9a0cfb23ebde` |
| manifest | `a630e5cb3c70eaa8441e63916b6b0e31e2b8f1f7a6457d5c2c8c1a04b1da9ef9` | `c625268cc015f1d15016077a7161d8e09ab2eeabe40bf1a4354e56ad5b171d59` |
| descriptor | `bcc6ac607706e934e5df4e044802aa74c7d7455e7711220df116080f1ab0cc70` | `d13becfdabb2de790bef1d06c01017d34c941254bdbdd62741b2330f9a41965b` |

## M2 — two non-publishing pre-tag checks

After the preparation PR's explicit merge, select the clean, signed current main
commit/tree, and preserve its CI and independent review evidence. Keep main fixed
through tagging; a change invalidates the selection and requires requalification.

- Dispatch `og-profile-qualification.yml` once on that exact main. Require all
  eight installed rows: Linux x86_64 and macOS arm64, each on CPython 3.12 and 3.13,
  with original wheel and original sdist installation paths. Source controls,
  Windows refusal, complete reports and aggregate must pass. Windows refusal is
  a negative control, not Windows installed-package qualification.
- Rehearse the generic public verifier once using explicit alpha.3 producer
  source/tree/tag object/publication-run inputs, with the newly selected verifier
  source authenticated separately. The published alpha.3 inputs remain
  `8c30f70e217722e719c5aedc322219ebccb87e68`,
  `de80d0473aa281c52d0fed10b4561024dd12d76f`,
  `c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24`, publication run `39887297548`.
  Use the explicit recovery selector where required by the reviewed workflow.
  This proves verifier behavior on those bytes, **not alpha.4 qualification**.
  If the workflow cannot express that separation, stop rather than force it.

No new tag, package publication or Trama post follows from either run. Retain run,
attempt, job and artifact identities and complete sanitized report evidence.

## M3 — exact tag handoff and separate publication consent

Show the maintainer the full selected commit/tree, exact source/CI/review results,
alert state, and signed-tag command. Creating or pushing `v2.1.0-alpha.4` requires
explicit consent on that source, acknowledging that the push triggers GitHub
Releases and PyPI. Until then, publication remains inactive.

Once separately authorized, verify absence of conflicting tags/version files,
source and policy anchors, and remaining gates. Create and verify the signed
annotated tag with the existing maintainer key, then push only that tag. Do not
re-sign, repoint, retry publication or re-run its workflow on a failure. Preserve
partial-publication facts and stop. Never change GPG configuration implicitly.

## M4 — actual public-byte verification

After terminal successful publication, one public qualification campaign verifies
the six GitHub assets, the two original PyPI distributions, attestations and
cross-registry byte parity. Repeat full installed metadata, RECORD, resources,
import-origin, static and operational TCK checks across all eight rows. Authenticate
producer and verifier independently; never substitute diagnostic archives or a
locally rebuilt wheel. A verifier defect stops the campaign with retained logs;
any repeat requires a separately allowed repair cycle, never retagging or republishing.

## M5 — public handoff and stable-track inventory

Publish a concise alpha.4 evidence handoff bound to the actual public bytes and
producer source. Only after successful public verification, direct experimental
users to `pip install matryca-plumber==2.1.0a4` (or the equivalent exact-version
managed-tool invocation). Plain installation still follows the stable release;
`--pre` alone does not pin this evidence tuple.

Prepare a one-page private inventory under #582 of Windows installed launcher/
package qualification, full three-platform Stage A and the separately governed
dual-profile Gate B (259,200 valid seconds per profile). Record evidence and unknown
effort honestly; alpha.4 does not complete those obligations. Do not post to Trama,
change its pin/admission, implement a real adapter, or access user graphs.

## Execution and stop rules

Use existing bounded execution mechanisms, command deadlines, output bounds and
the 20 GB free-space floor plus 1 GiB reserve. Preserve logs, failed attempts and
branches. Local Beads is advisory scheduling; this plan and release policy remain
authoritative. Keep one writer per overlapping path and one lifecycle owner.

Work by milestone, not hash-bound per-step envelopes. Correct a tooling false
positive only when criteria, source scope and evidence semantics are unchanged;
record it, with no new observer/controller. Real repairs remain limited to three
cycles per milestone where authorized. A CI failure, new security finding,
signature/hash/provenance mismatch, scope expansion, exhausted budget or uncertain
cleanup is a stop, not a silent retry or waiver. GPG unavailability needs local
unlock, not an unsigned substitute. Report at milestone boundaries.
