"""Owned process lifecycle shared by release-qualification helpers."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any, cast

TERMINATION_WAIT_SECONDS = 5.0
PROCESS_GROUP_POLL_SECONDS = 0.05
_READER_CHUNK_BYTES = 64 * 1024
_READER_CLEANUP_SECONDS = 5.0
_WINDOWS_OBSERVER_POISONED = False
_POISONED_READER_RESOURCES: list[tuple[object, threading.Thread, object | None]] = []

WINDOWS_GATE_CODE = (
    "import subprocess,sys; "
    "token=sys.stdin.buffer.read(1); "
    "sys.exit(subprocess.run(sys.argv[1:], stdin=subprocess.DEVNULL, "
    "stdout=sys.stdout, stderr=sys.stderr).returncode) "
    "if token == b'G' else sys.exit(125)"
)


class ProcessCleanupIncomplete(ValueError):
    """Owned output resources remain live after their bounded cleanup window."""


def _reader_kernel32() -> Any:
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:
        raise ValueError("Windows pipe cancellation APIs are unavailable.")
    kernel32 = win_dll("kernel32", use_last_error=True)
    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = ctypes.c_uint32
    kernel32.OpenThread.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenThread.restype = ctypes.c_void_p
    kernel32.CancelSynchronousIo.argtypes = [ctypes.c_void_p]
    kernel32.CancelSynchronousIo.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    return kernel32


class WindowsPipeReader:
    """Bounded raw-pipe reader; supervisor retains sole stream-close ownership."""

    _THREAD_TERMINATE = 0x0001
    _ERROR_NOT_FOUND = 1168

    def __init__(self, stream: Any, *, limit: int, chunk_size: int = _READER_CHUNK_BYTES) -> None:
        if limit < 0 or chunk_size <= 0:
            raise ValueError("Windows pipe reader bounds are invalid.")
        self.stream = stream
        self.limit = limit
        self.chunk_size = min(chunk_size, _READER_CHUNK_BYTES)
        self.data = bytearray()
        self.overflowed = False
        self.errors: list[BaseException] = []
        self.failed = threading.Event()
        self.ready = threading.Event()
        self.release_read = threading.Event()
        self.stop = threading.Event()
        self.done = threading.Event()
        self.thread_handle: object | None = None
        self.thread = threading.Thread(target=self._run, name="qualification-raw-pipe", daemon=True)
        self._handle_closed = False
        self._stream_closed = False
        self._cleanup_incomplete = False

    def start(self) -> None:
        if _WINDOWS_OBSERVER_POISONED:
            raise ProcessCleanupIncomplete("Windows qualification observer is poisoned.")
        self.thread.start()

    def _run(self) -> None:
        try:
            kernel32 = _reader_kernel32()
            thread_id = kernel32.GetCurrentThreadId()
            handle = kernel32.OpenThread(self._THREAD_TERMINATE, 0, thread_id)
            if not handle:
                raise ValueError("Could not retain qualification pipe-reader thread handle.")
            self.thread_handle = handle
        except BaseException as error:
            self.errors.append(error)
            self.failed.set()
            self.ready.set()
            self.done.set()
            return
        self.ready.set()
        self.release_read.wait()
        try:
            while not self.stop.is_set():
                chunk = self.stream.read(self.chunk_size)
                if not chunk:
                    break
                remaining = self.limit + 1 - len(self.data)
                if remaining > 0:
                    self.data.extend(chunk[:remaining])
                if len(chunk) > remaining or len(self.data) > self.limit:
                    self.overflowed = True
        except BaseException as error:
            self.errors.append(error)
            self.failed.set()
        finally:
            self.done.set()

    def wait_ready(self, timeout: float) -> bool:
        if not self.ready.wait(timeout):
            return False
        if self.errors:
            raise ValueError("Could not initialize qualification pipe reader.") from self.errors[0]
        return self.thread_handle is not None

    def release(self) -> None:
        self.release_read.set()

    def wait(self, timeout: float) -> bool:
        return self.done.wait(timeout)

    def cancel_and_join(self, *, deadline: float | None = None) -> None:
        global _WINDOWS_OBSERVER_POISONED
        if self._cleanup_incomplete or _WINDOWS_OBSERVER_POISONED:
            if not any(
                stream is self.stream and thread is self.thread
                for stream, thread, _handle in _POISONED_READER_RESOURCES
            ):
                _POISONED_READER_RESOURCES.append((self.stream, self.thread, self.thread_handle))
            raise ProcessCleanupIncomplete(
                "Qualification cleanup incomplete: reader resources remain owned."
            )
        stop_at = deadline if deadline is not None else time.monotonic() + _READER_CLEANUP_SECONDS
        self.stop.set()
        self.release_read.set()
        try:
            kernel32 = _reader_kernel32()
        except BaseException as error:
            kernel32 = None
            self.errors.append(error)
        try:
            self.thread.join(timeout=min(0.05, max(0.0, stop_at - time.monotonic())))
        except BaseException as error:
            self.errors.append(error)
        while self.thread.is_alive() and time.monotonic() < stop_at:
            try:
                self.thread.join(timeout=min(0.02, max(0.0, stop_at - time.monotonic())))
            except BaseException as error:
                self.errors.append(error)
                break
            if not self.thread.is_alive():
                break
            handle = self.thread_handle
            if handle is None or kernel32 is None:
                continue
            try:
                if not kernel32.CancelSynchronousIo(handle):
                    get_last_error = getattr(ctypes, "get_last_error", lambda: 0)
                    if get_last_error() != self._ERROR_NOT_FOUND:
                        self.errors.append(ValueError("Could not cancel qualification pipe read."))
                        break
            except BaseException as error:
                self.errors.append(error)
                break
            # ERROR_NOT_FOUND is a completion/pre-read race; all retries share stop_at.
            try:
                self.thread.join(timeout=min(0.02, max(0.0, stop_at - time.monotonic())))
            except BaseException as error:
                self.errors.append(error)
                break
        try:
            self.thread.join(timeout=max(0.0, stop_at - time.monotonic()))
        except BaseException as error:
            self.errors.append(error)
        if self.thread.is_alive():
            _WINDOWS_OBSERVER_POISONED = True
            self._cleanup_incomplete = True
            if not any(
                stream is self.stream and thread is self.thread
                for stream, thread, _handle in _POISONED_READER_RESOURCES
            ):
                _POISONED_READER_RESOURCES.append((self.stream, self.thread, self.thread_handle))
            cleanup_error = ProcessCleanupIncomplete(
                "Qualification cleanup incomplete: live reader, raw pipe and thread handle "
                "remain owned."
            )
            if self.errors:
                cleanup_error.add_note(f"Reader cleanup errors: {len(self.errors)}.")
            raise cleanup_error
        self._close_owned_resources()
        if self.errors:
            raise ValueError(
                "Qualification pipe reader failed or could not be cleaned up."
            ) from self.errors[0]

    def close_stream(self) -> None:
        """Close completed raw stream once; caller must confirm worker termination first."""
        if self.thread.is_alive():
            raise ProcessCleanupIncomplete("Cannot close a raw pipe with a live reader.")
        if not self._stream_closed:
            self._stream_closed = True
            self.stream.close()

    def _close_owned_resources(self) -> None:
        failures: list[BaseException] = []
        try:
            self.close_stream()
        except BaseException as error:
            failures.append(error)
        if self.thread_handle is not None and not self._handle_closed:
            self._handle_closed = True
            try:
                result = _reader_kernel32().CloseHandle(self.thread_handle)
                if result is False or result == 0:
                    raise ValueError("Could not close qualification pipe-reader thread handle.")
            except BaseException as error:
                failures.append(error)
                self.failed.set()
        self.errors.extend(failures)


class _JobBasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JobIoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "ReadOperationCount",
            "WriteOperationCount",
            "OtherOperationCount",
            "ReadTransferCount",
            "WriteTransferCount",
            "OtherTransferCount",
        )
    ]


class _JobExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JobBasicLimitInformation),
        ("IoInfo", _JobIoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobBasicAccountingInformation(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaults", ctypes.c_uint32),
        ("TotalProcesses", ctypes.c_uint32),
        ("ActiveProcesses", ctypes.c_uint32),
        ("TotalTerminatedProcesses", ctypes.c_uint32),
    ]


class WindowsJob:
    """Own a kill-on-close Windows Job Object and verify its process tree."""

    _KILL_ON_CLOSE = 0x00002000
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1

    def __init__(self) -> None:
        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            raise ValueError("Windows Job Objects are unavailable.")
        self._kernel32: Any = win_dll("kernel32", use_last_error=True)
        self._configure_api()
        self._handle = self._kernel32.CreateJobObjectW(None, None)
        self._close_attempted = False
        self._close_error: BaseException | None = None
        self._termination_attempted = False
        if not self._handle:
            raise self._last_error("Could not create Windows qualification Job Object.")
        limits = _JobExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = self._KILL_ON_CLOSE
        try:
            if not self._kernel32.SetInformationJobObject(
                self._handle,
                self._JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                raise self._last_error("Could not configure Windows qualification Job Object.")
        except BaseException as error:
            try:
                self.close()
            except BaseException as close_error:
                error.add_note(
                    f"Windows Job Object close also failed: {type(close_error).__name__}."
                )
            raise

    def _configure_api(self) -> None:
        self._kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        self._kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        self._kernel32.SetInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
        ]
        self._kernel32.SetInformationJobObject.restype = ctypes.c_int
        self._kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        self._kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self._kernel32.TerminateJobObject.restype = ctypes.c_int
        self._kernel32.QueryInformationJobObject.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        self._kernel32.QueryInformationJobObject.restype = ctypes.c_int
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int

    @staticmethod
    def _last_error(message: str) -> OSError:
        get_last_error = getattr(ctypes, "get_last_error", lambda: 0)
        win_error = getattr(ctypes, "WinError", OSError)
        return cast(OSError, win_error(get_last_error(), message))

    def assign(self, process_handle: int) -> None:
        if not self._kernel32.AssignProcessToJobObject(self._handle, process_handle):
            raise self._last_error("Could not assign qualification gate to Job Object.")

    def active_processes(self) -> int:
        info = _JobBasicAccountingInformation()
        if not self._kernel32.QueryInformationJobObject(
            self._handle,
            self._JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
            None,
        ):
            raise self._last_error("Could not inspect Windows qualification Job Object.")
        return int(info.ActiveProcesses)

    def terminate(self) -> None:
        if self.active_processes() == 0:
            return
        self._termination_attempted = True
        if not self._kernel32.TerminateJobObject(self._handle, 1):
            raise self._last_error("Could not terminate Windows qualification Job Object.")
        deadline = time.monotonic() + TERMINATION_WAIT_SECONDS
        while self.active_processes() != 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Windows qualification Job Object did not become empty.")
            time.sleep(min(0.02, remaining))

    def require_empty(self) -> None:
        if self.active_processes():
            self.terminate()
            raise ValueError("Windows qualification Job Object retained active processes.")

    def close(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle:
            if self._close_attempted:
                if self._close_error is not None:
                    raise ValueError(
                        "Windows qualification Job Object close previously failed."
                    ) from self._close_error
                return
            self._close_attempted = True
            try:
                if not self._kernel32.CloseHandle(handle):
                    raise self._last_error("Could not close Windows qualification Job Object.")
                self._handle = None
            except BaseException as error:
                self._close_error = error
                raise


class OwnedProcess:
    """A direct child plus the process group or Job Object it owns."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        *,
        windows: bool,
        job: WindowsJob | Any | None = None,
    ) -> None:
        self.process = process
        self.windows = windows
        self.job = job
        self._handle_disposed = False
        self._handle_disposal_attempted = False
        self._handle_disposal_error: BaseException | None = None
        self._returncode: int | None = None
        self._reap_attempted = False
        self._termination_attempted = False
        self._termination_error: BaseException | None = None
        self._tree_cleanup_deadline: float | None = None
        self._direct_reap_deadline: float | None = None
        self._direct_reap_error: BaseException | None = None

    def group_exists(self) -> bool:
        if self.windows:
            raise ValueError("POSIX process groups are unavailable on Windows.")
        return process_group_exists(self.process.pid)

    def terminate(self, *, grace_seconds: float, immediate: bool = False) -> None:
        if self.windows and self._handle_disposed:
            raise ValueError("Cannot inspect or terminate a Windows child after handle disposal.")
        if self._termination_attempted:
            if self._termination_error is not None:
                raise ValueError(
                    "Owned qualification process termination previously failed."
                ) from self._termination_error
            return
        self._termination_attempted = True
        try:
            if self.job is not None:
                self.job.terminate()
                self._reap_attempted = True
                self._returncode = self.process.wait(timeout=TERMINATION_WAIT_SECONDS)
                if self.job.active_processes() != 0:
                    raise ValueError("Windows qualification Job Object retained active processes.")
                return
            if self.windows:
                try:
                    subprocess.run(
                        ["taskkill.exe", "/PID", str(self.process.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )
                except (OSError, subprocess.SubprocessError):
                    if self.process.poll() is None:
                        self.process.kill()
                return
            if self._tree_cleanup_deadline is None:
                self._tree_cleanup_deadline = time.monotonic() + TERMINATION_WAIT_SECONDS
            terminate_process_group(
                self.process.pid,
                leader=self.process,
                grace_seconds=grace_seconds,
                immediate=immediate,
                deadline=self._tree_cleanup_deadline,
                fallback_reap=self._reap_posix_child,
            )
        except BaseException as error:
            termination_attempted = bool(getattr(self.job, "_termination_attempted", True))
            query_only_failure = (
                self.job is not None
                and not termination_attempted
                and not self._reap_attempted
                and self._returncode is None
            )
            self._termination_attempted = not query_only_failure
            if self._termination_attempted:
                self._termination_error = error
            raise

    def require_empty(self) -> None:
        if self.job is not None:
            try:
                self.job.require_empty()
            except BaseException as error:
                if getattr(self.job, "_termination_attempted", True):
                    self._termination_attempted = True
                    self._termination_error = error
                raise

    def close(self) -> None:
        if self.job is not None:
            self.job.close()

    def reap_and_dispose_handle(self, *, timeout: float) -> int:
        """Cache terminal status, then dispose the Popen-owned Windows handle once."""
        if not self.windows:
            return self._reap_posix_child(timeout=timeout)
        if self._handle_disposed:
            if self._returncode is None:
                raise ValueError("Windows child state is unknown after handle disposal.")
            return self._returncode
        if self._handle_disposal_attempted:
            raise ValueError(
                "Could not reap and dispose the Windows qualification process."
            ) from self._handle_disposal_error
        primary: BaseException | None = None
        if self._returncode is None:
            cached_returncode = getattr(self.process, "returncode", None)
            if cached_returncode is not None:
                self._returncode = cached_returncode
            elif self._reap_attempted:
                primary = TimeoutError("Windows qualification child state remains unknown.")
            else:
                self._reap_attempted = True
                try:
                    self._returncode = self.process.wait(timeout=timeout)
                except BaseException as error:
                    primary = error
        if primary is not None and self.job is not None and not self._termination_attempted:
            self._termination_attempted = True
            try:
                self.job.terminate()
            except BaseException as cleanup_error:
                primary.add_note(
                    f"Windows Job cleanup also failed: {type(cleanup_error).__name__}."
                )
                self._termination_error = cleanup_error
        handle = getattr(self.process, "_handle", None)
        self._handle_disposal_attempted = True
        try:
            if handle is not None:
                handle.Close()
            self._handle_disposed = True
        except BaseException as error:
            self._handle_disposal_error = error
            if primary is None:
                primary = error
            else:
                primary.add_note(
                    f"Windows process-handle disposal also failed: {type(error).__name__}."
                )
        if primary is not None:
            raise ValueError(
                "Could not reap and dispose the Windows qualification process."
            ) from primary
        assert self._returncode is not None
        return self._returncode

    def _reap_posix_child(self, *, timeout: float = TERMINATION_WAIT_SECONDS) -> int:
        """Share one bounded direct-child reap attempt across cleanup paths."""
        if self._returncode is not None:
            return self._returncode
        cached_returncode = getattr(self.process, "returncode", None)
        if cached_returncode is None:
            cached_returncode = self.process.poll()
        if cached_returncode is not None:
            self._returncode = cached_returncode
            return cached_returncode

        now = time.monotonic()
        if self._direct_reap_deadline is None:
            self._direct_reap_deadline = now + min(timeout, TERMINATION_WAIT_SECONDS)
        if self._direct_reap_error is not None:
            raise ValueError(
                "Owned qualification child reaping previously failed."
            ) from self._direct_reap_error
        remaining = self._direct_reap_deadline - now
        if remaining <= 0:
            error = TimeoutError("Owned qualification child reaping deadline expired.")
            self._direct_reap_error = error
            raise error
        try:
            self._returncode = self.process.wait(timeout=remaining)
        except BaseException as error:
            self._direct_reap_error = error
            raise
        return self._returncode


def start_process(
    command: list[str],
    *,
    cwd: Any = None,
    env: dict[str, str] | None = None,
    stdin: Any = None,
    stdout: Any = subprocess.PIPE,
    stderr: Any = subprocess.PIPE,
    windows: bool | None = None,
    windows_job_factory: Any = WindowsJob,
    windows_gate_code: str | None = None,
    bufsize: int = -1,
) -> OwnedProcess:
    """Start a child in an owned POSIX session or optional gated Windows Job."""
    use_windows = os.name == "nt" if windows is None else windows
    if use_windows and _WINDOWS_OBSERVER_POISONED:
        raise ProcessCleanupIncomplete("Windows qualification observer is poisoned.")
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("Qualification command must be a nonempty shell-free argv.")
    job: Any | None = None
    process: subprocess.Popen[bytes] | None = None
    release_attempted = False
    close_attempted: set[int] = set()
    if use_windows and windows_gate_code is not None:
        job = windows_job_factory()
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", windows_gate_code, *command],
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                bufsize=bufsize,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            if process.stdin is None:
                raise ValueError("Windows qualification gate stdin was unavailable.")
            job.assign(process._handle)  # type: ignore[attr-defined]
            process.__dict__["_qualification_windows_job"] = job
            release_attempted = True
            if process.stdin.write(b"G") != 1:
                raise ValueError("Windows qualification gate release token was not fully written.")
            process.__dict__["_qualification_gate_released"] = True
            close_attempted.add(id(process.stdin))
            process.stdin.close()
        except BaseException as error:
            cleanup_errors: list[BaseException] = []
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None and id(stream) not in close_attempted:
                        close_attempted.add(id(stream))
                        try:
                            stream.close()
                        except BaseException as caught_error:
                            cleanup_errors.append(caught_error)
                try:
                    job.terminate()
                except BaseException as caught_error:
                    cleanup_errors.append(caught_error)
                if not release_attempted:
                    try:
                        process.kill()
                    except BaseException as caught_error:
                        cleanup_errors.append(caught_error)
                try:
                    process.wait(timeout=TERMINATION_WAIT_SECONDS)
                except BaseException as caught_error:
                    cleanup_errors.append(caught_error)
                try:
                    process._handle.Close()  # type: ignore[attr-defined]
                except BaseException as caught_error:
                    cleanup_errors.append(caught_error)
            try:
                job.close()
            except BaseException as caught_error:
                cleanup_errors.append(caught_error)
            for cleanup_error in cleanup_errors:
                error.add_note(f"Windows gate cleanup also failed: {type(cleanup_error).__name__}.")
            raise
    else:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                bufsize=bufsize,
                start_new_session=not use_windows,
            )
        except OSError:
            raise
    assert process is not None
    return OwnedProcess(process, windows=use_windows, job=job)


def process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        raise ValueError("Could not inspect the owned qualification process group.") from error
    return True


def _signal_process_group(process_group_id: int, signal_number: int) -> None:
    try:
        os.killpg(process_group_id, signal_number)
    except ProcessLookupError:
        return
    except OSError as error:
        raise ValueError("Could not signal the owned qualification process group.") from error


def _wait_process_group_exit(
    process_group_id: int,
    timeout: float | None = None,
    leader: subprocess.Popen[bytes] | None = None,
    *,
    deadline: float | None = None,
) -> bool:
    if deadline is None:
        deadline = time.monotonic() + max(0.0, timeout or 0.0)
    while process_group_exists(process_group_id):
        if leader is not None:
            leader.poll()
            if not process_group_exists(process_group_id):
                return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(PROCESS_GROUP_POLL_SECONDS, remaining))
    return True


