"""Bounded single-page Logseq parsing via a terminable spawn worker (#297 PR2B).

Every parse that must not hang indefinitely runs in a persistent child process
with a hard deadline. The parent never relies on thread interruption.

``GraphAstCache`` uses this worker for bounded bootstrap and incremental page
parsing. Shadow integration remains a separate transactional follow-up.

Privacy: diagnostic fields on :class:`BoundedParseResult` are content-free
(hash / byte / line counts only). The optional ``page`` AST is ``repr=False``
and must never be serialized or logged by callers — treat it as vault content.
"""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import multiprocessing as mp
import os
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from queue import Empty
from typing import Any, Literal

from loguru import logger

from ..utils.env_parse import env_float_clamped

ParseMode = Literal["logos", "stack"]
_VALID_MODES: frozenset[str] = frozenset({"logos", "stack"})

_TIMEOUT_ENV = "MATRYCA_PAGE_PARSE_TIMEOUT_S"
_DEFAULT_TIMEOUT_S = 15.0
_MIN_TIMEOUT_S = 2.0
_MAX_TIMEOUT_S = 120.0
_TERMINATE_GRACE_S = 5.0
_SHUTDOWN_JOIN_S = 5.0
# How often an idle worker wakes to check whether its parent is still alive.
_ORPHAN_POLL_S = 1.0
_SUBPROCESS_MODULE = "src.graph.bounded_page_parse_child"
_SUBPROCESS_HEADER_BYTES = 4

_CTX = mp.get_context("spawn")


def page_parse_timeout_s() -> float:
    """Hard deadline for one page parse (seconds), clamped."""
    return env_float_clamped(
        _TIMEOUT_ENV,
        _DEFAULT_TIMEOUT_S,
        minimum=_MIN_TIMEOUT_S,
        maximum=_MAX_TIMEOUT_S,
    )


def content_hash16(text: str) -> str:
    """Stable privacy-safe content fingerprint (sha256 hex prefix)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def page_line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


@dataclass(frozen=True, slots=True)
class BoundedParseResult:
    """Outcome of a bounded page parse.

    Diagnostic fields (``ok``, ``timed_out``, ``elapsed_s``, ``content_hash``,
    ``byte_count``, ``line_count``, ``mode``, ``error``) are content-free: no
    vault paths and no body text. ``page`` holds the AST when ``ok`` and is
    excluded from ``repr``; callers must not log or serialize ``page``.
    """

    ok: bool
    timed_out: bool
    elapsed_s: float
    content_hash: str
    byte_count: int
    line_count: int
    mode: str
    error: str | None = None
    page: Any | None = field(default=None, repr=False)


def _echo_fields(msg: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": msg.get("request_id"),
        "content_hash": msg.get("content_hash"),
    }


def _parse_request_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Parse one trusted local request and return a content-free response envelope.

    The AST is serialized separately as bytes.  This lets the daemon-parent
    fallback verify response correlation before decoding the AST payload.
    """
    op = str(msg.get("op", ""))
    echo = _echo_fields(msg)
    if op != "parse":
        return {**echo, "ok": False, "error": "unknown_op", "s": 0.0}
    mode = str(msg.get("mode", ""))
    text = str(msg.get("text", ""))
    title = str(msg.get("title", "Page"))
    tab_size = int(msg.get("tab_size", 2))
    started = time.perf_counter()
    if mode not in _VALID_MODES:
        return {
            **echo,
            "ok": False,
            "error": "invalid_mode",
            "s": round(time.perf_counter() - started, 6),
        }
    try:
        if mode == "stack":
            from logseq_matryca_parser.graph import StackMachineParser

            page = StackMachineParser(tab_size=tab_size).parse(
                text,
                page_title=title,
            )
        else:
            from logseq_matryca_parser import LogosParser

            page = LogosParser().parse(text)
        return {
            **echo,
            "ok": True,
            "blob": page.model_dump_json().encode("utf-8"),
            "s": round(time.perf_counter() - started, 6),
        }
    except Exception as exc:  # noqa: BLE001 - bounded type name only
        return {
            **echo,
            "ok": False,
            "error": type(exc).__name__,
            "s": round(time.perf_counter() - started, 6),
        }


