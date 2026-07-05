"""Tests for shared env parsing in :mod:`src.utils.env_parse`."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.graph.concurrency_probe import probe_concurrency_capability
from src.utils.env_parse import env_bool, env_float, env_int


def test_env_bool_truthy_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("MATRYCA_TEST_BOOL", raw)
        assert env_bool("MATRYCA_TEST_BOOL", default=False) is True


def test_env_bool_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_TEST_BOOL", raising=False)
    assert env_bool("MATRYCA_TEST_BOOL", default=True) is True


def test_env_int_warns_on_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []

    def _capture(msg: str, *args: object) -> None:
        warnings.append(msg.format(*args) if args else msg)

    monkeypatch.setattr("src.utils.env_parse.logger.warning", _capture)
    monkeypatch.setenv("MATRYCA_TEST_INT_ENV", "not-a-number")
    assert env_int("MATRYCA_TEST_INT_ENV", 42) == 42
    assert any("MATRYCA_TEST_INT_ENV" in warning for warning in warnings)


def test_env_float_warns_on_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []

    def _capture(msg: str, *args: object) -> None:
        warnings.append(msg.format(*args) if args else msg)

    monkeypatch.setattr("src.utils.env_parse.logger.warning", _capture)
    monkeypatch.setenv("MATRYCA_TEST_FLOAT_ENV", "not-a-float")
    assert env_float("MATRYCA_TEST_FLOAT_ENV", 1.5) == 1.5
    assert any("MATRYCA_TEST_FLOAT_ENV" in warning for warning in warnings)


# --- MATRYCA_ALLOW_FLOCK_DEGRADATION via env_bool ----------------------------


def test_flock_degradation_unset_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_ALLOW_FLOCK_DEGRADATION", raising=False)
    with patch("src.graph.concurrency_probe.cross_process_lock_available", return_value=False):
        cap = probe_concurrency_capability()
    assert cap.degradation_allowed is False
    assert cap.mode == "in_process_only"


def test_flock_degradation_truthy_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    for raw in ("1", "true", "yes", "on"):
        monkeypatch.setenv("MATRYCA_ALLOW_FLOCK_DEGRADATION", raw)
        with patch("src.graph.concurrency_probe.cross_process_lock_available", return_value=False):
            cap = probe_concurrency_capability()
        assert cap.degradation_allowed is True, f"failed for {raw!r}"
        assert cap.mode == "in_process_only"


def test_flock_degradation_ignored_when_flock_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_ALLOW_FLOCK_DEGRADATION", "true")
    with patch("src.graph.concurrency_probe.cross_process_lock_available", return_value=True):
        cap = probe_concurrency_capability()
    assert cap.mode == "full"
    assert cap.flock_available is True
