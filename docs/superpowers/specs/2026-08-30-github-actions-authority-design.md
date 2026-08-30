---
type: Specification
title: GitHub Actions qualification authority design
description: Direct hosted CI and exact-artifact release architecture for the public Matryca Plumber repository.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-30
stale_after: 2027-02-26
---

# GitHub Actions Qualification Authority Design

## Executive decision

Matryca Plumber will use GitHub Actions as the sole public pull-request,
protected-branch, security-analysis, package, and release qualification authority.
The active Commit CI Preflight (CCP) integration will be retired from this
repository because standard GitHub-hosted runners are free and unlimited for
public repositories. Retaining a second receipt-based control plane would add
maintenance and coordination cost without reducing billed runner minutes.

The migration has two independently reviewable deliveries:

1. consolidate pull-request qualification on secure, parallel, exact-head
   GitHub Actions jobs while preserving the required `Ironclad Gatekeeper`
   status context;
2. build release distributions once, verify and attest those exact bytes, and
   promote the same artifacts to GitHub Releases and PyPI.

The repository will not run CCP to qualify either delivery. Direct repository
checks and fresh hosted GitHub Actions are the accepted evidence.

## Goals

- Make one hosted system visibly authoritative for every merge decision.
- Preserve or strengthen Python, frontend, documentation, security, and
  cross-platform coverage.
- Reduce wall-clock feedback time by executing independent checks in parallel.
- Keep the existing protected-branch status name stable during migration.
- Make Python 3.13 and the supported macOS/Windows Shadow contract blocking.
- Pin external Actions to immutable full commit SHAs and minimize token scopes.
- Support GitHub merge queues without creating missing required checks and
  prove that the required result is reported by the expected GitHub Actions app.
- Publish exactly the distributions that passed package verification.
- Record release provenance without exposing local paths, credentials, or
  maintainer workstation state.
- Remove obsolete local receipt, policy, savings, and verifier surfaces from
  the active source tree.

## Non-goals

- Replacing durable Gate B, native runtime, benchmark, or post-release evidence
  with ordinary CI.
- Adding self-hosted or larger runners.
- Adding top-level path filters to the required CI workflow.
- Redesigning the scheduled metrics publisher or its dedicated branch.
- Changing product runtime behavior, dependency versions, or supported Shadow
  semantics.
- Rewriting historical Git commits or deleting existing evidence branches.
- Claiming that hosted CI proves an unexecuted platform or operational soak.

## Historical pre-Delivery A baseline

The following records the verified state before Delivery A changed the hosted
qualification route. It is preserved for migration traceability and does not
describe the current tree; the current authority is recorded in the
[GitHub Actions qualification authority decision](../../decisions/2026-08-30-github-actions-qualification-authority.md).

| Item | Historical state verified before Delivery A on 2026-08-30 |
| --- | --- |
| Design base | `origin/main@5fe19f5a1e9ce9afa8006eef642ecaf77d7c99c8` |
| Required status | `Ironclad Gatekeeper` |
| Rulesets | `main` (`17295807`) and `protect` (`16516530`) both require the same status; `protect` also requires a pull request and signed commits |
| Primary CI | `.github/workflows/ci.yml` on pull requests and pushes to `main` |
| Latest inspected PR CI | run `33252132302`, terminal success; `Ironclad Gatekeeper` took about 173 seconds |
| Security analysis | `.github/workflows/codeql.yml`, Python and JavaScript/TypeScript |
| Release workflow | `.github/workflows/release.yml`, tag-driven GitHub Release and PyPI trusted publishing |
| Active local-receipt observer | `.github/workflows/receipt-gate.yml`, opt-in and normally skipped |
| Current Python policy | Python 3.12 blocking; Python 3.13 full tests non-blocking |
| Current platform policy | bounded Shadow contract on `macos-latest` and `windows-latest`, not required by the rulesets |

The existing release-qualification documentation branch and its staged CCP
repair are separate state. They must not be mixed into this migration. The five
staged CCP-only changes are superseded and must not be committed.

## Considered approaches

### A. Minimal decommission

