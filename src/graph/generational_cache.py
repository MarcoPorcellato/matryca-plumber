"""Process-lifetime caches keyed by filesystem mtimes (incremental-style invalidation)."""

from __future__ import annotations

import math
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from src.utils.env_parse import env_int

from .alias_index import (
    AliasIndex,
    build_alias_index,
    index_aliases_from_file,
    is_journal_page_title_in_index,
    iter_alias_source_paths,
    iter_scannable_pages_markdown,
    page_title_from_path,
    purge_stale_alias_entries,
    remove_page_from_alias_index,
)
from .page_path import page_title_from_graph_relpath
from .path_sandbox import read_graph_file_text

_lock = threading.Lock()
_alias_cache: OrderedDict[str, tuple[frozenset[tuple[str, int]], AliasIndex]] = OrderedDict()
_bm25_cache: OrderedDict[str, tuple[frozenset[tuple[str, int]], Bm25Corpus]] = OrderedDict()
_DEFAULT_CACHE_MAX_GRAPHS = 4


def _generational_cache_max_graphs() -> int:
    value = env_int("MATRYCA_GENERATIONAL_CACHE_MAX_GRAPHS", _DEFAULT_CACHE_MAX_GRAPHS)
    return max(1, min(32, value))


def _evict_oldest_graph_caches() -> None:
    limit = _generational_cache_max_graphs()
    while len(_alias_cache) > limit:
        _alias_cache.popitem(last=False)
    while len(_bm25_cache) > limit:
        _bm25_cache.popitem(last=False)


def _cache_get[T](cache: OrderedDict[str, T], key: str) -> T | None:
    hit = cache.get(key)
    if hit is not None:
        cache.move_to_end(key)
    return hit


def _cache_set[T](cache: OrderedDict[str, T], key: str, value: T) -> None:
    cache[key] = value
    cache.move_to_end(key)
    _evict_oldest_graph_caches()


def clear_generational_caches() -> None:
    """Drop all cached graph artifacts (for tests / hot reload)."""
    with _lock:
        _alias_cache.clear()
        _bm25_cache.clear()


_BM25_VALID_MODES = {"resident", "ondemand"}
_DEFAULT_BM25_MODE = "resident"


def _bm25_mode() -> str:
    from src.utils.env_parse import env_str  # noqa: PLC0415

    raw = env_str("MATRYCA_BM25_MODE", _DEFAULT_BM25_MODE)
    if raw not in _BM25_VALID_MODES:
        from loguru import logger

        logger.warning(
            "Unknown MATRYCA_BM25_MODE={!r}; expected one of {}; using {!r}",
            raw,
            sorted(_BM25_VALID_MODES),
            _DEFAULT_BM25_MODE,
        )
        return _DEFAULT_BM25_MODE
    return raw


def release_bm25_corpus(graph_root: str | Path) -> None:
    """Drop in-memory BM25 corpus for one graph (Phase 1 teardown)."""
    key = str(Path(graph_root).expanduser().resolve(strict=False))
    with _lock:
        _bm25_cache.pop(key, None)


def _tokens_to_term_freqs(tokens: list[str]) -> dict[str, int]:
    tf: dict[str, int] = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1
    return tf


def _mtime_ns(path: Path) -> int | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))


def _signature(paths: list[Path], root: Path) -> frozenset[tuple[str, int]]:
    pairs: list[tuple[str, int]] = []
    for p in paths:
        mt = _mtime_ns(p)
        if mt is None:
            continue
        rel = p.relative_to(root).as_posix()
        pairs.append((rel, mt))
    return frozenset(pairs)


def _patch_signature(
    sig: frozenset[tuple[str, int]],
    root: Path,
    *,
    updated_paths: list[Path] | None = None,
    removed_rels: list[str] | None = None,
) -> frozenset[tuple[str, int]]:
    """Return a copy of ``sig`` with updated mtimes or removed paths."""
    merged = dict(sig)
    for rel in removed_rels or []:
        merged.pop(rel, None)
    for path in updated_paths or []:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        mt = _mtime_ns(path)
        if mt is None:
            merged.pop(rel, None)
        else:
            merged[rel] = mt
    return frozenset(merged.items())


def _page_title_from_rel(rel: str) -> str:
    return page_title_from_graph_relpath(rel)


