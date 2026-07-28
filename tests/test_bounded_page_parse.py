"""PR2B — bounded page parse worker contracts."""

from __future__ import annotations

import contextlib
import os
import random
import signal
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

import pytest
from src.graph.bounded_page_parse import (
    BoundedPageParseWorker,
    ParseMode,
    content_hash16,
    get_bounded_page_parse_worker,
    page_parse_timeout_s,
    parse_page_text_bounded,
    reset_bounded_page_parse_worker_for_tests,
)

from tests.a_cli_01_generator import (
    PATHOLOGICAL_PAGE_LINE_COUNT,
    generate_control_page,
    generate_pathological_page,
)


@pytest.fixture(autouse=True)
def _reset_worker() -> Iterator[None]:
    reset_bounded_page_parse_worker_for_tests()
    yield
    reset_bounded_page_parse_worker_for_tests()


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _page_raw(page: Any) -> str:
    raw = getattr(page, "raw_content", None)
    return raw if isinstance(raw, str) else ""


def _daemon_pool_parse_probe(text: str) -> dict[str, object]:
    """Pool workers are daemon processes and cannot create mp children."""
    import multiprocessing as mp

    result = parse_page_text_bounded(text, mode="stack", timeout_s=15.0)
    return {
        "daemon": bool(mp.current_process().daemon),
        "ok": result.ok,
        "timed_out": result.timed_out,
        "content_hash": result.content_hash,
        "error": result.error,
        "page_present": result.page is not None,
    }


def test_page_parse_timeout_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_PAGE_PARSE_TIMEOUT_S", "0.5")
    assert page_parse_timeout_s() == 2.0
    monkeypatch.setenv("MATRYCA_PAGE_PARSE_TIMEOUT_S", "999")
    assert page_parse_timeout_s() == 120.0
    monkeypatch.delenv("MATRYCA_PAGE_PARSE_TIMEOUT_S", raising=False)
    assert page_parse_timeout_s() == 15.0


def test_control_page_parses_ok_logos_and_stack() -> None:
    text = generate_control_page(line_count=80)
    modes: tuple[ParseMode, ...] = ("logos", "stack")
    for mode in modes:
        result = parse_page_text_bounded(text, mode=mode, timeout_s=30.0)
        assert result.ok is True
        assert result.timed_out is False
        assert result.page is not None
        assert result.content_hash == content_hash16(text)
        assert result.error is None


def test_daemon_pool_worker_uses_terminable_subprocess_fallback() -> None:
    """A daemon Pool worker must retain hard process isolation without mp.spawn."""
    import multiprocessing as mp

    text = "- parser fallback from daemon pool\n"
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=1) as pool:
        payload = pool.apply(_daemon_pool_parse_probe, (text,))

    assert payload == {
        "daemon": True,
        "ok": True,
        "timed_out": False,
        "content_hash": content_hash16(text),
        "error": None,
        "page_present": True,
    }


def test_invalid_mode_rejected_without_silent_logos() -> None:
    text = "- should not parse as logos\n"
    result = parse_page_text_bounded(
        text,
        mode=cast(ParseMode, "not-a-parser"),
        timeout_s=15.0,
    )
    assert result.ok is False
    assert result.error == "invalid_mode"
    assert result.mode == "not-a-parser"
    assert result.page is None


def test_pathological_page_times_out_and_kills_worker() -> None:
    text = generate_pathological_page()
    assert text.count("\n") == PATHOLOGICAL_PAGE_LINE_COUNT
    worker = BoundedPageParseWorker()
    try:
        result = worker.parse_text(text, mode="logos", timeout_s=3.0)
        assert result.ok is False
        assert result.timed_out is True
        assert result.error == "timeout"
        assert result.page is None
        assert "/" not in (result.error or "")
        # Worker must not remain alive after timeout kill.
        assert worker.pid is None
    finally:
        worker.shutdown()
        assert worker.pid is None


