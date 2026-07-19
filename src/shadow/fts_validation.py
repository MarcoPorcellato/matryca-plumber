"""Bounded FTS5 user-query validation (leaf module; no query/format imports)."""

from __future__ import annotations

_FTS_VALIDATION_PREFIX = "Invalid FTS query for `method=bm25`"
# Interactive FTS ``MATCH`` input cap (Unicode code points, post-``strip``). Chosen as 2×
# ``MAX_REGEX_PATTERN_LEN`` (256) to allow multi-token queries with operators while
# rejecting multi-kilobyte probes before SQLite.
MAX_FTS_MATCH_QUERY_CHARS = 512


class FtsQueryValidationError(ValueError):
    """User-supplied keyword is not a valid FTS5 ``MATCH`` expression."""


def check_fts_query_length_bounded(stripped_query: str) -> None:
    """Reject overlong user input before FTS preparation or SQLite ``MATCH``."""
    if len(stripped_query) > MAX_FTS_MATCH_QUERY_CHARS:
        raise FtsQueryValidationError(
            f"{_FTS_VALIDATION_PREFIX}: query exceeds max length "
            f"({MAX_FTS_MATCH_QUERY_CHARS} Unicode characters)."
        )


def validate_fts_match_query(keyword: str) -> None:
    """Reject obviously invalid FTS5 query syntax before hitting SQLite."""
    q = keyword.strip()
    if not q:
        raise FtsQueryValidationError(
            f"{_FTS_VALIDATION_PREFIX}: query is empty after trimming whitespace."
        )
    check_fts_query_length_bounded(q)
    if q.count('"') % 2 != 0:
        raise FtsQueryValidationError(
            f"{_FTS_VALIDATION_PREFIX}: unbalanced double quotes in {q!r}."
        )


__all__ = [
    "FtsQueryValidationError",
    "MAX_FTS_MATCH_QUERY_CHARS",
    "check_fts_query_length_bounded",
    "validate_fts_match_query",
]
