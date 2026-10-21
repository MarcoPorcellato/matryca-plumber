"""Small POSIX process reader for the installed operational TCK."""

from __future__ import annotations

import errno
import os
import selectors
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, cast


@dataclass(frozen=True, slots=True)
class ChildResult:
    """Bounded child result after the complete owned process group has exited."""

    returncode: int
    stdout: bytes
    stderr: bytes
    cleanup_ok: bool
    cleanup_events: tuple[str, ...] = ()


class ChildFailure(RuntimeError):
    """Sanitized primary process failure plus independent cleanup evidence."""

    def __init__(
        self,
        reason: str,
        *,
        cleanup_ok: bool,
        cleanup_events: tuple[str, ...] = (),
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.cleanup_ok = cleanup_ok
        self.cleanup_events = cleanup_events


def _note(events: list[str], event: str) -> None:
    """Retain only fixed, sanitized cleanup event names."""
    if event not in events:
        events.append(event)


def _note_term_signal_failure(events: list[str], error: BaseException) -> None:
    """Classify an already-caught failure without exposing arbitrary exception data."""
    _note(events, "term_signal_failed")
    try:
        if isinstance(error, PermissionError):
            category = "permission_error"
        elif isinstance(error, InterruptedError):
            category = "interrupted_error"
        elif isinstance(error, OSError):
            category = "os_error"
        elif isinstance(error, KeyboardInterrupt):
            category = "keyboard_interrupt"
        elif isinstance(error, SystemExit):
            category = "system_exit"
        elif isinstance(error, Exception):
            category = "exception"
        else:
            category = "base_exception"
        _note(events, f"term_signal_type_{category}_failed")

        errno_category = "not_applicable"
        if isinstance(error, OSError):
            try:
                number = error.errno
                if number is None:
                    errno_category = "unavailable"
                elif type(number) is int:
                    errno_category = {
                        errno.EPERM: "eperm",
                        errno.EACCES: "eacces",
                        errno.EINTR: "eintr",
                        errno.EINVAL: "einval",
                    }.get(number, "other")
                else:
                    errno_category = "unknown"
            except BaseException:
                errno_category = "unknown"
        _note(events, f"term_signal_errno_{errno_category}_failed")
    except BaseException:
        _note(events, "term_signal_diagnostics_failed")


def _group_state(group_id: int) -> bool | None:
    """Return whether a process group exists, or None when the check is uncertain."""
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        return None
    except BaseException:
        return None
    return True


def _remaining(deadline: float, events: list[str]) -> float:
    try:
        return max(0.0, deadline - time.monotonic())
    except BaseException:
        _note(events, "cleanup_clock_failed")
        return 0.0


def _cleanup_group(process: subprocess.Popen[bytes], deadline: float, events: list[str]) -> bool:
    """Stop and reap only this child group before one absolute deadline."""
    try:
        returncode = process.poll()
    except BaseException:
        returncode = None
        _note(events, "process_poll_failed")
    state = _group_state(process.pid)
    if state is None:
        _note(events, "group_check_failed")
    if returncode is not None and state is False:
        return True

    term_failed = False
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as error:
        if error.errno != errno.ESRCH:
            term_failed = True
            _note_term_signal_failure(events, error)
    except BaseException as error:
        term_failed = True
        _note_term_signal_failure(events, error)

    remaining = _remaining(deadline, events)
    kill_at = 0.0 if term_failed else remaining * 0.5
    kill_immediately = term_failed
    kill_sent = False
    poll_failed = False
    group_check_failed = False
    while True:
        try:
            returncode = process.poll()
        except BaseException:
            returncode = None
            if not poll_failed:
                _note(events, "process_poll_failed")
                poll_failed = True
        state = _group_state(process.pid)
        if state is None and not group_check_failed:
            _note(events, "group_check_failed")
            group_check_failed = True
        if returncode is not None and state is False:
            return True

        remaining = _remaining(deadline, events)
        if not kill_sent and (kill_immediately or remaining <= 0 or remaining <= kill_at):
            kill_sent = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as error:
                if error.errno != errno.ESRCH:
                    _note(events, "kill_signal_failed")
            except BaseException:
                _note(events, "kill_signal_failed")
        if remaining <= 0:
            break

        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            pass
        except InterruptedError:
            continue
        except BaseException:
            _note(events, "process_reap_failed")
        try:
            time.sleep(min(0.01, _remaining(deadline, events)))
        except InterruptedError:
            continue
        except BaseException:
            _note(events, "cleanup_wait_failed")

    try:
        returncode = process.poll()
    except BaseException:
        returncode = None
        _note(events, "process_poll_failed")
    state = _group_state(process.pid)
    if state is None:
        _note(events, "group_check_failed")
    return returncode is not None and state is False


def _kill_reap_fallback(
    process: subprocess.Popen[bytes], deadline: float, events: list[str]
) -> bool:
    """Independently force-stop and reap the owned group under the existing deadline."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError as error:
        if error.errno != errno.ESRCH:
            _note(events, "fallback_kill_failed")
    except BaseException:
        _note(events, "fallback_kill_failed")

    poll_failed = False
    group_check_failed = False
    while True:
        try:
            returncode = process.poll()
        except BaseException:
            returncode = None
            if not poll_failed:
                _note(events, "fallback_poll_failed")
                poll_failed = True
        state = _group_state(process.pid)
        if state is None and not group_check_failed:
            _note(events, "fallback_group_check_failed")
            group_check_failed = True
        if returncode is not None and state is False:
            return True

        remaining = _remaining(deadline, events)
        if remaining <= 0:
            return False
        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            pass
        except InterruptedError:
            continue
        except BaseException:
            _note(events, "fallback_reap_failed")
        try:
            time.sleep(min(0.01, _remaining(deadline, events)))
        except InterruptedError:
            continue
        except BaseException:
            _note(events, "fallback_wait_failed")


def _finalize_child(
    process: subprocess.Popen[bytes],
    selector: selectors.BaseSelector | None,
    streams: dict[IO[bytes], bytearray],
    cleanup_budget: float,
    events: list[str],
) -> bool:
    """Finalize group first, then independently close every parent-owned reader."""
    try:
        deadline = time.monotonic() + cleanup_budget
    except BaseException:
        _note(events, "cleanup_clock_failed")
        deadline = 0.0

    group_ok = False
    try:
        group_ok = _cleanup_group(process, deadline, events)
    except BaseException:
        _note(events, "group_finalize_failed")
    if not group_ok:
        try:
            group_ok = _kill_reap_fallback(process, deadline, events)
        except BaseException:
            _note(events, "fallback_finalize_failed")
            group_ok = False

    selector_ok = selector is None
    if selector is not None:
        try:
            selector.close()
            selector_ok = True
        except BaseException:
            _note(events, "selector_close_failed")

    streams_ok = True
    for name in ("stdout", "stderr"):
        try:
            stream = getattr(process, name)
            if stream is None:
                continue
            if not stream.closed:
                stream.close()
            if not stream.closed:
                streams_ok = False
                _note(events, "pipe_close_unverified")
        except BaseException:
            streams_ok = False
            _note(events, "pipe_close_failed")
    try:
        for stream in streams:
            try:
                if not stream.closed:
                    stream.close()
                if not stream.closed:
                    streams_ok = False
                    _note(events, "pipe_close_unverified")
            except BaseException:
                streams_ok = False
                _note(events, "pipe_close_failed")
    except BaseException:
        streams_ok = False
        _note(events, "pipe_inventory_failed")

    try:
        if time.monotonic() >= deadline:
            _note(events, "cleanup_deadline_exceeded")
            group_ok = False
    except BaseException:
        _note(events, "cleanup_clock_failed")
        group_ok = False

    return group_ok and selector_ok and streams_ok and not events


def _run_child(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    execution_timeout: float = 180.0,
    cleanup_budget: float = 5.0,
    max_stdout_bytes: int = 4_194_304,
    max_stderr_bytes: int = 512,
) -> ChildResult:
    """Run one owned POSIX process group with bounded output and fail-closed cleanup."""
    if (
        os.name != "posix"
        or not isinstance(argv, Sequence)
        or isinstance(argv, (str, bytes))
        or not argv
        or any(type(value) is not str or not value or "\x00" in value for value in argv)
        or not isinstance(cwd, Path)
        or cwd.is_symlink()
        or not cwd.is_dir()
        or not isinstance(env, Mapping)
        or any(
            type(key) is not str
            or not key
            or "=" in key
            or "\x00" in key
            or type(value) is not str
            or "\x00" in value
            for key, value in env.items()
        )
        or type(execution_timeout) not in (int, float)
        or not 0 < execution_timeout <= 180.0
        or type(cleanup_budget) not in (int, float)
        or not 0 < cleanup_budget <= 5.0
        or type(max_stdout_bytes) is not int
        or not 0 < max_stdout_bytes <= 4_194_304
        or type(max_stderr_bytes) is not int
        or not 0 < max_stderr_bytes <= 512
    ):
        raise ChildFailure("invalid_invocation", cleanup_ok=True)

    streams: dict[IO[bytes], bytearray] = {}
    selector: selectors.BaseSelector | None = None
    events: list[str] = []
    failure: str | None = None
    stdout_stream: IO[bytes] | None = None
    stderr_stream: IO[bytes] | None = None
    try:
        # Private TCK callers supply the current interpreter and fixed arguments.
        # The TCK interface accepts no user-supplied command or interpreter flags.
        process = subprocess.Popen(  # noqa: S603
            list(argv),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
        )
    except OSError:
        raise ChildFailure("startup_error", cleanup_ok=True) from None

    try:
        deadline = time.monotonic() + execution_timeout
        stdout_stream = process.stdout
        stderr_stream = process.stderr
        if stdout_stream is None or stderr_stream is None:
            failure = "internal"
        else:
            streams[stdout_stream] = bytearray()
            streams[stderr_stream] = bytearray()
            limits = {stdout_stream: max_stdout_bytes, stderr_stream: max_stderr_bytes}
            selector = selectors.DefaultSelector()
            for stream in streams:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)

            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    failure = "timeout"
                    break
                try:
                    ready = selector.select(min(0.1, remaining))
                except InterruptedError:
                    continue
                for key, _ in ready:
                    stream = cast(IO[bytes], key.fileobj)
                    captured = streams[stream]
                    limit = limits[stream]
                    try:
                        chunk = os.read(stream.fileno(), min(65_536, limit + 1 - len(captured)))
                    except BlockingIOError:
                        continue
                    except InterruptedError:
                        continue
                    except OSError:
                        failure = "read_error"
                        break
                    if not chunk:
                        selector.unregister(stream)
                        continue
                    if len(chunk) > limit - len(captured):
                        failure = (
                            "stdout_overflow" if stream is stdout_stream else "stderr_overflow"
                        )
                        break
                    captured.extend(chunk)
                if failure is not None:
                    break

            if failure is None:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        failure = "timeout"
                        break
                    try:
                        process.wait(timeout=remaining)
                        break
                    except subprocess.TimeoutExpired:
                        failure = "timeout"
                        break
                    except InterruptedError:
                        continue
            if failure is None:
                state = _group_state(process.pid)
                if state is None:
                    failure = "group_check_failed"
                elif state:
                    failure = "surviving_process_group"
    except KeyboardInterrupt:
        failure = failure or "interrupted"
    except BaseException:
        failure = failure or "internal"

    cleanup_ok = False
    try:
        cleanup_ok = _finalize_child(process, selector, streams, cleanup_budget, events)
    except BaseException:
        _note(events, "finalizer_failed")
        cleanup_ok = False
    if not cleanup_ok:
        failure = failure or "cleanup_error"

    if failure is not None:
        raise ChildFailure(failure, cleanup_ok=cleanup_ok, cleanup_events=tuple(events)) from None

    if process.returncode is None or stdout_stream is None or stderr_stream is None:
        raise ChildFailure(
            "internal", cleanup_ok=cleanup_ok, cleanup_events=tuple(events)
        ) from None
    if not cleanup_ok:
        raise ChildFailure(
            "cleanup_error", cleanup_ok=False, cleanup_events=tuple(events)
        ) from None

    try:
        return ChildResult(
            returncode=process.returncode,
            stdout=bytes(streams[stdout_stream]),
            stderr=bytes(streams[stderr_stream]),
            cleanup_ok=True,
            cleanup_events=tuple(events),
        )
    except BaseException:
        raise ChildFailure("internal", cleanup_ok=True, cleanup_events=tuple(events)) from None
