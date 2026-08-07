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
