---
type: Specification
title: Hybrid Commit CI Preflight adoption design
description: Fail-closed architecture for replacing duplicated pull-request Linux checks with exact-head local receipts while retaining trusted hosted fallbacks and measurable savings evidence.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-24
stale_after: 2027-02-20
---

# Hybrid Commit CI Preflight Adoption Design

## Executive decision

Matryca Plumber will adopt Commit CI Preflight (CCP) as a hybrid pull-request
qualification path. The local path may replace only reproducible Linux work for
eligible maintainer branches. GitHub remains authoritative for repository-event,
security, native-platform, protected-environment, release, and publication work.

The rollout is deliberately reversible:

1. bootstrap the repository contract without skipping hosted checks;
2. produce exact-head CCP receipts and compare them with hosted results;
3. exercise missing, corrupt, stale, mismatched, and hosted-fallback paths;
4. require the receipt-or-fallback decision only after terminal parity evidence;
5. skip duplicated hosted Linux work only for eligible same-repository PRs;
6. retain full hosted qualification on the signed squash result on `main`;
7. preserve machine-readable savings observations for a later public case study.

This design does not treat an unsigned CCP receipt as producer identity, does
not accept fork-provided evidence, and does not weaken review or branch
protection when local infrastructure is unavailable.

## Outcome

An eligible maintainer PR can prove the Python 3.12, Python 3.13, and Node.js 22
Linux checks on admitted local hardware. A small trusted GitHub workflow verifies
the exact-head receipt and repository policy. GitHub-hosted Linux duplication is
then skipped, while external contributors and any uncertain local state use the
existing hosted path.

The repository also retains an append-only evidence series that distinguishes:

- observed hosted compute;
- observed CCP local execution;
- observed remote verifier compute;
- estimated avoided hosted compute;
- provider-reported billed minutes, when independently available;
- monetary savings, only when supported by an explicit billing source.

## Authoritative anchors

| Item | Verified state | Evidence |
| --- | --- | --- |
| Matryca Plumber base | `main@48eae93b1152c9fe7d1f19d63de3f781b686932e` | Fresh `git fetch origin main` on 2026-08-24 |
| Delivery branch | `docs/ccp-hybrid-adoption-20260824` | Isolated worktree created from the verified base |
| CCP reviewed source | `866db18a571f55ed3d9b481d6c9c9c3bd5e98d55` | Current `commit-ci-preflight` `origin/main` on 2026-08-24 |
| CCP producer version | `commit-ci-preflight 0.1.0` | Installed CLI version; source identity remains separately unproven |
| Current required check | `Ironclad Gatekeeper` | Active GitHub rulesets `17295807` and `16516530` |
| Documentation profile | OKF v0.2 plus Matryca profile v1.0, target MKQ-4 | `docs/knowledge/profile.md` |
| Matryca Knowledge MCP | degraded: `sources.toml` unavailable | `matryca_status` failure on 2026-08-24 |

Every drift-prone anchor must be reverified before a local qualification, push,
PR, ruleset change, merge, or cross-repository publication.

## Status vocabulary

- **Observed:** raw source evidence was collected without authorizing routing.
- **Comparable:** local and hosted runs bind the same source SHA and required
  check set.
- **Qualified:** every required check and integrity gate is terminal PASS for
  the exact source SHA.
- **Eligible:** a same-repository maintainer PR satisfies the approved routing
  contract and has a fresh qualified receipt.
- **Fallback:** hosted Linux validation was selected and completed instead of
  local authorization.
- **Inconclusive:** evidence is missing, stale, non-terminal, mismatched, or not
  comparable; it cannot authorize a skip.
- **Saved estimate:** observed hosted candidate seconds minus observed verifier
  seconds for an eligible PR. It is not billing evidence.
- **Provider-confirmed saving:** a billing export independently confirms the
  avoided billed quantity.

## Verified current-state audit

The current `CI` workflow runs on pull requests and pushes to `main`:

| Job | Current role | CCP disposition |
| --- | --- | --- |
| Dependency Review | GitHub event and dependency graph | Retain on GitHub |
| Ironclad Gatekeeper | Python 3.12, documentation, typing, tests, frontend | Candidate for exact-head local replacement on eligible PRs only |
| Python 3.13 evidence | Compatibility evidence, currently non-blocking | Candidate for exact-head local replacement on eligible PRs only |
| Shadow contract on macOS | Native-platform evidence | Retain on GitHub |
| Shadow contract on Windows | Native-platform evidence | Retain on GitHub |
| CodeQL Python and JavaScript | GitHub security analysis | Retain on GitHub |
| Release and publication workflows | Protected release control plane | Retain on GitHub |

