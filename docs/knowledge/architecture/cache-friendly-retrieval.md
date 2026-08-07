---
type: Architecture
title: Cache-friendly retrieval and inference context
description: Keep document retrieval and inference KV caches separate while making retrieval output deterministic, attributable, and suitable for reusable prefixes.
resource: src/shadow/ src/graph/generational_cache.py src/semantic/
tags: [retrieval, cache, shadow-db, context, privacy]
generated: { by: human:marco-porcellato, at: '2026-08-02T00:00:00Z' }
verified: { by: human:marco-porcellato, at: '2026-08-06T00:00:00Z' }
last_verified: 2026-08-06
stale_after: 2027-02-02
status: draft
classification: active
audience: [maintainer, contributor, operator]
owner: retrieval-runtime
since: v2.0.0-rc
supersedes: []
related:
  - /architecture/shadow-db.md
  - /architecture/graph-plane.md
  - /architecture/llm-free-cluster-recognition.md
---

# Cache-friendly retrieval and inference context

## Decision

Matryca owns document retrieval and document-context caching. The inference engine
owns model-specific key/value (KV) cache lifecycle. Shadow DB remains a derived
read cache for vault structure and text; it must never store model tensors, token
states, or engine cache keys.

The boundary is intentionally one-way:

```text
Vault Markdown (system of record)
        │
        ▼
Shadow DB / BM25 / semantic index ──► canonical retrieval envelope ──► inference engine
        │                                      │                            │
        └── invalidation on graph change       └── context fingerprint       └── model KV cache
```

The engine may reuse the stable prefix represented by a canonical envelope. It is
not a Matryca dependency and it receives no control-plane coupling from retrieval.
By default, no vault material is sent to a remote cache service.

## Current evidence

- Shadow DB is an external, derived SQLite read cache with readiness gating and
  Markdown/BM25 fallback. It is not the vault system of record.
- Generational BM25 caches token bags in-process, use filesystem signatures, and
  are incrementally patched after known changed paths.
- Semantic retrieval streams the persisted vector sidecar, caps candidates, and
  orders final results by score then block UUID.
- Local prompt construction already keeps page content before dynamic task text,
  which is the right shape for prefix reuse.

The first implementation slice makes the remaining Shadow FTS tie contract
explicit: equal BM25 ranks sort by `block_uuid`. This provides stable retrieval
ordering without changing relevance, storing new content, or creating a second
cache.

## Why the boundary matters

KV cache entries are model-, tokenizer-, precision-, and engine-specific tensor
state. Persisting them beside retrieval data would make Shadow DB coupled to
inference internals, complicate invalidation, increase disk/privacy exposure, and
break the current read-only model. In contrast, deterministic retrieval and a
stable context envelope benefit every local or future inference runtime without
requiring Matryca to know its cache format.