def test_slow_receive_past_readiness_is_bounded_by_deadline() -> None:
    """Queue.get(timeout=...) only bounds wait-for-readiness; once the pipe is
    readable it falls through to an unbounded recv_bytes(). Stub ``_out_q.get``
    to simulate a response that becomes "ready" instantly but whose full
    receive stalls well past the deadline, and assert parse_text still enforces
    the deadline end-to-end instead of blocking for the stub's full duration.
    """
    worker = BoundedPageParseWorker()
    try:
        with worker._lock:
            worker._ensure_worker_unlocked()
            real_out_q: Any = worker._out_q
        assert real_out_q is not None

        class _StalledQueue:
            def get_nowait(self) -> Any:
                return real_out_q.get_nowait()

            def get(self, timeout: float | None = None) -> Any:
                # Simulate readiness-then-stall: recv_bytes() blocking far
                # longer than the caller's configured deadline.
                time.sleep(5.0)
                return real_out_q.get()

        worker._out_q = cast(Any, _StalledQueue())

        start = time.perf_counter()
        result = worker.parse_text("- stalled receive\n", mode="logos", timeout_s=1.0)
        elapsed = time.perf_counter() - start

        assert result.ok is False
        assert result.timed_out is True
        assert result.error == "timeout"
        # Must not wait for the stub's full 5s stall — bounded near the 1s deadline.
        assert elapsed < 3.0
        assert worker.pid is None
    finally:
        worker.shutdown()
        assert worker.pid is None


@pytest.mark.parametrize("deadline_s", [0.4, 0.75, 1.0, 1.5])
def test_slow_receive_bounded_across_randomized_stall_lengths(deadline_s: float) -> None:
    """Same stalled-receive contract as above, but randomize the stall length
    per deadline (always well past it) across several deadlines, so the
    bound is verified independent of exactly how long the stall runs.
    """
    rng = random.Random(f"bounded-parse-recv-{deadline_s}")
    stall_s = deadline_s + rng.uniform(2.0, 4.0)

    worker = BoundedPageParseWorker()
    try:
        with worker._lock:
            worker._ensure_worker_unlocked()
            real_out_q: Any = worker._out_q
        assert real_out_q is not None

        class _StalledQueue:
            def get_nowait(self) -> Any:
                return real_out_q.get_nowait()

            def get(self, timeout: float | None = None) -> Any:
                time.sleep(stall_s)
                return real_out_q.get()

        worker._out_q = cast(Any, _StalledQueue())

        start = time.perf_counter()
        result = worker.parse_text("- randomized stall\n", mode="logos", timeout_s=deadline_s)
        elapsed = time.perf_counter() - start

        assert result.ok is False
        assert result.timed_out is True
        assert result.error == "timeout"
        # Bound must track the configured deadline, not the (randomized, always
        # longer) stall duration — generous slack for scheduler/kill overhead.
        assert elapsed < deadline_s + 2.0
        assert worker.pid is None
    finally:
        worker.shutdown()
        assert worker.pid is None


def test_healthy_parse_survives_random_page_shapes() -> None:
    """Fuzz the real (non-stubbed) success path with randomized page content —
    varied line counts, block depths, and both parse modes — to catch shape-
    dependent regressions the fixed-fixture tests wouldn't surface.
    """
    rng = random.Random("bounded-parse-random-page-shapes")
    worker = BoundedPageParseWorker()
    try:
        for _ in range(8):
            line_count = rng.randint(1, 200)
            mode: ParseMode = rng.choice(["logos", "stack"])
            lines = []
            for i in range(line_count):
                depth = rng.randint(0, 4)
                lines.append("  " * depth + f"- item {i} {rng.choice(['a', 'bb', 'ccc'])}")
            text = "\n".join(lines) + "\n"

            result = worker.parse_text(text, mode=mode, timeout_s=15.0)

            assert result.ok is True, f"mode={mode} line_count={line_count} error={result.error}"
            assert result.timed_out is False
            assert result.content_hash == content_hash16(text)
            assert result.page is not None
            assert worker.pid is not None
    finally:
        worker.shutdown()
        assert worker.pid is None


