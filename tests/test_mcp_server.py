"""Tests for MCP server models and outline validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from logseq_matryca_parser.agent_press import XRAY_STATE_FILENAME
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError
from src.agent.graph_dispatch import _headless_write_outline
from src.agent.graph_tool_helpers import (
    format_regex_search_markdown,
    parse_optional_json_query,
    read_block_ast_markdown,
    read_xray_page_markdown,
)
from src.agent.mcp_server import OutlineNode, register_mcp_tools
from src.agent.mcp_tool_guard import guard_mcp_tool
from src.agent.outline_models import validate_outline_for_write
from src.graph.safety.write_policy import GraphReadOnlyError


def test_mcp_registers_five_mega_tools() -> None:
    """Consolidated MCP surface exposes eight tools (mega-tools + memory + ingest + tana)."""
    app = FastMCP("matryca-test")
    register_mcp_tools(app)
    names = sorted(app._tool_manager._tools.keys())  # noqa: SLF001
    assert names == [
        "import_tana",
        "ingest_document",
        "mutate_graph",
        "read_graph_data",
        "refactor_blocks",
        "run_linter",
        "search_graph",
        "store_fact",
    ]


@pytest.mark.asyncio
async def test_guard_mcp_tool_returns_graph_read_only_error() -> None:
    @guard_mcp_tool
    async def sample() -> dict[str, Any]:
        raise GraphReadOnlyError(
            "write_outline",
            path="/tmp/graph/pages/Demo.md",
            reason="graph_root_mutation_blocked",
        )

    out = await sample()

    assert out["ok"] is False
    assert out["code"] == "graph_read_only"
    assert "graph read-only policy" in out["error"]


def test_parse_optional_json_query_accepts_plain_or_json() -> None:
    assert parse_optional_json_query("") == {}
    assert parse_optional_json_query("alpha") == {}
    assert parse_optional_json_query('{"days": 3}') == {"days": 3}


def test_read_block_ast_markdown_returns_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    block_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    (pages / "Demo.md").write_text(
        f"- Parent\n  id:: {block_id}\n  - Child bullet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    md = read_block_ast_markdown(str(tmp_path), f"Demo|{block_id}")
    assert "Child bullet" in md
    assert block_id in md


def test_read_block_ast_markdown_resolves_xray_alias(tmp_path: Path) -> None:
    """``read_block_ast`` accepts ``Page|[n]`` after ``xray_page`` populates alias state."""
    pages = tmp_path / "pages"
    pages.mkdir()
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    (pages / "Alias Demo.md").write_text(
        f"- Parent bullet\n  id:: {block_id}\n",
        encoding="utf-8",
    )
    read_xray_page_markdown(str(tmp_path), "Alias Demo")
    md = read_block_ast_markdown(str(tmp_path), "Alias Demo|[0]")
    assert "Parent bullet" in md
    assert block_id in md


def test_format_regex_search_markdown_finds_line(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Hit.md").write_text("- TODO fix parser\n", encoding="utf-8")
    report = format_regex_search_markdown(str(tmp_path), r"TODO", limit=10)
    assert "Hit.md" in report
    assert "TODO" in report


def test_outline_node_validates_nested_hierarchy() -> None:
    """``OutlineNode`` should accept nested JSON and preserve parent/child structure."""
    payload: dict[str, object] = {
        "text": "Root thesis",
        "properties": {"tags::": "[[AI]]"},
        "children": [
            {
                "text": "Supporting claim",
                "children": [{"text": "Evidence leaf", "properties": {}, "children": []}],
            },
        ],
    }
    node = OutlineNode.model_validate(payload)
    assert node.text == "Root thesis"
    assert len(node.children) == 1
    assert node.children[0].text == "Supporting claim"
    assert node.children[0].children[0].text == "Evidence leaf"


def test_outline_knowledge_requires_domain_when_typed() -> None:
    """Knowledge ``page_type`` without ``domain`` must fail validation."""
    with pytest.raises(ValidationError):
        OutlineNode.model_validate({"text": "Note", "page_type": "knowledge"})


def test_outline_entity_merges_entity_type_into_properties() -> None:
    """Entity nodes merge ``entity-type::`` for Logseq."""
    node = OutlineNode.model_validate(
        {
            "text": "Tool X",
            "page_type": "entity",
            "entity_type": "tool",
        },
    )
    assert node.properties.get("type::") == "entity"
    assert node.properties.get("entity-type::") == "tool"


def test_outline_child_without_schema_fields() -> None:
    """Nested bullets may omit schema fields when the parent carries classification."""
    node = OutlineNode.model_validate(
        {
            "text": "Root",
            "page_type": "knowledge",
            "domain": "tech",
            "children": [{"text": "Evidence", "properties": {"source::": "[[Paper]]"}}],
        },
    )
    assert node.children[0].properties.get("source::") == "[[Paper]]"


def test_outline_heading_level_coerces_int_in_properties() -> None:
    """Parser round-trip: ``properties.heading_level`` int is hoisted and coerced to str."""
    node = validate_outline_for_write(
        {
            "text": "### Section A",
            "properties": {"heading_level": 3, "id": "aaa-bbb-ccc"},
        },
    )
    assert node.heading_level == "3"
    assert "heading_level" not in node.properties
    assert "heading_level::" not in node.properties
    assert node.properties.get("id") == "aaa-bbb-ccc"


def test_outline_heading_level_coerces_int_top_level() -> None:
    """Top-level ``heading_level: 2`` is accepted as the string ``\"2\"``."""
    node = OutlineNode.model_validate({"text": "Title", "heading_level": 2})
    assert node.heading_level == "2"
    assert "heading_level" not in node.properties


