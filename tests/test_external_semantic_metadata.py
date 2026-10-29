"""MCP metadata describes both semantic backends without implying graph writes."""

import pytest
from mcp.server.fastmcp import FastMCP
from src.agent.mcp_server import register_mcp_tools


@pytest.mark.asyncio
async def test_semantic_metadata_describes_external_read_only_snapshot() -> None:
    app = FastMCP("external-semantic-contract")
    register_mcp_tools(app)
    tools = await app.list_tools()
    search = next(tool for tool in tools if tool.name == "search_graph")
    description = " ".join((search.description or "").split())
    assert "MATRYCA_EXTERNAL_SEMANTIC_ENABLED" in description
    assert "external" in description and "snapshot" in description
    assert "does not build" in description
    assert "MATRYCA_DUAL_EMBEDDING_ENABLED" in description
    assert "no vector DB" not in description
