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


def test_llm_failure_logs_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM raises, a warning must be emitted before the fallback."""
    root = _minimal_graph_root(tmp_path)

    warnings: list[str] = []

    def _capture(msg: str, *args: object, **kwargs: object) -> None:  # noqa: ARG001
        warnings.append(msg)

    monkeypatch.setattr("src.graph.insights_engine.logger.warning", _capture)

    run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert any("fallback" in w.lower() or "llm" in w.lower() for w in warnings), (
        f"Expected a warning mentioning the LLM fallback; got: {warnings}"
    )


def test_llm_failure_sets_llm_used_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the LLM raises, ``InsightsRunResult.llm_used`` must be False."""
    root = _minimal_graph_root(tmp_path)
    # Silence the warning so test output is clean
    monkeypatch.setattr("src.graph.insights_engine.logger.warning", lambda *a, **k: None)

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
    monkeypatch.setattr("src.graph.insights_engine.logger.warning", lambda *a, **k: None)

    result: InsightsRunResult = run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert result.output_path.is_file(), (
        "The insights page must be written even when the LLM call fails."
    )


def test_llm_failure_warning_contains_exc_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The warning call must pass ``exc_info=True`` so the traceback is captured."""
    root = _minimal_graph_root(tmp_path)

    captured_kwargs: list[dict] = []

    def _capture_kwargs(msg: str, *args: object, **kwargs: object) -> None:  # noqa: ARG001
        captured_kwargs.append(dict(kwargs))

    monkeypatch.setattr("src.graph.insights_engine.logger.warning", _capture_kwargs)

    run_graph_insights_engine(root, llm=_FailingInsightsLLM())

    assert captured_kwargs, "logger.warning was not called"
    assert any(kw.get("exc_info") for kw in captured_kwargs), (
        "logger.warning must be called with exc_info=True to capture the traceback"
    )
