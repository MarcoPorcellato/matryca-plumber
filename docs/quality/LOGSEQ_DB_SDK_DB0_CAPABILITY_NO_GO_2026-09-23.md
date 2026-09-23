---
type: audit
title: Logseq DB Plugin SDK DB-0 capability no-go — 2026-09-23
description: Public-safe exact-source evidence that the reviewed official Plugin SDK cannot satisfy the strict DB-0 admission requirements.
resource: docs/quality/LOGSEQ_DB_SDK_DB0_CAPABILITY_NO_GO_2026-09-23.md
tags: [logseq, database, compatibility, provenance, safety]
last_verified: 2026-09-23
stale_after: 2026-12-22
status: blocked
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - LOGSEQ_DB_CLI_DB0_ADMISSION_BLOCKER_2026-09-19.md
  - LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md
  - EVIDENCE_INDEX.md
---

# Logseq DB Plugin SDK DB-0 capability no-go — 2026-09-23

## Verdict

**`capability_no_go` for the Plugin SDK lane before DB-0 admission.**

The exact reviewed Plugin SDK source exposes useful graph and editor reads, but
does not establish the identity, snapshot, completeness, ordering, provenance,
or enforceable read-only guarantees required by the current DB-0 profile.
This is a bounded result for the pinned source below. It does not assert that a
future SDK version, a different official host surface, or a separately approved
adapter can never satisfy those requirements.

No SDK package, host application, executable, fixture, graph, database, or user
root was downloaded, installed, opened, executed, or changed for this decision.

## Exact public-source record

| Surface | Exact record | Finding used by this review |
| --- | --- | --- |
| Official source | `logseq/logseq@d58ff171693eb5ac71b68188c99836fce051d790`, tree `25c50c552dc47b03404882aee4bd8e70182d093f` | Inspectable source boundary for this ruling. |
| SDK declarations | [`libs/src/LSPlugin.ts`](https://github.com/logseq/logseq/blob/d58ff171693eb5ac71b68188c99836fce051d790/libs/src/LSPlugin.ts), blob `34b2226e332db09cd540bdbb8f18cac89d137695` | Graph, editor, DB, notification, and write API declarations. |
| SDK package metadata | [`libs/package.json`](https://github.com/logseq/logseq/blob/d58ff171693eb5ac71b68188c99836fce051d790/libs/package.json), blob `5778bc61debe74451d908ef113a0033fb3248d96` | Declares `@logseq/libs` version `0.3.4`. |
| DB query guide | [`libs/guides/db_query_guide.md`](https://github.com/logseq/logseq/blob/d58ff171693eb5ac71b68188c99836fce051d790/libs/guides/db_query_guide.md), blob `29044c08ba599f4da0edd9ebb239fa13d838c455` | Documents broad query access, not a bounded DB-0 payload contract. |
| Release context | Official nightly release `248188362`, mutable `nightly` tag, target `dde0aba2d441c962d28989b0af894cc261da3898`, prerelease | Context only; it is not a qualification artifact or source binding. |

## Available operations are not DB-0 admission evidence

The declarations expose `App.getCurrentGraph()` and DB-mode detection, and
`Editor.getPage()` plus `Editor.getPageBlocksTree()` provide named page and tree
operations. `BlockEntity` includes identifiers, an `order` field, and optional
children. These APIs show that a future integration may have a useful surface.
They do not, by their names or declarations alone, prove the required DB-0
guarantees.

The same declarations expose general DB querying and change notifications, as
well as page and block write operations. Their presence does not mean a write
occurred. It means that a conventionally read-only plugin is not an
SDK-enforced observer boundary under the strict profile.

## Missing required bindings

| DB-0 requirement | Exact-source result | Why admission cannot continue |
| --- | --- | --- |
| Immutable graph, session, and source-revision binding | `getCurrentGraph()` exposes name, URL, and path; no immutable graph ID, session token, snapshot token, or source revision is declared for a read result. | A page or subtree cannot be bound to one verified source state. |
| One bounded page read with provenance | `getPage()` accepts an identifier but its declared result is not bound to artifact, graph session, or revision evidence. | Result identity cannot meet the payload contract. |
| Complete ordered block-subtree read | `getPageBlocksTree()` and `BlockEntity.order` exist, but the reviewed declarations and guide do not promise an atomic, complete, stable ordered snapshot during concurrent host activity. | A returned tree cannot prove completeness or contiguous sibling order. |
| Enforceable zero-side-effect observer | The SDK exposes writes alongside reads; no reviewed permission or observer-only capability constrains the caller to the required surface. | DB-0 cannot depend on an application convention to prevent forbidden state change. |
| Bounded typed payload contract | `DB.datascriptQuery()` is broad, and the reviewed material provides no DB-0-specific schema, limits, redaction, or provenance contract. | Generic query capability cannot substitute for the approved bounded payload semantics. |

`DB.onChanged()` does not close these gaps: observing transactions is not an
immutable read snapshot and cannot prove that a page and its entire subtree came
from one coherent source revision.

## Classification and limits

This is `capability_no_go`, rather than `upstream_blocked`, because the exact
official source was available and inspectable and the required guarantees were
not established. It is not a general rejection of the Plugin SDK, a runtime
failure, or evidence that any SDK operation is unsafe in every context.

This blocks the **Plugin SDK transport lane only**. It does not qualify a DB
read, complete issue #491, classify MCP stdio, or authorize an adapter,
artifact, fixture, executable, host process, graph access, or upstream change.

## Next gate

Preserve this record and update #491 without closing it. The only next transport
activity is a separate MCP stdio pre-admission evidence review against exact
official public material. It must begin as a new bounded attempt. MCP HTTP
remains prohibited while [db-test #1101](https://github.com/logseq/db-test/issues/1101)
is open.