def _worker_loop(
    in_q: mp.Queue[dict[str, Any] | None],
    out_q: mp.Queue[dict[str, Any]],
) -> None:
    """Child entry: parse requests until shutdown sentinel or the parent dies.

    ``daemon=True`` only reaps the child when the parent exits through the
    ``multiprocessing`` atexit hook. A parent that dies via ``os._exit`` or
    ``SIGKILL`` skips it and leaves this process reparented to init, holding a
    duplicate of the ``resource_tracker`` pipe open for the lifetime of the
    machine. So do not block forever on the queue: wake periodically and exit
    once the parent that spawned us is gone.
    """
    parent_pid = os.getppid()
    while True:
        try:
            msg = in_q.get(timeout=_ORPHAN_POLL_S)
        except Empty:
            if os.getppid() != parent_pid:
                break
            continue
        if msg is None:
            break
        if str(msg.get("op", "")) == "shutdown":
            break
        out_q.put(_parse_request_message(msg))


class BoundedPageParseWorker:
    """Persistent spawn worker; one outstanding parse at a time (lock-serialized).

    Ownership is tied to the creating process PID. After ``os.fork``, inherited
    handles must be abandoned without terminating the parent's worker.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._owner_pid = os.getpid()
        self._next_request_id = 0
        self._proc: Any | None = None
        self._in_q: Any | None = None
        self._out_q: Any | None = None

    @property
    def pid(self) -> int | None:
        if os.getpid() != self._owner_pid:
            return None
        proc = self._proc
        return proc.pid if proc is not None and proc.is_alive() else None

    @property
    def owner_pid(self) -> int:
        return self._owner_pid

    def _start_unlocked(self) -> None:
        self._in_q = _CTX.Queue(maxsize=1)
        self._out_q = _CTX.Queue(maxsize=1)
        self._proc = _CTX.Process(
            target=_worker_loop,
            args=(self._in_q, self._out_q),
            name="matryca-bounded-page-parse",
            daemon=True,
        )
        self._proc.start()

    def _abandon_inherited_unlocked(self) -> None:
        """Drop inherited refs after fork; do not terminate the parent's worker."""
        self._proc = None
        self._in_q = None
        self._out_q = None

    def abandon_inherited_handles(self) -> None:
        """Public: discard fork-inherited handles without killing the parent worker."""
        with self._lock:
            self._abandon_inherited_unlocked()
            self._owner_pid = os.getpid()

    def _ensure_worker_unlocked(self) -> None:
        if os.getpid() != self._owner_pid:
            self._abandon_inherited_unlocked()
            self._owner_pid = os.getpid()
            self._start_unlocked()
            return
        if self._proc is not None and self._proc.is_alive():
            return
        self._discard_queues_unlocked()
        self._start_unlocked()

    def _discard_queues_unlocked(self) -> None:
        for q in (self._in_q, self._out_q):
            if q is None:
                continue
            with contextlib.suppress(Exception):
                q.close()
            with contextlib.suppress(Exception):
                q.join_thread()
        self._in_q = None
        self._out_q = None

    def _kill_worker_unlocked(self) -> None:
        proc = self._proc
        if proc is None:
            self._discard_queues_unlocked()
            return
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=_TERMINATE_GRACE_S)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=_TERMINATE_GRACE_S)
        self._proc = None
        self._discard_queues_unlocked()

    def shutdown(self) -> None:
        """Stop the worker process (idempotent). Skip kill if we are a forked child."""
        with self._lock:
            if os.getpid() != self._owner_pid:
                self._abandon_inherited_unlocked()
                self._owner_pid = os.getpid()
                return
            proc = self._proc
            in_q = self._in_q
            if proc is not None and proc.is_alive() and in_q is not None:
                with contextlib.suppress(Exception):
                    in_q.put_nowait(None)
                proc.join(timeout=_SHUTDOWN_JOIN_S)
            if proc is not None and proc.is_alive():
                self._kill_worker_unlocked()
            else:
                self._proc = None
                self._discard_queues_unlocked()

    def _protocol_mismatch_unlocked(
        self,
        *,
        digest: str,
        byte_count: int,
        line_count: int,
        mode: ParseMode,
        elapsed_s: float,
    ) -> BoundedParseResult:
        logger.bind(content_hash=digest, mode=mode).warning(
            "bounded page parse protocol mismatch; terminating worker"
        )
        self._kill_worker_unlocked()
        return BoundedParseResult(
            ok=False,
            timed_out=False,
            elapsed_s=elapsed_s,
            content_hash=digest,
            byte_count=byte_count,
            line_count=line_count,
            mode=mode,
            error="protocol_mismatch",
            page=None,
        )

    def _daemon_subprocess_result_unlocked(
        self,
        *,
        request: dict[str, Any],
        request_id: int,
        digest: str,
        byte_count: int,
        line_count: int,
        mode: ParseMode,
        deadline: float,
    ) -> BoundedParseResult:
        """Run one parse in a terminable subprocess for a daemon parent.

        ``multiprocessing`` blocks ``spawn`` from a daemon pool worker.  The
        fallback intentionally does not parse in-process: it starts a fresh
        interpreter without a shell and exchanges one binary framed response.
        The frame header is validated before the AST blob is decoded.
        """
        started = time.perf_counter()
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", _SUBPROCESS_MODULE],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            request_bytes = json.dumps(
                request,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            output, _ = proc.communicate(input=request_bytes, timeout=deadline)
        except subprocess.TimeoutExpired:
            wall = round(time.perf_counter() - started, 6)
            if proc is None:  # Defensive guard for static analysis and startup failures.
                raise
            proc.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=_TERMINATE_GRACE_S)
            if proc.poll() is None:
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=_TERMINATE_GRACE_S)
            logger.bind(
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                timeout_s=deadline,
                request_id=request_id,
            ).warning("bounded page parse timed out; terminating subprocess child")
            return BoundedParseResult(
                ok=False,
                timed_out=True,
                elapsed_s=wall,
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                error="timeout",
                page=None,
            )
        except OSError:
            return BoundedParseResult(
                ok=False,
                timed_out=False,
                elapsed_s=round(time.perf_counter() - started, 6),
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                error="subprocess_error",
                page=None,
            )

        wall = round(time.perf_counter() - started, 6)
        if proc.returncode != 0 or len(output) < _SUBPROCESS_HEADER_BYTES:
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        header_size = struct.unpack("!I", output[:_SUBPROCESS_HEADER_BYTES])[0]
        header_end = _SUBPROCESS_HEADER_BYTES + header_size
        if header_end > len(output):
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        try:
            header = json.loads(output[_SUBPROCESS_HEADER_BYTES:header_end].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        if not isinstance(header, dict):
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        if header.get("request_id") != request_id or header.get("content_hash") != digest:
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        if not header.get("ok"):
            error = str(header.get("error") or "parse_error")
            if "/" in error or "\\" in error:
                error = "parse_error"
            return BoundedParseResult(
                ok=False,
                timed_out=False,
                elapsed_s=float(header.get("s", wall)),
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                error=error,
                page=None,
            )
        blob = output[header_end:]
        if header.get("blob_length") != len(blob):
            return self._protocol_mismatch_unlocked(
                digest=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                elapsed_s=wall,
            )
        try:
            from logseq_matryca_parser.logos_core import LogseqPage

            page = LogseqPage.model_validate_json(blob)
        except Exception:  # noqa: BLE001 - AST payload is untrusted until correlation
            return BoundedParseResult(
                ok=False,
                timed_out=False,
                elapsed_s=float(header.get("s", wall)),
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=mode,
                error="unpickle_error",
                page=None,
            )
        return BoundedParseResult(
            ok=True,
            timed_out=False,
            elapsed_s=float(header.get("s", wall)),
            content_hash=digest,
            byte_count=byte_count,
            line_count=line_count,
            mode=mode,
            error=None,
            page=page,
        )

    def parse_text(
        self,
        text: str,
        *,
        mode: ParseMode = "logos",
        page_title: str = "Page",
        tab_size: int = 2,
        timeout_s: float | None = None,
    ) -> BoundedParseResult:
        """Parse ``text`` in the worker; kill the worker on deadline overrun."""
        digest = content_hash16(text)
        byte_count = len(text.encode("utf-8"))
        line_count = page_line_count(text)

        if mode == "logos":
            parse_mode: ParseMode = "logos"
        elif mode == "stack":
            parse_mode = "stack"
        else:
            return BoundedParseResult(
                ok=False,
                timed_out=False,
                elapsed_s=0.0,
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=str(mode),
                error="invalid_mode",
                page=None,
            )

        deadline = page_parse_timeout_s() if timeout_s is None else float(timeout_s)
        deadline = min(_MAX_TIMEOUT_S, max(_MIN_TIMEOUT_S, deadline))

        with self._lock:
            self._next_request_id += 1
            request_id = self._next_request_id
            request = {
                "op": "parse",
                "request_id": request_id,
                "content_hash": digest,
                "mode": parse_mode,
                "text": text,
                "title": page_title,
                "tab_size": tab_size,
            }
            if mp.current_process().daemon:
                return self._daemon_subprocess_result_unlocked(
                    request=request,
                    request_id=request_id,
                    digest=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    deadline=deadline,
                )

            self._ensure_worker_unlocked()
            assert self._in_q is not None
            assert self._out_q is not None
            assert self._proc is not None
            out_q = self._out_q

            # Leftover output with no outstanding task = protocol corruption.
            try:
                unexpected = out_q.get_nowait()
            except Empty:
                unexpected = None
            if unexpected is not None:
                return self._protocol_mismatch_unlocked(
                    digest=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    elapsed_s=0.0,
                )

            wall0 = time.perf_counter()
            self._in_q.put(request)

            # Queue.get(timeout=...) only bounds wait-for-readiness; once the
            # pipe is readable it calls recv_bytes() with no timeout, which
            # can still block past the deadline while a large/partial
            # response is still being received. Bound the *entire* receive
            # by running it on a helper thread and enforcing the deadline
            # ourselves; a deadline overrun always kills the worker, which
            # closes the pipe and unblocks the helper thread.
            received: dict[str, Any] = {}
            done = threading.Event()

            def _receive() -> None:
                try:
                    received["raw"] = out_q.get()
                except Exception as exc:  # noqa: BLE001
                    received["exc"] = exc
                finally:
                    done.set()

            receiver = threading.Thread(
                target=_receive, name="matryca-bounded-page-parse-recv", daemon=True
            )
            receiver.start()

            if not done.wait(timeout=deadline):
                wall = round(time.perf_counter() - wall0, 6)
                logger.bind(
                    content_hash=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    timeout_s=deadline,
                    request_id=request_id,
                ).warning("bounded page parse timed out; terminating worker")
                self._kill_worker_unlocked()
                return BoundedParseResult(
                    ok=False,
                    timed_out=True,
                    elapsed_s=wall,
                    content_hash=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    error="timeout",
                    page=None,
                )

            if "exc" in received:
                wall = round(time.perf_counter() - wall0, 6)
                self._kill_worker_unlocked()
                return self._protocol_mismatch_unlocked(
                    digest=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    elapsed_s=wall,
                )

            raw = received["raw"]
            wall = round(time.perf_counter() - wall0, 6)
            if raw.get("request_id") != request_id or raw.get("content_hash") != digest:
                return self._protocol_mismatch_unlocked(
                    digest=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    elapsed_s=wall,
                )

            if not raw.get("ok"):
                err = str(raw.get("error") or "parse_error")
                if "/" in err or "\\" in err:
                    err = "parse_error"
                return BoundedParseResult(
                    ok=False,
                    timed_out=False,
                    elapsed_s=float(raw.get("s", wall)),
                    content_hash=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    error=err,
                    page=None,
                )

            blob = raw.get("blob")
            try:
                from logseq_matryca_parser.logos_core import LogseqPage

                page = (
                    LogseqPage.model_validate_json(blob)
                    if isinstance(blob, (bytes, bytearray))
                    else None
                )
            except Exception:  # noqa: BLE001
                return BoundedParseResult(
                    ok=False,
                    timed_out=False,
                    elapsed_s=float(raw.get("s", wall)),
                    content_hash=digest,
                    byte_count=byte_count,
                    line_count=line_count,
                    mode=parse_mode,
                    error="unpickle_error",
                    page=None,
                )
            return BoundedParseResult(
                ok=True,
                timed_out=False,
                elapsed_s=float(raw.get("s", wall)),
                content_hash=digest,
                byte_count=byte_count,
                line_count=line_count,
                mode=parse_mode,
                error=None,
                page=page,
            )


_worker_lock = threading.Lock()
_worker: BoundedPageParseWorker | None = None
_worker_owner_pid: int | None = None


def get_bounded_page_parse_worker() -> BoundedPageParseWorker:
    """Process-wide singleton worker (recreated after fork in the child)."""
    global _worker, _worker_owner_pid
    with _worker_lock:
        pid = os.getpid()
        if _worker is not None and _worker_owner_pid == pid:
            return _worker
        if _worker is not None:
            # Forked child (or stale owner): drop inherited handles; do not kill.
            _worker.abandon_inherited_handles()
            _worker = None
            _worker_owner_pid = None
        _worker = BoundedPageParseWorker()
        _worker_owner_pid = pid
        return _worker


def reset_bounded_page_parse_worker_for_tests() -> None:
    """Shutdown and drop the singleton (tests only; owner PID only)."""
    global _worker, _worker_owner_pid
    with _worker_lock:
        if _worker is None:
            _worker_owner_pid = None
            return
        if _worker_owner_pid == os.getpid():
            _worker.shutdown()
        else:
            _worker.abandon_inherited_handles()
        _worker = None
        _worker_owner_pid = None


def parse_page_text_bounded(
    text: str,
    *,
    mode: ParseMode = "logos",
    page_title: str = "Page",
    tab_size: int = 2,
    timeout_s: float | None = None,
) -> BoundedParseResult:
    """Public API: always process-isolated; never an unbounded in-process LogosParser call."""
    return get_bounded_page_parse_worker().parse_text(
        text,
        mode=mode,
        page_title=page_title,
        tab_size=tab_size,
        timeout_s=timeout_s,
    )


def _atexit_shutdown() -> None:
    reset_bounded_page_parse_worker_for_tests()


def _after_fork_in_child() -> None:
    """Drop singleton after fork so the child never shares parent's queues/worker."""
    global _worker, _worker_owner_pid
    # register_at_fork after_in_child: avoid waiting on locks held by parent threads.
    inherited = _worker
    _worker = None
    _worker_owner_pid = None
    if inherited is not None:
        inherited._abandon_inherited_unlocked()  # noqa: SLF001 - fork path only


atexit.register(_atexit_shutdown)
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork_in_child)

__all__ = [
    "BoundedParseResult",
    "BoundedPageParseWorker",
    "ParseMode",
    "content_hash16",
    "get_bounded_page_parse_worker",
    "page_parse_timeout_s",
    "parse_page_text_bounded",
    "reset_bounded_page_parse_worker_for_tests",
]
