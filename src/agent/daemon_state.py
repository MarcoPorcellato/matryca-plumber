"""Daemon checkpoint persistence — ledger models, load/save, and file-key normalization.

Single-responsibility slice of :mod:`maintenance_daemon` (issue #58). Orchestration
(``MaintenanceDaemon``, LLM cycles) stays in the parent module; this module owns the
on-disk ``.matryca_daemon_state.json`` contract only.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from loguru import logger

from ..graph.bootstrap_harvest import BootstrapHarvestStatus
from ..graph.graph_analytics import reconcile_telemetry_ledger
from ..graph.json_flock import cross_process_json_flock
from ..graph.path_sandbox import graph_relative_path_key, normalize_daemon_file_key
from ..graph.safety.write_policy import (
    GraphReadOnlyError,
    guard_graph_mutation,
    is_graph_read_only,
)
from ..utils.bounded_json import BoundedJsonError, read_bounded_json
from .journey_log import JourneyDayLedger
from .plumber_config import DEFAULT_LM_MODEL, resolve_llm_model_name

STATE_FILENAME = ".matryca_daemon_state.json"
STATE_TMP_FILENAME = f"{STATE_FILENAME}.tmp"
STATE_BAK_FILENAME = f"{STATE_FILENAME}.bak"

_FILE_STATUS_PRIORITY = {
    "processed": 5,
    "error": 4,
    "skipped": 3,
    "lock_backoff": 2,
    "pending": 1,
}
_LOCK_BACKOFF_INITIAL_S = 30.0
_LOCK_BACKOFF_MAX_S = 300.0

DaemonStatus = Literal["running", "idle", "stopped", "error"]
FileStatus = Literal["processed", "skipped", "error", "pending", "lock_backoff"]

BOOTSTRAP_RECENT_MAX = 30


@dataclass
class FileState:
    """Processing record for one markdown file."""

    mtime: float
    processed_at: str
    status: FileStatus = "processed"
    error: str | None = None
    lock_backoff_until: float | None = None
    lock_backoff_seconds: float | None = None


@dataclass
class BootstrapRecentEntry:
    """Recent Phase 1 catalog page for control-room pills."""

    harvest: BootstrapHarvestStatus
    processed_at: str


@dataclass
class DaemonState:
    """Persistent daemon checkpoint stored inside the graph root."""

    version: int = 1
    files: dict[str, FileState] = field(default_factory=dict)
    status: DaemonStatus = "idle"
    model: str = DEFAULT_LM_MODEL
    bootstrap_complete: bool = False
    bootstrap_failed: bool = False
    bootstrap_failed_reason: str | None = None
    bootstrap_scanned: int = 0
    bootstrap_total: int = 0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    current_cluster: str | None = None
    current_cluster_files_total: int = 0
    current_cluster_files_done: int = 0
    phase2_cognitive_total: int = 0
    phase2_cognitive_done: int = 0
    phase2_vault_baseline_total: int = 0
    phase2_cluster_file_in_flight: bool = False
    phase2_llm_turns: int = 0
    last_scan_at: str | None = None
    last_file: str | None = None
    ai_pages_created: int = 0
    ai_links_injected: int = 0
    ai_blocks_healed: int = 0
    hygiene_corrections: int = 0
    page_summaries_created: int = 0
    bootstrap_recent: dict[str, BootstrapRecentEntry] = field(default_factory=dict)
    journey_day: JourneyDayLedger = field(default_factory=JourneyDayLedger)

    def to_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "model": self.model,
            "bootstrap_complete": self.bootstrap_complete,
            "bootstrap_failed": self.bootstrap_failed,
            "bootstrap_failed_reason": self.bootstrap_failed_reason,
            "bootstrap_scanned": self.bootstrap_scanned,
            "bootstrap_total": self.bootstrap_total,
            "session_prompt_tokens": self.session_prompt_tokens,
            "session_completion_tokens": self.session_completion_tokens,
            "current_cluster": self.current_cluster,
            "current_cluster_files_total": self.current_cluster_files_total,
            "current_cluster_files_done": self.current_cluster_files_done,
            "phase2_cognitive_total": self.phase2_cognitive_total,
            "phase2_cognitive_done": self.phase2_cognitive_done,
            "phase2_vault_baseline_total": self.phase2_vault_baseline_total,
            "phase2_cluster_file_in_flight": self.phase2_cluster_file_in_flight,
            "phase2_llm_turns": self.phase2_llm_turns,
            "last_scan_at": self.last_scan_at,
            "last_file": self.last_file,
            "ai_pages_created": self.ai_pages_created,
            "ai_links_injected": self.ai_links_injected,
            "ai_blocks_healed": self.ai_blocks_healed,
            "hygiene_corrections": self.hygiene_corrections,
            "page_summaries_created": self.page_summaries_created,
            "bootstrap_recent": {
                path: {
                    "harvest": rec.harvest,
                    "processed_at": rec.processed_at,
                }
                for path, rec in self.bootstrap_recent.items()
            },
            "journey_day": self.journey_day.to_json(),
            "files": {
                path: {
                    "mtime": rec.mtime,
                    "processed_at": rec.processed_at,
                    "status": rec.status,
                    "error": rec.error,
                    "lock_backoff_until": rec.lock_backoff_until,
                    "lock_backoff_seconds": rec.lock_backoff_seconds,
                }
                for path, rec in self.files.items()
            },
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> DaemonState:
        files: dict[str, FileState] = {}
        raw_files = payload.get("files", {})
        if isinstance(raw_files, dict):
            for path, rec in raw_files.items():
                if not isinstance(rec, dict):
                    continue
                backoff_until = rec.get("lock_backoff_until")
                backoff_seconds = rec.get("lock_backoff_seconds")
                files[str(path)] = FileState(
                    mtime=float(rec.get("mtime", 0.0)),
                    processed_at=str(rec.get("processed_at", "")),
                    status=cast(FileStatus, str(rec.get("status", "processed"))),
                    error=rec.get("error") if rec.get("error") is not None else None,
                    lock_backoff_until=(
                        float(backoff_until) if backoff_until is not None else None
                    ),
                    lock_backoff_seconds=(
                        float(backoff_seconds) if backoff_seconds is not None else None
                    ),
                )
        return cls(
            version=int(payload.get("version", 1)),
            files=files,
            status=cast(DaemonStatus, str(payload.get("status", "idle"))),
            model=str(payload.get("model", DEFAULT_LM_MODEL)),
            bootstrap_complete=bool(payload.get("bootstrap_complete", False)),
            bootstrap_failed=bool(payload.get("bootstrap_failed", False)),
            bootstrap_failed_reason=(
                str(payload["bootstrap_failed_reason"])
                if payload.get("bootstrap_failed_reason") not in (None, "")
                else None
            ),
            bootstrap_scanned=int(payload.get("bootstrap_scanned", 0)),
            bootstrap_total=int(payload.get("bootstrap_total", 0)),
            session_prompt_tokens=int(payload.get("session_prompt_tokens", 0)),
            session_completion_tokens=int(payload.get("session_completion_tokens", 0)),
            current_cluster=(
                str(payload["current_cluster"])
                if payload.get("current_cluster") not in (None, "")
                else None
            ),
            current_cluster_files_total=int(payload.get("current_cluster_files_total", 0)),
            current_cluster_files_done=int(payload.get("current_cluster_files_done", 0)),
            phase2_cognitive_total=int(payload.get("phase2_cognitive_total", 0)),
            phase2_cognitive_done=int(payload.get("phase2_cognitive_done", 0)),
            phase2_vault_baseline_total=int(payload.get("phase2_vault_baseline_total", 0)),
            phase2_cluster_file_in_flight=bool(payload.get("phase2_cluster_file_in_flight", False)),
            phase2_llm_turns=int(payload.get("phase2_llm_turns", 0)),
            last_scan_at=payload.get("last_scan_at"),
            last_file=payload.get("last_file"),
            ai_pages_created=int(payload.get("ai_pages_created", 0)),
            ai_links_injected=int(
                payload.get("ai_links_injected", payload.get("links_backpropagated", 0))
            ),
            ai_blocks_healed=int(payload.get("ai_blocks_healed", payload.get("blocks_healed", 0))),
            hygiene_corrections=int(payload.get("hygiene_corrections", 0)),
            page_summaries_created=int(payload.get("page_summaries_created", 0)),
            bootstrap_recent=_bootstrap_recent_from_json(payload.get("bootstrap_recent")),
            journey_day=JourneyDayLedger.from_json(payload.get("journey_day")),
        )


def _bootstrap_recent_from_json(
    raw: object,
) -> dict[str, BootstrapRecentEntry]:
    if not isinstance(raw, dict):
        return {}
    recent: dict[str, BootstrapRecentEntry] = {}
    for path, rec in raw.items():
        if not isinstance(rec, dict):
            continue
        harvest = str(rec.get("harvest", ""))
        if harvest not in ("regex", "llm", "skipped", "error"):
            continue
        recent[str(path)] = BootstrapRecentEntry(
            harvest=cast(BootstrapHarvestStatus, harvest),
            processed_at=str(rec.get("processed_at", "")),
        )
    return recent


def upsert_bootstrap_recent(
    state: DaemonState,
    path_key: str,
    harvest: BootstrapHarvestStatus,
) -> None:
    """Record one cataloged page; evict oldest entries beyond ``BOOTSTRAP_RECENT_MAX``."""
    now = datetime.now(tz=UTC).isoformat()
    state.bootstrap_recent[path_key] = BootstrapRecentEntry(harvest=harvest, processed_at=now)
    if len(state.bootstrap_recent) <= BOOTSTRAP_RECENT_MAX:
        return
    oldest_key = min(
        state.bootstrap_recent,
        key=lambda key: state.bootstrap_recent[key].processed_at,
    )
    del state.bootstrap_recent[oldest_key]


def record_bootstrap_harvest_impact(
    state: DaemonState,
    harvest: BootstrapHarvestStatus | None,
) -> None:
    """Increment session ledger when a catalog summary is written."""
    if harvest in ("regex", "llm"):
        state.page_summaries_created += 1


def lock_backoff_active(rec: FileState) -> bool:
    if rec.status != "lock_backoff":
        return False
    if rec.lock_backoff_until is None:
        return False
    return time.time() < rec.lock_backoff_until


def _next_lock_backoff_seconds(rec: FileState | None) -> float:
    if rec is None or rec.status != "lock_backoff":
        return _LOCK_BACKOFF_INITIAL_S
    previous = rec.lock_backoff_seconds or _LOCK_BACKOFF_INITIAL_S
    return min(previous * 2.0, _LOCK_BACKOFF_MAX_S)


def record_page_lock_backoff(
    state: DaemonState,
    *,
    key: str,
    mtime: float,
    message: str,
    prior: FileState | None,
) -> None:
    if prior is not None and prior.status == "processed":
        return
    interval = _next_lock_backoff_seconds(prior)
    state.files[key] = FileState(
        mtime=mtime,
        processed_at=datetime.now(tz=UTC).isoformat(),
        status="lock_backoff",
        error=message,
        lock_backoff_until=time.time() + interval,
        lock_backoff_seconds=interval,
    )


def _merge_file_state(existing: FileState, incoming: FileState) -> FileState:
    """Merge duplicate ledger keys preferring higher-status, newer records."""
    existing_prio = _FILE_STATUS_PRIORITY.get(existing.status, 0)
    incoming_prio = _FILE_STATUS_PRIORITY.get(incoming.status, 0)
    if incoming_prio > existing_prio:
        return incoming
    if incoming_prio < existing_prio:
        return existing
    if incoming.mtime > existing.mtime:
        return incoming
    if incoming.mtime < existing.mtime:
        return existing
    return incoming if incoming.processed_at >= existing.processed_at else existing


def normalize_daemon_state_file_keys(graph_root: Path, state: DaemonState) -> bool:
    """Rewrite legacy absolute file keys to graph-relative POSIX paths."""
    if not state.files:
        return False
    migrated: dict[str, FileState] = {}
    changed = False
    for key, rec in state.files.items():
        new_key = normalize_daemon_file_key(graph_root, key)
        if not new_key:
            logger.warning(
                "Dropping unmapped or invalid ledger key during migration: {}",
                key,
            )
            changed = True
            continue
        if new_key != key:
            changed = True
        if new_key in migrated:
            migrated[new_key] = _merge_file_state(migrated[new_key], rec)
            changed = True
        else:
            migrated[new_key] = rec
    if changed:
        state.files = migrated
    return changed


def daemon_file_key(graph_root: Path, path: Path) -> str:
    return graph_relative_path_key(path, graph_root)


def lookup_file_state(
    graph_root: Path,
    state: DaemonState,
    path: Path,
) -> tuple[str, FileState | None]:
    """Resolve file ledger entry using graph-relative keys with legacy fallback."""
    key = daemon_file_key(graph_root, path)
    rec = state.files.get(key)
    if rec is not None:
        return key, rec
    legacy = str(path.resolve())
    return key, state.files.get(legacy)


def heal_daemon_state_ledger(graph_root: Path, state: DaemonState) -> bool:
    """Clamp ledger counters when live graph totals fall below persisted AI impact."""
    snapshot = reconcile_telemetry_ledger(
        graph_root,
        ai_links_injected=state.ai_links_injected,
        ai_blocks_healed=state.ai_blocks_healed,
        ai_pages_created=state.ai_pages_created,
        page_summaries_created=state.page_summaries_created,
    )
    if not snapshot.healed:
        return False
    state.ai_links_injected = snapshot.ai_links_injected
    state.ai_blocks_healed = snapshot.ai_blocks_healed
    state.ai_pages_created = snapshot.ai_pages_created
    state.page_summaries_created = snapshot.page_summaries_created
    return True


def resolve_graph_root() -> Path:
    """Return validated ``LOGSEQ_GRAPH_PATH`` (must contain ``pages/``)."""
    from ..graph.graph_path_validate import validate_logseq_graph_path

    raw = os.environ.get("LOGSEQ_GRAPH_PATH", "").strip()
    if not raw:
        msg = "LOGSEQ_GRAPH_PATH must be set for the Matryca Plumber daemon"
        raise ValueError(msg)
    return validate_logseq_graph_path(raw)


def state_path(graph_root: Path) -> Path:
    return graph_root / STATE_FILENAME


def state_bak_path(graph_root: Path) -> Path:
    return graph_root / STATE_BAK_FILENAME


def sync_daemon_state_from_env(state: DaemonState) -> DaemonState:
    """Ensure persisted daemon state reflects the current ``LLM_MODEL_NAME`` env value."""
    state.model = resolve_llm_model_name()
    return state


def _read_daemon_state_payload(path: Path) -> dict[str, Any] | None:
    """Load JSON payload from disk, retrying once on transient empty or malformed reads."""
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


def load_daemon_state(graph_root: Path) -> DaemonState:
    path = state_path(graph_root)
    bak_path = state_bak_path(graph_root)
    if not path.is_file() and not bak_path.is_file():
        return sync_daemon_state_from_env(DaemonState())

    payload = _read_daemon_state_payload(path) if path.is_file() else None
    if payload is None and bak_path.is_file():
        logger.warning(
            "[METADATA CORRUPTION DETECTED] Primary checkpoint unreadable; "
            "attempting recovery from .bak backup."
        )
        payload = _read_daemon_state_payload(bak_path)
        if payload is not None and not is_graph_read_only():
            try:
                shutil.copy2(bak_path, path)
            except OSError:
                logger.exception(
                    "Recovered daemon state from backup but failed to restore primary at {}",
                    path,
                )

    if payload is None:
        logger.warning(
            "[METADATA CORRUPTION DETECTED] Checkpoint and backup both unreadable; "
            "initializing a fresh instance."
        )
        return sync_daemon_state_from_env(DaemonState())
    state = sync_daemon_state_from_env(DaemonState.from_json(payload))
    if normalize_daemon_state_file_keys(graph_root, state):
        logger.info("Migrated daemon file ledger keys to graph-relative POSIX paths")
    return state


def save_daemon_state(graph_root: Path, state: DaemonState) -> None:
    """Persist daemon state via POSIX atomic write-and-replace under a cross-process flock."""
    path = state_path(graph_root)
    try:
        guard_graph_mutation(graph_root, path, operation="save_daemon_state")
    except GraphReadOnlyError:
        logger.debug("Skipping graph-local daemon state save under read-only policy")
        return
    normalize_daemon_state_file_keys(graph_root, state)
    payload = json.dumps(state.to_json(), indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with cross_process_json_flock(path):
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        committed = False
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(tmp_path), str(path))
            committed = True
            bak_path = state_bak_path(graph_root)
            try:
                shutil.copy2(path, bak_path)
            except OSError:
                logger.exception(
                    "Daemon state primary write succeeded but backup copy failed for {}",
                    bak_path,
                )
        finally:
            if not committed:
                tmp_path.unlink(missing_ok=True)


# Backward-compatible private aliases for in-repo call sites and tests.
_lock_backoff_active = lock_backoff_active
_record_page_lock_backoff = record_page_lock_backoff
_daemon_file_key = daemon_file_key
_lookup_file_state = lookup_file_state


__all__ = [
    "BOOTSTRAP_RECENT_MAX",
    "BootstrapRecentEntry",
    "DaemonState",
    "DaemonStatus",
    "FileState",
    "FileStatus",
    "STATE_BAK_FILENAME",
    "STATE_FILENAME",
    "STATE_TMP_FILENAME",
    "daemon_file_key",
    "heal_daemon_state_ledger",
    "load_daemon_state",
    "lock_backoff_active",
    "lookup_file_state",
    "normalize_daemon_state_file_keys",
    "record_bootstrap_harvest_impact",
    "record_page_lock_backoff",
    "resolve_graph_root",
    "save_daemon_state",
    "state_bak_path",
    "state_path",
    "sync_daemon_state_from_env",
    "upsert_bootstrap_recent",
]
