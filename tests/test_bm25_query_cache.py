"""Deterministic, synthetic coverage for the in-process BM25 query-result cache."""

from __future__ import annotations

import math
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from src.graph.generational_cache import (
    Bm25Corpus,
    bm25_query_cache_stats,
    clear_generational_caches,
    get_cached_bm25_corpus,
    patch_generational_caches_for_paths,
    score_bm25_query,
)
from src.rag import local_query


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


def _score_reference(
    corpus: Bm25Corpus,
    query: str,
    *,
    limit: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """Independent pre-cache BM25 oracle for cache-equivalence tests."""
    q_tokens = local_query.tokenize(query)
    scores: list[tuple[str, float]] = []
    for rel, tf_map, dl in zip(
        corpus.rels,
        corpus.doc_term_freqs,
        corpus.doc_lens,
        strict=True,
    ):
        score = 0.0
        for token in q_tokens:
            freq = tf_map.get(token, 0)
            if not freq:
                continue
            document_frequency = corpus.df.get(token, 0)
            idf = math.log(
                (corpus.n_docs - document_frequency + 0.5) / (document_frequency + 0.5) + 1.0
            )
            denom = freq + k1 * (1.0 - b + b * (dl / corpus.avgdl if corpus.avgdl else 1.0))
            score += idf * ((freq * (k1 + 1.0)) / denom)
        if score > 0.0:
            scores.append((rel, score))
    scores.sort(key=lambda item: (-item[1], item[0]))
    return scores[: max(1, min(limit, 100))]


def test_bm25_query_cache_matches_uncached_random_queries() -> None:
    corpus = _synthetic_corpus()
    rng = random.Random(20260802)
    queries = [f"topic{rng.randrange(31)} bucket{rng.randrange(17)}" for _ in range(300)]

    for query in queries:
        expected = _score_reference(corpus, query, limit=8)
        replay = score_bm25_query(corpus, query, limit=8)
        assert replay == expected
        replay.clear()
        assert score_bm25_query(corpus, query, limit=8) == expected

    stats = bm25_query_cache_stats(corpus)
    assert stats["hits"] >= len(queries)
    assert stats["hits"] + stats["misses"] == len(queries) * 2
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


def test_bm25_query_and_corpus_patch_are_serialized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_generational_caches()
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "source.md"
    page.write_text("oldtoken shared", encoding="utf-8")
    corpus = get_cached_bm25_corpus(tmp_path)

    score_entered = threading.Event()
    allow_score = threading.Event()
    patch_started = threading.Event()
    original_tokenize = local_query.tokenize

    def blocking_tokenize(text: str) -> list[str]:
        if text == "oldtoken":
            score_entered.set()
            assert allow_score.wait(timeout=2.0)
        return original_tokenize(text)

    def patch_page() -> bool:
        patch_started.set()
        return patch_generational_caches_for_paths(tmp_path, [page])

    monkeypatch.setattr(local_query, "tokenize", blocking_tokenize)
    page.write_text("newtoken shared", encoding="utf-8")

    with ThreadPoolExecutor(max_workers=2) as executor:
        score_future = executor.submit(score_bm25_query, corpus, "oldtoken", limit=5)
        assert score_entered.wait(timeout=2.0)
        patch_future = executor.submit(patch_page)
        assert patch_started.wait(timeout=2.0)
        assert not patch_future.done()
        allow_score.set()
        assert score_future.result(timeout=2.0)[0][0] == "pages/source.md"
        assert patch_future.result(timeout=2.0) is True

    assert score_bm25_query(corpus, "oldtoken", limit=5) == []
    assert score_bm25_query(corpus, "newtoken", limit=5)[0][0] == "pages/source.md"


def test_bm25_query_cache_is_bounded_lru() -> None:
    corpus = _synthetic_corpus()
    capacity = bm25_query_cache_stats(corpus)["capacity"]
    for index in range(capacity + 1):
        score_bm25_query(corpus, f"unique{index}", limit=1)

    stats = bm25_query_cache_stats(corpus)
    assert stats["entries"] == stats["capacity"] == capacity
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
