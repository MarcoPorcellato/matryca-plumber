---
type: ResearchSpike
title: Learn Agent Memory patterns for Matryca Plumber
description: Evidence-preserving memory contracts, retrieval views, context assembly and evaluation patterns assessed against Matryca Plumber.
source: https://github.com/hardness1020/learn-agent-memory
source_license: MIT
timestamp: 2026-08-10T00:00:00Z
status: research
audience: [maintainer, contributor, architect]
owner: retrieval-runtime
---

# Learn Agent Memory: ideas for Matryca Plumber

## Executive decision

`hardness1020/learn-agent-memory` is a design-and-teaching repository, not a
drop-in memory runtime. Its strongest contribution is a disciplined separation
between raw evidence, derived memory records, index views, context assembly and
evaluation. Those boundaries align with Matryca Plumber's Shadow DB model, but
the repository also describes capabilities that belong in Matryca Brain, ReMe or
another agent runtime rather than in Plumber.

Adopt the following ideas as vendor-neutral contracts and test scenarios:

1. scope is a mandatory access precondition, not a text filter;
2. raw events and evidence references are preserved separately from rebuildable
   views;
3. retrieval records carry typed provenance and explicit generation/version data;
4. stale, superseded, retracted and merely absent evidence are distinct states;
5. candidate channels remain independent and are fused through a stable contract;
6. context assembly is budgeted, contradiction-aware and framed as untrusted data;
7. metrics are computed from append-only observations, distinguish missing from
   zero, and have actions attached to their thresholds.

Do not copy its memory engine into Plumber. Plumber must remain a local,
read-oriented graph and retrieval boundary: Markdown is authoritative, Shadow DB
is derived, no model KV tensors are stored, and normal operation does not write
to the user's vault. Learning, write approval, consolidation and long-term
memory policy belong to a higher Brain/agent plane.

## Source and evidence quality

The source repository is MIT-licensed and was inspected at its `main` branch.
It contains ten self-contained sections with standard-library Python examples and
offline tests. All ten upstream section tests passed locally with `python3`.
The material is an educational reconstruction of mechanisms from other systems
and papers; it is useful as a design catalogue, not as independent benchmark
evidence for Matryca.

Primary source links:

- [Repository](https://github.com/hardness1020/learn-agent-memory)
- [Memory contract](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/01-memory-contract)
- [Event ledger](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/02-event-ledger)
- [Write policy](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/03-write-policy)
- [Typed memory](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/04-typed-memory)
- [Temporal resolution](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/05-temporal-resolution)
- [Consolidation](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/06-consolidation)
- [Index views](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/07-index-views)
- [Hybrid retrieval](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/08-hybrid-retrieval)
- [Context assembly](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/09-context-assembly)
- [Evaluation and governance](https://github.com/hardness1020/learn-agent-memory/tree/main/sections/10-evaluation-governance)

## What the source system teaches

### 1. A small memory contract protects replaceability

The first section exposes only `observe`, `recall` and `consolidate`, while
every record carries a frozen scope. The point is architectural: callers never
query a specific index directly, so indexes, stores and resolvers can be rebuilt
without changing the caller contract.

For Plumber, the equivalent is not a new memory engine. It is a typed retrieval
boundary in which every request has an opaque graph scope and every result is
returned through the existing graph search/read APIs. The scope should be
validated before cache lookup. A cache key that contains only a query and limit
is unsafe if the same process serves more than one graph.

### 2. The event ledger keeps evidence recoverable

The second section stores immutable events with `occurred_at` and
`recorded_at`, scope, event type and metadata. SQLite triggers reject update and
delete. Derived memories point back to event IDs, so an extraction mistake can
be corrected by replaying evidence.

Matryca already has a stronger Markdown source-of-truth rule than a memory
database: the vault is canonical and Shadow DB is disposable. The transferable
part is the provenance discipline, not an event store inside Shadow DB.

Recommended boundary:

```text
Logseq Markdown                 canonical human-owned evidence
        │
        ├── Shadow DB / BM25 / semantic sidecars   rebuildable views
        │
        └── optional Brain evidence ledger         agent/session evidence
```

Plumber may emit an immutable evidence reference in a retrieval envelope, but a
full conversation/tool ledger should be owned by Brain or ReMe. If an operator
later enables a local diagnostics ledger, it must be append-only, separately
scoped, opt-in, content-minimal and never required to rebuild Shadow DB.

### 3. Write decisions are typed and auditable

The write-policy section uses deterministic checks first, then an optional model
classifier, followed by a validator. Decisions are explicit:
`store`, `ignore`, `defer` and `require_approval`; rejections have reasons too.
Sensitive writes are checked before duplicate/near-duplicate rules, and a
deferred candidate is retained so consolidation can actually see it.

This is valuable for Brain's future memory-learning loop, but it is not a reason
to give Plumber autonomous write powers. Plumber can help by returning stable
evidence IDs and hashes that a higher plane can cite in a proposal. Any write
approval, candidate queue or memory mutation must remain outside the read-only
Plumber boundary.

### 4. Functional kind and epistemic status are different axes

The source distinguishes `episodic`, `semantic` and `procedural` memory from
`evidence`, `fact`, `preference`, `inference` and `opinion`. A record cannot be
created without a legal type, confidence and source event IDs. Procedures retain
their trigger condition instead of becoming generic advice.

Plumber's current Shadow memory tables are schema-only and not a shipped memory
write/read surface. The safe near-term adoption is pass-through metadata in
retrieval provenance: preserve block properties, source hashes and any existing
state labels without inventing epistemic labels from text. Brain may later map
those labels into a typed memory model.

### 5. Bitemporal resolution prevents silent history loss

The temporal section separates `valid_from`/`valid_to` (when a claim was true)
from `recorded_at`/`superseded_at` (when the system believed it). `SUPERSEDE`
means a fact was once true; `RETRACT` means the record was wrong. Neither
operation erases the historical row.

Plumber currently has file mtimes, sync timestamps and Shadow graph generations,
which are excellent cache-consistency signals but are not semantic validity
intervals. Do not overload `file_mtime_ns` with world time. A future Brain memory
plane should own bitemporal claim state; Plumber should expose source mtime,
graph generation and content hash so that plane can resolve time safely.

### 6. Consolidation is propose → validate → commit

The consolidation section handles compression, abstraction and procedure/skill
formation off the query hot path. A proposer can suggest a merge, but a
deterministic validator rejects unknown levels, empty content, missing sources,
closed sources, cross-scope sources and incompatible claim keys. Derived records
inherit the union of their evidence IDs and retain inference status. Rejections
are logged rather than swallowed.

This maps cleanly to a future Brain sleep-consolidation service, not to Shadow
DB. Plumber can provide a stable snapshot/generation and read-only evidence
lookup. It must not decide that two human blocks should merge, supersede or be
deleted.

### 7. One ledger, many rebuildable index views

The index-view section treats sparse FTS/BM25, dense embeddings, temporal lists,
profiles, wiki links and graphs as views. The authoritative data is upstream;
rebuild is the normal recovery operation. Scope is part of both read and rebuild
so rebuilding one tenant cannot wipe another tenant's rows.

This is the closest direct match to Matryca's architecture. Shadow DB already
has explicit generation, readiness and rebuild paths; generational BM25 and
semantic sidecars are disposable. The missing refinement is to make every view
generation visible in the internal retrieval contract and to test cross-graph
cache isolation as a first-class property.

### 8. Hybrid retrieval uses independent candidate channels

The hybrid section runs keyword, recency, dense, graph and temporal channels as
independent ranked lists, then fuses them with Reciprocal Rank Fusion. RRF avoids
pretending raw BM25 and cosine scores share a scale. A broken channel degrades
without making a successful no-match look like an infrastructure error.

Matryca already has Shadow FTS/BM25, dual semantic embeddings and structural
subtree/link operations, but they do not yet form one universal retrieval
envelope. The practical idea is not to add another search backend; it is to
standardize channel output:

```json
{
  "block_uuid": "...",
  "channel": "fts|semantic|structural|temporal",
  "rank": 1,
  "score": 0.82,
  "generation": "..."
}
```

Fusion, deduplication and diversity should then be tested independently from
each channel. Structural expansion remains bounded and optional. Recency or
temporal channels must not outrank an explicit scope or read-policy failure.

### 9. Context assembly is a safety boundary

The context section treats retrieval output as an evidence bundle, not a string.
Each item carries kind, epistemic status, score, confidence, timestamp,
provenance and contradiction links. Selection is token-budgeted and
contradiction groups travel together; an empty selection is valid. Rendering
starts with a guard that recalled text is reference data, not instructions.

Plumber should stop at the canonical retrieval envelope and not become a prompt
renderer. Still, the envelope should make Brain's assembly safe by providing
stable block IDs, page/title metadata, content hashes, source generation and
bounded excerpts on request. The full block body should not be duplicated into
telemetry or cache keys.

### 10. Evaluation becomes governance only when thresholds have actions

The final section computes write, retrieval, context and end-to-end metrics from
the event ledger. It distinguishes retrieval `no_inject_rate` from answer
`abstention_rate`, treats missing as `None` rather than zero, and attaches an
action to each threshold. It also warns against letting a model grade its own
answer and against running full evaluation on the hot path.

For Plumber, the direct contribution is a content-free retrieval ledger or
metrics adapter with `hit`, `miss`, `invalidated`, `generation_mismatch`,
`backend_error`, method, result count and duration. The ledger can remain
optional and local. Brain can join it with answer outcomes later. A retrieval
cache metric must never be presented as answer correctness.

## Crosswalk against current Matryca Plumber

| Learn Agent Memory pattern | Matryca status | Safe next interpretation |
| --- | --- | --- |
| Scope-first contract | Graph-specific cache roots and external cache IDs exist; user/agent scope is not a universal retrieval DTO | Add opaque graph scope to cache/provenance contracts; enforce before lookup. |
| Append-only evidence ledger | Markdown is canonical; Shadow is derived; no full session ledger in Plumber | Keep session/tool evidence in Brain/ReMe; expose references only. |
| Write gate | Not a Plumber runtime feature | Future Brain proposal queue, never automatic Plumber mutation. |
| Typed/epistemic records | Memory DDL is schema-only; blocks retain properties | Preserve metadata; do not infer memory state in Shadow. |
| Bitemporal resolution | File mtime and graph generation are available; semantic validity is not | Keep cache time separate from claim validity; add fields only in Brain. |
| Rebuildable index views | Strong: Shadow, generational BM25 and semantic sidecars | Add per-view generation to the retrieval envelope and rebuild tests. |
| Parallel channels + RRF | FTS/BM25 and semantic paths exist; application-wide fusion is partial | Define a common candidate record and one bounded fusion layer. |
| Context evidence bundle | MCP Markdown formatters exist; canonical typed envelope is planned | Add an internal envelope while retaining current rendering compatibility. |
| Untrusted-memory framing | Plumber returns evidence; prompt authority belongs to Brain | Preserve framing metadata, never turn retrieved text into instructions. |
| Feedback ledger | Content-free cache counters exist; answer outcomes are outside Plumber | Add optional retrieval observations; join answer feedback elsewhere. |
| Evaluation gates | Many deterministic tests and targeted benchmarks exist | Add explicit cold/warm, invalidation and missing-vs-zero gates. |

## Prioritized improvements for Matryca Plumber

### P0 — strengthen the existing retrieval contract

1. **Typed retrieval envelope.** Define an internal immutable result with schema
   version, graph scope, graph/Shadow/semantic generations, method/channel, rank,
   score components, block UUID, page identity, content hash and provenance.
2. **Generation-aware cache key.** Include the relevant generation before reading
   a cached value. A stale generation must be an ineligible miss, not a value that
   is inspected and then rejected.
3. **Scope isolation tests.** Use two synthetic graphs with identical queries and
   overlapping block UUIDs. Assert that every cache, rebuild and semantic store
   remains isolated.
4. **No-match/error distinction.** Preserve the difference between a successful
   channel returning zero candidates and a backend failure that triggers fallback.
5. **Content-free observation fields.** Extend local diagnostics with method,
   cache state, generation transition, result count and latency buckets only.

These changes are LLM-free and build on current Shadow/generational hooks.

### P1 — make hybrid retrieval and context assembly composable

1. Normalize FTS, semantic, structural and future temporal candidates into one
   record shape, then fuse with stable RRF or a documented equivalent.
2. Keep channel scores separate from the fused score so later evaluation can say
   which channel found or lost a block.
3. Add deterministic diversity (for example, bounded blocks per page) only after
   measuring whether it improves labelled recall.
4. Return a canonical evidence manifest to MCP formatters and prompt builders;
   treat Markdown output as a renderer, not as cache state.
5. Keep contradiction groups and temporal validity as Brain-level metadata until
   the graph has an authoritative representation for them.

### P2 — give Brain a safe learning seam

1. Add an optional local `RetrievalObservation` stream owned by Brain or a
   separate sidecar, not Shadow DB's source of truth.
2. Record selected, cited, accepted, corrected and outdated evidence separately;
   selection alone is not positive feedback.
3. Generate offline policy candidates from observations; never update ranking
   weights synchronously from one click or one model selection.
4. Introduce `propose → validate → approve → apply` for memory changes, with OCC,
   diff and rollback in the mutation plane.

### P3 — only after evidence supports it

1. Add temporal/claim indexes if real queries require as-of or validity-aware
   recall.
2. Add graph or profile views only for measured multi-hop/profile workloads.
3. Consider a model-assisted memory controller only after deterministic traces,
   held-out fixtures and hard safety gates are stable.

## Recommended data contracts

### Retrieval provenance

```json
{
  "schema_version": 1,
  "graph_scope": "opaque-graph-id",
  "graph_generation": 42,
  "shadow_generation": 19,
  "semantic_index_generation": "bge-m3:v1:hash",
  "method": "hybrid",
  "query": {"normalized": "...", "limit": 8},
  "results": [
    {
      "block_uuid": "...",
      "page_title": "...",
      "channel_ranks": {"fts": 1, "semantic": 4},
      "fused_rank": 1,
      "score_components": {"bm25": 0.8, "semantic": 0.7},
      "content_hash": "sha256:..."
    }
  ]
}
```

The fingerprint is a hash of canonical JSON bytes. It is a comparison/debug
identifier, not an authorization token. Query text, paths and body text stay out
of default telemetry.

### Retrieval observation

```json
{
  "event_type": "retrieval_observation",
  "graph_scope": "opaque-graph-id",
  "trace_id": "...",
  "policy_id": "hybrid-r1",
  "method": "hybrid",
  "cache_state": "miss",
  "generation": 42,
  "result_count": 6,
  "latency_ms": 12.4,
  "selected_block_ids": ["..."],
  "outcome": "not_recorded"
}
```

`selected`, `cited`, `answer_accepted`, `task_verified`, `corrected` and
`outdated` should be separate later events. Do not collapse them into one
mutable score in Shadow DB.

## Test and benchmark plan

Use synthetic fixtures only and never write to a real vault. Each case should
compare the current path with the candidate path and record dimensions, not
content.

### Correctness gates

- repeated identical retrieval has identical ordered IDs and fingerprint;
- equal-score candidates use a total deterministic tie-breaker;
- mutation, rename and delete make the old generation ineligible;
- Shadow readiness loss falls back without serving stale cached rows;
- semantic model/index version changes invalidate only eligible semantic values;
- two graph scopes cannot see or evict each other's entries;
- zero matches, backend failure and policy rejection have distinct states;
- no telemetry field contains raw content, absolute paths or vault text;
- the read-only boundary remains unchanged.

### Performance matrix

| Case | Compare | Primary measures |
| --- | --- | --- |
| FTS cold/warm | existing Shadow/generational path vs query cache | p50/p95, hits, misses |
| Semantic cold/warm | vector sidecar load and repeated query | p50/p95, index generation correctness |
| Hybrid fusion | channels individually vs fused result | recall@k, MRR/NDCG, dedupe cost |
| Mutation invalidation | warm hit then edit/rename/delete | stale-ID rate, invalidation latency |
| Context manifest | rendered Markdown vs canonical envelope | byte/fingerprint stability, token estimate |
| Failure fallback | healthy, stale, unavailable Shadow | correctness and recovery latency |

Cold and warm retrieval must be measured separately from engine TTFT or token
generation. A retrieval benchmark cannot claim an inference speedup.

## Cost, risk and non-goals

| Option | Benefit | Risk/cost | Decision |
| --- | --- | --- | --- |
| Copy the full source engine into Plumber | Fast prototype | Duplicates runtime, violates boundary and creates a second memory store | Reject |
| Add an event ledger to Shadow DB | Convenient local writes | Shadow becomes non-rebuildable and risks vault/session mixing | Reject |
| Typed provenance envelope | Stable interoperability and diagnostics | Contract/version maintenance | Prefer |
| Per-scope generation-aware cache | Correct warm reuse | More cache-key discipline | Prefer |
| Full Brain consolidation in Plumber | One integrated loop | LLM coupling, write authority and unsafe mutations | Reject |
| Optional retrieval observations | Enables offline improvement | Retention/privacy policy needed | Brain-side only |

Explicit non-goals:

- no model or embedding dependency added to Plumber;
- no remote memory or telemetry service by default;
- no KV tensors or engine cache IDs in Shadow DB;
- no automatic merge, supersede, retract or delete of Logseq blocks;
- no claim that the source repository's examples are production benchmarks for
  Matryca;
- no broad refactor until a small contract slice demonstrates measurable value.

## Proposed implementation sequence

1. **Contract slice:** typed provenance envelope, opaque graph scope, generation
   fields and deterministic serialization; preserve current MCP response shapes.
2. **Correctness slice:** synthetic cross-scope, mutation, rename/delete and
   Shadow fallback tests; fingerprint and total-order assertions.
3. **Fusion slice:** common candidate records for existing FTS, semantic and
   structural channels; bounded, explainable fusion only if labelled fixtures
   justify it.
4. **Observation slice:** optional content-free retrieval events and
   cold/warm/invalidation dashboards; keep answer outcomes in Brain.
5. **Brain integration:** use the envelope and observations as inputs to a
   separate proposal/consolidation workflow with human approval and rollback.

Each slice should be independently reversible. Stop if relevance ordering
changes unexpectedly, stale IDs appear after mutation, scope isolation fails, or
the warm path does not improve retrieval latency on a representative synthetic
fixture.

## Final assessment

The source repository does not reveal a missing cache technology. It reveals a
missing set of contracts around memory lifecycle and evidence quality. Matryca
Plumber already has the most important infrastructure prerequisite—canonical
Markdown plus rebuildable Shadow/semantic views—and should use this study to
make those views easier to compose, fingerprint, invalidate and evaluate.

The highest-return, lowest-risk next step is the LLM-free provenance and
generation contract. The highest-value future capability is a Brain-owned
observation and proposal loop that can learn from retrieval outcomes without
turning Shadow DB into an opaque memory authority.

## References

- [Learn Agent Memory](https://github.com/hardness1020/learn-agent-memory)
- [MIT license](https://github.com/hardness1020/learn-agent-memory/blob/main/LICENSE)
- [Matryca cache-friendly retrieval decision](../knowledge/architecture/cache-friendly-retrieval.md)
- [Matryca Shadow DB architecture](../knowledge/architecture/shadow-db.md)
- [Matryca graph plane](../knowledge/architecture/graph-plane.md)
- [Matryca LLM-free cluster recognition](../knowledge/architecture/llm-free-cluster-recognition.md)
