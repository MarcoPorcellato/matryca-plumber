---
type: Guide
title: Documentation evolution and operating model
description: How Matryca Plumber documentation evolved into an OKF v0.2-compatible, provenance-aware, progressively disclosed knowledge system.
resource: docs/knowledge/
tags: [documentation, okf, governance, maintenance, provenance]
generated: { by: human:marco-porcellato, at: '2026-08-06T00:00:00Z' }
verified: { by: human:marco-porcellato, at: '2026-08-24T00:00:00Z' }
last_verified: 2026-08-24
stale_after: 2027-02-20
status: stable
classification: canonical
canonical_for: documentation.governance
audience: [maintainer, contributor, operator, agent]
owner: core-runtime
supersedes: []
related:
  - /profile.md
  - /inventory.md
---

# Documentation evolution and operating model

Matryca Plumber documentation is both a human learning surface and an agent-readable knowledge system. Its current design preserves the repository’s long technical history without forcing every audit, release record, or issue body into one metadata template.

The result is a layered model: maintained concepts are structured and strongly validated; the complete legacy corpus remains discoverable through a curated inventory; Matryca Knowledge consumes committed source bytes through a reviewed, read-only projection.

## Why the documentation changed

The repository originally grew through conventional entry points, architecture documents, OpenSpec contracts, roadmaps, release notes, and extensive quality evidence. That breadth was valuable, but it created three navigation problems:

1. readers had to know exact filenames before discovering the right document;
2. current contracts and historical evidence were difficult to distinguish mechanically;
3. external knowledge tools could copy documents without a precise source-authority boundary.

The first documentation pilot introduced `docs/knowledge/`, YAML metadata, a generated inventory, and progressive-disclosure indexes. It was intentionally described as an OKF-inspired v0.1 draft pilot. The updated model corrects that transitional language and aligns the maintained bundle with the pinned Google Open Knowledge Format v0.2 specification while keeping stricter Matryca quality rules separate.

## The current model

```text
authoritative Matryca Plumber repository
├── maintained knowledge bundle: docs/knowledge/
│   ├── OKF v0.2 concepts with trust and lifecycle metadata
│   ├── progressive-disclosure index files
│   ├── chronological log.md
│   └── deterministic generated inventory view
├── canonical detailed contracts at established repository paths
├── OpenSpec, roadmaps, runbooks, releases, and quality evidence
└── inventory.json classification for the complete documentation corpus

committed source bytes
└── Matryca Knowledge inventory and reviewed projection
    └── navigation and retrieval only; never the editing origin
```

## Two conformance layers

### Official OKF compatibility

OKF supplies the portable interchange format: Markdown concepts, YAML frontmatter, stable path identity, ordinary links, optional trust and lifecycle families, and reserved index/log files. A generic OKF consumer requires only `type` on concept documents and must preserve unknown extensions.

### Matryca quality

Matryca adds producer guarantees needed for a maintained engineering repository: title and description, explicit lifecycle, classification, verification freshness, canonical ownership, valid maintained links and anchors, repository-safe legacy pointers, deterministic inventory, and immutable Git provenance at the federation boundary.

The repository targets MKQ-4. MKQ levels are Matryca maturity labels, not Google OKF conformance levels.

## Source of truth and projection boundary

Matryca Plumber is the sole editing origin for its documentation. Matryca Knowledge may:

- inventory allowlisted committed Markdown;
- attach the exact repository, commit, path, and hash;
- validate the selected source profile;
- build a reviewed Git projection and local search index;
- propose source changes for maintainer review.

It must not silently rewrite source files, ingest uncommitted documentation, or become a second canonical copy. A projection lag is acceptable and visible; ambiguous authority is not.

## How to find documentation

Use the smallest surface that answers the question:

