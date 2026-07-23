"""Shared environment variable parsing (graph + agent safe)."""

from __future__ import annotations

import os

from loguru import logger


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def env_int(key: str, default: int) -> int:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for {}={!r}; using default {}", key, raw, default)
        return default


def env_int_clamped(
    key: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    """Parse an integer env var and clamp to ``[minimum, maximum]``."""
    value = env_int(key, default)
    if value < minimum:
        logger.warning(
            "Integer for {}={} below minimum {}; clamping",
            key,
            value,
            minimum,
        )
        return minimum
    if value > maximum:
        logger.warning(
            "Integer for {}={} above maximum {}; clamping",
            key,
            value,
            maximum,
        )
        return maximum
    return value


def env_float(key: str, default: float) -> float:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for {}={!r}; using default {}", key, raw, default)
        return default


def env_float_clamped(
    key: str,
    default: float,
    *,
    minimum: float,
    maximum: float,
) -> float:
    """Parse a float env var and clamp to ``[minimum, maximum]``."""
    value = env_float(key, default)
    if value < minimum:
        logger.warning(
            "Float for {}={} below minimum {}; clamping",
            key,
            value,
            minimum,
        )
        return minimum
    if value > maximum:
        logger.warning(
            "Float for {}={} above maximum {}; clamping",
            key,
            value,
            maximum,
        )
        return maximum
    return value


def env_str(key: str, default: str = "") -> str:
    raw = os.environ.get(key, "").strip().lower()
    return raw if raw else default


__all__ = [
    "env_bool",
    "env_float",
    "env_float_clamped",
    "env_int",
    "env_int_clamped",
    "env_str",
]