def test_worker_survives_success_and_shuts_clean() -> None:
    worker = BoundedPageParseWorker()
    try:
        first = worker.parse_text("- ok\n", mode="logos", timeout_s=15.0)
        assert first.ok is True
        pid = worker.pid
        assert pid is not None
        second = worker.parse_text("- still ok\n", mode="stack", timeout_s=15.0)
        assert second.ok is True
        assert worker.pid == pid
    finally:
        alive_pid = worker.pid
        worker.shutdown()
        assert worker.pid is None
        if alive_pid is not None:
            # Give OS a beat; process must be gone.
            time.sleep(0.05)
            assert not _pid_alive(alive_pid)


def test_parse_result_repr_excludes_page_and_sensitive_text() -> None:
    """repr must stay content-free even when page AST embeds path-like / secret-like text."""
    secret = "AKIAIOSFODNN7EXAMPLE"
    pathish = "/Users/marco/Documents/secret-vault/pages/Private.md"
    title = f"Title with {pathish} and {secret}"
    text = f"- marker {secret}\n- also {pathish}\n- body leak check\n"
    result = parse_page_text_bounded(
        text,
        mode="logos",
        page_title=title,
        timeout_s=15.0,
    )
    assert result.ok is True
    assert result.page is not None
    blob = repr(result)
    assert "page=" not in blob
    assert secret not in blob
    assert pathish not in blob
    assert "/Users/" not in blob
    assert "Documents/" not in blob
    assert "Private.md" not in blob
    assert "body leak check" not in blob
    assert "AKIA" not in blob


def test_timeout_then_healthy_parse_gets_new_pid() -> None:
    worker = BoundedPageParseWorker()
    try:
        timed = worker.parse_text(
            generate_pathological_page(),
            mode="logos",
            timeout_s=3.0,
        )
        assert timed.timed_out is True
        assert worker.pid is None

        healthy_text = "- recovered after timeout\n"
        healthy = worker.parse_text(healthy_text, mode="logos", timeout_s=15.0)
        assert healthy.ok is True
        assert healthy.timed_out is False
        assert healthy.content_hash == content_hash16(healthy_text)
        assert healthy.page is not None
        assert "recovered after timeout" in _page_raw(healthy.page)
        new_pid = worker.pid
        assert new_pid is not None
    finally:
        worker.shutdown()


def test_concurrent_callers_get_matched_results() -> None:
    texts = [f"- concurrent marker {i} unique-{i * 17}\n" for i in range(8)]

    def _one(text: str) -> tuple[str, str, str]:
        result = parse_page_text_bounded(text, mode="logos", timeout_s=30.0)
        assert result.ok is True
        assert result.page is not None
        marker = text.strip().removeprefix("- ").strip()
        assert marker in _page_raw(result.page)
        # content_hash is only accepted after worker echo correlation.
        assert result.content_hash == content_hash16(text)
        return text, result.content_hash, marker

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_one, t) for t in texts]
        got = {
            text: (digest, marker)
            for text, digest, marker in (f.result() for f in as_completed(futures))
        }
    for text in texts:
        digest, marker = got[text]
        assert digest == content_hash16(text)
        assert marker in text


def test_worker_crash_recovers_bounded() -> None:
    worker = BoundedPageParseWorker()
    try:
        first = worker.parse_text("- before crash\n", mode="logos", timeout_s=15.0)
        assert first.ok is True
        crash_pid = worker.pid
        assert crash_pid is not None
        os.kill(crash_pid, signal.SIGKILL)
        # Wait until multiprocessing reaps the child (kill(pid,0) stays true for zombies).
        deadline = time.monotonic() + 5.0
        while worker.pid is not None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert worker.pid is None

        recovered_text = "- after crash recovery\n"
        recovered = worker.parse_text(recovered_text, mode="logos", timeout_s=15.0)
        assert recovered.ok is True
        assert recovered.content_hash == content_hash16(recovered_text)
        assert "after crash recovery" in _page_raw(recovered.page)
        assert worker.pid is not None
        assert worker.pid != crash_pid
    finally:
        worker.shutdown()