def _remove_bm25_doc(corpus: Bm25Corpus, rel: str) -> None:
    if rel not in corpus.rels:
        return
    idx = corpus.rels.index(rel)
    old_tf = corpus.doc_term_freqs[idx]
    for token in old_tf:
        count = corpus.df.get(token, 0) - 1
        if count <= 0:
            corpus.df.pop(token, None)
        else:
            corpus.df[token] = count
    del corpus.rels[idx]
    del corpus.doc_term_freqs[idx]
    del corpus.doc_lens[idx]
    corpus.n_docs = max(0, corpus.n_docs - 1)
    corpus.avgdl = sum(corpus.doc_lens) / corpus.n_docs if corpus.n_docs else 1.0


def _replace_bm25_doc(corpus: Bm25Corpus, rel: str, tokens: list[str]) -> None:
    _remove_bm25_doc(corpus, rel)
    if not tokens:
        return
    tf = _tokens_to_term_freqs(tokens)
    corpus.rels.append(rel)
    corpus.doc_term_freqs.append(tf)
    corpus.doc_lens.append(len(tokens))
    for token in tf:
        corpus.df[token] = corpus.df.get(token, 0) + 1
    corpus.n_docs += 1
    corpus.avgdl = sum(corpus.doc_lens) / corpus.n_docs if corpus.n_docs else 1.0


def patch_generational_caches_for_paths(
    graph_root: str | Path,
    changed_paths: list[Path],
    *,
    removed_rels: list[str] | None = None,
) -> bool:
    """Incrementally refresh alias + BM25 caches for touched paths (no full rebuild).

    Call after the Plumber daemon writes a page so MCP sessions keep warm caches.
    Returns ``True`` when at least one in-memory cache was patched.
    """
    root = Path(graph_root).expanduser().resolve(strict=False)
    key = str(root)
    resolved = [p.expanduser().resolve(strict=False) for p in changed_paths]
    patched = False

    with _lock:
        alias_hit = _cache_get(_alias_cache, key)
        if alias_hit is not None:
            sig, idx = alias_hit
            for rel in removed_rels or []:
                remove_page_from_alias_index(idx, _page_title_from_rel(rel))
            for path in resolved:
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                title = _page_title_from_rel(rel)
                if not path.is_file():
                    remove_page_from_alias_index(idx, title)
                    continue
                remove_page_from_alias_index(idx, title)
                index_aliases_from_file(idx, root, path)
            new_sig = _patch_signature(
                sig,
                root,
                updated_paths=resolved,
                removed_rels=removed_rels,
            )
            _cache_set(_alias_cache, key, (new_sig, idx))
            patched = True

        bm25_hit = _cache_get(_bm25_cache, key)
        if bm25_hit is not None:
            sig, corpus = bm25_hit
            from src.rag.local_query import tokenize

            for rel in removed_rels or []:
                _remove_bm25_doc(corpus, rel)
            for path in resolved:
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                if not path.is_file():
                    _remove_bm25_doc(corpus, rel)
                    continue
                try:
                    raw = read_graph_file_text(path, root, errors="replace")
                except OSError:
                    _remove_bm25_doc(corpus, rel)
                    continue
                toks = tokenize(raw)
                _replace_bm25_doc(corpus, rel, toks)
            new_sig = _patch_signature(
                sig,
                root,
                updated_paths=resolved,
                removed_rels=removed_rels,
            )
            _cache_set(_bm25_cache, key, (new_sig, corpus))
            patched = True

    if resolved:
        from .backlink_index import patch_backlink_index_for_paths

        patch_backlink_index_for_paths(root, resolved)

    return patched


def gc_generational_alias_cache(graph_root: str | Path) -> int:
    """Purge deleted pages from the warm alias cache without a full rebuild."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    key = str(root)
    with _lock:
        hit = _cache_get(_alias_cache, key)
        if hit is None:
            return 0
        _sig, idx = hit
        live_titles = {page_title_from_path(root, path) for path in iter_alias_source_paths(root)}
        purged = purge_stale_alias_entries(idx, live_titles)
        new_sig = _signature(iter_alias_source_paths(root), root)
        _cache_set(_alias_cache, key, (new_sig, idx))
        return purged


def cached_build_alias_index(graph_root: str | Path) -> AliasIndex:
    """Return :class:`AliasIndex`, reusing memory when source mtimes are unchanged."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    key = str(root)
    with _lock:
        idx: AliasIndex | None = None
        for _attempt in range(3):
            paths = iter_alias_source_paths(root)
            sig_before = _signature(paths, root)
            hit = _cache_get(_alias_cache, key)
            if hit is not None and hit[0] == sig_before:
                return hit[1]
            idx = build_alias_index(root)
            sig_after = _signature(iter_alias_source_paths(root), root)
            if sig_before == sig_after:
                _cache_set(_alias_cache, key, (sig_after, idx))
                return idx
        assert idx is not None
        return idx


