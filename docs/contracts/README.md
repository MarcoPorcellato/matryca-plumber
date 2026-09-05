---
type: Specification
title: Plumber public contract catalogue
description: Ownership and admission rules for versioned Matryca Plumber contracts.
tags: [architecture, contracts, interoperability]
classification: active
audience: [maintainer, contributor]
owner: core-runtime
---

# Plumber public contract catalogue

This catalogue reserves the public contract namespace owned by Matryca Plumber.
It introduces no endpoint, compatibility claim, or Logseq DB support.
`plumber.graph.read/v1` additionally has a static, transport-neutral schema
and synthetic fixture artifact. Its page and subtree capabilities remain
feature-off; an internal OG identity-only session slice is not a transport or
consumer-compatibility surface.

| Contract family | Intended responsibility | Status |
| --- | --- | --- |
| [`plumber.graph.read/v1`](plumber-graph-read-v1.md) | Session-bound identity, page, and complete ordered subtree reads. | Static artifact; identity-only internal OG slice. |
| `plumber.graph.topology/v1` | Derived graph topology for consumers. | Reserved; feature-off. |
| `plumber.control/v1` | Bounded operator configuration and gardening commands. | Reserved; feature-off. |
| `plumber.host.navigate/v1` | Explicit host navigation request, never implicit UI control. | Reserved; feature-off. |
| `plumber.graph.mutate/v1` | Future host-authoritative mutation only. | Deferred. |

`plumber.graph.read/v1` source of truth is its Plumber-owned,
transport-neutral artifact containing a schema, synthetic content-free fixtures,
producer and consumer profiles, and a deterministic compatibility test kit. Its
fixture attestation does not make the contract usable. The internal OG identity
slice reuses only contract vocabulary and does not qualify consumer transport.
A runtime contract becomes usable only after its exact artifact, producer
profile, and consumer profile pass the recorded admission gate.

Consumers include Matryca Trama and Matryca Brain. They do not import Parser or
access Logseq directly. Parser remains an internal implementation selected by
Plumber for Logseq OG Markdown. `GraphReadPort` remains a separate
filesystem/Shadow repository port and is not the public session contract.

Historical `trama.logseq.read/v1` documents remain audit material only. They
must not be copied, renamed, or presented as the production authority for a
new Plumber contract.