def test_no_stale_result_after_timeout() -> None:
    worker = BoundedPageParseWorker()
    try:
        timed = worker.parse_text(
            generate_pathological_page(),
            mode="logos",
            timeout_s=3.0,
        )
        assert timed.timed_out is True
        next_text = "- fresh after timeout no stale MARKER-9911\n"
        nxt = worker.parse_text(next_text, mode="logos", timeout_s=15.0)
        assert nxt.ok is True
        assert nxt.content_hash == content_hash16(next_text)
        assert nxt.content_hash != timed.content_hash
        assert nxt.page is not None
        assert "MARKER-9911" in _page_raw(nxt.page)
        assert "MARKER-9911" not in (timed.error or "")
    finally:
        worker.shutdown()


def test_unexpected_output_is_protocol_mismatch() -> None:
    worker = BoundedPageParseWorker()
    try:
        assert worker.parse_text("- seed worker\n", timeout_s=15.0).ok is True
        assert worker._out_q is not None  # noqa: SLF001 - inject stale reply
        worker._out_q.put(  # noqa: SLF001
            {
                "ok": True,
                "request_id": 999,
                "content_hash": "deadbeefdeadbeef",
                "blob": b"not-a-pickle",
                "s": 0.0,
            }
        )
        result = worker.parse_text("- next legitimate request\n", timeout_s=15.0)
        assert result.ok is False
        assert result.error == "protocol_mismatch"
        assert result.page is None
        # Worker was killed; a later parse must recover on a fresh child.
        recovered = worker.parse_text("- after mismatch recovery\n", timeout_s=15.0)
        assert recovered.ok is True
        assert "after mismatch recovery" in _page_raw(recovered.page)
    finally:
        worker.shutdown()


def test_request_id_hash_mismatch_rejects_ast() -> None:
    from unittest.mock import patch

    worker = BoundedPageParseWorker()
    try:
        assert worker.parse_text("- warm\n", timeout_s=15.0).ok is True
        assert worker._out_q is not None  # noqa: SLF001
        real_get = worker._out_q.get

        def _corrupt_echo(*args: object, **kwargs: object) -> dict[str, object]:
            raw = real_get(*args, **kwargs)
            assert isinstance(raw, dict)
            # Keep blob so a naive parent would accept the wrong AST.
            return {**raw, "request_id": -1, "content_hash": "0" * 16}

        with patch.object(worker._out_q, "get", side_effect=_corrupt_echo):
            result = worker.parse_text("- should reject mismatched echo\n", timeout_s=15.0)
        assert result.ok is False
        assert result.error == "protocol_mismatch"
        assert result.page is None
    finally:
        worker.shutdown()


def test_shutdown_idempotent() -> None:
    worker = BoundedPageParseWorker()
    assert worker.parse_text("- shutdown once\n", timeout_s=15.0).ok is True
    worker.shutdown()
    assert worker.pid is None
    worker.shutdown()
    worker.shutdown()
    assert worker.pid is None


