"""Environment-driven configuration for the Shadow DB read cache (v2 Phase 3)."""

from __future__ import annotations

from ..utils.env_parse import env_bool


def shadow_db_enabled() -> bool:
    """Return whether the Shadow DB subsystem is enabled (opt-in alpha).

    Parsing only — no runtime wiring in this slice. When false or unset, callers
    must not create, sync, or read ``shadow.sqlite`` (enforced in follow-up PR-0).
    """
    return env_bool("MATRYCA_SHADOW_DB_ENABLED", default=False)


__all__ = ["shadow_db_enabled"]
