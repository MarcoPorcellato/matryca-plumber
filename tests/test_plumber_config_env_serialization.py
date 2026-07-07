"""Tests for ``.env`` serialization helpers in :mod:`src.agent.plumber_config`."""

from __future__ import annotations

import pytest
from src.agent.plumber_config import (
    format_dotenv_value,
    serialize_plumber_config_field_for_dotenv,
)


def test_format_dotenv_value_quotes_dollar_sign() -> None:
    assert format_dotenv_value("plain") == "plain"
    quoted = format_dotenv_value("a$b")
    assert quoted.startswith('"')
    assert quoted.endswith('"')
    assert "$" in quoted


def test_serialize_thermal_rejects_nan_and_inf() -> None:
    with pytest.raises(ValueError, match="finite"):
        serialize_plumber_config_field_for_dotenv("thermal_delay_bootstrap", float("nan"))
    with pytest.raises(ValueError, match="finite"):
        serialize_plumber_config_field_for_dotenv("thermal_delay_cognitive", float("inf"))
    assert serialize_plumber_config_field_for_dotenv("thermal_delay_bootstrap", 1.5) == "1.5"


def test_serialize_thermal_accepts_int() -> None:
    assert serialize_plumber_config_field_for_dotenv("thermal_delay_bootstrap", 2) == "2.0"


def test_env_int_warns_on_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.utils import env_parse

    warnings: list[str] = []

    def _capture(msg: str, *args: object) -> None:
        warnings.append(msg.format(*args) if args else msg)

    monkeypatch.setattr("src.utils.env_parse.logger.warning", _capture)
    monkeypatch.setenv("MATRYCA_TEST_INT_ENV", "not-a-number")
    assert env_parse.env_int("MATRYCA_TEST_INT_ENV", 42) == 42
    assert any("MATRYCA_TEST_INT_ENV" in warning for warning in warnings)


def test_env_float_warns_on_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.utils import env_parse

    warnings: list[str] = []

    def _capture(msg: str, *args: object) -> None:
        warnings.append(msg.format(*args) if args else msg)

    monkeypatch.setattr("src.utils.env_parse.logger.warning", _capture)
    monkeypatch.setenv("MATRYCA_TEST_FLOAT_ENV", "not-a-float")
    assert env_parse.env_float("MATRYCA_TEST_FLOAT_ENV", 1.5) == 1.5
    assert any("MATRYCA_TEST_FLOAT_ENV" in warning for warning in warnings)
