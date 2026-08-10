---
type: Architecture
title: LLM-free information-cluster recognition
description: Extend deterministic generational retrieval features to recognize, cache, and evaluate information neighborhoods without requiring model inference.
resource: src/graph/semantic_clustering.py src/graph/generational_cache.py src/graph/insights_engine.py
tags: [clustering, retrieval, cache, logseq, privacy]
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
  - /architecture/cache-friendly-retrieval.md
  - /architecture/graph-plane.md
  - /architecture/shadow-db.md
---

# LLM-free information-cluster recognition

## Decision

Matryca should recognize information neighborhoods from deterministic graph and
text features before considering an LLM or embedding service. The existing
generational BM25 corpus is a useful feature source and invalidation pattern, but
its query-result LRU is not itself a cluster cache.

The target pipeline is:

```text
Logseq Markdown
      │
      ├── title / properties / tags / wikilinks
      ├── bounded lexical term frequencies
      └── graph-relative provenance + content hash
                    │
                    ▼
        deterministic page feature generation
                    │
                    ▼
      sparse candidate graph + weighted similarity
                    │
                    ▼
       balanced communities + cluster fingerprint
              ┌─────┼───────────┐
              ▼     ▼           ▼
        related notes  retrieval  maintenance/insights
```

No model call is necessary for feature extraction, clustering, invalidation, or
quality measurement. Optional model-generated summaries or embeddings may later
add evidence, but they must remain adapters and must not become prerequisites for
basic cluster coverage.

## Current implementation

### Cluster producer

`compute_semantic_clusters` currently:

1. reads one-sentence summaries and tags from `MasterCatalog`;
2. builds sparse TF-IDF vectors from summaries;
3. combines lexical cosine similarity with tag Jaccard similarity;
4. builds a bounded candidate graph;
5. runs deterministic bounded Louvain community detection; and
6. splits or merges communities to enforce cluster-size limits.

Daily journals are excluded from these semantic neighborhoods and are handled as
a distinct scheduling group. Result members and cluster identifiers are emitted
in a stable order.

The important coverage limitation is upstream: `MasterCatalog` only creates an
entry when a page already contains a non-empty `Matryca Semantic Index` summary.
The clustering algorithm is LLM-free, but the default source of its summary and
tag features may be produced by semantic indexing. Pages without that metadata
are therefore absent rather than weakly clustered from deterministic evidence.

### Existing cluster cache

`load_or_compute_semantic_clusters` already persists `semantic_clusters.json` and
reuses it when `catalog_updated_at` and `max_cluster_size` match. This is strong
but coarse invalidation: any catalog update invalidates the whole cluster map.
The payload also carries a schema version, while the loader rejects incompatible
data.

This cache is separate from the new BM25 query LRU:

| Cache | Value | Key / generation | Consumer |
| --- | --- | --- | --- |
| BM25 corpus | term-frequency bags | graph filesystem signature | keyword scorer |
| BM25 query LRU | ordered path/score rows | tokenized request + BM25 parameters | repeated keyword requests |
| Semantic clusters | page-to-neighborhood assignment | catalog update + size setting | daemon scheduling and context |
| Semantic inference cache | validated structured model result | page-relative path + mtime + operation | optional cognitive modules |

No cluster data, query result, or KV tensor belongs in Shadow DB merely because
it is cacheable. Cluster artifacts remain derived application state; inference
KV remains owned by the inference engine.

### Current consumers

- The maintenance daemon groups pending pages by cluster so related work is
  processed together.
- The daemon formats a cluster neighborhood and may inject it into an optional
  inference context after resetting history at a cluster boundary.
- The manual cluster command reports cluster counts and size distribution.
- Graph Insights independently computes deterministic topology, tag overlap,
  orphan pages, dense pages, domain distribution, and catalog coverage. An LLM
  is optional for prose; the fallback report is deterministic.
- Entity consolidation currently requires an LLM for the final alias/merge
  judgment. Deterministic clusters can safely generate a smaller candidate set,
  but must not automatically turn similarity into a destructive merge.

## What the BM25 result cache changes

