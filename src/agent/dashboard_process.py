"""Cancellable POSIX dashboard supervisor and the single qualified-finalizer seam."""

from __future__ import annotations

import importlib.util
import json
import os
import selectors
import subprocess
import sys
import threading
import time
from pathlib import Path

from matryca_plumber.graph_gateway.consumer import (
    _CleanupSnapshot,
    _group_state,
)
from matryca_plumber.graph_gateway.consumer import (
    _finalize_child as _finalize_child,
)

from .dashboard_protocol import (
    DashboardCode,
    DashboardFrame,
    DashboardIntent,
    DashboardLimits,
    DashboardOutcome,
    DashboardRequest,
    PhaseReader,
    decode_frame,
)


class DashboardJobControl:
    """Data-only cancellation bridge with one immutable terminal cleanup deadline."""

    def __init__(self, limits: DashboardLimits) -> None:
        self.started = time.monotonic()
        self.execution_deadline = self.started + limits.execution_s
        self.cancelled = threading.Event()
        self._lock = threading.Lock()
        self._cleanup_s = limits.cleanup_s
        self._cleanup_deadline: float | None = None
        self._reason: DashboardCode | None = None
        # Only the supervisor touches this handle. A poisoned job retains it even
        # after the owner returns; the async side never signals or reaps through it.
        self._process: subprocess.Popen[bytes] | None = None
        self._cleanup_events: tuple[str, ...] = ()

    @property
    def cleanup_deadline(self) -> float | None:
        with self._lock:
            return self._cleanup_deadline

    @property
    def reason(self) -> DashboardCode | None:
        with self._lock:
            return self._reason

    def begin_cleanup(self, reason: DashboardCode | None) -> float:
        with self._lock:
            if self._cleanup_deadline is None:
                self._cleanup_deadline = time.monotonic() + self._cleanup_s
                self._reason = reason
            return self._cleanup_deadline

    def finish_execution(self, reason: DashboardCode | None) -> tuple[DashboardCode | None, float]:
        """Atomically admit the validated result without losing an earlier terminal trigger."""
        with self._lock:
            if self._cleanup_deadline is None:
                now = time.monotonic()
                self._reason = "dashboard_timeout" if now >= self.execution_deadline else reason
                self._cleanup_deadline = now + self._cleanup_s
            return self._reason, self._cleanup_deadline

    def request_cancel(self) -> None:
        self.begin_cleanup("dashboard_worker_failed")
        self.cancelled.set()

    def stopped(self) -> bool:
        if time.monotonic() >= self.execution_deadline:
            self.begin_cleanup("dashboard_timeout")
            return True
        return self.cancelled.is_set()


_BOOTSTRAP = """
import importlib.util, json, os, pathlib, sys
roots = json.loads(sys.argv[1])
root = pathlib.Path(roots[0])
sys.path[:0] = roots
os.environ['LOGURU_AUTOINIT'] = 'False'
os.environ['MATRYCA_READ_ONLY'] = 'true'
os.environ['MATRYCA_DEBUG'] = 'false'
for name, relative in [('src', 'src/__init__.py'),
                       ('src.agent.dashboard_worker', 'src/agent/dashboard_worker.py')]:
    spec = importlib.util.find_spec(name)
    if (spec is None or spec.origin is None
            or pathlib.Path(spec.origin).resolve() != root / relative):
        raise SystemExit(2)
    if name == 'src':
        import src
        if pathlib.Path(src.__file__).resolve() != root / relative:
            raise SystemExit(2)
from src.agent import dashboard_worker
if pathlib.Path(dashboard_worker.__file__).resolve() != root / 'src/agent/dashboard_worker.py':
    raise SystemExit(2)
raise SystemExit(dashboard_worker.main())
"""


def _build_launch() -> tuple[list[str], dict[str, str], Path]:
    """Admit only this source/install root and the current dependency roots."""
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.find_spec("src")
    if (
        spec is None
        or spec.origin is None
        or Path(spec.origin).resolve() != root / "src/__init__.py"
    ):
        raise ValueError("dashboard source origin rejected")
    roots = [str(root)]
    for entry in sys.path:
        path = Path(entry)
        if path.is_absolute() and path.name == "site-packages" and path.is_dir():
            resolved = str(path.resolve(strict=True))
            if resolved not in roots:
                roots.append(resolved)
    env = dict(os.environ)
    env.pop("LOGSEQ_GRAPH_PATH", None)
    env.update(LOGURU_AUTOINIT="False", MATRYCA_READ_ONLY="true", MATRYCA_DEBUG="false")
    # -I ignores PYTHONPATH; -S prevents executable .pth and site customization.
    argv = [sys.executable, "-I", "-S", "-B", "-c", _BOOTSTRAP, json.dumps(roots)]
    return argv, env, root


