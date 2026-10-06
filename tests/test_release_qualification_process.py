from __future__ import annotations

import ctypes
import io
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import pytest
from scripts.release_qualification import focused, installed, process, sdist_build


def test_shared_windows_gate_is_the_focused_gate() -> None:
    assert focused._WINDOWS_GATE_CODE == process.WINDOWS_GATE_CODE


def test_windows_start_assigns_before_single_release_and_forwards_bufsize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Pipe:
        def write(self, payload: bytes) -> int:
            events.append(f"write:{payload!r}")
            return len(payload)

        def close(self) -> None:
            events.append("stdin-close")

    class _Handle:
        def Close(self) -> None:
            events.append("process-handle-close")

    class _Child:
        stdin = _Pipe()
        _handle = _Handle()

        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

    child = _Child()

    class _Job:
        def assign(self, _handle: int) -> None:
            events.append("assign")

        def terminate(self) -> None:
            events.append("terminate")

        def active_processes(self) -> int:
            return 0

        def close(self) -> None:
            events.append("job-close")

    def _popen(_argv: list[str], **kwargs: object) -> _Child:
        child.kwargs = kwargs
        return child

    monkeypatch.setattr(subprocess, "Popen", _popen)
    owned = process.start_process(
        ["synthetic-child"],
        windows=True,
        windows_job_factory=_Job,
        windows_gate_code=process.WINDOWS_GATE_CODE,
        bufsize=0,
    )

    assert events[:3] == ["assign", "write:b'G'", "stdin-close"]
    assert child.kwargs["bufsize"] == 0
    assert child.kwargs["stdin"] == subprocess.PIPE
    assert owned.job is not None


def test_windows_gate_rejects_short_release_write_without_second_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Pipe:
        def write(self, _payload: bytes) -> int:
            events.append("write")
            return 0

        def close(self) -> None:
            events.append("stdin-close")

    class _Child:
        stdin = _Pipe()
        stdout = None
        stderr = None
        _handle = object()

        def kill(self) -> None:
            events.append("kill")

        def wait(self, timeout: float) -> int:
            events.append("wait")
            return 1

    class _Job:
        def assign(self, _handle: int) -> None:
            events.append("assign")

        def terminate(self) -> None:
            events.append("terminate")

        def close(self) -> None:
            events.append("job-close")

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)

    with pytest.raises(ValueError, match="release token"):
        process.start_process(
            ["synthetic-child"],
            windows=True,
            windows_job_factory=_Job,
            windows_gate_code=process.WINDOWS_GATE_CODE,
            bufsize=0,
        )

    assert events.count("write") == 1
    assert events.index("assign") < events.index("write")
    assert "terminate" in events and "wait" in events
    assert "kill" not in events
    assert events[-1] == "job-close"


def test_windows_terminal_disposition_closes_popen_handle_once() -> None:
    calls: list[str] = []

    class _Handle:
        def Close(self) -> None:
            calls.append("close")

    class _Child:
        _handle = _Handle()
        returncode = None

        def wait(self, timeout: float) -> int:
            calls.append("wait")
            self.returncode = 7
            return self.returncode

    owned = process.OwnedProcess(_Child(), windows=True)  # type: ignore[arg-type]

    assert owned.reap_and_dispose_handle(timeout=1.0) == 7
    assert owned.reap_and_dispose_handle(timeout=1.0) == 7
    assert calls == ["wait", "close"]


def test_failed_popen_handle_close_is_terminal_and_never_retried() -> None:
    close_calls: list[int] = []

    class _Handle:
        def Close(self) -> None:
            close_calls.append(1)
            raise OSError("synthetic Close failure")

    class _Child:
        _handle = _Handle()
        returncode = 0

        def wait(self, timeout: float) -> int:
            return 0

    owned = process.OwnedProcess(_Child(), windows=True)  # type: ignore[arg-type]
    for _ in range(2):
        with pytest.raises(ValueError, match="reap and dispose"):
            owned.reap_and_dispose_handle(timeout=1.0)

    assert close_calls == [1]


def test_owned_windows_process_never_polls_after_handle_disposal() -> None:
    poll_calls: list[int] = []

    class _Handle:
        def Close(self) -> None:
            pass

    class _Child:
        _handle = _Handle()
        returncode = 0

        def wait(self, timeout: float) -> int:
            return 0

        def poll(self) -> int:
            poll_calls.append(1)
            return 0

    owned = process.OwnedProcess(_Child(), windows=True)  # type: ignore[arg-type]
    assert owned.reap_and_dispose_handle(timeout=1.0) == 0
    with pytest.raises(ValueError, match="after handle disposal"):
        owned.terminate(grace_seconds=0, immediate=True)
    assert poll_calls == []


class _NativeFunction:
    def __init__(self, callback: object) -> None:
        self.callback = callback
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *args: object) -> object:
        return self.callback(*args)  # type: ignore[operator]


class _FakeKernelReaderApi(Protocol):
    CancelSynchronousIo: _NativeFunction
    OpenThread: _NativeFunction


class _FakeWinDLLFactory(Protocol):
    def __call__(self, *args: object, **kwargs: object) -> _FakeKernelReaderApi: ...


def _install_fake_windows_apis(
    monkeypatch: pytest.MonkeyPatch, events: list[str]
) -> dict[str, int]:
    state = {"active": 0, "thread_handle": 0}
    job_handle = 0xA001

    def _query(_handle: object, _kind: object, payload: ctypes._CArgObject, *_args: object) -> int:
        events.append("job-query")
        info = ctypes.cast(payload, ctypes.POINTER(process._JobBasicAccountingInformation)).contents
        info.ActiveProcesses = state["active"]
        return 1

    class _Kernel:
        def __init__(self) -> None:
            def _create_job(*_args: object) -> int:
                events.append("job-create")
                return job_handle

            def _configure_job(*_args: object) -> int:
                events.append("job-configure")
                return 1

            def _assign_job(*_args: object) -> int:
                events.append("job-assign")
                state["active"] = 1
                return 1

            def _terminate_job(*_args: object) -> int:
                events.append("job-terminate")
                state["active"] = 0
                return 1

            def _cancel_reader(_handle: object) -> int:
                events.append("reader-cancel")
                return 1

            self.CreateJobObjectW = _NativeFunction(_create_job)
            self.SetInformationJobObject = _NativeFunction(_configure_job)
            self.AssignProcessToJobObject = _NativeFunction(_assign_job)
            self.TerminateJobObject = _NativeFunction(_terminate_job)
            self.QueryInformationJobObject = _NativeFunction(_query)
            self.CloseHandle = _NativeFunction(self._close)
            self.GetCurrentThreadId = _NativeFunction(lambda: 123)
            self.OpenThread = _NativeFunction(self._open_thread)
            self.CancelSynchronousIo = _NativeFunction(_cancel_reader)

        @staticmethod
        def _close(handle: int) -> int:
            events.append(f"native-close:{int(handle)}")
            return 1

        def _open_thread(self, *_args: object) -> int:
            state["thread_handle"] += 1
            handle = 0xB000 + state["thread_handle"]
            events.append(f"reader-open:{handle}")
            return handle

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)
    return state


def test_each_pipe_reader_kernel_object_is_configured_and_keeps_pointer_sized_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pointer_handle = 0x1_0000_1234
    closed: list[int] = []
    cancelled: list[int] = []

    class _Kernel:
        def __init__(self) -> None:
            api_objects.append(self)
            self.GetCurrentThreadId = _NativeFunction(lambda: 12)
            self.OpenThread = _NativeFunction(lambda *_args: pointer_handle)

            def _cancel_reader(handle: int) -> int:
                cancelled.append(int(handle))
                return 1

            def _close_handle(handle: int) -> int:
                closed.append(int(handle))
                return 1

            self.CancelSynchronousIo = _NativeFunction(_cancel_reader)
            self.CloseHandle = _NativeFunction(_close_handle)

    api_objects: list[_Kernel] = []

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)
    stream = io.BytesIO(b"synthetic")
    reader = process.WindowsPipeReader(stream, limit=32)
    reader.start()
    assert reader.wait_ready(1.0)
    reader.release()
    assert reader.wait(1.0)
    reader.cancel_and_join(deadline=time.monotonic() + 1.0)

    assert len(api_objects) == 3
    for api in api_objects:
        assert api.GetCurrentThreadId.restype is ctypes.c_uint32
        assert api.OpenThread.argtypes == [
            ctypes.c_uint32,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        assert api.OpenThread.restype is ctypes.c_void_p
        assert api.CancelSynchronousIo.argtypes == [ctypes.c_void_p]
        assert api.CancelSynchronousIo.restype is ctypes.c_int
        assert api.CloseHandle.argtypes == [ctypes.c_void_p]
        assert api.CloseHandle.restype is ctypes.c_int
    assert closed == [pointer_handle]
    assert cancelled == []


@pytest.mark.parametrize("failure", ["create", "configure", "query", "terminate", "close"])
def test_windows_job_api_failures_fail_closed_and_close_once(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    job_handle = 0x1_0000_4567
    closed: list[int] = []
    active_processes = [1]

    class _Kernel:
        def __init__(self) -> None:
            self.CreateJobObjectW = _NativeFunction(
                lambda *_args: 0 if failure == "create" else job_handle
            )
            self.SetInformationJobObject = _NativeFunction(
                lambda *_args: 0 if failure == "configure" else 1
            )
            self.AssignProcessToJobObject = _NativeFunction(lambda *_args: 1)

            def _terminate_job(*_args: object) -> int:
                if failure == "terminate":
                    return 0
                active_processes[0] = 0
                return 1

            def _close_handle(handle: int) -> int:
                closed.append(handle)
                return 0 if failure == "close" else 1

            self.TerminateJobObject = _NativeFunction(_terminate_job)
            self.QueryInformationJobObject = _NativeFunction(self._query)
            self.CloseHandle = _NativeFunction(_close_handle)

        @staticmethod
        def _query(
            _handle: object,
            _class: object,
            payload: ctypes._CArgObject,
            *_args: object,
        ) -> int:
            if failure == "query":
                return 0
            info = ctypes.cast(
                payload, ctypes.POINTER(process._JobBasicAccountingInformation)
            ).contents
            info.ActiveProcesses = active_processes[0]
            return 1

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)

    if failure in {"create", "configure"}:
        with pytest.raises(OSError):
            process.WindowsJob()
        assert closed == ([] if failure == "create" else [job_handle])
    else:
        job = process.WindowsJob()
        if failure == "query":
            with pytest.raises(OSError):
                job.active_processes()
        elif failure == "terminate":
            with pytest.raises(OSError):
                job.terminate()
        else:
            for _ in range(2):
                with pytest.raises((OSError, ValueError)):
                    job.close()
            assert closed == [job_handle]


def test_reader_retains_short_raw_reads_and_close_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pointer_handle = 0x1_0000_2222
    close_calls: list[int] = []

    class _Stream:
        def __init__(self) -> None:
            self.chunks = iter((b"ab", b"c", b"def", b""))
            self.close_calls = 0

        def read(self, _size: int) -> bytes:
            return next(self.chunks)

        def close(self) -> None:
            self.close_calls += 1

    def _close_handle(handle: int) -> int:
        close_calls.append(int(handle))
        return 1

    class _Kernel:
        GetCurrentThreadId = _NativeFunction(lambda: 31)
        OpenThread = _NativeFunction(lambda *_args: pointer_handle)
        CancelSynchronousIo = _NativeFunction(lambda _handle: 1)
        CloseHandle = _NativeFunction(_close_handle)

    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    stream = _Stream()
    reader = process.WindowsPipeReader(stream, limit=8, chunk_size=4)
    reader.start()
    assert reader.wait_ready(1.0)
    reader.release()
    assert reader.wait(1.0)
    reader.cancel_and_join(deadline=time.monotonic() + 1.0)
    reader.cancel_and_join(deadline=time.monotonic() + 1.0)

    assert reader.data == b"abcdef"
    assert not reader.overflowed
    assert stream.close_calls == 1
    assert close_calls == [pointer_handle]


@pytest.mark.parametrize("runner_name", ["installed", "sdist"])
def test_posix_runner_never_closes_a_pipe_with_a_live_reader(
    monkeypatch: pytest.MonkeyPatch, runner_name: str, tmp_path: Path
) -> None:
    entered = threading.Event()
    release = threading.Event()

    class _Stream:
        def __init__(self, blocked: bool) -> None:
            self.blocked = blocked
            self.closed = False
            self.exited = threading.Event()

        def read(self, _size: int) -> bytes:
            try:
                if self.blocked:
                    entered.set()
                    release.wait(2.0)
                return b""
            finally:
                self.exited.set()

        def close(self) -> None:
            self.closed = True

    stdout = _Stream(True)
    stderr = _Stream(False)
    worker_threads: list[threading.Thread] = []
    original_start = threading.Thread.start

    def _start(thread: threading.Thread) -> None:
        if "(drain)" in thread.name or thread.name == "sdist-build-output":
            worker_threads.append(thread)
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", _start)

    class _Child:
        def __init__(self) -> None:
            self.stdout = stdout
            self.stderr = stderr

        def wait(self, timeout: float) -> int:
            return 0

        def poll(self) -> int:
            return 0

    class _Owned:
        process = _Child()

        def terminate(self, **_kwargs: object) -> None:
            return None

        def group_exists(self) -> bool:
            return False

    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "TERMINATION_WAIT_SECONDS", 0.02)
    if runner_name == "installed":
        monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="posix"))

        def _run_installed() -> tuple[int, bytes, bytes]:
            return installed._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=cast(int, 0.03)
            )
    else:
        monkeypatch.setattr(sdist_build, "os", __import__("types").SimpleNamespace(name="posix"))
        monkeypatch.setattr(sdist_build, "_TERMINATE_SECONDS", 0.02)

        def _run_sdist() -> sdist_build._CommandResult:
            return sdist_build._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=0.03, capture=True
            )

    run_test: Callable[[], object]
    run_test = _run_installed if runner_name == "installed" else _run_sdist

    try:
        with pytest.raises(ValueError, match="reader|output"):
            run_test()
        assert entered.is_set()
        assert stdout.closed is False
        assert stderr.closed is False
    finally:
        release.set()
        assert stdout.exited.wait(1.0)
        for thread in worker_threads:
            thread.join(timeout=1.0)
            assert not thread.is_alive()


