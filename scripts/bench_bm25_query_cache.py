"""Measure synthetic, LLM-free BM25 query-cache cold and warm paths."""

from __future__ import annotations

import json
import random
import time

from src.graph.generational_cache import Bm25Corpus, bm25_query_cache_stats, score_bm25_query

_DOCUMENTS = 2_000
_REQUESTS = 2_000
_SEED = 20260802


def _corpus() -> Bm25Corpus:
    rels: list[str] = []
    doc_term_freqs: list[dict[str, int]] = []
    doc_lens: list[int] = []
    df: dict[str, int] = {}
    for index in range(_DOCUMENTS):
        tokens = [
            "shared",
            f"topic{index % 64}",
            f"bucket{index % 29}",
            f"document{index}",
        ]
        term_freqs = {token: tokens.count(token) for token in tokens}
        rels.append(f"pages/{index:05d}.md")
        doc_term_freqs.append(term_freqs)
        doc_lens.append(len(tokens))
        for token in term_freqs:
            df[token] = df.get(token, 0) + 1
    return Bm25Corpus(
        rels=rels,
        doc_term_freqs=doc_term_freqs,
        doc_lens=doc_lens,
        df=df,
        n_docs=_DOCUMENTS,
        avgdl=sum(doc_lens) / _DOCUMENTS,
    )


def _uniform_random_requests() -> list[str]:
    rng = random.Random(_SEED)
    return [f"topic{rng.randrange(64)} bucket{rng.randrange(29)}" for _ in range(_REQUESTS)]


def _hot_set_random_requests() -> list[str]:
    rng = random.Random(_SEED)
    hot_set = [f"topic{rng.randrange(64)} bucket{rng.randrange(29)}" for _ in range(64)]
    return [rng.choice(hot_set) for _ in range(_REQUESTS)]


def _measure(corpus: Bm25Corpus, requests: list[str], *, force_miss: bool) -> float:
    started = time.perf_counter()
    for query in requests:
        if force_miss:
            corpus.query_cache.clear()
        score_bm25_query(corpus, query, limit=8)
    return time.perf_counter() - started


def _benchmark(requests: list[str]) -> dict[str, float | int | dict[str, int]]:
    uncached = _corpus()
    uncached_seconds = _measure(uncached, requests, force_miss=True)

    cached = _corpus()
    cached_seconds = _measure(cached, requests, force_miss=False)
    return {
        "cache": bm25_query_cache_stats(cached),
        "cached_seconds": round(cached_seconds, 6),
        "speedup": round(uncached_seconds / cached_seconds, 2) if cached_seconds else 0.0,
        "uncached_seconds": round(uncached_seconds, 6),
        "unique_requests": len(set(requests)),
    }


def main() -> None:
    payload = {
        "documents": _DOCUMENTS,
        "requests": _REQUESTS,
        "seed": _SEED,
        "workloads": {
            "hot_set_random": _benchmark(_hot_set_random_requests()),
            "uniform_random": _benchmark(_uniform_random_requests()),
        },
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
