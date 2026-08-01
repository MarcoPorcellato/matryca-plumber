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
    eager_flags: list[bool] = []

    def _prepare(*, eager_graph: bool = True) -> None:
        order.append("prepare")
        eager_flags.append(eager_graph)

    monkeypatch.setattr("src.cli.try_prepare_matryca_runtime_from_env", _prepare)

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
    assert eager_flags == [True]


def test_cli_main_read_only_read_path_skips_graph_local_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.cli import main as cli_main

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(tmp_path / "logs" / "ops.log"))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(tmp_path / "logs" / "app.log"))
    monkeypatch.setattr(
        "src.utils.runtime_bootstrap.ensure_repo_dotenv_from_example",
        lambda **_kw: False,
    )
    monkeypatch.setattr(
        "src.agent.plumber_config.reload_plumber_dotenv",
        lambda **_kw: None,
    )

    def _blocked(*_args: object, **_kwargs: object) -> None:
        pytest.fail("read-only CLI bootstrap must not touch graph-local runtime artifacts")

    monkeypatch.setattr("src.utils.runtime_bootstrap.ensure_matryca_l1_dir", _blocked)
    monkeypatch.setattr("src.utils.runtime_bootstrap.ensure_graph_runtime_directories", _blocked)
    monkeypatch.setattr("src.utils.runtime_bootstrap.ensure_matryca_wiki_config_file", _blocked)
    monkeypatch.setattr("src.daemon.register_daemon_post_write_hooks", _blocked)
    monkeypatch.setattr("src.shadow.bootstrap.ensure_shadow_runtime_at_startup", _blocked)

    async def _run_cli(_args: object) -> int:
        return 0

    monkeypatch.setattr("src.cli.run_cli", _run_cli)

    with pytest.raises(SystemExit) as exc:
        cli_main(["read", "memory"])

    assert exc.value.code == 0
    assert not (graph / ".matryca_semantic_cache").exists()
    assert not (graph / "templates").exists()
    assert not (graph / "matryca-wiki.yml").exists()
    assert not (tmp_path / "matryca-l1").exists()


def test_cli_main_rejects_read_only_write_before_prepare(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.cli import main as cli_main

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setattr(
        "src.cli.try_prepare_matryca_runtime_from_env",
        lambda **_kwargs: pytest.fail("bootstrap must not run"),
    )

    with pytest.raises(SystemExit) as exc:
        cli_main(
            [
                "mutate",
                "write_outline",
                "--target",
                "parent-uuid",
                "--payload",
                '{"text":"x","children":[]}',
            ],
        )

    assert exc.value.code == 1


def test_cli_eager_graph_route_matrix() -> None:
    from argparse import Namespace

    from src.cli import _cli_eager_graph

    assert _cli_eager_graph(Namespace(command="search", method="bm25")) is False
    assert _cli_eager_graph(Namespace(command="search", method="regex")) is True
    assert _cli_eager_graph(Namespace(command="search", method="semantic")) is True
    assert _cli_eager_graph(Namespace(command="read", method=None)) is True
    assert _cli_eager_graph(Namespace(command="lint", method=None)) is True


@pytest.mark.asyncio
async def test_cli_rejects_read_only_write_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from argparse import Namespace

    from src.cli import run_cli

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    called = {"mutate": False}

    async def _dispatch_mutate(*args: object, **kwargs: object) -> dict[str, object]:
        called["mutate"] = True
        return {"ok": True}

    monkeypatch.setattr("src.cli.dispatch_mutate", _dispatch_mutate)

    code = await run_cli(
        Namespace(
            command="mutate",
            action="write_outline",
            target="parent-uuid",
            payload='{"text":"x","children":[]}',
            json=False,
        ),
    )

    assert code == 1
    assert called["mutate"] is False


@pytest.mark.asyncio
async def test_cli_allows_dry_run_append_journal_under_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from argparse import Namespace

    from src.cli import run_cli

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    called = {"mutate": False}

    async def _dispatch_mutate(*args: object, **kwargs: object) -> dict[str, object]:
        called["mutate"] = True
        return {"ok": True, "dry_run": True}

    monkeypatch.setattr("src.cli.dispatch_mutate", _dispatch_mutate)

    code = await run_cli(
        Namespace(
            command="mutate",
            action="append_journal",
            target="",
            payload='{"markdown_body":"- dry run note","dry_run":true}',
            json=False,
        ),
    )

    assert code == 0
    assert called["mutate"] is True


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


@pytest.mark.asyncio
async def test_mcp_lifespan_skips_graph_writes_in_read_only_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.main import app_lifespan

    graph = _minimal_graph(tmp_path)
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setattr(
        "src.main.prepare_matryca_runtime",
        lambda **_kwargs: pytest.fail("bootstrap must not run"),
    )
    monkeypatch.setattr(
        "src.main.sweep_dangling_atomic_tmp_files",
        lambda _path: pytest.fail("sweep must not run"),
    )

    async with app_lifespan(MagicMock()):
        pass


def test_start_daemon_foreground_defers_prepare_to_run_forever(
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
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.register_bootstrap_shutdown_handlers",
        lambda _r: None,
    )
    monkeypatch.setattr("src.agent.maintenance_daemon.MaintenanceDaemon", lambda root, **kw: daemon)

    start_daemon_foreground(graph)

    assert prepared == []
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


def test_ui_lifespan_calls_try_prepare_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli.ui_server import _ui_app_lifespan

    calls: list[bool] = []

    def _prepare(*, eager_graph: bool = True) -> None:
        calls.append(eager_graph)

    monkeypatch.setattr("src.cli.ui_server.try_prepare_matryca_runtime_from_env", _prepare)
    monkeypatch.setattr("src.cli.ui_server._ensure_graph_root_env_loaded", lambda: None)

    async def _run() -> None:
        async with _ui_app_lifespan(MagicMock()):
            pass

    import asyncio

    asyncio.run(_run())
    assert calls == [False]


def test_cli_ui_skips_eager_prepare_before_run_ui_server(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli import main as cli_main

    order: list[str] = []

    monkeypatch.setattr(
        "src.cli.try_prepare_matryca_runtime_from_env",
        lambda **kwargs: order.append(f"prepare:eager={kwargs.get('eager_graph', True)}"),
    )
    monkeypatch.setattr("src.cli.run_ui_server", lambda: order.append("ui"))

    with pytest.raises(SystemExit) as exc:
        cli_main(["plumber", "ui"])

    assert exc.value.code == 0
    assert order == ["ui"]
