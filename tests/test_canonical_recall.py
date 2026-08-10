"""Contract tests for the P0 canonical recall envelope (#186)."""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import pytest
from src.agent.dispatch_search_handlers import dispatch_search_target
from src.memory import recall
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.freshness import ShadowFreshnessError, ShadowFreshnessReason
from src.shadow.health import ShadowHealthState
from src.shadow.query import BlockHit


def _request(**changes: object) -> recall.RecallRequest:
    values: dict[str, object] = {"normalized_query": "alpha beta", "filters": {}, "limit": 3}
    values.update(changes)
    return recall.RecallRequest(**values)  # type: ignore[arg-type]


def _hits(*, jitter: float = 0.0, content: str = "alpha") -> list[BlockHit]:
    return [
        BlockHit(block_uuid="b", content="bravo", page_id=1, rank=-2.0 + jitter),
        BlockHit(block_uuid="a", content=content, page_id=1, rank=-2.0 + jitter),
        BlockHit(block_uuid="c", content="charlie", page_id=2, rank=-1.0 + jitter),
    ]


def test_equivalent_permutations_are_byte_stable() -> None:
    expected = recall._completed_bundle(_request(), 7, _hits(), 1.0)  # noqa: SLF001
    for seed in range(1_000):
        shuffled = _hits()
        random.Random(seed).shuffle(shuffled)
        actual = recall._completed_bundle(_request(), 7, shuffled, float(seed))  # noqa: SLF001
        assert actual.fingerprint == expected.fingerprint
        assert actual.model_dump_json(exclude={"volatile"}) == expected.model_dump_json(
            exclude={"volatile"}
        )


def test_score_jitter_without_rank_change_preserves_prefix_and_fingerprint() -> None:
    baseline = recall._completed_bundle(_request(), 7, _hits(), 1.0)  # noqa: SLF001
    jittered = recall._completed_bundle(_request(), 7, _hits(jitter=0.1), 99.0)  # noqa: SLF001
    assert jittered.cache_stable_prefix() == baseline.cache_stable_prefix()
    assert jittered.fingerprint == baseline.fingerprint
    assert jittered.volatile != baseline.volatile


@pytest.mark.parametrize(
    ("recall_request", "generation", "hits"),
    [
        (_request(normalized_query="alpha gamma"), 7, _hits()),
        (_request(filters={"page": "alpha"}), 7, _hits()),
        (_request(limit=2), 7, _hits()),
        (_request(), 8, _hits()),
        (_request(), 7, _hits(content="changed")),
        (_request(), 7, [BlockHit("z", "alpha", 1, -2.0)]),
    ],
)
def test_stable_contract_inputs_invalidate_fingerprint(
    recall_request: recall.RecallRequest,
    generation: int,
    hits: list[BlockHit],
) -> None:
    baseline = recall._completed_bundle(_request(), 7, _hits(), 1.0)  # noqa: SLF001
    changed = recall._completed_bundle(recall_request, generation, hits, 1.0)  # noqa: SLF001
    assert changed.fingerprint != baseline.fingerprint


def test_index_and_instruction_versions_invalidate_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = recall._completed_bundle(_request(), 7, _hits(), 1.0)  # noqa: SLF001
    monkeypatch.setattr(recall, "RECALL_INDEX_VERSION", "shadow-fts5/schema-next")
    assert recall._completed_bundle(_request(), 7, _hits(), 1.0).fingerprint != baseline.fingerprint  # noqa: SLF001
    monkeypatch.setattr(recall, "RECALL_INSTRUCTION_VERSION", "recall-next")
    assert recall._completed_bundle(_request(), 7, _hits(), 1.0).fingerprint != baseline.fingerprint  # noqa: SLF001


@pytest.mark.asyncio
async def test_disabled_recall_is_explicit_and_never_reads_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "false")
    monkeypatch.delenv("LOGSEQ_GRAPH_PATH", raising=False)
    monkeypatch.setattr(
        recall, "resolve_shadow_health", lambda _root: pytest.fail("unexpected read")
    )
    result = await dispatch_search_target("recall", '{"query":"alpha"}')
    assert isinstance(result, dict)
    assert result["state"] == "disabled"
    assert result["code"] == "recall_disabled"