The implemented query LRU improves repeated BM25 requests, not offline Louvain
execution. Directly calling the query cache once per page or pair would be the
wrong abstraction and could make clustering slower.

The reusable parts are lower-level:

- the resident corpus already holds bounded term frequencies without raw token
  lists;
- graph signatures and mutation hooks provide an invalidation boundary;
- deterministic tokenization and total ordering support reproducible feature
  fingerprints; and
- content-free hit/miss/invalidation counters establish a telemetry pattern.

The next cluster slice should therefore reuse or project corpus features, not
route cluster computation through `score_bm25_query`.

## Synthetic baseline

Run:

```bash
uv run python scripts/bench_semantic_clustering_quality.py
```

The benchmark uses 288 opaque-titled synthetic notes, 12 labelled topics, five
fixed random seeds, and no vault or model. It measures pairwise precision,
recall, F1, purity, adjusted Rand index (ARI), predicted and expected cluster
counts, largest-cluster fraction, latency, and stability after reversing catalog
input order. Quality aggregates also include deterministic percentile bootstrap
intervals over the five fixed seed runs. `collapse_detected` is true only for
total collapse (one predicted cluster for a non-empty catalogue); the
largest-cluster fraction makes partial collapse visible without treating it as
a binary failure.

Observed on the development Mac:

| Available metadata | Pair F1 | Purity | p50 | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Summary + tags | 1.0000 | 1.0000 | 13.9 ms | Ideal synthetic separation |
| Summary only | 0.4546 | 0.5840 | 1.9 ms | Lexical evidence helps but blocking is weak |
| Tags only | 0.5914 | 0.6465 | 1.1 ms | Explicit structure is valuable |
| No features | 0.0903 | 0.1646 | 0.7 ms | Fast output is not useful recognition |

Every scenario produced identical clusters after reversing input insertion
order. Timing is machine-specific and the perfect combined score reflects an
intentionally separable synthetic corpus; it is not evidence of equivalent
quality on a real vault. The useful result is the gap between feature regimes:
coverage and deterministic metadata matter more than caching the final map.

The existing isolated scale gate also passed with 3,000 synthetic pages in
0.35 seconds against its 15-second ceiling. This reinforces the current
priority: cache and incrementally refresh page-local features first; do not add
complex incremental community repair until a larger measured corpus requires it.

## Proposed deterministic feature contract

Introduce an immutable `PageClusterFeatures` value outside MCP formatting and
outside the inference layer:

```text
schema_version
graph_generation
page_id or stable graph-relative identity
content_hash
normalized title terms
bounded term-frequency features
explicit tags and selected page properties
outgoing wikilink identifiers
incoming-link count or bounded neighbor identifiers
page class (page/journal/generated/config)
```

Raw page content is read locally to derive features but is not persisted in
telemetry. Absolute paths, query text, secrets, inference responses, and model KV
state are excluded. Feature serialization has a fixed order and a SHA-256
fingerprint.

The first implementation should source lexical features from the existing BM25
tokenization/corpus rather than create a competing text index. Explicit Logseq
tags, properties, and wikilinks come from existing bounded parsers and indexes.
Generated/config pages and journals require explicit eligibility rules.

## Cluster generation and invalidation

A cluster generation is eligible only when all of these inputs match:

```text
graph generation
feature schema version
clustering algorithm version
similarity weights and thresholds
min/max cluster sizes
stopword/config fingerprint
ordered page-feature fingerprints
```

| Event | Feature action | Cluster action |
| --- | --- | --- |
| Page text change | rebuild one page feature | invalidate assignment generation |
| Tag/property change | rebuild one page feature | invalidate assignment generation |
| Rename/delete | remove old identity and update affected links | invalidate assignment generation |
| Link target change | update source plus bounded neighbor features | invalidate assignment generation |
| Algorithm/weight change | retain page features | recompute assignments |
| Formatting/prompt change | retain features and assignments | regenerate presentation only |

Initially, recompute the full assignment after an affected feature changes. The
existing 3,000-page scale gate shows full deterministic clustering is bounded;
incremental Louvain or partial community repair should be attempted only after a
larger benchmark proves full recomputation is the bottleneck. Feature extraction
is the safer first cache because it is page-local and easy to invalidate.

