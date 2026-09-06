---
type: execution-goal
title: Logseq DB read-only gateway qualification
description: Restart-safe pointer for qualifying the smallest evidence-backed Logseq DB read surface through Plumber.
status: active
classification: active
authority: docs/decisions/2026-09-05-plumber-logseq-gateway-authority.md
owner: integration
last_verified: 2026-09-06
---

# Logseq DB Read-Only Gateway Qualification

This file is the restart-safe execution pointer for the next qualification
attempt. It is operationally subordinate to the accepted Plumber gateway
decision and the live issue [#491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491).
The historical plan and persistent goal remain useful evidence, but are
**historical and non-authorizing**. They must not be used to revive the former
Trama-owned `trama.logseq.read/v1` authority or to authorize runtime changes.

## Authority hierarchy

1. The accepted Plumber gateway decision defines ownership and forbidden paths.
2. The active gateway design defines architecture and contract boundaries.
3. The active implementation plan defines dependency order and completion.
4. Issue #491 defines the current public qualification objective and checklist.
5. This pointer defines restart state, attempt boundaries, and operator gates.
6. The active artifact-evidence record defines the last terminal result.
7. Live source, GitHub, and exact runtime receipts outrank dated anchors.

Plumber is the sole Logseq gateway. The future public contract and any DB host
adapter are Plumber-owned. `GraphReadPort` remains filesystem/Shadow-only.
Existing session identity and opaque topology behavior remains unchanged;
payload-bearing page and complete-subtree operations remain feature-off until
qualification passes.
Trama and Brain are consumers, never direct Logseq readers or Parser imports.

## Exact current anchors

| Surface | Anchor | Meaning |
| --- | --- | --- |
| Plumber public main | `74884c38edb9cae445fa465969aa2c9cee5ecd1c`, tree `196df91996ebccb5f40cb37b927a4fbf55a4211a` | Signed and GitHub-verified rebaseline after RC4 qualification-plan PR #583 and frontend-security PR #585 |
| Current issue | Plumber #491 | Open P0 capability qualification |
| Prior artifact attempt | PR #580 / main `00b56329ed9b44e6d1e0ab0a2b83afac502b5ba2` | Terminal `upstream_blocked` before execution |
| Active authority | `docs/decisions/2026-09-05-plumber-logseq-gateway-authority.md` | Accepted ownership decision |
| Active design | `docs/superpowers/specs/2026-09-06-logseq-db-read-only-gateway-design.md` | Additive payload and host-adapter boundary |
| Active plan | `docs/superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md` | Dependency order and definition of done |
| Active evidence | `docs/quality/LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md` | Exact failed CLI admission record |
| Closed page-read issue | `logseq/db-test#833` | Closed 2026-08-31; closure is not artifact evidence |
| MCP HTTP blocker | `logseq/db-test#1101` | Open; HTTP remains prohibited |

All anchors are reverified before every new boundary. A changed main commit,
Logseq source, artifact, Trama contract, platform, or #1101 state requires a
checkpoint and rebaseline; it never silently extends an old result.

## Objective and scope

Qualify, through one exact official host surface, only:

- graph identification and DB-mode detection;
- one page read;
- one complete ordered block-subtree read;
- graph/session/revision binding, bounded output, provenance, and zero forbidden
  state change.

The current DB-0 profile sets `forbidden_state_changes: all`. Pre/post evidence
therefore covers every observed graph, metadata, worker, lock, and lifecycle
object under the isolated root, not only semantic graph content. Any change is
an unclassified stop. It cannot trigger transport fallback or be accepted until
a separate evidence-profile decision explicitly defines the permitted
lifecycle transition and its cleanup semantics.

Transport order is: exact bundled CLI, official Plugin SDK, then MCP stdio.
MCP HTTP is blocked while #1101 is open. No support claim follows from static
docs, synthetic policy fixtures, or partial operation evidence.

## Completed boundary

The first exact official macOS arm64 bundled-CLI attempt is terminal
`upstream_blocked`: published and local digests matched, but Apple signature
and Gatekeeper admission failed before execution. No graph, fixture, transport,
worker, lock, configuration, or user data was touched. This evidence is
preserved in PR #580 and must never be reclassified or overwritten.

## Current and next boundaries

Current boundary: finish, verify, commit, publish, and merge the three active
authority documents from branch `docs/logseq-db-gateway-authority-20260906-v2`,
which started at public main `118b265b5c6b29682c76453aad5fbde0de0c841f`
and is rebaselined to exact current main
`74884c38edb9cae445fa465969aa2c9cee5ecd1c`. PR #583 changed RC4 qualification
documentation and tests; PR #585 changed frontend dependency security policy,
lock data, and tests. Neither changed graph contracts or graph runtime code. No
Logseq artifact is acquired or executed in this boundary.

After that merge:

1. freeze the additive `plumber.graph.payload.read/v1` semantics in one
   documentation-only ADR;
2. prepare a new bundled-CLI attempt, never a retry of #580;
3. reverify and admit the official arm64 DMG candidate;
4. stop with `upstream_blocked` on artifact-admission failure;
5. only after executable admission, provision one synthetic fixture in a fresh
   disposable root using documented official examples;
6. freeze runtime-generated identifiers and fixture digest;
7. run a separate read-only qualification for the three operations;
8. preserve exact raw-result digests, provenance, session/revision binding, and
   post-run forbidden-change evidence;
9. classify an admitted but insufficient read surface as
   `capability_no_go`, preserve it, and only then open the Plugin SDK lane.

The independent `get_graph_read_port` characterization and pure-selector lane
may proceed without becoming a prerequisite or acquiring any DB behavior.

## Approved authorization envelope

The maintainer-approved programme envelope permits:

- read-only repository, GitHub, release, issue, source, documentation, and
  artifact inspection;
- code-audit refresh and impact/change analysis;
- owned isolated worktrees, plan-defined local edits, deterministic tests, and
  signed commits;
- official provenance-bound artifact and SDK acquisition without global
  installation;
- at most one separately bounded artifact admission, synthetic-fixture
  provisioning, and read-only qualification attempt for each transport in the
  fixed CLI, Plugin SDK, MCP stdio order;
- scoped #490/#491 issue maintenance;
- short branch pushes, pull requests, hosted-CI monitoring, and sequential
  signed squash merges after every exact gate is green;
- `--admin` only when protected-main signature enforcement is the sole blocker;
- deletion of only a successfully merged PR branch and cleanup of only clean,
  merged, task-owned worktrees after checkpoint preservation.

The envelope is not permission to ignore prerequisites, combine attempts,
retry a consumed attempt, or continue after a stop condition. GPG failure stops
signing; no unsigned substitute is permitted.

Tags, releases, PyPI, stable support claims, DB writes, events, sync,
import/export, internal SQLite, DB-to-Markdown fallback, DB-source Shadow,
public UI, active-desktop coexistence claims, real user graphs, force-pushes,
and unrelated repository changes remain unauthorized.

## Attempt ledger template

Each attempt gets a new row and immutable evidence record:

| Field | Required value |
| --- | --- |
| `attempt_id` | New unique identifier; never reuse #580 |
| `plumber_commit` | Full 40-hex source commit and dirty state |
| `transport` | `cli`, `plugin_sdk`, or `mcp_stdio` |
| `artifact` | Release, asset ID, platform, size, all digests |
| `source` | Logseq source/docs/SDK exact commits |
| `fixture` | Disposable root, generated IDs, fixture digest |
| `probe` | Exact command/source commit and bounded limits |
| `result` | Raw-result digest plus terminal outcome |
| `forbidden_change` | Post-run state and zero-change evidence |
| `authorization` | Exact user gate and stop boundary |

## Checkpoint schema

At every interruption, record: timestamp; authority version; issue/PR state;
Plumber main and worktree; branch and full HEAD/base; dirty state; attempt ID;
artifact/source/platform digests; fixture/probe/result digests; delegated work;
terminal or running state; negative findings; unproven gates; next action; and
the exact authorization still required. Checkpoints must contain no secrets,
raw user data, local credentials, or unbounded logs.

## Terminal outcomes and stop rules

- `supported`: all three reads, identity, ordering, completeness, provenance,
  boundedness, and zero-forbidden-change gates pass for the exact matrix.
- `capability_no_go`: admitted host lacks a required selector, binding, order,
  completeness, or safe-read guarantee.
- `upstream_blocked`: artifact, host surface, signature, runtime, or upstream
  dependency cannot safely cross the admission boundary.

Stop immediately on drift, dirty/conflicted source, digest mismatch, signature
failure, missing capability, foreign/stale session, incomplete ordering,
payload overflow, forbidden state change, resource/authorization failure, or
unreviewed external mutation. Never reinterpret partial, stale, synthetic-only,
or documentation-only evidence as `supported`.

## Delegation ownership

A bounded evidence delegate may perform inventory, documentation, fixture
review, deterministic tests, and log distillation. An implementation delegate
may perform ordinary implementation, integration, and focused architecture
review. The primary orchestrator retains transport selection,
persistence/data-integrity judgment, final qualification, release/support
claims, and all external mutations. Delegated output is orientation until
independently verified against exact bytes, refs, and checks.

## Next executable action

Complete Phase 0 of the active plan: curate the documentation inventory and
knowledge log for the three new authority files, run the complete documentation
and repository gates, commit and publish the scoped branch, obtain exact-head
hosted CI, then conditionally signed-squash merge it. After checkpointing the
merge, cut the payload-contract ADR branch from freshly verified `main`.