def test_partial_windows_reader_startup_joins_started_worker_and_closes_owned_pipes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    streams: list[io.BytesIO] = []

    class _Child:
        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            streams.extend((self.stdout, self.stderr))

        def wait(self, timeout: float) -> int:
            return 0

    class _Owned:
        process = _Child()

        def terminate(self, **_kwargs: object) -> None:
            pass

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            return 0

        def close(self) -> None:
            pass

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 44

        def OpenThread(self, *_args: object) -> int:
            return 0x1_0000_4444

        def CancelSynchronousIo(self, _handle: int) -> int:
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    original_start = threading.Thread.start
    started_readers = 0

    def _start(thread: threading.Thread) -> None:
        nonlocal started_readers
        if thread.name == "qualification-raw-pipe":
            started_readers += 1
            if started_readers == 2:
                raise RuntimeError("synthetic second-reader startup failure")
        original_start(thread)

    monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(threading.Thread, "start", _start)

    with pytest.raises(RuntimeError, match="second-reader startup failure"):
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))

    assert started_readers == 2
    assert all(stream.closed for stream in streams)


def test_windows_reader_readiness_failure_terminates_and_reaps_synthetic_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    streams: list[io.BytesIO] = []
    events: list[str] = []

    class _Child:
        def __init__(self) -> None:
            self.stdout = io.BytesIO()
            self.stderr = io.BytesIO()
            streams.extend((self.stdout, self.stderr))

    class _Owned:
        process = _Child()

        def terminate(self, **_kwargs: object) -> None:
            events.append("terminate")

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            events.append("reap")
            return 0

        def close(self) -> None:
            events.append("close-job")

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 46

        def OpenThread(self, *_args: object) -> int:
            return 0

        def CancelSynchronousIo(self, _handle: int) -> int:
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)

    with pytest.raises(ValueError, match="initialize qualification pipe reader"):
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))

    assert events == ["terminate", "reap", "close-job"]
    assert all(stream.closed for stream in streams)


def test_error_not_found_cancel_race_waits_for_completion_without_poison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    entered = threading.Event()
    cancelled: list[int] = []
    pointer_handle = 0x1_0000_9876

    class _Stream:
        def read(self, _size: int) -> bytes:
            entered.set()
            release.wait(1.0)
            return b""

        def close(self) -> None:
            pass

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 45

        def OpenThread(self, *_args: object) -> int:
            return pointer_handle

        def CancelSynchronousIo(self, handle: int) -> int:
            cancelled.append(handle)
            release.set()
            return 0

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 1168, raising=False)
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)
    reader = process.WindowsPipeReader(_Stream(), limit=4)
    reader.start()
    assert reader.wait_ready(1.0)
    reader.release()
    assert entered.wait(1.0)
    reader.cancel_and_join(deadline=time.monotonic() + 1.0)

    assert cancelled == [pointer_handle]
    assert not reader.thread.is_alive()
    assert process._WINDOWS_OBSERVER_POISONED is False


@pytest.mark.parametrize(
    ("case", "returncode", "stdout_bytes", "stderr_bytes", "expected"),
    [
        ("clean", 0, b"out", b"err", (0, b"out", b"err")),
        ("nonzero", 7, b"out", b"err", (7, b"out", b"err")),
    ],
)
def test_windows_installed_runner_returns_clean_and_nonzero_synthetic_children(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
    returncode: int,
    stdout_bytes: bytes,
    stderr_bytes: bytes,
    expected: tuple[int, bytes, bytes],
) -> None:
    class _Stream:
        def __init__(self, payload: bytes) -> None:
            self.stream = io.BytesIO(payload)

        def read(self, size: int) -> bytes:
            return self.stream.read(size)

        def close(self) -> None:
            self.stream.close()

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Stream(stdout_bytes)
            self.stderr = _Stream(stderr_bytes)

        def wait(self, timeout: float) -> int:
            return returncode

    class _Owned:
        process = _Child()

        def require_empty(self) -> None:
            return None

        def terminate(self, **_kwargs: object) -> None:
            return None

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            return returncode

        def close(self) -> None:
            return None

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 51

        def OpenThread(self, *_args: object) -> int:
            return 0x1_0000_5151

        def CancelSynchronousIo(self, _handle: int) -> int:
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)

    assert installed._run_bounded([f"synthetic-{case}"], cwd=tmp_path, timeout=1) == expected


@pytest.mark.parametrize(
    "failure", ["timeout", "overflow", "reader", "closed-descendant", "retained-descendant"]
)
def test_windows_installed_runner_fails_closed_for_output_and_job_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    reader_done = threading.Event()
    unblock = threading.Event()
    terminated: list[str] = []
    pipe_closed: list[bool] = []
    job_active = [int(failure.endswith("descendant"))]
    payload = b"abcdef" if failure == "overflow" else b""

    class _Stream:
        def read(self, _size: int) -> bytes:
            try:
                if failure == "reader":
                    raise OSError("synthetic read failure")
                if failure == "retained-descendant":
                    unblock.wait(1.0)
                return payload
            finally:
                reader_done.set()

        def close(self) -> None:
            pipe_closed.append(True)

    class _Child:
        stdout = _Stream()
        stderr = io.BytesIO()

        def wait(self, timeout: float) -> int:
            if failure in {"overflow", "reader"}:
                assert reader_done.wait(1.0)
                raise subprocess.TimeoutExpired("synthetic-child", timeout)
            if failure == "timeout":
                time.sleep(0.002)
                raise subprocess.TimeoutExpired("synthetic-child", timeout)
            return 0

    class _Owned:
        process = _Child()

        def require_empty(self) -> None:
            if job_active[0]:
                raise ValueError("synthetic descendant remains in Job Object")

        def terminate(self, **_kwargs: object) -> None:
            terminated.append("terminate")
            job_active[0] = 0
            unblock.set()

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            return 0

        def close(self) -> None:
            pass

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 52

        def OpenThread(self, *_args: object) -> int:
            return 0x1_0000_5252

        def CancelSynchronousIo(self, _handle: int) -> int:
            unblock.set()
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)
    with pytest.raises(
        ValueError, match="time limit|output bound|reader failed|descendant remains"
    ) as caught:
        installed._run_bounded(
            ["synthetic-child"],
            cwd=tmp_path,
            timeout=cast(int, 0.03 if failure == "timeout" else 1.0),
            output_limit=4,
        )

    assert terminated
    assert pipe_closed
    if failure == "reader":
        assert "cleanup also failed" in " ".join(getattr(caught.value, "__notes__", []))
        assert "reader failed" in str(caught.value)
    elif failure == "overflow":
        assert "output bound" in str(caught.value)
    elif failure == "timeout":
        assert "time limit" in str(caught.value)


def test_windows_consumer_observes_reader_error_during_wait_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    waits: list[str] = []

    class _Process:
        stdout = object()
        stderr = object()

        def wait(self, timeout: float) -> int:
            waits.append("wait")
            raise subprocess.TimeoutExpired("synthetic-child", timeout)

    class _Owned:
        process = _Process()

        def terminate(self, **_kwargs: object) -> None:
            waits.append("terminate")

        def require_empty(self) -> None:
            waits.append("require-empty")

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            waits.append("reap")
            return 0

        def close(self) -> None:
            waits.append("close-job")

    class _Reader:
        def __init__(self, stream: object, *, limit: int) -> None:
            self.stream = stream
            self.thread = type("_Thread", (), {"ident": 1})()
            self.errors = [OSError("synthetic reader error")]
            self.failed = threading.Event()
            self.failed.set()
            self.overflowed = False
            self.data = bytearray()

        def start(self) -> None:
            pass

        def wait_ready(self, _timeout: float) -> bool:
            return True

        def release(self) -> None:
            pass

        def cancel_and_join(self, *, deadline: float) -> None:
            waits.append("cancel-reader")

    monkeypatch.setattr(installed, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "WindowsPipeReader", _Reader)

    with pytest.raises(ValueError, match="output reader failed"):
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))

    assert waits == ["wait", "terminate", "cancel-reader", "cancel-reader", "reap", "close-job"]


def test_sdist_windows_consumer_observes_reader_error_during_wait_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []

    class _Process:
        stdout = object()

        def wait(self, timeout: float) -> int:
            raise subprocess.TimeoutExpired("synthetic-child", timeout)

    class _Owned:
        process = _Process()

        def terminate(self, **_kwargs: object) -> None:
            events.append("terminate")

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            events.append("reap")
            return 0

        def close(self) -> None:
            events.append("close-job")

    class _Reader:
        def __init__(self, stream: object, *, limit: int) -> None:
            self.stream = stream
            self.thread = type("_Thread", (), {"ident": 1})()
            self.errors = [OSError("synthetic reader error")]
            self.failed = threading.Event()
            self.failed.set()
            self.overflowed = False
            self.data = bytearray()

        def start(self) -> None:
            pass

        def wait_ready(self, _timeout: float) -> bool:
            return True

        def release(self) -> None:
            pass

        def wait(self, _timeout: float) -> bool:
            return False

        def cancel_and_join(self, *, deadline: float) -> None:
            events.append("cancel")
            raise ValueError("synthetic reader cleanup failure")

    monkeypatch.setattr(sdist_build, "os", __import__("types").SimpleNamespace(name="nt"))
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: _Owned())
    monkeypatch.setattr(process, "WindowsPipeReader", _Reader)

    with pytest.raises(ValueError, match="output reader failed") as caught:
        sdist_build._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=1.0, capture=True)

    assert "cleanup also failed" in " ".join(getattr(caught.value, "__notes__", []))
    assert events == ["terminate", "cancel", "reap", "close-job"]


@pytest.mark.parametrize(
    "failure",
    [
        "stdout-overflow",
        "stderr-overflow",
        "timeout",
        "reader-error",
        "closed-descendant",
        "retained-pipe-descendant",
        "stream-close-failure",
    ],
)
def test_windows_installed_consumer_failure_matrix_uses_real_owner_and_readers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    events: list[str] = []
    cancel = threading.Event()
    state = _install_fake_windows_apis(monkeypatch, events)
    real_win_dll = cast(_FakeWinDLLFactory, vars(ctypes)["WinDLL"])

    def _reader_cancellable_win_dll(*args: object, **kwargs: object) -> object:
        kernel = real_win_dll(*args, **kwargs)
        original_cancel = kernel.CancelSynchronousIo

        def _cancel_reader(handle: object) -> object:
            cancel.set()
            return original_cancel(handle)

        kernel.CancelSynchronousIo = _NativeFunction(_cancel_reader)
        return kernel

    monkeypatch.setattr(ctypes, "WinDLL", _reader_cancellable_win_dll, raising=False)
    reader_instances: list[process.WindowsPipeReader] = []
    real_reader_factory = process.WindowsPipeReader

    def _record_real_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader_factory(stream, limit=limit)
        reader_instances.append(reader)
        return reader

    monkeypatch.setattr(process, "WindowsPipeReader", _record_real_reader)

    class _Stream:
        def __init__(self, name: str) -> None:
            self.name = name
            self.payload = b"12345" if failure == f"{name}-overflow" else b""
            self.read_started = threading.Event()
            self.read_done = threading.Event()
            self.closed = False
            self.close_calls = 0

        def read(self, _size: int) -> bytes:
            self.read_started.set()
            if failure == "retained-pipe-descendant" and self.name == "stdout":
                cancel.wait(2.0)
                self.read_done.set()
                return b""
            if failure == "reader-error" and self.name == "stdout":
                self.read_done.set()
                raise OSError("synthetic raw-reader failure")
            if self.payload:
                payload, self.payload = self.payload, b""
                return payload
            self.read_done.set()
            return b""

        def close(self) -> None:
            self.close_calls += 1
            self.closed = True
            events.append(f"{self.name}-close")
            if failure == "stream-close-failure" and self.name == "stdout":
                raise OSError("synthetic stream close failure")

    class _Pipe:
        def write(self, payload: bytes) -> int:
            events.append(f"stdin-write:{payload!r}")
            return len(payload)

        def close(self) -> None:
            events.append("stdin-close")

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe()
            self.stdout = _Stream("stdout")
            self.stderr = _Stream("stderr")
            self._handle = _Handle()
            self.returncode: int | None = None
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            if self.wait_calls > 1:
                if state["active"] == 0:
                    self.returncode = 0
                    return 0
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            if failure in {"stdout-overflow", "stderr-overflow", "reader-error"}:
                wait_deadline = time.monotonic() + timeout
                for reader in reader_instances:
                    remaining = max(0.0, wait_deadline - time.monotonic())
                    if remaining:
                        reader.wait(remaining)
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            if failure == "timeout":
                clock.expire = True
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            if failure == "retained-pipe-descendant":
                self.stdout.read_started.wait(1.0)
            elif failure in {"closed-descendant", "stream-close-failure"}:
                self.stdout.read_done.wait(1.0)
                self.stderr.read_done.wait(1.0)
            self.returncode = 0
            if failure not in {"closed-descendant", "retained-pipe-descendant"}:
                state["active"] = 0
            return 0

    class _ConsumerClock:
        def __init__(self) -> None:
            self.started: float | None = None
            self.expire = False

        def monotonic(self) -> float:
            now = time.monotonic()
            if self.started is None:
                self.started = now
            if self.expire:
                self.expire = False
                return self.started + 1.01
            return now

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(installed, "os", type("_Windows", (), {"name": "nt"})())
    clock = _ConsumerClock()
    if failure == "timeout":
        # Keep process.py's real clock for raw-reader cleanup deadlines.
        monkeypatch.setattr(installed, "time", clock)

    messages = {
        "stdout-overflow": "output bound",
        "stderr-overflow": "output bound",
        "timeout": "time limit",
        "reader-error": "output reader failed",
        "closed-descendant": "retained active processes",
        "retained-pipe-descendant": "retained active processes",
        "stream-close-failure": "cleanup failed",
    }
    try:
        with pytest.raises(ValueError, match=messages[failure]) as caught:
            installed._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0), output_limit=4
            )
    finally:
        cancel.set()

    assert child.wait_calls >= 1
    assert child.stdout.closed and child.stdout.close_calls == 1
    assert child.stderr.closed and child.stderr.close_calls == 1
    assert events.count("job-terminate") == (0 if failure == "stream-close-failure" else 1)
    assert events.count("popen-handle-close") == 1
    assert events.count("native-close:40961") == 1
    assert events.count("native-close:45057") == 1
    assert events.count("native-close:45058") == 1
    if failure == "reader-error":
        assert "Subprocess cleanup also failed" in " ".join(getattr(caught.value, "__notes__", []))
    if failure == "retained-pipe-descendant":
        assert child.stdout.read_started.is_set()
        assert "reader-cancel" in events


