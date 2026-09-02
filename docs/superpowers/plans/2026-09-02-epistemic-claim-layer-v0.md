# Epistemic Claim Layer v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a local, bounded, source-bound Epistemic Claim Layer v0 whose
immutable events replay into deterministic, read-only explanations without
changing Markdown authority, P0 evidence contracts, or Shadow DB.

**Architecture:** A new, isolated `src.memory.epistemic` package owns closed
event models, canonical bytes, a pure reducer, external ledger containment, and
read-only explanation DTOs. The delivery is split so schema/reducer work proves
the contract before any durable storage exists; a separately reviewed recovery
contract is mandatory before the external writer is implemented. No existing
CLI, MCP, daemon, UI, retrieval ranking, or write path consumes the layer in
v0.

**Tech Stack:** Python 3.12+, standard-library `dataclasses`, `hashlib`,
`json`, `os`, `pathlib`, `uuid`, existing platform locks and filesystem safety
helpers, pytest, Ruff, mypy, and uv. No new dependency.

**Spec:** [`docs/superpowers/specs/2026-09-02-epistemic-claim-layer-v0-design.md`](../specs/2026-09-02-epistemic-claim-layer-v0-design.md)

## Global Constraints

- The canonical Logseq Markdown graph remains the semantic source of record.
- The ledger is derived, external to the graph and Shadow DB, append-only, and
  disposable; it can never authorize a graph write.
- Do not change `EvidenceEvent`, `EvidenceArchive`, `P0EvidencePacket`,
  `MemoryCandidate`, `RecallBundle`, or `memory_procedures` fields.
- Events contain only closed schema fields, opaque bounded references, revision
  digests, and normalized timestamps. They never contain raw vault text,
  prompts, credentials, absolute paths, model output, or generic metadata.
- `graph_scope_id` is exactly `local_random_scope_v1:<uuidv4>` and is bound to a
  resolved graph only in a private external binding record. Never derive it
  from a graph path or reuse Shadow's path-derived cache identity.
- v0 source kinds are exactly `graph-block`, `p0-evidence-event`,
  `human-feedback`, and test-only `synthetic-fixture`; runtime rejects the
  fixture kind.
- `actor_kind` is `system` except for explicit human-feedback event variants,
  which require `human`. v0 has no principal, context, agent identity,
  delegation, or inferred-interaction field.
- The assessment policy is exactly `evidence_relation_presence_v0`; it has no
  numeric confidence, weights, thresholds, reliability model, or hidden
  tie-breaker.
- A read-only caller never creates, repairs, appends, or deletes a ledger.
  Strict Read Only writer semantics remain a later, separately approved slice.
- The single ledger file maximum is 32 MiB. An append that would reach or exceed
  it fails before mutation. v0 has no expiry, pruning, compaction, or migration.
- No external-ledger code begins until the focused torn-record recovery contract
  in Task 3 is reviewed and accepted.
- New or changed symbols require current upstream impact analysis before edits;
  every commit requires `detect_changes()` and direct diff review.
- Each task is a separate narrow branch/PR from current `main`; do not stack
  implementation on an unmerged unrelated change. Commit, push, PR, merge,
  release, and announcement require separate authorization.
- Public files use English and maintainer-only attribution. No public artifact
  names an assistant, model, or tool.

## Delivery Topology

| Delivery | Scope | Merge gate | Explicitly excluded |
| --- | --- | --- | --- |
| A | Schema, canonical identity, fixtures, pure reducer | focused tests, lint, types, docs | filesystem, APIs, product integration |
| B | Recovery contract and storage threat model | maintainer design approval | runtime writer |
| C | Private location and append-only ledger | crash, lock, containment, cap tests | CLI/MCP/daemon/UI |
| D | Read-only projection/explanation facade | determinism and no-write tests | automatic action or ranking |
| E | Documentation, evidence, evaluation and release classification | docs and full CI | external standard proposal |

Each delivery is independently valuable. A failed safety or recovery gate is a
valid NO-GO outcome and stops the next delivery without weakening previous
boundaries.

## File Structure

