"""Tests for dual embedding storage and hybrid retrieval."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.semantic.applicability import synthesize_applicability
from src.semantic.config import hybrid_weights
from src.semantic.indexer import index_page_blocks
from src.semantic.math_util import cosine_similarity, hybrid_score
from src.semantic.search import hybrid_block_search
from src.semantic.store import (
    BlockVectorRecord,
    BlockVectorStore,
    apply_page_block_vector_updates,
    clear_block_vector_store_cache,
    iter_block_records_from_disk,
    load_block_vector_store,
)


@pytest.fixture(autouse=True)
def _resident_block_vector_store_for_round_trip_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Store round-trip tests expect resident caching unless they override mode."""
    monkeypatch.setenv("MATRYCA_BLOCK_VECTOR_STORE_MODE", "resident")


class MockApplicabilityLLM:
    def complete_applicability(self, block_text: str) -> str:
        return f"Useful when asking about: {block_text[:40]}"


class MockEmbeddingClient:
    """Deterministic vectors keyed by exact input text."""

    _TABLE: dict[str, list[float]] = {
        "query": [1.0, 0.0],
        "alpha content": [1.0, 0.0],
        "beta content": [0.0, 1.0],
        "Useful when asking about: alpha content": [0.8, 0.2],
        "Useful when asking about: beta content": [0.2, 0.8],
    }

    def embed_text(self, text: str) -> list[float]:
        key = text.strip()
        if key in self._TABLE:
            return list(self._TABLE[key])
        return [0.1, 0.1]


def test_cosine_similarity_identical() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_hybrid_score_respects_weights(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_WEIGHT_CONTENT", "0.7")
    monkeypatch.setenv("MATRYCA_WEIGHT_APPLICABILITY", "0.3")
    weights = hybrid_weights()
    query = [1.0, 0.0]
    content_match = [1.0, 0.0]
    app_orthogonal = [0.0, 1.0]
    score = hybrid_score(
        query,
        content_match,
        app_orthogonal,
        weight_content=weights.content,
        weight_applicability=weights.applicability,
    )
    assert score == pytest.approx(0.7)


def test_synthesize_applicability_mock() -> None:
    out = synthesize_applicability("alpha content", MockApplicabilityLLM())
    assert "alpha" in out


def test_block_vector_store_round_trip(tmp_path: Path) -> None:
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-a",
        BlockVectorRecord(
            page_title="Demo",
            block_text="hello",
            applicability_text="when greeting",
            vec_content=[1.0, 0.0],
            vec_applicability=[0.5, 0.5],
            updated_at="2026-01-01T00:00:00+00:00",
        ),
    )
    store.save()
    reloaded = load_block_vector_store(tmp_path, force_reload=True)
    record = reloaded.blocks["uuid-a"]
    assert record.page_title == "Demo"
    assert record.vec_content == [1.0, 0.0]


def test_hybrid_block_search_ranking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_block_vector_store_cache()
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_WEIGHT_CONTENT", "0.5")
    monkeypatch.setenv("MATRYCA_WEIGHT_APPLICABILITY", "0.5")

    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-alpha",
        BlockVectorRecord(
            page_title="P",
            block_text="alpha content",
            applicability_text="Useful when asking about: alpha content",
            vec_content=[1.0, 0.0],
            vec_applicability=[0.8, 0.2],
            updated_at="t",
        ),
    )
    store.upsert(
        "uuid-beta",
        BlockVectorRecord(
            page_title="P",
            block_text="beta content",
            applicability_text="Useful when asking about: beta content",
            vec_content=[0.0, 1.0],
            vec_applicability=[0.2, 0.8],
            updated_at="t",
        ),
    )
    store.save()

    client = MockEmbeddingClient()
    hits = hybrid_block_search(tmp_path, "query", embedding_client=client, limit=5)
    assert hits
    assert hits[0].block_uuid == "uuid-alpha"
    assert hits[0].final_score >= hits[1].final_score


