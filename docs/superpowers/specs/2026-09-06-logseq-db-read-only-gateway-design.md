---
type: Specification
title: Logseq DB read-only gateway design
description: Additive, evidence-gated design for a Plumber-owned Logseq DB read path without widening existing filesystem or content-free contracts.
tags: [architecture, contracts, logseq, database, interoperability, safety]
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: core-runtime
verified: { by: human:marco-porcellato, at: '2026-09-06T00:00:00Z' }
last_verified: 2026-09-15
stale_after: 2027-03-05
related:
  - ../../decisions/2026-09-05-plumber-logseq-gateway-authority.md
  - ../../contracts/plumber-graph-read-v1.md
  - ../../quality/LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
  - ../../quality/V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md
---

# Logseq DB read-only gateway design

## Status and decision scope

This specification defines the only admissible architecture for a future
experimental Logseq DB read path in Matryca Plumber. It is a design and
admission boundary, not a runtime feature, transport qualification, release
claim, or authorization to execute Logseq.

It implements the accepted [Plumber Logseq gateway authority](../../decisions/2026-09-05-plumber-logseq-gateway-authority.md): Plumber owns selection of an official Logseq DB host surface and publishes `plumber.*` contracts. Matryca Trama and Matryca Brain are downstream consumers. They neither import Parser nor access a Logseq graph directly.

