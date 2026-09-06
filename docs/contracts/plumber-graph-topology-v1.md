---
type: Specification
title: Plumber graph topology v1 static contract artifact
description: Canonical static schema, synthetic fixtures, and deterministic admission boundary for plumber.graph.topology/v1.
tags: [architecture, contracts, interoperability, topology]
classification: canonical
audience: [maintainer, contributor, operator]
owner: core-runtime
---

# `plumber.graph.topology/v1` static contract artifact

## Status

`plumber.graph.topology/v1` is a **proposed public contract** for complete,
content-free structural graph topology. Its checked-in artifact remains static
interoperability input only: it creates no endpoint, CLI command, MCP tool,
Logseq DB support, Shadow use, consumer wiring, or public transport.

The internal OG implementation slice separately selects Parser 1.9 behind
Plumber's adapter boundary. Plumber captures at most 1,024 regular Markdown
sources / 16 MiB, hashes those exact bytes into one source revision, then calls
`LogseqGraph.from_snapshot_pages()` once. It projects that in-memory graph to
opaque nodes and reference edges, and rejects node or edge counts above the
v1 1,024 / 4,096 limits. Parser strict-reference and strict-title-collision
validation reject incomplete or ambiguous source graphs before projection. The
projection accepts only explicitly resolved Parser wikilinks and block
references. Parser's page-level `refs` is an aggregate of block convenience
references plus property-derived wikilinks, tags, and block references; v1
excludes it entirely because that aggregate loses the source semantics required
for a structural edge. It likewise does not infer topology from Parser `tags`
or node convenience `refs` fields. It never reopens source pages through
Parser. This is not a consumer
qualification, external endpoint, or Logseq DB capability.

The canonical artifact is repository-owned and transport-neutral:

- [schema](../../contracts/plumber.graph.topology/v1/schema.json)
- [fixture catalogue](../../contracts/plumber.graph.topology/v1/manifest.json)
- [synthetic producer profile](../../contracts/plumber.graph.topology/v1/fixtures/producer-profile-v1.json)
- [synthetic consumer profile](../../contracts/plumber.graph.topology/v1/fixtures/consumer-profile-v1.json)
- [deterministic TCK runner](../../scripts/run_plumber_graph_topology_v1_tck.py)

## Session and provenance binding

Each fixture binds to an opaque, active `plumber.graph.read/v1` session,
graph identifier, and source revision. A passing topology provenance repeats
the exact read-contract identifier, schema version, and source revision. A
foreign graph, terminal session, or revision mismatch fails closed.

This does not make `plumber.graph.read/v1` page or subtree delivery usable.
`GraphReadPort` remains the filesystem/Shadow repository port; it is not a
public session or topology port. The internal OG topology slice retains the
same Plumber-owned close and expiry lifecycle as identity reads and returns no
page or subtree payload.

## Contract shape

The only capability and operation are `graph.topology.snapshot.complete`.
Producer and consumer profiles declare identical bounded maximum node and edge
counts; v1 performs no implicit limit negotiation. The canonical synthetic
profiles declare 1,024 nodes and 4,096 edges.

A passing result contains only:

- opaque topology and node identifiers;
- node kind (`page` or `block`), parent identifier, and sibling ordinal;
- non-containment `reference` edges between declared nodes; and
- structural provenance bound to the source revision.

Containment uses node `parent_id` and `ordinal`; it is not duplicated as an
edge. Nodes use parent-before-child canonical preorder. Every root and sibling
ordinal is contiguous from zero. Reference edges use canonical lexical
`(kind, source_id, target_id)` order.

Success is complete-only. There is no cursor, pagination, continuation, or
partial successful topology result. A source that cannot produce a complete
result within declared bounds is rejected with an empty result.

## Privacy and identifier boundary

Topology fixtures and receipts never contain Markdown, text, titles, paths,
properties, URLs, hosts, Parser models, native Logseq IDs, or source locations.
Identifiers are opaque contract tokens. Their syntax and static fixture value
do not claim cryptographic derivation, native-ID reuse, cross-graph
linkability, or stability across a different source revision.

Trama and Brain may consume a future qualified Plumber topology contract only.
They do not import Parser or access Logseq directly. For OG, Plumber's internal
adapter now selects Parser 1.9 and projects Parser-owned structures into
Plumber-owned values from one coherent bounded source revision. The static
artifact and internal slice still do not qualify Trama, Brain, DB support, or
an external consumer transport.

## Canonical fixture catalogue

| Fixture | Expected outcome | Boundary exercised |
| --- | --- | --- |
| `topology-complete-pass-v1` | `pass` | Complete canonical parentage and reference topology. |
| `foreign-graph-rejected-v1` | `rejected` | Session cannot serve a foreign graph. |
| `closed-session-rejected-v1` | `rejected` | Terminal read session cannot serve topology. |
| `incomplete-topology-rejected-v1` | `rejected` | Incomplete topology is never a successful payload. |
| `unsupported-capability-v1` | `unsupported` | Unadvertised capability is explicit. |

All fixture data is synthetic and content-free. It does not reproduce Parser,
Logseq, Trama, Brain, user-vault, or external contributor material.

## Deterministic fixture admission

Run local static admission with:

```bash
uv run python scripts/run_plumber_graph_topology_v1_tck.py
```

The runner validates canonical schema/profile bindings, complete-only session
semantics, opaque result shapes, parentage, ordinal and edge ordering, bounds,
content-free fields, and deterministic fixture hashes. Its receipt is a
`deterministic-fixture-attestation`; it is not an operational provenance
receipt, consumer compatibility qualification, source execution, or host
capability claim.

The runner does not open a graph or Shadow cache, import Parser, call Logseq,
select a DB or Markdown source, invoke MCP or CLI transport, mutate data, or
emit events.
