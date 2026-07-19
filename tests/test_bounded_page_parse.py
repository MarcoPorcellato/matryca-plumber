"""PR2B — bounded page parse worker (no Shadow/AST integration)."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator

import pytest
from src.graph.bounded_page_parse import (
    BoundedPageParseWorker,
    ParseMode,
    content_hash16,
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


def test_parse_result_never_embeds_abs_paths() -> None:
    result = parse_page_text_bounded("- hello\n", mode="logos", timeout_s=15.0)
    blob = repr(result)
    assert "/Users/" not in blob
    assert "Documents/" not in blob