Delete the receipt observer and CCP configuration while keeping the monolithic
`Ironclad Gatekeeper` unchanged.

This is low risk but leaves Python 3.13 and cross-platform checks non-blocking,
keeps the slow serial critical path, and does not fix release artifact identity.

### B. Parallel hosted authority and exact-artifact release

Split independent checks into parallel jobs, aggregate them behind the existing
required context, retire active CCP surfaces, then harden the release workflow
in a second PR.

This is the selected approach. It strengthens coverage without requiring an
immediate ruleset mutation and keeps release risk isolated from CI migration.

### C. One comprehensive workflow rewrite

Replace CI, CodeQL, Dependabot support, metrics, release, and rulesets in one
change.

This creates too much review and rollback coupling. Unrelated privileged
workflows remain separate follow-up audits.

## Delivery A: hosted pull-request authority

### Required workflow triggers

The primary workflow runs on:

- every `pull_request` event needed by ordinary contribution flow;
- pushes to `main` for the exact merged commit;
- `merge_group` with exact `types: [checks_requested]` for future or active
  merge-queue use.

The workflow must not use top-level `paths` or `paths-ignore`. GitHub leaves a
required check pending when the complete required workflow is skipped by path
or branch filtering. Job-level optimizations are permitted only when the final
gate deterministically reports success or failure for every trigger.

Concurrency remains fail-fast for superseded work:

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### Job graph

```text
Dependency Review (PR only) ------------------+
Python 3.12 quality --------------------------+
Frontend quality -----------------------------+--> Ironclad Gatekeeper
Python 3.13 compatibility --------------------+    exact required name
Shadow contract (macOS) ----------------------+    always evaluates needs
Shadow contract (Windows) --------------------+
```

The independent jobs start in parallel. The final aggregation job uses
`if: always()` and accepts `skipped` only for Dependency Review on non-PR
events. Any cancellation, failure, or unexpected skip fails the gate.

### Python 3.12 quality

The blocking Python 3.12 job performs the complete repository gate:

- locked development dependency synchronization;
- format check and Ruff lint;
- Ruff security baseline;
- strict mypy;
- graph-read sandbox, version, agent, public-metrics, documentation, and
  generated-prompt checks;
- the default pytest suite with its coverage threshold.

`make ci` remains the canonical command so local and hosted contracts do not
diverge.

### Frontend quality

The Node.js 22 job runs `npm ci`, lint, tests, and production build from the
locked frontend dependency graph. It no longer waits for Python checks.

### Python 3.13 compatibility

The existing full Python 3.13 test suite becomes blocking. This matches the
package declaration that supports Python versions from 3.12 upward. A Python
3.13 failure therefore blocks the final gate instead of being converted into a
green workflow through `continue-on-error`.

### Cross-platform Shadow contract

The bounded named Shadow tests remain on standard GitHub-hosted macOS and
Windows runners. Each matrix child is blocking, and the aggregator fails if
either platform fails or is cancelled. This is targeted platform evidence, not
a full native-product or soak claim.

### Dependency review

Dependency Review remains pull-request-only and read-only. The aggregator
requires its success on pull requests and permits its expected skip on pushes
and merge groups.

### CodeQL

CodeQL remains a separate workflow because it owns GitHub security-event
publication and a weekly schedule. It gains:

- `merge_group` support;
- full-SHA Action pins;
- explicit least-privilege permissions;
- bounded concurrency and existing language separation.

After the new exact check names have completed successfully, adding the two
CodeQL language contexts to the active rulesets is a separate remote mutation.
Until that mutation is explicitly authorized and applied, the design must not
claim that CodeQL is branch-protection-required.

### Action dependency security

Every `uses:` reference in active workflows is pinned to a reviewed full commit
SHA, including GitHub-authored Actions. A comment records the human-readable
release line. Dependabot's `github-actions` ecosystem remains responsible for
proposing pin updates; each update receives normal review and CI.

Workflow-level permissions default to read-only or empty. Write permissions are
declared only on the job that needs them. No pull-request workflow executes
untrusted code through `pull_request_target` after the receipt observer is
removed.

