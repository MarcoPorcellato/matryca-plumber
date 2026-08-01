"""Strict read-only daemon profile backed only by the external Shadow cache."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from ..graph.safety.write_policy import is_graph_read_only
from ..shadow.cache_location import ShadowCacheLocationError, resolve_shadow_cache_location
from ..shadow.config import shadow_db_enabled

DaemonProfile = Literal["standard", "read_only_shadow_observer"]

STANDARD_DAEMON_PROFILE: DaemonProfile = "standard"
READ_ONLY_SHADOW_OBSERVER_PROFILE: DaemonProfile = "read_only_shadow_observer"
READ_ONLY_DISABLED_DUTIES: tuple[str, ...] = (
    "bootstrap_harvest",
    "semantic_writes",
    "journey_log",
    "property_hygiene",
    "generated_content",
    "post_write_hooks",
    "robot_git",
    "graph_local_state",
)


class ReadOnlyDaemonProfileError(RuntimeError):
    """A content-free failure to start the strict read-only daemon profile."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Read-only daemon profile unavailable ({reason})")


def active_daemon_profile() -> DaemonProfile:
    """Return the configured daemon profile without touching the filesystem."""

    if is_graph_read_only():
        return READ_ONLY_SHADOW_OBSERVER_PROFILE
    return STANDARD_DAEMON_PROFILE


def disabled_daemon_duties() -> tuple[str, ...]:
    """Return duties disabled by the active profile."""

    if active_daemon_profile() == READ_ONLY_SHADOW_OBSERVER_PROFILE:
        return READ_ONLY_DISABLED_DUTIES
    return ()


def prepare_read_only_daemon_environment(graph_root: Path) -> Path:
    """Validate the external cache and route daemon logs outside the graph."""

    if not is_graph_read_only():
        raise ReadOnlyDaemonProfileError("read_only_not_enabled")
    if not shadow_db_enabled():
        raise ReadOnlyDaemonProfileError("shadow_disabled")
    try:
        location = resolve_shadow_cache_location(graph_root)
        location.ensure_directory()
    except (OSError, RuntimeError, ShadowCacheLocationError) as exc:
        raise ReadOnlyDaemonProfileError("external_cache_unavailable") from exc

    daemon_dir = (location.shadow_dir.parent / "daemon").resolve(strict=False)
    if not daemon_dir.is_relative_to(location.cache_root) or daemon_dir.is_symlink():
        raise ReadOnlyDaemonProfileError("daemon_directory_unsafe")
    daemon_dir.mkdir(mode=0o700, exist_ok=True)
    if os.name == "posix":
        daemon_dir.chmod(0o700)

    os.environ["MATRYCA_PLUMBER_LOG_PATH"] = str(daemon_dir / "operations.jsonl")
    os.environ["MATRYCA_LOGURU_LOG_PATH"] = str(daemon_dir / "daemon.log")
    return daemon_dir


__all__ = [
    "DaemonProfile",
    "READ_ONLY_DISABLED_DUTIES",
    "READ_ONLY_SHADOW_OBSERVER_PROFILE",
    "ReadOnlyDaemonProfileError",
    "active_daemon_profile",
    "disabled_daemon_duties",
    "prepare_read_only_daemon_environment",
]