def test_windows_installed_consumer_readiness_failure_cleans_started_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    real_win_dll = cast(_FakeWinDLLFactory, vars(ctypes)["WinDLL"])
    opened = 0

    def _one_reader_fails_readiness(*args: object, **kwargs: object) -> object:
        nonlocal opened
        kernel = real_win_dll(*args, **kwargs)
        original_open = kernel.OpenThread

        def _open(*open_args: object) -> int:
            nonlocal opened
            opened += 1
            if opened == 2:
                events.append("reader-readiness-failure")
                return 0
            return cast(int, original_open(*open_args))

        kernel.OpenThread = _NativeFunction(_open)
        return kernel

    monkeypatch.setattr(ctypes, "WinDLL", _one_reader_fails_readiness, raising=False)

    class _Stream:
        def __init__(self, name: str) -> None:
            self.name = name
            self.closed = False
            self.close_calls = 0

        def read(self, _size: int) -> bytes:
            events.append(f"{self.name}-read")
            return b""

        def close(self) -> None:
            self.close_calls += 1
            self.closed = True
            events.append(f"{self.name}-close")

    class _Pipe:
        def write(self, payload: bytes) -> int:
            return len(payload)

        def close(self) -> None:
            pass

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe()
            self.stdout = _Stream("stdout")
            self.stderr = _Stream("stderr")
            self._handle = _Handle()
            self.returncode: int | None = None

        def wait(self, *, timeout: float) -> int:
            self.returncode = 0
            state["active"] = 0
            return 0

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(installed, "os", type("_Windows", (), {"name": "nt"})())

    with pytest.raises(ValueError, match="initialize qualification pipe reader"):
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))

    assert "reader-readiness-failure" in events
    assert "stdout-read" not in events and "stderr-read" not in events
    assert child.stdout.closed and child.stdout.close_calls == 1
    assert child.stderr.closed and child.stderr.close_calls == 1
    assert events.count("job-terminate") == 1
    assert events.count("native-close:40961") == 1
    assert events.count("native-close:45057") == 1
    assert events.count("popen-handle-close") == 1


def test_windows_sdist_consumer_reader_error_uses_real_owner_and_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    reader_instances: list[process.WindowsPipeReader] = []
    real_reader_factory = process.WindowsPipeReader

    def _record_real_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader_factory(stream, limit=limit)
        reader_instances.append(reader)
        return reader

    monkeypatch.setattr(process, "WindowsPipeReader", _record_real_reader)

    class _Stream:
        def __init__(self) -> None:
            self.failed = threading.Event()
            self.closed = False
            self.close_calls = 0

        def read(self, _size: int) -> bytes:
            self.failed.set()
            raise OSError("synthetic sdist reader failure")

        def close(self) -> None:
            self.closed = True
            self.close_calls += 1
            events.append("stdout-close")

    class _Pipe:
        def write(self, payload: bytes) -> int:
            return len(payload)

        def close(self) -> None:
            pass

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe()
            self.stdout = _Stream()
            self.stderr = None
            self._handle = _Handle()
            self.returncode: int | None = None
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            if self.wait_calls == 1:
                if reader_instances:
                    reader_instances[0].wait(timeout)
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            if state["active"] != 0:
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            self.returncode = 0
            return 0

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(sdist_build, "os", type("_Windows", (), {"name": "nt"})())

    with pytest.raises(ValueError, match="output reader failed") as caught:
        sdist_build._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=1.0, capture=True)

    assert "Qualification cleanup also failed" in " ".join(getattr(caught.value, "__notes__", []))
    assert child.wait_calls >= 2
    assert child.stdout.closed and child.stdout.close_calls == 1
    assert events.count("job-terminate") == 1
    assert events.count("native-close:40961") == 1
    assert events.count("native-close:45057") == 1
    assert events.count("popen-handle-close") == 1


def test_windows_pipe_reader_retains_limit_plus_one_and_supervisor_closes_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 123

        def OpenThread(self, *_args: object) -> int:
            return 91

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    stream = io.BytesIO(b"abcdefgh")
    reader = process.WindowsPipeReader(stream, limit=4, chunk_size=2)
    reader.start()
    assert reader.wait_ready(1.0)
    reader.release()
    assert reader.wait(1.0)
    assert reader.data == b"abcde"
    assert reader.overflowed is True
    assert stream.closed is False
    reader.close_stream()
    assert stream.closed is True


def test_live_windows_reader_cleanup_poisons_process_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_read = threading.Event()
    read_started = threading.Event()

    class _Stream:
        closed = False

        def read(self, _size: int) -> bytes:
            read_started.set()
            release_read.wait(2.0)
            return b""

        def close(self) -> None:
            self.closed = True

    class _Kernel:
        def GetCurrentThreadId(self) -> int:
            return 124

        def OpenThread(self, *_args: object) -> int:
            return 92

        def CancelSynchronousIo(self, _handle: int) -> int:
            return 1

        def CloseHandle(self, _handle: int) -> int:
            return 1

    monkeypatch.setattr(process, "_reader_kernel32", lambda: _Kernel())
    monkeypatch.setattr(process, "_READER_CLEANUP_SECONDS", 0.03)
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)
    reader = process.WindowsPipeReader(_Stream(), limit=4, chunk_size=2)
    reader.start()
    assert reader.wait_ready(1.0)
    reader.release()
    assert read_started.wait(1.0)
    with pytest.raises(process.ProcessCleanupIncomplete):
        reader.cancel_and_join()
    assert process._WINDOWS_OBSERVER_POISONED is True
    with pytest.raises(process.ProcessCleanupIncomplete):
        process.start_process(["synthetic-child"], windows=True)

    release_read.set()
    reader.thread.join(timeout=1.0)
    assert not reader.thread.is_alive()


@pytest.mark.skipif(os.name == "nt", reason="POSIX runner lifecycle integration")
def test_all_qualification_runners_use_the_shared_process_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[tuple[str, ...]] = []
    start_process = process.start_process

    def record_start(command: list[str], **kwargs: object) -> process.OwnedProcess:
        starts.append(tuple(command))
        return start_process(command, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(process, "start_process", record_start)

    focused_result = focused._run_command(
        [sys.executable, "-c", "print('focused')"],
        tmp_path,
        "Focused command failed.",
        timeout=3.0,
    )
    sdist_result = sdist_build._run_bounded(
        [sys.executable, "-I", "-c", "print('sdist')"],
        cwd=tmp_path,
        timeout=3.0,
        capture=True,
    )
    installed_result = installed._run_bounded(
        [sys.executable, "-c", "print('installed')"], cwd=tmp_path, timeout=3
    )

    assert focused_result.stdout == "focused\n"
    assert sdist_result.stdout == b"sdist\n"
    assert installed_result[1] == b"installed\n"
    assert len(starts) == 3


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group cleanup")
def test_group_signal_failure_still_kills_and_reaps_direct_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owned = process.start_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=None,
        stderr=None,
        windows=False,
    )

    def fail_group_signal(_process_group_id: int, _signal_number: int) -> None:
        raise ValueError("injected process-group signal failure")

    monkeypatch.setattr(process, "_signal_process_group", fail_group_signal)
    try:
        with pytest.raises(ValueError, match="Could not stop an owned qualification process group"):
            owned.terminate(grace_seconds=0.1, immediate=True)

        assert owned.process.poll() is not None
        assert owned.process.returncode is not None
    finally:
        if owned.process.poll() is None:
            owned.process.kill()
            owned.process.wait(timeout=3)


def test_windows_gate_stdin_close_failure_terminates_tree_and_disposes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Pipe:
        def __init__(self, name: str, *, fail_close: bool = False) -> None:
            self.name = name
            self.fail_close = fail_close

        def write(self, payload: bytes) -> int:
            events.append(f"{self.name}-write:{payload!r}")
            return len(payload)

        def close(self) -> None:
            events.append(f"{self.name}-close")
            if self.fail_close:
                raise OSError("synthetic gate stdin close failure")

    class _Handle:
        def Close(self) -> None:
            events.append("process-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe("stdin", fail_close=True)
            self.stdout = _Pipe("stdout")
            self.stderr = _Pipe("stderr")
            self._handle = _Handle()

        def wait(self, *, timeout: float) -> int:
            events.append("reap")
            return 0

        def kill(self) -> None:
            events.append("direct-child-kill")

    class _Job:
        def assign(self, _handle: object) -> None:
            events.append("assign")

        def terminate(self) -> None:
            events.append("job-terminate")

        def close(self) -> None:
            events.append("job-close")

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)

    with pytest.raises(OSError, match="synthetic gate stdin close failure"):
        process.start_process(
            ["synthetic-child"],
            windows=True,
            windows_job_factory=_Job,
            windows_gate_code=process.WINDOWS_GATE_CODE,
            bufsize=0,
        )

    assert events.count("stdin-write:b'G'") == 1
    assert events.index("assign") < events.index("stdin-write:b'G'")
    assert events.count("job-terminate") == 1
    assert events.count("reap") == 1
    assert events.count("process-handle-close") == 1
    assert events.count("job-close") == 1
    assert events.count("stdin-close") == 1
    assert events.count("stdout-close") == 1
    assert events.count("stderr-close") == 1
    assert events.index("stdin-write:b'G'") < events.index("job-terminate")
    assert events.index("job-terminate") < events.index("reap")
    assert events.index("reap") < events.index("process-handle-close")
    assert events.index("process-handle-close") < events.index("job-close")
    assert events.index("stdout-close") < events.index("job-close")
    assert events.index("stderr-close") < events.index("job-close")
    assert "direct-child-kill" not in events


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX fake-child fixture; native Windows gate requires separate controls",
)
@pytest.mark.parametrize(
    "payload, expect_overflow",
    [(b"a" * 65_536, False), (b"b" * 65_537, True)],
    ids=["at-limit", "one-byte-over-limit"],
)
def test_sdist_capture_enforces_64k_bound_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, expect_overflow: bool
) -> None:
    children: list[object] = []

    class _TrackedStream(io.BytesIO):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            super().close()

    class _Child:
        def __init__(self, payload: bytes) -> None:
            self.pid = 0x7FFF_FFFE
            self.returncode: int | None = None
            self.stdout = _TrackedStream(payload)
            self.stdin = None
            self.stderr = None
            self.kwargs: dict[str, object] = {}
            self.wait_calls = 0
            children.append(self)

        def wait(self, timeout: float) -> int:
            self.wait_calls += 1
            self.returncode = 0
            return 0

        def poll(self) -> int | None:
            return self.returncode

    child = _Child(payload)

    def _popen(_argv: list[str], **kwargs: object) -> _Child:
        child.kwargs = kwargs
        return child

    monkeypatch.setattr(subprocess, "Popen", _popen)
    monkeypatch.setattr(process, "process_group_exists", lambda _pid: False)

    if expect_overflow:
        with pytest.raises(ValueError, match="capture limit"):
            sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
    else:
        accepted = sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
        assert accepted.returncode == 0
        assert len(accepted.stdout) == 65_536
        assert accepted.stdout == b"a" * 65_536

    assert child.stdout.closed is True
    assert child.wait_calls >= 1
    assert child.returncode == 0
    assert child.stdout.close_calls == 1


