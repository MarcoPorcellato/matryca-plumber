"""The outer MCP identity boundary must preserve finite dashboard failures."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from src.agent import dashboard_job as jobs
from src.agent import dashboard_process as runtime
from src.agent import mcp_server
from src.agent.dashboard_protocol import DashboardLimits, DashboardOutcome
from src.agent.mcp_tool_guard import guard_mcp_tool
from src.config import MatrycaWikiConfig
from src.daemon import config_layer

from tests.test_dashboard_job import _until


@pytest.mark.asyncio
@pytest.mark.parametrize("positional", [False, True])
async def test_dashboard_mcp_identity_wrapper_preserves_failure_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, positional: bool
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    class SyntheticIdentity:
        def format_system_section(self) -> str:
            return "Synthetic identity context"

    monkeypatch.setattr(config_layer, "_resolved_graph_root_from_env", lambda: tmp_path)
    monkeypatch.setattr(config_layer, "get_identity_store", lambda _root: SyntheticIdentity())

    @guard_mcp_tool
    async def read_graph_data(target_type: str, query: str = "") -> str:
        return DashboardOutcome(
            code="dashboard_timeout", elapsed_ms=120000, last_phase="refs", cleanup_verified=True
        ).public_text()

    response = await (
        read_graph_data("dashboard") if positional else read_graph_data(target_type="dashboard")
    )
    try:
        payload = json.loads(response)
    except json.JSONDecodeError:
        pytest.fail("MCP identity postprocessing corrupts the structured dashboard failure")
    assert payload["code"] == "dashboard_timeout"
    assert payload["cleanup_verified"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target,name,platform",
    [
        ("page", "read_graph_data", "darwin"),
        ("dashboard", "other_tool", "darwin"),
        ("dashboard", "read_graph_data", "win32"),
    ],
)
async def test_dashboard_identity_exception_does_not_change_other_tools_or_windows(
    monkeypatch: pytest.MonkeyPatch, target: str, name: str, platform: str
) -> None:
    async def result(target_type: str) -> str:
        return "- result"

    result.__name__ = name
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(
        "src.agent.mcp_tool_guard.append_identity_to_mcp_payload",
        lambda body: body + "\nidentity unchanged",
    )
    assert await guard_mcp_tool(result)(target) == "- result\nidentity unchanged"


@pytest.mark.asyncio
async def test_dashboard_mcp_has_no_out_of_budget_identity_or_notification_await(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")

    async def bounded(_config: MatrycaWikiConfig, target_type: str, query: str) -> str:
        assert target_type == "dashboard"
        assert jobs.dashboard_identity_owned.get()
        return DashboardOutcome(
            code="dashboard_timeout", elapsed_ms=120000, cleanup_verified=True
        ).public_text()

    async def forbidden_notification(*_args: object, **_kwargs: object) -> None:
        pytest.fail("dashboard notification outside bounded owner")

    def forbidden_identity(_body: object) -> str:
        pytest.fail("parent dashboard identity read outside bounded owner")

    monkeypatch.setattr(mcp_server, "dispatch_read", bounded)
    monkeypatch.setattr(mcp_server, "mcp_tool_info", forbidden_notification)
    monkeypatch.setattr(
        "src.agent.mcp_tool_guard.append_identity_to_mcp_payload", forbidden_identity
    )
    app = FastMCP("dashboard-boundary")
    mcp_server.register_mcp_tools(app)
    tool = app._tool_manager.get_tool("read_graph_data")
    assert tool is not None
    context = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=mcp_server.AppContext(wiki_config=MatrycaWikiConfig())
        )
    )
    body = await tool.fn(ctx=context, target_type="dashboard", query="ignored")
    assert json.loads(body)["code"] == "dashboard_timeout"
    assert not jobs.dashboard_identity_owned.get()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")
async def test_dashboard_mcp_cancel_notification_reaches_owner_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anyio
    import mcp.types as types
    from mcp.shared.exceptions import McpError
    from mcp.shared.memory import create_connected_server_and_client_session

    pool = jobs._DashboardJobs()
    children: list[subprocess.Popen[bytes]] = []
    original = subprocess.Popen

    def retain(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", retain)
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(20)"],
            dict(os.environ),
            tmp_path,
        ),
    )

    async def bounded(_config: MatrycaWikiConfig, target_type: str, query: str) -> str:
        return await pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=2.0, cleanup_s=1.0)
        )

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[mcp_server.AppContext]:
        yield mcp_server.AppContext(wiki_config=MatrycaWikiConfig())

    monkeypatch.setattr(mcp_server, "dispatch_read", bounded)
    app = FastMCP("dashboard-notification", lifespan=lifespan)
    mcp_server.register_mcp_tools(app)
    with anyio.fail_after(5):
        async with create_connected_server_and_client_session(app) as client:
            pending = asyncio.create_task(
                client.call_tool(
                    "read_graph_data", {"target_type": "dashboard", "query": "ignored"}
                )
            )
            try:
                await _until(lambda: bool(children))
                assert children
                request_id = client._request_id - 1
                await client.send_notification(
                    types.ClientNotification(
                        types.CancelledNotification(
                            params=types.CancelledNotificationParams(
                                requestId=request_id, reason="synthetic owner cancellation"
                            )
                        )
                    )
                )
                with pytest.raises(McpError, match="cancel"):
                    await pending
                await _until(lambda: pool._active is None)
                assert pool._active is None
            finally:
                if pool._active is not None:
                    pool._active.control.request_cancel()
                if not pending.done():
                    pending.cancel()
                    with suppress(asyncio.CancelledError, McpError):
                        await pending
    assert children[0].returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(children[0].pid, 0)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")
async def test_dashboard_client_local_timeout_does_not_claim_server_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import anyio
    from mcp.shared.memory import create_connected_server_and_client_session

    pool = jobs._DashboardJobs()
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(20)"],
            dict(os.environ),
            tmp_path,
        ),
    )

    async def bounded(_config: MatrycaWikiConfig, target_type: str, query: str) -> str:
        return await pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=0.3, cleanup_s=1.0)
        )

    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[mcp_server.AppContext]:
        yield mcp_server.AppContext(wiki_config=MatrycaWikiConfig())

    monkeypatch.setattr(mcp_server, "dispatch_read", bounded)
    app = FastMCP("dashboard-local-timeout", lifespan=lifespan)
    mcp_server.register_mcp_tools(app)
    with anyio.fail_after(5):
        async with create_connected_server_and_client_session(app) as client:
            pending = asyncio.create_task(
                client.call_tool("read_graph_data", {"target_type": "dashboard"})
            )
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(pending), timeout=0.05)
            assert pool._active is not None
            assert not pool._active.control.cancelled.is_set()
            result = await pending
            text = next(item.text for item in result.content if item.type == "text")
            assert json.loads(text)["code"] == "dashboard_timeout"
            assert json.loads(text)["cleanup_verified"]
            assert pool._active is None