def test_index_page_blocks_noop_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MATRYCA_DUAL_EMBEDDING_ENABLED", raising=False)
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    block_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (pages / "Demo.md").write_text(
        f"- Alpha bullet\n  id:: {block_id}\n",
        encoding="utf-8",
    )
    count = index_page_blocks(
        tmp_path,
        pages / "Demo.md",
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 0


def test_index_page_blocks_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage

    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    block_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    node = LogseqNode.model_validate(
        {
            "uuid": block_id,
            "source_uuid": block_id,
            "content": "Alpha bullet",
            "clean_text": "Alpha bullet",
            "indent_level": 0,
            "properties": {"id": block_id},
            "children": [],
            "synthetic_id": False,
        },
    )
    page = LogseqPage.model_validate(
        {
            "title": "Demo",
            "raw_content": "- Alpha bullet",
            "root_nodes": [node],
        },
    )

    class _FakeGraph:
        pages = {"Demo": page}

    class _FakeCache:
        def apply_file_event(self, path: Path, kind: str) -> None:
            _ = path, kind

        def get_graph(self) -> _FakeGraph:
            return _FakeGraph()

    monkeypatch.setattr(
        "src.semantic.indexer.get_graph_ast_cache",
        lambda _root: _FakeCache(),
    )
    clear_block_vector_store_cache()
    page_path = tmp_path / "pages" / "Demo.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(f"- Alpha bullet\n  id:: {block_id}\n", encoding="utf-8")

    count = index_page_blocks(
        tmp_path,
        page_path,
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 1
    store = load_block_vector_store(tmp_path, force_reload=True)
    assert block_id in store.blocks


def test_index_page_blocks_preserves_vectors_when_embed_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from logseq_matryca_parser.logos_core import LogseqNode, LogseqPage

    block_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    node = LogseqNode.model_validate(
        {
            "uuid": block_id,
            "source_uuid": block_id,
            "content": "Alpha bullet",
            "clean_text": "Alpha bullet",
            "indent_level": 0,
            "properties": {"id": block_id},
            "children": [],
            "synthetic_id": False,
        },
    )
    page = LogseqPage.model_validate(
        {
            "title": "Demo",
            "raw_content": "- Alpha bullet",
            "root_nodes": [node],
        },
    )

    class _FakeGraph:
        pages = {"Demo": page}

    class _FakeCache:
        def apply_file_event(self, path: Path, kind: str) -> None:
            _ = path, kind

        def get_graph(self) -> _FakeGraph:
            return _FakeGraph()

    class _FailingApplicability:
        def complete_applicability(self, block_text: str) -> str:
            raise RuntimeError("embed down")

    monkeypatch.setattr(
        "src.semantic.indexer.get_graph_ast_cache",
        lambda _root: _FakeCache(),
    )
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        block_id,
        BlockVectorRecord(
            page_title="Demo",
            block_text="old",
            applicability_text="old",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    page_path = tmp_path / "pages" / "Demo.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text(f"- Alpha bullet\n  id:: {block_id}\n", encoding="utf-8")

    count = index_page_blocks(
        tmp_path,
        page_path,
        "Demo",
        llm_client=_FailingApplicability(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 0
    reloaded = load_block_vector_store(tmp_path, force_reload=True)
    assert block_id in reloaded.blocks


def test_index_page_blocks_keeps_vectors_when_page_missing_from_ast(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")

    class _EmptyGraph:
        pages: dict[str, object] = {}

    class _FakeCache:
        def apply_file_event(self, path: Path, kind: str) -> None:
            _ = path, kind

        def get_graph(self) -> _EmptyGraph:
            return _EmptyGraph()

    monkeypatch.setattr(
        "src.semantic.indexer.get_graph_ast_cache",
        lambda _root: _FakeCache(),
    )
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "keep-me",
        BlockVectorRecord(
            page_title="Demo",
            block_text="stale",
            applicability_text="stale",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    page_path = tmp_path / "pages" / "Demo.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text("- x\n", encoding="utf-8")

    count = index_page_blocks(
        tmp_path,
        page_path,
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 0
    reloaded = load_block_vector_store(tmp_path, force_reload=True)
    assert "keep-me" in reloaded.blocks


def test_index_page_blocks_prunes_when_no_indexable_nodes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from logseq_matryca_parser.logos_core import LogseqPage

    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    page = LogseqPage.model_validate(
        {
            "title": "Demo",
            "raw_content": "- plain bullet without id",
            "root_nodes": [],
        },
    )

    class _FakeGraph:
        pages = {"Demo": page}

    class _FakeCache:
        def apply_file_event(self, path: Path, kind: str) -> None:
            _ = path, kind

        def get_graph(self) -> _FakeGraph:
            return _FakeGraph()

    monkeypatch.setattr(
        "src.semantic.indexer.get_graph_ast_cache",
        lambda _root: _FakeCache(),
    )
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "orphan-uuid",
        BlockVectorRecord(
            page_title="Demo",
            block_text="stale",
            applicability_text="stale",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    page_path = tmp_path / "pages" / "Demo.md"
    page_path.parent.mkdir(parents=True)
    page_path.write_text("- plain bullet without id\n", encoding="utf-8")

    count = index_page_blocks(
        tmp_path,
        page_path,
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 0
    reloaded = load_block_vector_store(tmp_path, force_reload=True)
    assert "orphan-uuid" not in reloaded.blocks


def test_block_vector_store_reload_when_disk_mtime_changes(tmp_path: Path) -> None:
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-a",
        BlockVectorRecord(
            page_title="P",
            block_text="alpha",
            applicability_text="when alpha",
            vec_content=[1.0, 0.0],
            vec_applicability=[0.8, 0.2],
            updated_at="t",
        ),
    )
    store.save()
    first = load_block_vector_store(tmp_path)
    assert "uuid-a" in first.blocks

    path = first.store_path(tmp_path)
    import json
    import time

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["blocks"]["uuid-b"] = {
        "page_title": "P",
        "block_text": "beta",
        "applicability_text": "when beta",
        "vec_content": [0.0, 1.0],
        "vec_applicability": [0.2, 0.8],
        "updated_at": "t2",
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    time.sleep(0.02)

    second = load_block_vector_store(tmp_path)
    assert "uuid-b" in second.blocks


def test_index_page_blocks_skips_without_flag_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "false")
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Demo.md").write_text("- No id line\n", encoding="utf-8")
    count = index_page_blocks(
        tmp_path,
        pages / "Demo.md",
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
    )
    assert count == 0


def test_index_page_blocks_respects_injected_runtime_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.semantic.config import (
        EmbeddingSettings,
        HybridWeights,
        SemanticRuntimeConfig,
    )

    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Demo.md").write_text("- No id line\n", encoding="utf-8")
    disabled = SemanticRuntimeConfig(
        dual_embedding_enabled=False,
        embedding=EmbeddingSettings(
            base_url="http://127.0.0.1:9",
            model="test",
            api_key="test",
        ),
        hybrid=HybridWeights(content=0.5, applicability=0.5),
    )
    count = index_page_blocks(
        tmp_path,
        pages / "Demo.md",
        "Demo",
        llm_client=MockApplicabilityLLM(),
        embedding_client=MockEmbeddingClient(),
        runtime_config=disabled,
    )
    assert count == 0


def test_hybrid_block_search_streams_without_resident_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.semantic import store as store_module

    clear_block_vector_store_cache()
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-alpha",
        BlockVectorRecord(
            page_title="P",
            block_text="alpha content",
            applicability_text="Useful when asking about: alpha content",
            vec_content=[1.0, 0.0],
            vec_applicability=[0.8, 0.2],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    hits = hybrid_block_search(
        tmp_path,
        "query",
        embedding_client=MockEmbeddingClient(),
        limit=5,
    )
    assert hits
    assert len(store_module._loaded) == 0


def test_hybrid_block_search_caps_candidates_while_streaming(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_block_vector_store_cache()
    monkeypatch.setenv("MATRYCA_DUAL_EMBEDDING_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SEMANTIC_SEARCH_MAX_CANDIDATES", "3")

    store = load_block_vector_store(tmp_path)
    for index in range(10):
        store.upsert(
            f"uuid-{index}",
            BlockVectorRecord(
                page_title="P",
                block_text=f"block {index} query token",
                applicability_text=f"Useful when asking about: block {index}",
                vec_content=[1.0, 0.0],
                vec_applicability=[0.8, 0.2],
                updated_at=f"2026-01-{index + 1:02d}",
            ),
        )
    store.save()
    clear_block_vector_store_cache()

    hits = hybrid_block_search(
        tmp_path,
        "query token",
        embedding_client=MockEmbeddingClient(),
        limit=5,
    )
    assert hits
    assert hits[0].block_uuid.startswith("uuid-")


def test_block_vector_store_lru_eviction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.semantic import store as store_module

    clear_block_vector_store_cache()
    monkeypatch.setattr(store_module, "_block_vector_store_max_graphs", lambda: 2)
    roots = [tmp_path / f"g{i}" for i in range(3)]
    for root in roots:
        root.mkdir()
        store = load_block_vector_store(root)
        store.save()
    assert len(store_module._loaded) == 2


def test_block_vector_store_ondemand_does_not_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.semantic import store as store_module

    clear_block_vector_store_cache()
    monkeypatch.setenv("MATRYCA_BLOCK_VECTOR_STORE_MODE", "ondemand")
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-1",
        BlockVectorRecord(
            page_title="P",
            block_text="alpha",
            applicability_text="app",
            vec_content=[1.0],
            vec_applicability=[1.0],
            updated_at="t",
        ),
    )
    store.save()
    assert len(store_module._loaded) == 0
    reloaded = load_block_vector_store(tmp_path)
    assert reloaded.blocks == {}
    on_disk = dict(iter_block_records_from_disk(tmp_path))
    assert on_disk["uuid-1"].page_title == "P"


def test_apply_page_block_vector_updates_preserves_other_pages(
    tmp_path: Path,
) -> None:
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "other-page-block",
        BlockVectorRecord(
            page_title="Other",
            block_text="keep me",
            applicability_text="keep",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.upsert(
        "demo-stale",
        BlockVectorRecord(
            page_title="Demo",
            block_text="stale",
            applicability_text="stale",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    indexed, pruned = apply_page_block_vector_updates(
        tmp_path,
        "Demo",
        upserts={
            "demo-new": BlockVectorRecord(
                page_title="Demo",
                block_text="fresh",
                applicability_text="fresh",
                vec_content=[0.0, 1.0],
                vec_applicability=[0.5, 0.5],
                updated_at="t2",
            ),
        },
        keep_uuids={"demo-new"},
    )
    assert indexed == 1
    assert pruned == 1

    reloaded = load_block_vector_store(tmp_path, force_reload=True)
    assert "other-page-block" in reloaded.blocks
    assert "demo-stale" not in reloaded.blocks
    assert reloaded.blocks["demo-new"].block_text == "fresh"


def test_block_vector_store_skips_graph_local_save_when_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    graph.mkdir()
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    def _unexpected_cache_update(*_args: object, **_kwargs: object) -> None:
        pytest.fail("read-only save must not update the resident cache")

    monkeypatch.setattr(
        "src.semantic.store._cache_block_vector_store",
        _unexpected_cache_update,
    )
    store = BlockVectorStore(graph_root=graph)
    store.upsert(
        "uuid-block",
        BlockVectorRecord(
            page_title="Demo",
            block_text="blocked",
            applicability_text="blocked",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )

    store.save()

    assert not BlockVectorStore.store_path(graph).exists()
    assert not (graph / ".matryca_semantic_cache").exists()


def test_apply_page_block_vector_updates_preserves_graph_store_when_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    graph.mkdir()
    clear_block_vector_store_cache()
    store = load_block_vector_store(graph)
    store.upsert(
        "uuid-block",
        BlockVectorRecord(
            page_title="Demo",
            block_text="seed",
            applicability_text="cached",
            vec_content=[1.0, 0.0],
            vec_applicability=[1.0, 0.0],
            updated_at="t",
        ),
    )
    store.save()
    path = BlockVectorStore.store_path(graph)
    before = path.read_bytes()

    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    def _unexpected_cache_invalidation(*_args: object, **_kwargs: object) -> None:
        pytest.fail("read-only update must not invalidate the block vector cache")

    monkeypatch.setattr(
        "src.semantic.store._invalidate_block_vector_cache",
        _unexpected_cache_invalidation,
    )
    result = apply_page_block_vector_updates(
        graph,
        "Demo",
        upserts={
            "uuid-updated": BlockVectorRecord(
                page_title="Demo",
                block_text="updated",
                applicability_text="updated",
                vec_content=[0.0, 1.0],
                vec_applicability=[0.5, 0.5],
                updated_at="t2",
            ),
        },
        keep_uuids={"uuid-updated"},
    )

    assert result == (0, 0)
    assert path.read_bytes() == before
    assert not path.with_suffix(".json.tmp").exists()


def test_apply_page_block_vector_updates_allows_external_store_when_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    graph.mkdir()
    external_cache = tmp_path / "external-cache"
    external_path = external_cache / "block_vectors.json"

    def _external_store_path(_root: Path) -> Path:
        return external_path

    monkeypatch.setattr(
        BlockVectorStore,
        "store_path",
        staticmethod(_external_store_path),
    )
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(external_cache))

    result = apply_page_block_vector_updates(
        graph,
        "Demo",
        upserts={
            "uuid-external": BlockVectorRecord(
                page_title="Demo",
                block_text="external",
                applicability_text="external cache",
                vec_content=[0.2, 0.8],
                vec_applicability=[0.3, 0.7],
                updated_at="t",
            ),
        },
        keep_uuids={"uuid-external"},
    )

    assert result == (1, 0)
    assert external_path.is_file()
    assert not (graph / ".matryca_semantic_cache").exists()


def test_load_block_vector_store_ondemand_reads_header_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_block_vector_store_cache()
    store = load_block_vector_store(tmp_path)
    store.upsert(
        "uuid-a",
        BlockVectorRecord(
            page_title="P",
            block_text="alpha",
            applicability_text="when alpha",
            vec_content=[1.0, 0.0],
            vec_applicability=[0.8, 0.2],
            updated_at="t",
        ),
    )
    store.save()
    clear_block_vector_store_cache()

    monkeypatch.setenv("MATRYCA_BLOCK_VECTOR_STORE_MODE", "ondemand")
    shell = load_block_vector_store(tmp_path)
    assert shell.blocks == {}
    assert shell.embedding_dim == 2

    monkeypatch.setenv("MATRYCA_BLOCK_VECTOR_STORE_MODE", "resident")
    clear_block_vector_store_cache()
    resident = load_block_vector_store(tmp_path, force_reload=True)
    assert "uuid-a" in resident.blocks


def test_load_block_vector_store_self_heals_corrupt_vectors(tmp_path: Path) -> None:
    import json

    clear_block_vector_store_cache()
    cache_dir = tmp_path / ".matryca_semantic_cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "block_vectors.json").write_text(
        json.dumps(
            {
                "version": 1,
                "blocks": {
                    "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee": {
                        "page_title": "P",
                        "block_text": "x",
                        "applicability_text": "",
                        "vec_content": None,
                        "vec_applicability": [],
                        "updated_at": "",
                    },
                },
            },
        ),
        encoding="utf-8",
    )
    store = load_block_vector_store(tmp_path, force_reload=True)
    assert store.blocks == {}


def test_block_text_dedupes_identical_content_and_clean_text() -> None:
    from types import SimpleNamespace
    from typing import Any

    from src.semantic.indexer import _block_text

    node: Any = SimpleNamespace(content="Deploy checklist", clean_text="Deploy checklist")
    assert _block_text(node) == "Deploy checklist"
