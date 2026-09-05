"""Parser adapter behavior for the OG identity-only session slice."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from src.agent.og_parser_identity_adapter import ParserOgIdentityAdapter
from src.graph.session_read_models import GraphSessionReadError


def test_parser_adapter_returns_opaque_plumber_identity_for_one_safe_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if adapter leaks Parser objects or derives identity outside selected OG source."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    page.write_text("- root\n", encoding="utf-8")

    class _ParsedPage:
        title = "Selected"

    class _Parser:
        def parse_page_file(self, path: str) -> _ParsedPage:
            assert path == str(page)
            return _ParsedPage()

    monkeypatch.setattr("src.agent.og_parser_identity_adapter.LogosParser", _Parser)

    identity = ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")

    assert identity.graph_id == hashlib.sha256(str(tmp_path.resolve()).encode()).hexdigest()[:32]
    assert identity.source_revision == hashlib.sha256(b"- root\n").hexdigest()[:32]


def test_parser_adapter_rejects_path_traversal_before_parsing(tmp_path: Path) -> None:
    """Breaks if an unsafe page reference reaches Parser file access."""
    with pytest.raises(GraphSessionReadError, match="invalid OG page reference"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "../outside")


def test_parser_adapter_normalizes_parser_failures_to_a_closed_boundary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a Parser implementation exception escapes the Plumber boundary."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Selected.md").write_text("- root\n", encoding="utf-8")

    class _FailingParser:
        def parse_page_file(self, path: str) -> None:
            raise RuntimeError("parser internals")

    monkeypatch.setattr("src.agent.og_parser_identity_adapter.LogosParser", _FailingParser)

    with pytest.raises(GraphSessionReadError, match="OG Parser identity read failed"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")
