"""Pytest hooks: ensure ``logseq-matryca-parser`` is importable in dev."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    from logseq_matryca_parser import LogosParser  # noqa: F401
except ImportError:
    _PARSER_SRC = Path(__file__).resolve().parents[2] / "logseq-matryca-parser" / "src"
    if _PARSER_SRC.is_dir():
        parser_src = str(_PARSER_SRC)
        if parser_src not in sys.path:
            sys.path.insert(0, parser_src)
    from logseq_matryca_parser import LogosParser  # noqa: F401

_THERMAL_DELAY_ENV_KEYS = (
    "MATRYCA_THERMAL_DELAY_BOOTSTRAP",
    "MATRYCA_THERMAL_DELAY_COGNITIVE",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-prompt-hashes",
        action="store_true",
        default=False,
        help="Rewrite tests/prompt_hash_snapshots.json from current Tier-1 builders",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--update-prompt-hashes", default=False):
        from tests.test_daemon_prompts import update_prompt_hash_snapshots

        update_prompt_hash_snapshots()
        print("Updated tests/prompt_hash_snapshots.json")


@pytest.fixture(autouse=True)
def zero_thermal_delays_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip real thermal cool-down sleeps unless a test overrides these env vars."""
    for key in _THERMAL_DELAY_ENV_KEYS:
        monkeypatch.setenv(key, "0")


@pytest.fixture(autouse=True)
def isolated_shadow_cache_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Keep runtime Shadow caches outside graph fixtures and inside pytest storage."""
    cache_root = tmp_path.parent / f"{tmp_path.name}-matryca-cache"
    monkeypatch.setenv("MATRYCA_CACHE_PATH", str(cache_root))
    return cache_root