Current inference-cache systems operate at the engine connector layer, where they
look up token sequences, inject compatible KV chunks, and asynchronously persist
new chunks. Their documented integrations target inference engines such as vLLM
and SGLang, rather than an application retrieval database. This supports a clean
adapter boundary, not embedding an inference cache in Shadow DB. [LMCache
architecture](https://docs.lmcache.ai/developer_guide/architecture.html) and
[integration guide](https://docs.lmcache.ai/developer_guide/integration.html).

## Problem statement and success criteria

An interactive question has two independent latency paths:

1. **Retrieval latency:** interpret the request, select graph evidence, rank it,
   and serialize it for the caller.
2. **Inference latency:** tokenize the resulting prompt and produce a response.

Improving one must not make the other less correct. Matryca therefore optimizes
the first path and makes its output easy for an inference runtime to reuse. An
engine can independently optimize the second path through a local prefix or KV
cache when its platform supports that feature.

The product goal is both faster and more complete answers. "Fast" means lower
retrieval p50/p95 and fewer repeated index computations; "complete" means that
the same request returns a reproducible, explainable set of relevant evidence,
and that a cache never hides an eligible changed block. A cache hit is valid only
when it is semantically equivalent to a fresh retrieval for the same graph
generation.

The following indicators are the decision criteria for each later slice:

| Concern | Primary signal | Guardrail |
| --- | --- | --- |
| Retrieval speed | cold/warm p50 and p95 latency by method | warm path must not bypass invalidation |
| Retrieval completeness | recall@limit against synthetic labelled fixtures | no cache-specific loss of eligible blocks |
| Determinism | repeated result and fingerprint equality | defined tie-breakers for equal scores |
| Context reuse | identical canonical-prefix rate | fixed schema/version and field order |
| Safety | stale-result and privacy test failures | no vault writes; no raw text in telemetry |

These are deliberately independent from model response quality and time-to-first
token (TTFT). Those are measured at the engine boundary, not attributed to a
Shadow DB cache.

## Retrieval contract

### Stable results before caching

The cacheable value is the retrieval result, not a rendered MCP response.
Rendering may gain fields or formatting without changing retrieval semantics;
putting that representation in a cache would make presentation changes behave
like data changes. The result contract must instead carry immutable records with
stable identifiers, method, rank/score, and provenance.

Every method needs a total order:

- FTS/BM25: descending relevance rank, then `block_uuid` ascending.
- Semantic: descending similarity score, then `block_uuid` ascending.
- Hybrid/future graph methods: a documented primary score, then source method,
  then `block_uuid` ascending when previous terms are equal.

The tie rule added in this slice completes the FTS side of that contract. It does
not alter scoring or broaden the result set; it only removes database-plan
dependent ordering for otherwise equal results.

### Request normalization

Normalization is conservative because FTS syntax can be meaningful. A cache key
may trim outer whitespace and normalize Unicode only after the search parser has
established that the transformation preserves the parsed request. It must not
silently lowercase quoted text, reorder terms, drop operators, or rewrite a
semantic query. The canonical request includes:

```text
schema version | graph generation | retrieval method | parsed/normalized query
limit | filter set | embedding model and index version (when applicable)
```

The graph generation is the safety boundary: an entry from any older generation
is ineligible before its value is inspected. This makes invalidation easy to
reason about and permits later eviction policies without weakening correctness.

### Canonical envelope and fingerprint

The next envelope should be a typed internal value with a deterministic JSON
encoding. MCP and prompt builders consume a projection of that value; neither
becomes its owner. Its compact wire shape is intentionally boring:

```json
{
  "schema_version": 1,
  "provenance": {
    "graph_generation": "...",
    "method": "fts",
    "embedding": null
  },
  "query": {"normalized": "...", "limit": 8},
  "results": [{"block_uuid": "...", "content_hash": "..."}],
  "instructions": {"version": 1}
}
```

The `context_fingerprint` is SHA-256 over the canonical JSON bytes, including
the ordered result identifiers and content hashes. It is a comparison and
debugging token, not a bearer credential and not a substitute for access
control. Logs may contain the fingerprint and counts but never the serialized
context, query text, page paths, or raw content.

## Cache ownership and invalidation

The existing generational cache is the correct extension point because it already
models file signatures and incremental graph changes. A query-result layer, if
introduced, sits beside it in the same process and stores immutable retrieval
records. It must not become a separate service, shared remote store, or hidden
second source of truth.

| Event | Required action before the next eligible hit | Reason |
| --- | --- | --- |
| Page text/metadata change | advance graph generation; invalidate affected or all query entries | ranking and selected content may change |
| Page rename or delete | advance generation; remove entries that can mention old identifiers | prevents dangling or stale provenance |
| Graph watcher reconciliation | reconcile signatures, then advance/invalidate | catches changes outside a direct mutation path |
| Shadow rebuild or readiness loss | discard query entries for that Shadow generation | FTS state no longer matches cache value |
| Semantic index/model rebuild | advance semantic index generation | vector scores and candidate space changed |
| MCP formatting or prompt wording change | retain retrieval entry; regenerate projection | presentation is not retrieval state |

For the first query-cache slice, full invalidation per generation is preferable to
clever dependency tracking. Targeted invalidation may follow only after traces
show it materially improves warm-hit value and tests prove correct handling of
rename/delete edges.

### Implemented LLM-free BM25 result cache

The resident Markdown/BM25 fallback now has a bounded in-process LRU of up to
8,192 immutable query results, keyed by tokenized query, limit, and BM25
parameters. A second 65,536-result-row budget prevents broad requests from making
the entry count an unsafe proxy for memory: 8,192 cached queries remain possible
when they average at most eight `(page-relative-path, score)` rows, while queries
returning up to the public 100-row limit evict proportionally sooner. It stores
neither page body nor model state, performs no network I/O, and needs no model,
embedding, daemon, or cache service. Callers receive a fresh list so they cannot
mutate the cached value.

The 8,192-entry bound was selected from the checked-in seeded
512/1,024/2,048/4,096/8,192 capacity benchmark over 16,000 requests and an
8,192-query working set. A separate bounded maintainer study used only aggregate
measurements from an explicitly selected sanitized 493-document local-copy
corpus: its uniform workload improved from 1.10x at 512 entries to 2.29x at
8,192; a skewed workload improved from 1.93x to 3.99x, with diminishing returns
after 4,096. That private-fixture result is supporting evidence, not output of the
public synthetic harness. At an eight-row request limit the full 8,192-entry
cache used about 7.4 MiB; a deliberately broad 100-row synthetic workload would
use about 71.6 MiB per corpus without the row budget. The dual bound retains the
high-cardinality benefit while bounding that payload to 65,536 rows. These
machine- and corpus-specific measurements justify the default but do not
establish a universal latency or memory guarantee.

When a known graph mutation patches the resident BM25 corpus, the batch clears
this result cache before it can serve another request. Per-corpus synchronization
serializes scoring with corpus mutation, so a query observes either the complete
pre-patch generation or the complete post-patch generation, never a partially
updated corpus. A corpus rebuilt after a filesystem-signature mismatch is a new
object with an empty cache. The counters are intentionally content-free: entries,
entry capacity, result rows, result-row capacity, hits, misses, and invalidations.
They support local diagnostics and synthetic benchmarks without recording
queries, paths, or document text.

This is not an FTS or semantic cache. Shadow FTS continues to execute against
SQLite, whose own page/query machinery remains the only cache at that layer; the
semantic index also remains unchanged. The bounded BM25 LRU accelerates repeated
fallback and local keyword requests only, while preserving their exact scoring
and stable order.

## Context and inference integration

Prompt construction benefits from a stable prefix only when the repeated part
arrives in the same order and encoding. The envelope permits the builder to put
stable policy and selected document context before per-turn instructions. It does
not force a specific prompt template, model, server, or cache provider.

Matryca exports ordinary text/context to a local engine. The engine alone decides
whether it has a reusable prefix, how its tokenizer segments it, what precision
to use, and when to evict KV state. No engine cache identifier returns to Shadow
DB, and retrieval never waits on an engine cache operation. This keeps failures
isolated: a disabled or unsupported KV cache degrades only inference speed, never
retrieval correctness.

For the current local deployment, an engine prefix cache can remain an operational
choice. A fuller persistent-KV implementation currently requires a compatible
engine/runtime, while this repository work remains useful for local and future
engines alike.

## Incremental plan

1. **Deterministic retrieval (now):** retain score-first ordering and use stable
   identifiers for all ties. Normalize query whitespace/case only where it does
   not change FTS syntax or semantic meaning.
2. **Canonical context envelope:** introduce a compact typed envelope outside MCP
   formatting. Its fixed field order is `schema_version`, `provenance`, `query`,
   `results`, then `instructions`; human Markdown remains a rendering of it.
3. **Provenance and fingerprint:** hash canonical JSON with SHA-256. Include graph
   generation, method, normalized query, limit, embedding model/version when
   applicable, and ordered block identifiers plus content hashes. Do not put
   absolute graph paths, raw content, API keys, or model KV data in telemetry.
4. **Application query cache:** extend the existing generational cache rather than
   add a cache service. Key it by the canonical retrieval request plus graph
   generation; invalidate before serving after a successful graph mutation,
   watcher reconciliation, Shadow rebuild, or semantic-index generation change.
   Cache immutable retrieval records, never formatted mutable output.
5. **Telemetry and benchmarks:** record content-free method, hit/miss,
   invalidation reason, result count, and latency buckets. Benchmark cold and warm
   retrieval separately from engine TTFT, using only synthetic fixtures.

## Cost and risk assessment

| Option | Benefit | Cost / risk | Decision |
| --- | --- | --- | --- |
| Persist KV in Shadow DB | None beyond an engine cache | Model coupling, sensitive tensors, invalidation complexity | Reject |
| New retrieval-cache service | Potential sharing | Duplicate cache/infrastructure and remote-default risk | Reject |
| Extend generational cache | Low latency, existing invalidation hooks | Requires clear generation contract | Prefer |
| Canonical context envelope | Better prefix reuse and debuggability | Contract/versioning discipline | Next |
| Engine-local persistent KV | Low TTFT where supported | Runtime/hardware-specific operations | Optional, external to Matryca |

## Acceptance tests and benchmark protocol

Use synthetic pages and vectors only. For each method, assert identical ordering
and fingerprint across repeated reads; mutate, rename, and delete a fixture page;
then assert the next request misses or changes generation and never returns stale
identifiers. Measure p50/p95 latency for a cold request, a warm retrieval request,
and an inference-engine prefix hit independently. Report counts and duration only;
do not retain fixture content in telemetry artifacts.

### Benchmark matrix

Benchmarks use a small, medium, and large synthetic graph with labelled relevant
blocks, including equal-score ties, renamed blocks, deleted blocks, and semantic
index-version changes. Each case records only dimensions, method, hit state,
generation transition, result count, and duration.

| Scenario | Expected result | What it proves |
| --- | --- | --- |
| FTS cold | correct ordered top-k | baseline lookup and deterministic ties |
| FTS warm | same top-k/fingerprint, lower cache-path work | value of generational query caching |
| Semantic cold/warm | same stable ordered candidates | vector index cache contract |
| Mutation after warm hit | miss or new generation; no old identifiers | strong invalidation |
| Rename/delete after warm hit | no stale source identifiers | provenance safety |
| Prefix-equivalent context | identical envelope bytes/fingerprint | opportunity for engine reuse |
| Engine prefix hit | separate TTFT measurement | inference optimization without coupling |

Report p50 and p95 after a fixed number of warm-up and measured iterations. Keep
cold and warm data separate, state hardware/runtime versions, and compare only
like-for-like fixture sizes. A benchmark that combines retrieval with generation
cannot attribute an improvement to the correct layer and is not sufficient to
accept this design.

## Delivery plan

1. **Completed:** document the boundary and make FTS equal-rank ordering stable.
2. **Validate the contract:** add synthetic determinism and invalidation cases to
   existing Shadow/BM25 and semantic tests; publish the benchmark harness output
   format without recording content.
3. **Introduce provenance:** add the typed canonical envelope and its SHA-256
   fingerprint, retaining existing MCP output compatibility through a renderer.
4. **Add a bounded query cache:** extend the in-process generational cache with
   graph/index generations, explicit size/eviction limits, content-free metrics,
   and full-generation invalidation first. The resident BM25 fallback now covers
   this first narrow case; Shadow FTS and semantic retrieval remain separate.
5. **Measure and tune:** compare cold/warm retrieval against the baseline, then
   separately evaluate local engine prefix/KV behavior where a supported runtime
   exists. Only optimize invalidation granularity after measured evidence.

Each stage is independently releasable, reversible, and testable without a real
vault. A stage should stop if it changes relevance ordering unintentionally,
allows a stale identifier after mutation, or produces no measurable benefit over
the existing generational cache.

Run `uv run python scripts/bench_bm25_query_cache.py` to compare the synthetic
uncached scorer with the cold-plus-warm LRU path. Its 8,192-document corpus,
16,000 requests, and fixed random seed produce both an 8,192-query uniform
working set and a repeated 64-query hot set. Each workload reports the complete
512/1,024/2,048/4,096/8,192 matrix, including both cache budgets, so the capacity
decision and diminishing returns remain reproducible without graph content.
Timings remain machine-specific and are evidence for the BM25 fallback only, not
an end-to-end LLM response benchmark.

## Non-goals

- Adding an inference-cache package or runtime dependency.
- Sending vault content to a remote cache by default.
- Changing the read-only boundary or writing to a user vault during tests.
- Refactoring Shadow DB, semantic indexing, or MCP response contracts in this
  decision slice.