def test_owned_process_preserves_primary_when_job_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Pipe:
        def write(self, payload: bytes) -> int:
            events.append(f"write:{payload!r}")
            return len(payload)

        def close(self) -> None:
            events.append("stdin-close")

    class _Handle:
        def Close(self) -> None:
            events.append("process-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe()
            self.stdout = None
            self.stderr = None
            self._handle = _Handle()
            self.returncode = None

        def wait(self, *, timeout: float) -> int:
            events.append("wait-primary-failure")
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)

    class _Job:
        def assign(self, _handle: object) -> None:
            events.append("assign")

        def terminate(self) -> None:
            events.append("job-cleanup-failure")
            raise RuntimeError("synthetic Job termination failure")

        def close(self) -> None:
            events.append("job-close")

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    owned = process.start_process(
        ["synthetic-child"],
        windows=True,
        windows_job_factory=_Job,
        windows_gate_code=process.WINDOWS_GATE_CODE,
        bufsize=0,
    )

    with pytest.raises(ValueError, match="reap and dispose") as raised:
        owned.reap_and_dispose_handle(timeout=0.1)
    primary = raised.value.__cause__
    assert isinstance(primary, subprocess.TimeoutExpired)
    assert any(
        "Windows Job cleanup also failed: RuntimeError" in note for note in primary.__notes__
    )
    owned.close()

    assert events.count("write:b'G'") == 1
    assert events.count("wait-primary-failure") == 1
    assert events.count("job-cleanup-failure") == 1
    assert events.count("process-handle-close") == 1
    assert events.count("job-close") == 1


@pytest.mark.parametrize(
    "payload, expect_overflow",
    [(b"a" * 65_536, False), (b"b" * 65_537, True)],
    ids=["at-limit", "one-byte-over-limit"],
)
def test_sdist_windows_capture_uses_real_reader_and_finalizes(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, expect_overflow: bool
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)

    class _WindowsPlatform:
        name = "nt"

    class _Pipe:
        def write(self, data: bytes) -> int:
            events.append(f"stdin-write:{data!r}")
            return len(data)

        def close(self) -> None:
            events.append("stdin-close")

    class _PopenHandle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _RawStream(io.BytesIO):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            events.append("stdout-close")
            super().close()

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe()
            self.stdout = _RawStream(payload)
            self.stderr = None
            self._handle = _PopenHandle()
            self.returncode: int | None = None
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            self.returncode = 0
            state["active"] = 0
            events.append("popen-wait")
            return self.returncode

    child = _Child()
    monkeypatch.setattr(sdist_build, "os", _WindowsPlatform())
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)

    if expect_overflow:
        with pytest.raises(ValueError, match="capture limit"):
            sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
    else:
        result = sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
        assert result.returncode == 0
        assert len(result.stdout) == 65_536
        assert result.stdout == b"a" * 65_536

    assert child.stdout.closed is True
    assert child.stdout.close_calls == 1
    assert child.wait_calls >= 1
    assert events.count("job-query") >= 1
    assert events.count("native-close:40961") == 1
    assert events.count("popen-handle-close") == 1
    assert events.count("native-close:45057") == 1


def test_posix_tree_termination_shares_one_five_second_fake_clock_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Clock:
        now = 0.0

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.now += seconds

    clock = _Clock()
    events: list[tuple[str, float]] = []

    class _Leader:
        def poll(self) -> None:
            return None

        def kill(self) -> None:
            events.append(("direct-kill", clock.now))

        def wait(self, *, timeout: float) -> int:
            events.append((f"direct-reap:{timeout}", clock.now))
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)

    leader = _Leader()
    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(process, "process_group_exists", lambda _pid: True)
    monkeypatch.setattr(
        process,
        "_signal_process_group",
        lambda _pid, sig: events.append((str(sig), clock.now)),
    )

    with pytest.raises(ValueError, match="process group safely"):
        process.terminate_process_group(
            4321,
            # The fixture implements the consumed poll/kill/wait surface.
            leader=cast(subprocess.Popen[bytes], leader),
            grace_seconds=3.0,
            immediate=False,
        )

    kill_time = next(at for signal_number, at in events if signal_number == str(signal.SIGKILL))
    assert kill_time <= 5.0
    assert clock.now <= 5.0


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX fake-child fixture; native Windows gate requires separate controls",
)
def test_sdist_timeout_shares_five_second_direct_reap_budget_with_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Clock:
        now = 0.0

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.now += seconds

    clock = _Clock()
    reap_waits: list[float] = []

    class _Child:
        pid = 5432
        stdout = None
        stderr = None
        returncode = None

        def __init__(self) -> None:
            self.wait_calls = 0

        def wait(self, timeout: float) -> int:
            self.wait_calls += 1
            if self.wait_calls == 1:
                clock.now += timeout
                raise subprocess.TimeoutExpired(["synthetic-child"], timeout)
            reap_waits.append(timeout)
            clock.now += timeout
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)

        def poll(self) -> None:
            return None

        def kill(self) -> None:
            return None

    child = _Child()
    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(sdist_build, "time", clock)
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(process, "process_group_exists", lambda _pid: True)
    monkeypatch.setattr(
        process,
        "_signal_process_group",
        lambda *_args: (_ for _ in ()).throw(ValueError("synthetic signal failure")),
    )

    with pytest.raises(ValueError, match="exceeded its timeout"):
        sdist_build._run_bounded(["synthetic-child"], timeout=0.01)

    assert reap_waits
    assert sum(reap_waits) <= 5.0


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX fake-child fixture; native Windows gate requires separate controls",
)
def test_sdist_consumer_preserves_reader_failure_when_pipe_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Stream:
        def __init__(self) -> None:
            self.close_calls = 0

        def read(self, _size: int) -> bytes:
            raise OSError("synthetic primary reader failure")

        def close(self) -> None:
            self.close_calls += 1
            raise RuntimeError("synthetic cleanup close failure")

    class _Child:
        pid = 6543
        stderr = None
        returncode = None

        def __init__(self) -> None:
            self.stdout = _Stream()
            self.wait_calls = 0

        def wait(self, timeout: float) -> int:
            self.wait_calls += 1
            self.returncode = 0
            return 0

        def poll(self) -> int:
            return self.returncode if self.returncode is not None else 0

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(process, "process_group_exists", lambda _pid: False)

    with pytest.raises(ValueError, match="output reader failed") as raised:
        sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)

    assert any("cleanup also failed: RuntimeError" in note for note in raised.value.__notes__)
    assert child.wait_calls >= 1
    assert child.stdout.close_calls >= 1


@pytest.mark.parametrize("consumer", ["sdist", "installed"], ids=["sdist", "installed"])
def test_posix_reader_constructor_baseexception_finalizes_owner(
    monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    events: list[str] = []
    group_active = [True]

    class _PosixPlatform:
        name = "posix"

    class _Stream(io.BytesIO):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            events.append("pipe-close")
            super().close()

    class _Child:
        pid = 7654

        def __init__(self) -> None:
            self.returncode: int | None = None
            self.stdout = _Stream(b"synthetic")
            self.stderr = None if consumer == "sdist" else _Stream(b"synthetic")
            self.stdin = None
            self.wait_calls = 0

        def wait(self, timeout: float) -> int:
            self.wait_calls += 1
            events.append("popen-wait")
            self.returncode = 0
            return 0

        def poll(self) -> int | None:
            return self.returncode

        def kill(self) -> None:
            events.append("popen-kill")

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(process, "process_group_exists", lambda _pid: group_active[0])

    def _signal_group(_pid: int, sig: int) -> None:
        events.append(f"group-signal:{sig}")
        group_active[0] = False

    monkeypatch.setattr(
        process,
        "_signal_process_group",
        _signal_group,
    )

    module = sdist_build if consumer == "sdist" else installed
    monkeypatch.setattr(module, "os", _PosixPlatform())
    real_threading = threading
    created_threads: list[threading.Thread] = []
    attempts = 0

    def _thread(*args: object, **kwargs: object) -> threading.Thread:
        nonlocal attempts
        attempts += 1
        if consumer == "sdist" or attempts == 2:
            raise KeyboardInterrupt("synthetic reader allocation failure")
        created = real_threading.Thread(*args, **kwargs)  # type: ignore[arg-type]
        created_threads.append(created)
        return created

    class _ThreadingFacade:
        Event = real_threading.Event

        Thread = staticmethod(_thread)

    monkeypatch.setattr(module, "threading", _ThreadingFacade())

    with pytest.raises(KeyboardInterrupt, match="synthetic reader allocation failure"):
        if consumer == "sdist":
            sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
        else:
            installed._run_bounded(["synthetic-child"], cwd=Path("."), timeout=1)

    assert events.count("group-signal:9") >= 1
    assert child.wait_calls >= 1
    assert child.stdout is not None
    assert child.stdout.closed is True
    assert child.stdout.close_calls == 1
    if consumer == "installed":
        assert child.stderr is not None
        assert child.stderr.closed is True
        assert child.stderr.close_calls == 1
        assert len(created_threads) == 1
        assert created_threads[0].ident is None
        assert not created_threads[0].is_alive()


@pytest.mark.parametrize("consumer", ["sdist", "installed"], ids=["sdist", "installed"])
def test_windows_reader_constructor_baseexception_finalizes_owner(
    monkeypatch: pytest.MonkeyPatch, consumer: str
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)

    class _WindowsPlatform:
        name = "nt"

    class _Pipe(io.BytesIO):
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            events.append("pipe-close")
            super().close()

    class _GatePipe:
        def write(self, payload: bytes) -> int:
            events.append(f"gate-write:{payload!r}")
            return len(payload)

        def close(self) -> None:
            events.append("gate-close")

    class _PopenHandle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        pid = 8765

        def __init__(self) -> None:
            self.stdin = _GatePipe()
            self.stdout = _Pipe(b"stdout")
            self.stderr = None if consumer == "sdist" else _Pipe(b"stderr")
            self._handle = _PopenHandle()
            self.returncode: int | None = None
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            events.append("popen-wait")
            self.returncode = 0
            state["active"] = 0
            return 0

        def poll(self) -> int | None:
            return self.returncode

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    module = sdist_build if consumer == "sdist" else installed
    monkeypatch.setattr(module, "os", _WindowsPlatform())
    real_reader = process.WindowsPipeReader
    created_readers: list[process.WindowsPipeReader] = []
    attempts = 0

    def _reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        nonlocal attempts
        attempts += 1
        if consumer == "sdist" or attempts == 2:
            raise KeyboardInterrupt("synthetic raw-reader allocation failure")
        reader = real_reader(stream, limit=limit)
        created_readers.append(reader)
        return reader

    monkeypatch.setattr(process, "WindowsPipeReader", _reader)

    with pytest.raises(KeyboardInterrupt, match="synthetic raw-reader allocation failure"):
        if consumer == "sdist":
            sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
        else:
            installed._run_bounded(["synthetic-child"], cwd=Path("."), timeout=1)

    assert events.count("job-terminate") == 1
    assert child.wait_calls >= 1
    assert child.stdout is not None
    assert child.stdout.closed is True
    assert child.stdout.close_calls == 1
    assert events.count("native-close:40961") == 1
    assert events.count("popen-handle-close") == 1
    if consumer == "installed":
        assert child.stderr is not None
        assert child.stderr.closed is True
        assert child.stderr.close_calls == 1
        assert len(created_readers) == 1
        assert created_readers[0].stream is child.stdout
        assert created_readers[0].thread.ident is None
        assert not created_readers[0].thread.is_alive()


class _InjectedCleanupBaseException(BaseException):
    pass


@pytest.mark.parametrize(
    "boundary",
    [
        "stdin-close",
        "stdout-close",
        "stderr-close",
        "job-terminate",
        "child-kill",
        "child-wait",
        "process-handle-close",
        "job-close",
    ],
    ids=[
        "stdin-close",
        "stdout-close",
        "stderr-close",
        "job-terminate",
        "child-kill",
        "child-wait",
        "process-handle-close",
        "job-close",
    ],
)
def test_windows_gate_cleanup_baseexception_preserves_primary_and_finishes(
    monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    events: list[str] = []
    primary = ValueError("synthetic assignment failure")

    class _Pipe:
        def __init__(self, name: str) -> None:
            self.name = name

        def close(self) -> None:
            events.append(self.name)
            if boundary == self.name:
                raise _InjectedCleanupBaseException(self.name)

        def write(self, _payload: bytes) -> int:
            events.append("gate-write")
            return 0

    class _Handle:
        def Close(self) -> None:
            events.append("process-handle-close")
            if boundary == "process-handle-close":
                raise _InjectedCleanupBaseException(boundary)

    class _Child:
        def __init__(self) -> None:
            self.stdin = _Pipe("stdin-close")
            self.stdout = _Pipe("stdout-close")
            self.stderr = _Pipe("stderr-close")
            self._handle = _Handle()

        def kill(self) -> None:
            events.append("child-kill")
            if boundary == "child-kill":
                raise _InjectedCleanupBaseException(boundary)

        def wait(self, *, timeout: float) -> int:
            events.append("child-wait")
            if boundary == "child-wait":
                raise _InjectedCleanupBaseException(boundary)
            return 1

    class _Job:
        def assign(self, _handle: object) -> None:
            events.append("job-assign")
            if boundary == "child-kill":
                raise primary

        def terminate(self) -> None:
            events.append("job-terminate")
            if boundary == "job-terminate":
                raise _InjectedCleanupBaseException(boundary)

        def close(self) -> None:
            events.append("job-close")
            if boundary == "job-close":
                raise _InjectedCleanupBaseException(boundary)

    child = _Child()
    monkeypatch.setattr(subprocess, "Popen", lambda *_args, **_kwargs: child)
    observed: BaseException | None = None
    try:
        process.start_process(
            ["synthetic-child"],
            windows=True,
            windows_job_factory=_Job,
            windows_gate_code=process.WINDOWS_GATE_CODE,
            bufsize=0,
        )
    except BaseException as error:
        observed = error

    assert isinstance(observed, ValueError)
    assert observed.__notes__ == [
        "Windows gate cleanup also failed: _InjectedCleanupBaseException."
    ]
    if boundary == "child-kill":
        assert observed is primary
    else:
        assert str(observed) == "Windows qualification gate release token was not fully written."
    assert events == (
        ["job-assign"]
        + ([] if boundary == "child-kill" else ["gate-write"])
        + [
            "stdin-close",
            "stdout-close",
            "stderr-close",
            "job-terminate",
        ]
        + ([] if boundary != "child-kill" else ["child-kill"])
        + ["child-wait", "process-handle-close", "job-close"]
    )
    assert events.count("gate-write") == (0 if boundary == "child-kill" else 1)


def test_windows_job_configuration_close_baseexception_preserves_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    primary = OSError("synthetic Job configuration failure")

    class _Kernel:
        def __init__(self) -> None:
            self.CreateJobObjectW = _NativeFunction(lambda *_args: 0xA001)

            def _configure_job(*_args: object) -> int:
                events.append("job-configure")
                return 0

            self.SetInformationJobObject = _NativeFunction(_configure_job)
            self.AssignProcessToJobObject = _NativeFunction(lambda *_args: 1)
            self.TerminateJobObject = _NativeFunction(lambda *_args: 1)
            self.QueryInformationJobObject = _NativeFunction(lambda *_args: 1)
            self.CloseHandle = _NativeFunction(self._close)

        def _close(self, _handle: object) -> int:
            events.append("job-close")
            raise _InjectedCleanupBaseException("configuration-close")

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)
    monkeypatch.setattr(process.WindowsJob, "_last_error", staticmethod(lambda _message: primary))
    observed: BaseException | None = None
    try:
        process.WindowsJob()
    except BaseException as error:
        observed = error

    assert observed is primary
    assert primary.__notes__ == [
        "Windows Job Object close also failed: _InjectedCleanupBaseException."
    ]
    assert events == ["job-configure", "job-close"]


@pytest.mark.parametrize(
    ("consumer", "scenario"),
    [
        ("installed", "failure"),
        ("installed", "descendant"),
        ("sdist", "failure"),
        ("sdist", "descendant"),
    ],
    ids=[
        "installed-failure",
        "installed-descendant",
        "sdist-failure",
        "sdist-descendant",
    ],
)
def test_windows_consumer_requests_reader_stop_before_job_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    consumer: str,
    scenario: str,
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    state["active"] = 1
    entered: list[threading.Event] = []
    release: list[threading.Event] = []
    readers: list[process.WindowsPipeReader] = []
    stop_at_job_cleanup: list[bool] = []
    stream_close_with_live_reader: list[bool] = []

    class _Pipe:
        def __init__(self) -> None:
            self.entered = threading.Event()
            self.release = threading.Event()
            entered.append(self.entered)
            release.append(self.release)

        def read(self, _size: int) -> bytes:
            self.entered.set()
            self.release.wait(1.0)
            return b""

        def close(self) -> None:
            stream_close_with_live_reader.append(
                any(reader.stream is self and reader.thread.is_alive() for reader in readers)
            )
            events.append("pipe-close")

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Pipe()
            self.stderr = None if consumer == "sdist" else _Pipe()
            self._handle = _Handle()
            self.returncode: int | None = None

        def wait(self, *, timeout: float) -> int:
            if scenario == "failure" and timeout <= 0.05:
                for ready in entered:
                    ready.wait(1.0)
                raise subprocess.TimeoutExpired("synthetic-child", timeout)
            self.returncode = -9 if scenario == "failure" else 0
            return self.returncode

    class _ReaderKernel:
        def __init__(self) -> None:
            self.handle = 0xB000

        def GetCurrentThreadId(self) -> int:
            return 91

        def OpenThread(self, *_args: object) -> int:
            self.handle += 1
            return self.handle

        def CancelSynchronousIo(self, _handle: object) -> int:
            return 1

        def CloseHandle(self, _handle: object) -> int:
            return 1

    child = _Child()
    job = process.WindowsJob()
    real_job_terminate = job.terminate

    def _observe_job_terminate() -> None:
        stop_at_job_cleanup.append(
            bool(readers) and all(reader.stop.is_set() for reader in readers)
        )
        for signal in release:
            signal.set()
        real_job_terminate()

    job.terminate = _observe_job_terminate  # type: ignore[method-assign]
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    real_reader = process.WindowsPipeReader

    def _make_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader(stream, limit=limit)
        readers.append(reader)
        return reader

    class _WindowsPlatform:
        name = "nt"

    module = sdist_build if consumer == "sdist" else installed
    monkeypatch.setattr(module, "os", _WindowsPlatform())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "WindowsPipeReader", _make_reader)
    monkeypatch.setattr(process, "_READER_CLEANUP_SECONDS", 0.3)
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)

    observed: BaseException | None = None
    try:
        if consumer == "installed":
            installed._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=cast(int, 0.08), output_limit=8
            )
        else:
            sdist_build._run_bounded(["synthetic-child"], timeout=0.08, capture=True)
    except BaseException as error:
        observed = error
    finally:
        for signal in release:
            signal.set()
        for reader in readers:
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=1.0)

    assert isinstance(observed, ValueError)
    assert stop_at_job_cleanup == [True]
    assert events.count("job-terminate") == 1
    assert stream_close_with_live_reader and not any(stream_close_with_live_reader)
    assert all(not reader.thread.is_alive() for reader in readers)
    assert events.count("popen-handle-close") == 1


