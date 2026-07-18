"""Shadow DB sync errors with bounded operator diagnostics."""

from __future__ import annotations

from ..utils.console_sanitize import sanitize_for_console

_SHADOW_ERROR_MAX_LEN = 200
_MAX_PATHS_IN_MESSAGE = 5


class ShadowSyncError(RuntimeError):
    """Raised when shadow ingestion cannot proceed without ambiguous block identity."""


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


__all__ = [
    "ShadowSyncError",
    "format_duplicate_block_uuid_error",
]
