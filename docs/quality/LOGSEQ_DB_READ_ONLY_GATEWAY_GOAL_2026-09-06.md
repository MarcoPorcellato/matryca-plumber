---
type: execution-goal
title: Logseq DB read-only gateway qualification
description: Restart-safe pointer for qualifying the smallest evidence-backed Logseq DB read surface through Plumber.
status: active
classification: active
authority: docs/decisions/2026-09-05-plumber-logseq-gateway-authority.md
owner: integration
last_verified: 2026-09-19
---

# Logseq DB Read-Only Gateway Qualification

This file is the restart-safe execution pointer for the next separately
authorized Plugin SDK pre-admission evidence review. It is operationally
subordinate to the accepted Plumber gateway decision and active tracking issue
[#491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491).
The historical plan and persistent goal remain useful evidence, but are
**historical and non-authorizing**. They must not be used to revive the former
Trama-owned `trama.logseq.read/v1` authority or to authorize runtime changes.

## Authority hierarchy

1. The accepted Plumber gateway decision defines ownership and forbidden paths.
2. The active gateway design defines architecture and contract boundaries.
3. The active implementation plan defines dependency order and completion.
4. Issue #491 defines the active public qualification objective and checklist;
   the payload-semantics ADR merged by PR #590 freezes semantics only.
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
| Plumber public main | `0bab28afdd10efaeff82d541d5b9b6552ebd5595`, tree `8ed111c8498e76b5d37609fb34400808d84c01a9` | Current rebaseline |
| Active tracking issue | Plumber #491 | Qualification objective; do not infer host support |
| Accepted decision | Payload-semantics ADR merged by PR #590 | No static contract or runtime support follows |
| Prior artifact attempt | PR #580 / main `00b56329ed9b44e6d1e0ab0a2b83afac502b5ba2` | Terminal `upstream_blocked` before execution |
| Active authority | `docs/decisions/2026-09-05-plumber-logseq-gateway-authority.md` | Accepted ownership decision |
| Active design | `docs/superpowers/specs/2026-09-06-logseq-db-read-only-gateway-design.md` | Additive payload and host-adapter boundary |
| Active plan | `docs/superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md` | Dependency order and definition of done |
| Active evidence | Private 2026-09-12 checkpoint | Exact 2026-09-08 DMG admission and later incomplete fixture attempt; raw evidence stays private |
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

PR #580 remains the historic `upstream_blocked` attempt: its selected official ZIP failed
Apple signature and Gatekeeper admission before execution. Preserve that result
unchanged. A separate 2026-09-08 official arm64 DMG passed artifact admission
and help-only CLI discovery; exact records remain private. The CLI revision
reported `be800f1-dirty`. This is artifact evidence only, not DB capability or
support evidence.

The later synthetic-fixture attempt stopped after nested insertion returned
only the root identifier. It is an ambiguous fixture-verification failure:
the nested tree remains unproven and no terminal transport classification
exists.

### 2026-09-15 CLI schema boundary

Read-only review of the exact upstream revision reported by the privately
admitted CLI established the documented command forms and one lifecycle result
shape, but not the JSON envelopes required for semantic read validation. The
exact source tree builds the shipped CLI from a generated Melange entrypoint
that is not present in that tree. The checked-in DB API wrapper returns worker
responses unchanged, and the checked-in server implementation defines the
structured `server stop` success/error result, but neither is the CLI JSON
serializer for property, graph, or `show` commands.

The exact admitted DMG was subsequently inspected statically under a read-only
mount. Its packaged CLI establishes a hash-bound JSON success/error envelope
and shallow command-data shapes for `graph info`, property listing, page/root
`show`, and server listing. The complete public-safe record is
[`LOGSEQ_DB_CLI_STATIC_SCHEMA_EVIDENCE_2026-09-15.md`](LOGSEQ_DB_CLI_STATIC_SCHEMA_EVIDENCE_2026-09-15.md).

At the time it was written, this removed only a `schema_blocked` state for a
proposed Gate B observer design. It is historical preparation evidence, not a
supported transport result. The 2026-09-19 CLI-lane `upstream_blocked` ruling
supersedes the proposed recovery route under DB-0; it cannot receive a later
execution authorization from this pointer.

The execution-safety design is recorded in
[`LOGSEQ_DB_CLI_RECOVERY_OBSERVER_SAFETY_DESIGN_2026-09-16.md`](LOGSEQ_DB_CLI_RECOVERY_OBSERVER_SAFETY_DESIGN_2026-09-16.md).
It excludes `server stop` under the current DB-0 profile, because lifecycle
changes remain forbidden until a separate evidence-profile decision exists.

## 2026-09-19 terminal CLI-lane boundary

The current official CLI documentation makes normal startup a potential
worker/lock/lifecycle transition. Public upstream material also lacks the
versioned signed provenance and read-observer contract required by the M1
execution-safety design. The terminal public-safe record is
[`LOGSEQ_DB_CLI_DB0_ADMISSION_BLOCKER_2026-09-19.md`](LOGSEQ_DB_CLI_DB0_ADMISSION_BLOCKER_2026-09-19.md).

The CLI lane is therefore `upstream_blocked` before admission and execution.
The earlier proposed recovery verification is superseded for DB-0 and must not
be revived from this pointer. Its historic evidence remains retained.

## Next bounded boundary

The next separate lane is **Plugin SDK pre-admission evidence review only**.
It may inspect public official documentation, source, release metadata, issue
state, and package provenance without downloading, installing, executing, or
provisioning an SDK, host, artifact, graph, or fixture. It must preserve the
same payload, identity, ordering, provenance, and zero-state-change criteria.

No Plugin SDK or MCP execution is authorized by this pointer. MCP HTTP remains
blocked while #1101 is open. The independent `get_graph_read_port` lane remains
unrelated and must not gain DB behavior.

The independent `get_graph_read_port` characterization and pure-selector lane
may proceed without becoming a prerequisite or acquiring any DB behavior.

## Current authorization boundary

The completed CLI decision consumed no artifact or execution authority. The
only next activity is the separately bounded, read-only Plugin SDK
pre-admission review described above. No lifecycle action, artifact download,
SDK installation, graph/fixture mutation, qualification probe, fallback, retry,
or MCP action is permitted by this pointer.

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

## Next gate

Perform only the Plugin SDK pre-admission evidence review. Preserve an exact
public-source record and a terminal `supported`, `capability_no_go`, or
`upstream_blocked` pre-admission result. Do not download, install, execute, or
provision an SDK, artifact, host, graph, or fixture; do not start MCP work.
