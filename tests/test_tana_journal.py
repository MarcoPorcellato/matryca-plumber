"""Tests for Logseq EDN journal date pattern translation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from src.agent.importers.tana.journal import (
    day_ordinal_suffix,
    format_edn_date_pattern,
    format_journal_page_title,
    resolve_journal_path,
    resolve_journal_path_from_vault,
)
from src.graph.logseq_config import get_logseq_journal_file_name_format

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tana"
_SAMPLE_DAY = date(2026, 6, 22)  # Monday


@pytest.mark.parametrize(
    ("day", "suffix"),
    [
        (1, "st"),
        (2, "nd"),
        (3, "rd"),
        (4, "th"),
        (11, "th"),
        (12, "th"),
        (13, "th"),
        (21, "st"),
        (22, "nd"),
        (23, "rd"),
        (31, "st"),
    ],
)
def test_day_ordinal_suffix(day: int, suffix: str) -> None:
    assert day_ordinal_suffix(day) == suffix


@pytest.mark.parametrize("day", range(1, 32))
def test_do_token_all_days_of_month(day: int) -> None:
    current = date(2026, 1, day)
    rendered = format_edn_date_pattern("do", current)
    assert rendered == f"{day}{day_ordinal_suffix(day)}"


def test_yyyy_mm_dd_pattern() -> None:
    assert format_edn_date_pattern("yyyy-MM-dd", _SAMPLE_DAY) == "2026-06-22"


def test_mmm_do_yyyy_pattern() -> None:
    assert format_edn_date_pattern("MMM do, yyyy", _SAMPLE_DAY) == "Jun 22nd, 2026"


def test_eee_mmm_dd_pattern() -> None:
    assert format_edn_date_pattern("EEE MMM dd", _SAMPLE_DAY) == "Mon Jun 22"


def test_yyyy_slash_mmm_slash_dd_pattern() -> None:
    assert format_edn_date_pattern("yyyy/MMM/dd", _SAMPLE_DAY) == "2026/Jun/22"


def test_single_quoted_literals() -> None:
    assert format_edn_date_pattern("'Journal:' yyyy-MM-dd", _SAMPLE_DAY) == "Journal: 2026-06-22"


def test_escaped_quote_literal() -> None:
    assert format_edn_date_pattern("yyyy''MMdd", _SAMPLE_DAY) == "2026'0622"


def test_doubled_quote_inside_literal() -> None:
    assert format_edn_date_pattern("'o''clock' yyyy", _SAMPLE_DAY) == "o'clock 2026"


def test_unmatched_quote_consumes_remaining_literal() -> None:
    assert format_edn_date_pattern("yyyy 'journal MM", _SAMPLE_DAY) == "2026 journal MM"


def test_whitespace_pattern_uses_default_format() -> None:
    assert format_edn_date_pattern("   ", _SAMPLE_DAY) == "2026-06-22"


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        ("MMMMM", "June6"),
        ("EEEEE", "MondayE"),
        ("'Q' q yyyy", "Q q 2026"),
    ],
)
def test_token_longest_prefix_boundaries(pattern: str, expected: str) -> None:
    assert format_edn_date_pattern(pattern, _SAMPLE_DAY) == expected


def test_format_journal_page_title_alias() -> None:
    assert format_journal_page_title(_SAMPLE_DAY, "yyyy-MM-dd") == "2026-06-22"


def test_resolve_journal_path_default_format() -> None:
    result = resolve_journal_path("/tmp/vault", _SAMPLE_DAY, page_title_format="yyyy-MM-dd")
    assert result.page_title == "2026-06-22"
    assert result.relative_path == "journals/2026-06-22.md"
    assert result.absolute_path.name == "2026-06-22.md"


def test_resolve_journal_path_split_title_and_filename(tmp_path: Path) -> None:
    result = resolve_journal_path(
        tmp_path,
        _SAMPLE_DAY,
        page_title_format="MMM do, yyyy",
        file_name_format="yyyy-MM-dd",
    )
    assert result.page_title == "Jun 22nd, 2026"
    assert result.relative_path == "journals/2026-06-22.md"


def test_resolve_journal_path_from_vault_custom_config(tmp_path: Path) -> None:
    logseq_dir = tmp_path / "logseq"
    logseq_dir.mkdir()
    (logseq_dir / "config.edn").write_text(
        '{:journal/page-title-format "MMM do, yyyy"\n :journal/file-name-format "yyyy-MM-dd"}',
        encoding="utf-8",
    )
    result = resolve_journal_path_from_vault(tmp_path, _SAMPLE_DAY)
    assert result.page_title == "Jun 22nd, 2026"
    assert result.relative_path == "journals/2026-06-22.md"
    assert result.format_warning is None
    assert get_logseq_journal_file_name_format(tmp_path) == "yyyy-MM-dd"


def test_resolve_journal_path_from_vault_missing_config_fallback(tmp_path: Path) -> None:
    result = resolve_journal_path_from_vault(tmp_path, _SAMPLE_DAY)
    assert result.page_title == "2026-06-22"
    assert result.relative_path == "journals/2026-06-22.md"
    assert result.format_warning is not None