The full hosted `main` run remains necessary because the repository uses signed
squash merges: the resulting `main` commit is not the pull-request head attested
by the CCP receipt.

## Trust architecture

```text
clean exact PR-head commit on maintainer branch
                    |
                    v
       host resource and admission gates
                    |
                    v
     pinned multi-runtime CCP execution
                    |
                    v
      receipt bound to exact source SHA
                    |
                    v
ccp-evidence/<40-hex-source-sha> (append-only)
                    |
                    v
trusted pull_request_target verifier
  - trusted base policy only
  - pinned CCP verifier source only
  - receipt treated only as bounded data
  - no PR code execution
                    |
          +---------+---------+
          |                   |
          v                   v
 eligible internal PR     hosted fallback
 skip duplicated Linux   run full Ironclad
                    |
                    v
 GitHub-only checks remain required in both routes
```

The trusted workflow must never check out and execute PR-head code under
`pull_request_target`. It may read the trusted base, pinned CCP verifier source,
and the exact SHA-derived evidence branch. The receipt remains unsigned
integrity and policy evidence; it does not prove who controlled the producer.

## Local matrix contract

The first candidate contract uses CCP schema `2.0`, which is designed for one
receipt spanning independently pinned runtimes:

| Runtime ID | Immutable image candidate | Required checks |
| --- | --- | --- |
| `python312` | `ghcr.io/astral-sh/uv@sha256:e5b65587bce7de595f299855d7385fe7fca39b8a74baa261ba1b7147afa78e58` | dependency sync, version consistency, format, Ruff, mypy, sandbox read check, agent coherence, public-metrics policy, documentation, generated prompt, pytest |
| `python313` | `ghcr.io/astral-sh/uv@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca` | dependency sync and full Python 3.13 pytest evidence |
| `node22` | `docker.io/library/node@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436` | `npm ci`, lint, test, and build |

These registry index digests were resolved read-only on 2026-08-24. They are
planning candidates until source, architecture selection, installed runtime,
package-lock behavior, cold-cache behavior, and exact plan digests pass the
qualification milestone.

The source mount remains read-only. Declared writable mounts cover only the two
Python environments, uv cache, mypy cache, coverage output, Hypothesis state,
npm cache, `frontend/node_modules`, and `frontend/dist`. Explicit argv binds
runtime-local environment values; no host secret is inherited.

Network access is enabled only because locked Python and npm dependencies may
need a cold-cache download. Exact lockfiles and image digests are evidence, but
the first contract is not a fully offline or hermetic build claim.

CCP schema `2.0` does not currently carry all later single-runtime schema
`1.2`/`1.3` storage, no-pull, and disabled-swap declarations. The first pilot
therefore claims only the multi-runtime contract actually proven by its plan,
receipt, macOS resource admission, watchdog, and runtime limits. Expansion of
the claim requires a separately reviewed CCP contract evolution.

## Pull-request routing contract

| PR state | Receipt decision | Hosted Linux path | Merge effect |
| --- | --- | --- | --- |
| Same-repository maintainer PR, fresh valid receipt | PASS | Skipped only after activation milestone | May proceed if every other required check passes |
| Same-repository maintainer PR, missing/invalid/stale/mismatched receipt | FAIL | Not silently substituted | Blocked until a fresh receipt or explicit fallback |
| Same-repository maintainer PR with trusted `ci:hosted-fallback` label | Fallback selected | Full hosted path | May proceed after hosted and retained checks pass |
| Fork PR | Fallback selected | Full hosted path | Fork receipt is ignored |
| Dependabot PR | Fallback selected | Full hosted path | Hosted dependency and Linux checks remain authoritative |
| Push to `main` | Receipt not applicable | Full hosted path | Qualifies the exact merged commit |

`Ironclad Gatekeeper` remains a required context. The receipt-or-fallback status
is added as a second required context only after observation proves it attaches
to the latest PR-head SHA. Job-level conditions are used for hosted skips;
workflow-level path or commit filters must not leave a required context pending.

The fallback label is controlled by repository writers. It is a routing choice,
not a waiver: it authorizes the hosted path and never marks a failing check as
successful.

## Failure and recovery rules

- `resource status` must be supported/enforced and return `admit`.
- `admission status` must be readable with no active owner and an empty queue
  before starting a heavy run.
- Unknown, denied, unsafe, malformed, or ambiguous coordinator state blocks the
  run. Lock, ticket, lease, and coordinator files are never deleted manually.
- The Docker-compatible runtime must be responsive and unaccounted containers
  must be absent.
- The checkout must be clean and its exact SHA must match the intended PR head.
- Any check failure, timeout, pressure cancellation, receipt mismatch, or
  evidence-publication failure is inconclusive or failed, never a partial PASS.
