---
type: Decision
title: Plumber Logseq gateway authority
description: Cross-repository authority and dependency direction for Logseq graph access.
resource: docs/contracts/README.md
tags: [architecture, contracts, logseq, parser, trama]
status: accepted
classification: active
audience: [maintainer, contributor, operator]
owner: core-runtime
---

# Plumber Logseq gateway authority

## Decision

**Matryca Plumber is the sole Logseq gateway** for Matryca products. It owns
the public `plumber.*` graph and control contract families, the selection of a
supported Logseq host surface, and the application boundary presented to
consumers.

The dependency direction is:

```text
Logseq OG Markdown -> Parser -> Plumber -> Trama or Brain
Logseq DB official host surface -> Plumber -> Trama or Brain
```

Parser is a Plumber-internal OG implementation dependency. Trama and Brain
consume Plumber public contracts only: Trama does not import Parser, and Brain
does not import Parser. Neither consumer obtains a graph directly from Logseq.

Parser's existing **legacy/experimental LENS visualization surface** remains
compatible during its deprecation window. It receives no new product UI or
graph-intelligence ownership: Trama remains the product intelligence and graph
UI owner, while Plumber retains its bounded Operator Console. No LENS source or asset is removed or copied by this decision.

## Scope and ownership

| Surface | Owner | Current boundary |
| --- | --- | --- |
| OG Markdown parsing | Parser, selected by Plumber | Parser owns parsing; legacy/experimental LENS remains compatible only during its deprecation window. |
| OG and Shadow repository reads | Plumber `GraphReadPort` | `GraphReadPort remains filesystem/Shadow-only`; it is not a session or DB port. |
| Logseq DB host access | Plumber | A future adapter may use only a qualified **Logseq DB official host surface**. |
| Consumer graph reads | Plumber `GraphSessionReadPort` | Internal OG identity and complete opaque topology slices exist; page/subtree and external transport remain feature-off. |
| Graph and control contracts | Plumber | `plumber.graph.read/v1`, `plumber.graph.topology/v1`, `plumber.control/v1`, and `plumber.host.navigate/v1`. |
| Product intelligence and graph UI | Trama | Consumer implementation over published Plumber contracts. |
| Optional analysis consumer | Brain | Consumer implementation over published Plumber contracts. |
| Operator Console | Plumber | Bounded control UI for status, configuration, and gardening actions; not Trama's graph-intelligence UI. |

## Prohibited paths

- No Trama or Brain import of Parser source, Parser DTOs, or Parser-owned UI.
- No Trama or Brain adapter that reads Logseq OG Markdown or Logseq DB directly.
- No Plumber public contract named `trama.*`; historical `trama.logseq.read/v1`
  material is not the future production authority.
- No direct mutation of Logseq internal database, including SQLite files,
  internal tables, or an undocumented storage transport.
- No DB-to-Markdown fallback, hidden graph selection, or inferred session.

## Contract and implementation gates

This decision defines ownership, not a shipped runtime capability. The public
contract artifact must be transport-neutral and contain versioned schemas,
synthetic fixtures, and a compatibility test kit before a consumer is wired.
The internal OG identity-only `GraphSessionReadPort` uses only an explicit
Parser source, one byte-bounded UTF-8 snapshot, opaque identity, session
binding, source revision, and Plumber-owned close/monotonic-expiry lifecycle.
The internal complete-topology slice captures one bounded graph-wide OG source
set and calls Parser 1.9 `LogseqGraph.from_snapshot_pages()` once; it projects
only opaque structural values from explicitly resolved wikilinks and block
references. It fails closed for unresolved block references, title collisions,
and values above its declared bounds.
Page and complete ordered subtree reads remain feature-off until the artifact
and the selected source profile qualify bounded payloads, failure semantics,
and consumer compatibility.

For OG, Plumber may call Parser behind its internal boundary. For DB, Plumber
may add an adapter only after an exact official host capability qualifies; no
claim of DB execution, support, or parity follows from this decision. Shadow
remains a disposable derived cache and never becomes a Logseq system of
record.

## Consequences

The earlier DB-read programme that named Trama as host adapter and DTO authority
is superseded as execution authority, while its historical evidence remains
available for audit. Future work first publishes the Plumber-owned contract;
only then can Parser deprecate its visualization surface or Trama and Brain
implement consumers. License, provenance, and contributor-review constraints
remain independent gates for every transfer or reuse of source, assets, and
fixtures.
