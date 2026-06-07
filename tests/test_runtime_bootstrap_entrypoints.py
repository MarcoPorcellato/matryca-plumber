"""Ensure every Matryca entry surface invokes runtime bootstrap before graph work."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from src.agent.maintenance_daemon import MaintenanceDaemon, start_daemon_foreground


@pytest.fixture(autouse=True)
def _isolate_graph_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_L1_PATH", raising=False)


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def test_cli_main_calls_try_prepare_before_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from src.cli import main as cli_main

    order: list[str] = []

    monkeypatch.setattr(
        "src.cli.try_prepare_matryca_runtime_from_env",
        lambda: order.append("prepare"),
    )

    async def _run_cli(_args: object) -> int:
        order.append("dispatch")
        return 0

    def _asyncio_run(coro: object) -> int:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)  # type: ignore[arg-type]
        finally:
            loop.close()

    monkeypatch.setattr("src.cli.run_cli", _run_cli)
    monkeypatch.setattr("src.cli.asyncio.run", _asyncio_run)

    with pytest.raises(SystemExit) as exc:
        cli_main(["read", "memory"])

    assert exc.value.code == 0
    assert order == ["prepare", "dispatch"]


@pytest.mark.asyncio
async def test_mcp_lifespan_calls_prepare_before_yield(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.main import app_lifespan

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    calls: list[dict[str, object]] = []

    def _prepare(
        *,
        graph_root: Path | None,
        wiki_config: object,
        eager_graph: bool = True,
    ) -> None:
        calls.append(
            {"graph_root": graph_root, "wiki_config": wiki_config, "eager_graph": eager_graph},
        )

    monkeypatch.setattr("src.main.prepare_matryca_runtime", _prepare)
    monkeypatch.setattr("src.main.sweep_dangling_atomic_tmp_files", lambda _p: 0)

    async with app_lifespan(MagicMock()):
        pass

    assert len(calls) == 1
    graph_root = calls[0]["graph_root"]
    assert isinstance(graph_root, Path)
    assert graph_root.resolve() == graph.resolve()
    assert calls[0]["eager_graph"] is False


def test_start_daemon_foreground_calls_prepare(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    graph = _minimal_graph(tmp_path)
    prepared: list[Path | None] = []

    def _prepare(*, graph_root: Path | None, wiki_config: object) -> None:
        prepared.append(graph_root)

    daemon = MagicMock()
    monkeypatch.setattr("src.agent.maintenance_daemon.prepare_matryca_runtime", _prepare)
    monkeypatch.setattr("src.agent.maintenance_daemon.configure_loguru", lambda: None)
    monkeypatch.setattr("src.agent.maintenance_daemon.reload_plumber_dotenv", lambda: None)
    monkeypatch.setattr(
        "src.agent.maintenance_daemon._try_acquire_daemon_process_lock",
        lambda _r: 42,
    )
    monkeypatch.setattr("src.agent.maintenance_daemon.MaintenanceDaemon", lambda root, **kw: daemon)

    start_daemon_foreground(graph)

    assert prepared == [graph.resolve()]
    daemon.run_forever.assert_called_once()


def test_daemon_run_forever_prepares_before_bootstrap_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    graph = _minimal_graph(tmp_path)
    order: list[str] = []

    monkeypatch.setattr(
        "src.agent.maintenance_daemon.prepare_matryca_runtime",
        lambda **kw: order.append("prepare"),
    )
    monkeypatch.setattr(MaintenanceDaemon, "_register_daemon_signal_handlers", lambda self: None)
    monkeypatch.setattr("src.agent.maintenance_daemon.write_pid_file", lambda _r: None)
    monkeypatch.setattr("src.agent.maintenance_daemon.load_daemon_state", lambda _r: MagicMock())
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.load_plumber_lint_config",
        lambda: MagicMock(),
    )
    monkeypatch.setattr(MaintenanceDaemon, "_sync_runtime_config", lambda self, s: s)
    monkeypatch.setattr(MaintenanceDaemon, "_hydrate_bootstrap_phase", lambda self, s: None)
    monkeypatch.setattr(MaintenanceDaemon, "_hydrate_token_logger_from_state", lambda self, s: None)
    monkeypatch.setattr("src.agent.maintenance_daemon.save_daemon_state", lambda *a, **k: None)
    monkeypatch.setattr(MaintenanceDaemon, "_finalize_graceful_shutdown", lambda self, s=None: None)

    def _bootstrap(self: MaintenanceDaemon, state: object = None) -> None:
        order.append("bootstrap")
        self._stop_requested = True

    monkeypatch.setattr(MaintenanceDaemon, "run_bootstrap_pipeline", _bootstrap)
    monkeypatch.setattr(MaintenanceDaemon, "run_cycle", lambda self, s: s)

    MaintenanceDaemon(graph).run_forever()

    assert order == ["prepare", "bootstrap"]


def test_ui_lifespan_calls_try_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli.ui_server import _ui_app_lifespan

    called = False

    def _prepare() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("src.cli.ui_server.try_prepare_matryca_runtime_from_env", _prepare)
    monkeypatch.setattr("src.cli.ui_server._ensure_graph_root_env_loaded", lambda: None)

    async def _run() -> None:
        async with _ui_app_lifespan(MagicMock()):
            pass

    import asyncio

    asyncio.run(_run())
    assert called is True
