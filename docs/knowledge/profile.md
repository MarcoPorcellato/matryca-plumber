---
type: Specification
title: Matryca Plumber knowledge profile
description: Producer rules for the maintained knowledge bundle, legacy inventory, provenance, lifecycle, and deterministic documentation gates.
resource: docs/knowledge/
tags: [okf, documentation, governance, provenance]
generated: { by: human:marco-porcellato, at: '2026-07-18T00:00:00Z' }
verified: { by: human:marco-porcellato, at: '2026-08-08T00:00:00Z' }
last_verified: 2026-08-08
stale_after: 2027-02-04
status: stable
classification: canonical
canonical_for: documentation.profile
audience: [maintainer, contributor, agent]
owner: core-runtime
supersedes: []
related:
  - /documentation-evolution.md
  - /inventory.md
profile_version: "1.0"
okf_spec_version: "0.2"
official_conformance: not-assessed
matryca_quality_target: MKQ-4
okf_reference: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/3fcbb9f828c2f23d109c855ee403c3a4c81f3a96/okf/SPEC.md
---

# Matryca Plumber knowledge profile

Matryca Plumber uses [Open Knowledge Format v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/3fcbb9f828c2f23d109c855ee403c3a4c81f3a96/okf/SPEC.md) as its portable Markdown contract and applies a stricter Matryca quality profile to maintained repository knowledge. These are separate results: OKF compatibility does not imply Matryca quality, and Matryca quality is not an official Google conformance level.

The repository remains authoritative. Matryca Knowledge may inventory, validate, and project committed documentation, but its reviewed projection is not an editing origin and never becomes a competing source of truth.

## Scope

| Surface | Contract |
| --- | --- |
| `docs/knowledge/` concepts | Maintained OKF v0.2-compatible concepts with Matryca metadata and blocking local validation |
| `docs/knowledge/index.md` | Reserved root index for progressive disclosure; only `okf_version` frontmatter is allowed |
| Nested `index.md` files | Reserved indexes with no frontmatter |
| `docs/knowledge/log.md` | Reserved newest-first update chronology with ISO date headings |
| Legacy `docs/**/*.md` and root documentation | Classified in `inventory.json`; not mass-rewritten merely to add frontmatter |
| Matryca Knowledge projection | Read-only, Git-provenanced consumer view generated from committed source bytes |

## Official OKF v0.2 layer

Every non-reserved concept document has YAML frontmatter and a non-empty `type`. Unknown type names and extension fields remain consumable. The bundle uses ordinary Markdown links as graph edges, stable repository paths as concept identity, and the reserved `index.md` and `log.md` structures defined by OKF.

The official lifecycle fields are:

- `status`: `draft`, `stable`, or `deprecated`; absence means `stable` to a generic OKF consumer, although the Matryca producer profile requires it explicitly.
- `generated`: an optional `{ by, at }` production event.
- `verified`: one verification event or a list of events, each with `by` and `at`.
- `stale_after`: an absolute `YYYY-MM-DD` date.

`type` is the only universally required OKF concept field. The additional requirements below are Matryca producer rules, not official OKF requirements.

## Matryca quality layer

Maintained concepts require:

| Field | Requirement |
| --- | --- |
| `type` | One descriptive repository type; unknown types remain readable |
| `title` | Human-readable display title |
| `description` | One-sentence discovery summary |
| `status` | Explicit official OKF lifecycle value |
| `classification` | `canonical`, `active`, `historical`, or `generated` |
| `verified` | At least one actor and ISO 8601 verification timestamp |
| `last_verified` | Transitional ISO date for the current Matryca Knowledge validator |
| `stale_after` | Absolute review deadline; currently 180 days after verification |
| `canonical_for` | Required and globally unique when `classification: canonical` |
| `audience` | Any of `maintainer`, `contributor`, `operator`, or `agent` when present |
| `owner` | Maintainer area responsible for the concept |

