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
It is a documentation authority only. It introduces no wire schema, endpoint,
runtime adapter, compatibility claim, or Logseq DB support.

| Contract family | Intended responsibility | Status |
| --- | --- | --- |
| `plumber.graph.read/v1` | Session-bound page and complete ordered subtree reads. | Reserved; feature-off. |
| `plumber.graph.topology/v1` | Derived graph topology for consumers. | Reserved; feature-off. |
| `plumber.control/v1` | Bounded operator configuration and gardening commands. | Reserved; feature-off. |
| `plumber.host.navigate/v1` | Explicit host navigation request, never implicit UI control. | Reserved; feature-off. |
| `plumber.graph.mutate/v1` | Future host-authoritative mutation only. | Deferred. |

The future contract source of truth is a Plumber-owned, transport-neutral
artifact containing schemas, synthetic content-free fixtures, provenance and
capability metadata, and a compatibility test kit. A contract becomes usable
only after its exact artifact, producer profile, and consumer profile pass the
recorded admission gate.

Consumers include Matryca Trama and Matryca Brain. They do not import Parser or
access Logseq directly. Parser remains an internal implementation selected by
Plumber for Logseq OG Markdown. `GraphReadPort` remains a separate
filesystem/Shadow repository port and is not the public session contract.

Historical `trama.logseq.read/v1` documents remain audit material only. They
must not be copied, renamed, or presented as the production authority for a
new Plumber contract.
