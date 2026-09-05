---
type: execution-goal
title: Logseq DB Read-Only Compatibility Persistent Goal
description: Restart-safe goal for delivering evidence-backed experimental Logseq DB reads without weakening Matryca Plumber's existing graph safety.
resource: docs/quality/LOGSEQ_DB_READ_ONLY_COMPATIBILITY_PERSISTENT_GOAL_2026-09-05.md
tags: [logseq-db, interoperability, read-only, trama, quality, roadmap]
timestamp: 2026-09-05T00:00:00Z
status: draft
decision_status: approved
classification: active
last_verified: 2026-09-05
stale_after: 2027-03-04
audience: [maintainer, contributor, agent]
owner: integrations
authority: execution-goal
execution_mode: gated
source_repository: MarcoPorcellato/matryca-plumber
source_ref: origin/main
source_commit: 12ca79cb14f9bbdf196ec409a48025afb6503ca1
official_okf_spec_version: "0.2"
official_okf_conformance: not_claimed
matryca_quality_profile: "1.0"
registry_projection: reviewed_only
valid_terminal_outcomes:
  - experimental_read_compatibility
  - capability_no_go
  - upstream_blocked
self_amendment: forbidden
related:
  - ../superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md
  - ../roadmaps/TINE_LOGSEQ_ECOSYSTEM_INTEGRATION_STRATEGY_2026-08-12.md
---

# Logseq DB Read-Only Compatibility Persistent Goal

Deliver one evidence-backed terminal outcome for experimental Logseq DB
read-only compatibility according to the canonical implementation plan at
`docs/superpowers/plans/2026-09-01-logseq-db-read-only-compatibility.md`.
Success means exact graph identification, one page read, and one complete
ordered block-subtree read through a supported official Logseq host surface.
An honest public capability NO-GO or upstream-blocked result is also valid when
the plan's stopping gates prove it.

Before every milestone, verify live repository and GitHub state, current
official Logseq source, documentation, release artifact and issue state,
Matryca Trama contract state, exact branch base, and required checks. Start from
the last known Plumber anchor
`12ca79cb14f9bbdf196ec409a48025afb6503ca1` only if it still matches the
selected public base. Dated anchors are evidence, not permanent compatibility
claims.

Execute the canonical plan in dependency order using short-lived trunk-based
branches and one independently reviewable concern per pull request. Use the
exact CLI bundled with the selected Logseq artifact first, the official plugin
SDK second, and MCP stdio third. Keep MCP HTTP blocked while upstream issue
#1101 remains open. Bind every result to exact code, artifact, fixture, command,
platform, and evidence digests.

Preserve these hard boundaries: never access Logseq internal `db.sqlite` as an
integration shortcut; never invoke graph switching, mutation, sync, import,
export, or arbitrary query during the initial spike; never use a real user
graph; never treat an unexpected server replacement as harmless. Existing
Logseq OG, Shadow DB, Strict Read Only, CLI, and MCP behavior must remain
unchanged. Events, DB-source Shadow acceleration, all DB writes, and Matryca
Brain integration remain separate programmes.

Matryca Trama owns official Logseq host adapters and normalization into
`trama.logseq.read/v1`. Matryca Plumber owns the transport-neutral consumer
session boundary and agent-facing routes. Keep the filesystem `GraphReadPort`
unchanged; a DB graph must never fall back to Markdown. Introduce
`GraphSessionReadPort` only after the capability spike proves graph identity
and complete subtree semantics.

Reduce `get_graph_read_port` only in the separate characterization-first Clean
Architecture lane defined by the plan. The current selector has a CRITICAL
transitive blast radius. Do not change its public signature, filesystem-only
ownership, Shadow health/fallback semantics, or wheel-probe behavior until the
characterization PR passes. Never add DB selection to it.

Use deterministic tools first. Delegate bounded inventory, documentation,
fixtures, test execution, and log distillation to Luna. Delegate ordinary
implementation, cross-file integration, and focused architecture review to
Terra. Keep final evidence reconciliation, data-integrity and persistence
judgment, transport selection, release claims, and external authorization
boundaries with the primary orchestrator; escalate only a named unresolved
high-risk decision. Independently verify every delegated result against exact
bytes, refs, and terminal checks.

Proceed autonomously through read-only work and explicitly authorized local
edits. Treat commit, push, pull request, issue mutation, merge, branch deletion,
tag, release, package publication, external download, and execution against a
Logseq artifact as separate gates unless the current authorization names that
exact action and scope. Never convert running, skipped, stale, mismatched, or
partial evidence into PASS.

At every interruption or pull-request boundary, record repository, worktree,
branch, exact HEAD and base, dirty state, checks, evidence digests, negative
results, unproven gates, and next dependency. Continue until every canonical
completion item is either proven or closed by one valid terminal outcome. This
goal may point to the plan but must never redefine its requirements.

## Current execution checkpoint

The planning refresh is isolated at
`/private/tmp/matryca-logseq-db-plan-refresh-20260905` on branch
`docs/logseq-db-plan-refresh-20260905`, based on
`12ca79cb14f9bbdf196ec409a48025afb6503ca1`. Its pending diff is documentation
only. On 2026-09-05, documentation inventory generation, `docs-check`,
`docs-audit`, whitespace validation, and local code-graph change detection all
passed; the last check classified the change as low risk with no affected
runtime process.

Task 3 is now constrained to a Plumber consumer-evidence policy. It references
Trama's `trama.logseq.read/v1` authority and must not copy a wire schema, widen
Trama's current OG-only consumer, or claim DB support before the exact host
spike. The first implementation slice may contain only `unverified` and
negative fixtures. The next gated action is the signed local planning commit;
push, pull request, issue mutation, merge, download, and Logseq execution remain
separate authorization boundaries.