The current public-main baseline is
`233731cde79ceb2e26da91b935ad5a4dfd02c85c`, tree
`215122c0329643425de153cd42cba53fe142f812`. This rebaseline includes accepted
payload semantics in the ADR merged by [PR #590](../../decisions/2026-09-12-plumber-graph-payload-read-v1.md).
That decision completes the semantic-definition boundary only. It does not
qualify a DB host, payload implementation, adapter, consumer, or release.

## Current upstream evidence

At the 2026-09-15 evidence boundary:

- [Logseq db-test #833](https://github.com/logseq/db-test/issues/833) is
  closed. Closure is useful upstream status, not proof that any selected
  application artifact provides a correct page read.
- [Logseq db-test #1101](https://github.com/logseq/db-test/issues/1101) is
  open. MCP HTTP therefore remains prohibited.
- the earlier 2026-08-26 candidate is historical evidence only;
- a separate private 2026-09-08 arm64 DMG admission and help-only CLI discovery
  exists, with an embedded revision reported as `be800f1-dirty`. That revision
  is a provenance limitation and does not establish a DB read capability.

Every mutable upstream fact and the complete immutable asset identity must be
reverified before a new acquisition. The 2026-09-08 DMG is a completed,
separate admission attempt and must not overwrite or reinterpret the failed ZIP
attempt.

## Goal

After separately qualified host evidence exists, make exactly three bounded
read operations available through a Plumber-owned, session-bound boundary:

1. graph identification;
2. one selected page read;
3. one complete ordered block-subtree read.

The result must be bound to an exact official host artifact, selected graph,
session, source revision, synthetic fixture, Plumber source, and evidence
digest. A capability cannot become supported merely because a schema, fixture,
package, or local synthetic test passes.

## Non-goals

This design does not authorize or introduce:

- direct `db.sqlite`, internal table, Datascript, or undocumented-storage access;
- a Parser DB path or any Parser use for DB data;
- DB-to-Markdown fallback, implicit current-graph selection, or inferred session;
- mutations, graph switching, events, sync, login, import, export, backup, or UI control;
- Shadow ingestion, DB-backed Shadow acceleration, or a DB system-of-record claim;
- HTTP MCP while Logseq db-test issue #1101 remains open;
- a new public CLI command, MCP tool, FastAPI route, Trama integration, Brain integration, or release;
- use of a user graph, user root, global Logseq CLI, ambient configuration, or a host process outside the selected isolated root.

## Existing contracts remain intact

`plumber.graph.read/v1` remains the canonical, transport-neutral, **content-free**
static contract. Its passing page result contains only an opaque page identity;
its complete-subtree result contains opaque identifiers, parentage, and ordinal
structure. It must not be widened to carry page text, block text, titles,
properties, host objects, paths, credentials, or raw Logseq entities.

`plumber.graph.topology/v1` remains a separate content-free structural
projection. It is not a page or subtree payload substitute.

`GraphReadPort` remains the filesystem/Shadow repository port. It is not a DB
or session port. Its public signature, Markdown ownership, Shadow-health
selection, fallback semantics, and wheel-probe behavior remain outside this
programme.

## Additive payload contract

The DB-0 capability profile requires content and supported typed properties,
which cannot be represented by the existing content-free graph-read contract.
The additive contract family is therefore:

```text
plumber.graph.payload.read/v1
```

It is a separate public artifact and never an amendment of
`plumber.graph.read/v1`. Its static artifact must define:

- one contract identifier and major version;
- producer and consumer profiles with explicit capability declarations;
- `graph.identify`, `page.read`, and `block.subtree.read.complete` operation
  envelopes;
- exact graph, session, source-revision, host-artifact, and provenance bindings;
- bounded page and block payloads;
- a complete subtree assertion with contiguous per-parent sibling ordinals;
- a supported typed-property projection, not raw host-property objects;
- explicit `pass`, `rejected`, `unsupported`, and `error` outcomes;
- synthetic fixtures and a deterministic test kit that contain no user graph
  content, host credentials, local paths, or copied third-party fixture data.

The contract may carry runtime content only under its declared byte, node,
depth, property-count, and per-value limits. Static fixtures use synthetic
text. Public evidence contains sanitized structural facts and hashes, never
raw private graph payloads.

Before this contract is written, its dedicated ADR must select the property
projection, payload limits, redaction policy, consumer entitlement model, and
whether any consumer package may declare static intent. A consumer profile is
not runtime authority.

## Dependency direction

```text
Official Logseq DB host surface
        |
        v
+------------------------------------------------------------+
| Plumber-owned gateway boundary                             |
| agent-layer host adapter and composition                   |
| graph-layer session service and plumber.* payload contract |
+------------------------------------------------------------+
        |
        v
Trama or Brain consumer through the public contract only
```

The graph layer owns pure session state, validation, limits, operation result
models, expiry, close semantics, and graph/session binding. It does not import
`agent`, `daemon`, `rag`, Parser, subprocess, a database driver, or Logseq SDK
code.

The agent layer owns the selected official-host adapter and composition root.
It passes prevalidated values into the graph layer; the graph layer never
selects a binary, root directory, graph, transport, or fallback.

The future `GraphSessionReadPort` may add bounded page and complete-subtree
methods only after the payload contract and exact host qualification pass:

```python
class GraphSessionReadPort(Protocol):
    def identify(self, *, session_id: str, graph_id: str) -> GraphIdentityResponse: ...

    def read_page(
        self, *, session_id: str, graph_id: str, page_id: str
    ) -> GraphPageResponse: ...

    def read_complete_subtree(
        self, *, session_id: str, graph_id: str, root_block_id: str
    ) -> GraphSubtreeResponse: ...

    def close(self) -> None: ...
```

Every method rejects a foreign graph, unknown/closed/expired session,
unadvertised capability, unsupported version, malformed payload, incomplete
tree, excessive bound, or source-revision mismatch. It never retries through a
different source.

## Host selection and transport order

The host selection order is fixed:

1. the exact CLI bundled with an admitted official Logseq application artifact;
2. the official Logseq Plugin SDK, only after a documented CLI terminal result;
3. MCP stdio, only after independently documented CLI and SDK terminal results.

MCP HTTP is blocked while [Logseq db-test #1101](https://github.com/logseq/db-test/issues/1101) remains open. Closure of an upstream issue is discovery information, not executable compatibility evidence.

The adapter receives an immutable binding rather than resolving ambient state:

```python
@dataclass(frozen=True, slots=True)
class OfficialHostBinding:
    executable: Path
    executable_sha256: str
    embedded_revision: str
    root_dir: Path
    graph_name: str
    artifact_digest: str
```

For a CLI selection, every graph-bound invocation must explicitly bind the
selected root, graph, JSON output, and timeout. The permitted normal read
family is limited to host metadata and documented page/tree inspection. It
must not invoke `query`, debug, server lifecycle, sync, graph switching,
import/export, login, or a shell. The only exception is the separately
authorized, one-attempt Gate B recovery `server stop` described below; it is
not a read, adapter behavior, or Gate C operation.

## Artifact, fixture, and read-only evidence gates

### Gate A: artifact admission

An attempt begins only after a new official macOS arm64 artifact has immutable
release/asset identity, publisher-provided digest, matching local digest,
successful Apple code-signature verification, successful Gatekeeper admission,
and an inspectable bundled CLI. The exact `--version` revision and relevant
help output are bound before fixture creation.

The failed 2026-09-06 nightly archive remains immutable `upstream_blocked`
evidence. The separate 2026-09-08 admission also remains private artifact
evidence, not CLI semantic evidence. Neither record may be overwritten,
reclassified, or combined into a support claim.

### Gate B: fixture provisioning

Fixture provisioning is a separately authorized, destructive-to-fixture phase.
It uses a fresh disposable root and only the admitted artifact's documented
examples/help. It may create the one synthetic graph, one page, and one ordered
three-level block tree, then records generated host identifiers and an expected
graph-data fingerprint.

`graph create` switches the fixture graph according to the official CLI
documentation. Consequently it must never be included in, or credited as,
read-only qualification evidence. No user graph or user root may be opened.

### Gate B recovery verification for the incomplete nested fixture

The 2026-09-12 fixture attempt stopped after nested insertion returned only
the root identifier. This is an ambiguous fixture-verification failure, not a
fixture pass, host capability result, or transport result. The admitted
2026-09-08 DMG and help-only CLI discovery remain exact private artifact
evidence; artifact admission does not support a DB read claim. Preserve the
earlier PR #580 `upstream_blocked` result unchanged.

One separately authorized recovery-verification attempt may inspect only the
exact existing synthetic root and write evidence only to a new private
evidence directory. Its complete command set is limited to property
inventory, graph info, page show, root-UUID show, owner-scoped server stop,
and final server list. Record lifecycle effects as a separate inventory from
graph-semantic state, with inventories before reads, after reads, and after
server stop. Declare expected lifecycle transitions before the attempt; an
undeclared transition or unknown ownership stops it.

This boundary earns no Gate C credit and cannot produce a terminal transport
classification. It authorizes no fallback, graph or fixture writes,
import/export, query, sync, login, graph switch, reprovisioning, or retry. An
ambiguous or incomplete result remains preserved and stopped; no next transport
opens from this verification.

### Gate C: read-only qualification

The read-only phase reuses the frozen private fixture with explicit root and
graph binding. It captures pre/post graph-data fingerprints and bounded,
private raw output for each operation. Public evidence contains only sanitized
facts and digests.

The phase requires successful, mutually bound results for graph identification,
one page, and one complete ordered three-level subtree. It verifies graph and
source identity, generated runtime identifiers, parentage, sibling ordering,
content, supported typed properties, completeness, bounds, and selected-host
revision.

The bundled CLI automatically manages its worker and lock protocol. A later
evidence-profile change must therefore distinguish forbidden graph-semantic
state changes from explicitly declared lifecycle artifacts. Until that change
is separately reviewed, DB-0's `forbidden_state_changes: all` remains
fail-closed: any observed side effect stops the attempt. No qualification may
claim generic zero filesystem writes.

## Threat model and controls

| Threat | Required control |
| --- | --- |
| Repacked or mismatched application | Immutable asset identity, publisher digest, local digest, signature, Gatekeeper, embedded revision, and executable digest. |
| User graph selection or ambient config | Fresh disposable root; explicit root and graph on every call; reject missing, foreign, or inferred binding. |
| CLI lifecycle takeover | No manual server command except the separately authorized Gate B owner-scoped recovery stop; abort on replacement, stale-lock cleanup, orphan cleanup, unknown owner, or undeclared lifecycle action. |
| Internal-storage shortcut | No SQLite driver, file parser, Parser DB path, debug/query command, or undocumented host protocol. |
| Incomplete or reordered subtree | Require `complete: true`, stable identifiers, canonical parentage, contiguous per-parent ordinal order, and bounded depth/node count. |
| Source or session drift | Bind graph, source revision, artifact revision, session identity, and evidence digest on every delivered result. |
| Payload privacy leak | Synthetic static fixtures only; bounded runtime payloads; no raw graph text, paths, credentials, or private logs in GitHub evidence. |
| Silent fallback or capability escalation | One selected transport per attempt; no Markdown, Shadow, SDK, MCP, or retry fallback after a terminal result. |
| Consumer bypass | Consumers bind only versioned Plumber contracts and never import Parser or contact Logseq directly. |

## Terminal outcomes

The DB-0 vocabulary remains authoritative:

- `supported`: one exact host profile passes all three operations, bindings,
  bounds, read-only state checks, and consumer-compatibility gates;
- `capability_no_go`: the admitted host cannot provide a safe complete contract;
- `upstream_blocked`: official artifact admission or an upstream host defect
  blocks the selected host before a capability claim can be made.

An unexpected local failure, ambiguous output, missing evidence, sandbox
denial, timeout, or unreviewed lifecycle side effect is not a successful
classification. Preserve the evidence and stop; do not convert it into support
or use it to advance the transport order. Gate B recovery verification cannot
classify a transport or advance the transport order.

## RC4 distribution baseline

RC4 establishes that static contracts and their deterministic test kits must be
present in both wheel and source distribution and verified from an installed
artifact. A future payload contract therefore updates its own static resource
catalogue and the release build's required-member checks. It must not alter the
installed bytes, hashes, or meaning of existing `plumber.graph.read/v1`,
`plumber.graph.topology/v1`, or `plumber.consumer.package/v1` resources.

The payload contract's distribution proof is only archive integrity. It does
not prove an adapter, host, consumer, DB read, or release qualification.

## Implementation sequence

1. Approve the payload-boundary ADR and retain `plumber.graph.read/v1` byte
   compatibility.
2. Run the independent characterization-first `get_graph_read_port` lane;
   stop if its existing filesystem/Shadow behavior cannot be preserved exactly.
3. Complete a separately authorized official-host artifact, fixture, and
   read-only qualification sequence; publish a sanitized evidence record only
   after one valid terminal outcome.
4. Add the static payload contract, deterministic TCK, consumer-intent policy,
   and RC4-style installed-resource checks in one short contract PR.
5. Add pure session payload models and service behavior in one PR, with no host
   adapter or process execution.
6. Add the selected host adapter with an injected runner and synthetic
   transcript tests in one PR.
7. Add the narrow composition root only after the preceding contracts, host
   evidence, and adapter checks pass. Public surfaces remain a separate
   decision.

Each branch starts from current `main`, contains one independently reviewable
concern, and merges before a dependent branch is cut.

## Required validation

Every source or contract PR runs focused tests, `tests/test_graph_layer_boundary.py`,
the relevant deterministic TCK, documentation inventory generation/checks, and
hosted `make ci`. Before a release candidate, build the wheel and source
distribution from a clean tracked snapshot and prove that every static contract
and its colocated TCK is present, byte-correct, and executable from the
installed package.

Before any change to `get_graph_read_port`, run fresh code-graph impact analysis
and preserve its existing Markdown/Shadow caller behavior. Its known blast
radius includes the subtree read handler and the wheel qualification probe; DB
selection must never be added to that function.

## Authorization boundaries

Each operational phase remains independently identifiable even when one
maintainer-approved execution envelope authorizes several phases. The active
programme authorization permits the bounded artifact acquisition, admission,
fixture provisioning, read-only qualification, local implementation, signed
commits, issue maintenance, short pull requests, conditional signed squash
merges, and cleanup defined by the accompanying plan. Every action must still
pass its local prerequisites and stop conditions; authorization is not evidence
that a gate passed.

Tags, releases, package publication, stable support claims, public endpoint
exposure, DB writes, events, sync, internal SQLite access, DB-to-Markdown
fallback, DB-source Shadow ingestion, active-desktop coexistence claims, and
unrelated repository changes remain outside that envelope.
