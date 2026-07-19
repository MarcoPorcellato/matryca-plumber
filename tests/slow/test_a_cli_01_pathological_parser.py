"""A-CLI-01 — LogosParser pathological latency (parser-only, no Matryca).

Finding: a privacy-clean structural synthetic page (~1.1k lines) completes in
tens of seconds under ``LogosParser().parse``, while a same-scale well-formed
control page stays well under a healthy budget. This is **pathological
latency**, not an infinite hang / deadlock.

Excluded from default CI (``@pytest.mark.slow`` / ``make perf``).
Track: https://github.com/MarcoPorcellato/matryca-plumber/issues/297
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import time
from queue import Empty
from typing import Any

import pytest
from logseq_matryca_parser import LogosParser
from tests.a_cli_01_generator import (
    PATHOLOGICAL_PAGE_BYTE_COUNT,
    PATHOLOGICAL_PAGE_LINE_COUNT,
    PATHOLOGICAL_PAGE_SHA256,
    generate_control_page,
    generate_pathological_page,
)

# Healthy single-page budget for ~1k-line Logseq Markdown on CI laptops.
# Control page must pass; pathological page currently violates (~10–15s locally).
_HEALTHY_BUDGET_S = 2.0
# Hard ceiling: proves completion (latency class), not a process deadlock.
_HARD_CEILING_S = 90.0
_TERMINATE_GRACE_S = 5.0


def _child_parse_pathological(text: str, queue: mp.Queue[dict[str, Any]]) -> None:
    """Parse in a child process; report minimal status (no AST payload)."""
    started = time.perf_counter()
    try:
        page = LogosParser().parse(text)
        queue.put(
            {
                "ok": page is not None,
                "s": round(time.perf_counter() - started, 3),
            }
        )
    except Exception as exc:  # noqa: BLE001 - surface type only to parent
        queue.put(
            {
                "ok": False,
                "error": type(exc).__name__,
                "s": round(time.perf_counter() - started, 3),
            }
        )


def _parse_pathological_bounded(text: str) -> dict[str, Any]:
    """Run LogosParser in a spawn child; enforce hard ceiling or fail.

    Overrun/deadlock → terminate/kill + ``pytest.fail`` (never hangs the suite).
    Successful completion → minimal ``{ok, s}`` status dict.
    """
    ctx = mp.get_context("spawn")
    queue: mp.Queue[dict[str, Any]] = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_child_parse_pathological, args=(text, queue))
    proc.start()
    try:
        proc.join(timeout=_HARD_CEILING_S)
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=_TERMINATE_GRACE_S)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=_TERMINATE_GRACE_S)
            assert not proc.is_alive(), (
                "child still alive after terminate/kill — hard ceiling unenforceable"
            )
            pytest.fail(
                f"pathological LogosParser exceeded {_HARD_CEILING_S:.0f}s hard ceiling "
                "(child terminated)"
            )
        assert proc.exitcode == 0, f"child exitcode={proc.exitcode}"
        try:
            result = queue.get(timeout=1.0)
        except Empty:
            pytest.fail("child produced no status")
        assert result.get("ok") is True, f"child parse failed: {result}"
        return result
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=_TERMINATE_GRACE_S)
        queue.close()
        queue.join_thread()


@pytest.mark.slow
def test_a_cli_01_generator_hash_contract() -> None:
    text = generate_pathological_page()
    assert text.count("\n") == PATHOLOGICAL_PAGE_LINE_COUNT
    assert len(text.encode("utf-8")) == PATHOLOGICAL_PAGE_BYTE_COUNT
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == PATHOLOGICAL_PAGE_SHA256


@pytest.mark.slow
def test_a_cli_01_control_page_meets_healthy_budget() -> None:
    text = generate_control_page(line_count=PATHOLOGICAL_PAGE_LINE_COUNT)
    started = time.perf_counter()
    page = LogosParser().parse(text)
    elapsed = time.perf_counter() - started
    assert page is not None
    assert elapsed < _HEALTHY_BUDGET_S, f"control page too slow: {elapsed:.3f}s"


@pytest.mark.slow
def test_a_cli_01_pathological_page_completes_within_hard_ceiling() -> None:
    """Pathological page must finish within hard ceiling (child process enforced)."""
    result = _parse_pathological_bounded(generate_pathological_page())
    assert float(result["s"]) < _HARD_CEILING_S


@pytest.mark.slow
def test_a_cli_01_pathological_page_meets_healthy_budget() -> None:
    """Audit probe: pathological shape should meet the healthy single-page budget.

    Uses the same spawn hard ceiling as the completion probe so a deadlock cannot
    hang ``make perf``. Pathological latency (≥2s) is reported via ``pytest.xfail``
    (not ``@pytest.mark.xfail``), so overrun remains a hard failure.
    """
    result = _parse_pathological_bounded(generate_pathological_page())
    duration = float(result["s"])
    if duration >= _HEALTHY_BUDGET_S:
        pytest.xfail(
            "A-CLI-01: LogosParser pathological latency "
            f"{duration:.3f}s exceeds healthy budget {_HEALTHY_BUDGET_S:.1f}s (#297)"
        )
    assert duration < _HEALTHY_BUDGET_S
