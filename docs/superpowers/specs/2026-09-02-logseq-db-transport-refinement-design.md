# Logseq DB Transport Refinement Design

**Status:** proposed architecture refinement; no runtime compatibility claim

## Purpose

Matryca Plumber already supports Logseq OG directly through its file-backed
Markdown and Shadow read paths. That path remains independent of Matryca Trama.
Logseq DB is a separate authority model. This design defines how the existing
DB read-only programme chooses one supported host-mediated transport without
weakening OG safety or treating an internal database file as an integration
surface.

The first possible DB claim remains deliberately small:

1. identify one active DB graph;
2. read one page;
3. read one complete ordered block subtree.

## Context and Evidence

Logseq OG is maintained as a separate file-graph application. Its own tracking
includes an open request to reject DB graphs rather than attempt to open them.
That establishes a product-level safety boundary: an OG reader must not interpret
a DB graph as a file graph.

Official Logseq DB documentation describes `db.sqlite` as DB graph storage and
documents a separate Markdown Mirror format. The official Plugin SDK exposes
graph identity, DB-mode detection, page/block query APIs, and page block-tree
methods. These are candidate inputs to a capability spike, not a support claim.

Every executable probe must record exact upstream source commit, application
build, SDK or CLI version, fixture digest, probe commit, command/result digest,
and platform. A later version creates a new evidence row; it never replaces an
older result.

## Authority Model

The three source modes are not interchangeable:

| Mode | Authority | Plumber behaviour |
| --- | --- | --- |
| OG direct files | Selected Logseq OG Markdown graph | Existing Plumber direct path; parser and Shadow behaviour remain unchanged. Trama is not an inline dependency. |
| DB Markdown Mirror | Official host-produced projection of a DB graph | Candidate read transport only after identity, completeness, freshness, and provenance qualify. Never canonical by inference. |
| DB host route | Official DB host surface | Candidate session-bound transport only after the capability spike selects it. |

`db.sqlite` is never a transport. Plumber, Trama, tests, fixtures, and
documentation must not open, query, copy, or mutate it.

The OG adapter must reject a DB graph. The DB route must reject a missing or
foreign host session. Neither route may silently fall back to another source,
cache, export, or Shadow projection.

## Candidate DB Transports

The capability spike evaluates these alternatives independently and selects at
most one:

1. **Markdown Mirror.** It is eligible only when an official host contract
   proves graph binding, page identity, complete ordered descendants, freshness,
   and version provenance. Its `id::` marker is identity metadata, not an
   ordinary page property. A mirror must never be assumed current merely because
   files exist.
2. **Official CLI or built-in MCP.** It is eligible only when the exact pinned
   release supplies all three operations, bounded response semantics, graph
   selection, and complete descendants. A nightly-only surface remains probe-only.
3. **In-process Plugin SDK bridge.** It is eligible only when the exact pinned
   application and SDK prove the required operations. The bridge remains inside
   the Logseq host and exposes only the versioned Trama contract to an external
   consumer.

No candidate is preferred before execution. A partial top-level-block response
does not satisfy complete subtree read.

## Trama and Plumber Responsibilities

For a future DB route, Matryca Trama owns capability probing, host lifecycle,
graph/session binding, host-object normalization, and the selected DB
transport. Matryca Plumber owns the consumer-side session boundary and
preserves existing agent-facing CLI/MCP behaviour. This does not put Trama in
front of Plumber's existing direct OG path.

Trama remains Python-first for contracts, core behaviour, synthetic fixtures,
and OG integration. If and only if the Plugin SDK wins the capability spike, a
minimal TypeScript host bridge may be separately designed. It must contain no
domain logic, persistence, cache, write capability, or alternate authority.

Plumber keeps filesystem `GraphReadPort` unchanged. A distinct session-bound
read port may be introduced only after one transport has passed the capability
spike and the shared contract is accepted by both repositories.

## D1 Capability Decision

For each candidate, synthetic and disposable-app qualification must prove:

- DB-mode detection and stable graph identity;
- one page result with explicit supported-field semantics;
- one complete, ordered descendant tree with IDs, parentage, and no duplicates;
- exact host/version/provenance binding;
- bounded payloads and privacy-safe evidence;
- explicit rejection of graph switch, stale session, disconnect, foreign graph,
  unsupported version, malformed result, and incomplete subtree;
- zero direct SQLite access and zero writes.

Decision D1 has only three valid outcomes:

| Result | Action |
| --- | --- |
| One candidate passes every requirement | Record its exact profile; write one transport-specific implementation plan. |
| More than one candidate passes | Select one using the smallest least-authority, versioned, externally consumable boundary; document why others remain unselected. |
| No candidate passes | Publish a bounded NO-GO evidence record; keep DB support unavailable. |

## Explicit Deferrals

This design does not authorize user-graph access, DB writes, events, live
convergence, Shadow ingestion from DB, search expansion, export, recovery,
sync, credentials, UI, Nodi, or a Matryca Brain connection. Trama's future
applications, Nodi, exports, and integrations are product direction, not
current runtime capability. Existing OG, Strict Read Only, Shadow, Tine Direct
Files, MCP, and CLI contracts remain unchanged.

## Delivery Sequence

1. Amend Plumber and Trama planning documents with this transport-neutral model.
2. Freeze one shared evidence schema and negative fixtures.
3. Run isolated capability probes against synthetic and disposable DB fixtures.
4. Record D1 as supported or NO-GO.
5. Only if D1 selects one transport, write its implementation plan and start
   short, repository-local trunk branches.

## Acceptance Criteria

- Documentation distinguishes OG authority, DB authority, and derived projections.
- Markdown Mirror, CLI/MCP, and Plugin SDK are alternatives, not implicit fallbacks.
- Python-first Trama remains intact; any TypeScript bridge is conditional and isolated.
- No document implies DB runtime support, direct SQLite access, or write capability.
- Both repositories retain a clear stop condition when no official candidate qualifies.
