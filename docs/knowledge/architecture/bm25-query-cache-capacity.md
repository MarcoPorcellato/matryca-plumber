---
type: Decision
title: BM25 query-cache capacity decision
description: Reproducible workload, latency, memory, churn, and parity evidence for the 8,192-entry BM25 query-cache default.
resource: src/graph/generational_cache.py
tags: [bm25, cache, performance, benchmark, capacity]
generated: { by: human:marco-porcellato, at: '2026-08-07T00:00:00Z' }
verified: { by: human:marco-porcellato, at: '2026-08-07T00:00:00Z' }
last_verified: 2026-08-07
stale_after: 2027-02-03
status: stable
classification: canonical
canonical_for: performance.bm25-query-cache-capacity
audience: [maintainer, contributor, agent]
owner: core-runtime
supersedes: []
related:
  - /architecture/cache-friendly-retrieval.md
legacy_sources:
  - ../../../scripts/bench_bm25_query_cache.py
  - ../../../benchmarks/results/bm25_query_cache_capacity_macos_arm64_2026-08-07.json
  - ../../../benchmarks/results/bm25_query_cache_large_corpus_macos_arm64_2026-08-07.json
---

# BM25 query-cache capacity decision

## Decision

Keep **8,192 entries** and **65,536 result rows** as the production defaults. The evidence does not justify doubling the entry capacity to 16,384.