Persist new cluster/feature artifacts only through the repository's approved
cache-location policy. Read-only operation must be able to compute in memory or
use an external cache without creating or modifying files inside the vault.

## Candidate graph improvement

The current sparse candidate builder derives candidate pairs from shared summary
terms and then uses tag overlap to score those pairs. Deterministic tags and
wikilinks should also be able to propose candidates; otherwise pages with useful
structural metadata but no semantic summary can be under-connected.

A conservative next experiment is a union of bounded candidate sources:

1. uncommon shared lexical terms;
2. explicit shared tags or compatible typed properties;
3. direct and two-hop wikilink adjacency with capped degree; and
4. optional local embedding neighbors behind a separate adapter.

Each source contributes candidates, not final truth. A documented weighted score
and stable tie-breaker determine graph edges. High-degree generic tags and hubs
must be capped or down-weighted to prevent one broad concept from collapsing
unrelated topics.

## Functions that can reuse cluster generations

| Function | LLM-free use | Safety boundary |
| --- | --- | --- |
| Related-note discovery | return nearest pages and cluster provenance | suggestion only |
| Search result diversification | spread top results across neighborhoods | preserve original scores and expose method |
| Graph Insights | cache topology/features and report cluster health | deterministic report remains available |
| Maintenance scheduling | batch related pages and retain warm local data | scheduling must not change vault semantics |
| Generated hub candidates | propose cluster anchors and members | no vault write in read-only/dry-run |
| Entity consolidation | generate likely duplicate pairs | merge/alias requires strict rules or review |
| Unlinked mentions | prioritize candidates within relevant clusters | exact mention validation still required |
| Semantic indexing | avoid reprocessing unchanged neighborhoods | inference output cache stays separate |
| Context construction | emit a compact stable neighborhood prefix | engine owns KV; no remote vault data by default |

Cluster diversity can improve retrieval completeness: after relevance ranking,
a bounded diversification step may reserve evidence from more than one strong
neighborhood when scores are close. This must be evaluated against labelled
queries; cluster membership must never silently replace relevance or raise the
requested result limit.

## Incremental delivery plan

1. **Completed:** deterministic synthetic quality benchmark and documentation of
   current producers, caches, consumers, and limitations.
2. **Feature prototype:** build `PageClusterFeatures` in memory from synthetic
   Markdown fixtures, reusing tokenization, tags, properties, and links. Do not
   alter production clustering yet.
3. **Quality comparison:** compare current catalog-only clustering with the
   deterministic feature path across seeded clean, noisy, sparse-tag, rename,
   and deletion fixtures.
4. **Candidate union:** add bounded tag/link candidate generation if it improves
   pair F1 or recall without unacceptable cluster collapse.
5. **Generational integration:** cache page features through existing cache
   infrastructure and invalidate on the established mutation hooks.
6. **Consumer pilots:** expose read-only related-note and diversified-retrieval
   experiments before using clusters for any write-capable module.
7. **Optional enrichment:** evaluate local embeddings or inference summaries only
   as additional evidence, with separate provenance and no remote default.

## Acceptance criteria

- Every eligible synthetic page appears exactly once; excluded page classes are
  explicit.
- Repeated runs and shuffled input order produce the same canonical assignment.
- A mutation, rename, deletion, or feature-schema change cannot serve a stale
  feature or assignment generation.
- Pairwise precision/recall/F1 and purity are reported for labelled fixtures;
  latency alone cannot approve the change.
- A deterministic feature path materially outperforms the no-feature baseline
  and does not regress the existing summary+tag path.
- Tests never read or write a real vault and telemetry contains no note content,
  absolute path, query, or inference payload.
- Optional LLM/embedding failures affect enrichment only; deterministic cluster
  recognition and read-only consumers remain available.

## Non-goals

- Treating clusters as ground truth or automatically merging notes.
- Reusing BM25 query results as a substitute for page feature extraction.
- Adding a second search index, remote cache, or inference dependency.
- Persisting feature or cluster artifacts inside a read-only vault.
- Promising real-vault quality from a synthetic benchmark.
