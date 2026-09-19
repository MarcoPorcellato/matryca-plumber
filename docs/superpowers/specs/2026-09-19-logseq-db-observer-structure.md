---
type: Specification
title: Logseq DB observer structural-contract v1
description: Pure in-memory structural validation for a future DB-0 observer; no authentication, filesystem, process, or host operation.
resource: docs/superpowers/specs/2026-09-19-logseq-db-observer-structure.md
tags: [logseq, database, qualification, safety, fixtures]
status: proposed
classification: active
audience: [maintainer, contributor]
owner: integration
related:
  - ../../quality/LOGSEQ_DB_CLI_RECOVERY_OBSERVER_SAFETY_DESIGN_2026-09-16.md
  - ../../quality/LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../../decisions/2026-09-12-plumber-graph-payload-read-v1.md
---

# Logseq DB observer structural-contract v1

## Purpose

This slice validates bounded **in-memory bytes** into immutable structural
candidates for a synthetic fixture and a future observer envelope. It does not
authenticate an admission manifest, establish a trust anchor, inspect a path,
create a process, provision or read a graph, or grant runtime permission.

`validated structure` means only that bytes satisfy this internal schema. It
does not mean authenticated, fixture-ready, DB-0 compliant, launch-ready, or
host-supported.

## Canonical digest domain

`plumber.logseq-db-observer-structure/v1` uses a private deterministic JSON
encoding: UTF-8, `ensure_ascii=true`, lexically sorted object keys, compact
`,` and `:` separators, and JSON values limited to objects, arrays, strings,
integers, booleans, and null. Floats, duplicate keys, non-finite constants,
malformed UTF-8, trailing values, and data outside the declared schema are
rejected. This encoding is **not RFC 8785** and must never be described as the
payload contract's canonical JSON.

The fixture semantic digest is lowercase SHA-256 over the canonical encoding
of the complete fixture object after omitting only `semantic_sha256`. Every
fixture semantic field is in that domain: IDs, declared source revision, page
metadata, nodes, order, text, and property declarations.

## Fixture structure

The fixture schema is `plumber.logseq-db.fixture-structure/v1`. It contains:

- opaque graph, page, and root-block IDs;
- a declared synthetic source revision, which is not evidence of a host
  revision or session;
- one exact page title;
- depth-first-preorder block nodes with opaque IDs, parent IDs, contiguous
  sibling ordinals, and exact UTF-8 text;
- public property declarations only: key, payload-v1 wire type, cardinality,
  and scope. No host property values are represented;
- the semantic digest.

The structural ceilings reuse only the payload ADR's ID, text, node, depth,
property-key, and property-count ceilings. They do not define operation-result
or raw-capture limits and do not create a second payload contract.

## Observer-envelope structure

The envelope schema is `plumber.logseq-db.observer-structure/v1`. It binds
structural claims for the static-record digest, signer fingerprint, artifact
and archived-entry containment facts, distinct launcher identity and argument
prefix, DB-0 policy ID, protected-root declarations, fixture digest and IDs,
observer/config identities, and effective fixture limits.

Protected roots are opaque `present` or `absent` declarations. This slice does
not resolve, stat, open, create, normalize, or claim ownership of them.
Likewise, a fingerprint, signature-looking string, or matching caller hash is
only data: no returned object is authenticated or executable.

## Acceptance and exclusions

The parser rejects malformed or oversized inputs; duplicate/unknown/coerced
fields; bad digests; invalid fixture topology; and envelope/fixture mismatch.
It must preserve block and page text exactly. Its module dependency closure may
not import `os`, `pathlib`, `subprocess`, `socket`, HTTP clients, or Logseq
adapters.

Detached Ed25519 verification with a reviewed-source trust anchor, safe
filesystem verification, immutable launch planning, and every runtime action
are later, separate slices.