def test_windows_initial_job_query_failure_still_terminates_before_reader_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    query_error = OSError("synthetic initial Job query failure")
    active = [1]
    query_calls = [0]
    pipe_closed_live: list[bool] = []
    readers: list[process.WindowsPipeReader] = []

    class _Kernel:
        def __init__(self) -> None:
            self.CreateJobObjectW = _NativeFunction(lambda *_args: 0xA001)
            self.SetInformationJobObject = _NativeFunction(lambda *_args: 1)
            self.AssignProcessToJobObject = _NativeFunction(lambda *_args: 1)
            self.TerminateJobObject = _NativeFunction(self._terminate)
            self.QueryInformationJobObject = _NativeFunction(self._query)
            self.CloseHandle = _NativeFunction(self._close)

        def _terminate(self, *_args: object) -> int:
            events.append("job-terminate")
            active[0] = 0
            return 1

        def _query(
            self,
            _handle: object,
            _kind: object,
            payload: ctypes._CArgObject,
            *_args: object,
        ) -> int:
            query_calls[0] += 1
            events.append("job-query")
            if query_calls[0] == 1:
                return 0
            info = ctypes.cast(
                payload, ctypes.POINTER(process._JobBasicAccountingInformation)
            ).contents
            info.ActiveProcesses = active[0]
            return 1

        @staticmethod
        def _close(_handle: object) -> int:
            events.append("job-close")
            return 1

    class _Pipe:
        def read(self, _size: int) -> bytes:
            return b""

        def close(self) -> None:
            pipe_closed_live.append(
                any(reader.stream is self and reader.thread.is_alive() for reader in readers)
            )
            events.append("pipe-close")

    class _PopenHandle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Pipe()
            self.stderr = _Pipe()
            self._handle = _PopenHandle()
            self.returncode: int | None = None

        def wait(self, *, timeout: float) -> int:
            events.append("popen-wait")
            self.returncode = 0
            return 0

    class _ReaderKernel:
        def GetCurrentThreadId(self) -> int:
            return 92

        def OpenThread(self, *_args: object) -> int:
            return 0xB092

        def CancelSynchronousIo(self, _handle: object) -> int:
            return 1

        def CloseHandle(self, _handle: object) -> int:
            return 1

    class _WindowsPlatform:
        name = "nt"

    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)
    monkeypatch.setattr(
        process.WindowsJob,
        "_last_error",
        staticmethod(lambda _message: query_error),
    )
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "_READER_CLEANUP_SECONDS", 0.3)
    monkeypatch.setattr(installed, "os", _WindowsPlatform())
    child = _Child()
    job = process.WindowsJob()
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)
    real_reader = process.WindowsPipeReader

    def _make_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader(stream, limit=limit)
        readers.append(reader)
        return reader

    monkeypatch.setattr(process, "WindowsPipeReader", _make_reader)
    observed: BaseException | None = None
    try:
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))
    except BaseException as error:
        observed = error
    finally:
        for reader in readers:
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=1.0)

    assert observed is query_error
    assert events.count("job-terminate") == 1
    assert events.index("job-terminate") < events.index("pipe-close")
    assert query_calls[0] >= 3
    assert events.count("job-close") == 1
    assert events.count("popen-handle-close") == 1
    assert pipe_closed_live == [False, False]
    assert all(not reader.thread.is_alive() for reader in readers)


