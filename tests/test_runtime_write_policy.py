from __future__ import annotations

from pathlib import Path

import pytest
from src.graph.safety.write_policy import GraphReadOnlyError, RuntimeWritePolicy


def _graph_root(tmp_path: Path) -> Path:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    return graph


def _symlink(target: Path, link: Path, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (AttributeError, NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")


@pytest.mark.parametrize(
    "env",
    [{}, {"MATRYCA_CACHE_PATH": "   "}, {"MATRYCA_READ_ONLY": "   "}],
)
def test_runtime_write_policy_defaults_and_blank_inputs(
    tmp_path: Path, env: dict[str, str]
) -> None:
    graph = _graph_root(tmp_path)
    policy = RuntimeWritePolicy.from_env(graph, env=env)

    assert policy.graph_root == graph.resolve(strict=False)
    assert policy.read_only is False
    assert policy.cache_path is None

    nested = graph / "pages" / ".." / "pages" / "note.md"
    assert policy.ensure_write_allowed(nested) == nested.resolve(strict=False)


@pytest.mark.parametrize("token", ["1", "true", "yes", "on"])
def test_runtime_write_policy_parses_truthy_tokens(tmp_path: Path, token: str) -> None:
    graph = _graph_root(tmp_path)
    policy = RuntimeWritePolicy.from_env(graph, env={"MATRYCA_READ_ONLY": token})

    assert policy.read_only is True


@pytest.mark.parametrize("token", ["0", "false", "no", "off"])
def test_runtime_write_policy_parses_false_tokens(tmp_path: Path, token: str) -> None:
    graph = _graph_root(tmp_path)
    policy = RuntimeWritePolicy.from_env(graph, env={"MATRYCA_READ_ONLY": token})

    assert policy.read_only is False


def test_runtime_write_policy_rejects_invalid_read_only_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = _graph_root(tmp_path)
    monkeypatch.setenv("MATRYCA_READ_ONLY", "maybe")
    monkeypatch.delenv("MATRYCA_CACHE_PATH", raising=False)

    with pytest.raises(ValueError, match="MATRYCA_READ_ONLY"):
        RuntimeWritePolicy.from_env(graph)


def test_runtime_write_policy_rejects_relative_cache_path(tmp_path: Path) -> None:
    graph = _graph_root(tmp_path)

    with pytest.raises(GraphReadOnlyError) as exc_info:
        RuntimeWritePolicy.from_env(graph, env={"MATRYCA_CACHE_PATH": "cache"})

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "cache_path_not_absolute"


def test_runtime_write_policy_accepts_tilde_expanded_external_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = _graph_root(tmp_path)
    home = tmp_path / "home"
    external_cache = home / "external-cache"
    external_cache.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    policy = RuntimeWritePolicy.from_env(graph, env={"MATRYCA_CACHE_PATH": "~/external-cache"})

    assert policy.cache_path == external_cache.resolve(strict=False)


def test_runtime_write_policy_canonicalizes_graph_root_alias_and_external_cache(
    tmp_path: Path,
) -> None:
    graph = _graph_root(tmp_path)
    graph_alias = tmp_path / "graph-alias"
    _symlink(graph, graph_alias, target_is_directory=True)
    external_cache = tmp_path / "external-cache"
    external_cache.mkdir()
    cache_alias = tmp_path / "cache-alias"
    _symlink(external_cache, cache_alias, target_is_directory=True)

    policy = RuntimeWritePolicy.from_env(
        graph_alias,
        env={
            "MATRYCA_READ_ONLY": "true",
            "MATRYCA_CACHE_PATH": str(cache_alias),
        },
    )

    assert policy.graph_root == graph.resolve(strict=False)
    assert policy.cache_path == external_cache.resolve(strict=False)

    with pytest.raises(GraphReadOnlyError) as exc_info:
        policy.ensure_write_allowed(graph_alias / "pages" / "note.md")

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "graph_root_mutation_blocked"


def test_runtime_write_policy_blocks_nested_graph_path_when_read_only(tmp_path: Path) -> None:
    graph = _graph_root(tmp_path)
    policy = RuntimeWritePolicy(graph_root=graph, read_only=True)
    nested = graph / "pages" / ".." / "pages" / "note.md"

    with pytest.raises(GraphReadOnlyError) as exc_info:
        policy.ensure_write_allowed(nested, operation="write note")

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "graph_root_mutation_blocked"


def test_runtime_write_policy_blocks_symlink_alias_into_graph(tmp_path: Path) -> None:
    graph = _graph_root(tmp_path)
    target = graph / "pages" / "note.md"
    target.write_text("note", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = outside / "note.md"
    _symlink(target, alias)

    policy = RuntimeWritePolicy(graph_root=graph, read_only=True)

    with pytest.raises(GraphReadOnlyError) as exc_info:
        policy.ensure_write_allowed(alias)

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "graph_root_mutation_blocked"


@pytest.mark.parametrize("read_only", [False, True])
def test_runtime_write_policy_rejects_cache_path_inside_graph_for_any_read_only_value(
    tmp_path: Path, read_only: bool
) -> None:
    graph = _graph_root(tmp_path)
    cache_root = graph / ".matryca_semantic_cache"

    with pytest.raises(GraphReadOnlyError) as exc_info:
        RuntimeWritePolicy(graph_root=graph, read_only=read_only, cache_path=cache_root)

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "cache_path_inside_graph"


def test_runtime_write_policy_rejects_cache_symlink_alias_into_graph(tmp_path: Path) -> None:
    graph = _graph_root(tmp_path)
    target_cache_root = graph / "externalized-cache"
    target_cache_root.mkdir()
    cache_alias = tmp_path / "cache-alias"
    _symlink(target_cache_root, cache_alias, target_is_directory=True)

    with pytest.raises(GraphReadOnlyError) as exc_info:
        RuntimeWritePolicy.from_env(
            graph,
            env={
                "MATRYCA_CACHE_PATH": str(cache_alias),
            },
        )

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "cache_path_inside_graph"


def test_runtime_write_policy_fails_closed_on_unresolvable_cache_path(tmp_path: Path) -> None:
    graph = _graph_root(tmp_path)
    cache_loop = tmp_path / "cache-loop"
    _symlink(cache_loop, cache_loop)

    with pytest.raises(GraphReadOnlyError) as exc_info:
        RuntimeWritePolicy.from_env(
            graph,
            env={
                "MATRYCA_READ_ONLY": "true",
                "MATRYCA_CACHE_PATH": str(cache_loop),
            },
        )

    assert exc_info.value.code == "graph_read_only"
    assert exc_info.value.reason == "cache_path_unresolvable"
