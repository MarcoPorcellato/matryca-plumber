"""Tests for runtime directory bootstrap (L1 memory and log sinks)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.l1_memory import collect_l1_markdown_paths, ensure_matryca_l1_dir
from src.config import MatrycaWikiConfig
from src.shadow.cache_location import resolve_shadow_cache_location
from src.utils.config_paths import ensure_plumber_log_directories
from src.utils.runtime_bootstrap import (
    ensure_graph_runtime_directories,
    ensure_matryca_wiki_config_file,
    ensure_repo_dotenv_from_example,
    prepare_matryca_runtime,
    try_prepare_matryca_runtime_from_env,
)


@pytest.fixture(autouse=True)
def _isolate_l1_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_L1_PATH", raising=False)


def test_ensure_matryca_l1_creates_sibling_directory(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    l1 = tmp_path / "matryca-l1"
    assert not l1.is_dir()

    created = ensure_matryca_l1_dir(logseq_graph_path=str(graph))

    assert created == l1
    assert l1.is_dir()
    assert (l1 / "README.md").is_file()
    assert (l1 / "session-rules.md").is_file()
    assert (l1 / "llm-os-rules.md").is_file()
    paths = collect_l1_markdown_paths(logseq_graph_path=str(graph))
    assert (l1 / "session-rules.md") in paths


def test_ensure_matryca_l1_does_not_overwrite_existing_markdown(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    graph.mkdir()
    l1 = tmp_path / "matryca-l1"
    l1.mkdir()
    custom = l1 / "session-rules.md"
    custom.write_text("keep me", encoding="utf-8")

    ensure_matryca_l1_dir(logseq_graph_path=str(graph))

    assert custom.read_text(encoding="utf-8") == "keep me"


def test_ensure_matryca_l1_honors_explicit_directory(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    graph.mkdir()
    explicit = tmp_path / "custom-l1"
    created = ensure_matryca_l1_dir(
        matryca_l1_path=str(explicit),
        logseq_graph_path=str(graph),
    )
    assert created == explicit
    assert explicit.is_dir()


def test_ensure_plumber_log_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ops = tmp_path / "ops" / "matryca_plumber_ops.log"
    loguru = tmp_path / "app" / "matryca_plumber.log"
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(ops))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(loguru))

    resolved_ops, resolved_loguru = ensure_plumber_log_directories()

    assert resolved_ops == ops
    assert resolved_loguru == loguru
    assert ops.parent.is_dir()
    assert loguru.parent.is_dir()


def test_ensure_plumber_log_directories_redirects_graph_local_read_only_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    cache = tmp_path / "external-cache"
    graph_logs = graph / "logs"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache))
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(graph_logs / "ops.log"))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(graph_logs / "app.log"))

    resolved_ops, resolved_loguru = ensure_plumber_log_directories()

    runtime_logs = resolve_shadow_cache_location(graph).shadow_dir.parent / "logs"
    assert resolved_ops == runtime_logs / "ops.log"
    assert resolved_loguru == runtime_logs / "app.log"
    assert resolved_ops.parent.is_dir()
    assert not graph_logs.exists()


def test_collect_l1_skips_readme(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    ensure_matryca_l1_dir(logseq_graph_path=str(graph))
    l1 = tmp_path / "matryca-l1"
    (l1 / "rules.md").write_text("rules", encoding="utf-8")
    paths = collect_l1_markdown_paths(logseq_graph_path=str(graph))
    names = {p.name for p in paths}
    assert "rules.md" in names
    assert "session-rules.md" in names
    assert "README.md" not in names


def test_ensure_graph_runtime_directories(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    graph.mkdir()
    ensure_graph_runtime_directories(graph, templates_subdir="templates")
    assert (graph / ".matryca_semantic_cache").is_dir()
    assert (graph / "templates").is_dir()


def test_ensure_matryca_wiki_config_from_example(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    graph.mkdir()
    l1 = tmp_path / "matryca-l1"
    l1.mkdir()
    created = ensure_matryca_wiki_config_file(graph, l1_dir=l1)
    assert created is not None
    assert created.is_file()
    text = created.read_text(encoding="utf-8")
    assert f"memory_path: {l1}" in text


def test_ensure_repo_dotenv_from_example_creates_file(tmp_path: Path) -> None:
    example = tmp_path / ".env.example"
    example.write_text("LOGSEQ_GRAPH_PATH=/tmp/graph\n", encoding="utf-8")
    target = tmp_path / ".env"
    assert not target.is_file()

    created = ensure_repo_dotenv_from_example(repo_root=tmp_path)

    assert created is True
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == example.read_text(encoding="utf-8")
    assert ensure_repo_dotenv_from_example(repo_root=tmp_path) is False


def test_try_prepare_from_env_without_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOGSEQ_GRAPH_PATH", raising=False)
    monkeypatch.setattr("src.agent.plumber_config.reload_plumber_dotenv", lambda **_kw: None)
    ops = tmp_path / "only-logs" / "ops.log"
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(ops))
    try_prepare_matryca_runtime_from_env()
    assert ops.parent.is_dir()


def test_prepare_matryca_runtime_graph_and_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    l1 = tmp_path / "matryca-l1"
    ops = tmp_path / "logs" / "ops.log"
    loguru = tmp_path / "logs" / "app.log"
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(ops))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(loguru))

    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())

    assert l1.is_dir()
    assert ops.parent.is_dir()
    assert loguru.parent.is_dir()
    assert (graph / ".matryca_semantic_cache").is_dir()
    assert (graph / "templates").is_dir()
    assert (graph / "matryca-wiki.yml").is_file()


def test_ensure_graph_runtime_directories_rejects_traversal(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    graph.mkdir()
    ensure_graph_runtime_directories(graph, templates_subdir="../evil")
    assert not (tmp_path / "evil").exists()
    assert (graph / "templates").is_dir()