This decision changes no runtime behavior. It closes the evidence gap tracked by [issue #392](https://github.com/MarcoPorcellato/matryca-plumber/issues/392) and must be revisited only with stronger live-corpus or cross-platform evidence.

## Reproducible evidence

Both runs use Python 3.12.13 on macOS 15.7.3 arm64, seed `20260802`, and benchmark source commit `5ef1418602a0363b2e9457920e9af34011743507`. Every measured request asserts exact result parity before contributing latency data.

| Profile | Corpus | Requests | Repetitions | Purpose | Raw result |
| --- | ---: | ---: | ---: | --- | --- |
| Capacity | 128 documents | 20,000 | 3 | Working-set pressure across 512, 2,048, 8,192, and 16,384 entries | [JSON](../../../benchmarks/results/bm25_query_cache_capacity_macos_arm64_2026-08-07.json) |
| Large corpus | 8,192 documents | 1,000 | 1 | Four concurrent corpora, rebuild cost, RSS, and large-corpus latency | [JSON](../../../benchmarks/results/bm25_query_cache_large_corpus_macos_arm64_2026-08-07.json) |

Reproduce from the bound commit:

```bash
uv run python scripts/bench_bm25_query_cache.py \
  --output benchmarks/results/bm25_query_cache_capacity_macos_arm64_2026-08-07.json

uv run python scripts/bench_bm25_query_cache.py \
  --documents 8192 --requests 1000 --repetitions 1 --warmup 128 \
  --capacities 512,2048,8192,16384 --multi-corpora 4 \
  --output benchmarks/results/bm25_query_cache_large_corpus_macos_arm64_2026-08-07.json
```

## Capacity results

Values are medians across three repetitions. Hit ratios are exact deterministic run ratios; p99 is microseconds.

| Workload | 512 hit / p99 | 2,048 hit / p99 | 8,192 hit / p99 | 16,384 hit / p99 |
| --- | ---: | ---: | ---: | ---: |
| Hot 80/20 | 9.880% / 17.791 | 36.710% / 15.250 | **66.385% / 14.000** | 66.385% / 14.084 |
| Uniform | 3.135% / 17.792 | 11.675% / 20.293 | **37.155% / 18.000** | 42.340% / 17.708 |
| Zipf | 67.485% / 13.166 | 78.625% / 12.625 | **80.725% / 12.625** | 80.725% / 12.542 |
| Full-key replay | 0% / 19.417 | 0% / 19.042 | **0% / 20.750** | 18.080% / 19.500 |

The 16,384-entry candidate adds no hit-rate benefit for the representative hot or Zipf distributions. It adds 5.185 percentage points for broad uniform traffic and benefits the deliberately adversarial replay of all 16,384 keys. Those cases do not outweigh the doubled retention ceiling without live-corpus evidence showing a comparable working set.

## Memory, row pressure, and churn

- The 8,192 capacity-pressure phase retained 8,192 entries and 8,192 result rows. Its largest observed per-run RSS delta was 2,195,456 bytes. The 16,384 phase retained 16,384 entries and rows with a 3,702,784-byte largest delta.
- Broad `limit=100` queries reached 65,500 retained rows and only 655 entries at every entry capacity of 2,048 or greater. The row budget therefore bounds memory before the entry limit for broad results.
- The 128-document mutation probe completed 99 invalidations with 15.429 microseconds p99 invalidation latency and 109.949 microseconds p99 rebuild latency.
- The 8,192-document probe completed 99 invalidations with 4.340 microseconds p99 invalidation latency and 5,527.052 microseconds p99 rebuild latency.
- Four concurrent 8,192-document corpora preserved parity, completed 1,000 requests per corpus in 2.080604 seconds, and ended at 63,930,368 bytes RSS in the benchmark process.

## Evidence boundary

These are deterministic synthetic results, not live-vault qualification. RSS and process peak are measured in one sequential benchmark process, so allocator reuse and cumulative peak state make per-capacity memory deltas directional rather than isolated. The run covers one arm64 macOS machine and one fixed seed. A future capacity increase requires representative sanitized live-corpus traces, isolated-process memory measurements, and cross-platform confirmation without material p99 or correctness regression.

## Scorecard baseline (manifest-driven hard-negative benchmark)

The same benchmark harness now supports an additional scorecard profile for deterministic retrieval quality baselines.

Run with:

```bash
uv run python scripts/bench_bm25_query_cache.py \
  --manifest-path tests/fixtures/bm25_hard_negative_manifest_v1.json \
  --top-k 8 \
  --output benchmarks/results/bm25_query_cache_scorecard_macos_arm64_2026-08-10.json
```

Scorecard output includes:

- `benchmark_schema_version: 3`, with manifest schema v2
- `manifest` identity and SHA-256 digest
- retrieval-only Recall@K, MRR, nDCG, stale, contradiction, and abstention metrics
- explicit `update_gold` / `superseded_gold` case classification; update accuracy is
  measured only over `update_gold` cases, while stale metrics remain independent
- abstention precision, recall, and confusion counts, with zero-denominator ratios
  reported as `0.0`
- deterministic 95% percentile-bootstrap confidence intervals for mean ranking metrics
- the `no_retrieval` signal ablation, which makes the lexical BM25 contribution explicit
- latency micro-profile and RSS/payload-context measurements, including a transparent
  byte-derived context-token estimate and zero external-model cost

The profile is synthetic and deterministic: no external data or network runtime dependency is required.
Cases are ordered by `(seed, query)` before output and fingerprinting. The fingerprint
binds deterministic retrieval evidence only; it intentionally excludes timing and RSS
measurements, which remain diagnostic rather than reproducibility claims.
It intentionally does not report end-to-end answer quality: that belongs to the
separate adapter layer, where answer model, judge, prompt, token budget, and
failure policy can be pinned rather than conflated with retrieval quality.

### Retained baseline result

[`bm25_query_cache_scorecard_macos_arm64_2026-08-10.json`](../../../benchmarks/results/bm25_query_cache_scorecard_macos_arm64_2026-08-10.json)
is the first retained execution of this profile. It binds the 24-case synthetic
manifest digest `c1b7eef66bd60aa0caaea5a04bdfb3095d1ecd435a17db377b3e54d99e6cc1d7`
to source commit `dcf45eb3764aa6857ce4310a7ec4b418ff4a5deb` on macOS arm64,
Python 3.12.13. Its deterministic retrieval fingerprint is
`072d0f912f3aa47e3dbd53f4a46b023e16ea56030d4de29111caefa080683502`.

The run reports Recall@8 `0.8333`, MRR `0.7708`, and nDCG `0.7898`; each has a
deterministic 1,000-sample percentile-bootstrap interval in the retained JSON.
Its no-retrieval ablation scores zero on those ranking metrics. Latency and RSS
are diagnostic measurements from this one process and machine, not portable
performance claims. The committed regression test re-executes only the
deterministic scoring path and requires matching case results, metrics,
ablation, manifest digest, and fingerprint. It deliberately does not compare
host-dependent timing or RSS.

## Cross-system evidence contract

`src.memory.benchmark_protocol` provides a closed, provider-free contract for
the later public-suite adapter layer. It validates metadata only: no benchmark
suite is downloaded, no model is invoked, and no prompt, answer, vault content,
credential, path, or raw result is retained in the contract.

Each run pins its suite and dataset revision, harness and Matryca revisions,
dependency lock digest, system revision/configuration digest, hardware/runtime,
budget, cache state, retry/failure policy, and model/judge configuration where applicable. Four
opaque artifact digests are mandatory: item results, exclusions, failed runs,
and run metadata. This makes omissions visible without publishing content.

The comparative validator accepts only completed, like-for-like cohorts with
one Matryca no-semantic-memory control, one Matryca candidate-feature control,
and at least two distinct open external systems. It rejects mismatched dataset,
model, judge, budget, or runtime context, and it keeps retrieval and end-to-end
answer layers separate. The contract is evidence infrastructure, not a claim
that a public suite or external system has already been executed.

### LoCoMo local-data adapter

`src.memory.locomo_adapter` accepts an already acquired LoCoMo JSON file and
normalizes its documented ordered sessions, dialogue IDs, QA categories, and
evidence IDs into deterministic retrieval cases. An empty upstream evidence
list is represented as unavailable retrieval evidence, not an abstention label.
The documented category-5 `adversarial_answer` is retained when the standard
answer is absent. It does not download the
dataset, resolve optional image URLs, call a model, read a vault, or persist
outcomes. Missing or inconsistent required evidence fails closed.

Its public conversation text is available only in memory to an evaluator. A
later runner must retain outcomes, exclusions, and failures through the opaque
artifact digests required by the cross-system evidence contract; loading LoCoMo
alone is neither an executed benchmark nor a comparative claim.
