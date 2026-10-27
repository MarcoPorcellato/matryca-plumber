"""Synthetic native POSIX controls for the product supervisor, not a test observer."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest
from src.agent import dashboard_process as runtime
from src.agent.dashboard_protocol import (
    DashboardFrame,
    DashboardIntent,
    DashboardLimits,
    decode_frame,
)
from src.config import MatrycaWikiConfig

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")
REQUEST = "b" * 32
PRELUDE = "import sys,json,time,os; r=json.loads(sys.stdin.buffer.read()); "
PHASES = ["discover", "stat", "load_ast", "ids", "refs", "format", "complete"]
SUCCESS = (
    "sys.stderr.write(''.join(json.dumps({'phase':p})+'\\n' for p in " + repr(PHASES) + ")); "
    "sys.stderr.flush(); sys.stdout.write(json.dumps({'schema_version':1,"
    "'request_id':r['request_id'],'kind':'ok','markdown':'- synthetic'})); sys.stdout.flush(); "
)


def _script(monkeypatch: pytest.MonkeyPatch, root: Path, program: str) -> None:
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", PRELUDE + program],
            dict(os.environ),
            root,
        ),
    )


def _intent(root: Path) -> DashboardIntent:
    return DashboardIntent(
        request_id=REQUEST, raw_graph_path=str(root), wiki_config=MatrycaWikiConfig()
    )


def test_dashboard_first_terminal_deadline_never_extends() -> None:
    control = runtime.DashboardJobControl(DashboardLimits())
    first = control.begin_cleanup("dashboard_timeout")
    control.request_cancel()
    assert control.begin_cleanup("dashboard_worker_failed") == first
    assert control.reason == "dashboard_timeout"


def test_dashboard_production_budget_allows_long_read_and_keeps_cleanup_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    control = runtime.DashboardJobControl(DashboardLimits())
    clock[0] = 131.0
    assert not control.stopped(), "production dashboard expired at the former 120-second budget"
    assert control.cleanup_deadline is None
    clock[0] = 1809.99
    assert not control.stopped()
    clock[0] = 1810.0
    assert control.stopped()
    first_cleanup = control.cleanup_deadline
    assert first_cleanup == 1815.0
    clock[0] = 1811.0
    control.request_cancel()
    assert control.cleanup_deadline == first_cleanup
    assert control.reason == "dashboard_timeout"


def test_dashboard_cancel_before_spawn_does_not_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("process created after cancellation")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    limits = DashboardLimits()
    control = runtime.DashboardJobControl(limits)
    control.request_cancel()
    result = runtime.run_dashboard_process(_intent(tmp_path), limits=limits, control=control)
    assert result.code == "dashboard_worker_failed"
    assert result.cleanup_verified


def test_dashboard_success_requires_reap_esrch_and_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, tmp_path, SUCCESS)
    pids: list[int] = []
    original = subprocess.Popen

    def retain(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process = original(*args, **kwargs)
        pids.append(process.pid)
        return process

    monkeypatch.setattr(subprocess, "Popen", retain)
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    result = runtime.run_dashboard_process(
        _intent(tmp_path), limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert result.code is None
    assert result.markdown == "- synthetic"
    assert result.cleanup_verified
    with pytest.raises(ProcessLookupError):
        os.killpg(pids[0], 0)


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("late_without_watchdog", "dashboard_timeout"),
        ("late_with_watchdog", "dashboard_timeout"),
        ("cancelled_during_decode", "dashboard_worker_failed"),
        ("timely_success", None),
    ],
)
def test_dashboard_terminal_admission_honors_deadline_and_first_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, expected: str | None
) -> None:
    """Late validation must not publish success or renew an existing cleanup deadline."""
    _script(monkeypatch, tmp_path, SUCCESS)
    real_clock = time.monotonic
    offset = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: real_clock() + offset[0])
    limits = DashboardLimits(execution_s=2.0, cleanup_s=3.0)
    control = runtime.DashboardJobControl(limits)
    original_decode = decode_frame
    original_finalize = runtime._finalize_child
    deadlines: list[float] = []

    def decode(data: bytes, request_id: str, *, complete: bool) -> DashboardFrame:
        frame = original_decode(data, request_id, complete=complete)
        if scenario.startswith("late_"):
            offset[0] = control.execution_deadline - real_clock() + 0.05
        if scenario == "late_with_watchdog":
            deadlines.append(control.begin_cleanup("dashboard_timeout"))
        elif scenario == "cancelled_during_decode":
            control.request_cancel()
            assert control.cleanup_deadline is not None
            deadlines.append(control.cleanup_deadline)
        return frame

    def finalize(*args: Any, **kwargs: Any) -> bool:
        assert control.cleanup_deadline is not None
        deadlines.append(control.cleanup_deadline)
        verified = original_finalize(*args, **kwargs)
        if scenario == "timely_success":
            offset[0] = control.execution_deadline - real_clock() + 0.05
        return bool(verified)

    monkeypatch.setattr(runtime, "decode_frame", decode)
    monkeypatch.setattr(runtime, "_finalize_child", finalize)
    outcome = runtime.run_dashboard_process(_intent(tmp_path), limits=limits, control=control)
    assert outcome.code == expected
    assert outcome.cleanup_verified
    assert outcome.markdown == ("- synthetic" if expected is None else None)
    assert deadlines and len(set(deadlines)) == 1
    assert control.cleanup_deadline == deadlines[0]
    assert control.reason == expected
    if scenario == "timely_success":
        assert time.monotonic() > control.execution_deadline


def test_dashboard_valid_frame_followed_by_nonzero_exit_is_not_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, tmp_path, SUCCESS + "raise SystemExit(7)")
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    outcome = runtime.run_dashboard_process(
        _intent(tmp_path), limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert outcome.code == "dashboard_worker_failed"
    assert outcome.markdown is None
    assert outcome.cleanup_verified


@pytest.mark.parametrize("channel", ["stdout", "stderr"])
def test_dashboard_overflow_is_capped_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, channel: str
) -> None:
    _script(
        monkeypatch,
        tmp_path,
        f"sys.{channel}.buffer.write(b'x'*65536); sys.{channel}.flush(); time.sleep(20)",
    )
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0, stdout_bytes=1024, stderr_bytes=1024)
    outcome = runtime.run_dashboard_process(
        _intent(tmp_path), limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert outcome.code == "dashboard_output_overflow"
    assert outcome.cleanup_verified
    assert outcome.elapsed_ms < 2000


def test_dashboard_timeout_returns_error_only_after_verified_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, tmp_path, "time.sleep(20)")
    limits = DashboardLimits(execution_s=0.2, cleanup_s=1.0)
    result = runtime.run_dashboard_process(
        _intent(tmp_path), limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert result.code == "dashboard_timeout"
    assert result.cleanup_verified
    assert result.elapsed_ms < 1200


@pytest.mark.parametrize(
    "tail",
    [
        "sys.stderr.write('bad\\n')",
        "sys.stdout.write('{}')",
        "sys.stderr.write('{')",
        "raise RuntimeError('synthetic')",
    ],
)
def test_dashboard_rejects_corrupt_partial_or_failed_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tail: str
) -> None:
    _script(monkeypatch, tmp_path, tail)
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    result = runtime.run_dashboard_process(
        _intent(tmp_path), limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert result.code in {"dashboard_protocol_error", "dashboard_worker_failed"}
    assert result.markdown is None
    assert result.cleanup_verified


def test_dashboard_stdin_backpressure_obeys_execution_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(20)"],
            dict(os.environ),
            tmp_path,
        ),
    )
    intent = _intent(tmp_path).model_copy(
        update={"wiki_config": MatrycaWikiConfig(dashboard_page_title="x" * 60000)}
    )
    limits = DashboardLimits(execution_s=0.2, cleanup_s=1.0)
    result = runtime.run_dashboard_process(
        intent, limits=limits, control=runtime.DashboardJobControl(limits)
    )
    assert result.code == "dashboard_timeout"
    assert result.cleanup_verified
    assert result.elapsed_ms < 1200


def test_dashboard_closes_stdin_and_retains_finalizer_baseexception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, tmp_path, SUCCESS)
    original = runtime._finalize_child
    retained = []

    def interrupted(process: subprocess.Popen[bytes], *args: Any, **kwargs: Any) -> bool:
        assert process.stdin is not None and process.stdin.closed
        result = original(process, *args, **kwargs)
        assert result
        retained.append(process)
        raise KeyboardInterrupt("synthetic finalizer interruption")

    monkeypatch.setattr(runtime, "_finalize_child", interrupted)
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    control = runtime.DashboardJobControl(limits)
    result = runtime.run_dashboard_process(_intent(tmp_path), limits=limits, control=control)
    assert result.code == "dashboard_cleanup_unverified"
    assert not result.cleanup_verified
    assert retained and retained[0].returncode == 0
    assert "finalizer_interrupted" in control._cleanup_events


def test_dashboard_private_finalizer_gets_only_residual_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, tmp_path, SUCCESS)
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    control = runtime.DashboardJobControl(limits)
    original = runtime._finalize_child

    def verify(
        process: Any, selector: Any, streams: Any, budget: float, events: list[str], **kwargs: Any
    ) -> bool:
        assert control.cleanup_deadline is not None
        assert 0 < budget <= control.cleanup_deadline - time.monotonic() + 0.01
        return bool(original(process, selector, streams, budget, events, **kwargs))

    monkeypatch.setattr(runtime, "_finalize_child", verify)
    result = runtime.run_dashboard_process(_intent(tmp_path), limits=limits, control=control)
    assert result.cleanup_verified


def test_dashboard_child_without_stdin_is_a_failed_cleanup_not_success() -> None:
    class MissingStdin:
        stdin = None

    events: list[str] = []
    assert not runtime._close_stdin(cast(subprocess.Popen[bytes], MissingStdin()), events)
    assert events == ["stdin_missing"]