def _request_bytes(intent: DashboardIntent, limits: DashboardLimits) -> bytes:
    root = Path(intent.raw_graph_path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("dashboard root rejected")
    request = DashboardRequest(
        request_id=intent.request_id,
        graph_root=str(root),
        wiki_config=intent.wiki_config,
        include_identity=intent.include_identity,
    )
    encoded = request.model_dump_json().encode("utf-8")
    if len(encoded) > limits.request_bytes:
        raise ValueError("dashboard request bound exceeded")
    return encoded


def _close_stdin(process: subprocess.Popen[bytes], events: list[str]) -> bool:
    try:
        if process.stdin is None:
            events.append("stdin_missing")
            return False
        if not process.stdin.closed:
            process.stdin.close()
        if process.stdin.closed:
            return True
    except BaseException:
        events.append("stdin_close_failed")
        return False
    events.append("stdin_close_unverified")
    return False


def _capture(
    process: subprocess.Popen[bytes],
    selector: selectors.BaseSelector,
    data: bytes,
    *,
    limits: DashboardLimits,
    control: DashboardJobControl,
    phases: PhaseReader,
) -> tuple[DashboardCode | None, bytes]:
    """All pipe writes/reads and post-EOF waits share cancellation and deadline."""
    stdout = bytearray()
    stderr_count = 0
    sent = 0
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(process, name)
        if stream is None:
            return "dashboard_worker_failed", b""
        os.set_blocking(stream.fileno(), False)
        selector.register(
            stream, selectors.EVENT_WRITE if name == "stdin" else selectors.EVENT_READ, name
        )
    while True:
        if control.stopped():
            return control.reason or "dashboard_worker_failed", bytes(stdout)
        if not selector.get_map() and process.poll() is not None:
            return None, bytes(stdout)
        wait = min(limits.poll_s, max(0.0, control.execution_deadline - time.monotonic()))
        if not selector.get_map():
            control.cancelled.wait(wait)
            continue
        for key, _ in selector.select(wait):
            if control.stopped():
                return control.reason or "dashboard_worker_failed", bytes(stdout)
            stream = key.fileobj
            if key.data == "stdin":
                try:
                    sent += os.write(key.fd, data[sent : sent + 8192])
                except BlockingIOError:
                    continue
                except BrokenPipeError:
                    return "dashboard_worker_failed", bytes(stdout)
                if sent == len(data):
                    selector.unregister(stream)
                    if process.stdin is not None:
                        process.stdin.close()
                continue
            capacity = (
                limits.stdout_bytes - len(stdout)
                if key.data == "stdout"
                else limits.stderr_bytes - stderr_count
            )
            try:
                chunk = os.read(key.fd, min(65_536, capacity + 1))
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(stream)
                continue
            if len(chunk) > capacity:
                return "dashboard_output_overflow", bytes(stdout)
            if key.data == "stdout":
                stdout.extend(chunk)
            else:
                stderr_count += len(chunk)
                phases.feed(chunk)


def run_dashboard_process(
    intent: DashboardIntent, *, limits: DashboardLimits, control: DashboardJobControl
) -> DashboardOutcome:
    """Own one process group and retain cleanup failure independently of primary error."""
    phases = PhaseReader()
    process: subprocess.Popen[bytes] | None = None
    selector: selectors.BaseSelector | None = None
    frame: DashboardFrame | None = None
    code: DashboardCode | None = None
    events: list[str] = []
    spawn_entered = False
    cleanup_ok = False
    try:
        if sys.platform not in {"linux", "darwin"}:
            code = "dashboard_platform_unsupported"
        elif control.stopped():
            code = control.reason or "dashboard_worker_failed"
        else:
            data = _request_bytes(intent, limits)
            argv, env, cwd = _build_launch()
            # No process creation after an admission-time cancellation/deadline.
            if control.stopped():
                code = control.reason or "dashboard_worker_failed"
            else:
                spawn_entered = True
                # The private builder fixes executable/flags; graph data uses stdin only.
                process = subprocess.Popen(  # noqa: S603
                    argv,
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,
                    close_fds=True,
                    start_new_session=True,
                    bufsize=0,
                )
                control._process = process
                # A late Popen return retains its handle, but cannot renew the deadline.
                if control.stopped():
                    code = control.reason or "dashboard_worker_failed"
                else:
                    selector = selectors.DefaultSelector()
                    code, stdout = _capture(
                        process, selector, data, limits=limits, control=control, phases=phases
                    )
                    if code is None:
                        phases.finish()
                        if process.returncode != 0:
                            code = "dashboard_worker_failed"
                        else:
                            frame = decode_frame(
                                stdout, intent.request_id, complete=phases.complete
                            )
                            code = frame.code
    except (ValueError, UnicodeError):
        code = "dashboard_protocol_error"
    except BaseException:
        code = "dashboard_worker_failed"
    finally:
        code, deadline = control.finish_execution(code)
        if process is None:
            cleanup_ok = not spawn_entered and time.monotonic() < deadline
        else:
            stdin_ok = _close_stdin(process, events)
            try:
                cleanup_ok = _finalize_child(
                    process,
                    selector,
                    {},
                    max(0.0, deadline - time.monotonic()),
                    events,
                    snapshot=_CleanupSnapshot(),
                )
            except BaseException:
                events.append("finalizer_interrupted")
                cleanup_ok = False
            try:
                cleanup_ok = (
                    cleanup_ok
                    and stdin_ok
                    and not events
                    and process.poll() is not None
                    and _group_state(process.pid) is False
                    and time.monotonic() < deadline
                )
            except BaseException:
                cleanup_ok = False
    if not cleanup_ok:
        code = "dashboard_cleanup_unverified"
    control._cleanup_events = tuple(events)
    return DashboardOutcome(
        code=code,
        last_phase=phases.last_phase,
        elapsed_ms=max(0, int((time.monotonic() - control.started) * 1000)),
        cleanup_verified=cleanup_ok,
        markdown=frame.markdown if code is None and frame is not None else None,
    )