@pytest.mark.parametrize(
    "reason",
    [
        ShadowFreshnessReason.PAGE_UNTRACKED,
        ShadowFreshnessReason.SOURCE_MISSING,
        ShadowFreshnessReason.SOURCE_CHANGED,
    ],
)
def test_unproven_freshness_cannot_return_stale_refs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reason: ShadowFreshnessReason
) -> None:
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "true")
    monkeypatch.setattr(recall, "resolve_shadow_health", lambda _root: ShadowHealthState.READY)
    monkeypatch.setattr(
        recall, "open_shadow_db_query_only", lambda _root: sqlite3.connect(":memory:")
    )
    monkeypatch.setattr(recall, "get_meta", lambda _conn, _key: "7")
    monkeypatch.setattr(recall, "search_blocks_fts", lambda *_args, **_kwargs: _hits())

    def _stale(*_args: object, **_kwargs: object) -> None:
        raise ShadowFreshnessError(reason)

    monkeypatch.setattr(recall, "ensure_shadow_page_fresh", _stale)
    result = recall.recall_from_existing_retrieval(str(tmp_path), "alpha")
    assert result.state == "unavailable"
    assert result.code == "recall_freshness_unproven"
    assert result.results == ()


def test_recall_is_bounded_and_does_not_call_a_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "true")
    monkeypatch.setattr(recall, "resolve_shadow_health", lambda _root: ShadowHealthState.READY)
    monkeypatch.setattr(
        recall, "open_shadow_db_query_only", lambda _root: sqlite3.connect(":memory:")
    )
    monkeypatch.setattr(recall, "get_meta", lambda _conn, _key: "7")
    monkeypatch.setattr(recall, "ensure_shadow_page_fresh", lambda *_args, **_kwargs: None)
    seen: dict[str, object] = {}

    def _hits_limited(_conn: object, _query: str, *, limit: int) -> list[BlockHit]:
        seen["limit"] = limit
        return _hits()[:limit]

    monkeypatch.setattr(recall, "search_blocks_fts", _hits_limited)
    result = recall.recall_from_existing_retrieval(str(tmp_path), '{"query":"alpha", "limit": 2}')
    assert seen["limit"] == 2
    assert len(result.results) == 2
    assert result.per_turn_expansion_budget == recall.MAX_RECALL_RESULTS_PER_TURN
    assert result.no_progress_signature


@pytest.mark.parametrize(
    "query",
    [
        "x" * (recall.MAX_RECALL_REQUEST_CHARS + 1),
        '{"query":"alpha", "limit":1.9}',
        '{"query":"alpha", "limit":null}',
        '{"query":"alpha", "filters":{"nested":{"x":"y"}}}',
        '{"query":"alpha", "filters":null}',
    ],
)
def test_invalid_or_oversized_enabled_requests_fail_closed(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "true")
    result = recall.recall_from_existing_retrieval("/never-read", query)
    assert result.state == "unavailable"
    assert result.code == "recall_invalid_request"


def test_invalid_generation_cannot_produce_completed_bundle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "true")
    monkeypatch.setattr(recall, "resolve_shadow_health", lambda _root: ShadowHealthState.READY)
    monkeypatch.setattr(
        recall, "open_shadow_db_query_only", lambda _root: sqlite3.connect(":memory:")
    )
    monkeypatch.setattr(recall, "get_meta", lambda _conn, _key: "not-a-generation")
    result = recall.recall_from_existing_retrieval(str(tmp_path), "alpha")
    assert result.state == "unavailable"
    assert result.code == "recall_freshness_unproven"


def test_real_query_only_recall_is_graph_immutable_under_strict_read_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    graph = tmp_path / "graph"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    page = pages / "Alpha.md"
    page.write_text("- alpha cache\n  id:: alpha-block\n", encoding="utf-8")
    monkeypatch.setenv("MATRYCA_MEMORY_GRAPH_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    rebuild_shadow_from_graph(graph)
    before = page.read_bytes()
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    result = recall.recall_from_existing_retrieval(str(graph), "alpha")

    assert result.state == "completed"
    assert [item.block_uuid for item in result.results] == ["alpha-block"]
    assert page.read_bytes() == before
