---
type: Audit
title: Logseq DB CLI recovery observer safety design — 2026-09-16
description: Non-executing design for one bounded bundled-CLI recovery observation against an already existing synthetic fixture.
resource: docs/quality/LOGSEQ_DB_CLI_RECOVERY_OBSERVER_SAFETY_DESIGN_2026-09-16.md
tags: [logseq, database, compatibility, qualification, provenance, safety]
last_verified: 2026-09-16
stale_after: 2026-12-15
status: proposed
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - LOGSEQ_DB_CLI_STATIC_SCHEMA_EVIDENCE_2026-09-15.md
  - LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md
  - EVIDENCE_INDEX.md
---

# Logseq DB CLI recovery observer safety design — 2026-09-16

## Decision

This document defines the preparation boundary for a private, non-executing
observer. It may validate only a separately authenticated admission manifest
and its own immutable inputs deterministically, but it must not start Logseq,
create or read a graph, stop a server, create a fixture, create captures, or
write runtime evidence. A later execution attempt needs its own exact
authorization.

The observer is limited to recovery verification of the existing synthetic
fixture. It is Gate B evidence only. It cannot qualify the bundled CLI
transport, advance to Gate C, select another transport, enable an adapter, or
make a product support claim.

## Immutable inputs

Before a future process creation, a separately reviewed runner must revalidate
the following exact bindings from a trusted admission manifest rather than
caller-controlled matching hashes:

- admitted DMG SHA-256 `1a71e4c0f8c304452b3126e03256141c365dd2c69197c516a05027811cef429f`;
- packaged `app.asar` SHA-256 `9c476c014b6d65efa2d707f612d5cd26a3adcc0af4c048f1bb52c01ee7799ca7`;
- embedded `js/logseq-cli.js` SHA-256 `b3710e5a0eba20272ab5e3b8bfe7a87b2697e283de109973cd4bf5910eb40a98`;
- containment from DMG to mounted application, `app.asar`, and the archived
  CLI path, offset, size, and digest;
- a distinct launcher or interpreter identity, digest, fixed argument prefix,
  and archived-entry identity; the archived JavaScript entry is not assumed to
  be an executable path;
- verified artifact signature and Gatekeeper result recorded by the separate
  artifact-admission evidence;
- observer program and configuration hashes;
- canonical synthetic-root path, fixture manifest digest, graph identifier,
  page identifier, and root-block identifier;
- an allowlisted command grammar, timeout, output-size limit, and private
  evidence-root path.

Any mismatch is a pre-launch stop. The observer must not repair, infer, or
replace an input.

The trust anchor is not a caller argument. A future verifier pins, in reviewed
source, the canonical digest of this static-evidence record, an admission
manifest schema version, and the public-key fingerprint permitted to sign the
private manifest. The manifest is canonical JSON with a detached Ed25519
signature. It is admitted only when its schema, signer fingerprint, signature,
static-record digest, artifact bindings, DB-0 policy, protected-root bindings,
and semantic fixture-manifest digest all verify. An unsigned, self-signed,
foreign-signer, or differently anchored manifest is rejected before any path
is opened. The immutable-plan digest is computed from the verified manifest
and the observer's fixed validation policy; raw caller configuration cannot
replace either input.

Hash equality proves byte consistency with that admission manifest; it does
not independently admit provenance. The preflight may not open a declared
artifact or fixture path until it has established permitted-root containment,
component type, and no-symlink policy. A future runner consumes one immutable
plan with canonical roots, trusted bindings, launcher grammar, effective
limits, and capture grammar rather than mutable raw configuration.

## Root and process containment

The synthetic root, temporary root, and evidence root must be canonical,
owner-controlled, non-symlink paths that are pairwise disjoint. They must also
be disjoint from user graphs, default Logseq locations, accounts, sync state,
ambient configuration, and the observer working directory. The observer must
reject an inherited graph selection or an undeclared launcher. It validates all
protected-root bindings before opening a declared artifact or fixture file.

The verified manifest, not raw configuration, records the user graph, default
Logseq root, account root, sync root, configuration root, and working directory
as protected bindings. Each binding is either a validated present path or a
proven absent path; the observer never creates a missing protected path.
Categories may resolve to one protected location, but no protected location may
overlap an owned root. A future implementation needs nofollow type/owner/size
checks and immediate pre-launch replacement detection; this static design does
not claim to remove launch-time TOCTOU risk.

Every child must use a shell-free fixed argument vector. The only candidate
read commands are property inventory, `graph info`, selected-page `show`,
root-UUID `show`, and final `server list`, each with explicit `--root-dir`,
explicit graph selection, and `--output json`. Query, debug, SQLite, Parser,
sync, login, import, export, graph switching, fallback, retry, and all write
operations are prohibited.

`server stop` is excluded. Under the current DB-0 profile every lifecycle
change is forbidden. A future lifecycle profile must separately define its
owned paths, allowed transition, cleanup rules, fingerprints, and failure
semantics before a stop operation can be considered.

## Capture and validation

Each invocation must capture at most one bounded JSON value. A valid command
result is exactly one of the statically admitted envelopes:

- `{ "status": "ok", "data": ... }`;
- `{ "status": "error", "error": { "code": string, "message": string, ... } }`.

The observer must reject an error envelope, malformed JSON, trailing values,
unknown result modes, excess output, a nonzero semantic validation result, or
any shape outside the admitted shallow boundary. A zero child exit status alone
is not success. Dynamic entity and property fields remain unproven until a
separate qualified runtime result validates them against the payload contract.

## Inventory, cancellation, and evidence

Before and after every candidate read, the observer must produce distinct
semantic and lifecycle inventories. It must declare zero allowed changes under
the DB-0 profile and stop on any observed graph, metadata, worker, lock, or
lifecycle change.

The runner must own its child process group, impose fixed timeout and capture
limits, record timeout or signal outcomes, preserve bounded private partial
captures, and never retry or perform automatic cleanup. A cancellation,
overflow, unknown owner, stale session, undeclared side effect, incomplete
result, or failed revalidation terminalizes the attempt.

Its durable private attempt manifest must bind source state, artifact hashes,
fixture identifiers and digest, fixed arguments, limits, timestamps, child
exit or signal, inventories, capture hashes, result digest, and terminal stop
reason. Any later public record may contain only sanitized structural facts and
digests.

## Implementation and execution gates

1. Freeze a typed synthetic fixture-manifest schema that binds graph, page, and
   root-block IDs; parentage; sibling order; content; permitted properties;
   source revision; and a semantic digest.
2. Implement deterministic admission-manifest and configuration validation with
   synthetic unit tests. Negative coverage includes forged admission,
   protected-path rejection before reads, absent defaults, cwd overlap,
   symlink/replacement/type attacks, limits, and fixture-identifier mismatch.
   No production path may invoke a subprocess at this stage.
3. Independently review the exact diff, trusted-input contract, effective
   policy fields, limits, and root-disjointness checks.
4. Run repository documentation and hosted CI gates through a short PR.
5. Only after merge, request an authorization that names the exact observer
   commit and immutable-plan digest; admission-manifest identity, signer
   fingerprint, and static-record digest; launcher/interpreter and archived
   entry identities; artifact bindings; semantic fixture-manifest digest;
   protected-root set; fixture and evidence roots; fixed command set;
   timeout/cancellation policy; and one-attempt stop boundary.

This design does not authorize the fifth step.
