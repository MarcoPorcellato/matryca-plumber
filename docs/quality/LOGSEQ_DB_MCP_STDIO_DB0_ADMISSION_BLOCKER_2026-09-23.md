---
type: audit
title: Logseq DB native MCP stdio DB-0 admission blocker — 2026-09-23
description: Public-safe official-source evidence that blocks native Logseq MCP stdio before strict DB-0 admission.
resource: docs/quality/LOGSEQ_DB_MCP_STDIO_DB0_ADMISSION_BLOCKER_2026-09-23.md
tags: [logseq, database, mcp, compatibility, provenance, safety]
last_verified: 2026-09-23
stale_after: 2026-12-22
status: blocked
classification: active
audience: [maintainer, contributor, operator]
owner: integration
authority: logseq-db-host-capability-attempt
related:
  - LOGSEQ_DB_CLI_DB0_ADMISSION_BLOCKER_2026-09-19.md
  - LOGSEQ_DB_SDK_DB0_CAPABILITY_NO_GO_2026-09-23.md
  - LOGSEQ_DB_READ_ONLY_GATEWAY_GOAL_2026-09-06.md
  - ../superpowers/plans/2026-09-06-logseq-db-read-only-gateway.md
  - EVIDENCE_INDEX.md
---

# Logseq DB native MCP stdio DB-0 admission blocker — 2026-09-23

## Verdict

**`upstream_blocked` for native MCP stdio before strict DB-0 admission.**

The reviewed public material does not bind an exact official native-stdio
artifact to its implementing source and a versioned host contract. Consequently,
no official stdio host can cross DB-0 admission. Historical reports establish a
write-capable stdio surface, not an enforceable observer-only one. They also do
not establish immutable graph/session/revision binding or complete, coherently
ordered subtree reads.

This is not a finding that every official stdio implementation lacks those
capabilities. It is a bounded blocker for this evidence packet and this strict
admission attempt.

No MCP producer, package, host application, artifact, fixture, graph, database,
executable, or user root was downloaded, installed, opened, executed, or
changed for this decision.

## Exact public-source record

| Surface | Exact record | Finding used by this review |
| --- | --- | --- |
| Current official Logseq source | `logseq/logseq@43a540f35049689088ecb4038a2bec893f40ea94` | Exact current public source boundary. |
| Current source tree | `1e20d7437cb8e9b249e15b3154fa800a66f9d6aa` | Binds the current HTTP MCP source blobs without transferring historical stdio evidence. |
| Current HTTP MCP server | [`src/electron/electron/mcp_server.cljs`](https://github.com/logseq/logseq/blob/43a540f35049689088ecb4038a2bec893f40ea94/src/electron/electron/mcp_server.cljs), blob `7f8c3c5b186a98c6e86b0bd25883bf70226819c9` | Exact source implements HTTP MCP API tools, including `upsertNodes`. |
| Current HTTP MCP transport | [`src/electron/electron/mcp_transport.cljs`](https://github.com/logseq/logseq/blob/43a540f35049689088ecb4038a2bec893f40ea94/src/electron/electron/mcp_transport.cljs), blob `e8bfb849d5a682bd2b45918e1d610d4458b7510d` | Exact source implements HTTP request hand-off, not native stdio behavior. |
| Historical CLI reference | `@logseq/cli` `0.4.3`, reported build `b09316a`; full commit `b09316abd7bde39d25c6c5694d01b2d4e874fe01`, tree `234f3c40e21eff92a0c8bad5f10376e69b164914` | The claimed historical CLI source path is not present at that exact commit; it does not bind a stdio artifact to implementation bytes. |
| Official DB documentation | [`logseq/docs@08f855f24d66e4509b7ea808554c13b4649e6ee1`](https://github.com/logseq/docs/blob/08f855f24d66e4509b7ea808554c13b4649e6ee1/db-version.md), tree `3309b25a2a603036a1a56b51d6e38d206c8106a6` | Does not publish the required native-stdio artifact or DB-0 read contract. |

The current verified source is an HTTP implementation and must not be used as
evidence for historical stdio behavior. Conversely, historical issue reports
must not be used as a substitute for exact artifact and source provenance.

## Historical stdio evidence is insufficient for admission

The official closed [db-test #834](https://github.com/logseq/db-test/issues/834)
records `@logseq/cli` `0.4.3` and `logseq mcp-server --stdio -a ...`. It also
records that `upsertNodes` writes to the app even when its response cannot be
parsed as JSON. This establishes that a historical stdio invocation existed and
was write-capable. It does not establish a versioned read-only permission,
observer-only startup mode, artifact identity, source linkage, or safe complete
read contract.

The open [db-test #1101](https://github.com/logseq/db-test/issues/1101) is an
HTTP multi-session failure and states that separate stdio invocations are not
affected. It keeps MCP HTTP prohibited under the existing policy, but its
stdio observation does not cure the admission gaps above.

The closed [db-test #833](https://github.com/logseq/db-test/issues/833) and
open [logseq #12783](https://github.com/logseq/logseq/issues/12783) are
negative context for `getPage`; neither proves a complete ordered recursive
subtree read for an exact stdio candidate.

## Missing DB-0 admission bindings

| DB-0 requirement | Public-source result | Why admission cannot continue |
| --- | --- | --- |
| Exact official stdio host identity | No exact stdio artifact, implementation tree/blob, and versioned contract are bound together. | A historical command report cannot identify an admissible host. |
| Enforceable observer-only authority | Historical stdio evidence includes `upsertNodes`; no reviewed official stdio policy excludes writes, implicit lifecycle effects, or other entry points. | Omitting a write call is not an authority boundary. |
| Immutable graph/session/source-revision binding | No reviewed contract binds each page or subtree response to immutable graph, session, and revision evidence. | Result provenance cannot satisfy the payload contract. |
| Complete ordered block-subtree read | No reviewed stdio contract guarantees recursive descendants, canonical sibling order, truncation detection, or one coherent snapshot. | A returned partial tree could be mistaken for a complete subtree. |
| Bounded payload semantics | No reviewed stdio schema defines the approved page/subtree limits, typed property rules, redaction, or error semantics. | Generic MCP tool availability cannot substitute for the bounded Plumber contract. |

The missing subtree, ordering, revision, and coherence guarantees are **not
proven absent** from every possible stdio implementation. They are unproven for
an exact admissible official host, which is sufficient to block DB-0 admission.

## Classification and limits

This is `upstream_blocked`, not `capability_no_go`: required guarantees cannot
be attributed to an admitted exact stdio host because that host’s artifact,
implementing source, and contract are unbound. The current HTTP implementation
does not establish stdio behavior, and the historical stdio report does not
establish artifact provenance or observer enforcement.

This blocks the **native MCP stdio transport lane only**. It does not qualify a
DB read, complete issue #491, authorize a workaround or another API, or weaken
the DB-0 profile. Together with the terminal CLI and Plugin SDK records, it
completes the currently permitted three-transport programme with no supported
host.

## Reopening conditions

A fresh admission review may begin only when public upstream evidence supplies:

1. an exact official stdio artifact with reproducible linkage to implementing
   source, tree, and blobs;
2. a version-bound transport, tool-schema, authorization, lifecycle, and
   side-effect contract;
3. immutable graph/session/revision binding plus bounded page and complete
   ordered-subtree semantics, including coherence and truncation detection;
4. an enforceable observer authority covering startup and implicit effects; and
5. an exact-candidate disposition of relevant upstream defects.

Satisfying this documentary gate would permit only a request for separate
artifact and runtime-qualification authority. It would not itself authorize
downloads, installation, execution, fixtures, reads, or a Plumber adapter.