| Path | Responsibility |
| --- | --- |
| `src/memory/epistemic/errors.py` | Closed, content-free exception vocabulary. |
| `src/memory/epistemic/models.py` | Frozen event, reference, policy, and projection value objects with exact validation. |
| `src/memory/epistemic/canonical.py` | Canonical ASCII JSON, SHA-256 identities, and projection digest. |
| `src/memory/epistemic/reducer.py` | Pure, policy-bound event-to-projection reduction. |
| `src/memory/epistemic/location.py` | Private graph-scope binding and contained external paths. |
| `src/memory/epistemic/ledger.py` | Single-writer append/replay only after Task 3 approval. |
| `src/memory/epistemic/explanation.py` | Read-only DTOs; never imports writer/location creation paths. |
| `tests/test_epistemic_*.py` | Synthetic, deterministic contract, storage, and authority coverage. |
| `tests/fixtures/epistemic/v0/` | Non-sensitive canonical event and projection fixtures. |
| `docs/superpowers/specs/...ledger-recovery...md` | Exact recovery and mutation contract required before Task 4. |
| `docs/knowledge/architecture/epistemic-memory.md` | Public architecture status and later evidence links. |

---

### Task 1: Delivery A — Closed models and canonical identity

**Files:**

- Create: `src/memory/epistemic/__init__.py`
- Create: `src/memory/epistemic/errors.py`
- Create: `src/memory/epistemic/models.py`
- Create: `src/memory/epistemic/canonical.py`
- Create: `tests/test_epistemic_models.py`
- Create: `tests/test_epistemic_canonical.py`
- Create: `tests/fixtures/epistemic/v0/events.json`

**Interfaces:**

- Consumes: `src.memory.evidence_models.EvidenceRef` only as the closed opaque
  reference shape; no archive or storage imports.
- Produces: `EpistemicEvent`, `AssessmentPolicy`, `ClaimProjection`,
  `EpistemicProjection`, `EpistemicContractError`, `parse_event()`,
  `canonical_event_bytes()`, `event_id_for()`, and `projection_digest_for()`.

- [ ] **Step 1: Write failing model tests**

Create fixed test data with lowercase 64-character digests and one canonical
scope such as `local_random_scope_v1:123e4567-e89b-42d3-a456-426614174000`.
Cover each event type, exact payload keys, source-reference sorting, UUIDv4
scope rejection, invalid timestamp rejection, and actor/event mismatch:

```python
def test_event_identity_is_derived_not_embedded() -> None:
    event = _claim_proposed()
    payload = event.to_dict()
    assert "event_id" not in payload
    assert event_id_for(event) == event_id_for(parse_event(payload))

def test_human_actor_is_rejected_for_non_feedback_event() -> None:
    with pytest.raises(EpistemicContractError, match="invalid_actor_kind"):
        parse_event({**_claim_proposed().to_dict(), "actor_kind": "human"})

def test_schema_accepts_test_only_fixture_reference() -> None:
    event = parse_event(_event_with_source_kind("synthetic-fixture"))
    assert event.source_refs[0].source_kind == "synthetic-fixture"
```

Also parameterize unknown fields, missing fields, duplicate source references,
unsorted references, invalid `valid_time`, unknown event type, `event_id` in an
input payload, raw-content-like keys, and every invalid source kind. Keep
`synthetic-fixture` schema-valid for isolated fixtures; runtime admission is
tested separately in Task 5.

- [ ] **Step 2: Run focused tests and confirm RED**

Run:

```bash
rtk uv run pytest tests/test_epistemic_models.py tests/test_epistemic_canonical.py -q
```

Expected: import failure because `src.memory.epistemic` does not exist.

- [ ] **Step 3: Implement the closed contract minimally**

Define the envelope exactly as the approved specification requires. Use frozen,
slotted dataclasses and constructors that accept only mappings with exact keys.
`EpistemicEvent.to_dict()` returns only:

```python
{
    "schema_version": "epistemic-event.v0",
    "graph_scope_id": ...,
    "event_type": ...,
    "recorded_at": ...,
    "actor_kind": ...,
    "source_refs": [...],
    "payload": {...},
}
```

Make `canonical_event_bytes()` serialize `to_dict()` using UTF-8,
`ensure_ascii=True`, sorted keys, compact separators, and no newline. Compute
the identity as lowercase SHA-256 of those bytes. Do not add a storage envelope,
filesystem access, wall clock, or automatic ID generation.

- [ ] **Step 4: Add fixed synthetic fixture and passing tests**

Store only the canonical event list and expected IDs/digest in
`tests/fixtures/epistemic/v0/events.json`. Assert byte-for-byte stability and
that changed source revision, actor, relation, timestamp, or payload changes
the event ID.

