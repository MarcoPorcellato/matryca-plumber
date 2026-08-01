"""Contract tests for the side-effect-free strict read-only daemon profile."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from src.agent.daemon_read_only_profile import (
    READ_ONLY_DISABLED_DUTIES,
    ReadOnlyDaemonProfileError,
    active_daemon_profile,
    prepare_read_only_daemon_environment,
)
from src.agent.maintenance_daemon import (
    DaemonState,
    MaintenanceDaemon,
    start_daemon_detached,
    start_daemon_foreground,
)
from src.cli.ui_server import _build_daemon_state_response


def _graph(tmp_path: Path) -> Path:
    graph = tmp_path / "graph"
    (graph / "pages").mkdir(parents=True)
    (graph / "pages" / "Observed.md").write_text("- unchanged\n", encoding="utf-8")
    return graph


def _read_only_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, graph: Path) -> None:
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path / "external-cache"))


def test_prepare_read_only_daemon_environment_routes_logs_outside_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    _read_only_env(monkeypatch, tmp_path, graph)

    daemon_dir = prepare_read_only_daemon_environment(graph)

    assert active_daemon_profile() == "read_only_shadow_observer"
    assert not daemon_dir.is_relative_to(graph.resolve())
    assert Path(os.environ["MATRYCA_PLUMBER_LOG_PATH"]).parent == daemon_dir
    assert Path(os.environ["MATRYCA_LOGURU_LOG_PATH"]).parent == daemon_dir


def test_prepare_read_only_daemon_environment_requires_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    _read_only_env(monkeypatch, tmp_path, graph)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")

    with pytest.raises(ReadOnlyDaemonProfileError, match="shadow_disabled"):
        prepare_read_only_daemon_environment(graph)


def test_run_forever_read_only_runs_only_shadow_observer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    before = {
        path.relative_to(graph): path.read_bytes() for path in graph.rglob("*") if path.is_file()
    }
    _read_only_env(monkeypatch, tmp_path, graph)
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(tmp_path / "external-ops.jsonl"))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(tmp_path / "external-daemon.log"))

    daemon = MaintenanceDaemon(graph, llm_client=MagicMock(), poll_seconds=0.01)
    monkeypatch.setattr(daemon, "_register_daemon_signal_handlers", lambda: None)
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.prepare_matryca_runtime",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        daemon,
        "run_bootstrap_pipeline",
        lambda *_args, **_kwargs: pytest.fail("read-only observer ran LLM bootstrap"),
    )
    monkeypatch.setattr(
        daemon,
        "run_cycle",
        lambda *_args, **_kwargs: pytest.fail("read-only observer ran mutating duty cycle"),
    )
    stopped: list[bool] = []

    def _start() -> None:
        daemon._stop_requested = True

    monkeypatch.setattr(daemon, "_start_file_watcher", _start)
    monkeypatch.setattr(daemon, "_stop_file_watcher", lambda: stopped.append(True))

    daemon.run_forever()

    after = {
        path.relative_to(graph): path.read_bytes() for path in graph.rglob("*") if path.is_file()
    }
    assert after == before
    assert stopped == [True]
    assert "graph_local_state" in READ_ONLY_DISABLED_DUTIES


def test_start_daemon_foreground_read_only_skips_graph_control_files_and_llm_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    _read_only_env(monkeypatch, tmp_path, graph)
    order: list[str] = []
    daemon = MagicMock()

    def _prepare_profile(_root: Path) -> Path:
        order.append("profile")
        return tmp_path / "external-cache"

    monkeypatch.setattr("src.agent.maintenance_daemon.reload_plumber_dotenv", lambda: None)
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.prepare_read_only_daemon_environment",
        _prepare_profile,
    )
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.configure_loguru",
        lambda: order.append("logs"),
    )
    monkeypatch.setattr("src.agent.maintenance_daemon.load_plumber_lint_config", MagicMock())
    monkeypatch.setattr(
        "src.agent.maintenance_daemon._try_acquire_daemon_process_lock",
        lambda _root: pytest.fail("read-only foreground acquired a graph lock"),
    )
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.write_pid_file",
        lambda _root: pytest.fail("read-only foreground wrote a graph PID"),
    )
    monkeypatch.setattr("src.agent.maintenance_daemon.MaintenanceDaemon", lambda _root: daemon)

    start_daemon_foreground(graph)

    assert order == ["profile", "logs"]
    daemon.llm_client.probe_backend.assert_not_called()
    daemon.run_forever.assert_called_once_with()


def test_start_daemon_detached_read_only_fails_closed_before_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    _read_only_env(monkeypatch, tmp_path, graph)
    monkeypatch.setattr(
        "src.agent.maintenance_daemon.subprocess.Popen",
        lambda *_args, **_kwargs: pytest.fail("read-only detached daemon spawned"),
    )

    result = start_daemon_detached(graph)

    assert result["ok"] is False
    assert result["code"] == "read_only_foreground_required"


def test_state_api_reports_read_only_profile_and_disabled_duties(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _graph(tmp_path)
    _read_only_env(monkeypatch, tmp_path, graph)
    monkeypatch.setattr("src.cli.ui_server.load_daemon_state", lambda _root: DaemonState())
    monkeypatch.setattr("src.cli.ui_server.read_pid_file", lambda _root: None)
    monkeypatch.setattr(
        "src.cli.ui_server._session_token_totals_for_api",
        lambda _state: (0, 0),
    )

    response = _build_daemon_state_response(graph)

    assert response.daemon_profile == "read_only_shadow_observer"
    assert response.disabled_duties == list(READ_ONLY_DISABLED_DUTIES)