1. Start at the repository [Documentation table](../../README.md#documentation) for public entry points.
2. Open the [knowledge index](index.md) for progressive disclosure across maintained concepts and legacy collections.
3. Read the [profile](profile.md) when authoring or reviewing metadata.
4. Use the generated [inventory](inventory.md) to locate, classify, or migrate legacy documentation.
5. Follow detailed architecture, OpenSpec, roadmap, release, and quality links only when deeper evidence is required.

For v2 operation, use one path: the README links to the canonical
[Shadow DB runtime and operator contract](architecture/shadow-db.md). That contract
links onward to release mechanics and current qualification evidence without making
either surface a second runtime authority.

## Authority by surface

| Surface | Sole role |
| --- | --- |
| `README.md` | Stable product overview and navigation |
| `docs/knowledge/architecture/shadow-db.md` | Current v2 Shadow runtime and operator contract |
| `docs/RELEASE_PROCESS.md` | Release mechanics and maintainer authority gates |
| `CHANGELOG.md` | User-visible version deltas |
| `docs/roadmaps/` | Future work and sequencing |
| `docs/quality/` | Timestamped evidence and decisions |
| `docs/releases/` | Historical publication text |

When a mutable statement appears outside its owning surface, replace it with a concise
stable summary and a link. Do not rewrite historical release or quality evidence to
match the current runtime.

## How to add or update a maintained concept

1. Choose a stable lowercase path under `docs/knowledge/`; renaming changes the OKF concept ID.
2. Add the required frontmatter from the [profile](profile.md).
3. Use `status` only for the OKF lifecycle and `classification` only for Matryca governance.
4. Declare `canonical_for` only when the document is the sole owner of that role.
5. Record human or deterministic verification in `verified` and update `last_verified` during the transition period.
6. Set an absolute `stale_after` review date.
7. Link the concept from the nearest `index.md` with a concise description.
8. Add an entry to [`log.md`](log.md) for a material documentation-system change.
9. Run the documentation gates before requesting review.

## How to add ordinary repository documentation

Documentation outside `docs/knowledge/` keeps the format appropriate to its purpose. Do not mass-add frontmatter to historical evidence. After adding, moving, or removing a Markdown file:

```bash
make docs-inventory-sync
make docs-inventory-md
make docs-check
make docs-audit
```

Review the new `inventory.json` entry. Heuristics are discovery defaults, not authority decisions: correct its type, classification, owner, action, destination, and canonical role where needed.

## Deterministic gates

`make docs-check` validates:

- OKF v0.2 root-index shape and reserved filenames;
- required maintained-concept metadata;
- official lifecycle values and Matryca classifications;
- verification and freshness field shapes;
- unique canonical roles;
- local maintained links, anchors, and safe legacy-source paths;
- newest-first ISO dates in `log.md`;
- inventory schema and path drift;
- byte-identical generated inventory output.

`make docs-audit` reports legacy coverage and unresolved `keep` classifications without rewriting files.

`make check` and `make ci` both include `docs-check`, so documentation integrity is part of local acceptance, pull-request CI, and release-source verification.

## Evolution timeline

| Date | Evolution |
| --- | --- |
| 2026-07-18 | Introduced the OKF-inspired pilot bundle, architecture concepts, and repository inventory |
| 2026-07 to 2026-08 | Expanded architecture knowledge for Shadow DB, deterministic retrieval caching, and LLM-free cluster recognition |
| 2026-08-06 | Adopted the pinned OKF v0.2 contract, separated official lifecycle from Matryca classification, added trust/freshness metadata, enabled canonical roles and anchors, and documented the source/projection boundary |
| 2026-08-07 | Established one navigable v2 operator path and an explicit authority role for each maintained documentation surface |
| 2026-08-24 | Separated exact-artifact evidence retention from risk-selected release-gate applicability, preserving immutable history while avoiding disproportionate operational qualification for low-risk changes |

## Future evolution

Future registry-side improvements remain owned by Matryca Knowledge and require their
own exact-commit evidence. Any reviewed projection must continue to report official
OKF compatibility separately from Matryca quality, expose projection lag, and preserve
this repository as the editing origin. The transitional `last_verified` field can be
retired only after the registry freshness gate reads native `verified[].at` events.
Any broader relocation of legacy documents remains a separate, reviewed migration
rather than an automatic consequence of this profile.
