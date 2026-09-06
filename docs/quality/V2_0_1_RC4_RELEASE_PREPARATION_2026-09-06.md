---
type: release-preparation
title: v2.0.1-rc.4 release preparation
description: Proposed RC4 package and qualification boundary for internal OG topology and installed static public contract resources; no tag, publication, or qualification result is selected.
resource: docs/quality/V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md
tags: [release, provenance, contracts, topology, v2]
last_verified: 2026-09-06
stale_after: 2027-03-06
status: proposed
classification: active
audience: [maintainer, contributor, operator]
owner: release
authority: release-preparation
related:
  - V2_0_1_RC3_RELEASE_QUALIFICATION_PLAN_2026-08-31.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - EVIDENCE_INDEX.md
  - ../contracts/plumber-graph-topology-v1.md
---

# v2.0.1-rc.4 release preparation

## Authority and source boundary

This preparation is tracked by [#579](https://github.com/MarcoPorcellato/matryca-plumber/issues/579).
It begins from `origin/main` commit
`62e1abb6c6177c3063e0dd87c43510190fd9d24a`; that base and this preparation
commit are not a selected RC4 candidate. Creating the annotated `v2.0.1-rc.4` tag,
publishing GitHub Release or PyPI artifacts, and treating any qualification gate as
passed each require separate authority.

RC3 is historical and published. Its tag resolves to
`0506d975fe697646e5165db1505ee93a67041801`; its artifacts are recorded in
[`v2.0.1-rc.3-GITHUB.md`](../releases/v2.0.1-rc.3-GITHUB.md). RC3 evidence does not
transfer to RC4 or stable `v2.0.1`.

## Candidate scope

RC4 prepares one bounded runtime addition and one distribution addition:

- The OG topology projection stays Plumber-owned and internal. It uses the Parser
  1.9 public snapshot factory behind Plumber's session-bound contracts. It has no
  public Python adapter, `Path`-accepting consumer API, transport, CLI/MCP command,
  Trama or Brain import, UI, or LENS surface.
- The canonical content-free static resources for
  `plumber.consumer.package/v1`, `plumber.graph.read/v1`, and
  `plumber.graph.topology/v1`, plus their three deterministic TCK scripts, are
  present in both the wheel and source distribution. Packaging those bytes does not
  make a consumer package runtime-qualified or introduce consumer wiring.

The Logseq DB capability-discovery profile remains `test_only/unbound`. It declares
no supported artifact, runtime probe, DB adapter, direct internal access, Markdown
fallback, transport, Shadow route, mutation, event, sync, or import/export support.

## Required release evidence

Before any separate publication decision, maintainers must bind the exact candidate
commit and clean source state to terminal hosted CI, the wheel and sdist metadata,
and installed-resource byte checks for every static contract and TCK. The candidate
must retain the fail-closed Parser snapshot, topology completeness, and session
binding tests. A passing source check does not prove a published artifact, a DB
capability, or stable promotion.

## Stop conditions

Stop this preparation if an archive omits, changes, or adds compiled cache bytes to a
static contract resource; if the installed TCK cannot locate its colocated contract
root; if a new public adapter or transport is proposed; or if Logseq DB test policy
is represented as runtime support. Do not publish, tag, push, merge, or start a
qualification soak under this document.