## Validator reporting contract

`make docs-check` reports two independent top-level results: **OKF v0.2 format
compatibility** and **Matryca quality profile v1.0**. Passing the format gate is
not an official certification and does not imply that the stricter repository
profile passes. Unknown concept types and extension fields remain consumable;
the Matryca layer owns repository-specific links, anchors, freshness, canonical
roles, safe local paths, inventory drift, and generated-view integrity.

The specification, profile, validator, and finding-schema versions advance
independently. Text findings are sorted before emission. `make docs-check` keeps
the existing human-readable contract; automation may run
`python scripts/docs_knowledge_check.py check-bundle --format json` to receive
one JSON document and one final pass/fail exit status.

The machine report has a stable `kind`, finding-schema version, independently
versioned policy tuple, source provenance, per-layer and overall summaries, and
sorted findings. Each finding contains a policy-bound SHA-256 fingerprint,
layer, stable code, repository-relative path, structural pointer, bounded
parameters, and sanitized message. Fingerprints exclude human wording, source
commit, and timestamps; they change when identity fields or any policy version
changes. Repository provenance records only a normalized repository identifier,
the exact commit when available, the fixed bundle path, and a
`clean`/`dirty`/`unavailable` state. It never emits credentials, absolute local
paths, raw link targets, or raw legacy-source values.

Identical findings, policy versions, and source provenance produce
byte-identical JSON. Changed-byte and changed-policy invalidation, retained or
signed report artifacts, and Matryca Knowledge projection ingestion remain
separately reviewable follow-up work under
[#402](https://github.com/MarcoPorcellato/matryca-plumber/issues/402). A passing
report remains deterministic compatibility evidence, not official OKF
certification.

`last_verified` is intentionally dual-written during the transition to native OKF v0.2 trust parsing in Matryca Knowledge. It may be removed only after the registry validates `verified[].at` directly for freshness.

## Classification and lifecycle are different

`status` answers whether the content is ready for consumption. `classification` answers how Matryca governs it:

| Classification | Meaning |
| --- | --- |
| `canonical` | Authoritative owner of one declared semantic role |
| `active` | Maintained supporting or forward-looking knowledge |
| `historical` | Preserved evidence that is not maintained as current guidance |
| `generated` | Deterministic derived view; edit its source instead |

A historical audit can still be a stable, faithfully preserved record. A draft roadmap can be active. This is why Matryca lifecycle values must not be stored in the official OKF `status` field.

## Document types

Matryca Plumber currently recognizes Product Overview, Guide, Architecture, Specification, Reference, Runbook, Decision, Roadmap, Audit, Release Note, and Archive for consistent presentation. This is a producer taxonomy, not a closed OKF registry; consumers must tolerate new types.

## Links and authority

- Bundle-absolute links begin with `/` and resolve from `docs/knowledge/`.
- Relative Markdown links resolve from the containing document.
- Local maintained links and anchors must resolve, even though generic OKF consumers are required to tolerate broken links.
- `legacy_sources` contains repository-relative authority pointers outside the bundle and must resolve inside this repository.
- `related` is reserved for maintained bundle relationships.
- A canonical role declared through `canonical_for` has exactly one owner.

## Inventory profile

`inventory.json` is the curated full-repository documentation ledger. Schema version 2 uses `classification`, not the overloaded legacy `status` field. Each entry records discovery metadata, ownership, migration action, destination, canonical role, and missing-path state. Historical reports remain in place unless a separately reviewed migration changes their authority or location.

The generated [`inventory.md`](inventory.md) view is never edited by hand. See [Documentation evolution and operating model](documentation-evolution.md) for the complete maintenance workflow.

## Maturity target

This source targets **MKQ-4**: deterministic enforcement in source CI, on top of maintained metadata, navigation, link, anchor, lifecycle, and canonical-role integrity. `MKQ-*` is internal Matryca terminology and must never be presented as official OKF conformance.
