---
type: Runbook
title: Commit CI Preflight hybrid CI operator runbook
description: Fail-closed operating sequence for Matryca Plumber local qualification, exact-head receipt verification, hosted fallback, and savings evidence.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-24
stale_after: 2026-11-22
---

# Commit CI Preflight Hybrid CI Operator Runbook

## Current authority

The repository is in **bootstrap and observation mode**. GitHub-hosted CI remains
authoritative. The receipt workflow runs only for a non-draft, same-repository,
non-Dependabot pull request after a trusted maintainer applies
`ci:observe-local-receipt`; it may then report an exact-head observation, but no
hosted job is skipped and no branch-protection rule depends on that status.

The governing [design](../superpowers/specs/2026-08-24-ccp-hybrid-ci-adoption-design.md)
and [implementation plan](../superpowers/plans/2026-08-24-ccp-hybrid-ci-adoption.md)
define the later activation gates. This runbook never turns a local PASS into
merge, release, or publication authority.

## Frozen bootstrap contract

| Boundary | Value |
| --- | --- |
| CCP source | `866db18a571f55ed3d9b481d6c9c9c3bd5e98d55` |
| Matrix configuration digest | `sha256:c1c620a8f037d5368368eac8276c38e915b7663eafa4a1499b9e3a9b14166670` |
| Node.js 22 runtime digest | `sha256:c7df43272e7f276cdda9f505f693fd9d236aea8b4d5ecdc77109d9b799ae92f6` |
| Python 3.12 runtime digest | `sha256:fa83b8b1f3ab79cd6abbbf2682dc5b57cb86ef977aaa19794303353a1b3a5fad` |
| Python 3.13 runtime digest | `sha256:d9618eb286702885635073a77eaa36629aa49c94b2103c7609691cdc1377c576` |
| Receipt path | `.ccp/receipt.json` |
| Evidence branch | `ccp-evidence/<exact-40-hex-source-sha>` |
| Remote status | `commit-ci-preflight/receipt` |

Any config, policy, image, required-check, source, or digest change creates a
new qualification boundary. Never edit policy to match a completed receipt.

## Known upstream preflight gap

At the pinned CCP source, `plan` and `run` understand matrix schema `2.0`, but
`doctor` and `dry-run` still load only the single-runtime configuration path.
They reject a matrix check's `runtime_id`. This was reproduced during PR A
bootstrap and confirmed in the exact pinned source.

Consequences:

- `make ccp-plan` is the only repository-provided matrix preflight target;
- there are deliberately no `ccp-doctor` or `ccp-dry-run` Make targets;
- an official heavy matrix run is **blocked** until reviewed CCP source exposes
  equivalent matrix-aware runtime diagnosis and rendered-mount inspection, or
  the design accepts a separately proven replacement;
- a v1 diagnostic result must never be relabelled as matrix-v2 evidence.

This limitation does not weaken hosted CI. Unlabelled pull requests publish no
receipt status. A labelled observation fails closed when no valid receipt
exists, while the unconditional hosted workflow continues independently.

## CCP source compatibility acceptance gate

A newer CCP commit is a candidate, not an automatic upgrade. Before changing
the frozen source pin or any policy digest, preserve one review packet that
proves all of the following against the same exact clean source:

- exact source commit, complete source-test result, binary digest, version, and
  the prior rollback pin;
- matrix schema support across `plan`, `run`, `doctor`, and `dry-run`, including
  `runtime_id` dispatch and rendered read-only/writable mount inspection;
- receipt schema and verifier behavior for required checks, freshness,
  exact-head binding, policy binding, and incomplete terminal state;
- regenerated outer and per-runtime configuration digests derived from the
  reviewed plan rather than from a completed receipt;
- immutable image references, Linux arm64 resolution, platform declarations,
  and unchanged required-check ownership;
- workflow trust tests plus disposable rejection tests for missing, malformed,
  stale, corrupt-digest, wrong-SHA, wrong-policy, and incomplete receipts;
- unchanged unconditional hosted CI, a documented rollback, and no required
  receipt status or hosted skip before later authorization.

Any unsupported command, schema drift, digest mismatch, ambiguous mount,
unexpected skip, or incomplete negative case rejects the candidate. Existing
receipts and pins remain historical evidence under their original contract.

## Read-only operator checkpoint