- Evidence branches are append-only. No force-push or replacement of a prior
  receipt is allowed.
- Interruption preserves the source branch, receipt, journal, evidence branch,
  exact HEAD, and next recovery command.
- Hosted fallback remains available without weakening the rulesets.

The currently installed CLI is not ready for an official pilot: resource status
is `unknown` and admission inspection reports an unsafe coordinator layout at
the local admission root. That state must receive read-only diagnosis and an
independently authorized repair before any official CCP run.

## Savings evidence contract

### Evidence layout

```text
docs/quality/ccp-savings/
├── schema-v1.json
├── baseline/
│   └── <date>-<cohort-id>.json
└── observations/
    └── <date>-pr-<number>-<12-hex-sha>.json

docs/quality/CCP_GITHUB_ACTIONS_SAVINGS_CASE_STUDY.md
```

Each observation is immutable once merged. Corrections create a superseding
record that names the previous `record_id`; they do not rewrite historical
facts. The Markdown case study is generated deterministically from accepted
records and is never the numerical source of truth.

### Required observation fields

- schema version, record ID, classification, capture time, and supersession;
- repository, PR number, exact source SHA, and eligibility reason;
- GitHub workflow/run/job IDs, names, conclusions, timestamps, and elapsed
  seconds;
- CCP receipt digest, source SHA, policy/configuration digests, runtime IDs,
  terminal results, and local elapsed seconds when present;
- remote verifier run ID, conclusion, timestamps, and elapsed seconds;
- fallback reason when the hosted path ran;
- observed candidate hosted seconds;
- estimated avoided hosted seconds;
- observed verifier seconds;
- estimated net hosted seconds saved;
- provider-confirmed billed minutes and money only when an independent billing
  source exists; otherwise both fields are `null`;
- limitations and source URLs.

Cancelled, failed, skipped, draft-only, stale, non-comparable, or superseded
runs remain visible but do not enter the saved-compute numerator.

### Baseline

The initial comparable cohort contains six successful PR runs observed on
2026-08-19. For `Ironclad Gatekeeper` plus Python 3.13 evidence, the combined
durations were 314, 314, 325, 322, 316, and 339 seconds. The median was 319
seconds and the arithmetic mean was approximately 321.7 seconds.

One successful CCP receipt-gate sample from run `32330532453` took 50 seconds,
including 40 seconds to build the trusted verifier. The initial planning
estimate is therefore:

```text
median candidate hosted compute              319 seconds
- observed remote CCP verifier                50 seconds
= estimated net hosted compute avoided       269 seconds per eligible PR
```

This calculation does not establish billed minutes, account credits, energy
use, monetary savings, or a universal performance result.

## Public case-study promotion rule

A publication candidate for the CCP repository requires all of the following:

- at least 10 eligible, terminal, comparable PR observations;
- at least 21 calendar days between the first and last accepted observation;
- at least two successful hosted-fallback observations;
- negative evidence for missing, stale, corrupt, and SHA-mismatched receipts;
- separate counts for eligible, fallback, failed, cancelled, and excluded runs;
- median, interquartile range, total observed candidate seconds, total verifier
  seconds, and net estimated seconds saved;
- provider billing values kept `null` unless independently exported;
- exact Matryca Plumber and CCP source anchors;
- documented limitations, maintenance effort, and producer-identity boundary;
- a separately authorized PR to `commit-ci-preflight`.

The case study may report null or negative savings. The publication goal is
reproducible evidence, not a predetermined success narrative.

## Scope

- Repository CCP configuration and verification policy.
- Trusted receipt verification workflow.
- Hosted fallback and later conditional Linux-job routing.
- Local operator runbook and deterministic contract tests.
- Baseline, immutable observations, generated savings report, and publication
  export contract.
- Ruleset rollout and rollback procedure.
- Documentation inventory, evidence index, and knowledge-log integration.

## Non-goals

- Replacing CodeQL, Dependency Review, native macOS/Windows checks, releases,
  signing, publication, or protected-environment jobs.
- Accepting fork-produced receipts as trusted evidence.
- Claiming cryptographic producer identity from unsigned receipt v2.
- Claiming local macOS execution is GitHub-hosted Linux-native evidence.
- Eliminating the exact merged-commit run on `main`.
- Publishing a CCP case study before its promotion rule passes.
- Reporting estimated seconds as provider-confirmed billing or money.
- Modifying CCP source or repairing its local coordinator without a separate
  evidence-backed gate.

## Ordered milestones

### M0 — Design and baseline

**Outcome:** approved architecture, implementation plan, persistent goal, and
historical baseline are versioned under the Matryca documentation profile.

**Exit evidence:** documentation inventory is synchronized; `make docs-check`,
`make docs-audit`, link validation, and diff checks pass.