### Active CCP retirement scope

Delivery A removes active surfaces whose only purpose is local receipt routing:

- `.commit-ci-preflight.toml`;
- `.commit-ci-policy.toml`;
- `.github/workflows/receipt-gate.yml`;
- CCP Makefile targets and `.PHONY` entries;
- receipt and mount ignore rules that no remaining repository command produces;
- CCP adoption contract and savings-report scripts, tests, fixtures, and data;
- active CCP specification, implementation plan, runbook, savings baseline, and
  case-study documents;
- active knowledge-index, evidence-index, and knowledge-log claims that route
  maintainers through CCP.

Git history remains the durable historical record. The current documentation
tree does not retain an obsolete operational runbook or a savings claim whose
economic premise does not apply to standard runners in this public repository.
The documentation inventory is regenerated after removals.

The migration adds the active, quality-owned decision record
`docs/decisions/2026-08-30-github-actions-qualification-authority.md`, links it
from `docs/decisions/index.md`, records the material documentation-system change
in `docs/knowledge/log.md`, curates its inventory metadata, and adds one
changelog entry describing hosted qualification consolidation without local
tool attribution.

## Delivery B: exact-artifact release promotion

### Build and promotion flow

```text
verified maintainer-signed v* tag on protected main
    |
    v
verify source and frontend
    |
    v
build sdist once -> derive wheel once
    |
    +--> validate metadata, archive contents, install smoke, version
    |
    +--> generate SHA-256 manifest and build-provenance attestation
    |
    v
upload short-lived release artifact
    |
    v
download identical bytes in publish job
    |
    +--> GitHub Release
    +--> PyPI trusted publishing
```

The publish job never rebuilds the package. It consumes only the uploaded
artifact from the same workflow run and fails if expected files or the checksum
manifest are missing or different.

### Tag authority and immutability

A release tag is accepted only when all of these facts are terminally verified:

- it is an annotated tag signed by the maintainer release key;
- the public key is registered so GitHub reports the tag verification as valid,
  not `unknown_key`, unsigned, or unverifiable;
- the peeled commit is reachable from protected `main` and equals the exact
  release-preparation commit;
- the exact commit has terminal required CI from the expected GitHub Actions
  app;
- an active `v*` tag ruleset prevents update, deletion, and non-fast-forward
  replacement except through an explicitly reviewed maintainer bypass.

The current branch rulesets do not protect tags, and the historical `v2.0.0`
tag cannot establish this future policy because GitHub reports its key as
unknown. Delivery B therefore includes a separately authorized repository
settings gate for the `v*` tag ruleset and release-key verification before its
first publication. A missing or unverifiable condition stops publication.

### Concurrency and idempotency

The release workflow uses one per-tag concurrency group and never cancels an
in-progress publication:

```yaml
concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: false
```

Before the first external mutation, the workflow verifies that the version is
not already published on PyPI and that a conflicting GitHub Release does not
exist. A verified artifact set is never rebuilt, overwritten, or silently
replaced during a rerun. A partial external publication stops the workflow and
requires a separate maintainer recovery decision; rerunning the tag workflow is
not an implicit authorization to repeat completed mutations.

The build job writes one SHA-256 manifest for every distribution. The publish
job verifies that manifest immediately after artifact download and before
attestation, GitHub Release creation, or PyPI publication.

### Release permissions

- Verification and build jobs: `contents: read`.
- Attestation step: `id-token: write`, `attestations: write`, and
  `contents: read` only.
- Publication job: `contents: write` for the GitHub Release and
  `id-token: write` for PyPI trusted publishing.
- No long-lived PyPI API token is introduced.

A protected GitHub environment is recommended for PyPI publication. Adding an
environment name to the workflow is gated on live verification that the
matching GitHub environment and PyPI trusted-publisher configuration already
exist; otherwise it is delivered as a separate repository-settings step.

### Artifact retention

The workflow artifact exists only to promote exact verified bytes between jobs.
Its retention is kept short to minimize public-repository artifact storage.
GitHub Release assets and PyPI distributions remain the durable public copies.

