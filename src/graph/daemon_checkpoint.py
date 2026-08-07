"""Read-only daemon checkpoint access (graph-local; no ``maintenance_daemon`` import)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from ..utils.bounded_json import BoundedJsonError, read_bounded_json
from .safety.write_policy import is_graph_read_only

CHECKPOINT_FILENAME = ".matryca_daemon_state.json"
CHECKPOINT_BAK_FILENAME = f"{CHECKPOINT_FILENAME}.bak"


@dataclass(frozen=True, slots=True)
class DaemonCheckpointView:
    """Bootstrap fields read from ``.matryca_daemon_state.json``."""

    bootstrap_complete: bool = False
    bootstrap_failed: bool = False
    bootstrap_failed_reason: str | None = None
    bootstrap_scanned: int = 0
    bootstrap_total: int = 0
    status: str | None = None
    recovery_source: Literal["missing", "primary", "backup", "reset"] = "missing"
    reset_event: bool = False


def checkpoint_path(graph_root: Path) -> Path:
    return graph_root / CHECKPOINT_FILENAME


def _read_checkpoint_payload(path: Path) -> dict[str, Any] | None:
    for attempt in range(2):
        try:
            payload = read_bounded_json(path)
        except BoundedJsonError:
            if attempt == 0:
                continue
            return None
        if isinstance(payload, dict):
            return payload
        return None
    return None


def read_daemon_checkpoint(graph_root: str | Path) -> DaemonCheckpointView:
    """Load bootstrap gate fields from the on-disk daemon checkpoint."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    path = checkpoint_path(root)
    bak_path = root / CHECKPOINT_BAK_FILENAME
    if not path.is_file() and not bak_path.is_file():
        return DaemonCheckpointView()

    recovery_source: Literal["primary", "backup"] = "primary"
    payload = _read_checkpoint_payload(path) if path.is_file() else None
    if payload is None and bak_path.is_file():
        logger.warning(
            "[METADATA CORRUPTION DETECTED] Primary checkpoint unreadable; "
            "attempting recovery from .bak backup."
        )
        payload = _read_checkpoint_payload(bak_path)
        recovery_source = "backup"
        if payload is not None and not is_graph_read_only():
            try:
                shutil.copy2(bak_path, path)
            except OSError:
                logger.exception(
                    "Recovered daemon checkpoint from backup but failed to restore primary at {}",
                    path,
                )

    if payload is None:
        logger.warning(
            "[METADATA CORRUPTION DETECTED] Checkpoint and backup both unreadable; "
            "using empty bootstrap gate defaults."
        )
        return DaemonCheckpointView(recovery_source="reset", reset_event=True)

    reason = payload.get("bootstrap_failed_reason")
    status = payload.get("status")
    return DaemonCheckpointView(
        bootstrap_complete=bool(payload.get("bootstrap_complete", False)),
        bootstrap_failed=bool(payload.get("bootstrap_failed", False)),
        bootstrap_failed_reason=(str(reason) if reason not in (None, "") else None),
        bootstrap_scanned=int(payload.get("bootstrap_scanned", 0)),
        bootstrap_total=int(payload.get("bootstrap_total", 0)),
        status=str(status) if status not in (None, "") else None,
        recovery_source=recovery_source,
    )


__all__ = [
    "CHECKPOINT_BAK_FILENAME",
    "CHECKPOINT_FILENAME",
    "DaemonCheckpointView",
    "checkpoint_path",
    "read_daemon_checkpoint",
]
