---
type: Specification
title: Plumber consumer package v1 static profile artifact
description: Immutable static contract-intention packages for Matryca Trama and Matryca Brain.
tags: [architecture, contracts, interoperability, profiles]
classification: canonical
audience: [maintainer, contributor, operator]
owner: core-runtime
---

# `plumber.consumer.package/v1` static profile artifact

## Status

`plumber.consumer.package/v1` is a **proposed, static-only, unqualified**
package catalogue for Matryca Trama and Matryca Brain. It binds each product's
declared contract intention to exact checked-in bytes of the canonical
`plumber.graph.read/v1` and `plumber.graph.topology/v1` schemas and consumer
profiles.

It creates no runtime consumer support, producer support, capability
negotiation, endpoint, CLI command, MCP tool, UI, Parser import, Logseq source
access, Logseq DB support, Shadow use, graph scan, mutation, event, or release
claim.

The repository-owned, transport-neutral artifact is:

- [schema](../../contracts/plumber.consumer.package/v1/schema.json)
- [package catalogue](../../contracts/plumber.consumer.package/v1/manifest.json)
- [Matryca Brain profile](../../contracts/plumber.consumer.package/v1/fixtures/matryca-brain-profile-v1.json)
- [Matryca Trama profile](../../contracts/plumber.consumer.package/v1/fixtures/matryca-trama-profile-v1.json)
- [deterministic TCK runner](../../scripts/run_plumber_consumer_package_v1_tck.py)

## Immutable package shape

Each package declares exactly two bindings:

1. `plumber.graph.read/v1` with only the intended `graph.identify` capability.
2. `plumber.graph.topology/v1` with only the intended
   `graph.topology.snapshot.complete` capability and exact `1024` node / `4096`
   edge bounds.

Every binding pins the SHA-256 of the referenced schema and canonical synthetic
consumer-profile bytes. A profile is invalid if its binding drifts, its topology
entry omits the read identity binding, its bounds drift, or it includes a
runtime field. `qualification_status` is fixed to `static-only-unqualified`;
the artifact cannot express a qualified, operational, or transport capability.

The capability names are intent declarations for future admission only. They do
not advertise current Trama or Brain support and do not make either static
contract usable.

## Clean Architecture boundary

Trama and Brain consume only future qualified Plumber-owned contracts. They do
not import Parser or access Logseq directly. For Logseq OG, Plumber may select
Parser only behind its internal adapter boundary. `GraphReadPort` remains a
separate filesystem/Shadow repository port and is not a package or public
session contract.

This artifact does not change the current identity-only OG slice. In particular,
it cannot serve graph-wide topology, page payloads, subtree payloads, or a
runtime consumer. Logseq DB remains a separately qualified official-host path;
there is no DB fallback claim.

## Deterministic fixture admission

Run static admission with:

```bash
uv run python scripts/run_plumber_consumer_package_v1_tck.py
```

The runner validates package schema, exact referenced byte hashes, product and
package identity uniqueness, read/topology dependency, intended capability
allowlists, exact topology bounds, and content-free static shape. Its receipt is
a `deterministic-fixture-attestation`, not an operational provenance receipt,
consumer compatibility qualification, source execution, or host capability
claim.

The runner does not import Parser, open a graph or Shadow cache, call Logseq,
select a DB or Markdown source, invoke transport, mutate data, or emit events.

## Runtime admission hold

Runtime topology remains blocked until a separately reviewed implementation
qualifies one coherent bounded graph-wide snapshot and source revision,
operational producer behavior, and independent Trama or Brain consumer
compatibility. Parser publication, a Plumber dependency update, and any release
promotion remain separate actions and are not implied by this package.
