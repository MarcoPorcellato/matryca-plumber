---
type: Plan
title: Logseq DB read-only gateway implementation
description: Evidence-first implementation plan for graph identification, page content, and one complete ordered block subtree through a Plumber-owned official Logseq host adapter.
status: active
classification: active
audience: [maintainer, contributor, operator, agent]
owner: integration
verified: { by: human:marco-porcellato, at: '2026-09-06T00:00:00Z' }
last_verified: 2026-09-06
stale_after: 2027-03-05
tracking_issue: https://github.com/MarcoPorcellato/matryca-plumber/issues/491
related:
  - ../specs/2026-09-06-logseq-db-read-only-gateway-design.md
  - ../../decisions/2026-09-05-plumber-logseq-gateway-authority.md
  - ../../quality/LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../../quality/LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
---

# Logseq DB read-only gateway implementation plan

> **For implementing agents:** execute one numbered boundary at a time. Recheck
> its exact source, authority, evidence, and stop conditions before acting.
> Never weaken a failed gate or mix evidence from different transport attempts.

## Outcome

Experimentally qualify and then implement the smallest useful Plumber-owned
Logseq DB read surface:

1. identify one DB graph;
2. read one selected page with bounded content;
3. read one complete ordered block subtree with bounded content and permitted
   typed properties.

The result must be bound to one exact official host artifact, graph, session,
source revision, synthetic fixture, Plumber commit, and evidence record. Static
contracts, fixtures, unit tests, issue closure, and documentation do not by
themselves prove runtime compatibility.

## Authority and baseline

- Accepted architecture authority:
  [`2026-09-05-plumber-logseq-gateway-authority.md`](../../decisions/2026-09-05-plumber-logseq-gateway-authority.md).
- Active design:
  [`2026-09-06-logseq-db-read-only-gateway-design.md`](../specs/2026-09-06-logseq-db-read-only-gateway-design.md).
