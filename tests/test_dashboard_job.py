"""Cancellation, non-queued admission and bounded ownership retention."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import weakref
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anyio
import pytest
from src.agent import dashboard_job as jobs
from src.agent import dashboard_process as runtime
from src.agent.dashboard_protocol import (
    DashboardIntent,
    DashboardLimits,
    DashboardOutcome,
    PhaseReader,
)
from src.config import MatrycaWikiConfig

POSIX = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="POSIX lane")


def _sleeping_child(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(20)"],
            dict(os.environ),
            root,
        ),
    )


async def _until(predicate: Callable[[], bool], seconds: float = 2.0) -> None:
    deadline = time.monotonic() + seconds
    # State belongs to a native process/thread, not an asyncio.Event.
    while not predicate() and time.monotonic() < deadline:  # noqa: ASYNC110
        await asyncio.sleep(0.005)
    assert predicate(), "synthetic fixture deadline"


@pytest.mark.asyncio
@POSIX
async def test_dashboard_busy_does_not_queue_or_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sleeping_child(monkeypatch, tmp_path)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    first = asyncio.create_task(pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    await _until(lambda: pool._active is not None)
    try:
        second = json.loads(await pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
        assert second["code"] == "dashboard_busy"
    finally:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
    assert pool._active is None
    assert not pool._poisoned


@pytest.mark.asyncio
@POSIX
async def test_dashboard_cancel_waits_for_owned_group_and_reraises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _sleeping_child(monkeypatch, tmp_path)
    original = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def retain(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, "Popen", retain)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    pending = asyncio.create_task(pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    await _until(lambda: bool(children))
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert children[0].returncode is not None
    assert children[0].stdin is not None and children[0].stdin.closed
    assert children[0].stdout is not None and children[0].stdout.closed
    assert children[0].stderr is not None and children[0].stderr.closed
    with pytest.raises(ProcessLookupError):
        os.killpg(children[0].pid, 0)
    assert pool._active is None


@pytest.mark.asyncio
async def test_dashboard_repeated_cancellation_does_not_abandon_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    finished = threading.Event()

    def synthetic_owner(
        _intent: DashboardIntent, *, limits: DashboardLimits, control: runtime.DashboardJobControl
    ) -> DashboardOutcome:
        entered.set()
        assert control.cancelled.wait(1)
        time.sleep(0.06)
        control.begin_cleanup("dashboard_worker_failed")
        finished.set()
        return DashboardOutcome(
            code="dashboard_worker_failed", elapsed_ms=60, cleanup_verified=True
        )

    monkeypatch.setattr(jobs, "run_dashboard_process", synthetic_owner)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits(execution_s=2.0, cleanup_s=1.0)
    pending = asyncio.create_task(pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    await _until(entered.is_set)
    pending.cancel()
    await asyncio.sleep(0.01)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert finished.is_set()
    assert pool._active is None


@pytest.mark.asyncio
@POSIX
async def test_dashboard_blocked_before_popen_poison_prevents_late_popen_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = threading.Event()
    release = threading.Event()
    original = runtime._request_bytes

    def blocked(intent: DashboardIntent, limits: DashboardLimits) -> bytes:
        entered.set()
        assert release.wait(2)
        return original(intent, limits)

    calls: list[str] = []

    def forbidden(*_args: object, **_kwargs: object) -> None:
        calls.append("popen")
        pytest.fail("late process creation")

    monkeypatch.setattr(runtime, "_request_bytes", blocked)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits(execution_s=0.1, cleanup_s=0.1)
    pending = asyncio.create_task(pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    await _until(entered.is_set)
    try:
        body = await pending
        assert json.loads(body)["code"] == "dashboard_cleanup_unverified"
        owner = pool._active
        assert owner is not None and owner.thread is not None
        assert owner.thread.is_alive()
        assert pool._poisoned
    finally:
        release.set()
        await _until(lambda: pool._active is not None and pool._active.done.is_set())
        assert pool._active is not None and pool._active.thread is not None
        pool._active.thread.join(0.2)
        assert not pool._active.thread.is_alive()
    assert json.loads(await pool.read(str(tmp_path), MatrycaWikiConfig(), limits))["code"] == (
        "dashboard_cleanup_unverified"
    )
    assert not calls


@pytest.mark.asyncio
async def test_dashboard_async_deadline_fires_without_external_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()

    def stuck(
        _intent: DashboardIntent, *, limits: DashboardLimits, control: runtime.DashboardJobControl
    ) -> DashboardOutcome:
        assert release.wait(2)
        return DashboardOutcome(elapsed_ms=200, cleanup_verified=True, markdown="- too late")

    monkeypatch.setattr(jobs, "run_dashboard_process", stuck)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits(execution_s=0.1, cleanup_s=0.1)
    started = time.monotonic()
    try:
        body = json.loads(await pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
        assert body["code"] == "dashboard_cleanup_unverified"
        assert not body["cleanup_verified"]
        assert time.monotonic() - started < 0.8
    finally:
        release.set()
        await _until(lambda: pool._active is not None and pool._active.done.is_set())
        assert pool._active is not None and pool._active.thread is not None
        pool._active.thread.join(0.2)
        assert not pool._active.thread.is_alive()
    assert pool._poisoned


@pytest.mark.asyncio
async def test_dashboard_cleanup_uncertainty_poison_retains_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unverified(
        _intent: DashboardIntent, *, limits: DashboardLimits, control: runtime.DashboardJobControl
    ) -> DashboardOutcome:
        control.begin_cleanup("dashboard_cleanup_unverified")
        return DashboardOutcome(
            code="dashboard_cleanup_unverified", elapsed_ms=0, cleanup_verified=False
        )

    monkeypatch.setattr(jobs, "run_dashboard_process", unverified)
    pool = jobs._DashboardJobs()
    limits = DashboardLimits()
    first = json.loads(await pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    retained = pool._active
    second = json.loads(await pool.read(str(tmp_path), MatrycaWikiConfig(), limits))
    assert first["code"] == second["code"] == "dashboard_cleanup_unverified"
    assert retained is not None and pool._active is retained


@pytest.mark.asyncio
async def test_dashboard_level_cancellation_shields_cleanup_without_busy_spin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = threading.Event()
    sleeps: list[float] = []
    original_sleep = asyncio.sleep

    async def observe_sleep(delay: float) -> None:
        sleeps.append(delay)
        await original_sleep(delay)

    def owner(
        _intent: DashboardIntent, *, limits: DashboardLimits, control: runtime.DashboardJobControl
    ) -> DashboardOutcome:
        assert control.cancelled.wait(1)
        time.sleep(0.08)
        finished.set()
        return DashboardOutcome(
            code="dashboard_worker_failed", elapsed_ms=100, cleanup_verified=True
        )

    monkeypatch.setattr(jobs, "run_dashboard_process", owner)
    monkeypatch.setattr(asyncio, "sleep", observe_sleep)
    pool = jobs._DashboardJobs()
    with anyio.CancelScope() as cancellation:
        asyncio.get_running_loop().call_later(0.02, cancellation.cancel)
        await pool.read(str(tmp_path), MatrycaWikiConfig(), DashboardLimits())
    assert finished.is_set()
    assert pool._active is None
    assert len(sleeps) < 100, "one level cancellation busy-spun during cleanup"


@pytest.mark.asyncio
@POSIX
@pytest.mark.parametrize(
    "phase", ["discover", "stat", "load_ast", "ids", "refs", "format", "complete"]
)
async def test_dashboard_cancel_at_each_phase_and_after_output_before_reap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from tests.test_dashboard_process import PHASES, PRELUDE, SUCCESS

    observed = threading.Event()
    original = PhaseReader.feed

    def observe(reader: PhaseReader, data: bytes) -> None:
        original(reader, data)
        if reader.last_phase == phase:
            observed.set()

    monkeypatch.setattr(PhaseReader, "feed", observe)
    prefix = PHASES[: PHASES.index(phase) + 1]
    program = (
        "sys.stderr.write(''.join(json.dumps({'phase':p})+'\\n' for p in "
        + repr(prefix)
        + ")); sys.stderr.flush(); time.sleep(20)"
    )
    if phase == "complete":
        program = SUCCESS + "os.close(1); os.close(2); time.sleep(20)"
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: (
            [sys.executable, "-I", "-S", "-B", "-c", PRELUDE + program],
            dict(os.environ),
            tmp_path,
        ),
    )
    pool = jobs._DashboardJobs()
    pending = asyncio.create_task(
        pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=2.0, cleanup_s=1.0)
        )
    )
    await _until(observed.is_set)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert pool._active is None
    assert not pool._poisoned


@pytest.mark.asyncio
@POSIX
async def test_dashboard_cancel_preserves_parent_parser_worker_and_status_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.agent.dispatch_read_handlers import handle_read_shadow_status
    from src.graph.bounded_page_parse import get_bounded_page_parse_worker

    parent = get_bounded_page_parse_worker()
    assert parent.parse_text("- synthetic parent\n", mode="stack", page_title="Parent").ok
    pid = parent.pid
    assert pid is not None
    _sleeping_child(monkeypatch, tmp_path)
    pool = jobs._DashboardJobs()
    pending = asyncio.create_task(
        pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=2.0, cleanup_s=1.0)
        )
    )
    await _until(lambda: pool._active is not None)
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "false")
    status = json.loads(await handle_read_shadow_status(MatrycaWikiConfig(), str(tmp_path), ""))
    assert status["state"] == "disabled"
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert get_bounded_page_parse_worker() is parent
    assert parent.pid == pid
    assert parent.parse_text("- still usable\n", mode="stack", page_title="Parent").ok


@pytest.mark.asyncio
@POSIX
async def test_dashboard_descendant_is_gone_before_admission_reopens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "synthetic-child.pid"
    program = "\n".join(
        [
            "import subprocess,sys,time,os,signal",
            "child=subprocess.Popen([sys.executable,'-I','-S','-B','-c',"
            "'import time;time.sleep(20)'])",
            "def stop(*args):",
            "    child.wait(timeout=1)",
            "    raise SystemExit(0)",
            "signal.signal(signal.SIGTERM,stop)",
            f"open({str(marker)!r},'w').write(str(child.pid))",
            "time.sleep(20)",
        ]
    )
    monkeypatch.setattr(
        runtime,
        "_build_launch",
        lambda: ([sys.executable, "-I", "-S", "-B", "-c", program], dict(os.environ), tmp_path),
    )
    pool = jobs._DashboardJobs()
    pending = asyncio.create_task(
        pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=2.0, cleanup_s=2.0)
        )
    )
    await _until(marker.exists)
    descendant = int(marker.read_text(encoding="utf-8"))
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert pool._active is None
    with pytest.raises(ProcessLookupError):
        os.kill(descendant, 0)


@pytest.mark.asyncio
@POSIX
async def test_dashboard_popen_late_return_retains_handle_without_success_or_renewal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    entered = threading.Event()
    release = threading.Event()
    budgets: list[float] = []
    handles: list[weakref.ReferenceType[Any]] = []

    class LateHandle:
        pid = 999999999
        stdin = io.BytesIO()
        stdout = io.BytesIO()
        stderr = io.BytesIO()
        returncode = 0

        def poll(self) -> int:
            return 0

    def delayed(*_args: object, **_kwargs: object) -> Any:
        entered.set()
        assert release.wait(2)
        child = LateHandle()
        handles.append(weakref.ref(child))
        return child

    def finalize(
        child: Any, _selector: Any, _streams: Any, budget: float, _events: list[str], **_kwargs: Any
    ) -> bool:
        budgets.append(budget)
        child.stdout.close()
        child.stderr.close()
        return True

    monkeypatch.setattr(subprocess, "Popen", delayed)
    monkeypatch.setattr(runtime, "_finalize_child", finalize)
    monkeypatch.setattr(runtime, "_group_state", lambda _pid: False)
    pool = jobs._DashboardJobs()
    pending = asyncio.create_task(
        pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=0.1, cleanup_s=0.1)
        )
    )
    await _until(entered.is_set)
    try:
        assert json.loads(await pending)["code"] == "dashboard_cleanup_unverified"
        assert pool._active is not None
        deadline = pool._active.control.cleanup_deadline
    finally:
        release.set()
        await _until(lambda: pool._active is not None and pool._active.done.is_set())
        assert pool._active is not None and pool._active.thread is not None
        pool._active.thread.join(0.2)
        assert not pool._active.thread.is_alive()
    assert handles and budgets == [0.0]
    assert handles[0]() is not None, "late child handle lost after unverified finalization"
    assert pool._active is not None
    assert pool._active.control.cleanup_deadline == deadline
    assert pool._poisoned
    assert pool._active.outcome is not None
    assert pool._active.outcome.code == "dashboard_cleanup_unverified"


@pytest.mark.asyncio
async def test_dashboard_logging_cannot_block_the_async_caller_past_its_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()

    def release_later() -> None:
        time.sleep(0.5)
        release.set()

    rescue = threading.Thread(target=release_later)

    def log(_message: str) -> None:
        assert release.wait(1)

    def owner(
        _intent: DashboardIntent, *, limits: DashboardLimits, control: runtime.DashboardJobControl
    ) -> DashboardOutcome:
        control.begin_cleanup(None)
        return DashboardOutcome(elapsed_ms=0, cleanup_verified=True, markdown="- synthetic")

    monkeypatch.setattr(jobs, "run_dashboard_process", owner)
    monkeypatch.setattr(
        jobs, "logger", SimpleNamespace(bind=lambda **_fields: SimpleNamespace(info=log))
    )
    pool = jobs._DashboardJobs()
    rescue.start()
    started = time.monotonic()
    try:
        await pool.read(
            str(tmp_path), MatrycaWikiConfig(), DashboardLimits(execution_s=0.1, cleanup_s=0.1)
        )
        assert time.monotonic() - started < 0.4, "log sink blocked the asynchronous caller"
    finally:
        release.set()
        rescue.join(1)
        assert not rescue.is_alive()
        if pool._active is not None:
            await _until(pool._active.done.is_set)
            assert pool._active.thread is not None
            pool._active.thread.join(0.2)
            assert not pool._active.thread.is_alive()
