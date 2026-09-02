# Epistemic Claim Layer v0 design

## Status and decision boundary

This is a design specification only. It does not create a runtime feature,
schema, environment variable, CLI/MCP surface, issue, external repository, or
standards proposal. It is derived from the active research anchor
[`docs/knowledge/architecture/epistemic-memory.md`](../../knowledge/architecture/epistemic-memory.md).

The design baseline is the signed research commit
`9b5552e59ce654a520fc6f0ef58115614b922350`, itself based on reviewed Plumber
source `1673bc0167d5b45e8ce09567f75d86f2f50a302e`. It does not qualify any later
revision or transfer runtime evidence.

## Goal

Define the smallest safe v0 contract for a local **Epistemic Claim Layer**:
immutable source-bound events, deterministic replay into a rebuildable derived
projection, explicit support/challenge/revision relationships, and read-only
explanations.

The goal is not to decide whether a claim is true. The goal is to represent
what an explicitly versioned policy currently assesses about a claim, why that
assessment exists, and which source-bound events produced it.

## Non-goals

v0 excludes all of the following:

- canonical Markdown writes, automatic curation, promotion, correction, or
  deletion;
- direct Logseq DB access, DB host transport, sync, events, or Shadow changes;
- LLM training, fine-tuning, Bayesian Neural Networks, or a required
  probabilistic update algorithm;
- numerical confidence, probability calibration, source-reliability learning,
  or implicit-signal learning;
- automatic evidence capture, autonomous retrieval reranking, agent action, or
  proactive delivery;
- changing the existing P0 `EvidenceEvent`, `EvidenceArchive`,
  `P0EvidencePacket`, `MemoryCandidate`, or `RecallBundle` contracts;
- reusing `memory_procedures` fields as general claim semantics;
- public raw vault text, prompts, credentials, absolute paths, or content
  payloads in schemas, fixtures, receipts, or explanations;
- any claim that this contract is an external standard or AAIF proposal.

## Existing contracts that remain authoritative

| Existing contract | v0 relationship |
| --- | --- |
| Markdown graph plane | Remains the semantic source of record. Claims cannot replace or silently mutate it. |
| Logseq Matryca Parser | Remains the source of parsed block structure, locations, and source revisions. |
| P0 evidence models | Remain immutable provenance for proposed candidates. v0 may reference them but never extends their closed schemas. |
| P0 evidence archive | Remains a sparse, privacy-safe archive. It is not repurposed as the claim ledger. |
| Recall bundle | Remains a retrieval envelope. Retrieval rank/score never becomes epistemic confidence. |
| Shadow DB | Remains an external rebuildable acceleration. It does not become a claim authority or required ledger backend. |
| Graph-outcome programme | Remains authoritative for evaluating agent action and final graph state before any write-adjacent work. |

## Core architecture

```text
canonical graph or approved source revision
                |
                v
        source-bound observation
                |
                v
  immutable epistemic event ledger (external)
                |
                v
 deterministic reducer and materialized projection
                |
                v
 read-only explanation and future policy consumers
```

The ledger is append-only. The projection is disposable. A complete rebuild
must reproduce the same canonical projection bytes from the same ordered event
set, reducer version, policy revision, and source bindings.

The ledger is a new bounded subsystem. It must not overload P0 evidence
storage, Shadow tables, or canonical Markdown properties because those surfaces
have different lifecycle, privacy, and authority rules.

## Authority and storage rules

1. Every event is scoped to one private graph identity and one source binding.
2. A source binding contains only opaque identifiers and revision digests in the
   public contract.
3. The ledger is external to the graph and external to Shadow DB.
4. No event is accepted without a recognized schema version and exact key set.
5. A materialized projection is never an authority for a graph write.
6. A missing, malformed, oversized, or unreplayable ledger disables only
   epistemic features; baseline graph reads and retrieval remain independent.
7. A deleted external ledger removes only derived state. It cannot alter
   canonical graph content or be presented as a correction of user knowledge.
8. Strict Read Only handling must be specified separately before any runtime
   writer exists. A read-only explanation consumer must never create, repair, or
   append a ledger.