def _fork_ownership_probe(conn: object) -> None:
    """Spawn-child entry: fork once in a near-single-threaded process."""
    import multiprocessing.connection as mp_conn

    assert isinstance(conn, mp_conn.Connection)
    reset_bounded_page_parse_worker_for_tests()
    # Direct (non-singleton) ref must stay fork-safe for ``.pid`` after fork.
    direct_worker = BoundedPageParseWorker()
    assert direct_worker.parse_text("- parent before fork\n", timeout_s=15.0).ok
    parent_pid = direct_worker.pid
    assert parent_pid is not None

    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        try:
            # Inherited direct ref: must not raise on ``.pid``.
            try:
                inherited_pid = direct_worker.pid
                pid_safe = inherited_pid is None
            except Exception:  # noqa: BLE001
                pid_safe = False

            child_worker = get_bounded_page_parse_worker()
            parent_still_alive = _pid_alive(parent_pid)
            child_result = child_worker.parse_text("- child after fork\n", timeout_s=15.0)
            child_ok = bool(
                child_result.ok
                and child_result.content_hash == content_hash16("- child after fork\n")
                and "child after fork" in _page_raw(child_result.page)
            )
            child_wp = child_worker.pid
            distinct = child_wp is not None and child_wp != parent_pid
            os.write(
                write_fd,
                (
                    f"{int(parent_still_alive)} {int(child_ok)} {int(distinct)} {int(pid_safe)}\n"
                ).encode(),
            )
            os.close(write_fd)
            os._exit(0 if parent_still_alive and child_ok and distinct and pid_safe else 1)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                os.write(write_fd, b"0 0 0 0\n")
                os.close(write_fd)
            os._exit(2)

    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as pipe:
        raw = pipe.read()
    _waited, status = os.waitpid(child_pid, 0)
    ok_exit = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    parts = raw.decode().strip().split() if raw else []
    parent_after = direct_worker.parse_text("- parent after child exit\n", timeout_s=15.0)
    payload = {
        "parent_alive": bool(
            _pid_alive(parent_pid) and parent_after.ok and direct_worker.pid == parent_pid
        ),
        "child_ok": bool(ok_exit and len(parts) == 4 and parts[:3] == ["1", "1", "1"]),
        "distinct": bool(len(parts) == 4 and parts[2] == "1"),
        "pid_safe": bool(len(parts) == 4 and parts[3] == "1"),
    }
    conn.send(payload)
    conn.close()
    direct_worker.shutdown()
    reset_bounded_page_parse_worker_for_tests()
    raise SystemExit(0 if all(payload.values()) else 1)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Unix fork ownership only")
def test_fork_child_abandons_parent_worker_without_killing() -> None:
    """Probe runs under spawn so pytest threads do not poison os.fork()."""
    import multiprocessing as mp

    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_fork_ownership_probe, args=(child_conn,))
    proc.start()
    child_conn.close()
    try:
        payload = parent_conn.recv()
    except EOFError:
        payload = None
    proc.join(timeout=60.0)
    assert proc.exitcode == 0, payload
    assert payload == {
        "parent_alive": True,
        "child_ok": True,
        "distinct": True,
        "pid_safe": True,
    }


def test_spawn_start_method_is_used() -> None:
    import multiprocessing as mp

    worker = BoundedPageParseWorker()
    try:
        assert worker.parse_text("- spawn check\n", timeout_s=15.0).ok is True
        assert mp.get_context("spawn").get_start_method() == "spawn"
        assert worker.pid is not None
    finally:
        worker.shutdown()


def test_singleton_owner_pid_tracks_process() -> None:
    w = get_bounded_page_parse_worker()
    assert w.owner_pid == os.getpid()
    assert parse_page_text_bounded("- singleton\n", timeout_s=15.0).ok is True


def test_worker_exits_when_its_parent_is_killed() -> None:
    """A worker whose parent dies without cleanup must reap itself.

    ``daemon=True`` only covers a parent that exits through the multiprocessing
    atexit hook. A parent killed with SIGKILL (or exiting via ``os._exit``)
    skips it, and the orphan keeps a duplicate of the ``resource_tracker`` pipe
    open, which in turn blocks interpreter shutdown in any process that shares
    that tracker.
    """
    source = textwrap.dedent(
        """
        import sys, time
        from src.graph.bounded_page_parse import BoundedPageParseWorker

        worker = BoundedPageParseWorker()
        assert worker.parse_text("- orphan probe\\n", timeout_s=15.0).ok
        print(worker.pid, flush=True)
        time.sleep(120)
        """
    )
    parent = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", source],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert parent.stdout is not None
        worker_pid = int(parent.stdout.readline().strip())
        assert _pid_alive(worker_pid)
        parent.kill()
        parent.wait(timeout=10)

        deadline = time.monotonic() + 20.0
        while _pid_alive(worker_pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not _pid_alive(worker_pid), (
            f"worker {worker_pid} outlived its killed parent"
        )
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=10)