Run from a clean isolated checkout at the intended exact PR head:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse --verify HEAD^{commit}
commit-ci-preflight --version
commit-ci-preflight resource status --json
commit-ci-preflight admission status --json
docker context show
docker ps -q
make ccp-plan
make ccp-savings-check
```

Stop unless all facts are unambiguous:

- the checkout is clean and the SHA is the intended PR head;
- the installed binary's reviewed source identity is proven separately;
- resource capability is supported and enforced with decision `admit`;
- admission is inactive, queue count is zero, and every lease is safe;
- the Docker-compatible runtime is responsive and there are no unaccounted
  containers;
- the printed outer and per-runtime digests equal trusted policy;
- the known matrix preflight gap has been resolved under a reviewed source.

`unknown`, `deny`, unsafe layout, a held or queued admission slot, stale source,
dirty checkout, unexpected container, or digest drift is a stop condition.
Never delete or reinterpret tickets, leases, locks, journals, or cache markers.

## Official run after the gap is resolved

The following is a future sequence, not authorization to run it now:

```bash
commit-ci-preflight run \
  --config .commit-ci-preflight.toml \
  --repository . \
  --generation <next-monotonic-generation> \
  --admission-timeout-seconds 21600 \
  --json
make ccp-verify
```

Choose the generation only after reading the complete attempt chain and the
CCP recovery status. It must be greater than every prior attempt for the same
source and contract. Never guess a generation from filenames or wall-clock
time. A failed, interrupted, cancelled, or pressure-stopped attempt still
occupies its generation.

After a run, repeat resource, admission, container, repository-status, source
SHA, policy, and receipt verification checks. PASS requires every named runtime
and required check to be terminal PASS in one exact-head matrix receipt.

## Interruption, restart, and quarantine

On interruption or host restart:

1. preserve the checkout, receipt, run journal, admission state, cache, and logs;
2. inspect `resource status`, `admission status`, and CCP recovery status
   read-only before starting anything;
3. do not credit downtime or an incomplete attempt;
4. use only the recovery or quarantine primitive documented by the reviewed
   CCP source;
5. re-run the complete read-only checkpoint before choosing the next
   generation;
6. retain every terminal and non-terminal attempt in the evidence chain.

Manual deletion of coordinator state is not recovery. If the supported tool
cannot classify the state safely, stop and request a narrowly scoped repair.

## Append-only evidence publication

Evidence publication is a separate authority-bearing action. After an exact
receipt verifies locally:

1. create a temporary worktree at the exact source SHA;
2. create branch `ccp-evidence/<source-sha>` without changing source files;
3. force-add only `.ccp/receipt.json` because local receipts are ignored;
4. confirm the staged path, byte count, receipt digest, and expected commit;
5. check whether the remote evidence branch already exists;
6. stop if existing bytes differ;
7. use a normal non-force push;
8. preserve the resulting branch and remote workflow URL in the observation.

Never publish caches, logs, absolute paths, environment values, credentials,
raw graph content, or an unbounded artifact. The trusted GitHub workflow checks
out base policy, pinned verifier source, and the bounded receipt as data. It
never executes PR-head code under `pull_request_target`.

## Hosted fallback

Fork, Dependabot, uncertain infrastructure, and explicitly selected fallback
paths run the full hosted Linux qualification. The future
`ci:hosted-fallback` label is a routing choice controlled by trusted repository
writers; it is not a waiver and cannot synthesize PASS.

During bootstrap, hosted fallback is effectively universal because the current
CI workflow remains unconditional. Missing, malformed, stale, corrupt-digest,
wrong-SHA, wrong-policy, incomplete, failed, or unavailable local evidence must
not suppress it.

## Savings ledger

Immutable observations live under `docs/quality/ccp-savings/`. Validate and
rebuild the generated report with:

```bash
uv run python scripts/ccp_savings_report.py validate \
  --root docs/quality/ccp-savings
uv run python scripts/ccp_savings_report.py render \
  --root docs/quality/ccp-savings \
  --output docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
make ccp-savings-check
uv run python scripts/ccp_savings_report.py promotion-status \
  --root docs/quality/ccp-savings --json
```

Corrections append a record with `supersedes`; they never rewrite an accepted
observation. Failed, cancelled, fallback, excluded, non-comparable, and
superseded records remain visible but do not enter the savings numerator.
Provider billing and monetary fields remain `null` without an independently
digested provider export.

## Activation and rollback gates

Hosted Linux work may be conditionally skipped only after all of these are
terminal and separately reviewed:

- matrix-aware preflight gap resolved;
- exact-head local/hosted parity across the required change classes;
- missing, malformed, stale, corrupt-digest, wrong-SHA, wrong-policy, and
  incomplete receipts fail closed;
- two hosted fallback routes pass;
- latest-head status behavior is observed across PR lifecycle events;
- branch-protection change is explicitly authorized;
- one-command rollback restores unconditional hosted Linux work;
- the exact signed squash result still runs full hosted `main` CI.

Until then, the proposed evidence claim remains `proposed`, and every release,
publication, and merge gate is independent.