def test_windows_second_reader_start_exception_finalizes_real_owner_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    state["active"] = 1
    streams_closed_live: list[bool] = []
    readers: list[process.WindowsPipeReader] = []
    primary = RuntimeError("synthetic second-reader start failure")

    class _Pipe:
        def __init__(self) -> None:
            self.closed = False

        def read(self, _size: int) -> bytes:
            return b""

        def close(self) -> None:
            self.closed = True
            streams_closed_live.append(
                any(reader.stream is self and reader.thread.is_alive() for reader in readers)
            )
            events.append("pipe-close")

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Pipe()
            self.stderr = _Pipe()
            self._handle = _Handle()
            self.returncode: int | None = None

        def wait(self, *, timeout: float) -> int:
            events.append("popen-wait")
            self.returncode = 0
            state["active"] = 0
            return 0

    class _ReaderKernel:
        def GetCurrentThreadId(self) -> int:
            return 93

        def OpenThread(self, *_args: object) -> int:
            return 0xB093

        def CancelSynchronousIo(self, _handle: object) -> int:
            return 1

        def CloseHandle(self, _handle: object) -> int:
            events.append("reader-close")
            return 1

    class _WindowsPlatform:
        name = "nt"

    child = _Child()
    job = process.WindowsJob()
    job_terminate_calls = [0]
    real_job_terminate = job.terminate

    def _count_job_terminate() -> None:
        job_terminate_calls[0] += 1
        real_job_terminate()

    job.terminate = _count_job_terminate  # type: ignore[method-assign]
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    real_reader = process.WindowsPipeReader

    def _make_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader(stream, limit=limit)
        readers.append(reader)
        return reader

    real_start = threading.Thread.start
    starts = [0]

    def _start(thread: threading.Thread) -> None:
        if thread.name == "qualification-raw-pipe":
            starts[0] += 1
            if starts[0] == 2:
                raise primary
        real_start(thread)

    monkeypatch.setattr(installed, "os", _WindowsPlatform())
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "WindowsPipeReader", _make_reader)
    monkeypatch.setattr(threading.Thread, "start", _start)

    observed: BaseException | None = None
    try:
        installed._run_bounded(["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0))
    except BaseException as error:
        observed = error
    finally:
        for reader in readers:
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=1.0)

    assert observed is primary
    assert starts == [2]
    assert job_terminate_calls == [1]
    assert events.count("job-terminate") == 1
    assert events.count("popen-handle-close") == 1
    assert events.count("native-close:40961") == 1
    assert events.count("reader-close") == 1
    assert len(readers) == 2
    assert all(not reader.thread.is_alive() for reader in readers)
    assert streams_closed_live == [False, False]


def test_windows_empty_job_failed_direct_reap_does_not_get_a_fresh_wait_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrying an empty-Job failed wait must not grant a fresh direct-reap budget."""
    events: list[str] = []
    _install_fake_windows_apis(monkeypatch, events)

    class _Handle:
        def Close(self) -> None:
            events.append("process-handle-close")

    class _Child:
        stdin = None
        stdout = None
        stderr = None
        returncode = None
        _handle = _Handle()

        def __init__(self) -> None:
            self.wait_timeouts: list[float] = []

        def wait(self, *, timeout: float) -> int:
            self.wait_timeouts.append(timeout)
            events.append("direct-wait")
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)

    child = _Child()
    job = process.WindowsJob()
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]

    with pytest.raises(subprocess.TimeoutExpired) as first_wait:
        owned.terminate(grace_seconds=0, immediate=True)
    first_timeout = first_wait.value
    assert first_timeout.timeout == 5.0
    with pytest.raises(ValueError, match="termination previously failed") as repeated_terminate:
        owned.terminate(grace_seconds=0, immediate=True)
    assert repeated_terminate.value.__cause__ is first_timeout
    with pytest.raises(ValueError, match="reap and dispose") as repeated_reap:
        owned.reap_and_dispose_handle(timeout=5.0)
    assert isinstance(repeated_reap.value.__cause__, TimeoutError)
    assert "child state remains unknown" in str(repeated_reap.value.__cause__)
    owned.close()

    assert child.wait_timeouts == [5.0]
    assert events.count("direct-wait") == 1
    assert events.count("job-query") == 1
    assert events.count("job-terminate") == 0
    assert events.count("process-handle-close") == 1
    assert events.count("native-close:40961") == 1


@pytest.mark.parametrize(
    ("consumer", "scenario"),
    [
        ("installed", "polling-descendant"),
        ("installed", "final-query-error"),
        ("installed", "healthy-drainage"),
        ("sdist", "polling-descendant"),
        ("sdist", "final-query-error"),
        ("sdist", "healthy-drainage"),
    ],
    ids=[
        "installed-polling-descendant",
        "installed-final-query-error",
        "installed-healthy-drainage",
        "sdist-polling-descendant",
        "sdist-final-query-error",
        "sdist-healthy-drainage",
    ],
)
def test_windows_consumers_retain_drainage_outcomes_and_cleanup_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    consumer: str,
    scenario: str,
) -> None:
    """Catch late-Job acceptance, tree cleanup before reader stop, or lost cleanup notes."""
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    allow_first_read = threading.Event()
    allow_descendant_exit = threading.Event()
    reader_read_started = threading.Event()
    descendant_read_started = threading.Event()
    readers: list[process.WindowsPipeReader] = []
    stop_at_tree_cleanup: list[tuple[bool, ...]] = []
    query_phases: list[str] = []
    polling_observations: list[tuple[tuple[bool, ...], tuple[bool, ...]]] = []
    empty_queries_after_tree_cleanup: list[int] = []
    pipe_close_with_live_reader: list[bool] = []
    query_error = OSError("synthetic final Job query failure")
    final_query_failure_injected = False
    tree_cleanup_completed = False
    final_query_phase: str | None = None
    final_query_done_state: tuple[bool, ...] = ()
    final_query_stop_state: tuple[bool, ...] = ()

    class _WindowsPlatform:
        name = "nt"

    class _Pipe:
        def __init__(self, name: str) -> None:
            self.name = name
            self.read_once = False

        def read(self, _size: int) -> bytes:
            events.append(f"{self.name}-read")
            if self.read_once:
                return b""
            self.read_once = True
            if not allow_first_read.wait(1.0):
                raise AssertionError("initial Job inspection did not release the reader")
            if scenario == "polling-descendant":
                descendant_read_started.set()
            reader_read_started.set()
            if scenario == "polling-descendant":
                allow_descendant_exit.wait(1.0)
            return b"drained"

        def close(self) -> None:
            events.append(f"{self.name}-close")
            pipe_close_with_live_reader.append(
                any(reader.stream is self and reader.thread.is_alive() for reader in readers)
            )
            if scenario == "final-query-error" and self.name == "stdout":
                raise RuntimeError("synthetic reader stream cleanup failure")

    class _PopenHandle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Pipe("stdout")
            self.stderr = None if consumer == "sdist" else _Pipe("stderr")
            self.stdin = None
            self._handle = _PopenHandle()
            self.returncode: int | None = None
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            events.append("child-wait")
            self.returncode = 0
            return 0

    class _ReaderKernel:
        def __init__(self) -> None:
            self.handle = 0xB100

        def GetCurrentThreadId(self) -> int:
            return 101

        def OpenThread(self, *_args: object) -> int:
            self.handle += 1
            return self.handle

        def CancelSynchronousIo(self, _handle: object) -> int:
            return 1

        def CloseHandle(self, _handle: object) -> int:
            return 1

    child = _Child()
    job = process.WindowsJob()

    def _query(_handle: object, _kind: object, payload: ctypes._CArgObject, *_args: object) -> int:
        nonlocal final_query_done_state, final_query_failure_injected
        nonlocal final_query_phase, final_query_stop_state
        events.append("job-query")
        done_state = tuple(reader.done.is_set() for reader in readers)
        stop_state = tuple(reader.stop.is_set() for reader in readers)
        if tree_cleanup_completed:
            phase = "post-tree-cleanup"
            empty_queries_after_tree_cleanup.append(state["active"])
        elif readers and all(done_state) and all(stop_state):
            phase = "final-query-after-drainage-and-stop"
        elif any(stop_state):
            phase = "cleanup-after-reader-stop"
        elif reader_read_started.is_set() and not all(done_state):
            phase = "reader-drainage"
        elif not reader_read_started.is_set():
            phase = "pre-drainage"
        else:
            phase = "drained-before-stop"
        query_phases.append(phase)

        if phase == "pre-drainage":
            allow_first_read.set()
            active = state["active"]
        elif scenario == "polling-descendant" and phase == "reader-drainage":
            if not descendant_read_started.is_set():
                raise AssertionError("reader did not enter the bounded descendant drain")
            active = 1
            state["active"] = active
            polling_observations.append((done_state, stop_state))
        else:
            active = state["active"]
            if (
                scenario == "final-query-error"
                and not final_query_failure_injected
                and phase == "final-query-after-drainage-and-stop"
            ):
                final_query_failure_injected = True
                final_query_phase = phase
                final_query_done_state = done_state
                final_query_stop_state = stop_state
                return 0
        info = ctypes.cast(payload, ctypes.POINTER(process._JobBasicAccountingInformation)).contents
        info.ActiveProcesses = active
        return 1

    kernel32 = job._kernel32
    terminate_job = kernel32.TerminateJobObject

    def _terminate_job(handle: object, exit_code: int) -> int:
        nonlocal tree_cleanup_completed
        events.append("tree-cleanup")
        stop_at_tree_cleanup.append(tuple(reader.stop.is_set() for reader in readers))
        result = int(terminate_job(handle, exit_code))
        tree_cleanup_completed = True
        allow_descendant_exit.set()
        return result

    kernel32.QueryInformationJobObject = _NativeFunction(_query)
    kernel32.TerminateJobObject = _NativeFunction(_terminate_job)
    monkeypatch.setattr(
        process.WindowsJob,
        "_last_error",
        staticmethod(lambda _message: query_error),
    )
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    real_reader = process.WindowsPipeReader

    def _make_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader(stream, limit=limit)
        readers.append(reader)
        return reader

    module = sdist_build if consumer == "sdist" else installed
    monkeypatch.setattr(module, "os", _WindowsPlatform())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "WindowsPipeReader", _make_reader)
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)

    observed: BaseException | None = None
    result: object | None = None
    production_terminal_reader_alive: tuple[bool, ...] = ()
    production_terminal_pipe_close_with_live_reader: tuple[bool, ...] = ()
    fixture_rescue_reader_alive: tuple[bool, ...] = ()
    try:
        if consumer == "installed":
            result = installed._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=1, output_limit=8
            )
        else:
            result = sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
    except BaseException as error:
        observed = error
    finally:
        production_terminal_reader_alive = tuple(reader.thread.is_alive() for reader in readers)
        production_terminal_pipe_close_with_live_reader = tuple(pipe_close_with_live_reader)
        # Bounded fixture rescue is intentionally separate from the captured production state.
        allow_first_read.set()
        allow_descendant_exit.set()
        for reader in readers:
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=1.0)
        fixture_rescue_reader_alive = tuple(reader.thread.is_alive() for reader in readers)

    assert readers
    assert production_terminal_reader_alive == tuple(False for _ in readers)
    assert production_terminal_pipe_close_with_live_reader == tuple(False for _ in readers)
    assert fixture_rescue_reader_alive == tuple(False for _ in readers)
    if scenario == "polling-descendant":
        assert isinstance(observed, ValueError)
        assert "retained active processes" in str(observed)
        assert observed.__cause__ is None
        assert getattr(observed, "__notes__", []) == [
            "Subprocess cleanup also failed: ValueError."
            if consumer == "installed"
            else "Qualification cleanup also failed: ValueError."
        ]
        expected_stops = (True, True) if consumer == "installed" else (True,)
        assert stop_at_tree_cleanup == [expected_stops]
        assert polling_observations
        assert all(
            not all(done_state) and not any(stop_state)
            for done_state, stop_state in polling_observations
        )
        assert (
            query_phases.index("reader-drainage")
            < query_phases.index("cleanup-after-reader-stop")
            < query_phases.index("post-tree-cleanup")
        )
        assert events.count("tree-cleanup") == 1
        assert events.count("job-terminate") == 1
        assert empty_queries_after_tree_cleanup
        assert empty_queries_after_tree_cleanup[0] == 0
        assert events.count("popen-handle-close") == 1
    elif scenario == "final-query-error":
        assert observed is query_error
        assert final_query_failure_injected
        assert final_query_phase == "final-query-after-drainage-and-stop"
        assert final_query_done_state == tuple(True for _ in readers)
        assert final_query_stop_state == tuple(True for _ in readers)
        expected_note = (
            "Subprocess cleanup also failed: ValueError."
            if consumer == "installed"
            else "Qualification cleanup also failed: ValueError."
        )
        assert getattr(query_error, "__notes__", []) == [expected_note]
        assert events.count("tree-cleanup") == 0
        assert events.count("stdout-close") == 1
        assert events.count("popen-handle-close") == 1
    else:
        assert observed is None
        if consumer == "installed":
            assert result == (0, b"drained", b"drained")
        else:
            assert result is not None
            assert result.returncode == 0  # type: ignore[attr-defined]
            assert result.stdout == b"drained"  # type: ignore[attr-defined]
        assert all(reader.done.is_set() for reader in readers)
        assert "final-query-after-drainage-and-stop" in query_phases
        assert events.count("tree-cleanup") == 0
        assert events.count("popen-handle-close") == 1


@pytest.mark.parametrize(
    ("consumer", "failure_phase"),
    [
        ("installed", "unfinished-reader-drainage"),
        ("sdist", "unfinished-reader-drainage"),
        ("sdist", "initial-post-child-query"),
    ],
    ids=[
        "installed-unfinished-reader-drainage-query-error",
        "sdist-unfinished-reader-drainage-query-error",
        "sdist-initial-query-error-terminates-before-reader-cleanup",
    ],
)
def test_windows_consumers_preserve_job_query_failures_by_reader_phase(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    consumer: str,
    failure_phase: str,
) -> None:
    """Catch query errors that are hidden, mis-phased, or skip explicit tree cleanup."""
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    allow_first_read = threading.Event()
    allow_pipe_exit = threading.Event()
    child_wait_completed = threading.Event()
    read_started: dict[str, threading.Event] = {}
    readers: list[process.WindowsPipeReader] = []
    stop_at_terminate: list[tuple[bool, ...]] = []
    pipe_closed_live: list[bool] = []
    query_error = OSError("synthetic Job query failure")
    terminate_error = OSError("synthetic TerminateJobObject failure")
    injected_phase: str | None = None
    injection_count = 0
    initial_query_observed = False
    injection_done_state: tuple[bool, ...] = ()
    injection_stop_state: tuple[bool, ...] = ()
    observed: BaseException | None = None
    production_terminal_reader_alive: tuple[bool, ...] = ()
    fixture_rescue_reader_alive: tuple[bool, ...] = ()

    class _WindowsPlatform:
        name = "nt"

    class _Pipe:
        def __init__(self, name: str) -> None:
            self.name = name
            self.read_calls = 0
            read_started[name] = threading.Event()

        def read(self, _size: int) -> bytes:
            self.read_calls += 1
            if self.read_calls > 1:
                return b""
            if not allow_first_read.wait(1.0):
                raise AssertionError("initial Job query did not release reader")
            read_started[self.name].set()
            if not allow_pipe_exit.wait(1.0):
                raise AssertionError("fixture did not release blocked reader")
            return b"drained"

        def close(self) -> None:
            events.append(f"{self.name}-close")
            pipe_closed_live.append(
                any(reader.stream is self and reader.thread.is_alive() for reader in readers)
            )

    class _PopenHandle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Pipe("stdout")
            self.stderr = None if consumer == "sdist" else _Pipe("stderr")
            self.stdin = None
            self._handle = _PopenHandle()
            self.returncode: int | None = None

        def wait(self, *, timeout: float) -> int:
            events.append("child-wait")
            self.returncode = 0
            child_wait_completed.set()
            return 0

    class _ReaderKernel:
        def __init__(self) -> None:
            self.next_handle = 0xB200

        def GetCurrentThreadId(self) -> int:
            return 201

        def OpenThread(self, *_args: object) -> int:
            self.next_handle += 1
            return self.next_handle

        def CancelSynchronousIo(self, _handle: object) -> int:
            events.append("reader-cancel")
            allow_pipe_exit.set()
            return 1

        def CloseHandle(self, _handle: object) -> int:
            events.append("reader-handle-close")
            return 1

    child = _Child()
    job = process.WindowsJob()
    kernel32 = job._kernel32

    def _query(_handle: object, _kind: object, payload: ctypes._CArgObject, *_args: object) -> int:
        nonlocal injected_phase, injection_count, initial_query_observed
        nonlocal injection_done_state, injection_stop_state
        if child_wait_completed.is_set() and injected_phase is None:
            if failure_phase == "initial-post-child-query":
                injected_phase = "initial-post-child-query"
            elif not initial_query_observed:
                initial_query_observed = True
                allow_first_read.set()
                info = ctypes.cast(
                    payload,
                    ctypes.POINTER(process._JobBasicAccountingInformation),
                ).contents
                info.ActiveProcesses = 0
                return 1
            else:
                for name, started in read_started.items():
                    if not started.wait(1.0):
                        raise AssertionError(f"{name} reader did not reach drainage")
                injection_done_state = tuple(reader.done.is_set() for reader in readers)
                injection_stop_state = tuple(reader.stop.is_set() for reader in readers)
                if all(injection_done_state) or any(injection_stop_state):
                    raise AssertionError("query error fixture did not reach unfinished drainage")
                injected_phase = "unfinished-reader-drainage"
            injection_count += 1
            state["active"] = 1
            events.append(f"query-error:{injected_phase}")
            return 0
        info = ctypes.cast(payload, ctypes.POINTER(process._JobBasicAccountingInformation)).contents
        info.ActiveProcesses = state["active"]
        return 1

    def _terminate_job(_handle: object, _exit_code: int) -> int:
        events.append("job-terminate")
        stop_at_terminate.append(tuple(reader.stop.is_set() for reader in readers))
        state["active"] = 0
        allow_first_read.set()
        allow_pipe_exit.set()
        return 0 if failure_phase == "initial-post-child-query" else 1

    kernel32.QueryInformationJobObject = _NativeFunction(_query)
    kernel32.TerminateJobObject = _NativeFunction(_terminate_job)
    monkeypatch.setattr(
        process.WindowsJob,
        "_last_error",
        staticmethod(lambda message: query_error if "inspect" in message else terminate_error),
    )
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    real_reader = process.WindowsPipeReader

    def _make_reader(stream: object, *, limit: int) -> process.WindowsPipeReader:
        reader = real_reader(stream, limit=limit)
        readers.append(reader)
        return reader

    module = installed if consumer == "installed" else sdist_build
    monkeypatch.setattr(module, "os", _WindowsPlatform())
    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "WindowsPipeReader", _make_reader)
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)
    try:
        if consumer == "installed":
            installed._run_bounded(
                ["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0), output_limit=8
            )
        else:
            sdist_build._run_bounded(["synthetic-child"], timeout=1.0, capture=True)
    except BaseException as error:
        observed = error
    finally:
        production_terminal_reader_alive = tuple(reader.thread.is_alive() for reader in readers)
        allow_first_read.set()
        allow_pipe_exit.set()
        for reader in readers:
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=1.0)
        fixture_rescue_reader_alive = tuple(reader.thread.is_alive() for reader in readers)

    assert observed is query_error
    assert injection_count == 1
    assert injected_phase == failure_phase
    assert readers
    assert production_terminal_reader_alive == tuple(False for _ in readers)
    assert fixture_rescue_reader_alive == tuple(False for _ in readers)
    assert pipe_closed_live == [False for _ in readers]
    assert len(stop_at_terminate) == 1
    assert stop_at_terminate[0] == tuple(True for _ in readers)
    assert events.count("job-terminate") == 1
    assert events.count("popen-handle-close") == 1
    assert events.index("job-terminate") < events.index("stdout-close")
    assert events.count("reader-handle-close") == len(readers)
    if failure_phase == "unfinished-reader-drainage":
        assert all(started.is_set() for started in read_started.values())
        assert injection_done_state == tuple(False for _ in readers)
        assert injection_stop_state == tuple(False for _ in readers)
        assert getattr(query_error, "__notes__", []) == []
    else:
        assert consumer == "sdist"
        assert getattr(query_error, "__notes__", []) == [
            "Qualification cleanup also failed: OSError."
        ]


def test_windows_owner_uses_one_budget_per_tree_reap_and_reader_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Observe separate modeled cleanup phases, not cap exhaustion or reentry behavior."""

    class _Clock:
        def __init__(self) -> None:
            self.now = 0.0

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.now += seconds

        def consume_pending(self, seconds: float) -> None:
            self.now += seconds

    clock = _Clock()
    events: list[str] = []
    state = _install_fake_windows_apis(monkeypatch, events)
    state["active"] = 1
    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(installed, "time", clock)

    class _WindowsPlatform:
        name = "nt"

    monkeypatch.setattr(installed, "os", _WindowsPlatform())

    class _Handle:
        def Close(self) -> None:
            events.append("popen-handle-close")

    readers: list[process.WindowsPipeReader] = []
    reader_deadlines: list[float | None] = []
    reader_allowances: list[float] = []
    reader_handle_ids: list[int] = []
    handle_to_pipe: dict[int, str] = {}
    cancel_pending_pipes: list[str] = []
    blocked_before_command: list[tuple[bool, ...]] = []
    tree_phase_start: list[float] = []
    tree_phase_end: list[float] = []
    tree_phase_spend: list[float] = []
    reap_phase_start: list[float] = []
    reap_phase_end: list[float] = []
    reap_phase_spend: list[float] = []
    reader_phase_start: list[float] = []
    reader_phase_end: list[float] = []
    reader_phase_spend: list[float] = []
    reader_phase_deadline: list[float] = []

    class _BudgetPhasePipe:
        def __init__(self, name: str) -> None:
            self.name = name
            self.started = threading.Event()
            self.release_read = threading.Event()
            self.completed = threading.Event()
            self.close_calls = 0
            pipes[name] = self

        def read(self, _size: int) -> bytes:
            self.started.set()
            if not self.release_read.wait(1.0):
                raise AssertionError("budget fixture did not release its pipe")
            self.completed.set()
            return b""

        def close(self) -> None:
            self.close_calls += 1
            events.append(f"{self.name}-close")

    pipes: dict[str, _BudgetPhasePipe] = {}

    class _Child:
        returncode = None
        stdin = None
        _handle = _Handle()

        def __init__(self) -> None:
            self.stdout = _BudgetPhasePipe("stdout")
            self.stderr = _BudgetPhasePipe("stderr")
            self.wait_timeouts: list[float] = []

        def wait(self, *, timeout: float) -> int:
            self.wait_timeouts.append(timeout)
            if "job-terminate" in events:
                reap_phase_start.append(clock.monotonic())
                events.append("direct-reap")
                clock.now += 1.0
                reap_phase_end.append(clock.monotonic())
                reap_phase_spend.append(reap_phase_end[-1] - reap_phase_start[-1])
                self.returncode = 0
                return 0
            if not blocked_before_command:
                if not all(pipe.started.wait(1.0) for pipe in pipes.values()):
                    raise AssertionError("both readers did not block before command timeout")
                blocked_before_command.append(
                    tuple(
                        pipe.started.is_set()
                        and not pipe.release_read.is_set()
                        and not pipe.completed.is_set()
                        for pipe in pipes.values()
                    )
                )
            events.append("command-wait")
            clock.now += timeout
            raise subprocess.TimeoutExpired(["synthetic-child"], timeout)

        def poll(self) -> None:
            return None

    child = _Child()
    job = process.WindowsJob()
    kernel32 = job._kernel32

    def _query(_handle: object, _kind: object, payload: ctypes._CArgObject, *_args: object) -> int:
        if tree_phase_start and state["active"] and clock.monotonic() - tree_phase_start[0] >= 2.0:
            state["active"] = 0
            tree_phase_end.append(clock.monotonic())
            tree_phase_spend.append(tree_phase_end[-1] - tree_phase_start[0])
        return _record_active_job(payload, state)

    def _terminate_job(_handle: object, _exit_code: int) -> int:
        events.append("job-terminate")
        tree_phase_start.append(clock.monotonic())
        return 1

    kernel32.QueryInformationJobObject = _NativeFunction(_query)
    kernel32.TerminateJobObject = _NativeFunction(_terminate_job)
    owned = process.OwnedProcess(child, windows=True, job=job)  # type: ignore[arg-type]
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)

    class _ReaderKernel:
        def GetCurrentThreadId(self) -> int:
            return threading.get_native_id()

        def OpenThread(self, *_args: object) -> int:
            current = threading.current_thread()
            reader = next(item for item in readers if item.thread is current)
            handle = 0xB300 + len(reader_handle_ids) + 1
            reader_handle_ids.append(handle)
            handle_to_pipe[handle] = cast(_BudgetPhasePipe, reader.stream).name
            return handle

        def CancelSynchronousIo(self, handle: int) -> int:
            pipe_name = handle_to_pipe[int(handle)]
            pipe = pipes[pipe_name]
            if not pipe.started.is_set() or pipe.completed.is_set():
                raise AssertionError("reader cancellation did not target a pending pipe")
            cancel_pending_pipes.append(pipe_name)
            events.append(f"reader-cancel:{pipe_name}:{handle}")
            clock.consume_pending(1.25)
            pipe.release_read.set()
            if not pipe.completed.wait(1.0):
                raise AssertionError("reader did not acknowledge cancellation release")
            return 1

        def CloseHandle(self, _handle: object) -> int:
            events.append("reader-handle-close")
            return 1

    class _TrackingReader(process.WindowsPipeReader):
        def __init__(self, stream: object, *, limit: int) -> None:
            super().__init__(stream, limit=limit)
            readers.append(self)

        def wait_ready(self, timeout: float) -> bool:
            ready = super().wait_ready(timeout)
            if ready:
                events.append(f"reader-ready:{cast(_BudgetPhasePipe, self.stream).name}")
            return ready

        def cancel_and_join(self, *, deadline: float | None = None) -> None:
            reader_deadlines.append(deadline)
            assert deadline is not None
            assert self.thread.is_alive()
            assert not self.done.is_set()
            reader_allowances.append(deadline - clock.monotonic())
            if not reader_phase_start:
                reader_phase_start.append(clock.monotonic())
                reader_phase_deadline.append(deadline)
            super().cancel_and_join(deadline=deadline)
            if cast(_BudgetPhasePipe, self.stream).name == "stderr":
                reader_phase_end.append(clock.monotonic())
                reader_phase_spend.append(reader_phase_end[-1] - reader_phase_start[0])

    monkeypatch.setattr(process, "_reader_kernel32", lambda: _ReaderKernel())
    monkeypatch.setattr(process, "WindowsPipeReader", _TrackingReader)
    monkeypatch.setattr(installed, "_MAX_TCK_SECONDS", 1.0)
    observed: BaseException | None = None
    production_terminal_reader_alive: tuple[bool, ...] = ()
    production_terminal_pipes: tuple[tuple[str, bool, bool, bool, int], ...] = ()
    production_terminal_time = 0.0
    production_terminal_events: tuple[str, ...] = ()
    production_terminal_deadlines: tuple[float | None, ...] = ()
    production_terminal_allowances: tuple[float, ...] = ()
    production_terminal_cancelled_pipes: tuple[str, ...] = ()
    production_terminal_handles: tuple[int, ...] = ()
    production_terminal_phases: tuple[tuple[float, ...], ...] = ()
    fixture_rescue_reader_alive: tuple[bool, ...] = ()
    try:
        installed._run_bounded(["synthetic-child"], cwd=Path("."), timeout=cast(int, 0.1))
    except BaseException as error:
        observed = error
    finally:
        production_terminal_reader_alive = tuple(reader.thread.is_alive() for reader in readers)
        production_terminal_pipes = tuple(
            (
                name,
                pipe.started.is_set(),
                pipe.release_read.is_set(),
                pipe.completed.is_set(),
                pipe.close_calls,
            )
            for name, pipe in pipes.items()
        )
        production_terminal_time = clock.monotonic()
        production_terminal_events = tuple(events)
        production_terminal_deadlines = tuple(reader_deadlines)
        production_terminal_allowances = tuple(reader_allowances)
        production_terminal_cancelled_pipes = tuple(cancel_pending_pipes)
        production_terminal_handles = tuple(reader_handle_ids)
        production_terminal_phases = (
            tuple(tree_phase_start + tree_phase_end + tree_phase_spend),
            tuple(reap_phase_start + reap_phase_end + reap_phase_spend),
            tuple(reader_phase_start + reader_phase_end + reader_phase_spend),
            tuple(reader_phase_deadline),
        )
        rescue_deadline = time.monotonic() + 1.0
        for pipe in pipes.values():
            pipe.release_read.set()
        for reader in readers:
            reader.stop.set()
            reader.release()
            if reader.thread.ident is not None:
                reader.thread.join(timeout=max(0.0, rescue_deadline - time.monotonic()))
        fixture_rescue_reader_alive = tuple(reader.thread.is_alive() for reader in readers)

    assert type(observed) is ValueError
    assert str(observed) == "Isolated subprocess exceeded its time limit."
    assert getattr(observed, "__notes__", []) == []
    assert blocked_before_command == [(True, True)]
    assert set(event for event in events if event.startswith("reader-ready:")) == {
        "reader-ready:stdout",
        "reader-ready:stderr",
    }
    assert reader_handle_ids == list(handle_to_pipe)
    assert len(set(reader_handle_ids)) == 2
    assert set(handle_to_pipe.values()) == {"stdout", "stderr"}
    assert cancel_pending_pipes == ["stdout", "stderr"]
    assert len(readers) == 2
    assert len(reader_deadlines) == 2
    assert reader_deadlines[0] == reader_deadlines[1]
    assert reader_allowances[1] == pytest.approx(reader_allowances[0] - 1.25)
    assert reader_allowances[0] <= 5.0
    assert len(tree_phase_start) == len(tree_phase_end) == len(tree_phase_spend) == 1
    assert tree_phase_spend[0] == pytest.approx(2.0)
    assert len(reap_phase_start) == len(reap_phase_end) == len(reap_phase_spend) == 1
    assert reap_phase_spend[0] == pytest.approx(1.0)
    assert child.wait_timeouts.count(5.0) == 1
    assert len(reader_phase_start) == len(reader_phase_end) == len(reader_phase_spend) == 1
    assert reader_phase_deadline == [reader_deadlines[0]]
    assert reader_phase_deadline[0] - reader_phase_start[0] == pytest.approx(5.0)
    assert reader_phase_spend[0] == pytest.approx(2.5)
    assert reader_phase_spend[0] <= reader_phase_deadline[0] - reader_phase_start[0]
    assert production_terminal_deadlines == tuple(reader_deadlines)
    assert production_terminal_allowances == tuple(reader_allowances)
    assert production_terminal_cancelled_pipes == tuple(cancel_pending_pipes)
    assert production_terminal_handles == tuple(reader_handle_ids)
    assert production_terminal_phases == (
        tuple(tree_phase_start + tree_phase_end + tree_phase_spend),
        tuple(reap_phase_start + reap_phase_end + reap_phase_spend),
        tuple(reader_phase_start + reader_phase_end + reader_phase_spend),
        tuple(reader_phase_deadline),
    )
    assert production_terminal_reader_alive == (False, False)
    assert production_terminal_pipes == (
        ("stdout", True, True, True, 1),
        ("stderr", True, True, True, 1),
    )
    assert fixture_rescue_reader_alive == (False, False)
    assert clock.monotonic() == production_terminal_time
    assert tuple(events[: len(production_terminal_events)]) == production_terminal_events
    assert events.index("job-terminate") < events.index("direct-reap")
    handles_by_pipe = {pipe: handle for handle, pipe in handle_to_pipe.items()}
    assert events.index("direct-reap") < events.index(
        f"reader-cancel:stdout:{handles_by_pipe['stdout']}"
    )
    assert events.index(f"reader-cancel:stdout:{handles_by_pipe['stdout']}") < events.index(
        f"reader-cancel:stderr:{handles_by_pipe['stderr']}"
    )
    assert [child.stdout.close_calls, child.stderr.close_calls] == [1, 1]
    assert len(reader_handle_ids) == 2
    assert len(set(reader_handle_ids)) == 2
    assert events.count("reader-handle-close") == 2
    assert events.count("job-terminate") == 1
    assert events.count("direct-reap") == 1
    assert events.count("popen-handle-close") == 1
    assert events.count("native-close:40961") == 1


