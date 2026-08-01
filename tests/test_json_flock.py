"""Cross-process JSON flock used by daemon state and semantic cache."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.io_retry import PageLockUnavailableError
from src.graph.json_flock import cross_process_json_flock, cross_process_json_read_flock
from src.utils.platform_lock import clear_flock_depths

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fcntl flock is not available on Windows",
)


def test_cross_process_json_flock_serializes_subprocesses(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"n": 0}', encoding="utf-8")
    script = f"""
import json
import sys
import time
from pathlib import Path

from src.graph.json_flock import cross_process_json_flock

target = Path({str(target)!r})
with cross_process_json_flock(target):
    data = json.loads(target.read_text(encoding="utf-8"))
    time.sleep(0.05)
    data["n"] = data.get("n", 0) + 1
    target.write_text(json.dumps(data), encoding="utf-8")
"""
    repo_root = Path(__file__).resolve().parents[1]
    procs = [subprocess.Popen([sys.executable, "-c", script], cwd=str(repo_root)) for _ in range(2)]
    for proc in procs:
        proc.wait(timeout=10)
        assert proc.returncode == 0
    result = json.loads(target.read_text(encoding="utf-8"))
    assert result["n"] == 2


def test_in_process_json_flock_context_manager(tmp_path: Path) -> None:
    target = tmp_path / "payload.json"
    target.write_text("{}", encoding="utf-8")
    with cross_process_json_flock(target):
        target.write_text('{"ok": true}', encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_json_read_flock_does_not_create_sidecar_in_read_only_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "payload.json"
    target.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with cross_process_json_read_flock(target, graph_root=tmp_path):
        assert json.loads(target.read_text(encoding="utf-8")) == {}

    assert not (tmp_path / ".payload.json.flock").exists()


def test_nested_json_flock_same_thread_reentrant(tmp_path: Path) -> None:
    clear_flock_depths()
    target = tmp_path / "nested.json"
    target.write_text("{}", encoding="utf-8")
    with cross_process_json_flock(target), cross_process_json_flock(target):  # noqa: SIM117
        target.write_text('{"nested": true}', encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == {"nested": True}


def test_json_flock_raises_when_blocking_acquire_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_flock_depths()
    target = tmp_path / "contended.json"
    target.write_text("{}", encoding="utf-8")

    import fcntl

    def _contended_flock(fd: int, op: int) -> None:
        _ = fd
        if op & fcntl.LOCK_NB:
            raise BlockingIOError()
        raise OSError(95, "flock blocked")

    monkeypatch.delenv("MATRYCA_ALLOW_FLOCK_DEGRADATION", raising=False)
    monkeypatch.setattr("src.utils.platform_lock.IO_RETRY_ATTEMPTS", 2)
    monkeypatch.setattr("src.utils.platform_lock.IO_RETRY_INITIAL_DELAY_S", 0.01)
    monkeypatch.setattr("src.utils.platform_lock.IO_RETRY_MAX_DELAY_S", 0.02)
    with (
        patch("src.utils.platform_lock._fcntl.flock", side_effect=_contended_flock),
        pytest.raises(PageLockUnavailableError),
        cross_process_json_flock(target),
    ):
        pass


def test_json_flock_degradation_on_unsupported_fs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_flock_depths()
    target = tmp_path / "cloud.json"
    target.write_text("{}", encoding="utf-8")

    def _reject_flock(fd: int, op: int) -> None:
        _ = (fd, op)
        raise OSError(95, "flock not supported on this filesystem")

    monkeypatch.setenv("MATRYCA_ALLOW_FLOCK_DEGRADATION", "true")
    with (
        patch("src.utils.platform_lock._fcntl.flock", side_effect=_reject_flock),
        cross_process_json_flock(target),
    ):
        target.write_text('{"degraded": true}', encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8")) == {"degraded": True}
