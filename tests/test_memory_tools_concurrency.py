"""Regression test for the _ensure_config_page create-race fix (#43, #331)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from src.agent.memory_tools import _ensure_config_page
from src.daemon.ast_cache import clear_graph_ast_cache
from src.daemon.config_layer import TELOS_HEADING, clear_identity_config_stores


@pytest.fixture(autouse=True)
def _clear_identity_caches() -> Iterator[None]:
    clear_graph_ast_cache()
    clear_identity_config_stores()
    yield
    clear_graph_ast_cache()
    clear_identity_config_stores()


def test_ensure_config_page_survives_concurrent_creation(tmp_path: Path) -> None:
    """Concurrent first-write races on a missing matryca-config.md must not clobber it."""
    graph_root = tmp_path
    thread_count = 8
    barrier = threading.Barrier(thread_count)
    results: list[Path] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def _race() -> None:
        barrier.wait()
        try:
            path = _ensure_config_page(graph_root)
        except BaseException as exc:  # noqa: BLE001 - surface any thread failure to main
            with lock:
                errors.append(exc)
            return
        with lock:
            results.append(path)

    threads = [threading.Thread(target=_race) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    assert len(results) == thread_count
    assert len({str(p) for p in results}) == 1

    config_path = results[0]
    assert config_path.is_file()
    content = config_path.read_text(encoding="utf-8")
    assert content.strip()
    assert f"# {TELOS_HEADING}" in content
