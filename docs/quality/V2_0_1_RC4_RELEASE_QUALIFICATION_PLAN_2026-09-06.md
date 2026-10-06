---
type: release-qualification-plan
title: v2.0.1-rc.4 release qualification plan
description: Two-stage exact-artifact qualification for RC4; pre-publication gates precede the public-wheel Gate B campaign and final decision.
resource: docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md
tags: [release, qualification, parser, topology, contracts, v2]
last_verified: 2026-10-01
stale_after: 2027-03-30
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
remains historical evidence. The 2026-09-27 observation
`main@50d3fc9f34c0c88d054a5abc8fcacad8b1da5b6f` was 18 commits later, with
product and release-workflow changes; it was an observed source anchor, not a
candidate. The earlier hashes and passes cannot qualify later `main` commits.

The subsequent source-selection record used
`e350125fbc758839be6f0f474d50af9d5f361240` (tree
`14676a7f937c48c178a768c320fa3faf2500b09b`). On 2026-09-30, signed PR
[#618](https://github.com/MarcoPorcellato/matryca-plumber/pull/618) advanced
protected `main` to `da65a3aeecb68d5420dafc8147b773d7f507eb55` (tree
`ee67cbe725ca0e42bcd115df194b4fdd4f8e9cb9`), whose GitHub commit signature is
verified. Its parent is the prior `e350125f...` source. The PR changes only
`tests/test_release_package_focused.py` (+7/-0): it adds the actual repository
root to the nested pytest child's `PYTHONPATH` while retaining the synthetic
temporary repository as the source under test. This test-harness correction
does not change package runtime behavior. The prior local focused-test failure
remains historical diagnostic evidence; the correction and later green hosted
checks do not relabel or replace that attempt.

For the exact post-merge `main@da65a3ae...`, GitHub reported ten completed
check runs: nine `success` and the push-event `Dependency Review` expected
`skipped`; CI/Ironclad, CodeQL, and the separate generated Windows launcher lane
all completed successfully. These are source-check results, not package
installation, artifact, or release-qualification evidence. The source-selection
record at `e350125f...` is now historical because `main` advanced. As observed
on 2026-09-30, `da65a3ae...` is a source anchor only; it is not newly selected
as the RC4 candidate. Reselect only after any required plan correction has
merged, and reverify the resulting exact `main` commit immediately before use.

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
| Focused release-runner test import | PR #618 fixes the nested pytest plugin import path in one test; no production module changed. | Preserve the earlier diagnostic failure; verify the fix through exact-source hosted CI, then rerun candidate-bound focused controls only after a new source selection. | Test-only; no runtime or package evidence and no Tier 3 downgrade. |
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
   whose complete observed package-name/version manifests are recorded at all
   four checkpoints: `provisioned_packages`, `before_hooks_packages`,
   `after_hooks_packages`, and `after_build_packages`. Require all four lists
   to match exactly. Check static `build-system.requires` and backend-returned
   dynamic requirements against packages already present, failing rather than
   opportunistically installing a missing requirement; then run
   `uv build --wheel --no-build-isolation` from that exact sdist. Bind the
   temporary wheel name, size, and SHA-256, keep it outside canonical `dist`,
   and install it with `--no-deps` into the separate sdist runtime environment.
   The installed verifier must receive the original bound sdist as its artifact
   input, not the temporary wheel. Run all three installed TCKs from the
   installed package context; source-checkout success alone is insufficient.

   The qualification-only build project at `release-qualification-build/`
   keeps its direct requirements separate from application dependency
   resolution. Its reviewed lock,
   `release-qualification-build/uv.lock`, has SHA-256
   `72b95c7c4d89d0a1382882078914094b08be25acbf47da4a14ecb6f4d6972d9f` and
   contains the static inputs `setuptools>=61` and `wheel`, resolved to
   `setuptools==84.0.0`, `wheel==0.48.0`, and transitive `packaging==26.3`.
   Independent review compared all six wheel/sdist URLs, hashes, sizes, and
   registry/dependency edges with a fresh official metadata snapshot. This is
   metadata review only; it does not qualify artifact bytes, installation,
   backend hooks, the provisioned environment, any target, Stage A, or release.
   Revalidate the lock and recipe for the exact candidate before provisioning.
   This plan's build-interpreter profile is CPython 3.12 only; it does not
   qualify CPython 3.13 or a future Python profile. Keep the PEP 517 build lock
   distinct from the root runtime/test `uv.lock`: receipt `build_lock_sha256`
   binds the former, while outer `lock_sha256` continues to bind the latter.

   The trusted caller/provisioner owns the private environment lifecycle and
   must retain and authenticate evidence of exact-lock use, locked-artifact hash
   verification, and no re-resolution or repair. It supplies the environment
   descriptor and an independently bound expected descriptor SHA-256 to
   `prepare-sdist-build --expected-build-environment-sha256`; the helper must
   never derive its expected digest from the descriptor it reads. Aggregation
   separately requires `verify-receipts --expected-build-environments PATH`, a
   caller-authenticated schema-v1 binding file for exactly `linux-x64`,
   `macos-arm64`, and `windows-x64`. Expected lock, recipe, descriptor, and
   provisioning-evidence digests are independent inputs, never values inferred
   from receipt rows. The three-target completeness check does not admit a
   Windows lane or change its NO-GO status.

   Nested sdist receipt schema v2 records four complete package-name/version
   manifests: `provisioned_packages`, `before_hooks_packages`,
   `after_hooks_packages`, and `after_build_packages`. Require all four lists
   to match exactly; any package-set drift stops qualification. The helper
   consumes the existing provisioned environment and must not create, resolve,
   install, sync, or repair it. It verifies supplied identities and observes
   these manifests; it does not authenticate provisioning evidence that it
   never receives, prove unseen evidence contents, or prove executable-to-
   descriptor content consistency. The caller/provisioner trust boundary
   remains responsible for authenticating retained descriptor and provisioning
   evidence before constructing expected bindings.

   The CPython identity probe uses isolated mode but retains `site` startup:
   disabling `site` prevents the admitted CPython 3.12 venv from reporting its
   venv prefix. Startup may therefore process that environment's site
   configuration, which the caller must trust. This is not a hostile-code
   sandbox. The helper's explicit path and digest checks do not restrict the
   interpreter or backend's ordinary filesystem access; no OS-level filesystem
   containment or hostile-backend isolation is established.

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
also binds all four complete observed build-package manifests:
`provisioned_packages`, `before_hooks_packages`, `after_hooks_packages`, and
`after_build_packages`; all four lists must match exactly. Each receipt also
binds static and dynamic requirement satisfiers and temporary-wheel
name/size/SHA-256. This is exact-attempt evidence, not a reproducibility claim.
The issue #582 evidence
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
historical only. Initially unresolved byte-only admission attempts, including a
verification-command construction error rather than artifact rejection, remain
historical evidence. A subsequent bounded, non-executing admission on 2026-10-01
accepted the exact pinned installer/template chain under the authenticated
upstream release-builder policy: inspected source/build/sign/assembly behavior
and cryptographic archive verification establish trusted upstream provenance,
not independent compilation, reproducible builds or local Authenticode checks.
This admission does not qualify actual installed launchers or Windows packages.
Independent installed-launcher authentication, process-tree containment and
native platform evidence remain separate required gates; the aggregate Stage A
workflow remains withheld.

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
run. Final quality and security reviews are PASS_WITH_NOTES.
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

Bounded Windows launcher-lane evidence from PRs [#614](https://github.com/MarcoPorcellato/matryca-plumber/pull/614)
and [#615](https://github.com/MarcoPorcellato/matryca-plumber/pull/615) is separate
from candidate-bound Stage A results. PR #614 head
`709c475ee441a1de76c5254b21ea926ad922deaf` merged as
`f3977eec98481d2042068dbd5817bc4887b13960`; CI run `36462221350` and CodeQL run
`36462221329` succeeded, while Dependabot uv lock auto-fixer run `36462221474`
was skipped. Its only files were the bounded verifier and synthetic PE tests,
so it was not Windows runtime qualification.

PR #615 head `246d8c98bbf0177b920adfbc55fa5af8905b41dd` merged as
`28ef8ae015ec013edb3ad1dbbce1b082b9d16df7`; CI `36534885784`, CodeQL
`36534885858`, and Windows launcher lane `36534885814` succeeded, with the
expected uv lock auto-fixer skip `36534885829`. The merge's main checks also
passed: CI `36537138054`, CodeQL `36537138099`, and Windows lane `36537137950`.
The lane pinned uv source commit
`bea138450f0e620a4ce5765b0e38cff7b9f0799f`, Git blob
`c6d3881fc6b7d3ef0c6d3c08d505ab2b4c0ad9c4` (45,056 bytes; SHA-256
`0447a4febf43fdd958e4236129d6050b1dad64c124c43355d557542b3229cae8`), kept the
template read-only, reconstructed a synthetic generated candidate, and ran only
that candidate on hosted Windows x64/Python 3.12. It did not install an RC4
wheel or sdist, run installed TCKs, qualify process-tree containment, establish
general Windows package support, pass Stage A, qualify Trama, or establish
release readiness. Windows installed-package/TCK status remains `Unselected`.

Release-note disposition: retain the `CHANGELOG.md` Unreleased bullet as
maintainer-facing tooling, but exclude this bounded Windows x64 launcher CI
entry from the v2.0.1-rc.4 product release notes. This release-note
classification does not exclude the exact-source change from candidate delta
review or applicable workflow checks. It does not establish installed Windows
package or TCK qualification, process-tree containment, general Windows
support, Trama compatibility, or release readiness. It makes no claim about
whether the entry is present in the wheel or sdist; that requires direct archive
evidence. Windows installed-package/TCK status remains `Unselected`.

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