Build-provenance attestation is a required terminal green release condition.
An unavailable or failed attestation blocks normal publication. Omitting it
requires a separately documented and explicitly authorized release exception;
the ordinary workflow cannot convert a blocked attestation into success.

## Deterministic contract tests

Repository tests must parse the workflow YAML and assert semantic properties,
not fragile formatting:

- required workflow triggers include pull requests, pushes to `main`, and exact
  `merge_group: { types: [checks_requested] }` semantics;
- no top-level path filter can suppress the required workflow;
- the final job name is exactly `Ironclad Gatekeeper`;
- the final job depends on every blocking quality job;
- Python 3.13 has no `continue-on-error` escape;
- both Shadow matrix platforms are present;
- concurrency cancellation and timeouts are configured;
- permissions remain least privilege;
- no active workflow uses `pull_request_target`;
- no active workflow or Makefile target references CCP receipts;
- every external Action reference uses a full 40-hex commit SHA;
- release publication depends on the exact-artifact build and does not execute
  `make release-build` a second time;
- release concurrency is per tag with cancellation disabled;
- downloaded distributions pass the build-produced SHA-256 manifest before any
  publication step;
- release acceptance requires a GitHub-verified signed tag reachable from
  protected `main` and a terminal provenance attestation.

Tests must fail before each relevant configuration change and pass after it.

## Verification

Delivery A local verification, executed directly without CCP:

```bash
make agents-check
make docs-check
uv run pytest -q tests/test_ci_workflow_contract.py
make ci
```

Delivery B adds targeted release-workflow contract tests and a local
`make release-build` package verification. Fresh hosted CI is required on each
exact PR head. The first tag using Delivery B must also prove:

- terminal workflow success;
- exact tag and source SHA;
- GitHub-valid tag signature, protected-tag policy, and reachability from
  protected `main`;
- artifact checksums before and after upload/download;
- GitHub Release asset identity;
- PyPI filename, version, and digest identity;
- terminal build-provenance attestation success.

## Migration and rollback

1. Merge Delivery A while preserving the exact `Ironclad Gatekeeper` context.
2. Observe a terminal pull-request run and a terminal `main` run.
3. Verify the two active rulesets still resolve `Ironclad Gatekeeper` from the
   GitHub Actions app with integration ID `15368`.
4. Separately authorize any CodeQL ruleset additions only after exact context
   names are observed.
5. Exercise or observe one hosted `merge_group` run before claiming merge-queue
   support; contract tests alone are insufficient.
6. Merge Delivery B only after Delivery A is stable.
7. Verify the maintainer release key and create the immutable `v*` tag ruleset
   through a separately authorized repository-settings mutation.
8. Use the next prerelease or patch tag as the first exact-artifact publication.

Delivery A rollback restores the previous workflow from Git without accepting
or recreating local receipts. Delivery B rollback restores the prior release
workflow before another tag; published package versions and GitHub Releases are
immutable external state and are never overwritten.

## Acceptance criteria

Delivery A is complete when:

- no active CCP configuration, receipt observer, command, test, or operator
  route remains in the current tree;
- hosted jobs cover Python 3.12, Python 3.13, frontend, dependency review, and
  macOS/Windows Shadow contracts;
- `Ironclad Gatekeeper` is terminal green only when all applicable jobs pass;
- the required result is reported by GitHub Actions app integration `15368`,
  and merge-queue support is not claimed before a hosted merge-group result;
- active Actions are full-SHA pinned with minimum permissions;
- direct local checks and fresh exact-head hosted CI are green;
- documentation and generated inventory are current.

Delivery B is complete when:

- release distributions are built once and verified before publication;
- the exact same bytes reach GitHub Releases and PyPI;
- provenance and checksums bind artifacts to the tag and workflow;
- the tag is GitHub-verified, immutable by ruleset, and reachable from protected
  `main`;
- release concurrency and partial-publication recovery are fail-closed;
- no additional long-lived publishing secret is introduced;
- the release documentation describes the exact-artifact boundary.

Neither delivery changes Gate B applicability. Release risk classification and
artifact-bound operational evidence remain governed by the release
qualification gate map.
