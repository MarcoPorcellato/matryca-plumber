---
type: Architecture
title: Cache-friendly retrieval and inference context
description: Keep document retrieval and inference KV caches separate while making retrieval output deterministic, attributable, and suitable for reusable prefixes.
resource: src/shadow/ src/graph/generational_cache.py src/semantic/
tags: [retrieval, cache, shadow-db, context, privacy]
timestamp: 2026-08-02T00:00:00Z
status: experimental
audience: [maintainer, contributor, operator]
owner: retrieval-runtime
since: v2.0.0-rc
supersedes: []
related:
  - /architecture/shadow-db.md
  - /architecture/graph-plane.md
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

## Non-goals

- Adding an inference-cache package or runtime dependency.
- Sending vault content to a remote cache by default.
- Changing the read-only boundary or writing to a user vault during tests.
- Refactoring Shadow DB, semantic indexing, or MCP response contracts in this
  decision slice.
