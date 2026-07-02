"""Matryca Plumber Maintenance Daemon — progressive local LLM graph indexing."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from loguru import logger

from ..config import load_matryca_wiki_config
from ..daemon.ast_cache import get_graph_ast_cache
from ..daemon.file_watcher import FileEventKind, GraphFileWatcher
from ..graph.alias_index import (
    AliasIndex,
)
from ..graph.bootstrap_harvest import (
    BootstrapHarvestStatus,
    run_bootstrap_harvest,
    run_incremental_catalog_refresh,
)
from ..graph.concurrency_probe import probe_concurrency_capability
from ..graph.generational_cache import (
    cached_build_alias_index,
    gc_generational_alias_cache,
)
from ..graph.insights_engine import (
    run_graph_insights_engine,
)
from ..graph.link_verification import (
    link_verify_enabled,
    register_page_links_from_path,
)
from ..graph.master_catalog import (
    SEMANTIC_INDEX_HEADER,
    extract_catalog_fields_from_content,
    is_bootstrap_catalog_complete,
    load_master_catalog,
    master_index_page_path,
)
from ..graph.page_write_lock import (
    clear_page_write_locks,
    sweep_matryca_lock_sidecars,
)
from ..graph.path_sandbox import (
    graph_relative_path_key,
    read_graph_file_text,
)
from ..graph.semantic_clustering import (
    CLUSTER_IDS_WITHOUT_FOCUS,
    JOURNAL_CLUSTER_ID,
    format_cluster_neighborhood,
    load_or_compute_semantic_clusters,
)
from ..utils.logging_config import configure_loguru
from ..utils.runtime_bootstrap import prepare_matryca_runtime
from ..utils.token_logger import TokenLogger
from . import daemon_process_lock as _daemon_process_lock
from . import daemon_state as _daemon_state
from .control_room_progress import refresh_phase2_cognitive_totals
from .cooperative_yield import (
    bootstrap_checkpoint_every,
    bootstrap_pill_checkpoint_every,
    telemetry_heartbeat_seconds,
)
from .daemon_llm_client import InstructorLLMClient, LLMClient
from .daemon_llm_cycle import (
    DaemonLLMCycleHost,
    finalize_link_and_journey_pass,
    process_llm_cycle_file,
    quarantine_structural_lint,
    record_daemon_impact,
    settle_journal_structural_cycle_file,
    settle_journey_journal_in_state,
    try_fast_track_cycle_file,
)
from .daemon_page_queue import (
    ScanMetrics,
    clear_phase1_error_backoff,
    compute_phase2_progress_metrics,
    compute_scan_metrics,
    list_pending_files,
    page_needs_phase2_cognitive,
    prune_stale_daemon_file_entries,
)
from .daemon_process_lock import (
    DAEMON_LOCK_FILENAME,
    DEFAULT_STOP_GRACE_SECONDS,
    DEFAULT_STOP_SIGKILL_AFTER_SECONDS,
    PID_FILENAME,
    _release_daemon_process_lock,
    _try_acquire_daemon_process_lock,
    bind_daemon_process_lock_fd,
    is_plumber_process,
    is_process_alive,
    read_pid_file,
    register_bootstrap_shutdown_handlers,
    remove_pid_file,
    stop_daemon,
    write_pid_file,
)
from .daemon_semantic_write import (
    STRUCTURAL_LINT_HEADER,
    CorrectionOutcome,
    LintType,
    SemanticCrossRef,
    SemanticIndexResult,
    SemanticLintCorrection,
    _enumerate_blocks_for_prompt,
    _page_title_from_path,
    append_semantic_index,
    append_structural_lint_warning,
    apply_semantic_corrections_to_lines,
    apply_semantic_page_result,
    run_dual_embedding_after_semantic_write,
)
from .daemon_state import (
    DaemonState,
    FileState,
    _record_page_lock_backoff,
    heal_daemon_state_ledger,
    load_daemon_state,
    normalize_daemon_state_file_keys,
    record_bootstrap_harvest_impact,
    resolve_graph_root,
    save_daemon_state,
    sync_daemon_state_from_env,
    upsert_bootstrap_recent,
)
from .llm_client import (
    LLMResponseError,
    StructuredOutputExhaustedError,
    ThermalProfile,
)
from .memory_budget import log_snapshot, maybe_release_after_cycle, release_phase1_memory
from .plumber_config import (
    DEFAULT_LLM_MODEL_NAME,
    DEFAULT_LM_BASE_URL,
    PlumberLintConfig,
    bootstrap_phase_lint_config,
    load_plumber_lint_config,
    reload_plumber_dotenv,
)
from .plumber_modules._shared import is_journal_page_path
from .plumber_modules.semantic_cache_router import purge_expired_semantic_cache
from .process_priority import apply_cpu_sandbox, apply_plumber_priority, resolve_cpu_sandbox_config

# Backward-compatible re-exports for CLI/tests (issue #58 slice).
pid_path = _daemon_process_lock.pid_path
state_path = _daemon_state.state_path
state_bak_path = _daemon_state.state_bak_path
daemon_lock_path = _daemon_process_lock.daemon_lock_path
_fcntl = _daemon_process_lock._fcntl
_register_bootstrap_shutdown_handlers = register_bootstrap_shutdown_handlers

SHUTDOWN_INFLIGHT_TIMEOUT_SECONDS = 120.0
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = DEFAULT_LLM_MODEL_NAME  # backward-compatible alias for CLI/TUI
DEFAULT_POLL_SECONDS = 30.0


class MaintenanceDaemon:
    """Long-polling daemon that indexes Logseq pages with a local LLM."""

    def __init__(
        self,
        graph_root: Path,
        *,
        llm_client: LLMClient | None = None,
        token_logger: TokenLogger | None = None,
        poll_seconds: float | None = None,
        max_files_per_cycle: int = 1,
    ) -> None:
        self.graph_root = graph_root
        self.token_logger = token_logger or TokenLogger()
        self.llm_client = llm_client or InstructorLLMClient(token_logger=self.token_logger)
        self.poll_seconds = poll_seconds or float(
            os.environ.get("MATRYCA_PLUMBER_POLL_SECONDS", str(DEFAULT_POLL_SECONDS)),
        )
        self.max_files_per_cycle = max_files_per_cycle
        self._stop_requested = False
        self._shutdown_in_progress = False
        self._shutdown_event = threading.Event()
        self._cycle_wake = threading.Event()
        self._file_watcher: GraphFileWatcher | None = None
        self._inflight_writes = threading.Condition()
        self._active_write_count = 0
        self._state_persist_failed = False
        self._telemetry_lock = threading.Lock()
        self._telemetry_dirty = False
        self._last_heartbeat_monotonic = 0.0
        self._vault_refresh_counter = 0
        self.bootstrap_complete = False
        self.bootstrap_failed = False
        self._ensure_shared_token_logger()
        capability = probe_concurrency_capability()
        if capability.mode == "full":
            logger.debug("Concurrency: {}", capability.message)
        elif capability.degradation_allowed:
            logger.info("Concurrency: {}", capability.message)
        else:
            logger.warning("Concurrency: {}", capability.message)

    def _ensure_shared_token_logger(self) -> None:
        """Bind the LLM client to the daemon's central token logger."""
        if isinstance(self.llm_client, InstructorLLMClient):
            self.llm_client.token_logger = self.token_logger
            self.llm_client.thermal_stop_event = self._shutdown_event

    def _absorb_token_logger_delta(
        self,
        other: TokenLogger,
        *,
        baseline_prompt: int,
        baseline_completion: int,
    ) -> None:
        """Merge token deltas from a submodule logger into the central session counters."""
        if other is self.token_logger:
            return
        delta_prompt = other.session_prompt_tokens - baseline_prompt
        delta_completion = other.session_completion_tokens - baseline_completion
        if delta_prompt:
            self.token_logger.session_prompt_tokens += delta_prompt
        if delta_completion:
            self.token_logger.session_completion_tokens += delta_completion

    def _hydrate_token_logger_from_state(self, state: DaemonState) -> None:
        """Restore in-memory session counters from the last persisted checkpoint."""
        self.token_logger.session_prompt_tokens = max(
            self.token_logger.session_prompt_tokens,
            state.session_prompt_tokens,
        )
        self.token_logger.session_completion_tokens = max(
            self.token_logger.session_completion_tokens,
            state.session_completion_tokens,
        )
        log_prompt, log_completion = self.token_logger.session_token_totals_from_log()
        self.token_logger.session_prompt_tokens = max(
            self.token_logger.session_prompt_tokens,
            log_prompt,
        )
        self.token_logger.session_completion_tokens = max(
            self.token_logger.session_completion_tokens,
            log_completion,
        )

    def _hydrate_bootstrap_phase(self, state: DaemonState) -> None:
        """Restore Phase 2 readiness from persisted state or a complete on-disk catalog."""
        self.bootstrap_failed = bool(state.bootstrap_failed)
        if state.bootstrap_complete or is_bootstrap_catalog_complete(self.graph_root):
            self.bootstrap_complete = True
            state.bootstrap_complete = True
            state.bootstrap_failed = False
            state.bootstrap_failed_reason = None
            self.bootstrap_failed = False
            if state.phase2_vault_baseline_total <= 0 and state.phase2_cognitive_total > 0:
                state.phase2_vault_baseline_total = state.phase2_cognitive_total
        elif not self.bootstrap_complete:
            self.bootstrap_complete = False

    def _persist_bootstrap_failure(self, state: DaemonState, message: str) -> None:
        """Record Phase 1 failure and block Phase 2 LLM until bootstrap succeeds."""
        self.bootstrap_complete = False
        self.bootstrap_failed = True
        state.bootstrap_complete = False
        state.bootstrap_failed = True
        state.bootstrap_failed_reason = message
        state.status = "idle"
        self._sync_live_telemetry(state)
        save_daemon_state(self.graph_root, state)
        logger.error("Bootstrap failed: {}", message)

    def _persist_bootstrap_complete(self, state: DaemonState) -> None:
        self.bootstrap_failed = False
        self.bootstrap_complete = True
        state.bootstrap_failed = False
        state.bootstrap_failed_reason = None
        state.bootstrap_complete = True
        state.bootstrap_scanned = 0
        state.bootstrap_total = 0
        state.bootstrap_recent = {}
        try:
            refresh_phase2_cognitive_totals(self.graph_root, state)
        except OSError as exc:
            logger.warning("Phase 2 progress totals skipped after bootstrap: {}", exc)
        if state.phase2_vault_baseline_total <= 0 and state.phase2_cognitive_total > 0:
            state.phase2_vault_baseline_total = state.phase2_cognitive_total
        self._sync_live_telemetry(state)
        save_daemon_state(self.graph_root, state)

    def _effective_lint_config(self) -> PlumberLintConfig:
        """Return env lint config, or an all-disabled override during Phase 1."""
        if not self.bootstrap_complete:
            return bootstrap_phase_lint_config()
        return load_plumber_lint_config()

    def _compiled_alias_index(self) -> AliasIndex:
        return cached_build_alias_index(self.graph_root)

    def _register_daemon_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers before the polling loop starts."""
        signal.signal(signal.SIGTERM, self._handle_daemon_graceful_shutdown)
        signal.signal(signal.SIGINT, self._handle_daemon_graceful_shutdown)

    def _handle_daemon_graceful_shutdown(self, signum: int, _frame: object) -> None:
        """Request cooperative shutdown; the main loop performs flush and cleanup."""
        if self._shutdown_in_progress:
            return
        self._shutdown_in_progress = True
        self._stop_requested = True
        self._shutdown_event.set()

        try:
            self.token_logger.log_daemon_shutdown(signum)
        except OSError:
            logger.exception("Daemon shutdown token log failed during graceful shutdown")

    def _begin_phase2_write(self) -> None:
        with self._inflight_writes:
            self._active_write_count += 1

    def _end_phase2_write(self) -> None:
        with self._inflight_writes:
            self._active_write_count -= 1
            self._inflight_writes.notify_all()

    def _wait_for_inflight_writes(
        self,
        *,
        timeout_s: float = SHUTDOWN_INFLIGHT_TIMEOUT_SECONDS,
    ) -> None:
        """Block until active Phase-2 writes finish or ``timeout_s`` elapses."""
        deadline = time.monotonic() + timeout_s
        with self._inflight_writes:
            while self._active_write_count > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(
                        "Shutdown timed out waiting for {} in-flight Phase-2 write(s)",
                        self._active_write_count,
                    )
                    return
                self._inflight_writes.wait(timeout=remaining)

    def _finalize_graceful_shutdown(self, state: DaemonState | None = None) -> None:
        """Flush ledger telemetry and release daemon resources after the loop exits."""
        self._wait_for_inflight_writes()

        try:
            load_master_catalog(self.graph_root).save()
        except OSError:
            logger.exception("Final master catalog save failed during graceful shutdown")

        checkpoint = state or load_daemon_state(self.graph_root)
        checkpoint.status = "stopped"
        self._sync_live_telemetry(checkpoint)
        try:
            save_daemon_state(self.graph_root, checkpoint)
        except OSError:
            logger.exception("Final daemon state save failed during graceful shutdown")

        self._stop_file_watcher()
        remove_pid_file(self.graph_root)
        _release_daemon_process_lock(self.graph_root)
        clear_page_write_locks()
        sweep_matryca_lock_sidecars(self.graph_root)

    def _on_watchdog_change(self, path: Path, kind: FileEventKind) -> None:
        """Refresh AST cache and wake the duty cycle after debounced vault edits."""
        get_graph_ast_cache(self.graph_root).apply_file_event(path, kind)
        from ..daemon.config_layer import refresh_identity_config

        refresh_identity_config(self.graph_root, path)
        if kind == "deleted" and link_verify_enabled():
            try:
                register_page_links_from_path(self.graph_root, path)
            except OSError:
                logger.exception("Link registry update failed for deleted page {}", path)
        self._cycle_wake.set()

    def _start_file_watcher(self) -> None:
        if self._file_watcher is not None:
            return
        watcher = GraphFileWatcher(
            self.graph_root,
            on_debounced_change=self._on_watchdog_change,
        )
        watcher.start()
        self._file_watcher = watcher

    def _stop_file_watcher(self) -> None:
        if self._file_watcher is not None:
            self._file_watcher.stop()
            self._file_watcher = None

    def _sync_runtime_config(self, state: DaemonState) -> DaemonState:
        """Align LLM client and persisted state with the active environment block."""
        reload_plumber_dotenv(override=True)
        self._ensure_shared_token_logger()
        if isinstance(self.llm_client, InstructorLLMClient):
            self.llm_client.refresh_config()
            self.llm_client.bind_lint_config(self._effective_lint_config())
        return sync_daemon_state_from_env(state)

    def request_stop(self) -> None:
        self._stop_requested = True
        self._shutdown_event.set()

    def run_bootstrap_pipeline(self, state: DaemonState | None = None) -> None:
        """Phase 1 bootstrap harvest (read/append only) before Phase 2 polling."""
        if self.bootstrap_complete:
            return

        checkpoint = state or load_daemon_state(self.graph_root)
        self._hydrate_bootstrap_phase(checkpoint)
        if self.bootstrap_complete:
            return

        checkpoint.status = "running"
        self._sync_live_telemetry(checkpoint, mark_running=True)
        save_daemon_state(self.graph_root, checkpoint)

        def _on_page_cataloged(
            scanned: int,
            total: int,
            last_path: Path | None,
            harvest_status: BootstrapHarvestStatus | None = None,
        ) -> None:
            checkpoint.bootstrap_scanned = scanned
            checkpoint.bootstrap_total = total
            if last_path is None:
                return
            key = graph_relative_path_key(last_path, self.graph_root)
            checkpoint.last_file = key
            if harvest_status is not None:
                upsert_bootstrap_recent(checkpoint, key, harvest_status)
            record_bootstrap_harvest_impact(checkpoint, harvest_status)
            self._mark_telemetry_dirty()
            pill_interval = bootstrap_pill_checkpoint_every()
            if scanned % pill_interval == 0 or scanned % bootstrap_checkpoint_every() == 0:
                checkpoint.status = "running"
                self._persist_daemon_state(checkpoint, mark_running=True)

        def _persist_bootstrap_progress(
            scanned: int,
            total: int,
            last_path: Path | None,
            harvest_status: BootstrapHarvestStatus | None = None,
        ) -> None:
            del last_path, harvest_status
            checkpoint.bootstrap_scanned = scanned
            checkpoint.bootstrap_total = total
            checkpoint.status = "running"
            self._persist_daemon_state(checkpoint, mark_running=True)

        max_attempts = 3
        backoff_s = 1.0
        last_exc: Exception | None = None
        metrics = None
        for attempt in range(1, max_attempts + 1):
            try:
                metrics = run_bootstrap_harvest(
                    self.graph_root,
                    llm=self.llm_client,
                    incremental=False,
                    rebuild_index=True,
                    phase1_strict=True,
                    on_progress=_persist_bootstrap_progress,
                    on_page_cataloged=_on_page_cataloged,
                    should_stop=lambda: self._stop_requested,
                    stop_event=self._shutdown_event,
                )
                break
            except Exception as exc:  # noqa: BLE001 - bootstrap must not block daemon start
                last_exc = exc
                if attempt >= max_attempts:
                    msg = f"Bootstrap harvest failed after {max_attempts} attempts: {exc}"
                    self.token_logger.log_structural_lint_warning(
                        target_file=self.graph_root,
                        message=msg,
                        malformed_refs=[],
                    )
                    self._persist_bootstrap_failure(checkpoint, msg)
                    return
                time.sleep(backoff_s)
                backoff_s *= 2.0

        if metrics is None:
            if last_exc is not None:
                msg = f"Bootstrap harvest failed: {last_exc}"
                self.token_logger.log_structural_lint_warning(
                    target_file=self.graph_root,
                    message=msg,
                    malformed_refs=[],
                )
                self._persist_bootstrap_failure(checkpoint, msg)
            return

        if self._stop_requested:
            checkpoint.status = "stopped"
            self._sync_live_telemetry(checkpoint)
            save_daemon_state(self.graph_root, checkpoint)
            return

        master_index = master_index_page_path(self.graph_root)
        if not master_index.is_file() or metrics.files_created != 0:
            msg = (
                "Bootstrap Phase 1 incomplete: master index missing or unexpected "
                f"concept pages created (files_created={metrics.files_created})."
            )
            self.token_logger.log_structural_lint_warning(
                target_file=self.graph_root,
                message=msg,
                malformed_refs=[],
            )
            self._persist_bootstrap_failure(checkpoint, msg)
            return

        self.bootstrap_complete = True
        self._persist_bootstrap_complete(checkpoint)
        checkpoint.status = "running"
        self._persist_daemon_state(checkpoint, mark_running=True)
        try:
            load_or_compute_semantic_clusters(self.graph_root)
        except Exception as exc:  # noqa: BLE001 - deferral must not block daemon
            logger.warning("Semantic cluster precompute after bootstrap skipped: {}", exc)
        self._maybe_heartbeat_checkpoint(checkpoint, force=True)
        try:
            release_phase1_memory(self.graph_root)
            log_snapshot(label="post_bootstrap_teardown")
        except Exception as exc:  # noqa: BLE001 - teardown must not block Phase 2
            logger.warning("Post-bootstrap memory release skipped: {}", exc)
        self._maybe_heartbeat_checkpoint(checkpoint, force=True)
        self._run_phase2_graph_insights()
        self._maybe_heartbeat_checkpoint(checkpoint, force=True)

    def _run_phase2_graph_insights(self) -> None:
        """Run graph insights after Phase 1 completes (Phase 2 entry)."""
        try:
            run_graph_insights_engine(self.graph_root, llm=self.llm_client)
        except Exception as exc:  # noqa: BLE001 - insights must not block daemon start
            self.token_logger.log_structural_lint_warning(
                target_file=self.graph_root,
                message=f"Graph insights engine failed: {exc}",
                malformed_refs=[],
            )

    def refresh_catalog_if_stale(self) -> None:
        """Incrementally sync catalog rows when page mtimes change."""
        try:
            run_incremental_catalog_refresh(self.graph_root, llm=self.llm_client)
        except Exception as exc:  # noqa: BLE001 - never abort daemon cycle
            self.token_logger.log_structural_lint_warning(
                target_file=self.graph_root,
                message=f"Incremental catalog refresh failed: {exc}",
                malformed_refs=[],
            )

    def _prune_stale_catalog_entries(self) -> None:
        """Drop ghost catalog rows and purge warm alias cache entries after each scan."""
        try:
            catalog = load_master_catalog(self.graph_root)
            pruned = catalog.prune_missing_pages()
            alias_purged = gc_generational_alias_cache(self.graph_root)
            if pruned > 0:
                catalog.save(replace=True)
            if pruned > 0 or alias_purged > 0:
                logger.debug(
                    "Catalog GC pruned {} catalog row(s) and {} alias cache row(s)",
                    pruned,
                    alias_purged,
                )
        except Exception as exc:  # noqa: BLE001 - never abort daemon cycle
            self.token_logger.log_structural_lint_warning(
                target_file=self.graph_root,
                message=f"Catalog prune failed: {exc}",
                malformed_refs=[],
            )

    def _sync_catalog_after_page_write(self, path: Path, title: str) -> None:
        """Upsert catalog row from on-disk semantic index immediately after a page write."""
        try:
            new_text = read_graph_file_text(path, self.graph_root, errors="replace")
            mtime = path.stat().st_mtime_ns
        except OSError as exc:
            self.token_logger.log_structural_lint_warning(
                target_file=path,
                message=f"Catalog sync read failed for {title}: {exc}",
                malformed_refs=[],
            )
            return

        extracted = extract_catalog_fields_from_content(new_text)
        if extracted is None:
            return

        catalog = load_master_catalog(self.graph_root)
        extracted.last_mtime = mtime
        existing = catalog.get(title)
        if existing is not None:
            extracted.orphan = existing.orphan
        catalog.upsert(title, extracted)
        catalog.save()

    def _use_semantic_cluster_cycle(self, lint_config: PlumberLintConfig) -> bool:
        """Phase 2 cluster isolation when cognitive routing modules are active."""
        return self.bootstrap_complete and (
            lint_config.semantic_routing or lint_config.backpropagate_links
        )

    def _group_pending_by_cluster(self, pending: list[Path]) -> list[tuple[str, list[Path]]]:
        """Order pending files into semantic cluster execution blocks."""
        clusters = load_or_compute_semantic_clusters(self.graph_root)
        title_to_cluster: dict[str, str] = {}
        for cluster_id, titles in clusters.items():
            for title in titles:
                title_to_cluster[title] = cluster_id

        journal_paths: list[Path] = []
        by_cluster: dict[str, list[Path]] = {}
        unclustered: list[Path] = []
        for path in pending:
            if is_journal_page_path(self.graph_root, path):
                journal_paths.append(path)
                continue
            title = _page_title_from_path(self.graph_root, path)
            mapped_cluster = title_to_cluster.get(title)
            if mapped_cluster is None:
                unclustered.append(path)
                continue
            by_cluster.setdefault(mapped_cluster, []).append(path)

        groups: list[tuple[str, list[Path]]] = [
            (cluster_id, by_cluster[cluster_id]) for cluster_id in sorted(by_cluster)
        ]
        if unclustered:
            groups.append(("unclustered", unclustered))
        if journal_paths:
            groups.append((JOURNAL_CLUSTER_ID, journal_paths))
        return groups

    def _begin_cluster_context(self, cluster_id: str, cluster_paths: list[Path]) -> None:
        """Hard-reset LLM history and inject neighborhood map for one cluster."""
        if not isinstance(self.llm_client, InstructorLLMClient):
            return
        catalog = load_master_catalog(self.graph_root)
        clusters = load_or_compute_semantic_clusters(self.graph_root)
        cluster_titles = clusters.get(cluster_id)
        if cluster_titles is None:
            cluster_titles = [
                _page_title_from_path(self.graph_root, path) for path in cluster_paths
            ]
        neighborhood = format_cluster_neighborhood(catalog.to_json(), cluster_titles)
        self.llm_client.inject_cluster_focus_context(neighborhood)

    def _sync_live_telemetry(
        self,
        state: DaemonState,
        *,
        cluster_id: str | None = None,
        mark_running: bool = False,
    ) -> None:
        """Mirror in-memory token totals and cluster focus onto the checkpoint plane."""
        state.session_prompt_tokens = self.token_logger.session_prompt_tokens
        state.session_completion_tokens = self.token_logger.session_completion_tokens
        if cluster_id is not None:
            state.current_cluster = cluster_id
        if mark_running and state.status != "stopped":
            state.status = "running"

    def _mark_telemetry_dirty(self) -> None:
        with self._telemetry_lock:
            self._telemetry_dirty = True

    def _snapshot_state_locked(self, state: DaemonState) -> DaemonState:
        """Return an immutable copy of ``state``; caller must hold ``_telemetry_lock``."""
        return DaemonState.from_json(state.to_json())

    def _persist_daemon_state(
        self,
        state: DaemonState,
        *,
        path: Path | None = None,
        mark_running: bool = False,
    ) -> None:
        """Persist under ``_telemetry_lock`` using an immutable JSON snapshot (thread-safe)."""
        try:
            with self._telemetry_lock:
                self._sync_live_telemetry(state, mark_running=mark_running)
                snapshot = self._snapshot_state_locked(state)
                self._last_heartbeat_monotonic = time.monotonic()
                self._telemetry_dirty = False
            save_daemon_state(self.graph_root, snapshot)
            self._state_persist_failed = False
        except Exception as save_exc:  # noqa: BLE001 - log and continue cycle
            self._state_persist_failed = True
            target = path if path is not None else self.graph_root
            self.token_logger.log_structural_lint_warning(
                target_file=target,
                message=f"Checkpoint save failed: {save_exc}",
                malformed_refs=[],
            )

    def _maybe_heartbeat_checkpoint(
        self,
        state: DaemonState,
        *,
        force: bool = False,
    ) -> None:
        """Flush telemetry when dirty or when the heartbeat interval has elapsed."""
        interval = telemetry_heartbeat_seconds()
        now = time.monotonic()
        with self._telemetry_lock:
            if (
                not force
                and not self._telemetry_dirty
                and now - self._last_heartbeat_monotonic < interval
            ):
                return
            self._sync_live_telemetry(state, mark_running=state.status != "stopped")
            snapshot = self._snapshot_state_locked(state)
            self._last_heartbeat_monotonic = now
            self._telemetry_dirty = False
        try:
            save_daemon_state(self.graph_root, snapshot)
            self._state_persist_failed = False
        except Exception as save_exc:  # noqa: BLE001 - heartbeat must not abort work
            self._state_persist_failed = True
            self.token_logger.log_structural_lint_warning(
                target_file=self.graph_root,
                message=f"Telemetry heartbeat save failed: {save_exc}",
                malformed_refs=[],
            )

    @contextlib.contextmanager
    def _telemetry_heartbeat_scope(self, state: DaemonState) -> Any:
        """Periodic checkpoint during blocking work (e.g. long ``index_page`` calls)."""
        stop = threading.Event()

        def _heartbeat_loop() -> None:
            while not stop.wait(timeout=telemetry_heartbeat_seconds()):
                if self._stop_requested or self._shutdown_event.is_set():
                    break
                self._maybe_heartbeat_checkpoint(state, force=True)

        thread = threading.Thread(
            target=_heartbeat_loop,
            name="plumber-telemetry-heartbeat",
            daemon=True,
        )
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=1.0)

    def _save_cycle_checkpoint(self, state: DaemonState, *, path: Path | None = None) -> None:
        """Persist daemon state after one file settles in the cycle flywheel.

        Uses :func:`save_daemon_state` (POSIX ``os.replace``) so concurrent FastAPI
        readers never observe a truncated checkpoint mid-write.
        """
        self._persist_daemon_state(state, path=path)

    def _try_fast_track_cycle_file(self, path: Path, state: DaemonState) -> bool:
        return try_fast_track_cycle_file(cast(DaemonLLMCycleHost, self), path, state)

    def _settle_journal_structural_cycle_file(
        self,
        path: Path,
        state: DaemonState,
        *,
        cluster_id: str | None = None,
    ) -> bool:
        return settle_journal_structural_cycle_file(
            cast(DaemonLLMCycleHost, self),
            path,
            state,
            cluster_id=cluster_id,
        )

    def _process_llm_cycle_file(
        self,
        path: Path,
        state: DaemonState,
        lint_config: PlumberLintConfig,
        *,
        reset_history_after: bool,
        cluster_id: str | None = None,
    ) -> bool:
        return process_llm_cycle_file(
            cast(DaemonLLMCycleHost, self),
            path,
            state,
            lint_config,
            reset_history_after=reset_history_after,
            cluster_id=cluster_id,
        )

    def _quarantine_structural_lint(
        self,
        *,
        path: Path,
        key: str,
        mtime: float,
        message: str,
        malformed_refs: list[str],
        state: DaemonState,
    ) -> None:
        quarantine_structural_lint(
            cast(DaemonLLMCycleHost, self),
            path=path,
            key=key,
            mtime=mtime,
            message=message,
            malformed_refs=malformed_refs,
            state=state,
        )

    def _settle_journey_journal_in_state(self, state: DaemonState) -> bool:
        return settle_journey_journal_in_state(cast(DaemonLLMCycleHost, self), state)

    def _finalize_link_and_journey_pass(
        self,
        state: DaemonState,
        *,
        llm_files_processed: int,
        fast_track_files: int,
    ) -> None:
        finalize_link_and_journey_pass(
            cast(DaemonLLMCycleHost, self),
            state,
            llm_files_processed=llm_files_processed,
            fast_track_files=fast_track_files,
        )

    def run_cycle(self, state: DaemonState | None = None) -> DaemonState:
        """Drain fast-skippable pending files, then up to ``max_files_per_cycle`` LLM turns."""
        state = self._sync_runtime_config(state or load_daemon_state(self.graph_root))
        self._hydrate_bootstrap_phase(state)
        self._hydrate_token_logger_from_state(state)
        normalize_daemon_state_file_keys(self.graph_root, state)
        try:
            purge_expired_semantic_cache(self.graph_root)
        except OSError as exc:
            logger.warning("Semantic cache purge skipped: {}", exc)
        try:
            prune_stale_daemon_file_entries(state, self.graph_root)
        except (OSError, FileNotFoundError) as exc:
            logger.error("Graph root inaccessible during prune: {}", exc)
            state.status = "error"
            self._sync_live_telemetry(state)
            save_daemon_state(self.graph_root, state)
            return state

        state.status = "running"
        state.last_scan_at = datetime.now(tz=UTC).isoformat()
        if self.bootstrap_complete:
            self._vault_refresh_counter += 1
            if state.phase2_cognitive_total <= 0 or self._vault_refresh_counter % 10 == 1:
                try:
                    refresh_phase2_cognitive_totals(self.graph_root, state)
                except OSError as exc:
                    logger.warning("Phase 2 progress totals skipped at cycle start: {}", exc)
        self._persist_daemon_state(state, mark_running=True)
        try:
            pending = list_pending_files(
                self.graph_root,
                state,
                bootstrap_complete=self.bootstrap_complete,
            )
        except (OSError, FileNotFoundError) as exc:
            logger.error("Graph root inaccessible during pending scan: {}", exc)
            state.status = "error"
            self._sync_live_telemetry(state)
            save_daemon_state(self.graph_root, state)
            return state

        if not pending:
            self.refresh_catalog_if_stale()
            self._prune_stale_catalog_entries()
            heal_daemon_state_ledger(self.graph_root, state)
            state.status = "idle"
            save_daemon_state(self.graph_root, state)
            self._finalize_link_and_journey_pass(
                state,
                llm_files_processed=0,
                fast_track_files=0,
            )
            return state

        cycle_budget = max(1, self.max_files_per_cycle)
        fast_track_count = 0
        for path in pending:
            if self._stop_requested:
                state.status = "stopped"
                break
            if cycle_budget <= 0:
                break
            if self._try_fast_track_cycle_file(path, state):
                self._save_cycle_checkpoint(state, path=path)
                cycle_budget -= 1
                fast_track_count += 1
                if link_verify_enabled():
                    try:
                        register_page_links_from_path(self.graph_root, path)
                    except OSError:
                        logger.exception("Fast-track link registry registration failed")

        if self._stop_requested:
            self._prune_stale_catalog_entries()
            self._sync_live_telemetry(state)
            save_daemon_state(self.graph_root, state)
            return state

        if self.bootstrap_failed and not self.bootstrap_complete:
            logger.warning(
                "Skipping Phase 2 LLM cycle: bootstrap_failed ({})",
                state.bootstrap_failed_reason or "unknown",
            )
            pending_llm: list[Path] = []
        else:
            pending_llm = list_pending_files(
                self.graph_root,
                state,
                bootstrap_complete=self.bootstrap_complete,
            )
        lint_config = self._effective_lint_config()
        cluster_cycle = self._use_semantic_cluster_cycle(lint_config)
        llm_turns_this_cycle = 0
        pending_groups: list[tuple[str, list[Path]]]
        if cluster_cycle:
            pending_groups = self._group_pending_by_cluster(pending_llm)
        else:
            pending_groups = [("flat", pending_llm)]

        for cluster_id, cluster_paths in pending_groups:
            if self._stop_requested:
                state.status = "stopped"
                break
            if llm_turns_this_cycle >= cycle_budget:
                break
            uses_cluster_focus = cluster_cycle and cluster_id not in CLUSTER_IDS_WITHOUT_FOCUS
            if uses_cluster_focus:
                self._begin_cluster_context(cluster_id, cluster_paths)
                state.current_cluster_files_total = len(cluster_paths)
                state.current_cluster_files_done = 0
                state.phase2_cluster_file_in_flight = False
                self._sync_live_telemetry(state, cluster_id=cluster_id, mark_running=True)
                self._save_cycle_checkpoint(state)
            elif cluster_cycle:
                state.current_cluster = cluster_id
                state.current_cluster_files_total = len(cluster_paths)
                state.current_cluster_files_done = 0
                state.phase2_cluster_file_in_flight = False
                self._sync_live_telemetry(state, cluster_id=cluster_id, mark_running=True)
                self._save_cycle_checkpoint(state)
            else:
                state.current_cluster = None
                state.current_cluster_files_total = 0
                state.current_cluster_files_done = 0
                state.phase2_cluster_file_in_flight = False
            for path in cluster_paths:
                if self._stop_requested:
                    state.status = "stopped"
                    break
                if llm_turns_this_cycle >= cycle_budget:
                    break
                llm_called_this_turn = self._process_llm_cycle_file(
                    path,
                    state,
                    lint_config,
                    reset_history_after=not cluster_cycle
                    or cluster_id in CLUSTER_IDS_WITHOUT_FOCUS,
                    cluster_id=cluster_id if uses_cluster_focus else None,
                )
                if cluster_cycle:
                    state.current_cluster_files_done += 1
                self._sync_live_telemetry(state, mark_running=True)
                self._save_cycle_checkpoint(state, path=path)
                if llm_called_this_turn:
                    llm_turns_this_cycle += 1

        self._prune_stale_catalog_entries()
        heal_daemon_state_ledger(self.graph_root, state)
        state.phase2_cluster_file_in_flight = False
        if self.bootstrap_complete and self._vault_refresh_counter % 10 == 0:
            try:
                refresh_phase2_cognitive_totals(self.graph_root, state)
            except OSError as exc:
                logger.warning("Phase 2 progress totals skipped at cycle end: {}", exc)
        if not self._stop_requested:
            state.status = "idle"
        self._persist_daemon_state(state)
        maybe_release_after_cycle(
            llm_turns=llm_turns_this_cycle,
            graph_root=self.graph_root,
        )
        self._finalize_link_and_journey_pass(
            state,
            llm_files_processed=llm_turns_this_cycle,
            fast_track_files=fast_track_count,
        )
        return state

    def run_forever(self) -> None:
        """Infinite polling loop until stop is requested."""
        self._register_daemon_signal_handlers()
        prepare_matryca_runtime(
            graph_root=self.graph_root,
            wiki_config=load_matryca_wiki_config(),
        )
        state = self._sync_runtime_config(load_daemon_state(self.graph_root))
        llm_config = load_plumber_lint_config()
        logger.info(
            "LLM Engine starting... Provider URL: {} | Target Model: {}",
            llm_config.lm_base_url,
            llm_config.lm_model,
        )
        cleared_errors = clear_phase1_error_backoff(state)
        if cleared_errors:
            logger.info(
                "Cleared {} Phase 1 error record(s) for retry on daemon restart",
                cleared_errors,
            )
            save_daemon_state(self.graph_root, state)
        self._hydrate_bootstrap_phase(state)
        self._hydrate_token_logger_from_state(state)
        state.status = "running"
        save_daemon_state(self.graph_root, state)
        log_snapshot(label="daemon_start")

        try:
            self.run_bootstrap_pipeline(state)
            self._start_file_watcher()
            while not self._stop_requested:
                self.run_cycle(state)
                if not self._state_persist_failed:
                    state = load_daemon_state(self.graph_root)
                else:
                    logger.warning(
                        "Skipping checkpoint reload after persist failure; "
                        "retaining in-memory daemon state",
                    )
                if self._stop_requested:
                    break
                deadline = time.monotonic() + self.poll_seconds
                heartbeat_s = telemetry_heartbeat_seconds()
                while not self._stop_requested and time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()
                    wait_s = min(remaining, heartbeat_s)
                    if self._cycle_wake.wait(timeout=wait_s):
                        self._cycle_wake.clear()
                    else:
                        self._maybe_heartbeat_checkpoint(state, force=True)
                    if self._shutdown_event.is_set():
                        break
                if self._shutdown_event.is_set():
                    break
        finally:
            self._finalize_graceful_shutdown(state)


def run_plumber_cluster(
    graph_root: Path | None = None,
    *,
    max_cluster_size: int = 35,
    force_recompute: bool = False,
) -> dict[str, Any]:
    """Manual entrypoint: compute or audit semantic cluster neighborhoods."""
    root = graph_root or resolve_graph_root()
    prepare_matryca_runtime(graph_root=root, wiki_config=load_matryca_wiki_config())
    catalog = load_master_catalog(root, force_reload=True)
    clusters = load_or_compute_semantic_clusters(
        root,
        catalog_data=catalog.to_json(),
        max_cluster_size=max_cluster_size,
        force_recompute=force_recompute,
    )
    sizes = [len(titles) for titles in clusters.values()]
    return {
        "ok": True,
        "graph_root": str(root),
        "cluster_count": len(clusters),
        "page_count": sum(sizes),
        "min_cluster_size": min(sizes) if sizes else 0,
        "max_cluster_size": max(sizes) if sizes else 0,
        "avg_cluster_size": round(sum(sizes) / len(sizes), 2) if sizes else 0.0,
        "clusters_path": str(
            (root / ".matryca_semantic_cache" / "semantic_clusters.json").relative_to(root),
        ),
        "catalog_updated_at": catalog.updated_at,
    }


def run_plumber_audit(graph_root: Path | None = None) -> dict[str, Any]:
    """Manual entrypoint: refresh catalog and compile graph insights dashboard."""
    root = graph_root or resolve_graph_root()
    prepare_matryca_runtime(graph_root=root, wiki_config=load_matryca_wiki_config())
    llm = InstructorLLMClient()
    run_bootstrap_harvest(root, llm=llm, incremental=True, rebuild_index=True)
    result = run_graph_insights_engine(root, llm=llm)
    return {
        "ok": True,
        "graph_root": str(root),
        "insights_path": str(result.output_path.relative_to(root)),
        "page_count": result.metrics.page_count,
        "orphan_pages": len(result.metrics.orphan_pages),
        "catalog_coverage": result.metrics.catalog_coverage,
        "llm_used": result.llm_used,
        "latency_seconds": round(result.latency_seconds, 3),
    }


def start_daemon_foreground(graph_root: Path | None = None) -> None:
    """Run the daemon in the current process (foreground)."""
    reload_plumber_dotenv()
    configure_loguru()
    root = graph_root or resolve_graph_root()
    config = load_plumber_lint_config()
    sandbox = resolve_cpu_sandbox_config(config)
    if sandbox.enabled:
        apply_cpu_sandbox(sandbox)
    else:
        apply_plumber_priority(config)
    lock_fd = _try_acquire_daemon_process_lock(root)
    if lock_fd is None:
        logger.error(
            "Matryca Plumber daemon already running (lock held) for graph_root={!r}",
            root,
        )
        sys.exit(1)
    bind_daemon_process_lock_fd(lock_fd)
    write_pid_file(root)
    register_bootstrap_shutdown_handlers(root)
    try:
        daemon = MaintenanceDaemon(root)
        if isinstance(daemon.llm_client, InstructorLLMClient):
            daemon.llm_client.probe_backend()
        daemon.run_forever()
    except BaseException:
        remove_pid_file(root)
        _release_daemon_process_lock(root)
        raise


def start_daemon_detached(graph_root: Path | None = None) -> dict[str, Any]:
    """Launch a background daemon worker via subprocess (cross-platform)."""
    root = graph_root or resolve_graph_root()
    existing = read_pid_file(root)
    if existing is not None and is_plumber_process(existing):
        return {
            "ok": False,
            "code": "already_running",
            "pid": existing,
            "message": f"Matryca Plumber daemon already running (pid {existing})",
        }
    if existing is not None and is_process_alive(existing):
        return {
            "ok": False,
            "code": "foreign_pid",
            "pid": existing,
            "message": f"PID file references a live non-plumber process (pid {existing})",
        }
    if existing is not None:
        remove_pid_file(root)

    env = os.environ.copy()
    env["LOGSEQ_GRAPH_PATH"] = str(root)
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "src.cli", "plumber", "start", "--foreground"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        pid = read_pid_file(root)
        if pid is not None and is_plumber_process(pid):
            return {"ok": True, "code": "started", "pid": pid, "graph_root": str(root)}
        exit_code = proc.poll()
        if exit_code is not None:
            return {
                "ok": False,
                "code": "startup_failed",
                "message": f"Daemon worker exited immediately with code {exit_code}",
            }
        time.sleep(0.15)

    pid = read_pid_file(root)
    if pid is not None and is_plumber_process(pid):
        return {"ok": True, "code": "started", "pid": pid, "graph_root": str(root)}
    with contextlib.suppress(OSError):
        proc.terminate()
        proc.wait(timeout=5.0)
    return {
        "ok": False,
        "code": "startup_timeout",
        "message": "Daemon did not publish a live PID in time",
    }


__all__ = [
    "DEFAULT_LM_BASE_URL",
    "DEFAULT_MODEL",
    "CorrectionOutcome",
    "DaemonState",
    "FileState",
    "InstructorLLMClient",
    "LLMClient",
    "LLMResponseError",
    "StructuredOutputExhaustedError",
    "LintType",
    "ThermalProfile",
    "MaintenanceDaemon",
    "PID_FILENAME",
    "DAEMON_LOCK_FILENAME",
    "DEFAULT_STOP_GRACE_SECONDS",
    "DEFAULT_STOP_SIGKILL_AFTER_SECONDS",
    "SEMANTIC_INDEX_HEADER",
    "STRUCTURAL_LINT_HEADER",
    "ScanMetrics",
    "SemanticCrossRef",
    "SemanticIndexResult",
    "SemanticLintCorrection",
    "apply_semantic_corrections_to_lines",
    "apply_semantic_page_result",
    "append_semantic_index",
    "append_structural_lint_warning",
    "run_dual_embedding_after_semantic_write",
    "clear_phase1_error_backoff",
    "compute_phase2_progress_metrics",
    "compute_scan_metrics",
    "heal_daemon_state_ledger",
    "is_plumber_process",
    "is_process_alive",
    "load_daemon_state",
    "list_pending_files",
    "normalize_daemon_state_file_keys",
    "page_needs_phase2_cognitive",
    "pid_path",
    "prune_stale_daemon_file_entries",
    "read_pid_file",
    "record_daemon_impact",
    "remove_pid_file",
    "resolve_graph_root",
    "run_plumber_audit",
    "save_daemon_state",
    "start_daemon_detached",
    "start_daemon_foreground",
    "state_bak_path",
    "state_path",
    "stop_daemon",
    "sync_daemon_state_from_env",
    "write_pid_file",
    "_enumerate_blocks_for_prompt",
    "_record_page_lock_backoff",
    "_release_daemon_process_lock",
    "_try_acquire_daemon_process_lock",
    "daemon_lock_path",
]
