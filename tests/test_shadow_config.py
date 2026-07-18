"""Tests for Shadow DB env flag (#184)."""

from __future__ import annotations

import pytest
from src.shadow.config import shadow_db_enabled


def test_shadow_db_enabled_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MATRYCA_SHADOW_DB_ENABLED", raising=False)
    assert shadow_db_enabled() is False


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", ""])
def test_shadow_db_enabled_false_tokens(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", value)
    assert shadow_db_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_shadow_db_enabled_true_tokens(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", value)
    assert shadow_db_enabled() is True
