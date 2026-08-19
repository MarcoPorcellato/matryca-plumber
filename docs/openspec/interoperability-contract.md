---
type: Specification
title: Matryca interoperability contract
description: A vendor-neutral, read-first contract for exchanging Logseq-compatible Markdown, blocks, properties, namespaces, and derived results.
status: draft
classification: canonical
audience: [maintainer, contributor, operator, agent]
owner: integrations
authority: proposal
last_verified: 2026-08-19
---

# Matryca interoperability contract

**Status:** normative proposal for review. It defines compatibility expectations; it is not evidence that an external provider, including Tine, currently qualifies.

## 1. Authority and format

Markdown files are the authoritative graph representation. Blocks, properties, namespaces, indentation, ordering, links, task markers, and `id::` semantics must be preserved when a consumer reads, derives from, or round-trips graph content. A parser may expose a typed view, but it must not silently discard unknown properties or rewrite source bytes merely to populate a derived view.

Derived indexes, caches, projections, search results, and imported knowledge are disposable consumer state. They are never a competing source of truth and must remain separately identifiable from source Markdown.

## 2. Capability levels

Providers and consumers declare the strongest level they have qualified:

| Level | Meaning | Required boundary |
| --- | --- | --- |
| `read` | Read source content and return bounded representations or references. | No source mutation, cache bootstrap, migration, or recovery is authorized. |
| `safe-derived-cache` | Read source content and maintain a disposable derived cache outside the authoritative graph. | Cache writes must be isolated, replaceable, provenance-bound, and unable to alter source Markdown. |
| `closed-writer` | Mutate source Markdown only while other known writers are closed and the provider's conflict/atomic-write checks pass. | The writer owns the complete mutation receipt and must reject stale or ambiguous source state. |
| `concurrent-writer-not-supported` | Explicit declaration that concurrent mutation is unsupported. | Consumers must not infer safety from atomic replacement, separate locks, or successful local tests. |

Capabilities are not implied by transport, API availability, or a successful single-process example. A provider may advertise multiple levels only when each level has separate evidence.

## 3. Authority and write boundaries

Every operation declares its source authority, target authority, capability level, and whether it can write. A read or derived-cache consumer must fail closed if the source identity, revision, schema, or capability is missing or unsupported. It must not write a graph, create a cache, migrate a schema, or repair a failed provider as a side effect of reading.

`closed-writer` permits writes only after an explicit closed-writer precondition has been established for the relevant graph and pages. The writer must perform last-moment conflict detection and atomic persistence according to its own reviewed protocol. A consumer must treat independent writer protocols as non-coordinated: concurrent Tine and Matryca mutation is unsupported pending deterministic two-process evidence covering disjoint and same-page races.

## 4. Provenance and result receipts

An operational interoperability receipt is the full evidence record for an executed
read, derive, or write operation. It must identify, at minimum:

- `schema_version` and the contract/profile version;
- normalized provider and consumer identifiers and versions;
- source authority and repository-relative or opaque graph identity, never a filesystem path or secret;
- exact source revision/generation when available, plus verification time;
- capability level and operation (`read`, `derive`, or `write`);
- bounded result metadata, counts, and outcome (`pass`, `partial`, `unsupported`, `rejected`, or `error`); and
- stable reasons for every non-pass outcome.

Receipts must be deterministic for identical source bytes, inputs, policy versions, and provider outputs. They must not expose credentials, absolute paths, private configuration, raw SQL, or unbounded graph content. A receipt is evidence of the stated operation only; it is not proof of a stronger capability.

The repository's `scripts/run_interop_tck.py` emits a different, deliberately limited
receipt kind: `deterministic-fixture-attestation`, with scope
`manifest-and-fixture-bytes`. This receipt binds the manifest bytes, fixture bytes,
declared outcomes, source authority, and its explicit non-goals. It does not assert
provider or consumer versions, source revision or generation, a verification time,
or that any read, derive, or write operation was executed. `declared_expected_result`
is preserved as a manifest declaration and is not independently evaluated by this
runner. A deterministic fixture-attestation receipt is limited evidence; it does not
substitute for an operational provenance receipt or for interoperability conformance
qualification.

## 5. Unsupported and negative cases

Implementations must report unsupported, malformed, future-version, unhealthy, foreign-binding, stale, conflict, and unavailable cases explicitly. They must not coerce an unknown profile into a supported one, treat a foreign graph as the requested graph, or convert an unsupported write into a successful read. Negative results include the rejected capability, stable reason, source identity (when safe), and the next required qualification evidence.

The current Tine qualification is not completed. In particular, concurrent mutation remains `concurrent-writer-not-supported`; deterministic two-process evidence is required before any concurrent-writer claim.

## 6. Consumer responsibilities

Consumers must validate closed schemas and required fields, preserve source semantics, enforce graph binding, bound result size and execution time, keep derived state isolated, and retain receipts with the exact source anchor. Consumers must distinguish verified evidence, proposals, historical evidence, partial results, and external gates. They must surface a no-serve/no-write decision rather than silently falling back to an unsafe interpretation.

## 7. Exact non-goals

This contract does not:

- replace Markdown with SQLite, a cloud service, or another system of record;
- define or claim a Tine plugin, Tine API, native MCP, or upstream change;
- authorize concurrent Tine and Matryca writes;
- certify Tine, Logseq, AAIF, OKF, or any other external implementation;
- define an authentication, transport, UI, marketplace, or deployment protocol;
- guarantee semantic equivalence for provider-private fields that are not represented in the declared schema; or
- turn local fixture parsing, green CI, or a single-process smoke test into interoperability qualification.

Qualification remains a separate, exact-head, reproducible evidence activity.
