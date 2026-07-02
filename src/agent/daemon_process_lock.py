"""Cross-process daemon singleton lock, PID file, and graceful stop.

Single-responsibility slice of :mod:`maintenance_daemon` (issue #58). Depends on
:mod:`daemon_state` for checkpoint updates during stop — not the reverse.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from ..graph.markdown_blocks import atomic_write_bytes
from .daemon_state import load_daemon_state, save_daemon_state

PID_FILENAME = ".matryca_plumber_daemon.pid"
DAEMON_LOCK_FILENAME = ".matryca_plumber_daemon.lock"
PLUMBER_PID_MARKER = "matryca-plumber-daemon"
DEFAULT_STOP_GRACE_SECONDS = 130.0
DEFAULT_STOP_SIGKILL_AFTER_SECONDS = 125.0

_fcntl: Any
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows and other non-Unix platforms
    _fcntl = None

_msvcrt: Any
try:
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - non-Windows platforms
    _msvcrt = None

_daemon_process_lock_fd: int | None = None


def pid_path(graph_root: Path) -> Path:
    return graph_root / PID_FILENAME


def daemon_lock_path(graph_root: Path) -> Path:
    return graph_root / DAEMON_LOCK_FILENAME


def bind_daemon_process_lock_fd(fd: int) -> None:
    """Store the OS file descriptor for the held cross-process daemon lock."""
    global _daemon_process_lock_fd
    _daemon_process_lock_fd = fd


def _try_acquire_daemon_process_lock_windows(graph_root: Path) -> int | None:
    """Acquire an exclusive daemon lock on platforms without ``fcntl`` (Windows)."""
    path = daemon_lock_path(graph_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    for _attempt in range(3):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            holder = _read_lock_holder_pid(path)
            if holder is not None and is_plumber_process(holder):
                return None
            if holder is None or not is_process_alive(holder):
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)
                continue
            return None
        except OSError:
            return None
        try:
            os.write(fd, f"{os.getpid()}\n".encode())
        except OSError:
            os.close(fd)
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
            return None
        if _msvcrt is not None:
            try:
                _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
            except OSError:
                os.close(fd)
                with contextlib.suppress(OSError):
                    path.unlink(missing_ok=True)
                return None
        return fd
    return None


def _try_acquire_daemon_process_lock(graph_root: Path) -> int | None:
    """Acquire an exclusive daemon lock; return ``None`` when another process holds it."""
    if _fcntl is None:
        return _try_acquire_daemon_process_lock_windows(graph_root)
    path = daemon_lock_path(graph_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def _release_daemon_process_lock(graph_root: Path) -> None:
    """Drop the cross-process daemon lock held by this process."""
    global _daemon_process_lock_fd
    if _daemon_process_lock_fd is not None and _daemon_process_lock_fd >= 0:
        with contextlib.suppress(OSError):
            if _fcntl is not None:
                _fcntl.flock(_daemon_process_lock_fd, _fcntl.LOCK_UN)
            elif _msvcrt is not None:
                _msvcrt.locking(_daemon_process_lock_fd, _msvcrt.LK_UNLCK, 1)
            os.close(_daemon_process_lock_fd)
        _daemon_process_lock_fd = None
    lock_path = daemon_lock_path(graph_root)
    with contextlib.suppress(OSError):
        lock_path.unlink(missing_ok=True)


def register_bootstrap_shutdown_handlers(graph_root: Path) -> None:
    """Ensure PID/lock cleanup when the worker is interrupted during bootstrap."""

    def _handler(signum: int, _frame: object) -> None:
        remove_pid_file(graph_root)
        _release_daemon_process_lock(graph_root)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def _read_lock_holder_pid(lock_path: Path) -> int | None:
    """Best-effort PID stored in a daemon lock sidecar."""
    if not lock_path.is_file():
        return None
    try:
        raw = lock_path.read_text(encoding="utf-8", errors="replace")  # sandbox-read-ok
        first_line = raw.splitlines()[0].strip()
        return int(first_line)
    except (OSError, ValueError, IndexError):
        return None


def _process_command_line(pid: int) -> str:
    """Return a best-effort command line for ``pid`` (platform-specific)."""
    if sys.platform == "win32":
        result = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        return result.stdout or ""
    if sys.platform == "darwin":
        result = subprocess.run(  # noqa: S603
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        return (result.stdout or "").strip()
    proc_path = Path(f"/proc/{pid}/cmdline")
    if proc_path.is_file():
        return proc_path.read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
    return ""


def is_plumber_process(pid: int) -> bool:
    """Return whether ``pid`` appears to be a Matryca Plumber daemon worker."""
    if pid <= 0 or not is_process_alive(pid):
        return False
    cmd = _process_command_line(pid).lower()
    if not cmd:
        return False
    if "maintenance_daemon" in cmd:
        return True
    return "src.cli" in cmd and "plumber" in cmd


def write_pid_file(graph_root: Path) -> None:
    path = pid_path(graph_root)
    payload = json.dumps({"pid": os.getpid(), "marker": PLUMBER_PID_MARKER}) + "\n"
    atomic_write_bytes(
        path,
        payload.encode("utf-8"),
        graph_root=graph_root,
        validate_block_refs=False,
    )


def read_pid_file(graph_root: Path) -> int | None:
    path = pid_path(graph_root)
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()  # sandbox-read-ok
    except OSError:
        return None
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
        if isinstance(payload, dict):
            pid = payload.get("pid")
            if isinstance(pid, int):
                return pid
            if isinstance(pid, str) and pid.strip().isdigit():
                return int(pid.strip())
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def remove_pid_file(graph_root: Path) -> None:
    path = pid_path(graph_root)
    if path.is_file():
        path.unlink(missing_ok=True)


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_daemon(
    graph_root: Path,
    *,
    grace_seconds: float = DEFAULT_STOP_GRACE_SECONDS,
    sigkill_after: float = DEFAULT_STOP_SIGKILL_AFTER_SECONDS,
) -> dict[str, Any]:
    """Gracefully stop a running daemon via SIGTERM, escalating to SIGKILL when needed."""
    pid = read_pid_file(graph_root)
    if pid is None:
        return {"ok": True, "code": "not_running", "message": "No PID file found"}
    if not is_process_alive(pid):
        remove_pid_file(graph_root)
        state = load_daemon_state(graph_root)
        state.status = "stopped"
        save_daemon_state(graph_root, state)
        return {"ok": True, "code": "stale_pid_removed", "pid": pid}
    if not is_plumber_process(pid):
        remove_pid_file(graph_root)
        return {
            "ok": False,
            "code": "foreign_pid",
            "pid": pid,
            "message": f"PID {pid} is not a Matryca Plumber daemon process",
        }

    os.kill(pid, signal.SIGTERM)
    sigkill_sent = False
    deadline = time.monotonic() + max(1.0, grace_seconds)
    sigkill_at = time.monotonic() + max(1.0, sigkill_after)
    while time.monotonic() < deadline:
        if not is_process_alive(pid):
            break
        if not sigkill_sent and time.monotonic() >= sigkill_at:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
            sigkill_sent = True
        time.sleep(0.1)

    if is_process_alive(pid):
        return {
            "ok": False,
            "code": "stop_failed",
            "pid": pid,
            "message": "Daemon process still alive after SIGTERM/SIGKILL",
        }

    remove_pid_file(graph_root)
    state = load_daemon_state(graph_root)
    state.status = "stopped"
    save_daemon_state(graph_root, state)
    code = "killed" if sigkill_sent else "signaled"
    signal_name = "SIGKILL" if sigkill_sent else "SIGTERM"
    return {"ok": True, "code": code, "pid": pid, "signal": signal_name}


__all__ = [
    "DAEMON_LOCK_FILENAME",
    "DEFAULT_STOP_GRACE_SECONDS",
    "DEFAULT_STOP_SIGKILL_AFTER_SECONDS",
    "PID_FILENAME",
    "PLUMBER_PID_MARKER",
    "_release_daemon_process_lock",
    "_try_acquire_daemon_process_lock",
    "bind_daemon_process_lock_fd",
    "daemon_lock_path",
    "is_plumber_process",
    "is_process_alive",
    "pid_path",
    "read_pid_file",
    "register_bootstrap_shutdown_handlers",
    "remove_pid_file",
    "stop_daemon",
    "write_pid_file",
]
