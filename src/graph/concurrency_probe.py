"""Detect cross-process file locking capabilities for operator preflight."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..utils.env_parse import env_bool
from .page_write_lock import cross_process_lock_available

ConcurrencyMode = Literal["full", "in_process_only"]


@dataclass(frozen=True, slots=True)
class ConcurrencyCapability:
    """Runtime concurrency contract exposed to UI preflight and daemon startup."""

    mode: ConcurrencyMode
    flock_available: bool
    degradation_allowed: bool
    message: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "mode": self.mode,
            "flock_available": self.flock_available,
            "degradation_allowed": self.degradation_allowed,
            "message": self.message,
        }


def probe_concurrency_capability() -> ConcurrencyCapability:
    """Return the active cross-process locking mode for this host."""
    flock_ok = cross_process_lock_available()
    degradation = env_bool("MATRYCA_ALLOW_FLOCK_DEGRADATION", default=False)
    if flock_ok:
        return ConcurrencyCapability(
            mode="full",
            flock_available=True,
            degradation_allowed=degradation,
            message="Cross-process flock is available for page and JSON sidecars.",
        )
    if degradation:
        return ConcurrencyCapability(
            mode="in_process_only",
            flock_available=False,
            degradation_allowed=True,
            message=(
                "Cross-process flock is unavailable; only in-process locks are active. "
                "Run a single Matryca Plumber writer (daemon OR MCP) on this vault."
            ),
        )
    return ConcurrencyCapability(
        mode="in_process_only",
        flock_available=False,
        degradation_allowed=False,
        message=(
            "Cross-process flock is unavailable and MATRYCA_ALLOW_FLOCK_DEGRADATION is not set. "
            "Concurrent daemon and MCP writes may corrupt files on this platform."
        ),
    )


__all__ = [
    "ConcurrencyCapability",
    "ConcurrencyMode",
    "probe_concurrency_capability",
]
