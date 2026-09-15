"""Parity tests for GraphReadPort / MarkdownGraphRepository (v2 Phase 1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import src.agent.markdown_graph_repository as markdown_graph_repository
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port
from src.agent.shadow_graph_repository import ShadowGraphRepository


@pytest.mark.parametrize(
    ("shadow_ready", "expected_type"),
    [
        (False, MarkdownGraphRepository),
        (True, ShadowGraphRepository),
    ],
)
def test_select_graph_read_port_returns_port_matching_shadow_readiness(
    shadow_ready: bool,
    expected_type: type[MarkdownGraphRepository] | type[ShadowGraphRepository],
) -> None:
    """Catches a selector that maps readiness to the wrong concrete read port."""
    assert isinstance(
        markdown_graph_repository._select_graph_read_port(shadow_ready=shadow_ready),
        expected_type,
    )


def test_get_graph_read_port_returns_markdown_adapter(tmp_path: Path) -> None:
    port = get_graph_read_port(tmp_path)
    assert isinstance(port, MarkdownGraphRepository)


def test_get_graph_read_port_without_root_skips_shadow_and_root_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(_root: Path) -> bool:
        raise AssertionError("a rootless selection must not inspect Shadow state")

    def unexpected_resolution(_root: Path) -> Path:
        raise AssertionError("rootless selection must not resolve a root")

    monkeypatch.setattr(markdown_graph_repository, "shadow_read_port_ready", unexpected_call)
    monkeypatch.setattr(markdown_graph_repository, "resolved_graph_root", unexpected_resolution)

    assert isinstance(get_graph_read_port(), MarkdownGraphRepository)


def test_get_graph_read_port_checks_shadow_before_markdown_root_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path]] = []

    def shadow_not_ready(root: Path) -> bool:
        calls.append(("shadow", root))
        return False

    def resolve_root(root: Path) -> Path:
        calls.append(("resolve", root))
        return root

    monkeypatch.setattr(markdown_graph_repository, "shadow_read_port_ready", shadow_not_ready)
    monkeypatch.setattr(markdown_graph_repository, "resolved_graph_root", resolve_root)

    assert isinstance(get_graph_read_port(tmp_path), MarkdownGraphRepository)
    assert calls == [("shadow", tmp_path), ("resolve", tmp_path)]


def test_get_graph_read_port_returns_shadow_without_markdown_root_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_resolution(_root: Path) -> Path:
        raise AssertionError("ready Shadow must be selected first")

    monkeypatch.setattr(markdown_graph_repository, "shadow_read_port_ready", lambda _root: True)
    monkeypatch.setattr(markdown_graph_repository, "resolved_graph_root", unexpected_resolution)

    assert isinstance(get_graph_read_port(tmp_path), ShadowGraphRepository)


def test_get_graph_read_port_propagates_markdown_root_resolution_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(markdown_graph_repository, "shadow_read_port_ready", lambda _root: False)

    def reject_root(_root: Path) -> Path:
        raise ValueError("invalid graph root")

    monkeypatch.setattr(markdown_graph_repository, "resolved_graph_root", reject_root)

    with pytest.raises(ValueError, match="invalid graph root"):
        get_graph_read_port(tmp_path)


def test_read_subtree_markdown_port_matches_direct_helper(tmp_path: Path) -> None:
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Demo.md").write_text(
        f"- Root\n  id:: {block_id}\n  - child\n",
        encoding="utf-8",
    )
    query = json.dumps({"page": "Demo", "block_uuid": block_id})
    repo = MarkdownGraphRepository()
    via_port = repo.read_subtree_markdown(tmp_path, query)
    via_helper = read_subtree_markdown(str(tmp_path), query)
    assert via_port == via_helper
    assert "child" in via_port


@pytest.mark.asyncio
async def test_read_page_spatial_port_delegates_to_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir(parents=True)
    (pages / "Note.md").write_text("- hello\n", encoding="utf-8")

    async def fake_spatial(title: str, graph_path: str) -> str:
        assert title == "Note"
        assert graph_path == str(tmp_path)
        return "# spatial body"

    monkeypatch.setattr(
        "src.agent.markdown_graph_repository.get_page_spatial_context",
        fake_spatial,
    )
    repo = MarkdownGraphRepository()
    body = await repo.read_page_spatial_markdown(tmp_path, "Note")
    assert body == "# spatial body"
