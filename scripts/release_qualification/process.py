"""Owned process lifecycle shared by release-qualification helpers."""

from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time
from typing import Any, cast

TERMINATION_WAIT_SECONDS = 5.0
PROCESS_GROUP_POLL_SECONDS = 0.05


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
            except Exception as close_error:
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
        if not self._kernel32.TerminateJobObject(self._handle, 1):
            raise self._last_error("Could not terminate Windows qualification Job Object.")
        deadline = time.monotonic() + TERMINATION_WAIT_SECONDS
        while self.active_processes() != 0:
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows qualification Job Object did not become empty.")
            time.sleep(0.02)

    def require_empty(self) -> None:
        if self.active_processes():
            self.terminate()
            raise ValueError("Windows qualification Job Object retained active processes.")

    def close(self) -> None:
        handle = getattr(self, "_handle", None)
        if handle:
            if not self._kernel32.CloseHandle(handle):
                raise self._last_error("Could not close Windows qualification Job Object.")
            self._handle = None


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

    def group_exists(self) -> bool:
        if self.windows:
            raise ValueError("POSIX process groups are unavailable on Windows.")
        return process_group_exists(self.process.pid)

    def terminate(self, *, grace_seconds: float, immediate: bool = False) -> None:
        if self.job is not None:
            self.job.terminate()
            self.process.wait(timeout=TERMINATION_WAIT_SECONDS)
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
        terminate_process_group(
            self.process.pid,
            leader=self.process,
            grace_seconds=grace_seconds,
            immediate=immediate,
        )

    def require_empty(self) -> None:
        if self.job is not None:
            self.job.require_empty()

    def close(self) -> None:
        if self.job is not None:
            self.job.close()


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
) -> OwnedProcess:
    """Start a child in an owned POSIX session or optional gated Windows Job."""
    use_windows = os.name == "nt" if windows is None else windows
    job: Any | None = None
    process: subprocess.Popen[bytes] | None = None
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
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            if process.stdin is None:
                raise ValueError("Windows qualification gate stdin was unavailable.")
            job.assign(process._handle)  # type: ignore[attr-defined]
            process.__dict__["_qualification_windows_job"] = job
            process.stdin.write(b"G")
            process.stdin.close()
        except BaseException as error:
            cleanup_errors: list[BaseException] = []
            if process is not None:
                try:
                    job.terminate()
                except Exception as caught_error:
                    cleanup_errors.append(caught_error)
                try:
                    process.kill()
                except Exception as caught_error:
                    cleanup_errors.append(caught_error)
                try:
                    process.wait(timeout=TERMINATION_WAIT_SECONDS)
                except Exception as caught_error:
                    cleanup_errors.append(caught_error)
            try:
                job.close()
            except Exception as caught_error:
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
    process_group_id: int, timeout: float, leader: subprocess.Popen[bytes] | None = None
) -> bool:
    deadline = time.monotonic() + timeout
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
) -> None:
    """Stop every member of an owned process group, failing closed if any remain."""
    try:
        if not process_group_exists(process_group_id):
            return
        _signal_process_group(process_group_id, signal.SIGKILL if immediate else signal.SIGTERM)
        if not immediate and _wait_process_group_exit(process_group_id, grace_seconds, leader):
            return
        _signal_process_group(process_group_id, signal.SIGKILL)
        if not _wait_process_group_exit(process_group_id, TERMINATION_WAIT_SECONDS, leader):
            raise ValueError(
                "Could not stop every member of the owned qualification process group."
            )
    except ValueError as error:
        if leader is not None:
            try:
                if leader.poll() is None:
                    leader.kill()
            except Exception as kill_error:
                error.add_note(f"Direct-child kill also failed: {type(kill_error).__name__}.")
            try:
                leader.wait(timeout=TERMINATION_WAIT_SECONDS)
            except Exception as wait_error:
                error.add_note(f"Direct-child reap also failed: {type(wait_error).__name__}.")
        raise ValueError("Could not stop an owned qualification process group safely.") from error