def _record_active_job(payload: ctypes._CArgObject, state: dict[str, int]) -> int:
    info = ctypes.cast(payload, ctypes.POINTER(process._JobBasicAccountingInformation)).contents
    info.ActiveProcesses = state["active"]
    return 1


@pytest.mark.parametrize("deadline_mode", ["same", "later", "omitted"])
def test_poisoned_reader_cleanup_reentry_preserves_unresolved_ownership(
    monkeypatch: pytest.MonkeyPatch, deadline_mode: str
) -> None:
    class _Clock:
        now = 0.0

        def monotonic(self) -> float:
            return self.now

    class _Thread:
        def __init__(self, clock: _Clock) -> None:
            self.clock = clock
            self.join_timeouts: list[float | None] = []

        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float | None = None) -> None:
            self.join_timeouts.append(timeout)
            if timeout is not None:
                self.clock.now += timeout

    class _Stream:
        close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    class _Kernel:
        cancel_calls = 0
        close_calls = 0

        def CancelSynchronousIo(self, _handle: object) -> int:
            self.cancel_calls += 1
            return 1

        def CloseHandle(self, _handle: object) -> int:
            self.close_calls += 1
            return 1

    clock = _Clock()
    kernel = _Kernel()
    stream = _Stream()
    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(process, "_READER_CLEANUP_SECONDS", 0.1)
    monkeypatch.setattr(process, "_reader_kernel32", lambda: kernel)
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)
    monkeypatch.setattr(process, "_POISONED_READER_RESOURCES", [])
    reader = process.WindowsPipeReader(stream, limit=4)
    reader.thread = _Thread(clock)  # type: ignore[assignment]
    reader.thread_handle = 0xB501
    initial_deadline = 0.05

    first_failure: BaseException | None = None
    try:
        reader.cancel_and_join(deadline=initial_deadline)
    except BaseException as error:
        first_failure = error

    first_join_timeouts = tuple(cast(_Thread, reader.thread).join_timeouts)
    first_cancel_calls = kernel.cancel_calls
    first_handle_close_calls = kernel.close_calls
    first_stream_close_calls = stream.close_calls
    first_owned_references = tuple(process._POISONED_READER_RESOURCES)

    if deadline_mode == "same":
        reentry_deadline = initial_deadline
    elif deadline_mode == "later":
        reentry_deadline = clock.monotonic() + 0.05
    else:
        reentry_deadline = None

    reentry_clock_before = clock.monotonic()
    reentry_failure: BaseException | None = None
    try:
        reader.cancel_and_join(deadline=reentry_deadline)
    except BaseException as error:
        reentry_failure = error

    reentry_clock_after = clock.monotonic()
    reentry_join_timeouts = tuple(cast(_Thread, reader.thread).join_timeouts)
    reentry_cancel_calls = kernel.cancel_calls
    reentry_handle_close_calls = kernel.close_calls
    reentry_stream_close_calls = stream.close_calls
    reentry_owned_references = tuple(process._POISONED_READER_RESOURCES)
    reader_still_alive = reader.thread.is_alive()
    observer_poisoned = process._WINDOWS_OBSERVER_POISONED

    assert isinstance(first_failure, process.ProcessCleanupIncomplete)
    assert observer_poisoned is True
    assert first_owned_references == ((stream, reader.thread, reader.thread_handle),)
    assert isinstance(reentry_failure, process.ProcessCleanupIncomplete)
    assert all(reference in reentry_owned_references for reference in first_owned_references)
    assert reader_still_alive
    assert reentry_stream_close_calls == first_stream_close_calls
    assert reentry_handle_close_calls == first_handle_close_calls
    assert reentry_cancel_calls == first_cancel_calls
    assert reentry_join_timeouts == first_join_timeouts
    assert reentry_clock_after == reentry_clock_before
    assert first_stream_close_calls == 0