- Tracking work item: [Plumber #491](https://github.com/MarcoPorcellato/matryca-plumber/issues/491),
  under epic [#490](https://github.com/MarcoPorcellato/matryca-plumber/issues/490).
- Verified planning base: public
  `main@74884c38edb9cae445fa465969aa2c9cee5ecd1c`, tree
  `196df91996ebccb5f40cb37b927a4fbf55a4211a`. The draft began at
  `118b265b5c6b29682c76453aad5fbde0de0c841f` and was rebaselined after RC4
  qualification-plan PR #583 and frontend-security PR #585; neither changed
  graph contracts or graph runtime code.
- RC4 baseline: the existing three static contract families and three TCKs are
  packaged and installed with byte parity. Their bytes and meaning are a
  regression boundary, not DB runtime evidence.
- Prior CLI attempt: [PR #580](https://github.com/MarcoPorcellato/matryca-plumber/pull/580)
  records `upstream_blocked` before execution because the admitted ZIP failed
  Apple signature verification. Preserve it unchanged.
- Current upstream status observed on 2026-09-06: Logseq db-test #833 is closed;
  #1101 is open. Reverify both before relying on them.

The former Trama-owned DB plan and persistent goal are historical and
non-authorizing. Plumber is the sole Logseq gateway. Trama and Brain are future
consumers of versioned Plumber contracts.

## Hard boundaries

- `plumber.graph.read/v1` remains byte-compatible and content-free.
- Add content only through `plumber.graph.payload.read/v1`.
- `GraphReadPort` and `get_graph_read_port` remain filesystem/Shadow-only.
- No DB selection is added to `get_graph_read_port`.
- No Parser path for DB values.
- No direct SQLite, internal table, Datascript, debug query, or undocumented
  host access.
- No DB-to-Markdown fallback, hidden graph selection, inferred session, or
  retry through another source.
- No DB writes, events, sync, import/export, Shadow ingestion, UI, public
  endpoint, or active-desktop coexistence claim.
- MCP HTTP remains blocked while #1101 is open.
- Standard GitHub-hosted CI is authoritative for this public repository. Do
  not perform CCP heavy runs.

## Transport state machine

```text
bundled CLI attempt
  supported ----------> implementation
  capability_no_go ----> preserve evidence, then Plugin SDK attempt
  upstream_blocked ----> preserve evidence, then Plugin SDK attempt

Plugin SDK attempt
  supported ----------> implementation
  capability_no_go ----> preserve evidence, then MCP stdio attempt
  upstream_blocked ----> preserve evidence, then MCP stdio attempt

MCP stdio attempt
  supported ----------> implementation
  capability_no_go ----> terminal public NO-GO
  upstream_blocked ----> terminal upstream blocker
```

A new lane begins only after the preceding lane has a complete terminal record.
There is no within-attempt fallback. An ambiguous failure is checkpointed and
stopped; it is not automatically one of the three terminal outcomes.

## Phase 0 — Publish active execution authority

### Task 0.1: authority-document PR

- [ ] Add the active design, this plan, and the restart-safe goal.
- [ ] Reconcile their authority hierarchy with the accepted gateway decision.
- [ ] Preserve historical plans and evidence without rewriting their verdicts.
- [ ] Regenerate and curate `docs/knowledge/inventory.json`.
- [ ] Regenerate `docs/knowledge/inventory.md`.
- [ ] Add a concise newest-first entry to `docs/knowledge/log.md` when required
  by the documentation profile.
- [ ] Run `make docs-inventory-sync`, `make docs-inventory-md`, `make
  docs-check`, `make docs-audit`, and `make agents-check`.
- [ ] Run full `make ci` before merge.
- [ ] Verify exact diff, hosted CI, review state, base, and head before signed
  squash merge.

No Logseq artifact is downloaded or executed in this task.

## Phase 1 — Freeze the payload boundary

### Task 1.1: payload-contract ADR

Create one documentation-only PR that decides:

- [ ] contract identifier `plumber.graph.payload.read/v1`;
- [ ] page title/content representation;
- [ ] block content, ID, parent ID, and sibling ordinal representation;
- [ ] supported typed-property allowlist and unsupported-value behavior;
- [ ] byte, node, depth, property-count, key, and per-value limits;
- [ ] redaction and public-evidence policy;
- [ ] graph, session, source-revision, artifact, and provenance fields;
- [ ] completeness and contiguous sibling-order requirements;
- [ ] consumer intent and entitlement rules;
- [ ] additive relationship to content-free `plumber.graph.read/v1`.

The ADR defines semantics only. It adds no runtime route or support claim.

## Independent lane — Simplify `get_graph_read_port`

This lane is useful Clean Architecture work but is never a prerequisite for
host qualification.

### Task S.1: characterization PR

- [ ] Refresh code-audit impact evidence for `get_graph_read_port`.
- [ ] Record direct callers and affected flows.
- [ ] Add exact tests for its current signature, root validation and call
  order, healthy Shadow selection, unhealthy-Shadow Markdown fallback,
  handler behavior, and installed-wheel probe.
- [ ] Stop and warn before edits if impact remains high or critical.

### Task S.2: pure selector PR

Only after Task S.1 is merged:

- [ ] extract one private, pure readiness decision;
- [ ] preserve public behavior and exception ordering exactly;
- [ ] add no DB condition, session type, transport, or new fallback;
- [ ] run focused tests, code-audit change detection, and full hosted CI.

## Phase 2 — Bundled CLI host evidence

### Task 2.1: immutable artifact dossier

- [ ] Reverify the official Logseq release list and selected arm64 asset.
- [ ] Prefer the official `Desktop app Nightly Release 20260826` DMG candidate,
  asset ID `530968256`, only if its live identity still matches.
- [ ] Reverify its official size, release target, checksum-list entry, and
  previously observed SHA-256
  `ff81dd7513efa080a7f9bd122fca99d82f455a5c6745f154671b7530b8f8379b`.
- [ ] Bind current official source, CLI guide, DB guide, build workflow, #833,
  and #1101 to exact commits or immutable API evidence.
- [ ] Allocate a new attempt ID and private evidence root.

Stop before download on any provenance, license, platform, or identity
ambiguity.

### Task 2.2: artifact acquisition and admission

- [ ] Download only the selected official asset and checksum material.
- [ ] Verify size and SHA-256 before opening it.
- [ ] Mount the DMG read-only; do not copy it into a global application path.
- [ ] Verify the application and nested code signatures strictly.
- [ ] Verify Gatekeeper admission and notarization evidence.
- [ ] Record bundle ID, version, architecture, Team Identifier, executable
  digest, and embedded build/source revision where available.
- [ ] Stop with `upstream_blocked` if admission fails. Do not execute Logseq.

### Task 2.3: bounded CLI discovery

Only after artifact admission:

- [ ] invoke the bundled CLI only for `--version` and relevant help output;
- [ ] bind exact executable digest, root option, graph selector, structured
  output selector, documented example surface, and worker lifecycle;
- [ ] reject shell wrappers, ambient graph selection, global installation, and
  any undocumented command;
- [ ] decide whether the CLI can safely proceed to fixture provisioning.

## Phase 3 — Disposable fixture mutation

Fixture provisioning is mutation and receives no read-only credit.

### Task 3.1: create and freeze one synthetic graph

- [ ] Use a fresh private disposable root.
- [ ] Use only the admitted artifact's own documented examples or commands.
- [ ] Create one graph, one page, and one ordered three-level block subtree.
- [ ] Include only synthetic text and representative properties admitted by
  the payload ADR.
- [ ] Record generated graph, page, and block identifiers; parentage; sibling
  order; source revision; and lifecycle artifacts.
- [ ] Freeze a semantic graph fingerprint and fixture digest.
- [ ] Stop all provisioning processes and prove the fixture is terminal before
  the qualification boundary begins.

Never open a user graph, default Logseq root, account, sync configuration, or
internal database directly.

## Phase 4 — Separate read-only qualification

### Task 4.1: qualify the required operation set

From the frozen fixture, with explicit root and graph binding:

- [ ] capture a pre-read inventory and digest of every observed graph,
  metadata, worker, lock, and lifecycle object under the isolated root;
- [ ] identify the exact DB graph and source revision;
- [ ] read the selected page and verify bounded content and permitted typed
  properties;
- [ ] read the complete ordered subtree and verify IDs, content, parentage,
  contiguous sibling ordinals, depth, node count, and `complete: true`;
- [ ] bind all results to one graph, session, source revision, artifact,
  fixture, platform, and Plumber evidence profile;
- [ ] capture the equivalent post-read inventory and digests;
- [ ] reject every observed state change under the current DB-0
  `forbidden_state_changes: all` profile, including graph-semantic, metadata,
  worker, lock, and lifecycle changes, as well as graph switching, server
  replacement, stale-lock cleanup, unknown ownership, incomplete output,
  malformed payload, timeout, excessive payload, or identity drift.

This initial profile is isolated/headless only. Active-desktop coexistence is a
later, separately designed qualification.

Any lifecycle side effect is an unclassified stop under the current profile;
it is not permission to ignore the change, declare a terminal transport result,
or start the next transport. A later attempt may permit a declared lifecycle
artifact only after a separate evidence-profile decision defines its exact
paths, ownership, expected transitions, cleanup, fingerprinting, and failure
semantics.

### Task 4.2: terminal evidence PR

- [ ] Preserve raw bounded output privately with hashes.
- [ ] Publish only sanitized facts, structural digests, limitations, and the
  exact terminal result.
- [ ] Update #491 without closing it unless every programme completion item is
  proven.
- [ ] If unsupported or blocked, stop before adapter implementation and open
  the next transport lane as a new attempt.

## Phase 5 — Plugin SDK and MCP stdio fallback lanes

Repeat Phases 2–4 independently for each permitted fallback transport.

### Plugin SDK requirements

- [ ] Pin official package/source identity, version, license, lockfile, host
  application, plugin manifest, permissions, and graph selection.
- [ ] Keep the companion minimal and read-only.
- [ ] Provision and qualify only in the disposable synthetic root.
- [ ] Do not treat plugin lifecycle or active-desktop presence as generic
  coexistence evidence.

### MCP stdio requirements

- [ ] Pin the exact official producer and stdio transport.
- [ ] Prove one client/session and explicit graph identity.
- [ ] Preserve the same page, subtree, completeness, limits, provenance, and
  forbidden-change gates.
- [ ] Never start or probe MCP HTTP while #1101 is open.

## Phase 6 — Static payload contract after `supported`

Implement one short contract/package PR:

- [ ] `contracts/plumber.graph.payload.read/v1/schema.json`;
- [ ] `contracts/plumber.graph.payload.read/v1/manifest.json`;
- [ ] synthetic positive and negative fixtures;
- [ ] `scripts/run_plumber_graph_payload_read_v1_tck.py`;
- [ ] contract documentation;
- [ ] schema and TCK tests;
- [ ] `MANIFEST.in` package inclusion;
- [ ] `setup.py` contract/TCK resource inclusion;
- [ ] release-build wheel/sdist required-member checks;
- [ ] installed-package discovery and byte-parity tests;
- [ ] consumer-package policy only for deliberately admitted static intent.

All pre-RC4 packaged contract and TCK bytes must remain unchanged.

## Phase 7 — Pure session domain

Implement one transport-free TDD PR:

- [ ] immutable page and block payload value objects;
- [ ] bounded property value model;
- [ ] narrow session page and complete-subtree protocols;
- [ ] exact graph/session/revision validation;
- [ ] closed, expired, foreign, stale, unsupported, incomplete, malformed, and
  excessive-payload failures;
- [ ] pure service behavior and synthetic tests;
- [ ] graph-layer import-boundary tests.

`src/graph/` must not import `agent`, `daemon`, `rag`, Parser, subprocess, a DB
driver, or Logseq SDK code.

## Phase 8 — Selected official-host adapter

Implement one adapter PR only for the qualified transport:

- [ ] injected command or SDK runner;
- [ ] immutable executable/package, artifact, root, graph, session, revision,
  and timeout binding;
- [ ] strict structured-output decoding;
- [ ] output, time, node, depth, property, and text limits;
- [ ] deterministic error mapping;
- [ ] no shell, ambient config, fallback, retry through another transport,
  Parser, SQLite, Markdown, Shadow, write, event, sync, or UI behavior;
- [ ] synthetic transcript tests for success and every fail-closed boundary.

Likely CLI implementation location:
`src/agent/logseq_db_cli_adapter.py`. Final placement follows the accepted
layer boundaries, not convenience.

## Phase 9 — Composition and final qualification

### Task 9.1: composition PR

- [ ] Bind one qualified official-host adapter to one session service behind an
  experimental feature boundary.
- [ ] Preserve existing OG and Shadow composition unchanged.
- [ ] Add no public CLI, MCP, HTTP, FastAPI, UI, Trama, or Brain surface.

### Task 9.2: exact integrated qualification

- [ ] Repeat graph identification, page read, and complete ordered subtree read
  through the Plumber composition boundary.
- [ ] Bind the result to the same exact artifact family and a freshly frozen
  synthetic fixture.
- [ ] Verify pre/post semantic state and every contract/TCK/package boundary.
- [ ] Record only an experimental exact-matrix claim.

## Phase 10 — Documentation and governance closure

- [ ] Update architecture and data-flow diagrams.
- [ ] Add an experimental support matrix naming exact supported versions and
  modes.
- [ ] Document installation, isolation, limits, failure behavior, privacy, and
  unsupported active-desktop/write/event/Shadow cases.
- [ ] Update evidence index, documentation inventory, knowledge log, and
  changelog where required.
- [ ] Reconcile #490, #491, #17, #492, and #493 without closing unrelated or
  deferred work.
- [ ] Run full local and hosted verification.
- [ ] Stop before any tag, release, PyPI publication, stable claim, or public
  endpoint. Those require a later release decision and authorization.

## PR discipline

- Start each branch from freshly verified current `main`.
- One concern per PR; merge before cutting its dependent child.
- Preserve dirty or divergent checkouts; use owned isolated worktrees.
- Signed commits and GitHub prose preserve maintainer-only authorship.
- No force-push.
- Before merge verify exact base/head, diff scope, review threads, required
  terminal-green checks, and expected skips.
- Use `--admin` only when the protected-main signature rule is the sole blocker.
- Delete only the successfully merged PR's remote branch.
- Preserve exact evidence and a restart checkpoint before removing a clean,
  merged, task-owned worktree.

## Verification matrix

Every documentation PR:

```text
make docs-inventory-sync
make docs-inventory-md
make docs-check
make docs-audit
make agents-check
```

Every code or contract PR additionally runs focused tests, relevant TCKs,
`tests/test_graph_layer_boundary.py`, code-audit change detection, full
`make ci`, and exact-head hosted CI. Archive/package changes additionally build
wheel and source distributions from a clean tracked snapshot and verify
installed-resource discovery and byte parity.

## Delegation

- Bounded evidence delegate: official-source research, fixture catalogue,
  documentation, deterministic fixtures/tests, CI monitoring, and private-log
  distillation.
- Implementation delegate: ordinary implementation, integration, and focused
  architecture review.
- Primary orchestrator: transport choice, contract rulings, artifact admission,
  persistence and data-integrity judgments, runtime qualification, external
  mutation verification, and final terminal verdict.
- High-risk resolver: only a named unresolved security, concurrency,
  persistence, or data-loss problem outside the implementation delegate's safe
  decision envelope.

Delegated output is orientation until the primary orchestrator verifies exact
bytes, refs, tests, and evidence.

## Restart checkpoint

After every authorization, artifact, fixture, terminal probe, commit, PR, merge,
and cleanup, update the restart-safe goal with:

- timestamp and authority version;
- exact repository, main, branch, base, head, tree, and dirty state;
- attempt ID, transport, platform, artifact and source identities;
- fixture and result digests;
- commands or deterministic test surface;
- terminal/running/blocked state;
- delegated work and independent verification;
- negative evidence and unresolved gates;
- next exact action and remaining authorization.

## Definition of done

The programme is complete only when either:

1. one official transport has terminal `supported` evidence for all three
   operations, the additive payload contract and selected adapter are
   implemented and packaged, the integrated Plumber path passes exact
   qualification, hosted CI is green, documentation is current, and no stable
   release claim has been made; or
2. CLI, Plugin SDK, and MCP stdio each have immutable terminal
   `capability_no_go` or `upstream_blocked` evidence, #491 records the public
   limitation, and no unsupported runtime path was introduced.

Acceptance criteria never shrink to manufacture completion.
