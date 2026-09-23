---
type: audit
title: Logseq DB bundled CLI DB-0 admission blocker — 2026-09-19
description: Public-safe official-source evidence that blocks the bundled Logseq CLI lane before any DB-0 execution attempt.
resource: docs/quality/LOGSEQ_DB_CLI_DB0_ADMISSION_BLOCKER_2026-09-19.md
tags: [logseq, database, compatibility, provenance, safety]
last_verified: 2026-09-19
stale_after: 2026-12-18
status: blocked
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - LOGSEQ_DB_CLI_STATIC_SCHEMA_EVIDENCE_2026-09-15.md
  - LOGSEQ_DB_CLI_RECOVERY_OBSERVER_SAFETY_DESIGN_2026-09-16.md
  - LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md
  - EVIDENCE_INDEX.md
---

# Logseq DB bundled CLI DB-0 admission blocker — 2026-09-19

## Verdict

**`upstream_blocked` for the bundled-CLI lane before DB-0 admission.**

The official CLI documents selectors that could potentially identify a graph and
read a page or a bounded subtree. That is not sufficient to run the DB-0
qualification. Its documented normal startup can create or reuse a worker,
clean stale lock state, and replace a revision-mismatched server. The current
DB-0 profile forbids every semantic, metadata, worker, lock, and lifecycle
change.

No executable, artifact, fixture, graph, database, or user root was opened or
changed for this decision.

## Official-source findings

The official CLI document at
[`logseq/logseq@eddbe5f95b380c88578c76cd25854e63123a0251`](https://github.com/logseq/logseq/blob/eddbe5f95b380c88578c76cd25854e63123a0251/docs/cli/logseq-cli.md)
(CLI blob `d3d7ca6961b6b626ce83bb5a1b7be028d47de51a`; repository tree
`a7c0d90718ec715fb196a4309a16a746a5191c15` at observed source commit
`274eae1ffe66110aa92d51170722aa1ac620601c`)
describes `graph list`, `graph info`, and `show` selectors and supports JSON or
EDN output. It also documents that CLI startup manages `db-worker-node`, uses
lock-file discovery, may replace a server with a revision mismatch, and cleans
stale lock or orphan state. Those lifecycle semantics are incompatible with a
no-change DB-0 observer.

The official DB-version document at
[`logseq/docs@08f855f24d66e4509b7ea808554c13b4649e6ee1`](https://github.com/logseq/docs/blob/08f855f24d66e4509b7ea808554c13b4649e6ee1/db-version.md)
(tree `3309b25a2a603036a1a56b51d6e38d206c8106a6`; blob
`7d991fef94604133cb5f9c75f4296fb2a7047490`) and the official
[Plugin documentation](https://logseq.github.io/plugins/) show that DB graphs
are scriptable, but they do not publish a versioned, signed, immutable
read-observer contract. Observed official nightly release `248188362` uses the
mutable `nightly` tag, targets `dde0aba2d441c962d28989b0af894cc261da3898`, and
is marked prerelease; it is not a stable CLI capability record.

The official MCP documentation and tracker do not close this CLI finding. MCP
HTTP remains prohibited while [db-test #1101](https://github.com/logseq/db-test/issues/1101)
is open (state observed 2026-09-19). The reported headless `getPage` failure
for pages containing blocks in [logseq #12783](https://github.com/logseq/logseq/issues/12783)
is also open as observed on 2026-09-19. It is negative evidence for using MCP
as complete ordered-subtree evidence without a separate transport lane.

## Missing DB-0 admission bindings

The following upstream-owned bindings are absent from the public material:

- a canonical signed static-record schema;
- an official allowed signer identity or public-key fingerprint;
- an immutable capability manifest binding exact artifact bytes, embedded
  revision, and the documented command semantics;
- a documented observer-only mode that cannot create, reuse, stop, replace, or
  clean worker and lock state;
- an output-stability and complete-ordering guarantee for the required page and
  block-subtree payloads.

Therefore a Plumber implementation cannot create a trusted admission manifest
or safely interpret a bundled-CLI probe under DB-0. Local claims, a
self-authored signer, documentation-only selector examples, or a static
schema record cannot supply these missing upstream guarantees.

## Classification

This is not `capability_no_go`: the documented CLI exposes plausible selectors,
so absence of a required operation is not proven. It is `upstream_blocked`:
the official surface cannot cross the current strict admission boundary without
an upstream provenance and no-side-effect contract.

This blocks the **CLI transport lane only**. It does not complete #491, prove a
Plugin SDK or MCP result, or authorize another transport attempt.

## Next gate

Preserve this record and update #491 without closing it. The next permitted
programme activity is a separate, read-only Plugin SDK pre-admission evidence
review. It may not download, install, execute, or provision a Logseq artifact
unless a later exact authorization names that transport, artifact, fixture, and
stop boundary.
