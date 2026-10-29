"""MCP semantic search backend selection tests."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from src.agent import dispatch_search_handlers
from src.semantic.external_config import ExternalSemanticSettings


def _settings(tmp_path: Path, *, enabled: bool) -> ExternalSemanticSettings:
    return ExternalSemanticSettings(
        enabled=enabled,
        cache_root=tmp_path / "semantic-cache",
        model="bge-m3-test",
        model_revision="fixture-sha256",
        dimensions=2,
    )


def _install_external_api(monkeypatch: pytest.MonkeyPatch, calls: dict[str, Any]) -> None:
    api = ModuleType("src.semantic.external")

    def search_graph(
        graph_root: str,
        query: str,
        settings: ExternalSemanticSettings,
        embedding_client: Any,
        *,
        limit: int = 15,
    ) -> dict[str, Any]:
        calls["external_search"] = (graph_root, query, settings, embedding_client, limit)
        return {"query": query, "hits": []}

    def format_search_result(result: dict[str, Any]) -> str:
        calls["external_result"] = result
        return "external semantic result"

    api.__dict__["search_graph"] = search_graph
    api.__dict__["format_search_result"] = format_search_result
    monkeypatch.setitem(sys.modules, "src.semantic.external", api)


@pytest.fixture
def inline_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run_inline(
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)


def test_external_flag_selects_external_search_without_creating_legacy_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inline_to_thread: None,
) -> None:
    settings = _settings(tmp_path, enabled=True)
    monkeypatch.setattr(
        ExternalSemanticSettings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    calls: dict[str, Any] = {}
    _install_external_api(monkeypatch, calls)

    class FakeExternalClient:
        def __init__(self, actual_settings: ExternalSemanticSettings) -> None:
            calls["client_settings"] = actual_settings

        def __enter__(self) -> FakeExternalClient:
            return self

        def __exit__(self, *_args: object) -> None:
            calls["client_closed"] = True

    monkeypatch.setattr(
        "src.semantic.external_embedding.ExternalEmbeddingClient",
        FakeExternalClient,
    )
    monkeypatch.setattr(
        "src.semantic.embedding.get_openai_embedding_client",
        lambda: (_ for _ in ()).throw(AssertionError("legacy client must not be created")),
    )
    monkeypatch.setattr(
        "src.semantic.search.format_semantic_search_markdown",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy search must not be selected"),
        ),
    )

    result = asyncio.run(
        dispatch_search_handlers.handle_search_semantic(
            "/synthetic/readonly-graph",
            '{"query":"synthetic concept","limit":7}',
        ),
    )

    assert result == "external semantic result"
    graph_root, query, actual_settings, embedding_client, limit = calls["external_search"]
    assert graph_root == "/synthetic/readonly-graph"
    assert query == "synthetic concept"
    assert actual_settings is settings
    assert isinstance(embedding_client, FakeExternalClient)
    assert limit == 7
    assert calls["client_settings"] is settings
    assert calls["client_closed"] is True
    assert calls["external_result"] == {"query": "synthetic concept", "hits": []}


def test_disabled_external_flag_preserves_legacy_semantic_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inline_to_thread: None,
) -> None:
    settings = _settings(tmp_path, enabled=False)
    monkeypatch.setattr(
        ExternalSemanticSettings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    calls: dict[str, Any] = {}
    legacy_client = object()
    monkeypatch.setattr(
        "src.semantic.embedding.get_openai_embedding_client",
        lambda: calls.setdefault("legacy_client_created", legacy_client),
    )

    def legacy_search(
        graph_root: str,
        query: str,
        *,
        embedding_client: Any,
        limit: int,
    ) -> str:
        calls["legacy_search"] = (graph_root, query, embedding_client, limit)
        return "legacy semantic result"

    monkeypatch.setattr(
        "src.semantic.search.format_semantic_search_markdown",
        legacy_search,
    )
    result = asyncio.run(
        dispatch_search_handlers.handle_search_semantic(
            "/synthetic/graph",
            '{"query":"old behavior","limit":9}',
        ),
    )

    assert result == "legacy semantic result"
    assert calls["legacy_search"] == ("/synthetic/graph", "old behavior", legacy_client, 9)


def test_empty_query_help_reflects_external_backend_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    inline_to_thread: None,
) -> None:
    settings = _settings(tmp_path, enabled=True)
    monkeypatch.setattr(
        ExternalSemanticSettings,
        "from_env",
        classmethod(lambda cls: settings),
    )
    result = asyncio.run(dispatch_search_handlers.handle_search_semantic("/synthetic/graph", " "))
    assert "MATRYCA_EXTERNAL_SEMANTIC_ENABLED" in result
    assert "MATRYCA_DUAL_EMBEDDING_ENABLED" not in result
