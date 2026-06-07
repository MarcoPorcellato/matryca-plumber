"""Hermes-style MCP stdio handshake: tools/list must complete within 30 seconds."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HANDSHAKE_TIMEOUT_S = 30.0


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    pages = graph / "pages"
    pages.mkdir(parents=True)
    (pages / "hello.md").write_text("- Hello from fixture\n", encoding="utf-8")
    return graph


@pytest.mark.asyncio
async def test_mcp_tools_list_handshake_within_30_seconds(tmp_path: Path) -> None:
    """MCP initialize + tools/list after lazy lifespan (no eager AST bootstrap)."""
    graph = _minimal_graph(tmp_path)
    env = {
        **os.environ,
        "MATRYCA_MCP_ENABLED": "true",
        "LOGSEQ_GRAPH_PATH": str(graph),
        "PYTHONPATH": str(_REPO_ROOT),
    }
    # Drop repo .env so the subprocess does not inherit a production vault path.
    env.pop("MATRYCA_L1_PATH", None)
    env.pop("MATRYCA_WIKI_CONFIG", None)

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.main"],
        env=env,
        cwd=str(_REPO_ROOT),
    )

    started = time.perf_counter()
    async with asyncio.timeout(_HANDSHAKE_TIMEOUT_S):
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()

    elapsed = time.perf_counter() - started
    names = sorted(tool.name for tool in result.tools)
    assert names == [
        "ingest_document",
        "mutate_graph",
        "read_graph_data",
        "refactor_blocks",
        "run_linter",
        "search_graph",
        "store_fact",
    ]
    assert elapsed < _HANDSHAKE_TIMEOUT_S
