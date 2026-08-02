"""Deterministic, synthetic coverage for the in-process BM25 query-result cache."""

from __future__ import annotations

import random
from pathlib import Path

from src.graph.generational_cache import (
    Bm25Corpus,
    bm25_query_cache_stats,
    clear_generational_caches,
    get_cached_bm25_corpus,
    patch_generational_caches_for_paths,
    score_bm25_query,
)


def _synthetic_corpus(document_count: int = 256) -> Bm25Corpus:
    rels: list[str] = []
    doc_term_freqs: list[dict[str, int]] = []
    doc_lens: list[int] = []
    df: dict[str, int] = {}
    for index in range(document_count):
        tokens = ["shared", f"topic{index % 31}", f"bucket{index % 17}", f"unique{index}"]
        term_freqs = {token: tokens.count(token) for token in tokens}
        rels.append(f"pages/{index:04d}.md")
        doc_term_freqs.append(term_freqs)
        doc_lens.append(len(tokens))
        for token in term_freqs:
            df[token] = df.get(token, 0) + 1
    return Bm25Corpus(
        rels=rels,
        doc_term_freqs=doc_term_freqs,
        doc_lens=doc_lens,
        df=df,
        n_docs=document_count,
        avgdl=sum(doc_lens) / document_count,
    )


def test_bm25_query_cache_matches_uncached_random_queries() -> None:
    corpus = _synthetic_corpus()
    rng = random.Random(20260802)
    queries = [f"topic{rng.randrange(31)} bucket{rng.randrange(17)}" for _ in range(300)]

    for query in queries:
        corpus.query_cache.clear()  # Reference path: equivalent to the pre-cache scorer.
        expected = score_bm25_query(corpus, query, limit=8)
        replay = score_bm25_query(corpus, query, limit=8)
        assert replay == expected
        replay.clear()
        assert score_bm25_query(corpus, query, limit=8) == expected

    stats = bm25_query_cache_stats(corpus)
    assert stats["hits"] >= len(queries) * 2
    assert stats["misses"] >= len(queries)
    assert stats["entries"] <= stats["capacity"]


def test_bm25_query_cache_invalidates_before_serving_changed_page(tmp_path: Path) -> None:
    clear_generational_caches()
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "source.md"
    page.write_text("oldtoken shared", encoding="utf-8")
    corpus = get_cached_bm25_corpus(tmp_path)

    assert score_bm25_query(corpus, "oldtoken", limit=5)
    assert score_bm25_query(corpus, "oldtoken", limit=5)
    assert bm25_query_cache_stats(corpus)["hits"] == 1

    page.write_text("newtoken shared", encoding="utf-8")
    assert patch_generational_caches_for_paths(tmp_path, [page]) is True
    assert bm25_query_cache_stats(corpus)["entries"] == 0
    assert bm25_query_cache_stats(corpus)["invalidations"] == 1
    assert score_bm25_query(corpus, "oldtoken", limit=5) == []
    assert score_bm25_query(corpus, "newtoken", limit=5)[0][0] == "pages/source.md"


def test_bm25_query_cache_is_bounded_lru() -> None:
    corpus = _synthetic_corpus()
    for index in range(129):
        score_bm25_query(corpus, f"unique{index}", limit=1)

    stats = bm25_query_cache_stats(corpus)
    assert stats["entries"] == stats["capacity"] == 128
    misses_before = stats["misses"]
    score_bm25_query(corpus, "unique0", limit=1)
    assert bm25_query_cache_stats(corpus)["misses"] == misses_before + 1


def test_bm25_query_cache_keys_include_limit_and_scoring_parameters() -> None:
    corpus = _synthetic_corpus()
    assert len(score_bm25_query(corpus, "shared", limit=1)) == 1
    assert len(score_bm25_query(corpus, "shared", limit=3)) == 3
    score_bm25_query(corpus, "shared", limit=3, k1=2.0, b=0.5)

    stats = bm25_query_cache_stats(corpus)
    assert stats["entries"] == 3
    assert stats["misses"] == 3
