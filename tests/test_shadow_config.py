"""Tests for Shadow DB env flags and writer-lock safety."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from src.graph.io_retry import PageLockUnavailableError
from src.graph.path_sandbox import PathTraversalSecurityError
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.config import (
    shadow_db_busy_timeout_ms,
    shadow_db_enabled,
    shadow_rebuild_lock_timeout_s,
    shadow_writer_lock_timeout_s,
)
from src.shadow.connection import open_shadow_db
from src.shadow.meta import (
    META_GENERATION,
    META_LAST_FULL_SYNC_COMPLETED,
    META_LAST_SYNC_ERROR,
    get_meta,
)
from src.shadow.writer_lock import shadow_rebuild_lock, shadow_writer_lock_path
from src.utils.platform_lock import clear_flock_depths, flock_depths

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fcntl flock is not available on Windows",
)


def test_shadow_db_enabled_default_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_SHADOW_DB_ENABLED", raising=False)
    assert shadow_db_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
def test_shadow_db_enabled_false_tokens(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", value)
    assert shadow_db_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_shadow_db_enabled_true_tokens(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", value)
    assert shadow_db_enabled() is True


def test_shadow_db_enabled_reads_isolated_mapping() -> None:
    assert shadow_db_enabled({}) is True
    assert shadow_db_enabled({"MATRYCA_SHADOW_DB_ENABLED": "false"}) is False
    assert shadow_db_enabled({"MATRYCA_SHADOW_DB_ENABLED": "true"}) is True


def test_shadow_busy_timeout_ms_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "999999")
    assert shadow_db_busy_timeout_ms() == 60_000
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "-5")
    assert shadow_db_busy_timeout_ms() == 0


def test_shadow_writer_lock_timeout_s_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S", raising=False)
    assert shadow_writer_lock_timeout_s() == 10.0
    monkeypatch.setenv("MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S", "0")
    assert shadow_writer_lock_timeout_s() == 1.0
    monkeypatch.setenv("MATRYCA_SHADOW_WRITER_LOCK_TIMEOUT_S", "9999")
    assert shadow_writer_lock_timeout_s() == 300.0


def test_shadow_rebuild_lock_timeout_s_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_SHADOW_REBUILD_LOCK_TIMEOUT_S", raising=False)
    assert shadow_rebuild_lock_timeout_s() == 120.0
    monkeypatch.setenv("MATRYCA_SHADOW_REBUILD_LOCK_TIMEOUT_S", "9999")
    assert shadow_rebuild_lock_timeout_s() == 600.0


@pytest.fixture(autouse=True)
def _shadow_cache_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(tmp_path / "operator-cache"))


def test_shadow_writer_lock_path_rejects_cache_symlink_escape(tmp_path: Path) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)

    outside = tmp_path / "outside-cache"
    outside.mkdir()
    (tmp_path / "operator-cache").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathTraversalSecurityError):
        shadow_writer_lock_path(graph)


def test_writer_lock_reentrancy_keyed_by_resolved_lock_path(tmp_path: Path) -> None:
    graph_a = tmp_path / "vault-a"
    graph_b = tmp_path / "vault-b"
    (graph_a / "pages").mkdir(parents=True)
    (graph_b / "pages").mkdir(parents=True)
    lock_a = shadow_writer_lock_path(graph_a)
    lock_b = shadow_writer_lock_path(graph_b)
    assert lock_a != lock_b
    clear_flock_depths()
    with shadow_rebuild_lock(graph_a):
        depths = flock_depths()
        assert depths[str(lock_a.resolve(strict=False))] == 1
        assert str(lock_b.resolve(strict=False)) not in depths


def test_page_lock_unavailable_does_not_invalidate_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    page = graph / "pages" / "Stable.md"
    page.write_text(
        "- stable\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    rebuild_shadow_from_graph(graph)

    conn = open_shadow_db(graph)
    try:
        generation_before = get_meta(conn, META_GENERATION)
    finally:
        conn.close()

    monkeypatch.setenv("MATRYCA_SHADOW_REBUILD_LOCK_TIMEOUT_S", "1")
    import subprocess
    import sys
    import time

    repo_root = Path(__file__).resolve().parents[1]
    ready_file = tmp_path / "rebuild-holder.ready"
    hold_script = f"""
import os
import time
from pathlib import Path
from src.shadow.writer_lock import shadow_rebuild_lock

os.environ["MATRYCA_SHADOW_DB_ENABLED"] = "true"
graph = Path({str(graph)!r})
ready = Path({str(ready_file)!r})
with shadow_rebuild_lock(graph):
    ready.write_text("ok", encoding="utf-8")
    time.sleep(5)
"""
    proc = subprocess.Popen([sys.executable, "-c", hold_script], cwd=str(repo_root))
    try:
        deadline = time.monotonic() + 5.0
        while not ready_file.is_file() and proc.poll() is None:
            if time.monotonic() >= deadline:
                pytest.fail("holder subprocess did not acquire rebuild lock in time")
            time.sleep(0.05)
        with pytest.raises(PageLockUnavailableError):
            rebuild_shadow_from_graph(graph)
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    conn = open_shadow_db(graph)
    try:
        assert get_meta(conn, META_LAST_FULL_SYNC_COMPLETED) == "true"
        assert get_meta(conn, META_GENERATION) == generation_before
        assert (get_meta(conn, META_LAST_SYNC_ERROR) or "").strip() == ""
    finally:
        conn.close()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="os.fork unavailable")
def test_fork_child_clears_flock_depth_state() -> None:
    clear_flock_depths()
    flock_depths()["synthetic-depth"] = 2
    pid = os.fork()
    if pid == 0:
        child_depths = flock_depths()
        assert "synthetic-depth" not in child_depths
        os._exit(0)
    _, status = os.waitpid(pid, 0)
    assert os.WEXITSTATUS(status) == 0
    clear_flock_depths()
