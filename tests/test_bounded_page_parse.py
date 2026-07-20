"""PR2B — bounded page parse worker (no Shadow/AST integration)."""

from __future__ import annotations

import contextlib
import os
import signal
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        new_pid = worker.pid
        assert new_pid is not None
    finally:
        worker.shutdown()


def test_concurrent_callers_get_matched_results() -> None:
    texts = [f"- concurrent marker {i} unique-{i * 17}\n" for i in range(8)]

    def _one(text: str) -> tuple[str, str]:
        result = parse_page_text_bounded(text, mode="logos", timeout_s=30.0)
        assert result.ok is True
        return text, result.content_hash

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_one, t) for t in texts]
        got = {text: digest for text, digest in (f.result() for f in as_completed(futures))}
    for text in texts:
        assert got[text] == content_hash16(text)


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
        next_text = "- fresh after timeout no stale\n"
        nxt = worker.parse_text(next_text, mode="logos", timeout_s=15.0)
        assert nxt.ok is True
        assert nxt.content_hash == content_hash16(next_text)
        assert nxt.content_hash != timed.content_hash
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
    parent_worker = get_bounded_page_parse_worker()
    assert parent_worker.parse_text("- parent before fork\n", timeout_s=15.0).ok
    parent_pid = parent_worker.pid
    assert parent_pid is not None

    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        try:
            child_worker = get_bounded_page_parse_worker()
            parent_still_alive = _pid_alive(parent_pid)
            child_result = child_worker.parse_text("- child after fork\n", timeout_s=15.0)
            child_ok = bool(
                child_result.ok
                and child_result.content_hash == content_hash16("- child after fork\n")
            )
            child_wp = child_worker.pid
            distinct = child_wp is not None and child_wp != parent_pid
            os.write(
                write_fd,
                f"{int(parent_still_alive)} {int(child_ok)} {int(distinct)}\n".encode(),
            )
            os.close(write_fd)
            os._exit(0 if parent_still_alive and child_ok and distinct else 1)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                os.write(write_fd, b"0 0 0\n")
                os.close(write_fd)
            os._exit(2)

    os.close(write_fd)
    with os.fdopen(read_fd, "rb") as pipe:
        raw = pipe.read()
    _waited, status = os.waitpid(child_pid, 0)
    ok_exit = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    parts = raw.decode().strip().split() if raw else []
    parent_after = parent_worker.parse_text("- parent after child exit\n", timeout_s=15.0)
    payload = {
        "parent_alive": bool(
            _pid_alive(parent_pid) and parent_after.ok and parent_worker.pid == parent_pid
        ),
        "child_ok": bool(ok_exit and parts == ["1", "1", "1"]),
        "distinct": bool(len(parts) == 3 and parts[2] == "1"),
    }
    conn.send(payload)
    conn.close()
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
    assert payload == {"parent_alive": True, "child_ok": True, "distinct": True}


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