Run:

```bash
rtk uv run pytest tests/test_epistemic_models.py tests/test_epistemic_canonical.py -q
rtk uv run ruff check src/memory/epistemic tests/test_epistemic_models.py tests/test_epistemic_canonical.py
rtk uv run mypy src/memory/epistemic
```

Expected: all pass.

- [ ] **Step 5: Inspect impact and commit Delivery A**

Run the repository impact query for each new public symbol, then
`detect_changes()` against current `main`; verify that only the Task 1 files
and generated documentation inventory differ. Commit only after direct diff
review:

```bash
rtk git add src/memory/epistemic tests/test_epistemic_models.py tests/test_epistemic_canonical.py tests/fixtures/epistemic/v0/events.json
rtk git commit -m "feat(memory): add epistemic event contract"
```

### Task 2: Delivery A — Pure reducer and rebuildable projection

**Files:**

- Modify: `src/memory/epistemic/models.py`
- Create: `src/memory/epistemic/reducer.py`
- Modify: `src/memory/epistemic/__init__.py`
- Create: `tests/test_epistemic_reducer.py`
- Create: `tests/fixtures/epistemic/v0/projection.json`

**Interfaces:**

- Consumes: validated `tuple[EpistemicEvent, ...]`, `AssessmentPolicy`, and
  canonical helpers from Task 1.
- Produces: `reduce_events(events, *, graph_scope_id, policy) -> EpistemicProjection`.
  `AssessmentPolicy` must be exactly
  `policy_id="evidence_relation_presence_v0"` plus a pinned 64-character
  `policy_revision`.

- [ ] **Step 1: Write failing reducer tests**

Use synthetic event sequences to cover exact ordering and every state rule:

```python
def test_reducer_is_byte_stable_independent_of_input_order() -> None:
    projection_a = reduce_events(_events(), graph_scope_id=_SCOPE, policy=_POLICY)
    projection_b = reduce_events(tuple(reversed(_events())), graph_scope_id=_SCOPE, policy=_POLICY)
    assert projection_a == projection_b
    assert projection_a.projection_digest == projection_b.projection_digest

def test_latest_human_event_overrides_evidence_but_not_supersession() -> None:
    projection = reduce_events(_support_then_human_rejection_then_supersession(), graph_scope_id=_SCOPE, policy=_POLICY)
    assert projection.claims[_CLAIM].status == "superseded"

def test_empty_rebuild_has_null_reduced_through() -> None:
    projection = reduce_events((), graph_scope_id=_SCOPE, policy=_POLICY)
    assert projection.reduced_through is None
```

Include support-only, challenge-only, contextual-only, conflict, explicit human
confirmation/challenge/rejection, missing claim reference, graph-scope mismatch,
dependency/supersession self-edge, dependency cycle, supersession cycle,
duplicate non-identical IDs, and same-time ordering by event ID.

- [ ] **Step 2: Run reducer tests and confirm RED**

Run:

```bash
rtk uv run pytest tests/test_epistemic_reducer.py -q
```

Expected: FAIL because `reduce_events` is absent.

- [ ] **Step 3: Implement reduction without side effects**

Sort validated events by `(recorded_at, event_id_for(event))`. Reject any invalid
event before emitting a projection. Maintain only in-memory claim, relationship,
and edge state. Apply status precedence exactly:

```text
accepted supersession
  > latest human confirmation/challenge/rejection by recorded_at,event_id
  > support/challenge evidence
  > proposed
```

Compute assessment as `insufficient_evidence`, `supported`, `challenged`, or
`conflicted` from relation presence only. Mark dependent claims
`needs_review=True` in their explanation data when an upstream claim is
challenged, rejected, or superseded; never convert this marker into refutation.
Return canonical, sorted claim projections carrying `policy_id`,
`policy_revision`, `reduced_through`, and `projection_digest`.

- [ ] **Step 4: Run deterministic and negative tests**

Run:

```bash
rtk uv run pytest tests/test_epistemic_reducer.py tests/test_epistemic_models.py tests/test_epistemic_canonical.py -q
rtk uv run ruff check src/memory/epistemic tests/test_epistemic_reducer.py
rtk uv run mypy src/memory/epistemic
```

Expected: all pass; no test creates a file or consults wall-clock time.

- [ ] **Step 5: Inspect impact and commit Delivery A reducer**

Review `detect_changes()` and the fixture projection against the specification.
Commit only the Task 2 files:

