"""Phase 1 bootstrap semaphore for Tier-2 MCP/CLI agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .master_catalog import is_bootstrap_catalog_complete, master_index_page_path


@dataclass(frozen=True, slots=True)
class BootstrapStatusSnapshot:
    """Deterministic Phase 1 gate state for cognitive agents."""

    bootstrap_complete: bool
    bootstrap_failed: bool
    bootstrap_failed_reason: str | None
    bootstrap_scanned: int
    bootstrap_total: int
    master_index_present: bool
    catalog_complete: bool
    catalog_stale: bool
    phase1_in_progress: bool
    soft_gate_active: bool
    daemon_status: str | None
    checkpoint_recovery_source: Literal["missing", "primary", "backup", "reset"]
    checkpoint_reset_event: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "bootstrap_complete": self.bootstrap_complete,
            "bootstrap_failed": self.bootstrap_failed,
            "bootstrap_failed_reason": self.bootstrap_failed_reason,
            "bootstrap_scanned": self.bootstrap_scanned,
            "bootstrap_total": self.bootstrap_total,
            "master_index_present": self.master_index_present,
            "catalog_complete": self.catalog_complete,
            "catalog_stale": self.catalog_stale,
            "phase1_in_progress": self.phase1_in_progress,
            "soft_gate_active": self.soft_gate_active,
            "daemon_status": self.daemon_status,
            "checkpoint_recovery_source": self.checkpoint_recovery_source,
            "checkpoint_reset_event": self.checkpoint_reset_event,
        }


def collect_bootstrap_status(graph_root: str | Path) -> BootstrapStatusSnapshot:
    """Merge daemon checkpoint fields with on-disk catalog completeness."""
    root = Path(graph_root).expanduser().resolve(strict=False)
    from .daemon_checkpoint import read_daemon_checkpoint

    checkpoint = read_daemon_checkpoint(root)
    master_present = master_index_page_path(root).is_file()
    catalog_complete = is_bootstrap_catalog_complete(root) if master_present else False

    daemon_complete = checkpoint.bootstrap_complete
    catalog_stale = daemon_complete and not catalog_complete
    phase1_in_progress = (
        not daemon_complete
        and not checkpoint.bootstrap_failed
        and checkpoint.bootstrap_total > 0
        and checkpoint.bootstrap_scanned < checkpoint.bootstrap_total
    )

    effective_complete = catalog_complete or (
        daemon_complete and master_present and not catalog_stale
    )

    soft_gate_active = not effective_complete or checkpoint.bootstrap_failed or phase1_in_progress

    return BootstrapStatusSnapshot(
        bootstrap_complete=effective_complete,
        bootstrap_failed=checkpoint.bootstrap_failed,
        bootstrap_failed_reason=checkpoint.bootstrap_failed_reason,
        bootstrap_scanned=checkpoint.bootstrap_scanned,
        bootstrap_total=checkpoint.bootstrap_total,
        master_index_present=master_present,
        catalog_complete=catalog_complete,
        catalog_stale=catalog_stale,
        phase1_in_progress=phase1_in_progress,
        soft_gate_active=soft_gate_active,
        daemon_status=checkpoint.status,
        checkpoint_recovery_source=checkpoint.recovery_source,
        checkpoint_reset_event=checkpoint.reset_event,
    )


def format_bootstrap_status_markdown(graph_root: str | Path) -> str:
    """Return JSON envelope plus a one-line agent hint for MCP/CLI reads."""
    snapshot = collect_bootstrap_status(graph_root)
    payload = snapshot.to_dict()
    payload["ok"] = True
    payload["graph_root"] = str(Path(graph_root).expanduser().resolve(strict=False))

    if snapshot.soft_gate_active:
        hint = (
            "SOFT GATE ACTIVE: pause and present Local Daemon / Blind Search / Cloud Indexing "
            "options; wait for explicit authorization before blind search or cloud indexing."
        )
    else:
        hint = "GREEN: proceed with Master Index scan, then targeted reads."

    return f"{hint}\n\n```json\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n```\n"


__all__ = [
    "BootstrapStatusSnapshot",
    "collect_bootstrap_status",
    "format_bootstrap_status_markdown",
]
