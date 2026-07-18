---
type: Specification
title: Matryca knowledge profile
description: Local OKF-inspired profile for the docs/knowledge bundle — types, metadata, and production rules.
resource: docs/knowledge/
tags: [okf, documentation, governance]
timestamp: 2026-07-18T00:00:00Z
status: current
audience: [maintainer, contributor, agent]
owner: core-runtime
supersedes: []
related:
  - /index.md
  - /inventory.md
profile_version: "0.1"
okf_target: "0.1-draft"
conformance: partial
okf_reference: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
---

# Matryca knowledge profile

This bundle is an **OKF-inspired pilot** with **partial conformance**. It is not yet the repository-wide single source of truth. Upstream reference: [Open Knowledge Format v0.1 (draft)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

## Conformance scope

| Layer | PR1 status |
| --- | --- |
| `docs/knowledge/` concept documents | Frontmatter + internal link checks via `make docs-check` |
| Legacy `docs/**` corpus | Classified in `inventory.json`; audit via `make docs-audit` |
| Public OKF conformance claim | Deferred to Phase 5 |

## Document types

| `type` | Use |
| --- | --- |
| Product Overview | Identity, principles, scope |
| Guide | Procedures for a specific audience |
| Architecture | Current system structure |
| Specification | Normative behavior |
| Reference | Commands, env vars, MCP tools, APIs |
| Runbook | Operations and recovery |
| Decision | ADR and durable trade-offs |
| Roadmap | Future work |
| Audit | Findings and hardening |
| Release Note | State of a shipped version |
| Archive | Historical, non-normative material |

## Required metadata

### OKF (draft v0.1)

- **`type`** — required on every concept document.

OKF also defines optional fields (`title`, `description`, `resource`, `tags`, `timestamp`) and reserved filenames (`index.md`, `log.md`).

### Matryca profile extensions

The pilot applies stricter producer rules inside `docs/knowledge/`:

| Field | Required | Notes |
| --- | --- | --- |
| `title` | yes | Human title |
| `description` | yes | One-line summary for indexes |
| `timestamp` | yes | ISO 8601 UTC |
| `status` | recommended | `current`, `experimental`, `planned`, `deprecated`, `archived` |
| `audience` | recommended | `maintainer`, `contributor`, `operator`, `agent` |
| `canonical_for` | optional | Globally unique semantic key when present |
| `owner` | recommended | Steward area |
| `supersedes` | optional | Prior concept paths |
| `related` | optional | **Bundle-internal** concept links only (`/architecture/foo.md`) |
| `legacy_sources` | optional | Transitional repo-relative legacy paths outside the bundle |
| `profile_version` | profile only | Matryca profile semver |
| `okf_target` | profile only | Target OKF revision |
| `conformance` | profile only | `partial` until Phase 5 |

Do not place legacy file paths in `related`. Use `legacy_sources` for transitional authority pointers. `make docs-check` validates that each `legacy_sources` entry is repo-relative, resolves inside the repository root, and points to an existing file.

## Inventory extensions

`inventory.json` entries may include:

- `action`: `keep`, `migrate`, `split`, `merge`, `archive`, `artifact`, `generated`
- `surface_class`: `concept-candidate`, `runtime-contract`, `repository-entrypoint`, `generated`, `artifact`
- `destination`: future repo-relative target under `docs/knowledge/` or `docs/artifacts/`
- `missing`: `true` when a curated path no longer exists on disk

## Link conventions

- **Bundle-internal:** `/architecture/system-overview.md` resolved from `docs/knowledge/`.
- **Legacy / external:** normal repo-relative Markdown links or `legacy_sources` in frontmatter.
- **Index files:** `index.md` at bundle or section roots; no frontmatter required in PR1.

## Reserved names

- `index.md` — progressive disclosure view for a directory.
- `log.md` — chronological decision index (Phase 4).
