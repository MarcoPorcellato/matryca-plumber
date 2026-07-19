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
import time

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
    """Pathological page must finish (bounded latency), not hang forever."""
    text = generate_pathological_page()
    started = time.perf_counter()
    page = LogosParser().parse(text)
    elapsed = time.perf_counter() - started
    assert page is not None
    assert elapsed < _HARD_CEILING_S, f"exceeded hard ceiling: {elapsed:.3f}s"


@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    reason="A-CLI-01: LogosParser pathological latency on structural synthetic page (#297)",
)
def test_a_cli_01_pathological_page_meets_healthy_budget() -> None:
    """Audit probe: pathological shape should meet the healthy single-page budget."""
    text = generate_pathological_page()
    started = time.perf_counter()
    page = LogosParser().parse(text)
    elapsed = time.perf_counter() - started
    assert page is not None
    assert elapsed < _HEALTHY_BUDGET_S, (
        f"pathological latency: {elapsed:.3f}s exceeds healthy budget "
        f"{_HEALTHY_BUDGET_S:.1f}s (expected until parser fix)"
    )