```bash
rtk git add src/memory/epistemic tests/test_epistemic_reducer.py tests/fixtures/epistemic/v0/projection.json
rtk git commit -m "feat(memory): reduce epistemic claim events"
```

### Task 3: Delivery B — Focused ledger recovery contract

**Files:**

- Create: `docs/superpowers/specs/2026-09-02-epistemic-ledger-recovery-design.md`
- Modify: `docs/knowledge/architecture/epistemic-memory.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**

- Consumes: the v0 event bytes and 32 MiB bound from Tasks 1–2, plus existing
  no-follow/lock safety patterns as implementation precedent only.
- Produces: a reviewed, testable definition of file layout, writer lock,
  append sequence, `fsync` sequence, valid unterminated final record, bounded
  torn final record, unrecoverable corruption, and content-free error mapping.

- [ ] **Step 1: Write the recovery specification before storage code**

Define exactly one JSONL record per canonical event byte plus newline. State
whether the final valid no-newline record is retained, which malformed final
record shapes may be truncated, the maximum truncatable byte count, and the
required `fsync` operations after truncation and append. Define explicit errors
for a symlink, non-regular file, oversized file, malformed non-final line,
unrecoverable tail, lock failure, short write, and `fsync` failure.

The specification must prohibit: scanning outside the private ledger directory,
repair on read, truncation of any complete/non-final record, replacement files,
compaction, and implicit deletion.

- [ ] **Step 2: Add a recovery truth table**

Include these exact cases with state, operation, outcome, and postcondition:

| Input tail | Operation | Required result |
| --- | --- | --- |
| complete JSON + newline | append | retain all prior bytes; append one record |
| complete JSON without newline | append | retain record; insert one newline; append |
| malformed final JSON beginning with `{` within bound | explicit writer recovery | truncate final fragment, fsync, then append |
| malformed final bytes outside bound | append | fail closed; no truncation |
| malformed non-final line | read or append | fail closed; no mutation |
| valid ledger at/over 32 MiB | append | fail before mutation |

- [ ] **Step 3: Run documentation gates and obtain design approval**

Run:

```bash
rtk make docs-inventory-md
rtk make docs-check
rtk make docs-audit
rtk git diff --check
```

Expected: all pass. Stop here for explicit maintainer review and approval. Do
not create `location.py` or `ledger.py` until the recovery contract is accepted.

- [ ] **Step 4: Commit the approved recovery contract**

After approval and diff review:

```bash
rtk git add docs/superpowers/specs/2026-09-02-epistemic-ledger-recovery-design.md docs/knowledge/architecture/epistemic-memory.md docs/knowledge/inventory.json docs/knowledge/inventory.md
rtk git commit -m "docs(memory): define epistemic ledger recovery"
```

### Task 4: Delivery C — Private scope binding and contained location

**Files:**

- Create: `src/memory/epistemic/location.py`
- Create: `tests/test_epistemic_location.py`
- Modify: `src/memory/epistemic/errors.py`
- Modify: `src/memory/epistemic/__init__.py`

**Interfaces:**

- Consumes: approved Task 3 recovery contract and existing external-cache/no-follow
  safety helpers.
- Produces: `EpistemicLedgerLocation`,
  `resolve_epistemic_ledger_location(graph_root, *, env=None)`, and
  `load_or_create_scope_binding(location) -> str` for writer-only use.

- [ ] **Step 1: Write failing location tests**

Create temporary graph/cache roots. Assert a writer creates one random UUIDv4
binding with mode `0600`, repeated resolution preserves it, two graph roots get
different scopes, and path moves do not silently reuse a binding. Assert read
location resolution never creates directories or binding files. Parameterize
symlinked cache root, symlinked binding, cache escape, non-directory root, and
world-readable binding rejection.

- [ ] **Step 2: Run location tests and confirm RED**

Run:

```bash
rtk uv run pytest tests/test_epistemic_location.py -q
```

Expected: FAIL because location helpers are absent.

- [ ] **Step 3: Implement writer-only location creation**

Use a dedicated external cache subtree such as
`<approved-cache-root>/epistemic/v0/<scope-namespace>/`. Validate containment
before every open, reject symlinks/non-regular files, use the existing
cross-process lock primitive, and atomically persist only the random scope
value. Expose a separate read resolver that returns absence without creating
anything.

- [ ] **Step 4: Verify and commit**

Run:

```bash
rtk uv run pytest tests/test_epistemic_location.py -q
rtk uv run ruff check src/memory/epistemic tests/test_epistemic_location.py
rtk uv run mypy src/memory/epistemic
```

Then run impact and change detection. Commit only Task 4 files:

```bash
rtk git add src/memory/epistemic tests/test_epistemic_location.py
rtk git commit -m "feat(memory): bind private epistemic graph scopes"
```

### Task 5: Delivery C — Append-only ledger and replay

**Files:**

- Create: `src/memory/epistemic/ledger.py`
- Create: `tests/test_epistemic_ledger.py`
- Modify: `src/memory/epistemic/errors.py`
- Modify: `src/memory/epistemic/__init__.py`

**Interfaces:**

- Consumes: `EpistemicLedgerLocation`, `EpistemicEvent`, canonical event bytes,
  and the approved recovery truth table.
- Produces: `EpistemicLedger`, `EpistemicAppendResult`,
  `EpistemicLedger.append(event)`, and `EpistemicLedger.events()`.

- [ ] **Step 1: Write failing storage tests from the approved truth table**

Test idempotent append, independent append processes, complete no-newline tail,
bounded torn final record, corruption outside the final record, no-follow
rejection, write loop short-write simulation, `fsync` failure simulation, read
without repair, 32 MiB pre-write limit, and runtime rejection of an otherwise
schema-valid event that references `synthetic-fixture`. Include this authority
test:

```python
def test_read_only_replay_never_creates_or_repairs_state(tmp_path: Path) -> None:
    location = _missing_location(tmp_path)
    assert EpistemicLedger.read_existing(location).events() == ()
    assert not location.directory.exists()
```

- [ ] **Step 2: Run storage tests and confirm RED**

Run:

```bash
rtk uv run pytest tests/test_epistemic_ledger.py -q
```

Expected: FAIL because `EpistemicLedger` is absent.

- [ ] **Step 3: Implement exactly the approved append/replay protocol**

`append()` alone may create a directory and acquire the writer lock. It must
validate an event before acquiring durable state, inspect size before write,
replay enough validated IDs for idempotency, execute only the approved tail
recovery under lock, write all bytes, and `fsync` before reporting success.
`events()` is read-only: it never creates paths, truncates tails, or repairs
records. It either returns validated events or raises a content-free error.

- [ ] **Step 4: Run storage, process, and full local checks**

Run:

```bash
rtk uv run pytest tests/test_epistemic_ledger.py tests/test_epistemic_location.py tests/test_epistemic_reducer.py -q
rtk uv run ruff check src/memory/epistemic tests/test_epistemic_ledger.py
rtk uv run mypy src/memory/epistemic
rtk make ci
```

Expected: all pass. If a failure involves recovery ambiguity, preserve the
fixture and stop; do not expand truncation or weaken a no-follow check.

- [ ] **Step 5: Inspect impact and commit ledger delivery**

Run `detect_changes()` against current `main`, inspect affected execution flows,
and commit only Task 5 files:

```bash
rtk git add src/memory/epistemic tests/test_epistemic_ledger.py
rtk git commit -m "feat(memory): persist epistemic event ledger"
```

### Task 6: Delivery D — Read-only explanation facade

**Files:**

- Create: `src/memory/epistemic/explanation.py`
- Create: `tests/test_epistemic_explanation.py`
- Modify: `src/memory/epistemic/__init__.py`
- Modify: `docs/knowledge/architecture/epistemic-memory.md`

**Interfaces:**

- Consumes: an already loaded `EpistemicProjection`; it must not accept a graph
  path, cache root, ledger location, or writer.
- Produces: `ClaimExplanation`, `explain_claim(projection, claim_id)`, and
  `explain_projection_state(projection)`.

- [ ] **Step 1: Write failing read-only explanation tests**

Assert explanations return only claim status, assessment, policy binding,
source-revision summary, supporting/challenging IDs, supersession path,
dependent IDs, and `needs_review`. Assert unknown claims return a content-free
result or closed error. Monkeypatch filesystem mutation primitives and assert
they are never called by any explanation function.

- [ ] **Step 2: Run explanation tests and confirm RED**

Run:

```bash
rtk uv run pytest tests/test_epistemic_explanation.py -q
```

Expected: FAIL because the facade is absent.

- [ ] **Step 3: Implement a projection-only facade**

Make explanation construction a pure conversion from projection values. Never
import `ledger`, `location`, `os`, `pathlib`, `sqlite3`, a parser, Shadow, or a
graph writer. Do not state that a claim is true; describe only recorded policy,
source-bound events, supersession, and incompleteness.

- [ ] **Step 4: Verify no-write boundary and commit**

Run:

```bash
rtk uv run pytest tests/test_epistemic_explanation.py tests/test_epistemic_reducer.py -q
rtk uv run ruff check src/memory/epistemic tests/test_epistemic_explanation.py
rtk uv run mypy src/memory/epistemic
rtk make docs-check
```

Review imports and `detect_changes()`, then commit:

```bash
rtk git add src/memory/epistemic tests/test_epistemic_explanation.py docs/knowledge/architecture/epistemic-memory.md
rtk git commit -m "feat(memory): explain epistemic projections"
```

### Task 7: Delivery E — Qualification, documentation, and bounded completion

**Files:**

- Modify: `docs/knowledge/architecture/epistemic-memory.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `CHANGELOG.md` only if the `matryca-changelog` decision gate requires it
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Create: `docs/quality/EPISTEMIC_CLAIM_LAYER_V0_QUALIFICATION.md`

**Interfaces:**

- Consumes: terminal tests and exact commits from Deliveries A–D.
- Produces: evidence-bound scope/status report that distinguishes static tests,
  durable storage tests, read-only behavior, and unproven action usefulness.

- [ ] **Step 1: Write the qualification report from exact evidence**

Record exact branch/commit, source files, test commands, test counts, supported
event types, source-kind domain, 32 MiB bound, recovery contract status, and
known exclusions. Explicitly state that v0 does not prove calibration, truth,
agent usefulness, cross-implementation interoperability, Logseq DB support,
autonomous action safety, or external-standard readiness.

- [ ] **Step 2: Run documentation and repository qualification**

Run:

```bash
rtk make docs-inventory-md
rtk make docs-check
rtk make docs-audit
rtk make ci
rtk git diff --check
```

Expected: all pass. Treat a failing durability, no-write, or privacy test as a
NO-GO for publication, not as justification to relax the contract.

- [ ] **Step 3: Apply the changelog decision gate**

Use `matryca-changelog` after the final diff is known. If the package exposes
new importable public runtime objects, add one concise `Unreleased` entry that
states the layer is derived and read-only. Otherwise record the documented
decision in the qualification report and leave `CHANGELOG.md` unchanged.

- [ ] **Step 4: Review scope and commit qualification documentation**

Run upstream impact analysis and `detect_changes()`; review every public
surface. Commit only the evidence/documentation files:

```bash
rtk git add docs/knowledge/architecture/epistemic-memory.md docs/quality/EVIDENCE_INDEX.md docs/quality/EPISTEMIC_CLAIM_LAYER_V0_QUALIFICATION.md docs/knowledge/inventory.json docs/knowledge/inventory.md CHANGELOG.md
rtk git commit -m "docs(memory): qualify epistemic claim layer v0"
```

If `CHANGELOG.md` was intentionally unchanged, omit it from `git add`.

## Final Acceptance Matrix

| Requirement | Evidence required |
| --- | --- |
| Canonical authority unchanged | Source and integration tests prove no Markdown/Shadow/P0 mutation or import expansion. |
| Deterministic events and projections | Fixed fixtures reproduce identical event IDs and projection digest after reordered input. |
| Privacy boundary | Negative tests reject raw-content-like fields; public fixtures are synthetic. |
| Status and assessment separation | Tests cover precedence, relation-presence assessment, and no numeric confidence. |
| Durable safety | Approved recovery contract plus exact lock, no-follow, cap, write-loop, fsync, and corruption tests. |
| Read-only explanations | Import and monkeypatch tests prove no path or writer mutation route. |
| Failure containment | Missing/corrupt ledger disables only epistemic features; baseline graph reads remain independent. |
| Scope honesty | Qualification report names all exclusions and makes no standard, DB, calibration, or action claim. |

## Execution Handoff

This plan is intentionally gated at Task 3. Start with Delivery A only after
the research anchor, v0 design, and this plan are committed and reviewed. Use
subagent-driven execution for the isolated tests and mechanical code slices;
retain architecture, recovery, privacy, authorization, integration, and final
evidence decisions centrally. Do not open issues, publish a standard, or add a
consumer integration merely because the schema and reducer pass.
