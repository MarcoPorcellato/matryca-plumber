"""Content-free operational diagnostics for an existing Shadow connection."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from .meta import META_LAST_INCREMENTAL_SYNC_AT, current_generation, get_meta


@dataclass(frozen=True, slots=True)
class ShadowDiagnosticsSnapshot:
    """Bounded-cardinality Shadow metadata and quarantine pressure."""

    schema_version: int
    generation: int
    last_incremental_sync_at: str | None
    quarantined_page_count: int
    quarantine_retry_count: int
    current_timeout_attempt_count: int
    current_error_attempt_count: int
    max_quarantine_attempt_count: int
    oldest_quarantine_age_seconds: int | None

    def to_dict(self) -> dict[str, int | str | None]:
        """Return a stable machine-readable payload with no paths or content."""
        return asdict(self)


def _parse_aware_timestamp(raw: str | None) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _normalized_timestamp(raw: str | None) -> str | None:
    parsed = _parse_aware_timestamp(raw)
    return parsed.isoformat() if parsed is not None else None


def _non_negative(value: object) -> int:
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def shadow_diagnostics_snapshot(
    connection: sqlite3.Connection,
    *,
    now: datetime | None = None,
) -> ShadowDiagnosticsSnapshot:
    """Aggregate diagnostics without changing the connection or Shadow state."""
    observed_at = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)

    row = connection.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(SUM(MAX(attempt_count - 1, 0)), 0),
            COALESCE(SUM(CASE WHEN reason = 'parse_timeout' THEN attempt_count ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN reason = 'parse_error' THEN attempt_count ELSE 0 END), 0),
            COALESCE(MAX(attempt_count), 0),
            MIN(first_quarantined_at)
        FROM quarantined_pages
        """
    ).fetchone()
    values = row or (0, 0, 0, 0, 0, None)
    first_quarantined_at = _parse_aware_timestamp(str(values[5]) if values[5] is not None else None)
    oldest_age = (
        max(0, int((observed_at - first_quarantined_at).total_seconds()))
        if first_quarantined_at is not None
        else None
    )

    return ShadowDiagnosticsSnapshot(
        schema_version=1,
        generation=current_generation(connection),
        last_incremental_sync_at=_normalized_timestamp(
            get_meta(connection, META_LAST_INCREMENTAL_SYNC_AT)
        ),
        quarantined_page_count=_non_negative(values[0]),
        quarantine_retry_count=_non_negative(values[1]),
        current_timeout_attempt_count=_non_negative(values[2]),
        current_error_attempt_count=_non_negative(values[3]),
        max_quarantine_attempt_count=_non_negative(values[4]),
        oldest_quarantine_age_seconds=oldest_age,
    )


__all__ = ["ShadowDiagnosticsSnapshot", "shadow_diagnostics_snapshot"]
