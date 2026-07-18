"""Tests for Graph Insights LLM fallback observability (issue #114).

Ensures that when ``llm.generate_graph_insights`` raises, the engine:
- emits a ``logger.warning`` so operators can detect LLM failures in logs, and
- returns ``llm_used=False`` (deterministic fallback semantics unchanged).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from src.graph.cognitive_llm import GraphInsightsLLMResult, InsightsLLM
from src.graph.insights_engine import InsightsRunResult, run_graph_insights_engine

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FailingInsightsLLM(InsightsLLM):
    """Stub LLM that always raises to simulate a network/model failure."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("simulated LLM failure")

    def generate_graph_insights(
        self, *, metrics_json: str, graph_root: Path
    ) -> GraphInsightsLLMResult:
        raise self._exc  # type: ignore[misc]


class _OkInsightsLLM(InsightsLLM):
    """Stub LLM that always succeeds."""

    def generate_graph_insights(
        self, *, metrics_json: str, graph_root: Path
    ) -> GraphInsightsLLMResult:
        return GraphInsightsLLMResult(
            ontology_report="LLM-enriched report.",
            cleanup_suggestions=["Fix orphan [[Alpha]]."],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_graph_root(tmp_path: Path) -> Path:
    """Create the minimum vault layout required by the insights engine."""
    (tmp_path / "pages").mkdir()
    (tmp_path / "pages" / "Alpha.md").write_text("- note\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_llm_failure_logs_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM raises, logger.exception must be called to capture the traceback."""
    root = _minimal_graph_root(tmp_path)

    messages: list[str] = []

    def _capture(msg: str, *args: object, **kwargs: object) -> None:  # noqa: ARG001
        messages.append(msg)

    monkeypatch.setattr("src.graph.insights_engine.logger.exception", _capture)

    run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert any("fallback" in m.lower() or "llm" in m.lower() for m in messages), (
        f"Expected a message mentioning the LLM fallback; got: {messages}"
    )


def test_llm_failure_sets_llm_used_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM raises, ``InsightsRunResult.llm_used`` must be False."""
    root = _minimal_graph_root(tmp_path)
    # Silence the exception log so test output is clean
    monkeypatch.setattr("src.graph.insights_engine.logger.exception", lambda *a, **k: None)

    result: InsightsRunResult = run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert result.llm_used is False, (
        "llm_used should remain False when the LLM raises and the deterministic fallback is used."
    )


def test_llm_success_sets_llm_used_true(tmp_path: Path) -> None:
    """When the LLM succeeds, ``InsightsRunResult.llm_used`` must be True."""
    root = _minimal_graph_root(tmp_path)

    result: InsightsRunResult = run_graph_insights_engine(root, llm=_OkInsightsLLM())

    assert result.llm_used is True


def test_llm_none_produces_deterministic_output(tmp_path: Path) -> None:
    """When no LLM is provided the deterministic path runs and llm_used=False."""
    root = _minimal_graph_root(tmp_path)

    result: InsightsRunResult = run_graph_insights_engine(root, llm=None)

    assert result.llm_used is False


def test_llm_failure_still_writes_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback path must still produce a written insights page."""
    root = _minimal_graph_root(tmp_path)
    monkeypatch.setattr("src.graph.insights_engine.logger.exception", lambda *a, **k: None)

    result: InsightsRunResult = run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert result.output_path.is_file(), (
        "The insights page must be written even when the LLM call fails."
    )


def test_llm_failure_uses_logger_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exception must be logged with logger.exception to capture the traceback."""
    root = _minimal_graph_root(tmp_path)

    called: list[bool] = []

    def _capture_exception(msg: str, *args: object, **kwargs: object) -> None:  # noqa: ARG001
        called.append(True)

    monkeypatch.setattr("src.graph.insights_engine.logger.exception", _capture_exception)

    run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert called, "logger.exception was not called"
