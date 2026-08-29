---
type: Runbook
title: Commit CI Preflight hybrid CI operator runbook
description: Fail-closed operating sequence for Matryca Plumber local qualification, exact-head receipt verification, hosted fallback, and savings evidence.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-29
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

## Current matrix contract

| Boundary | Value |
| --- | --- |
| Public receipt-verifier source | `3fccc197e5055a2759ee7afe51b91133938ec904` |
| Public verifier source tree | `9e478c1489a9926772e8ab8bea21bd57470494b6` |
| Public verifier qualification | five required checks PASS and independent verifier PASS; qualification receipt `sha256:2b6aec06b8b6cf6e07736c8e713dd05c03d439640c608cc52af124e93de290e7` (`sha256:0aa7ef0e9442b329a4ac71b6a3002d9331bef0f793cc9ab88d2f6a24fee3c0c5`) |
| Public verifier executable evidence | `commit-ci-preflight 0.1.0` — `sha256:b8d26013800c99ba806506a0539a9ddc781bfab52f95c8f1dbdff1b65c2fcd4c` |
| Latest official CCP documentation | `main@6ff736b1e2a1dfde8778330efdd4b82c845d45e7`, tree `8722c504d8fdf9196e8a71f615af501bc7de58e4`; GitHub verification `valid`, PR #72 merged, receipt status terminal `SUCCESS`; documentation, public-adoption, and test changes only after the runtime-equivalent PR #70 tree |
| Active local coordinator source | `27adf8d0820b3cd96f9c5e149de9b580ae41f639` — operational only; not the public verifier pin |
| Active local coordinator tree | `d8e0364d1313fde0898a44517ae6d233d9e10763` |
| Active installed executable | `commit-ci-preflight 0.1.0` — `sha256:c8021e2322e172686c0a0c07d2b0260eafb5812d085d2306dbbde3fe4e964bd4` |
| Active rollback executable | `sha256:7cde4c2888721d72fbb8c86b4fdcc75f992050979c5175a5bf10b0cecfa7c6f8` |
| Earlier rollback executable | `sha256:b8d26013800c99ba806506a0539a9ddc781bfab52f95c8f1dbdff1b65c2fcd4c` |
| Oldest retained rollback executable | `sha256:3c8621b8e834356ada379f3ad9bd916a7a884b2c4f4da7ffb606744ab79b4fa8` |
| Selected Matrix plan profile | `current-v2` — explicit across `plan`, `doctor`, and `dry-run` |
| Matrix configuration digest | `sha256:6f418ac6b90664e9ebbec4a5c7e28af946f0430250fcaf28b6a1f62196b4a635` |
| Non-selected legacy comparison | `matrix-v2-legacy-v1` produced `sha256:a583c176ccef26dbfbc1171d7715fdd5285fc30527d27f7b2c801ad170798f87`; this is a distinct policy/cache boundary, not accepted evidence |
| Node.js 22 runtime digest | `sha256:d42b8cca0aebe5ba215b961b9066666a12fd0ccb4bee2e53e5a85396899754d7` |
| Python 3.12 runtime digest | `sha256:0b022ab9c98c197c7a40c301d49ae6b0f871eb4153fab52b0ffb89ba9eb4a97b` |
| Python 3.13 runtime digest | `sha256:ff84d7597c7384b29ad598163b4c47323a27dc4b7b2f2ece91fb209c8abba327` |
| Receipt path | `.ccp/receipt.json` |
| Evidence branch | `ccp-evidence/<exact-40-hex-source-sha>` |
| Remote status | `commit-ci-preflight/receipt` |

Any config, policy, image, required-check, source, or digest change creates a
new qualification boundary. Never edit policy to match a completed receipt.

The trusted GitHub observer remains pinned to the signed, durable public
verifier source above. The newer active local coordinator has its own exact
qualification evidence, but that operational upgrade does not silently replace
the public verifier, transfer receipt compatibility, or authorize hosted skips.
Changing the workflow pin still requires the compatibility acceptance gate
below.

## Accepted source boundary

Task 6 Step 0 accepts source `3fccc197e5055a2759ee7afe51b91133938ec904` as
the reviewed public receipt-verifier boundary. Its qualification executable and
rollback evidence are recorded above. Matrix `plan`, `doctor`, and `dry-run`
support the three configured `runtime_id` values and render the declared source
and cache mounts. The resulting plan is the sole source of the policy digests
in this document. The source qualification remains bound to its recorded clean
source tree and terminal test receipt; it does not transfer to the active local
coordinator or any later source revision.

This acceptance is not an official matrix run, receipt, routing activation, or
hosted-skip authorization. Repository Make targets expose only the non-heavy
`ccp-plan`, `ccp-doctor`, and `ccp-dry-run` surfaces plus `ccp-verify` and
`ccp-savings-check`; there is deliberately no `ccp-run` target. A future heavy
operation must follow the explicit authorization and fresh-admission sequence
below.

This limitation does not weaken hosted CI. Unlabelled pull requests publish no
receipt status. A labelled observation fails closed when no valid receipt
exists, while the unconditional hosted workflow continues independently.

## Official guidance reconciliation

The current operator contract was checked against the official CCP
[adoption guide](https://github.com/MarcoPorcellato/commit-ci-preflight/blob/6ff736b1e2a1dfde8778330efdd4b82c845d45e7/docs/ADOPTION_GUIDE.md),
[local-run contract](https://github.com/MarcoPorcellato/commit-ci-preflight/blob/6ff736b1e2a1dfde8778330efdd4b82c845d45e7/docs/LOCAL_RUN.md),
[Matrix profile ADR](https://github.com/MarcoPorcellato/commit-ci-preflight/blob/6ff736b1e2a1dfde8778330efdd4b82c845d45e7/docs/adr/0005-matrix-v2-legacy-plan-profile.md),
and [PR #71 case study](https://github.com/MarcoPorcellato/commit-ci-preflight/blob/6ff736b1e2a1dfde8778330efdd4b82c845d45e7/docs/CASE_STUDY_PR71.md).

Matryca selects `current-v2` explicitly. The legacy profile exists only when a
current producer must reproduce historical Matrix digests accepted by an old
trusted verifier. It is never inferred from policy or evidence. The measured
legacy digest differs from Matryca's accepted policy, so selecting it would
require a separate compatibility, cache, receipt, and policy migration; this
runbook does not authorize that migration.

`dry-run` renders a planning and mount-review surface. It creates no replay
bundle and its lifecycle-managed cache paths must not be copied into a direct
container invocation. Any diagnostic reproduction must own and validate its
writable paths independently and remains diagnostic rather than qualification
evidence.

The official trusted receipt-v2 policy `1.1` reconstructs one single-runtime
plan from a trusted configuration and does not apply to the Matrix-only legacy
profile. Matryca's three-runtime policy remains schema `2.0`; migrating to a
future multi-runtime trusted-plan contract requires an explicit architecture
decision and complete requalification. Receipt verification proves integrity
and policy, not producer identity, signatures, arbitrary hosted parity, or an
unexecuted native platform.

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
unexpected skip, or incomplete negative case rejects a future candidate.
The previous source pin and its bootstrap findings remain historical evidence
under their original contract.

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
make ccp-doctor
make ccp-dry-run
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
- the explicit profile is `current-v2`, and dry-run output is reviewed but not
  executed as a replay command;
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
  --matrix-plan-profile current-v2 \
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

- the accepted source boundary is still current and independently rechecked;
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
