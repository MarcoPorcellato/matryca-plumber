"""Logseq ``config.edn`` Java/Clojure date patterns → Python journal titles and paths."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ....graph.logseq_config import (
    DEFAULT_JOURNAL_PAGE_TITLE_FORMAT,
    get_logseq_journal_file_name_format,
    get_logseq_journal_format,
)
from ....graph.page_path import page_title_to_filename

# Java SimpleDateFormat tokens (longest match first).
_JAVA_TOKENS: tuple[tuple[str, str], ...] = (
    ("yyyy", "%Y"),
    ("MMMM", "%B"),
    ("MMM", "%b"),
    ("EEEE", "%A"),
    ("EEE", "%a"),
    ("do", "__ORDINAL_DAY__"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("yy", "%y"),
    ("M", "%-m"),
    ("d", "%-d"),
)


def day_ordinal_suffix(day: int) -> str:
    """Return English ordinal suffix (``st``, ``nd``, ``rd``, ``th``) for ``day``."""
    if day in (11, 12, 13):
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_ordinal_day(day: date) -> str:
    """Format day with ordinal suffix (Logseq/Java ``do`` token)."""
    return f"{day.day}{day_ordinal_suffix(day.day)}"


def _format_python_strftime(pattern: str, day: date) -> str:
    """Apply a Python ``strftime`` pattern, supporting ``%-d`` / ``%-m`` on Unix."""
    try:
        return day.strftime(pattern)
    except ValueError:
        # Windows lacks ``%-d``; emulate no-zero-padding.
        patched = (
            pattern.replace("%-d", f"{day.day}")
            .replace("%-m", f"{day.month}")
            .replace("%-y", f"{day.year % 100}")
        )
        return day.strftime(patched)


def _consume_quoted_literal(pattern: str, start: int) -> tuple[str, int]:
    length = len(pattern)
    if start + 1 < length and pattern[start + 1] == "'":
        return "'", start + 2

    literal: list[str] = []
    i = start + 1
    while i < length:
        if pattern[i] == "'":
            if i + 1 < length and pattern[i + 1] == "'":
                literal.append("'")
                i += 2
                continue
            return "".join(literal), i + 1
        literal.append(pattern[i])
        i += 1
    return "".join(literal), i


def format_edn_date_pattern(pattern: str, day: date) -> str:
    """Translate a Logseq/Java ``journal/page-title-format`` pattern for ``day``.

    Supports common tokens (``yyyy``, ``MMM``, ``do``, ``EEE``, …) and single-quoted literals.
    """
    if not pattern.strip():
        pattern = DEFAULT_JOURNAL_PAGE_TITLE_FORMAT

    out: list[str] = []
    i = 0
    length = len(pattern)
    while i < length:
        ch = pattern[i]
        if ch == "'":
            literal, i = _consume_quoted_literal(pattern, i)
            out.append(literal)
            continue

        matched = False
        for java_tok, py_tok in _JAVA_TOKENS:
            if pattern.startswith(java_tok, i):
                if py_tok == "__ORDINAL_DAY__":
                    out.append(format_ordinal_day(day))
                else:
                    out.append(_format_python_strftime(py_tok, day))
                i += len(java_tok)
                matched = True
                break
        if not matched:
            out.append(ch)
            i += 1
    return "".join(out)


def format_journal_page_title(day: date, page_title_format: str) -> str:
    """Semantic Logseq journal page title for ``day``."""
    return format_edn_date_pattern(page_title_format, day)


@dataclass(frozen=True, slots=True)
class JournalPathResult:
    """Resolved journal title and on-disk path under a vault."""

    page_title: str
    relative_path: str
    absolute_path: Path
    page_title_format: str
    file_name_format: str
    format_warning: str | None = None


def resolve_journal_path(
    vault_path: str | Path,
    day: date,
    *,
    page_title_format: str | None = None,
    file_name_format: str | None = None,
    format_warning: str | None = None,
) -> JournalPathResult:
    """Build journal title + ``journals/*.md`` path using Logseq EDN date patterns."""
    root = Path(vault_path).expanduser()
    title_fmt = page_title_format or DEFAULT_JOURNAL_PAGE_TITLE_FORMAT
    file_fmt = file_name_format or title_fmt
    page_title = format_journal_page_title(day, title_fmt)
    file_stem_title = format_journal_page_title(day, file_fmt)
    filename = page_title_to_filename(file_stem_title)
    rel = Path("journals") / filename
    return JournalPathResult(
        page_title=page_title,
        relative_path=rel.as_posix(),
        absolute_path=root / rel,
        page_title_format=title_fmt,
        file_name_format=file_fmt,
        format_warning=format_warning,
    )


def resolve_journal_path_from_vault(vault_path: str | Path, day: date) -> JournalPathResult:
    """Read ``config.edn`` and resolve the journal path for ``day``."""
    fmt = get_logseq_journal_format(vault_path)
    file_fmt = get_logseq_journal_file_name_format(vault_path)
    return resolve_journal_path(
        vault_path,
        day,
        page_title_format=fmt.format_string,
        file_name_format=file_fmt or fmt.format_string,
        format_warning=fmt.warning,
    )


__all__ = [
    "JournalPathResult",
    "day_ordinal_suffix",
    "format_edn_date_pattern",
    "format_journal_page_title",
    "format_ordinal_day",
    "resolve_journal_path",
    "resolve_journal_path_from_vault",
]