For v0, graph scope uses `local_random_scope_v1`: a canonical lowercase UUIDv4
stored only in a private, permissions-restricted graph-to-scope binding record
outside the graph. Events carry
`local_random_scope_v1:<uuidv4>`, never a graph path or a path-derived digest.
Moving or restoring a graph creates a new scope; reattachment requires a later
explicit migration and verification contract. This adopts the existing
[`GraphScopeRefV1`](../../quality/HUMAN_GOVERNED_ADAPTIVE_RETRIEVAL_PROGRAMME_2026-08-16.md#graphscoperefv1)
direction and keeps the current path-derived Shadow/cache identity out of a
durable event contract.

## Proposed package boundary

The eventual implementation should be isolated below `src/memory/epistemic/`:

```text
src/memory/epistemic/
  __init__.py          public, minimal exports
  models.py            frozen closed-schema event/value objects
  canonical.py         canonical JSON bytes and identity validation
  location.py          external containment and private graph scoping
  ledger.py            append-once, lock, fsync, bounded replay
  reducer.py           pure event-to-projection reducer
  explanation.py       read-only deterministic explanation model
  errors.py            closed content-free error vocabulary
```

This is a future implementation boundary, not a request to create these files
now. It preserves the current clean-architecture direction: graph remains the
domain source; the memory layer owns derived contracts; CLI, MCP, daemon, and
UI remain thin consumers when and only when later scopes authorize them.

## v0 vocabulary

### Claim

A claim is a normalized, graph-scoped assertion with an opaque stable identity.
It contains no raw source text in its portable/public representation.

Required conceptual fields:

```text
claim_id             SHA-256 opaque identity
graph_scope_id       private graph-scoped identifier
assertion_digest     SHA-256 of canonical private assertion representation
assertion_kind       bounded identifier, for example relation
observed_at          UTC time source material was observed
recorded_at          copied from the introducing claim_proposed event
valid_time           optional [from, to) interval about represented world
```

`claim_id` must not be treated as a universal cross-graph identity. A claim can
be re-identified only by an explicit future portability contract.

### Evidence link

An evidence link connects one source-bound event to one claim. Its relation is
one of:

```text
supports
challenges
contextualizes
```

v0 has no numeric weight. A relation says what an event means to an assessment
policy; it does not quantify independent evidential strength.

### Assessment

An assessment is a policy-versioned interpretation of current evidence. It is
distinct from both evidence and claim content.

Required conceptual fields:

```text
policy_id            identifier matching ^[a-z][a-z0-9_.-]{0,63}$
policy_revision      lowercase 64-character SHA-256 policy digest
assessment_kind      exactly evidence_relation_presence_v0
assessment_value     one closed qualitative classification
reduced_through      final event ID in this reduction, or null for no events
```

`evidence_relation_presence_v0` has one closed, qualitative domain. It is not
a scalar, ranking, or confidence scale. Its permitted values are:

```text
insufficient_evidence
supported
challenged
conflicted
```

Its complete v0 policy is fixed: no `supports` or `challenges` link yields
`insufficient_evidence`; one or more support links and no challenge link yields
`supported`; one or more challenge links and no support link yields
`challenged`; one or more of both yields `conflicted`. `contextualizes` links
do not change this classification. Policy implementations may not add weights,
thresholds, source reliability, or a hidden tie-breaker under the same
`policy_revision`.

No decimal confidence is permitted in v0. A future calibrated confidence model
requires a separate specification covering data, calibration method, error
bounds, update semantics, and user-facing interpretation.

### Status

Status is procedural and user-governed, not statistical. The v0 vocabulary is:

```text
proposed
supported
user_confirmed
challenged
superseded
rejected
```

The reducer derives `supported` and `challenged` only from declared event rules.
`user_confirmed` and `rejected` require explicit human-feedback event types.
`superseded` requires an explicit replacement claim reference. A later event
never destroys prior history.

### Revision edge

Two edge families are needed:

```text
depends_on          this claim's interpretation relies on another claim
supersedes          this claim replaces an earlier interpretation
```

`depends_on` is an explanation and invalidation surface, not a proof that a
claim logically follows from another claim. v0 must reject self-edges and
cycles in `supersedes`. Dependency cycles are rejected in v0 to keep replay and
explanation bounded; a later graph algorithm would require separate proof.

## Event contract

Every v0 event is immutable, closed-schema, canonical JSON. It has:

```text
schema_version       exactly epistemic-event.v0
graph_scope_id       private graph-scoped identifier
event_type           one bounded value
recorded_at          normalized UTC timestamp
actor_kind           system | human
source_refs          non-empty sorted opaque revision-pinned references
payload              exact event-type payload
```

`event_id` is a derived property, never a field inside the event payload. It is
the SHA-256 of canonical event bytes containing only the fields listed above.
If a storage envelope stores an `event_id` beside the event, the reader must
recompute and compare it before accepting the record. This avoids a circular
hash preimage.

`graph_scope_id` exactly matches
`^local_random_scope_v1:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.
`source_refs` has one to 32 unique `EvidenceRef`-shaped values sorted by
`source_kind, source_id, revision_digest`; each value uses the existing bounded
identifier and digest grammar. v0 accepts exactly these `source_kind` values:
`graph-block` for one canonical block revision, `p0-evidence-event` for one
existing P0 evidence event, `human-feedback` for one explicit retained feedback
record, and `synthetic-fixture` for test-only fixtures. A runtime ledger must
reject `synthetic-fixture`; that kind is permitted only in isolated tests. New
source kinds require a later schema version, not an unannounced policy change.
`valid_time`, when present in a
`claim_proposed` payload, is either `null` or exactly `{from, to}`, where
`from` is a UTC timestamp and `to` is either a later UTC timestamp or `null`.

The allowed event types are intentionally small:

| Event type | Purpose | Exact payload keys |
| --- | --- | --- |
| `claim_proposed` | Introduce one proposed claim. | `claim_id`, `assertion_digest`, `assertion_kind`, `observed_at`, `valid_time` |
| `evidence_linked` | Attach one source-bound reference with declared relation. | `claim_id`, `evidence_ref`, `relation` |
| `claim_confirmed_by_human` | Record explicit human confirmation. | `claim_id`, `feedback_ref` |
| `claim_challenged_by_human` | Record explicit human challenge. | `claim_id`, `feedback_ref` |
| `claim_rejected_by_human` | Record explicit human rejection. | `claim_id`, `feedback_ref` |
| `claim_superseded` | Replace an interpretation without deleting it. | `claim_id`, `replacement_claim_id` |
| `claim_dependency_declared` | Declare one review/invalidation dependency. | `claim_id`, `depends_on_claim_id` |

`evidence_ref` and `feedback_ref` use the closed `EvidenceRef` shape already
used by P0: `source_kind`, `source_id`, and `revision_digest`. They must also
appear in the event's `source_refs`. v0 has no separate evidence registry and
does not perform external source resolution during replay; it validates the
opaque reference shape and preserves the declared binding. A later source
resolver is a separate feature and must not change v0 replay semantics.

`actor_kind` is exactly `system` or `human`. It is validated against the event
type: `human` is accepted only for the three explicit human-feedback events;
all other event types require `system`. v0 carries no principal identifier,
named context, agent identity, delegation depth, or inferred interaction data.
The `human-feedback` reference is the complete opaque binding available to the
reducer. A future consented identity/context contract must use a new schema
version, informed by the existing
[`FeedbackContextRefV1`](../../quality/HUMAN_GOVERNED_ADAPTIVE_RETRIEVAL_PROGRAMME_2026-08-16.md#feedbackcontextrefv1-and-namedcontextrefv1)
direction, rather than adding optional fields to v0.

No generic `metadata` field is allowed. Unknown fields, unknown event types,
unknown schema versions, duplicate event IDs, missing source references,
non-canonical ordering, invalid timestamps, or invalid graph scope all fail
closed.

## Canonicalization and identity

v0 must use the existing evidence-contract style:

- UTF-8 JSON;
- `ensure_ascii=True`;
- lexicographically sorted object keys;
- compact separators;
- exact closed key sets;
- normalized UTC timestamps ending in `Z`;
- lowercase 64-character SHA-256 digests;
- explicitly sorted lists where order has no semantic meaning.

`event_id` is SHA-256 of canonical event bytes with no embedded event-ID field.
Idempotency is by exact event ID; replaying the same event is a no-op. Similar
content with a different actor, source revision, timestamp, or relation is a
distinct event and must remain visible as such.

## Deterministic reducer

The reducer is pure. It receives one validated graph scope, one immutable
policy binding (`policy_id`, `policy_revision`), and validated events in
canonical total order. It returns either a projection or one content-free error.
The policy binding is part of the canonical projection bytes and every
explanation; it is not an event and does not depend on wall-clock time.

### Input ordering

Events sort by:

```text
recorded_at, event_id
```

An equal timestamp is resolved only by event ID. This gives a complete ordering
without relying on filesystem order or clock precision beyond normalized event
timestamps.

### Reducer rules

1. Verify all event bytes and event IDs before any projection is emitted.
2. Reject a ledger containing duplicate IDs with non-identical bytes.
3. Reject an event whose graph scope differs from the active ledger scope.
4. Create a claim only from `claim_proposed`.
5. Reject every later event that references an unknown claim.
6. Validate `evidence_ref` and `feedback_ref` shape without external source
   resolution, then record support/challenge/context links exactly as declared.
7. Derive `supported` only when support exists and no challenge exists.
8. Derive `challenged` only when challenge exists and no support exists.
9. Derive `assessment_value` exactly by the closed
   `evidence_relation_presence_v0` policy: no support/challenge is
   `insufficient_evidence`; support only is `supported`; challenge only is
   `challenged`; both is `conflicted`. Context-only links do not alter it.
10. Record `depends_on` only after validating distinct existing claims and an
    acyclic dependency relation.
11. Apply `superseded` only after validating distinct existing claims and an
    acyclic supersession relation.
12. Resolve status with this fixed precedence: an accepted supersession yields
    `superseded`; otherwise the latest human-status event by
    `recorded_at, event_id` yields `user_confirmed`, `challenged`, or
    `rejected`; otherwise derive `supported` or `challenged` from evidence; a
    claim with no support/challenge remains `proposed`. Evidence never overrides
    an explicit human status event.
13. Mark dependents as `needs_review` in the explanation projection when an
    upstream claim is challenged, rejected, or superseded. This is not automatic
    refutation.
14. Emit `policy_id`, `policy_revision`, `reduced_through`, and a deterministic
    projection digest over canonical projection bytes. `reduced_through` is
    `null` only for an empty ledger; otherwise it is the final validated event
    ID in canonical total order.

The initial reducer must not infer relation strength, truth, causal effect,
source reliability, or a numerical posterior. Any future update method is a new
policy revision and requires its own evaluation contract.

## Materialized projection and explanation

The projection is a local read model. It contains only the derived view needed
for a bounded explanation:

```text
claim_id
status
assessment
policy_id
policy_revision
reduced_through
source_revision_summary
supporting_event_ids
challenging_event_ids
supersession_path
dependent_claim_ids
projection_digest
```

An explanation must answer, without accessing raw vault text:

- Which policy and policy revision produced this assessment?
- Which source revisions and events support or challenge it?
- Does a later claim supersede it?
- Which dependent claims require review?
- Is the result current, unavailable, invalid, or incomplete?

An explanation must not claim that a statement is objectively true, expose
private payloads, or create/update the ledger while servicing a read.

## Storage, durability, and recovery design

The eventual ledger location must be graph-scoped and external, for example a
dedicated `epistemic/v0/` subtree under an already approved external cache root.
The exact path is deliberately deferred to implementation design because it
must be reconciled with current cache containment, permissions, Read Only, and
retention contracts.

Required durability properties:

- cross-process single-writer lock;
- no-follow protection and containment validation;
- complete-write loop plus `fsync` before success;
- bounded replay size;
- final torn-record recovery only when the interruption shape is provably
  bounded and separately specified;
- no in-place rewriting, compaction, or migration in v0;
- explicit fail-closed errors for corruption, oversized input, invalid event,
  unknown schema, and lock failure.

The v0 ledger maximum is 32 MiB measured from the single ledger file before an
append; an append that would reach or exceed that limit fails before any write.
v0 has no automatic expiry, pruning, compaction, or in-place migration. It
retains all accepted events until an explicitly authorized future retention or
deletion feature defines user-facing semantics. This fixed cap bounds replay
without silently inheriting the P0 archive's sparse-event policy.

The P0 evidence archive is a strong implementation precedent, but v0 must not
inherit its limits or retention semantics without explicit acceptance. The
external-ledger delivery is **NO-GO** until a focused recovery contract defines
the exact torn-final-record shape, bounded truncation procedure, fsync ordering,
and failure evidence; no implementation may infer it from P0 behaviour.

## Privacy, security, and consent

The implementation plan must include tests for each rule:

1. Events store opaque references and digest-bound revisions, never raw vault
   content, prompts, absolute paths, credentials, or arbitrary model output.
2. Human feedback is explicit, actor/context-scoped, and never inferred from
   clicks, dwell time, or interaction frequency.
3. A user can inspect what categories are retained before feedback is enabled.
4. Export/delete/retention semantics are not introduced until a separate
   feedback delivery defines their exact behaviour and recovery implications.
5. Public fixtures use synthetic non-sensitive examples only.
6. Errors are content-free and do not leak filesystem topology or event payloads.
7. No read API opens a writer, repairs a damaged ledger, or mutates external
   derived state.

## Testing and qualification requirements

v0 implementation may begin only with focused tests written before code. The
minimum test matrix is:

| Area | Required cases |
| --- | --- |
| Schema | Exact accepted keys; unknown field rejection; invalid type/version/timestamp/digest/source-kind rejection. |
| Canonical bytes | Stable JSON bytes, ID, list ordering, and projection digest across repeated runs. |
| Event ledger | Idempotent duplicate, malformed record, partial final write, lock contention, bounded replay, and fsync failure handling. |
| Reducer | Support-only, challenge-only, conflict, unknown claim, invalid evidence reference, human confirmation/challenge/rejection precedence, supersession, dependency review, cycles, policy binding, and same-time ordering. |
| Privacy | Raw content/path/prompt/credential rejection and content-free error assertions. |
| Authority | No canonical graph write, no Shadow opening, no read-side ledger creation, and baseline reads remain available on epistemic failure. |
| Recovery | Empty rebuild, replay equivalence, corrupted ledger fail-closed, and deliberate deletion affects only derived state. |
| Evaluation | Synthetic fixtures, frozen policy revision, abstention/contradiction measures, and graph-outcome controls before any influence on actions. |

Passing unit tests proves only the recorded schema and reducer. It does not
prove calibration, usefulness, safe agent behaviour, platform qualification, or
interoperability with another implementation.

## Delivery decomposition

The work must be split into independently reviewable deliveries:

1. **Schema-only contract.** Models, canonicalization, synthetic fixtures, and
   negative tests. No storage, API, or runtime integration.
2. **External ledger and replay.** Bounded durable storage and pure reducer.
   No daemon, retrieval, or user feedback surface.
3. **Read-only explanation.** Projection reader and explanation DTOs. No
   automatic action, ranking change, or write path.
4. **Explicit feedback design.** Consent, actor/context, retention,
   export/delete, and rollback specification before any feedback events are
   accepted at runtime.
5. **Evaluation gate.** Frozen controls demonstrate whether bounded use is
   justified or the feature remains research-only.
6. **Neutral externalization.** Only after independent consumption: extract a
   schema, examples, and conformance suite into a neutral RFC repository.

Each delivery requires its own issue, narrow branch, tests, review, and
qualification decision. A NO-GO result is valid completion for any delivery.

## Acceptance criteria for this design

This design is ready to become an implementation plan only when a reviewer
accepts all of the following:

- canonical authority remains unchanged;
- P0 evidence/archive and Shadow contracts are not expanded implicitly;
- status, assessment, confidence, provenance, and time remain distinct;
- all v0 events have closed schemas, deterministic identity, and explicit
  source binding;
- replay/recovery and content-free failure rules are specified enough to test;
- no event or explanation creates a write path;
- privacy/consent requirements are not deferred behind a generic metadata field;
- external standard work remains conditional on independent use and
  conformance evidence.

## Decisions fixed for v0

1. `graph_scope_id` uses the private `local_random_scope_v1` contract above;
   current path-derived cache identities are forbidden.
2. `actor_kind` is closed to `system` and `human`; v0 has no identity or context
   fields and does not infer feedback.
3. `proposed`, `supported`, and evidence-derived `challenged` are reducer
   results; `user_confirmed`, human-originated `challenged`, `rejected`, and
   `superseded` require their named explicit event. `needs_review` is only an
   explanation marker, never a status.
4. The ledger is capped at 32 MiB with no automatic retention action in v0.

## Deferred decisions

1. Which minimal synthetic corpus can test temporal supersession and dependency
   review without asserting a real-world truth model?
2. What PROV-O mapping is useful enough to include in v0 rather than document as
   a later interoperability profile?

No code, issues, environment variables, GitHub rules, or external repository
may be created until this design is reviewed and explicitly approved.