def test_headless_write_outline_strips_heading_level_from_disk(tmp_path: Path) -> None:
    """``write_outline`` must not persist parser metadata as ``heading_level::`` on disk."""
    pages = tmp_path / "pages"
    pages.mkdir()
    parent_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    (pages / "Demo.md").write_text(
        f"- Root page block\n  id:: {parent_id}\n",
        encoding="utf-8",
    )

    outline: dict[str, Any] = {
        "text": "### Section A",
        "properties": {"heading_level": 3},
    }
    out = _headless_write_outline(str(tmp_path), parent_id, outline)

    assert out.get("ok") is True
    page_text = (pages / "Demo.md").read_text(encoding="utf-8")
    assert "heading_level::" not in page_text
    assert "Section A" in page_text


def test_headless_append_child_without_trailing_newline(tmp_path: Path) -> None:
    """Append on a page file missing a final newline must not splice onto the last line."""
    pages = tmp_path / "pages"
    pages.mkdir()
    parent_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    # No trailing newline after id:: line (parser #72 / 1.4.2 parity).
    (pages / "NoNewline.md").write_bytes(
        f"- Root page block\n  id:: {parent_id}".encode(),
    )

    outline: dict[str, Any] = {"text": "Appended child", "children": []}
    out = _headless_write_outline(str(tmp_path), parent_id, outline)

    assert out.get("ok") is True
    page_text = (pages / "NoNewline.md").read_text(encoding="utf-8")
    lines = page_text.splitlines()
    assert any(line.strip() == "- Appended child" for line in lines)
    assert not any("id:: Appended" in line for line in lines)


def test_headless_write_outline_chains_parent_uuids(tmp_path: Path) -> None:
    """Headless outline write creates nested blocks with chained UUIDs on disk."""
    pages = tmp_path / "pages"
    pages.mkdir()
    parent_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    (pages / "Demo.md").write_text(
        f"- Root page block\n  id:: {parent_id}\n",
        encoding="utf-8",
    )

    outline: dict[str, Any] = {
        "text": "Root",
        "children": [{"text": "Child", "children": [{"text": "Grandchild"}]}],
    }
    out = _headless_write_outline(str(tmp_path), parent_id, outline)

    assert out.get("ok") is True
    assert len(out["uuids"]) == 3
    assert "routing_hint" in out
    assert "L2" in out["routing_hint"]
    assert out.get("outline_block_count") == 3
    assert "git_snapshot" in out

    page_text = (pages / "Demo.md").read_text(encoding="utf-8")
    assert "Root" in page_text
    assert "Child" in page_text
    assert "Grandchild" in page_text
    for block_uuid in out["uuids"]:
        assert block_uuid in page_text


def test_xray_page_persists_state_file(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    (pages / "Alias Demo.md").write_text(
        f"- Parent bullet\n  id:: {block_id}\n",
        encoding="utf-8",
    )
    from src.agent.graph_tool_helpers import read_xray_page_markdown

    md = read_xray_page_markdown(str(tmp_path), "Alias Demo")
    assert "[0]" in md
    assert (tmp_path / XRAY_STATE_FILENAME).is_file()


def test_xray_page_read_only_uses_external_alias_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    page = pages / "Alias Demo.md"
    page.write_text(f"- Parent bullet\n  id:: {block_id}\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path.parent / "external-cache"))
    before = page.read_bytes()

    md = read_xray_page_markdown(str(tmp_path), "Alias Demo")

    assert "[0]" in md
    assert "external runtime cache" in md
    assert page.read_bytes() == before
    assert not (tmp_path / XRAY_STATE_FILENAME).exists()
    assert block_id in read_block_ast_markdown(str(tmp_path), "Alias Demo|[0]")
