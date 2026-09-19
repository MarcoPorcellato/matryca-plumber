---
type: audit
title: Logseq DB bundled CLI static schema evidence — 2026-09-15
description: Hash-bound static evidence for the shallow JSON result schemas required by the bounded bundled-CLI recovery observation.
resource: docs/quality/LOGSEQ_DB_CLI_STATIC_SCHEMA_EVIDENCE_2026-09-15.md
tags: [logseq, database, compatibility, qualification, provenance, safety]
last_verified: 2026-09-15
stale_after: 2026-12-14
status: partial
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - ../decisions/2026-09-05-plumber-logseq-gateway-authority.md
  - LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
  - LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - EVIDENCE_INDEX.md
---

# Logseq DB bundled CLI static schema evidence — 2026-09-15

## Verdict

**Static admission: bounded Gate B observation schema only.**

The exact admitted macOS arm64 DMG was mounted read-only and its packaged CLI
entry was inspected statically. This establishes a narrow JSON envelope and
shallow command-data shapes sufficient to design a fail-closed *recovery
observation* validator for the already existing synthetic fixture.

It does not execute Logseq, create or read a graph, prove worker behavior,
establish a general CLI API, qualify a transport, or establish Logseq DB
support. It does not permit fixture mutation, Gate C qualification, an adapter,
or a public support claim.

## Exact artifact binding

| Object | SHA-256 |
| --- | --- |
| Admitted DMG | `1a71e4c0f8c304452b3126e03256141c365dd2c69197c516a05027811cef429f` |
| Packaged `app.asar` | `9c476c014b6d65efa2d707f612d5cd26a3adcc0af4c048f1bb52c01ee7799ca7` |
| `js/logseq-cli.js` | `b3710e5a0eba20272ab5e3b8bfe7a87b2697e283de109973cd4bf5910eb40a98` |

The CLI entry was found at the exact archived path `js/logseq-cli.js`, with
archive offset `80054483` and size `817565` bytes. These facts bind this record
to the inspected application image rather than to mutable upstream source.

## Admitted JSON boundary

Only `--output json` is admissible. One parseable JSON value is required.

| Result | Required envelope |
| --- | --- |
| Success | `{ "status": "ok", "data": ... }` |
| Failure | `{ "status": "error", "error": { "code": string, "message": string, ... } }` |

The recovery observer must reject missing or extra top-level result modes,
malformed JSON, an error result, multiple JSON values, excess output, or any
artifact/entry hash mismatch. Exit status alone is not evidence.

## Admitted shallow command data

| Command | Static shape admitted for Gate B | Boundary |
| --- | --- | --- |
| `graph info` | object with `graph` string, graph-created/schema fields, and `kv` object | Runtime values remain variable. |
| `list property` | object with `items` array | Item entity fields remain dynamic. |
| `show --page` / `show --uuid` | object with `root` object and default `linked-references` object containing `count` and `blocks` | Entity fields are dynamic; `show/` implementation keys are removed. |
| `server list` | object with `servers` array of lifecycle records | This is lifecycle evidence, not graph semantics. |

The exact entry also implements the documented JSON serializer and a fixed
`server stop` success object containing `repo`. `server stop` is intentionally
outside read observation: it is a separately bounded lifecycle action and its
return shape does not prove process ownership or cleanup.

## What remains unproven

- Runtime output for every command and error case.
- Complete fixed schemas for dynamic graph, property, and entity fields.
- The synthetic fixture's nested tree, page, graph identity, source revision,
  ordering, completeness, typed-property values, and lifecycle behavior.
- Zero forbidden state change under the DB-0 profile.
- Any terminal CLI transport result, Plugin SDK/MCP result, Plumber adapter, or
  product support.

## Re-entry boundary

Before any bounded recovery observation, bind the exact artifact, a separately
identified launcher or interpreter, the archived CLI entry, command grammar,
fixture manifest, configuration, private evidence root, time/output limits,
shallow validator, lifecycle inventory, and stop conditions. The archived
entry alone is not an executable claim. The runner must retain its separate
execution-safety requirements: revalidation immediately before process
creation, disjoint roots, bounded capture, durable evidence, cancellation
handling, and post-read inventory. `server stop` remains outside DB-0.

This record supersedes neither the historic ZIP `upstream_blocked` evidence nor
the current programme's transport order. It only removes the prior
`schema_blocked` state for a tightly scoped Gate B observation design.
