"""Tests for onboarding L1 provisioning."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.agent.l1_memory import default_matryca_l1_directory_for_graph
from src.config import MatrycaWikiConfig
from src.utils.provision_l1 import (
    clear_matryca_l1_path_placeholder_in_dotenv,
    provision_matryca_l1_sibling,
)


def test_clear_matryca_l1_path_placeholder_in_dotenv(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'LOGSEQ_GRAPH_PATH="/vault"\nMATRYCA_L1_PATH="/absolute/path/to/matryca-l1"\n',
        encoding="utf-8",
    )
    changed = clear_matryca_l1_path_placeholder_in_dotenv(repo_root=tmp_path)
    assert changed is True
    text = env_path.read_text(encoding="utf-8")
    assert "MATRYCA_L1_PATH=/absolute" not in text
    assert "cleared template" in text


def test_provision_matryca_l1_sibling_creates_next_to_vault(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    env_path = tmp_path / ".env"
    env_path.write_text(
        f'LOGSEQ_GRAPH_PATH="{graph}"\nMATRYCA_L1_PATH="/absolute/path/to/matryca-l1"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_L1_PATH", "/absolute/path/to/matryca-l1")
    monkeypatch.setattr(
        "src.utils.provision_l1.load_matryca_wiki_config",
        lambda: MatrycaWikiConfig(),
    )
    # Repo ``.env`` must not override explicit test env (``reload_plumber_dotenv`` loads git root).
    monkeypatch.setattr("src.utils.provision_l1.reload_plumber_dotenv", lambda **_kw: None)

    l1_dir = provision_matryca_l1_sibling(graph_root=graph, repo_root=tmp_path)

    assert l1_dir == default_matryca_l1_directory_for_graph(graph)
    assert l1_dir.is_dir()
    assert (l1_dir / "session-rules.md").is_file()
    wiki = graph / "matryca-wiki.yml"
    assert wiki.is_file()
    assert f"memory_path: {l1_dir}" in wiki.read_text(encoding="utf-8")