def terminate_process_group(
    process_group_id: int,
    *,
    leader: subprocess.Popen[bytes] | None = None,
    grace_seconds: float = TERMINATION_WAIT_SECONDS,
    immediate: bool = False,
    deadline: float | None = None,
    fallback_reap: Callable[[], int] | None = None,
) -> None:
    """Stop every member of an owned process group, failing closed if any remain."""
    now = time.monotonic()
    cleanup_deadline = min(
        deadline if deadline is not None else now + TERMINATION_WAIT_SECONDS,
        now + TERMINATION_WAIT_SECONDS,
    )
    try:
        if not process_group_exists(process_group_id):
            return
        _signal_process_group(process_group_id, signal.SIGKILL if immediate else signal.SIGTERM)
        grace_deadline = min(cleanup_deadline, now + max(0.0, grace_seconds))
        if not immediate and _wait_process_group_exit(
            process_group_id, leader=leader, deadline=grace_deadline
        ):
            return
        _signal_process_group(process_group_id, signal.SIGKILL)
        if not _wait_process_group_exit(process_group_id, leader=leader, deadline=cleanup_deadline):
            raise ValueError(
                "Could not stop every member of the owned qualification process group."
            )
    except ValueError as error:
        if leader is not None:
            try:
                if leader.poll() is None:
                    leader.kill()
            except BaseException as kill_error:
                error.add_note(f"Direct-child kill also failed: {type(kill_error).__name__}.")
            try:
                if fallback_reap is not None:
                    fallback_reap()
                else:
                    leader.wait(timeout=TERMINATION_WAIT_SECONDS)
            except BaseException as wait_error:
                error.add_note(f"Direct-child reap also failed: {type(wait_error).__name__}.")
        raise ValueError("Could not stop an owned qualification process group safely.") from error
