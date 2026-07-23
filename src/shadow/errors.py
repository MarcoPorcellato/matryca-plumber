"""Shadow DB sync errors with bounded operator diagnostics."""

from __future__ import annotations

import re

from ..utils.console_sanitize import sanitize_for_console

_SHADOW_ERROR_MAX_LEN = 200
_MAX_PATHS_IN_MESSAGE = 5
_PARSE_ERROR_CATEGORY = re.compile(r"[^A-Za-z0-9_-]+")
_PUBLIC_PARSE_CATEGORIES = frozenset(
    {"timeout", "protocol_mismatch", "unpickle_error", "invalid_mode", "parse_error"}
)


class ShadowSyncError(RuntimeError):
    """Raised when shadow ingestion cannot proceed without ambiguous block identity."""


class ShadowPageParseError(ShadowSyncError):
    """Raised when the bounded worker cannot parse one source page safely."""


def _display_uuid(block_uuid: str) -> str:
    cleaned = sanitize_for_console(block_uuid.strip())
    if len(cleaned) > 12:
        return f"{cleaned[:8]}…"
    return cleaned


def format_duplicate_block_uuid_error(
    block_uuid: str,
    file_paths: list[str],
    *,
    max_paths: int = _MAX_PATHS_IN_MESSAGE,
    max_len: int = _SHADOW_ERROR_MAX_LEN,
) -> str:
    """Build a bounded diagnostic for duplicate ``block_uuid`` conflicts."""
    uid = _display_uuid(block_uuid)
    unique_paths: list[str] = []
    for raw in file_paths:
        path = sanitize_for_console(raw.strip())
        if path and path not in unique_paths:
            unique_paths.append(path)
    unique_paths = unique_paths[:max_paths]

    if len(unique_paths) == 1:
        body = f"duplicate block_uuid {uid} within page: {unique_paths[0]}"
    else:
        body = f"duplicate block_uuid {uid} across pages: {', '.join(unique_paths)}"

    if len(body) <= max_len:
        return body
    return body[: max_len - 1] + "…"


def format_bounded_page_parse_error(
    *,
    category: str | None,
    content_hash: str,
    byte_count: int,
    line_count: int,
    mode: str,
    max_len: int = _SHADOW_ERROR_MAX_LEN,
) -> str:
    """Build a content-free bounded page-parse diagnostic for persisted meta.

    The source pathname, page title, body, and raw worker exception are
    deliberately excluded.  This string can appear in health/API diagnostics.
    """
    raw_category = sanitize_for_console(category or "parse_error")
    safe_category = _PARSE_ERROR_CATEGORY.sub("_", raw_category).strip("_")
    if safe_category not in _PUBLIC_PARSE_CATEGORIES:
        safe_category = "parse_error"
    safe_hash = sanitize_for_console(content_hash)[:64]
    safe_mode = _PARSE_ERROR_CATEGORY.sub("_", sanitize_for_console(mode)).strip("_")
    if not safe_mode:
        safe_mode = "unknown"
    body = (
        "bounded page parse failed: "
        f"category={safe_category} content_hash={safe_hash} "
        f"byte_count={max(0, byte_count)} line_count={max(0, line_count)} "
        f"mode={safe_mode[:16]}"
    )
    if len(body) <= max_len:
        return body
    return body[: max_len - 1] + "…"


__all__ = [
    "ShadowPageParseError",
    "ShadowSyncError",
    "format_bounded_page_parse_error",
    "format_duplicate_block_uuid_error",
]
