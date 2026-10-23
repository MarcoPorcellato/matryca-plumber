---
type: Document
---
# Release process

**Matryca Plumber** (Marco Porcellato · [Matryca.ai](https://matryca.ai)) uses a **curated** [`CHANGELOG.md`](../CHANGELOG.md) (Keep a Changelog). GitHub Release notes are **not** auto-generated from commits — CI copies the matching changelog section when you push a `v*` tag.

---

## During development

Add user-facing bullets under **`## [Unreleased]`** (`Added` / `Changed` / `Fixed` / `Removed`). One line per notable change.

---

## Release day (local)

Replace `X.Y.Z` with the semver you are shipping (no `v` prefix in `pyproject.toml`; use `vX.Y.Z` for the git tag).

### v2 release qualification rule

The generic checklist below is necessary but not sufficient for the Shadow DB
release track. Current runtime defaults, Read Only behavior, external-cache location,
health, and fallback are owned by the canonical
[v2 operator contract](knowledge/architecture/shadow-db.md); this document owns only
release mechanics and maintainer authority gates. The fail-closed decision record is
[`quality/issue-bodies/v2-rc-stable-readiness.md`](quality/issue-bodies/v2-rc-stable-readiness.md):

- classify the release delta before selecting operational gates, using the
  [risk-based qualification decision](quality/RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md);
- do not tag or publish a release candidate until its exact preparation commit
  has passed the pre-publication gates selected by its active qualification plan;
- when the selected risk tier requires Gate B, bind the campaign to the exact
  installed public candidate wheel and its runner, profiles, digest, checkpoints,
  and valid elapsed time;
- do not transfer RC, stable, benchmark, or observation evidence to changed source
  bytes or a later artifact, even for a patch release;
- do not tag or publish a stable v2 patch until its candidate-specific qualification
  plan records every applicable gate as terminal or explicitly dispositioned.

Evidence non-transferability and gate applicability are separate decisions. Every
release needs fresh source, CI, package, and publication evidence. A fresh 72-hour
soak is required only when the classified delta reaches the durable-state,
concurrency, recovery, parser/I/O, lifecycle, migration, default, or equivalent
high-risk boundary. Lower-risk changes use the smaller exact-artifact gate set
defined by the gate map; they never inherit an earlier soak and never claim a new
durability result.

Release preparation, tag creation, publication, and the final stable decision
remain separate maintainer authority gates.

The [v2.0.1-rc.1 qualification plan](quality/V2_0_1_RELEASE_QUALIFICATION_PLAN_2026-08-23.md)
and [release record](releases/v2.0.1-rc.1-GITHUB.md) are immutable historical records
for that exact prerelease. They do not classify or qualify a later `main`. Every new
maintenance candidate or stable decision must select a fresh exact source and artifact,
classify its complete delta, and record the applicable gates before publication.

The [v2.0.1-rc.2 attempt](releases/v2.0.1-rc.2-FAILED-PUBLICATION.md) is immutable
terminal failed-publication history: its signed tag and workflow passed source,
destination-preflight, build, attestation, and bundle-verification stages, but it
published neither destination. [RC3](releases/v2.0.1-rc.3-GITHUB.md) is a published,
historical prerelease; its source, artifacts, and qualification evidence do not transfer
to RC4 or stable `v2.0.1`. Its [qualification plan](quality/V2_0_1_RC3_RELEASE_QUALIFICATION_PLAN_2026-08-31.md)
is historical, not a proposal for the next candidate.

### Active experimental 2.1.0 alpha track

The active [2.1.0a3 qualification plan](quality/V2_1_0A3_RELEASE_QUALIFICATION_PLAN_2026-10-22.md)
prioritizes the offline OG identity/topology producer on Linux x86_64 and macOS
arm64, with CPython 3.12 and 3.13 and both wheel and sdist installation paths.
These eight rows are planned, not qualified. Windows gateway refusal is a
negative control, not Windows installed-package qualification.

The [RC4 supersession record](quality/RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md)
preserves historical evidence and transfers unfinished obligations to the later
full 2.1.0 qualification track. It does not waive native Windows, full
three-platform Stage A or the separately governed dual-profile Gate B. The
experimental POSIX publication decision is distinct from that full qualification
and from Trama's independent admission.

For this preparation, package metadata uses `2.1.0a3`, the signed tag is
prospective `v2.1.0-alpha.3`, and the changelog section is `[2.1.0-alpha.3]`. The release
workflow compares the metadata version with both byte-identical llms surfaces;
its changelog extractor requires the literal tag spelling without `v`. Do not
substitute a PEP 440-normalized changelog heading.

Freeze dependency versions through this alpha tag. Change only the root package
version in `uv.lock` for the version bump and verify the locked graph without
refreshing dependency selections. An actual security/gate failure requires an
explicit scoped correction; do not opportunistically update the closure.

The operational resources and additive
[`og-profile-qualification.yml`](../.github/workflows/og-profile-qualification.yml)
workflow must land before selecting the final source. The migration milestone
records the macOS cleanup repair and version preparation in `[2.1.0-alpha.3]`,
preserves the entire alpha.1 and alpha.2 changelog sections rather than
rewriting their history, and leaves an empty
`[Unreleased]` section. Verify the exact extracted notes again before final
candidate selection; later changes are not automatically included.
Pre-publication workflow artifact hashes are diagnostic only: publication builds
its own canonical pair. After the maintainer explicitly confirms publication,
requalify the actual public wheel and sdist bytes, including full installed
metadata, `RECORD`, resources, import-origin, static TCK and operational TCK
checks for every required row. A green preparation PR is not this evidence.

Signed tag creation, GitHub Releases and PyPI publication are maintainer actions
outside the approved preparation milestones. Stop with an exact handoff before
those actions. Trama receives only the independently verified public-artifact
bundle; recording acceptance policy is not compatibility admission.

#### Alpha qualification entrypoints and evidence

The new workflow is additive: it does not replace an existing required status,
change a legacy RC4 receipt schema or admit Windows installed packages. A pull
request run uses that exact head as diagnostic preparation evidence. Separately
authorized `workflow_dispatch` accepts only the exact current `main` SHA, equal
to the dispatch event's `GITHUB_SHA`, and the workflow itself must run from `main`.
An older reachable ancestor is rejected before provisioning or building, rather
than being confused with the run's independent REST identity. The maintainer
must still select that source and make the independent pre-publication decision;
neither merging this workflow nor a green preparation PR selects the release.

Use the explicit `scripts/qualify_release_package.py` alpha subcommands:

| Subcommand | Boundary and output |
| --- | --- |
| `alpha-build` | Canonical Node 22 frontend, normalized original sdist, then wheel from that sdist; independently provisioned CPython 3.12 and the dedicated locked build packages; canonical binding and build evidence. |
| `alpha-row` | One native original-wheel or original-sdist installed path; complete metadata, RECORD, resources, import-origin and static TCK verification, plus the complete installed operational TCK report. |
| `alpha-source-controls` | Separately executes the versioned source-unit control map; retains actual JUnit bytes. These controls are not relabeled as installed TCK executions. |
| `alpha-windows-refusal` | Native Windows x64 `unsupported_platform` before synthetic graph access; refusal-only evidence, not platform admission. |
| `alpha-aggregate` | Requires all eight rows, the source controls, Windows refusal, actual completed upstream job conclusions and exact upstream artifact IDs/digests for the same run and attempt. |

The legacy `build-handoff`, `verify-handoff`, `verify-installed` and
`prepare-sdist-build` commands retain their RC-only defaults. Alpha policy is a
closed opt-in for exactly `2.1.0a3`, not a caller-defined version expression.

Provision qualification tools with the unchanged project lock and no project
installation. Explicit interpreter provisioning uses the manual download policy
before any no-download environment consumption; later sync, build and package
installation commands forbid interpreter downloads. Provision each runtime from
the packaged hash-locked OG profile
using `--require-hashes`, then install only the authenticated package with
`--no-deps`. Each of the four sdist rows has a separate locked CPython 3.12 build
environment and its own temporary-wheel evidence; CPython 3.13 is tested as a
runtime, not inferred as a supported build interpreter. The temporary wheel is
never substituted for the original sdist or canonical manifest.

The canonical build records observed Node and npm versions. Runtime CPython
implementation is measured, not inferred from the selected minor version.
Sanitized sdist environment and provisioning documents are uploaded even when a
later build or installed check fails. A path-free failure marker identifies the
failed alpha-row operation; it is not a PASS receipt or a precise cleanup claim.

The aggregate binds the exact source/tree, resource/dependency/fixture/golden/TCK
chain, original distribution identities, observed native interpreter patches,
run/attempt/row/job identities, four sdist build instances and cleanup outcomes.
Missing, duplicate, stale, skipped, failed, mismatched or uncertain evidence is
NO-GO even when a receipt claims PASS. Passing operational results retain
`qualification: "unqualified"`; descriptor matrix rows remain `planned`.

Retain the workflow URL, selected source/tree, seven upstream artifact IDs and
archive digests, complete row/source/refusal evidence and aggregate. The final
aggregate is a preparation record, not a public producer handoff. Publication
rebuilds its own artifacts: after the maintainer confirms M5, repeat full
verification against the actual public wheel and original sdist before offering
an immutable evidence package to Trama #2. Trama admission remains its own gate.
No user graph, DB/payload access, write, sync, stable claim or full Tier 3
dual-profile campaign is authorized by this lane.

#### Exact-alpha publication and public-input bridge

Only the exact tag `v2.1.0-alpha.3` selects the additive publisher branch.
It reuses `alpha-build`, the canonical Node 22 frontend → normalized original
sdist → original wheel sequence, with uv 0.12.19 and an independently locked
CPython 3.12 build environment. The actual publisher records the original pair
and its `binding.json`, `content-ledger.json`, `canonical-build.json` and
canonical `SHA256SUMS`. All six subjects are attested. The Release retains
those six public assets, and the Actions copy is retained for at least 14 days.
The PyPI staging directory contains only the two byte-identical original
distributions; manifests and evidence are never uploaded as Python packages.
Other release tags retain the existing publisher path.

The exact-alpha publisher and public-input jobs authenticate each fresh
qualification-tool archive with the shared standard-library acquisition helper,
not an override of the reserved runner tool cache. Fixed official archive size
and SHA-256 are checked before bounded member inspection and extraction into an
owned root. Verification recomputes archive/executable identity before tool use;
only then does a bounded version probe run. Tooling/build CPython 3.12 selection,
independent tested runtime minors, owned managed-Python placement and PATH
resolution remain explicit. The separate non-publishing three-platform lane
qualifies bootstrap only, not installed packages or consumer compatibility.

The signed alpha.1 tag and failed publisher are preserved in the
[failure record](releases/v2.1.0-alpha.1-FAILED-PUBLICATION.md). The
[recovery decision](quality/ALPHA_RELEASE_RECOVERY_2026-10-18.md) and
[alpha.2 plan](quality/V2_1_0A2_RELEASE_QUALIFICATION_PLAN_2026-10-19.md)
remain historical authorities for that separately published candidate. Preserve
alpha.2's tag, public assets and failed verification; no rerun is part of alpha.3
preparation. The active closed policy is `og-alpha3`; historical internal
`alpha1_*` filenames and alpha subcommands remain unchanged. Active tooling
rejects stale alpha.1, alpha.2 and future versions. A main-only repair cannot
change an old-tag workflow; do not retarget a tag or manually replace assets.
The alpha.3 preparation PR performs no publication.

The separate
[`og-public-artifact-qualification.yml`](../.github/workflows/og-public-artifact-qualification.yml)
is manual-only. Its inputs are the exact final source commit `S` and the
successful publication run `R`. The verifier checkout, dispatch `main` and
artifact source must all be `S`. Public qualification run `Q` is distinct
from `R`; both must be first attempts. A later main commit, a rerun, incomplete
publication or a changed asset is a stop, not a fallback or a rebuild request.

`alpha-public-admit` authenticates the repository, signed annotated tag,
publication workflow/run and exact GitHub/PyPI inventories. It downloads the
six GitHub assets and the two PyPI originals once, bounds every response and
validates every HTTPS redirect before following it. Public bytes receive no
credential or cookie headers. Only the named repository asset routes, GitHub's
release-asset services and the exact PyPI distribution host are admitted.
GitHub's CLI performs six cryptographic verifications. Policy then checks the
verified certificate's source, tag, workflow, hosted-runner and signed invocation
`R/attempts/1`; an editable provenance predicate cannot substitute for that
invocation. This uses the official
[CLI verification policy](https://cli.github.com/manual/gh_attestation_verify)
and [certificate extension fields](https://github.com/sigstore/sigstore-go/blob/main/pkg/fulcio/certificate/extensions.go).

Before admission emits a successful handoff, the actual canonical-build record
must match source-derived lock, package, CPython, uv and frontend-tool
expectations. The aggregate independently repeats these checks.
After the public binding, ledger and locked-build record agree with the
selected Git tree, the same full installed and operational checks consume
these admitted originals. Each sdist row still builds only its own private
temporary wheel. `alpha-public-aggregate` validates the real admission,
source-control, Windows-refusal and four runtime jobs and artifact identities
under `Q`, while retaining `R` separately. It never rewrites public metadata
to resemble the diagnostic build job. The pre-publication workflow and legacy
RC4 defaults remain unchanged.

This bridge defines a route, not a release result. After it lands, select and
qualify the new full commit/tree; earlier green evidence does not transfer.
Publication still requires explicit maintainer activation of that exact source
and acknowledgement that pushing the signed tag triggers GitHub Releases and
PyPI. Complete publication is followed by a separately bounded public-input
campaign and independent review. Only then may a sanitized immutable producer
handoff be offered to Trama #2. No consumer admission, Windows installed support,
DB/payload access, user-graph use, stable claim or full-soak result follows from
this bridge.

### Explicit verifier-only recovery for immutable alpha.3

The same-source route above remains the default. A separate, manually selected
`alpha3_recovery: true` route repairs qualification tooling without changing the
published producer. It is closed to producer commit
`8c30f70e217722e719c5aedc322219ebccb87e68`, tree
`de80d0473aa281c52d0fed10b4561024dd12d76f`, tag object
`c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24`, and publisher run `39887297548/1`.
The failed public campaign `39888823938/1` remains evidence, not a reusable attempt.

Activation requires the exact separately reviewed, signed verifier commit and
tree through `verifier_sha` and `verifier_tree`. The dispatch, current main,
actual qualification run and jobs, artifact metadata, imported qualification
modules and committed tool inventory must all bind to that verifier. The original
tag, publisher, signed attestation source/signer digests, source/resource ledger,
canonical build and public archive inventories remain bound to the producer.
Both identities are recorded and independently rechecked during aggregation;
no metadata is rewritten and no report's self-declared success supplies an expectation.

Recovery uses disjoint `verifier` and `producer` checkouts, with canonical LF
tooling bytes on every runner. Dedicated `alpha3-recovery-*` commands require
the verifier root, full commit and tree; existing commands expose no generic
identity override. Wrong roots, code origins, signatures, identities or bytes
fail closed. The original eight installed rows, full package/operational TCKs,
independent sdist build environments, source controls, Windows refusal, output
limits and cleanup gates are unchanged. No dependency resolution or package
rebuild may replace an original published artifact.

This route requires its own explicit integration and bounded campaign approval.
A new qualification run must be separately authorized, distinct from the publisher
and failed campaign, and attempt 1; calling it a new run does not grant retry authority.
No tag, package upload, publication-workflow rerun or version migration is needed.
Preserve alpha.3, all original assets and historical evidence. Only accepted
actual-public-byte evidence and independent review can support a producer handoff;
Trama's admission decision remains separate.

### Historical RC4 qualification policy

The superseded [RC4 qualification plan](quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md)
defined two stages. Stage A was pre-publication GO/NO-GO for an exact source and
independently built artifact, required source/platform/resource/TCK controls, and
independent review; a GO permits only separate authorization to publish an experimental
RC4 prerelease. Stage B begins after publication: verify the exact workflow-built public
wheel against the frozen manifest, then run fresh exact-artifact Gate B for both required
profiles. Gate B is not a prerequisite to publish the experimental artifact, but both
terminal profile results and review of all other applicable gates are required for a
separate final RC4 qualification decision. Neither stage authorizes stable promotion.

### Historical RC4 Stage A on-demand package qualification

The following retained RC4 procedure is historical, not the active alpha
dispatch route. Its outstanding acceptance criteria remain obligations of the
full qualification track identified in the supersession record. Do not execute
it from this documentation or relabel its attempts as 2.1.0 evidence.

No Stage A workflow is currently deployed or dispatchable. Its prototype was
initially withheld pending upstream installer/template provenance and native
Windows x64 evidence. Later byte-only admission accepted the exact upstream
provenance chain described below; installed-launcher authentication and native
Windows x64 package/process qualification remain outstanding. The package
verifiers and operator procedure are preparatory only; Stage A remains NO-GO. Use the proposed manual
package-qualification workflow only after its implementation has landed on
protected `main` with a genuinely qualified Windows row. First select the exact,
reachable, clean `main` commit and record its full commit and tree IDs. The workflow's
own merge changes `main`; earlier diagnostic source and local build results remain
historical and cannot be relabeled as evidence for the new commit. Confirm ordinary
required hosted CI is terminal green for that exact commit before dispatch.

Before any dispatch, inspect the workflow at that exact `main`: its sdist lane must
authenticate the original sdist, record the complete observed private PEP 517 build
environment before and after, verify static and backend-returned dynamic requirements
against already installed packages, build a temporary wheel with
`uv build --wheel --no-build-isolation`, and bind that wheel's name, size, and SHA-256.
It must install the temporary wheel with `--no-deps` in the separate sdist runtime
environment while `verify-installed` continues to authenticate the original bound
sdist. The temporary wheel is not part of canonical `dist`. A recorded generated
wheel hash proves only this run's exact output, not reproducible builds. Generator
metadata alone does not prove the full build environment.

The required Windows row must also be genuinely qualified. Admitted upstream
installer/template provenance does not establish actual installed-launcher
authentication or native Windows x64 package/process evidence. Until those exist,
Windows remains NO-GO. A deliberately failing Windows step is not a qualification
result: do not dispatch such a workflow, call Stage A PASS, or infer stable-release
readiness.

The withheld qualification-workflow prototype pinned official uv `0.12.19`, which is outside the
affected range in the [official GHSA-2cv4-cqwr-gwf7 advisory](https://github.com/astral-sh/uv/security/advisories/GHSA-2cv4-cqwr-gwf7).
The [0.12.19 release page](https://github.com/astral-sh/uv/releases/tag/0.12.19)
links verified release commit `bea138450f0e620a4ce5765b0e38cff7b9f0799f`; the
official [Windows x64 archive checksum](https://releases.astral.sh/github/uv/releases/download/0.12.19/uv-x86_64-pc-windows-msvc.zip.sha256)
is `6dbb02d79e419522f1c500f0adb1cddcff0cda7d59b0d66ea7f5e3b4a1b2f5f0`.
The former `0.12.16` pin falls in the affected `>=0.12.7,<0.12.18` range and is
historical only; do not use it for Windows wheel installation. The new tool pin
alone did not qualify the generated launcher. Initial byte-only attempts retained
their failures, including a verification-command construction error that was not
an artifact rejection. A subsequent bounded, non-executing admission on
2026-10-01 accepted the exact archive and pinned template under the authenticated
upstream release-builder policy, binding the selected source and inspected
build/sign/assembly recipe to cryptographically verified archive identity. This
is trusted upstream provenance, not independent compilation, reproducible builds,
local Authenticode verification or generated-launcher execution evidence.
`RECORD` and an `MZ`/PE header alone do not authenticate generated
launcher bytes. Lifting NO-GO still requires an
independent architecture-specific template/payload verifier (including
interpreter binding, entry-point payload and trailing bytes), process-tree
containment review, and native Windows x64 install and lifecycle tests.

The planned SHA-pinned `astral-sh/setup-uv` action is a trusted bootstrap boundary:
action-internal code runs before explicit workflow verification. Independently
verify the official uv `0.12.19` artifact and active executable before every
workflow-owned uv command, including `uv sync`, and repeat verification in the
aggregate job before its own `uv sync`. State only that uv was verified before
workflow-owned use, not before action-internal code. The withheld prototype's
aggregate check passed 14 local focused workflow tests; neither the workflow
nor its contract tests are deployed. This is historical local implementation
evidence only, not hosted qualification or dispatch readiness.
After repair of raw PEP 517 dynamic-expression and extras handling, the focused
integrated package suite was 225 passed with 1 expected skip before final typing
additions. The subsequent exact clone-local, locked/offline full `make ci`
passed: 2443 passed, 6 skipped, 4 warnings, and 84.73% coverage, using four
pytest workers; all static, documentation, and type gates were green. Earlier
sandbox `ps` and shared-primary-venv coverage failures are diagnostic history,
not the final run. Final quality and security reviews are PASS_WITH_NOTES;
process-containment review separately passed with notes after 21 focused tests.
Review notes: PEP 518 environment
records observe package names/versions but not package artifact hashes; two
official uv archive downloads in the withheld prototype lacked a byte-count cap before digest verification;
and tested process containment is not a hostile-code sandbox. These scoped
local checks do not establish hosted qualification. Windows remains NO-GO and
no hosted dispatch or Stage A result is claimed.

Before dispatch, obtain separate authorization bound to this workflow,
`refs/heads/main`, the selected full SHA, and exactly one attempt. Green CI or
approved documentation does not authorize a run; any rerun requires new
authorization.

Dispatch from `refs/heads/main` and enter the full lowercase 40-character SHA for that
same `main` commit in the workflow's expected-commit input. The workflow must reject a
different ref, SHA, tree, version, or dirty checkout. One Linux build produces exactly
one canonical wheel and one canonical source distribution. Every platform verifies
both original archive byte identities. Install the canonical wheel directly. For the
sdist lane, build one temporary wheel from the authenticated original sdist in a
private PEP 517 build environment, then install that temporary output in the separate
sdist runtime environment; pass the original sdist—not the temporary wheel—to
`verify-installed`. Keep the temporary wheel outside `dist`. Require terminal success
and one complete, matching platform receipt for each platform. A missing, skipped,
failed, cancelled, timed-out, or mismatched required job or receipt is NO-GO; preserve
that attempt and its run identity. Any rerun is a distinct attempt, not a replacement
for a failed receipt.

Link the sanitized evidence record to issue #582. It must bind the workflow run and
event SHA/ref; source/tree and artifact identities; the one wheel/sdist pair and its
hashes; all three runner OS/architectures and terminal job conclusions; installed
metadata, `RECORD`, resource and TCK results; focused test counts; and any explicit
platform disposition. For each sdist row, also bind the complete observed build-env
package manifest before and after, static and dynamic requirement satisfiers, and the
temporary wheel's name/size/SHA-256. This is exact one-attempt evidence, not a
reproducible-build claim. Keep local paths, raw graph content, private logs, tokens,
and workstation state out of public evidence. Request independent human Stage A
GO/NO-GO against the complete RC4 plan; a green workflow alone is not that decision.

After a Stage A GO, obtain separate authorization before creating a signed tag or
publishing the experimental RC4 prerelease. Stage A-built bytes are not assumed to
match the later public release-workflow artifacts. Stage B starts only after authorized
publication and independently verifies those exact public artifacts against the frozen
manifest before either Gate B profile begins. Gate B and final RC4 disposition remain
separate from Stage A and publication; neither grants stable `v2.0.1` support.

### Publication prerequisites

A `v*` tag ruleset and a registered maintainer GPG key are external
prerequisites. The tag must be annotated, GitHub-verified, and reachable from
protected `main`. The release workflow imports the committed public release key
into an isolated keyring, confirms fingerprint
`FDF72C53A848EBA83AEFA0294F2221BBB930513B`, and cryptographically verifies
the tag before publication can continue.

### 1. Prepare (Cursor or manual)

- [ ] Move everything from `[Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`
- [ ] Leave an empty `## [Unreleased]` section at the top
- [ ] Set `version = "X.Y.Z"` in `pyproject.toml`
- [ ] Reconcile `uv.lock` with the preparation policy; for the frozen 2.1.0 alpha graph, change only the root version and use `uv lock --check --offline`, without a dependency refresh
- [ ] Run `make check` on CI-equivalent paths, or for a fast local gate before tag: `make test-fast` plus `uv run ruff check src tests` and `uv run mypy src tests` (see `make test-fast` — default 4 workers, no coverage, skips `tests/slow/` and `test_security_remediation.py`; override with `NUM_WORKERS=auto make test-fast`)
- [ ] For performance-heavy releases (e.g. **1.8.x**): optionally run `make perf` (`pytest -m slow`, no coverage gate) and note results in the GitHub release; see [`v1.8-OPTIMIZATION-PLAN.md`](v1.8-OPTIMIZATION-PLAN.md#verification-matrix)
- [ ] If CLI subcommands or flags changed: sync [`llms.txt`](../llms.txt) and [`.well-known/llms.txt`](../.well-known/llms.txt) (must stay identical); see [`openspec/agent-onboarding.md`](openspec/agent-onboarding.md)

**Cursor shortcut:** ask the agent to *“prepare release vX.Y.Z”* (see [`.cursor/rules/05-release-preparation.mdc`](../.cursor/rules/05-release-preparation.mdc)).

### 2. Verify release notes (optional but recommended)

```bash
python scripts/extract_changelog.py vX.Y.Z | less
```

You should see exactly the section that will appear on GitHub.

### 3. Commit, tag, push

```bash
git add CHANGELOG.md pyproject.toml uv.lock
git commit -m "chore: release X.Y.Z"
git tag -s -a vX.Y.Z -m "Release X.Y.Z"
git push origin main
git push origin vX.Y.Z
```

### 4. CI does the rest

On tag push, [`.github/workflows/release.yml`](../.github/workflows/release.yml):

1. `verify` checks the signed annotated tag, GitHub verification, protected-main
   reachability, the isolated-keyring fingerprint, and the required CI context.
2. `destination-preflight` stops if GitHub Releases or PyPI already contains the
   version.
3. `build-release` builds exactly one wheel and one sdist, writes a two-line
   SHA-256 manifest, attests both distributions, and uploads that release bundle.
4. `publish-release` downloads the bundle, verifies the exact two-file set and
   manifest, verifies the attestations against the downloaded subjects, then
   promotes only those downloaded bytes to GitHub Releases and PyPI. GitHub Release
   creation binds `gh` explicitly to `GITHUB_REPOSITORY`; the checkout-free promotion
   job must not rely on local Git repository discovery.

The workflow is fail-closed on existing destinations: do not rerun a release
after GitHub or PyPI already contains the version. Partial publication requires
a separate recovery decision. Package publication still does not replace
risk-selected Gate B or post-release evidence.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Release workflow fails on “extract changelog” | Ensure `## [X.Y.Z]` exists in `CHANGELOG.md` and matches the tag (`v1.6.2` → section `[1.6.2]`). |
| GitHub Release or PyPI version already exists | Stop; do not rerun. A partial publication needs a separate recovery decision, while a completed version is never re-used. |
| GitHub Release creation reports `not a git repository` | Do not rerun the unchanged tag workflow. Confirm that the checkout-free publish job passes `--repo "$GITHUB_REPOSITORY"` to `gh release create`, preserve the failed run and tag, then prepare a fresh candidate after the correction reaches protected `main`. |
| Notes on GitHub look wrong | Re-run locally: `python scripts/extract_changelog.py vX.Y.Z` and compare to the file. |

---

## Related

- [`CHANGELOG.md`](../CHANGELOG.md)
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — quality gates before tag
- [`scripts/extract_changelog.py`](../scripts/extract_changelog.py)
