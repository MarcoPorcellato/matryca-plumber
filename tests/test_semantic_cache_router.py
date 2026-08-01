"""Semantic inference cache with cross-process flock."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.plumber_llm import BootstrapSummaryResult
from src.agent.plumber_modules import semantic_cache_router as router
from src.agent.plumber_modules.semantic_cache_router import (
    cache_get,
    cache_put,
    clear_semantic_cache,
    semantic_cache_key,
    validate_cached_model,
)


@pytest.fixture
def graph_root(tmp_path: Path) -> Path:
    root = tmp_path / "graph"
    (root / "pages").mkdir(parents=True)
    return root


def test_semantic_cache_round_trip(graph_root: Path) -> None:
    clear_semantic_cache(graph_root)
    page = graph_root / "pages" / "Note.md"
    page.write_text("- note\n", encoding="utf-8")
    key = semantic_cache_key(page, "semantic_index")
    cache_put(graph_root, "index", key, {"summary": "cached"})
    hit = cache_get(graph_root, "index", key)
    assert hit == {"summary": "cached"}


def test_semantic_cache_preserves_disk_and_memory_in_read_only_mode(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_put(graph_root, "index", "key", {"summary": "cached"})
    cache_root = graph_root / ".matryca_semantic_cache"
    before = {path.name: path.read_bytes() for path in cache_root.iterdir()}
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    assert cache_put(graph_root, "index", "new", {"summary": "new"}) is None
    router.cache_evict(graph_root, "index", "key")
    assert router.purge_expired_semantic_cache(graph_root) == 0
    clear_semantic_cache(graph_root)

    assert cache_get(graph_root, "index", "key") == {"summary": "cached"}
    assert {path.name: path.read_bytes() for path in cache_root.iterdir()} == before


def test_semantic_cache_miss_after_ttl_expired(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_semantic_cache(graph_root)
    page = graph_root / "pages" / "TTL.md"
    page.write_text("- ttl\n", encoding="utf-8")
    monkeypatch.setenv("MATRYCA_LINT_SEMANTIC_CACHE_TTL", "1")
    key = semantic_cache_key(page, "semantic_index")
    fake_now = [1_000_000.0]
    monkeypatch.setattr(
        "src.agent.plumber_modules.semantic_cache_router.time.time",
        lambda: fake_now[0],
    )
    cache_put(graph_root, "index", key, {"summary": "old"}, ttl_seconds=1)
    fake_now[0] += 2.0
    assert cache_get(graph_root, "index", key) is None


def test_semantic_cache_memory_lru_eviction(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_semantic_cache(graph_root)
    monkeypatch.setattr(router, "_memory_max_entries", lambda: 2)
    page = graph_root / "pages" / "A.md"
    page.write_text("- a\n", encoding="utf-8")
    for index in range(3):
        key = f"op{index}:{page.name}:1"
        cache_put(graph_root, "index", key, {"n": index})
    with router._lock:
        assert len(router._memory) <= 2


def test_validate_cached_model_evicts_invalid_schema(graph_root: Path) -> None:
    clear_semantic_cache(graph_root)
    page = graph_root / "pages" / "Bad.md"
    page.write_text("- x\n", encoding="utf-8")
    key = semantic_cache_key(page, "semantic_index")
    cache_put(graph_root, "index", key, {"summary": 123, "suggested_tags": "not-a-list"})
    loaded = validate_cached_model(
        {"summary": 123, "suggested_tags": "not-a-list"},
        BootstrapSummaryResult,
        graph_root=graph_root,
        namespace="index",
        cache_key=key,
    )
    assert loaded is None
    assert cache_get(graph_root, "index", key) is None


def test_cache_get_evicts_oversize_payload(
    graph_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_semantic_cache(graph_root)
    monkeypatch.setattr(router, "_max_cache_payload_bytes", lambda: 64)
    page = graph_root / "pages" / "Huge.md"
    page.write_text("- huge\n", encoding="utf-8")
    key = semantic_cache_key(page, "semantic_index")
    huge = {"summary": "x" * 200}
    assert cache_put(graph_root, "index", key, huge) is None
    assert cache_get(graph_root, "index", key) is None


def test_clear_semantic_cache_preserves_block_vectors(graph_root: Path) -> None:
    clear_semantic_cache(graph_root)
    cache_dir = graph_root / ".matryca_semantic_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    vectors = cache_dir / "block_vectors.json"
    vectors.write_text('{"version":1,"blocks":{}}\n', encoding="utf-8")
    ephemeral = cache_dir / "ephemeral_cache.json"
    ephemeral.write_text('{"namespace":"x","payload":{}}\n', encoding="utf-8")

    clear_semantic_cache(graph_root)

    assert vectors.is_file()
    assert not ephemeral.is_file()


def test_semantic_cache_key_disambiguates_same_basename(tmp_path: Path) -> None:
    import os

    a = tmp_path / "ns1" / "Foo.md"
    a.parent.mkdir(parents=True)
    a.write_text("- x\n", encoding="utf-8")
    b = tmp_path / "ns2" / "Foo.md"
    b.parent.mkdir(parents=True)
    b.write_text("- x\n", encoding="utf-8")
    os.utime(a, ns=(1_000_000_000, 1_000_000_000))
    os.utime(b, ns=(1_000_000_000, 1_000_000_000))
    assert semantic_cache_key(a, "op") != semantic_cache_key(b, "op")
