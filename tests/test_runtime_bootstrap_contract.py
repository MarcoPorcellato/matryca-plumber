"""Contract tests for runtime bootstrap (regression guard).

These tests encode the operator-facing guarantees documented in
``docs/openspec/runtime-bootstrap.md``. Failures here mean startup provisioning
or L1 routing behavior changed unintentionally.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.l1_memory import (
    collect_l1_markdown_paths,
    ensure_matryca_l1_dir,
    resolve_matryca_l1_directory,
)
from src.config import MatrycaWikiConfig
from src.utils.runtime_bootstrap import (
    _patch_memory_path_in_wiki_yaml,
    ensure_matryca_wiki_config_file,
    prepare_matryca_runtime,
    try_prepare_matryca_runtime_from_env,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_l1_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent ``MATRYCA_L1_PATH`` leakage across tests."""
    monkeypatch.delenv("MATRYCA_L1_PATH", raising=False)


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _expected_sibling_l1(graph: Path) -> Path:
    return graph.expanduser().resolve(strict=False).parent / "matryca-l1"


# ---------------------------------------------------------------------------
# L1 placement contract (sibling of vault, not inside pages/)
# ---------------------------------------------------------------------------


def test_resolve_matryca_l1_directory_defaults_to_sibling_of_vault(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    resolved = resolve_matryca_l1_directory(logseq_graph_path=str(graph))
    assert resolved == _expected_sibling_l1(graph)
    assert not str(resolved).startswith(str(graph.resolve()))


def test_l1_is_not_created_under_vault_pages_tree(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())
    assert not (graph / "matryca-l1").exists()
    assert not (graph / "pages" / "matryca-l1").exists()
    assert _expected_sibling_l1(graph).is_dir()


# ---------------------------------------------------------------------------
# Idempotency & non-destructive updates
# ---------------------------------------------------------------------------


def test_prepare_matryca_runtime_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    l1 = _expected_sibling_l1(graph)
    l1.mkdir(parents=True)
    wiki = graph / "matryca-wiki.yml"
    custom_rules = l1 / "session-rules.md"
    custom_rules.write_text("operator rules", encoding="utf-8")
    wiki.write_text("namespaces:\n  - Preserved\nmemory_path: /tmp/ignored\n", encoding="utf-8")

    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())
    first_wiki = wiki.read_text(encoding="utf-8")
    first_rules = custom_rules.read_text(encoding="utf-8")

    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())

    assert wiki.read_text(encoding="utf-8") == first_wiki
    assert custom_rules.read_text(encoding="utf-8") == first_rules


def test_ensure_matryca_l1_does_not_overwrite_readme(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    l1 = _expected_sibling_l1(graph)
    l1.mkdir(parents=True)
    readme = l1 / "README.md"
    readme.write_text("custom operator readme", encoding="utf-8")

    ensure_matryca_l1_dir(logseq_graph_path=str(graph))

    assert readme.read_text(encoding="utf-8") == "custom operator readme"


def test_ensure_wiki_config_never_overwrites_existing_file(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    wiki = graph / "matryca-wiki.yml"
    wiki.write_text("namespaces:\n  - OperatorVault\n", encoding="utf-8")

    ensure_matryca_wiki_config_file(graph, l1_dir=_expected_sibling_l1(graph))

    assert "OperatorVault" in wiki.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Full prepare contract (all provisioned artifacts)
# ---------------------------------------------------------------------------


def test_prepare_matryca_runtime_provisions_documented_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    l1 = _expected_sibling_l1(graph)
    ops = tmp_path / "logs" / "ops.jsonl"
    loguru = tmp_path / "logs" / "app.log"
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(ops))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(loguru))

    prepare_matryca_runtime(
        graph_root=graph,
        wiki_config=MatrycaWikiConfig(templates_subdir="custom-templates"),
    )

    assert ops.parent.is_dir()
    assert loguru.parent.is_dir()
    assert l1.is_dir()
    assert (l1 / "README.md").is_file()
    assert (graph / ".matryca_semantic_cache").is_dir()
    assert (graph / "custom-templates").is_dir()
    assert (graph / "matryca-wiki.yml").is_file()


def test_prepare_matryca_runtime_lazy_skips_ast_bootstrap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    bootstrap_calls: list[Path] = []

    def _bootstrap(self: object) -> object:
        bootstrap_calls.append(graph)
        raise AssertionError("bootstrap should not run when eager_graph=False")

    monkeypatch.setattr(
        "src.daemon.ast_cache.GraphAstCache.bootstrap",
        _bootstrap,
    )

    prepare_matryca_runtime(
        graph_root=graph,
        wiki_config=MatrycaWikiConfig(),
        eager_graph=False,
    )

    assert bootstrap_calls == []
    assert (graph / "matryca-wiki.yml").is_file()


def test_prepare_does_not_create_lazy_runtime_ledgers(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())

    assert not (graph / ".matryca_daemon_state.json").exists()
    assert not (graph / ".matryca_xray_state.json").exists()
    assert not (graph / ".matryca_plumber_daemon.pid").exists()
    assert not (graph / ".matryca_semantic_cache" / "master_catalog.json").exists()


# ---------------------------------------------------------------------------
# Environment-driven prepare
# ---------------------------------------------------------------------------


def test_try_prepare_from_env_with_valid_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.delenv("MATRYCA_L1_PATH", raising=False)
    monkeypatch.setattr("src.agent.plumber_config.reload_plumber_dotenv", lambda **_kw: None)

    try_prepare_matryca_runtime_from_env()

    assert _expected_sibling_l1(graph).is_dir()
    assert (graph / ".matryca_semantic_cache").is_dir()


def test_try_prepare_invalid_graph_still_ensures_logs_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _minimal_graph(tmp_path)
    ops = tmp_path / "fallback-logs" / "ops.log"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph / "no-pages-dir"))
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(ops))

    try_prepare_matryca_runtime_from_env()

    assert ops.parent.is_dir()
    assert not _expected_sibling_l1(graph).exists()


def test_collect_l1_excludes_readme_after_bootstrap(tmp_path: Path) -> None:
    graph = _minimal_graph(tmp_path)
    prepare_matryca_runtime(graph_root=graph, wiki_config=MatrycaWikiConfig())
    l1 = _expected_sibling_l1(graph)
    (l1 / "operator.md").write_text("ok", encoding="utf-8")

    names = {p.name for p in collect_l1_markdown_paths(logseq_graph_path=str(graph))}

    assert "operator.md" in names
    assert "README.md" not in names


# ---------------------------------------------------------------------------
# Wiki YAML patch helper
# ---------------------------------------------------------------------------


def test_patch_memory_path_in_wiki_yaml_replaces_existing_key() -> None:
    original = "namespaces:\n  - X\nmemory_path: ~/old\n"
    patched = _patch_memory_path_in_wiki_yaml(original, Path("/new/l1"))
    assert "memory_path: /new/l1" in patched
    assert "~/old" not in patched


def test_patch_memory_path_prepends_when_missing() -> None:
    patched = _patch_memory_path_in_wiki_yaml("namespaces:\n  - X\n", Path("/new/l1"))
    assert patched.startswith("memory_path: /new/l1")