def test_installed_reader_poison_stops_second_reader_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Clock:
        now = 0.0

        def monotonic(self) -> float:
            return self.now

    class _WindowsPlatform:
        name = "nt"

    class _Stream:
        def __init__(self, name: str) -> None:
            self.name = name
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1

    class _Kernel:
        cancel_handles: list[int] = []
        close_handles: list[int] = []

        def CancelSynchronousIo(self, handle: int) -> int:
            self.cancel_handles.append(int(handle))
            return 1

        def CloseHandle(self, handle: int) -> int:
            self.close_handles.append(int(handle))
            return 1

    clock = _Clock()
    kernel = _Kernel()

    class _WorkerThread:
        def __init__(self, *, target: object, **_kwargs: object) -> None:
            self.reader: process.WindowsPipeReader = cast(
                process.WindowsPipeReader,
                target.__self__,  # type: ignore[attr-defined]
            )
            self.handle = 0xB601 + len(worker_threads)
            self.ident: int | None = None
            self.join_timeouts: list[float | None] = []
            worker_threads.append(self)

        def start(self) -> None:
            self.ident = self.handle
            self.reader.thread_handle = self.handle
            self.reader.ready.set()

        def is_alive(self) -> bool:
            return True

        def join(self, timeout: float | None = None) -> None:
            self.join_timeouts.append(timeout)
            if timeout is not None:
                clock.now += timeout

    worker_threads: list[_WorkerThread] = []

    class _Child:
        def __init__(self) -> None:
            self.stdout = _Stream("stdout")
            self.stderr = _Stream("stderr")
            self.wait_calls = 0

        def wait(self, *, timeout: float) -> int:
            self.wait_calls += 1
            raise primary_error

    class _Owned:
        job = None

        def __init__(self, child: _Child) -> None:
            self.process = child
            self.events: list[str] = []

        def terminate(self, *, grace_seconds: float, immediate: bool) -> None:
            self.events.append(f"terminate:{grace_seconds}:{immediate}")

        def reap_and_dispose_handle(self, *, timeout: float) -> int:
            self.events.append(f"reap:{timeout}")
            return 1

        def close(self) -> None:
            self.events.append("close")

    primary_error = LookupError("synthetic primary child failure")
    child = _Child()
    owned = _Owned(child)
    process_outcome: object = object()
    no_return = process_outcome
    observed_error: BaseException | None = None

    monkeypatch.setattr(installed, "os", _WindowsPlatform())
    monkeypatch.setattr(installed, "time", clock)
    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(process, "_READER_CLEANUP_SECONDS", 0.1)
    monkeypatch.setattr(process, "_WINDOWS_OBSERVER_POISONED", False)
    monkeypatch.setattr(process, "_POISONED_READER_RESOURCES", [])
    monkeypatch.setattr(process, "_reader_kernel32", lambda: kernel)
    monkeypatch.setattr(threading, "Thread", _WorkerThread)
    monkeypatch.setattr(process, "start_process", lambda *_args, **_kwargs: owned)

    try:
        process_outcome = installed._run_bounded(
            ["synthetic-child"], cwd=tmp_path, timeout=cast(int, 1.0)
        )
    except BaseException as error:
        observed_error = error

    retained_resources = tuple(process._POISONED_READER_RESOURCES)
    retained_summary = tuple(
        (stream, thread, handle) for stream, thread, handle in retained_resources
    )
    worker_waits = tuple(
        (worker.reader.stream, tuple(worker.join_timeouts)) for worker in worker_threads
    )
    cancel_handles = tuple(kernel.cancel_handles)
    close_handles = tuple(kernel.close_handles)
    stream_close_calls = (child.stdout.close_calls, child.stderr.close_calls)
    primary_error_notes = tuple(getattr(primary_error, "__notes__", []))
    observer_poisoned = process._WINDOWS_OBSERVER_POISONED
    clock_after_cleanup = clock.monotonic()
    child_wait_calls = child.wait_calls
    owner_events = tuple(owned.events)

    assert worker_waits[1][1] == ()
    assert observed_error is primary_error
    assert process_outcome is no_return
    assert primary_error_notes == ("Subprocess cleanup also failed: ProcessCleanupIncomplete.",)
    assert observer_poisoned is True
    assert tuple(
        (cast(_Stream, stream).name, handle) for stream, _thread, handle in retained_summary
    ) == (("stdout", 0xB601), ("stderr", 0xB602))
    assert len(retained_summary) == 2
    assert all(thread.is_alive() for _stream, thread, _handle in retained_summary)
    assert worker_waits[0][0] is child.stdout
    assert worker_waits[1][0] is child.stderr
    assert 0xB602 not in cancel_handles
    assert close_handles == ()
    assert stream_close_calls == (0, 0)
    assert child_wait_calls == 1
    assert owner_events[0] == "terminate:0:True"
    assert clock_after_cleanup <= 0.1


def test_windows_job_poll_wait_fits_remaining_allowance_and_owner_reentry_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check requested waits against allowance; this is not a wall-time claim."""

    class _Clock:
        now = 0.0
        deadline = 0.0
        requested_waits: list[tuple[float, float]] = []

        def monotonic(self) -> float:
            return self.now

        def sleep(self, seconds: float) -> None:
            self.requested_waits.append((seconds, self.deadline - self.now))
            self.now += seconds

    clock = _Clock()
    query_calls = 0
    active = 1

    class _Kernel:
        def __init__(self) -> None:
            self.CreateJobObjectW = _NativeFunction(lambda *_args: 0xA501)
            self.SetInformationJobObject = _NativeFunction(lambda *_args: 1)
            self.AssignProcessToJobObject = _NativeFunction(lambda *_args: 1)
            self.TerminateJobObject = _NativeFunction(self._terminate)
            self.QueryInformationJobObject = _NativeFunction(self._query)
            self.CloseHandle = _NativeFunction(lambda *_args: 1)

        def _terminate(self, *_args: object) -> int:
            clock.deadline = clock.monotonic() + 1.0
            return 1

        def _query(
            self,
            _handle: object,
            _kind: object,
            payload: ctypes._CArgObject,
            *_args: object,
        ) -> int:
            nonlocal active, query_calls
            query_calls += 1
            if query_calls == 2:
                clock.now = 0.99
            elif query_calls >= 3:
                active = 0
            info = ctypes.cast(
                payload, ctypes.POINTER(process._JobBasicAccountingInformation)
            ).contents
            info.ActiveProcesses = active
            return 1

    monkeypatch.setattr(process, "time", clock)
    monkeypatch.setattr(process, "TERMINATION_WAIT_SECONDS", 1.0)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: _Kernel(), raising=False)
    job = process.WindowsJob()
    job_failure: BaseException | None = None
    try:
        job.terminate()
    except BaseException as error:
        job_failure = error
    job.close()
    poll_wait_observations = tuple(clock.requested_waits)
    poll_terminal_clock = clock.monotonic()

    class _PopenHandle:
        close_calls = 0

        def Close(self) -> None:
            self.close_calls += 1

    class _Child:
        def __init__(self) -> None:
            self._handle = _PopenHandle()
            self.returncode: int | None = None
            self.wait_timeouts: list[float] = []

        def wait(self, *, timeout: float) -> int:
            self.wait_timeouts.append(timeout)
            self.returncode = 0
            return 0

    class _OwnedJob:
        terminate_calls = 0

        def terminate(self) -> None:
            self.terminate_calls += 1

        def active_processes(self) -> int:
            return 0

        def close(self) -> None:
            return None

    child = _Child()
    owned_job = _OwnedJob()
    owned = process.OwnedProcess(child, windows=True, job=owned_job)  # type: ignore[arg-type]
    owner_failures: list[BaseException] = []
    owner_results: list[int] = []
    for _ in range(2):
        try:
            owned.terminate(grace_seconds=0, immediate=True)
        except BaseException as error:
            owner_failures.append(error)
    for _ in range(2):
        try:
            owner_results.append(owned.reap_and_dispose_handle(timeout=1.0))
        except BaseException as error:
            owner_failures.append(error)
    owned.close()

    owner_terminate_calls = owned_job.terminate_calls
    owner_wait_timeouts = tuple(child.wait_timeouts)
    owner_handle_close_calls = child._handle.close_calls

    assert poll_wait_observations
    assert all(remaining > 0 for _requested, remaining in poll_wait_observations)
    assert all(requested <= remaining for requested, remaining in poll_wait_observations)
    assert job_failure is None
    assert poll_terminal_clock <= 1.0

    assert owner_failures == []
    assert owner_results == [0, 0]
    assert owner_terminate_calls == 1
    assert owner_wait_timeouts == (1.0,)
    assert owner_handle_close_calls == 1