### M1 — Bootstrap contract

**Outcome:** schema-v2 CCP config/policy, cache exclusions, contract tests,
trusted receipt gate, operator runbook, and savings schema/report tooling exist.
Hosted CI remains fully authoritative and no job is skipped.

**Exit evidence:** parser/schema tests, trusted-workflow security tests, report
goldens, CCP `plan`, `doctor`, and `dry-run` pass on the exact bootstrap head.

### M2 — Local runtime qualification

**Outcome:** a reviewed CCP binary built from the pinned source, a safe
coordinator, admitted host, cached images, and clean exact-head matrix run
produce a valid receipt.

**Exit evidence:** source/build receipt, resource and admission PASS, terminal
matrix receipt, independent policy verification, and post-run cleanup evidence.

### M3 — Parallel parity pilot

**Outcome:** at least five representative PR heads run both CCP and hosted Linux
checks with identical required-check dispositions. Negative and fallback tests
are terminal.

**Exit evidence:** source-bound comparison records for Python, frontend,
documentation, dependency, and mixed changes; missing/corrupt/stale/SHA mismatch
fail closed; fork and maintainer fallback run hosted checks.

### M4 — Routing observation

**Outcome:** the receipt-or-fallback status attaches to the latest PR-head SHA
without changing required checks or skipping work.

**Exit evidence:** current-head status observations, no pending-context defect,
ruleset rollback instructions, and explicit maintainer authorization for the
activation change.

### M5 — Savings activation

**Outcome:** eligible internal PRs skip duplicated Linux jobs only after receipt
PASS; all other routes run hosted Ironclad; `main` remains full hosted.

**Exit evidence:** exact-head CI, required ruleset contexts, fallback test,
post-squash `main` run, and first accepted savings observation.

### M6 — Measurement window

**Outcome:** immutable observations cover the publication sample and the
generated Matryca case study reports positive, null, and negative outcomes
without billing overclaims.

**Exit evidence:** promotion-rule checker passes and generated Markdown is
byte-identical.

### M7 — CCP case-study publication

**Outcome:** a separately reviewed case-study PR proposes the bounded Matryca
results to `commit-ci-preflight`.

**Exit evidence:** exact export digest, source links, CCP repository checks, no
producer-identity overclaim, and separate user authorization for push and PR.

## Validation and publication gates

- Deterministic tests precede local container execution.
- `commit-ci-preflight plan`, `doctor`, and `dry-run` precede `run`.
- Official local runs require supported/enforced admission and an exact clean
  source SHA.
- `make agents-check`, `make docs-check`, `make docs-audit`, and `make ci` remain
  the repository gates for implementation branches.
- GitHub observation precedes required-status activation.
- Ruleset mutation, push, PR, merge, and cross-repository publication remain
  separate authorization gates.
- Matryca Knowledge MCP conformity must be retried when `matryca_status` is
  healthy; the source repository remains authoritative while it is degraded.

## Delegation and cost policy

1. Use deterministic inspection and tests before LLM work.
2. Delegate independent inventory, fixtures, documentation mechanics, and log
   distillation to the cheapest suitable worker when available.
3. Keep architecture, workflow trust, rulesets, statistics, qualification, and
   publication decisions with the primary reviewer.
4. Assign one owner per file group and serialize overlapping writes.
5. Stop after one failed low-cost attempt and one focused correction.

## Interruption and recovery

Before interruption, record the worktree, branch, exact HEAD/base, dirty state,
active CCP/Docker/admission state, completed evidence, unproven gates, and next
commands. Preserve in-scope work through a local commit only when authorized.
Never rely on a temporary worktree path as the sole copy of valuable work.

## Completion checklist

- [ ] Bootstrap files and contract tests exist without skipping hosted CI.
- [ ] The pinned CCP binary and coordinator are independently qualified.
- [ ] The three-runtime exact-head receipt verifies against trusted policy.
- [ ] Five representative parity PRs and all negative/fallback cases pass.
- [ ] Receipt-or-fallback status is proven on the latest PR-head SHA.
- [ ] Ruleset activation is separately authorized and reversible.
- [ ] Eligible PRs skip only the duplicated Linux jobs.
- [ ] External, Dependabot, uncertain, and labelled fallback PRs run hosted CI.
- [ ] Every signed squash result receives the full `main` hosted run.
- [ ] Savings observations validate and remain append-only.
- [ ] The case-study promotion rule passes with at least 10 observations over
      at least 21 days and two hosted fallbacks.
- [ ] Matryca documentation inventory, evidence index, and knowledge log match
      current behavior.
- [ ] Cross-repository case-study publication has separate authorization and
      terminal CCP repository checks.

Completion is unproven until every applicable item has authoritative terminal
evidence.
