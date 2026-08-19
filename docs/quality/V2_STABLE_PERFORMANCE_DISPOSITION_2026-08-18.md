---
type: Document
---
# v2.0.0 stable performance disposition — 2026-08-18

## Decision

The v2.0.0 Shadow read path is performance-qualified for stable promotion under
a bounded, evidence-first policy. This is a disposition of release risk, not a
portable latency promise: host-dependent latency and RSS remain diagnostic and
must not be presented as universal benchmarks.

## Release thresholds

The stable read path passes this gate when all of the following remain true:

1. Shadow and fallback results preserve retrieval parity across the retained
   deterministic capacity and large-corpus cases.
2. Cache growth remains bounded by the configured 8,192-entry query cache and
   65,536-result-row budget; higher capacities may be used for diagnostic
   comparison but are not the production contract.
3. Repeated and concurrent corpus exercises do not show an unbounded RSS trend
   or correctness failure.
4. A Shadow health, schema, freshness, or cache-path failure remains safe: reads
   fall back to Markdown/generational BM25 and the graph remains authoritative.

No cross-machine p95/p99 latency threshold is asserted. The corpus, allocator,
filesystem, Python build, and CPU topology materially affect those measurements;
the fallback and integrity invariants are the portable release properties.

## Retained evidence

| Evidence | Result | Boundary |
| --- | --- | --- |
| Capacity matrix | All 36 capacity-pressure and hot-80/20 observations preserved `parity: true` across 512, 2,048, 8,192, and 16,384 entries | macOS arm64, Python 3.12.13, source `5ef1418602a0363b2e9457920e9af34011743507` |
| Large-corpus matrix | All capacity-pressure, hot-80/20, and edge-case observations preserved `parity: true`; 8,192-document p99 remained in the same diagnostic range as 16,384 | macOS arm64, Python 3.12.13, same source snapshot |
| Retrieval scorecard | Recall@8 `0.8333`, MRR `0.7708`, nDCG `0.7898`; update accuracy `1.0`; abstention precision `1.0` | 24-case synthetic Italian hard-negative manifest; source `dcf45eb3764aa6857ce4310a7ec4b418ff4a5deb`; retrieval-only, not answer-quality evidence |
| RC2 dual-profile soak | 417 cycles and 834 passing attempts per profile; unchanged source/working Markdown fingerprints; no skipped subtree checks | Exact public `2.0.0rc2` artifact; see the terminal Gate B record |

The retained JSON artifacts are:

- [`bm25_query_cache_capacity_macos_arm64_2026-08-07.json`](../../benchmarks/results/bm25_query_cache_capacity_macos_arm64_2026-08-07.json)
- [`bm25_query_cache_large_corpus_macos_arm64_2026-08-07.json`](../../benchmarks/results/bm25_query_cache_large_corpus_macos_arm64_2026-08-07.json)
- [`bm25_query_cache_scorecard_macos_arm64_2026-08-10.json`](../../benchmarks/results/bm25_query_cache_scorecard_macos_arm64_2026-08-10.json)
- [`GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md`](GATE_B_RC2_TERMINAL_EVIDENCE_2026-08-13.md)

## Stable-release conclusion

This closes the performance-disposition row for the stable Shadow read path.
It does not authorize a cache-capacity increase, remove the Markdown/BM25
fallback, or qualify future semantic, procedural, or proactive memory work.
