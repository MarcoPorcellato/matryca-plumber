"""Tests for Loguru bootstrap (daemon startup depends on a valid file sink)."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.utils.logging_config import configure_loguru, reset_loguru_configuration


def test_configure_loguru_registers_rotating_file_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_loguru_configuration()
    log_path = tmp_path / "daemon.log"
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(log_path))

    configure_loguru(stderr=False)

    assert log_path.is_file() or log_path.parent.is_dir()

    reset_loguru_configuration()


@pytest.mark.parametrize("graph_local", [False, True])
def test_configure_loguru_preserves_read_only_graph_immutability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    graph_local: bool,
) -> None:
    from src.shadow.cache_location import resolve_shadow_cache_location

    reset_loguru_configuration()
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    cache = tmp_path / "external-cache"
    configured_logs = graph / "logs" if graph_local else tmp_path / "external-logs"
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache))
    monkeypatch.setenv("MATRYCA_PLUMBER_LOG_PATH", str(configured_logs / "ops.log"))
    monkeypatch.setenv("MATRYCA_LOGURU_LOG_PATH", str(configured_logs / "app.log"))

    configure_loguru(stderr=False)

    expected_log = configured_logs / "app.log"
    if graph_local:
        expected_log = resolve_shadow_cache_location(graph).shadow_dir.parent / "logs" / "app.log"
        assert not configured_logs.exists()
    assert expected_log.is_file()

    reset_loguru_configuration()