def is_journal_page_title(graph_root: str | Path, title: str) -> bool:
    """Return whether *title* maps to a file under ``journals/`` (cached alias index)."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    return is_journal_page_title_in_index(cached_build_alias_index(root), title)


def _bm25_page_paths(root: Path) -> list[Path]:
    return iter_scannable_pages_markdown(root)


@dataclass(slots=True)
class Bm25Corpus:
    """Pre-tokenized page bag for Okapi BM25 (term frequencies only — no raw token lists)."""

    rels: list[str]
    doc_term_freqs: list[dict[str, int]]
    doc_lens: list[int]
    df: dict[str, int]
    n_docs: int
    avgdl: float


def _build_bm25_corpus(root: Path) -> Bm25Corpus:
    from src.rag.local_query import tokenize

    paths = _bm25_page_paths(root)
    doc_term_freqs: list[dict[str, int]] = []
    rels: list[str] = []
    doc_lens: list[int] = []
    for path in paths:
        try:
            raw = read_graph_file_text(path, root, errors="replace")
        except OSError:
            continue
        toks = tokenize(raw)
        if not toks:
            continue
        doc_term_freqs.append(_tokens_to_term_freqs(toks))
        doc_lens.append(len(toks))
        rels.append(path.relative_to(root).as_posix())

    n_docs = len(doc_term_freqs)
    if n_docs == 0:
        return Bm25Corpus(
            rels=[],
            doc_term_freqs=[],
            doc_lens=[],
            df={},
            n_docs=0,
            avgdl=1.0,
        )

    avgdl = sum(doc_lens) / n_docs
    df: dict[str, int] = {}
    for tf in doc_term_freqs:
        for t in tf:
            df[t] = df.get(t, 0) + 1
    return Bm25Corpus(
        rels=rels,
        doc_term_freqs=doc_term_freqs,
        doc_lens=doc_lens,
        df=df,
        n_docs=n_docs,
        avgdl=avgdl,
    )


def get_cached_bm25_corpus(graph_root: str | Path) -> Bm25Corpus:
    """Token bags + DF for BM25; rebuilt when any page ``st_mtime`` changes."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    key = str(root)
    with _lock:
        corpus: Bm25Corpus | None = None
        for _attempt in range(3):
            paths = _bm25_page_paths(root)
            sig_before = _signature(paths, root)
            if _bm25_mode() == "resident":
                hit = _cache_get(_bm25_cache, key)
                if hit is not None and hit[0] == sig_before:
                    return hit[1]
            corpus = _build_bm25_corpus(root)
            if _bm25_mode() != "resident":
                return corpus
            sig_after = _signature(_bm25_page_paths(root), root)
            if sig_before == sig_after:
                _cache_set(_bm25_cache, key, (sig_after, corpus))
                return corpus
        assert corpus is not None
        return corpus


def score_bm25_query(
    corpus: Bm25Corpus,
    query: str,
    *,
    limit: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """Run BM25 scoring using a pre-built corpus (shared with :mod:`src.rag.local_query`)."""
    from src.rag.local_query import tokenize

    q_tokens = tokenize(query)
    if not q_tokens or corpus.n_docs == 0:
        return []

    n_docs = corpus.n_docs
    avgdl = corpus.avgdl
    scores: list[tuple[str, float]] = []
    for rel, tf_map, dl in zip(corpus.rels, corpus.doc_term_freqs, corpus.doc_lens, strict=True):
        score = 0.0
        for t in q_tokens:
            freq = tf_map.get(t, 0)
            if freq == 0:
                continue
            idf = math.log((n_docs - corpus.df.get(t, 0) + 0.5) / (corpus.df.get(t, 0) + 0.5) + 1.0)
            denom = freq + k1 * (1.0 - b + b * (dl / avgdl if avgdl else 1.0))
            score += idf * ((freq * (k1 + 1.0)) / denom)
        if score > 0.0:
            scores.append((rel, score))

    scores.sort(key=lambda item: (-item[1], item[0]))
    return scores[: max(1, min(limit, 100))]


__all__ = [
    "Bm25Corpus",
    "cached_build_alias_index",
    "clear_generational_caches",
    "gc_generational_alias_cache",
    "get_cached_bm25_corpus",
    "is_journal_page_title",
    "patch_generational_caches_for_paths",
    "release_bm25_corpus",
    "score_bm25_query",
]
