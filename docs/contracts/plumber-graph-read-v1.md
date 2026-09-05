---
type: Specification
title: Plumber graph read v1 static contract artifact
description: Canonical static schema, synthetic fixtures, and deterministic admission boundary for plumber.graph.read/v1.
tags: [architecture, contracts, interoperability, logseq]
classification: canonical
audience: [maintainer, contributor, operator]
owner: core-runtime
---

# `plumber.graph.read/v1` static contract artifact

## Status

`plumber.graph.read/v1` remains a **proposed, feature-off** public contract for
page and complete-subtree delivery. This artifact defines static
interoperability inputs only. It creates no endpoint, CLI command, MCP tool,
or Logseq DB support.

Issue #566 adds one internal, in-process OG `graph.identify` vertical slice:
an explicit source is parsed through Plumber's private Parser adapter and then
served through a Plumber-owned session port. It returns opaque graph and source
revision bindings only. It serves no page or subtree payload and creates no
external consumer compatibility claim.

Issue #568 hardens that internal slice. Its private adapter validates and reads
one explicit source snapshot with a 1,048,576-byte (1 MiB) ceiling before
Parser invocation, binds pre/post `lstat` and descriptor `fstat` device, inode,
and size identities, and rejects symlink, non-regular, or replacement races.
It hashes the exact admitted bytes, decodes UTF-8 explicitly, and calls
Parser's in-memory `parse()` on that same snapshot. Read, decode, size, and
Parser failures are bounded Plumber errors with no path or graph-content
disclosure. The
Plumber-owned reader also supports idempotent close and an optional injected
monotonic deadline; closed and expired sessions reject every operation.

The canonical artifact is repository-owned and transport-neutral:

- [schema](../../contracts/plumber.graph.read/v1/schema.json)
- [fixture catalogue](../../contracts/plumber.graph.read/v1/manifest.json)
- [synthetic producer profile](../../contracts/plumber.graph.read/v1/fixtures/producer-profile-v1.json)
- [synthetic consumer profile](../../contracts/plumber.graph.read/v1/fixtures/consumer-profile-v1.json)
- [deterministic TCK runner](../../scripts/run_plumber_graph_read_v1_tck.py)

## Contract shape

The schema fixes the contract identifier to `plumber.graph.read/v1` and the
schema version to `1`. A fixture binds one producer profile, one consumer
profile, an opaque graph identifier, opaque source revision, and explicit
session state.

The only declared operation names are:

- `graph.identify`
- `page.read`
- `block.subtree.read.complete`

Passing reads require an active session and matching producer/consumer
capabilities. A passing complete-subtree response requires a root identifier,
`complete: true`, and a contiguous per-parent ordinal sequence. Result shapes
contain opaque identifiers and structural metadata only. They never carry
Markdown, text, titles, paths, host objects, credentials, or graph content.

## Canonical fixture catalogue

| Fixture | Expected outcome | Boundary exercised |
| --- | --- | --- |
| `identify-pass-v1` | `pass` | Bound graph identity. |
| `page-read-pass-v1` | `pass` | Opaque page result on an active session. |
| `ordered-subtree-pass-v1` | `pass` | Complete, ordered subtree structure. |
| `foreign-graph-rejected-v1` | `rejected` | Foreign graph binding is not served. |
| `incomplete-subtree-rejected-v1` | `rejected` | Incomplete subtree is not represented as complete. |
| `unsupported-capability-v1` | `unsupported` | Unadvertised capability is explicit. |

All fixture data is synthetic and content-free. It does not reproduce Parser,
Logseq, Trama, Brain, user-vault, or external contributor material.

## Deterministic fixture admission

Run the local static admission check with:

```bash
uv run python scripts/run_plumber_graph_read_v1_tck.py
```

The runner validates schema presence and shape, profile bindings, fixture
outcomes, opaque result constraints, subtree ordering, and deterministic hashes.
Its receipt is a `deterministic-fixture-attestation`; it is not an operational
provenance receipt, consumer compatibility qualification, or host capability
claim.

The runner does not open a graph or Shadow cache, import Parser, call Logseq,
select a DB or Markdown source, invoke MCP or CLI transport, mutate data, or
emit events.

## Admission boundary

The artifact remains the prerequisite for page and subtree implementations of
Plumber-owned `GraphSessionReadPort`. Issue #566 uses only its identity
vocabulary in an internal OG service; its runtime DTO is not a serialized
fixture-schema envelope. Existing `GraphReadPort` remains the
filesystem/Shadow repository port. A future producer and consumer must
separately qualify the exact source profile, graph binding, session lifecycle,
bounded reads, source revision, failure behavior, and consumer compatibility
before any page/subtree runtime wiring is introduced.

For Logseq OG, Plumber may select Parser behind its internal boundary. Parser
types never become public contract types. For Logseq DB, only a separately
qualified official host surface may be considered; this artifact does not
qualify DB execution, parity, fallback, or mutation.
