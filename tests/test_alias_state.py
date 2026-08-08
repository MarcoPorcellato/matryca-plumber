"""Tests for persistent X-Ray alias registry."""

from __future__ import annotations

import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from logseq_matryca_parser.agent_press import XRAY_STATE_FILENAME
from src.agent.alias_state import (
    SessionAliasRegistry,
    alias_file_path,
    load_alias_registry,
    resolve_pipe_target,
    resolve_target,
    save_alias_registry,
)
from src.shadow.cache_location import (
    ShadowCacheLocationError,
    resolve_shadow_cache_location,
)

BLOCK_UUID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


def _registry_with(mapping: dict[int, str]) -> SessionAliasRegistry:
    registry = SessionAliasRegistry()
    for alias, block_uuid in mapping.items():
        registry.register_alias(alias, block_uuid)
    return registry


def test_save_and_load_alias_registry(tmp_path: Path) -> None:
    registry = _registry_with(
        {0: BLOCK_UUID, 1: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
    )
    save_alias_registry(tmp_path, registry)
    path = alias_file_path(tmp_path)
    assert path.name == XRAY_STATE_FILENAME
    assert path.is_file()
    loaded = load_alias_registry(tmp_path)
    assert loaded.resolve_alias(0) == BLOCK_UUID
    assert loaded.resolve_alias(1) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["0"] == BLOCK_UUID


def test_resolve_target_passes_through_uuid(tmp_path: Path) -> None:
    save_alias_registry(tmp_path, _registry_with({0: BLOCK_UUID}))
    assert resolve_target(tmp_path, BLOCK_UUID) == BLOCK_UUID
    assert resolve_target(tmp_path, "My Page") == "My Page"


def test_resolve_target_unknown_alias_raises(tmp_path: Path) -> None:
    save_alias_registry(tmp_path, _registry_with({0: BLOCK_UUID}))
    with pytest.raises(ValueError, match=r"\[9\]"):
        resolve_target(tmp_path, "[9]")


def test_resolve_pipe_target(tmp_path: Path) -> None:
    save_alias_registry(tmp_path, _registry_with({0: BLOCK_UUID}))
    resolved = resolve_pipe_target(tmp_path, "Demo Page|[0]")
    assert resolved == f"Demo Page|{BLOCK_UUID}"


def test_load_alias_registry_rejects_corrupt_json(tmp_path: Path) -> None:
    path = alias_file_path(tmp_path)
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="Corrupt"):
        load_alias_registry(tmp_path)


def test_resolve_target_unknown_alias_with_empty_state(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\[99\]"):
        resolve_target(tmp_path, "[99]")


def test_read_only_alias_state_is_private_external_and_graph_is_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Alpha.md"
    page.write_text("- Alpha\n", encoding="utf-8")
    cache = tmp_path / "cache"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache))
    before = page.read_bytes()

    state_path = save_alias_registry(graph, _registry_with({0: BLOCK_UUID}))

    expected = resolve_shadow_cache_location(graph).shadow_dir.parent / "xray" / state_path.name
    assert state_path == expected
    assert load_alias_registry(graph).resolve_alias(0) == BLOCK_UUID
    assert page.read_bytes() == before
    assert not (graph / state_path.name).exists()
    if os.name == "posix":
        assert stat.S_IMODE(state_path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600


def test_read_only_alias_state_isolated_by_graph_and_concurrency_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    (first / "pages").mkdir(parents=True)
    (second / "pages").mkdir(parents=True)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(first))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path / "cache"))
    first_path = alias_file_path(first)
    second_path = alias_file_path(second)
    assert first_path != second_path

    registries = [
        _registry_with({0: BLOCK_UUID}),
        _registry_with({1: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}),
    ]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(save_alias_registry, first, registries[index % 2])
            for index in range(20)
        ]
        for future in futures:
            future.result()

    payload = json.loads(first_path.read_text(encoding="utf-8"))
    assert payload in [
        {"0": BLOCK_UUID},
        {"1": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"},
    ]
    assert not second_path.exists()


def test_read_only_alias_state_rejects_xray_directory_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    cache = tmp_path / "cache"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache))
    location = resolve_shadow_cache_location(graph)
    location.shadow_dir.parent.mkdir(parents=True)
    try:
        (location.shadow_dir.parent / "xray").symlink_to(graph, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ShadowCacheLocationError, match="xray_directory_symlink"):
        alias_file_path(graph)

    assert not (graph / XRAY_STATE_FILENAME).exists()
