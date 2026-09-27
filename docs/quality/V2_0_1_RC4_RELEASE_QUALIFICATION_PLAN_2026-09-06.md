---
type: release-qualification-plan
title: v2.0.1-rc.4 release qualification plan
description: Two-stage exact-artifact qualification for RC4; pre-publication gates precede the public-wheel Gate B campaign and final decision.
resource: docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md
tags: [release, qualification, parser, topology, contracts, v2]
last_verified: 2026-09-27
stale_after: 2027-03-26
status: proposed
classification: active
audience: [maintainer, contributor, operator]
owner: release
authority: release-qualification-plan
related:
  - V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md
  - GATE_B_RC_SOAK_RUNBOOK.md
  - LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
---

# v2.0.1-rc.4 release qualification plan

## Authority and current-source boundary

This proposed plan is tracked by
[#582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582). It is
separate from the implementation and package-preparation authority in
[#579](https://github.com/MarcoPorcellato/matryca-plumber/issues/579).

The original planning anchor was `origin/main@118b265b5c6b29682c76453aad5fbde0de0c841f`;
it was not a candidate. Issue #582 subsequently selected
`74884c38edb9cae445fa465969aa2c9cee5ecd1c` and recorded source, hosted-CI,
build, installed-resource, and TCK evidence for those exact bytes. That candidate
remains historical evidence. Protected `main@50d3fc9f34c0c88d054a5abc8fcacad8b1da5b6f`
on 2026-09-27 is 18 commits later, with product and release-workflow changes. The
earlier hashes and passes cannot qualify current `main`. This commit is an observed
source anchor, not a newly selected candidate; reverify it immediately before use.

For a current-source RC4, first merge any release-plan correction, then select the
resulting exact, reachable, clean `main` commit. Record full commit and tree IDs,
source provenance, version and lock, changelog-to-source agreement, and wheel/sdist
filenames and SHA-256 values. Resolve post-RC4-heading `Unreleased` changes before
freezing release notes. A subsequent source change requires a new selection and an
applicability review of every candidate-bound result.

No current-source candidate, public RC4 artifact, Gate B result, or final RC4
qualification decision is selected by this plan. It creates no tag, GitHub Release,
PyPI upload, hosted workflow run, or local qualification attempt; it authorizes no
heavy Gate B/CCP invocation.

Historical RC3 publication, RC2 failure, and earlier Gate B evidence remain bound to
their own artifacts. They do not qualify RC4 or a future stable `v2.0.1`.

## Complete RC4 delta classification

The delta is assessed against the last qualified public artifact, not against an
unpublished preparation commit. The original rows remain applicable. A current-main
candidate must also disposition every post-`74884c38` change; the additional rows
below name the currently observed categories, not evidence that they passed.

| Delta | Release-relevant behavior | Required control | Tier effect |
| --- | --- | --- | --- |
| Parser 1.9 snapshot | Plumber selects Parser 1.9 internally and calls `LogseqGraph.from_snapshot_pages()` for a bounded graph-wide snapshot. | Exact dependency resolution; parser-factory, bounded-snapshot, strict reference/title-collision, and source-provenance tests. | Parser/graph-I/O semantics: Tier 3. |
| Process timeout lifecycle | Pathological parser work is killed/recycled deterministically; no stale result crosses the process boundary. | Controlled seam/fake tests for timeout, terminate/recycle, result rejection, and later successful work. | Service lifecycle/recovery: Tier 3. |
| topology session | A Plumber-owned, session-bound read projection maps resolved wikilinks/block references into complete topology. | Complete-node/edge, closed-session, foreign-graph, incomplete-topology, strict-failure, and no-aggregated-page-ref tests. | Graph I/O/session semantics: Tier 3. |
| static contract/TCK resources | Three public, content-free contract families and their deterministic TCK scripts ship in wheel and sdist. | Archive membership/byte parity, installed-resource discovery, installed TCK, metadata, and `RECORD` checks. | Distribution change; included in the overall Tier 3 envelope. |
| Logseq DB policy | Capability discovery fixtures and protocol are test-only and unbound. | Negative protocol fixtures; inspect package/runtime imports to prove no DB adapter, transport, direct internal access, or capability claim. | No DB runtime support is introduced; it cannot lower the overall tier. |
| #580 external evidence | The first official bundled-CLI attempt is `upstream_blocked` at executable admission. | Preserve the artifact record as blocked; do not substitute it for runtime or DB compatibility evidence. | No executable/DB behavior was tested; no qualification credit. |
| OG read-port selection | The internal graph repository selection was characterized and refactored after the earlier candidate. | Run exact-candidate characterization, Shadow fallback, filesystem ownership, and read-path regressions. | Graph I/O remains Tier 3. |
| DB observer structure | An in-memory structural validator was added, while CLI, SDK, and MCP stdio DB-0 lanes remain blocked or no-go. | Run synthetic parser/bounds and negative capability-policy controls; prove no host access, DB read adapter, or supported DB claim. | No DB runtime support; include the new code in package and import review. |
| Frontend dependencies | A later dependency-group update changed the lock and direct manifest versions. | Recheck exact locked install, frontend tests/build, and high-severity audit before candidate selection. | Dependency/security review; no Tier 3 downgrade. |
| Hosted workflow pins | CI, CodeQL, dependency-update, and release action pins changed. | Verify exact-source workflow contract, required hosted checks, expected conditional skips, and tag-workflow provenance. | Publication control; no historical workflow result transfers. |
| Documentation and media | Later gateway research, policy, and overview content changed without adding a supported DB transport. | Check generated inventory, documentation gate, release notes, and claim boundaries. | No runtime credit or tier reduction. |

The release is **Tier 3** because the candidate delta changes Parser and graph-I/O
semantics and a process timeout lifecycle. The Tier 3 classification applies even
though the DB policy is test-only/unbound and the static resources are content-free.
No downgrade is available under this plan without a new reviewed decision.

## Candidate selection and source gates

After separate merge authority selects the candidate, record the following before
any RC4 tag or publication action:

1. Exact commit/tree, ancestry from protected `main`, clean worktree, version
   agreement (`2.0.1rc4` / `v2.0.1-rc.4`), dependency lock, and no uncommitted
   generated-resource drift; reconcile `Unreleased` entries that describe code
   included in that source with the RC4 release notes.
2. Terminal required hosted CI for that exact commit. Record workflow/run URLs,
   required-check names, conclusions, and any explicit non-blocking lane; a local
   pass is not a hosted-CI substitute.
3. One exact release build from the selected source. Record exactly one canonical
   wheel and one canonical sdist, each filename, size, SHA-256, build command,
   and archive manifest. Reject missing, additional, compiled-cache,
   version-drift, or resource-drift members. This is evidence for the exact
   artifacts built in that attempt; unless independent reproducibility tests
   separately prove it, do not call the result a reproducible build.
4. Isolated package checks. Install the canonical wheel directly and verify
   package metadata, `RECORD`, all 26 static contract/TCK resources, and
   byte-for-byte source/wheel/sdist parity. For the sdist installation, first
   authenticate the original sdist; use a private PEP 517 build environment
   whose complete observed package-name/version manifest is recorded before
   and after; check static `build-system.requires` and backend-returned dynamic
   requirements against packages already present, failing rather than
   opportunistically installing a missing requirement; then run
   `uv build --wheel --no-build-isolation` from that exact sdist. Bind the
   temporary wheel name, size, and SHA-256, keep it outside canonical `dist`,
   and install it with `--no-deps` into the separate sdist runtime environment.
   The installed verifier must receive the original bound sdist as its artifact
   input, not the temporary wheel. Run all three installed TCKs from the
   installed package context; source-checkout success alone is insufficient.

### Conditional on-demand Stage A procedure

The proposed manual workflow at
`.github/workflows/release-package-qualification.yml` is an implementation
deliverable, not authority supplied by this plan. Use this procedure only after
that workflow has landed on protected `main` and is available for dispatch. Its
merge changes the source: select the resulting exact, reachable, clean `main`
commit, record full commit/tree IDs, and confirm ordinary required hosted CI is
terminal green for that same SHA. Do not carry forward the historical
`b56254854b28701bd7f8b2e83a8ede58915f309d` diagnostic or earlier candidate
results as current-source evidence.

Before dispatch, confirm the exact-main workflow contains the full sdist
build-environment chain described above and a genuinely qualified required
Windows row. A generator name/version field alone is not complete PEP 517
environment provenance. An unconditional failing Windows step is a NO-GO
scaffold, not qualification evidence: do not dispatch it as Stage A, record
Stage A PASS, or infer stable readiness until launcher installer/template
provenance and native Windows x64 package/process evidence are admitted.

Before dispatch, obtain separate authorization bound to this workflow,
`refs/heads/main`, the selected full SHA, and exactly one attempt. Green CI or
approved documentation does not authorize a run; any rerun requires new
authorization.

Dispatch only from `refs/heads/main`, supplying the full lowercase 40-character
expected commit SHA equal to the selected `main` commit and workflow event SHA.
Require the workflow to bind its checkout, tree, version, and clean state to that
identity. One build must produce exactly one canonical wheel and one canonical
sdist; all three required platform rows—Linux x64, macOS arm64, and Windows x64—
must verify both original archive identities. Install the canonical wheel
directly. For the sdist lane, build and install a temporary wheel from the exact
original sdist using the separately recorded PEP 517 build environment; the
installed verifier still checks against the original bound sdist. Record one
sanitized, source- and artifact-bound receipt per platform, including runner
OS/architecture, installed metadata/`RECORD`, all 26 resource and three TCK
results, focused test counts, and terminal job conclusion. Every sdist receipt
also binds its before/after complete observed build-package manifest, static and
dynamic requirement satisfiers, and temporary-wheel name/size/SHA-256. This is
exact-attempt evidence, not a reproducibility claim. The issue #582 evidence
record also identifies the run URL and event SHA/ref, canonical artifact
names/sizes/hashes, and any explicit platform disposition.

Any failed, skipped, cancelled, timed-out, incomplete, or mismatched required
job or receipt is NO-GO. Preserve each attempt and its run ID; a later rerun is a
new attempt and cannot replace or relabel earlier historical evidence. Keep
private logs, local paths, workstation state, tokens, and graph content out of
public evidence. An independent human review records Stage A GO/NO-GO against
the entire plan; green workflow conclusions are evidence for that decision, not
the decision itself.

Stage A GO permits only a separately authorized signed tag and publication of
an experimental RC4 prerelease. It does not grant that authorization. After
authorized publication, Stage B independently binds the public workflow-built
wheel and sdist to the frozen deployment manifest before either Gate B profile
starts; never assume Stage A build hashes equal public artifact hashes. Stage B
and the final RC4 disposition remain separate from Stage A and publication, and
do not promote stable `v2.0.1`.

## Targeted runtime and package controls

The candidate must retain focused, deterministic evidence for:

- Parser 1.9’s public snapshot factory, bounded snapshot projection, unresolved
  block-reference and title-collision fail-closed behavior, and explicit reference
  origin handling. `LogseqNode.refs` and aggregated page-property references must
  not be inferred as topology edges without an explicit contract.
- Process timeout lifecycle: forced timeout, worker termination, recycle, no stale
  result, and a subsequent bounded parse. Fixture speed must not be used as an
  accidental timeout proxy.
- Topology session authority: Plumber composition only; no public Python adapter,
  `Path`-accepting consumer API, transport, CLI/MCP command, Trama/Brain import,
  UI, or LENS. Validate closed sessions, foreign graphs, incomplete topology, and
  all topology TCK fixtures fail or pass as declared.
- Package inclusions: `plumber.consumer.package/v1`, `plumber.graph.read/v1`, and
  `plumber.graph.topology/v1` schemas, profiles, fixtures, manifests, and TCKs;
  all stay static, content-free, and installable without a user graph.
- DB negative policy: the package contains no supported Logseq DB capability. The
  #580 `upstream_blocked` record is retained as evidence of a stopped external
  artifact admission, not as an operational test result.

The on-demand package-qualification workflow is not deployed while Windows
remains NO-GO. Its withheld prototype pinned uv `0.12.19`. The [official GHSA-2cv4-cqwr-gwf7 advisory](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7)
places `0.12.19` in the patched range (`>=0.12.18`) and identifies
`>=0.12.7,<0.12.18` as affected by Windows wheel-extraction traversal. Its
official Windows x64 archive checksum is recorded in the active package
qualification plan. The previous workflow pin `0.12.16` was affected and is
historical only. This toolchain correction does not qualify Windows: launcher
provenance, process-tree containment, and native platform evidence remain
separate required gates.

The planned SHA-pinned `astral-sh/setup-uv` action is a trusted bootstrap boundary;
action-internal code runs before explicit workflow verification. Require
independent verification of the official uv `0.12.19` artifact and active
executable before workflow-owned uv use, including `uv sync`, and repeat the
check in the aggregate job before its `uv sync`. Claim only “verified before
workflow-owned uv use,” not before action-internal code. The withheld prototype's
aggregate check passed 14 local workflow tests, but neither that workflow nor its
contract tests are deployed. Task 4 remains deferred; this is not hosted
qualification or dispatch readiness. After repair of raw PEP 517
dynamic-expression and extras handling, the latest integrated package suite is
225 passed with 1 expected skip before final typing additions. The subsequent
exact clone-local, locked/offline full `make ci` passed: 2443 passed, 6 skipped,
4 warnings, and 84.73% coverage, using four pytest workers; all static,
documentation, and type gates were green. Earlier sandbox `ps` and
shared-primary-venv coverage failures are diagnostic history, not the final
run. Sol's final quality and security reviews are PASS_WITH_NOTES.
Process-containment review separately passed with notes after 21 focused tests.
Review notes: PEP 518 environment records observe
package names and versions, not package artifact hashes; two official uv
archive downloads in the withheld prototype were not byte-count capped before digest verification; tested
process containment is not a hostile-code sandbox. Windows remains NO-GO. No
hosted dispatch, Stage A result, or Windows qualification is implied.

## Platform and profile matrix

No platform result is recorded by this plan. Before RC4 publication, attach
candidate-bound evidence for each applicable **pre-publication** row and disposition
any unavailable row explicitly. Gate B rows are post-publication and must not be
represented as pre-tag PASS; never mark an unrun row as covered by another runner.

| Surface | Required evidence | Status now |
| --- | --- | --- |
| Hosted source CI, Python 3.12 | Exact candidate required checks, including docs, lint, types, security, and full tests. | Unselected. |
| Hosted source CI, Python 3.13 | Exact candidate matrix conclusion and compatibility disposition. | Unselected. |
| Installed wheel and sdist | Isolated install, metadata/`RECORD`, 26-resource parity, and all installed TCKs on every supported release platform implicated by the artifact. | Unselected. |
| macOS arm64 | Candidate-bound Parser/topology and timeout controls on the supported maintainer platform. | Unselected. |
| Linux hosted runner | Candidate-bound parser/topology, archive, and installed-package controls. | Unselected. |
| Windows | Candidate-bound installed-package/TCK and process-lifecycle disposition if the release support claim includes Windows. | Unselected. |
| `default-on` Gate B profile | Post-publication: exact installed public RC4 artifact; independent attempt chain and terminal report. | Not started; not a pre-tag gate. |
| `read-only + external Shadow` Gate B profile | Post-publication: exact installed public RC4 artifact; independent attempt chain and terminal report. | Not started; not a pre-tag gate. |

## Two-stage publication and Gate B sequence

**Stage A — pre-publication GO/NO-GO:** freeze one exact source; pass required hosted
CI, platform and focused controls; build and hash the wheel/sdist; verify isolated
installs, all 26 resource bytes, metadata/`RECORD`, and all three installed TCKs;
check empty destinations and notes. An independent review must record a
pre-publication GO before separate tag/publication authorization. This GO permits
only an experimental RC4 prerelease, not final RC4 qualification or stable support.

**Stage B — post-publication qualification:** verify the workflow-built GitHub/PyPI
artifacts and download the exact public wheel. Its identity and installed `RECORD`
must match the frozen deployment manifest before either Gate B profile starts.
The independently built Stage A wheel is diagnostic pre-publication evidence; do
not assume its hash equals the public workflow-built wheel.

Tier 3 requires fresh exact-artifact Gate B. Each required profile must accumulate
at least **259,200 valid seconds per required profile**: `default-on` and
`read-only + external Shadow`. Setup, preflight, downtime, interruptions, prior
campaigns, and a different artifact contribute zero seconds. The campaign begins
only after a separately authorized public RC4 artifact and resource/admission check;
it must follow the Gate B runbook’s checkpoint, receipt, interruption, and
public-safe evidence rules.

Terminal Gate B PASS for both exact-artifact profiles, plus review of all other
applicable gates, yields a separate final RC4 qualification GO/NO-GO. Gate B is
**not** a prerequisite for publishing the experimental RC4 artifact needed to run
Gate B. It is a prerequisite for claiming that RC4 completed Tier 3 qualification.

This plan neither starts that campaign nor authorizes an exception. The local
coordinator/CCP is operational support, not release qualification; normal public
hosted CI must remain separate from the heavy soak decision.

The Stage A decision, tag/publication authority, Stage B terminal evidence, and
final RC4 disposition are distinct records. A prerelease result does not promote
stable `v2.0.1`.

Any future stable `v2.0.1` needs its own exact source/artifact selection, delta
classification, publication authority, and final decision. It may cite RC4 only as
historical, artifact-bound evidence and must not transfer RC4’s source, package,
platform, or Gate B result to changed stable bytes.

## Stop conditions

Stop and return to release authority if source/tree/package identity is missing;
hosted CI is absent or non-terminal; an archive resource differs; an installed TCK
uses checkout bytes; Parser/topology controls fail; timeout handling returns stale
data; a DB policy is presented as runtime support; a public artifact cannot be
bound to its source and deployment manifest; a Gate B profile lacks valid duration;
or the stable decision is attempted from RC4 inference. Preserve a published RC4
and its failed evidence rather than replacing its tag or artifact bytes.
