"""Generational cache concurrency tests (#155)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.graph.alias_index import AliasIndex, build_alias_index
from src.graph.generational_cache import (
    _DEFAULT_CACHE_MAX_GRAPHS,
    Bm25Corpus,
    _alias_cache,
    _bm25_cache,
    _bm25_mode,
    _generational_cache_max_graphs,
    cached_build_alias_index,
    clear_generational_caches,
    get_cached_bm25_corpus,
    score_bm25_query,
)


def test_alias_cache_retries_when_signature_drifts_mid_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not store stale alias index when mtimes change during build."""
    clear_generational_caches()
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "A.md"
    page.write_text("alias:: Alpha\n", encoding="utf-8")

    real_build = build_alias_index
    touched = False

    def build_then_touch(root: Path) -> AliasIndex:
        nonlocal touched
        idx = real_build(root)
        if not touched:
            page.write_text("alias:: Beta\n", encoding="utf-8")
            touched = True
        return idx

    monkeypatch.setattr(
        "src.graph.generational_cache.build_alias_index",
        build_then_touch,
    )

    idx = cached_build_alias_index(tmp_path)
    assert idx.resolve("Beta").matched
    assert not idx.resolve("Alpha").matched

    key = str(Path(tmp_path).expanduser().resolve(strict=False))
    assert key in _alias_cache
    cached_idx = _alias_cache[key][1]
    assert cached_idx.resolve("Beta").matched

    idx2 = cached_build_alias_index(tmp_path)
    assert idx2 is cached_idx


def test_bm25_cache_retries_when_signature_drifts_mid_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not store stale BM25 corpus when mtimes change during build."""
    clear_generational_caches()
    monkeypatch.setenv("MATRYCA_BM25_MODE", "resident")
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "a.md"
    page.write_text("cat dog", encoding="utf-8")

    from src.graph.generational_cache import _build_bm25_corpus

    real_build = _build_bm25_corpus
    touched = False

    def build_then_touch(root: Path) -> Bm25Corpus:
        nonlocal touched
        corpus = real_build(root)
        if not touched:
            page.write_text("cat dog elephant", encoding="utf-8")
            touched = True
        return corpus

    monkeypatch.setattr(
        "src.graph.generational_cache._build_bm25_corpus",
        build_then_touch,
    )

    corpus = get_cached_bm25_corpus(tmp_path)
    rows = score_bm25_query(corpus, "elephant", limit=5)
    assert rows and rows[0][0].endswith("a.md")

    key = str(Path(tmp_path).expanduser().resolve(strict=False))
    assert key in _bm25_cache
    cached_corpus = _bm25_cache[key][1]
    rows_cached = score_bm25_query(cached_corpus, "elephant", limit=5)
    assert rows_cached and rows_cached[0][0].endswith("a.md")

    corpus2 = get_cached_bm25_corpus(tmp_path)
    assert corpus2 is cached_corpus


# ---------------------------------------------------------------------------
# Clamp-contract tests for MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS (issue #173)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 1),  # below min → clamped to 1
        ("1", 1),  # exactly at min
        ("4", 4),  # default value
        ("32", 32),  # exactly at max
        ("33", 32),  # above max → clamped to 32
        ("999", 32),  # way above max → clamped to 32
        ("abc", 4),  # non-integer → default
        ("", 4),  # empty → default
        ("-1", 1),  # negative → clamped to 1
    ],
)
def test_generational_cache_max_graphs_clamp(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: int,
) -> None:
    """MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS is clamped to [1, 32];
    invalid input falls back to 4."""
    monkeypatch.setenv("MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS", raw)
    assert _generational_cache_max_graphs() == expected


# ---------------------------------------------------------------------------
# env_parse migration tests (issue #169)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("resident", "resident"),  # valid default
        ("ondemand", "ondemand"),  # valid non-default
        ("RESIDENT", "resident"),  # case-insensitive
        ("ONDEMAND", "ondemand"),  # case-insensitive
        ("invalid", "resident"),  # unknown → fallback
        ("", "resident"),  # empty → default
        ("garbage", "resident"),  # garbage → fallback
    ],
)
def test_bm25_mode_validates_membership(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: str,
) -> None:
    """_bm25_mode() accepts only 'resident'/'ondemand'; anything else falls back."""
    monkeypatch.setenv("MATRYCA_BM25_MODE", raw)
    assert _bm25_mode() == expected


def test_generational_cache_max_graphs_logs_warning_on_invalid_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """env_int emits a loguru warning when MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS is not an integer."""
    import logging

    from loguru import logger

    monkeypatch.setenv("MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS", "notanint")
    warning_messages: list[str] = []

    def _sink(message: object) -> None:
        warning_messages.append(str(message))

    logger.add(_sink, level="WARNING")
    try:
        result = _generational_cache_max_graphs()
    finally:
        logger.remove()

    assert result == _DEFAULT_CACHE_MAX_GRAPHS
    assert any("MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS" in m for m in warning_messages)
