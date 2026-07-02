"""Daemon LLM cycle — per-file indexing, fast-track settle, journey tail (issue #58 slice)."""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from loguru import logger

from ..daemon.ast_cache import get_graph_ast_cache
from ..graph.alias_index import AliasIndex
from ..graph.global_fence_scanner import compute_page_protected_line_indices
from ..graph.journal_task_scan import journal_file_path
from ..graph.link_verification import (
    link_verify_enabled,
    merge_page_links_into_registry,
    run_link_verification_cycle,
)
from ..graph.logseq_uuid import find_malformed_block_refs, is_malformed_block_ref_error
from ..graph.markdown_blocks import file_mtime_drifted, occ_snapshot
from ..graph.page_write_lock import PageLockUnavailableError
from ..graph.path_sandbox import read_graph_file_text
from ..utils.console_sanitize import sanitize_for_console
from ..utils.token_logger import TokenLogger
from .daemon_llm_client import InstructorLLMClient as _DaemonInstructorLLMClient
from .daemon_semantic_write import (
    CorrectionOutcome,
    SemanticIndexResult,
    _page_title_from_path,
    _semantic_index_section_present,
    append_structural_lint_warning,
    apply_semantic_page_result,
    run_dual_embedding_after_semantic_write,
)
from .daemon_state import (
    DaemonState,
    FileState,
    _daemon_file_key,
    _lookup_file_state,
    _record_page_lock_backoff,
    save_daemon_state,
)
from .journey_log import JourneyCycleStats, journey_log_enabled, upsert_journey_log
from .page_prompt_session import PagePromptSession, build_page_prompt_session
from .plumber_config import PlumberLintConfig
from .plumber_modules import CognitiveLintOutcome, run_cognitive_lint_pipeline
from .plumber_modules._shared import is_journal_page_path
from .semantic_lint_prompts import build_semantic_lint_system_prompt


class _DaemonCycleLLM(Protocol):
    token_logger: TokenLogger

    def index_page(
        self,
        page_title: str,
        content: str,
        *,
        page_path: Path | None = None,
        graph_root: Path | None = None,
        alias_index: AliasIndex | None = None,
        enable_semantic_routing: bool = False,
        prompt_session: PagePromptSession | None = None,
    ) -> tuple[SemanticIndexResult, dict[str, int]]: ...

    def reset_execution_history(self) -> None: ...


class DaemonLLMCycleHost(Protocol):
    """Narrow host surface for per-file LLM cycle helpers (``MaintenanceDaemon``)."""

    graph_root: Path
    token_logger: TokenLogger
    llm_client: _DaemonCycleLLM
    bootstrap_complete: bool

    def _absorb_token_logger_delta(
        self,
        other: TokenLogger,
        *,
        baseline_prompt: int,
        baseline_completion: int,
    ) -> None: ...

    def _compiled_alias_index(self) -> AliasIndex | None: ...

    def _begin_phase2_write(self) -> None: ...

    def _end_phase2_write(self) -> None: ...

    def _sync_catalog_after_page_write(self, path: Path, title: str) -> None: ...

    def _sync_live_telemetry(
        self,
        state: DaemonState,
        *,
        cluster_id: str | None = None,
        mark_running: bool = False,
    ) -> None: ...

    def _mark_telemetry_dirty(self) -> None: ...

    def _telemetry_heartbeat_scope(
        self,
        state: DaemonState,
    ) -> AbstractContextManager[object]: ...

    def _save_cycle_checkpoint(self, state: DaemonState, *, path: Path | None = None) -> None: ...


def record_daemon_impact(
    state: DaemonState,
    *,
    cognitive: CognitiveLintOutcome | None = None,
    lint: CorrectionOutcome | None = None,
    links_backpropagated: int = 0,
) -> None:
    """Accumulate provenance counters from one Plumber cycle turn."""
    if cognitive is not None:
        state.ai_pages_created += len(cognitive.pages_created)
        for detail in cognitive.details:
            if (
                detail.startswith("properties:")
                or detail.startswith("alias:")
                or detail.startswith("marpa:")
            ):
                state.hygiene_corrections += 1
            elif detail.startswith("split:"):
                state.ai_blocks_healed += 1
    if lint is not None:
        state.ai_blocks_healed += lint.applied
    if links_backpropagated > 0:
        state.ai_links_injected += links_backpropagated


def quarantine_structural_lint(
    host: DaemonLLMCycleHost,
    *,
    path: Path,
    key: str,
    mtime: float,
    message: str,
    malformed_refs: list[str],
    state: DaemonState,
) -> None:
    """Log, optionally annotate, and skip a page with malformed ``((uuid))`` refs."""
    rel_path = path.relative_to(host.graph_root).as_posix()
    host.token_logger.log_structural_lint_warning(
        target_file=path,
        message=f"{message} file={rel_path}",
        malformed_refs=malformed_refs,
    )
    try:
        append_structural_lint_warning(host.graph_root, path, malformed_refs)
    except Exception as inj_exc:  # noqa: BLE001 - never crash daemon on annotation
        host.token_logger.log_structural_lint_warning(
            target_file=path,
            message=f"Warning injection failed for {rel_path}: {inj_exc}",
            malformed_refs=malformed_refs,
        )
    recorded_mtime = path.stat().st_mtime if path.is_file() else mtime
    state.files[key] = FileState(
        mtime=recorded_mtime,
        processed_at=datetime.now(tz=UTC).isoformat(),
        status="skipped",
        error=message,
    )


def settle_journey_journal_in_state(host: DaemonLLMCycleHost, state: DaemonState) -> bool:
    """Record today's journal as settled so the next pending scan ignores daemon appends."""
    path = journal_file_path(host.graph_root, date.today())
    if not path.is_file():
        return False
    key = _daemon_file_key(host.graph_root, path)
    state.files[key] = FileState(
        mtime=path.stat().st_mtime,
        processed_at=datetime.now(tz=UTC).isoformat(),
        status="skipped",
    )
    return True


def finalize_link_and_journey_pass(
    host: DaemonLLMCycleHost,
    state: DaemonState,
    *,
    llm_files_processed: int,
    fast_track_files: int,
) -> None:
    """Background link verification + optional journal journey log."""
    stats = JourneyCycleStats(
        llm_files_processed=llm_files_processed,
        fast_track_files=fast_track_files,
    )
    if link_verify_enabled():
        try:
            link_result = run_link_verification_cycle(host.graph_root)
            stats.links_checked = link_result.checked
            stats.dead_links_flagged = link_result.flagged_url_blocks
            stats.missing_assets_flagged = link_result.flagged_asset_blocks
            flagged_total = link_result.flagged_blocks
            if flagged_total:
                stats.notes.append(
                    f"flagged {flagged_total} block(s) with hygiene properties",
                )
        except OSError as exc:
            logger.warning("Link verification cycle skipped: {}", exc)
    journey_state_updated = False
    if journey_log_enabled() and stats.has_journal_activity():
        today = date.today()
        state.journey_day.reset_if_new_day(today)
        state.journey_day.accumulate(stats)
        journey_state_updated = True
        try:
            result = upsert_journey_log(
                str(host.graph_root),
                state.journey_day,
                as_of=today,
            )
            if result.get("ok") and result.get("code") == "applied":
                settle_journey_journal_in_state(host, state)
        except OSError:
            logger.exception("Journey log upsert failed")
    if journey_state_updated:
        save_daemon_state(host.graph_root, state)


def try_fast_track_cycle_file(
    host: DaemonLLMCycleHost,
    path: Path,
    state: DaemonState,
) -> bool:
    """Settle a pending page without LLM tokens (quarantine, cache, empty)."""
    key = _daemon_file_key(host.graph_root, path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False

    state.last_file = sanitize_for_console(key)
    try:
        content = read_graph_file_text(path, host.graph_root, errors="replace")
    except OSError:
        return False

    protected_lines = compute_page_protected_line_indices(content)
    malformed_refs = find_malformed_block_refs(
        content,
        protected_lines=protected_lines,
    )
    if malformed_refs:
        quarantine_structural_lint(
            host,
            path=path,
            key=key,
            mtime=mtime,
            message="Malformed UUID detected in block ref. Must be standard 36-char format.",
            malformed_refs=malformed_refs,
            state=state,
        )
        return True
    if _semantic_index_section_present(content) and not host.bootstrap_complete:
        state.files[key] = FileState(
            mtime=mtime,
            processed_at=datetime.now(tz=UTC).isoformat(),
            status="skipped",
        )
        return True
    if not content.strip():
        state.files[key] = FileState(
            mtime=mtime,
            processed_at=datetime.now(tz=UTC).isoformat(),
            status="skipped",
        )
        return True
    if link_verify_enabled():
        try:
            merge_page_links_into_registry(host.graph_root, path, content)
        except OSError:
            logger.exception("Fast-track link registry merge failed")
    return False


def settle_journal_structural_cycle_file(
    host: DaemonLLMCycleHost,
    path: Path,
    state: DaemonState,
    *,
    cluster_id: str | None = None,
) -> bool:
    """Phase-1 structural settle for ``journals/`` pages (no semantic LLM or embeddings)."""
    key = _daemon_file_key(host.graph_root, path)
    mtime = path.stat().st_mtime
    state.last_file = sanitize_for_console(key)
    if cluster_id is not None:
        state.phase2_cluster_file_in_flight = True
    host._sync_live_telemetry(state, cluster_id=cluster_id, mark_running=True)
    host._save_cycle_checkpoint(state, path=path)
    try:
        if path.is_file():
            content = read_graph_file_text(path, host.graph_root, errors="replace")
            if link_verify_enabled():
                try:
                    merge_page_links_into_registry(host.graph_root, path, content)
                except OSError:
                    logger.exception("Journal structural settle link registry merge failed")
        get_graph_ast_cache(host.graph_root).apply_file_event(path, "modified")
        state.files[key] = FileState(
            mtime=path.stat().st_mtime,
            processed_at=datetime.now(tz=UTC).isoformat(),
            status="processed",
        )
    except Exception as exc:  # noqa: BLE001 - per-file settle must not abort cycle
        state.files[key] = FileState(
            mtime=mtime,
            processed_at=datetime.now(tz=UTC).isoformat(),
            status="error",
            error=str(exc),
        )
    finally:
        if cluster_id is not None:
            state.phase2_cluster_file_in_flight = False
    host._mark_telemetry_dirty()
    host._save_cycle_checkpoint(state, path=path)
    return False


def process_llm_cycle_file(
    host: DaemonLLMCycleHost,
    path: Path,
    state: DaemonState,
    lint_config: PlumberLintConfig,
    *,
    reset_history_after: bool,
    cluster_id: str | None = None,
) -> bool:
    """Index one pending page via LLM path. Returns whether inference ran this turn."""
    if is_journal_page_path(host.graph_root, path):
        return settle_journal_structural_cycle_file(
            host,
            path,
            state,
            cluster_id=cluster_id,
        )
    key = _daemon_file_key(host.graph_root, path)
    mtime = path.stat().st_mtime
    title = _page_title_from_path(host.graph_root, path)
    state.last_file = sanitize_for_console(key)
    if cluster_id is not None:
        state.phase2_cluster_file_in_flight = True
    host._sync_live_telemetry(
        state,
        cluster_id=cluster_id,
        mark_running=True,
    )
    host._save_cycle_checkpoint(state, path=path)
    content = ""
    prompt_before = host.token_logger.session_prompt_tokens
    completion_before = host.token_logger.session_completion_tokens
    llm_called_from_usage = False
    write_aborted = False
    host._begin_phase2_write()
    try:
        baseline_mtime = occ_snapshot(path) if path.is_file() else None
        if path.is_file():
            content = read_graph_file_text(path, host.graph_root, errors="replace")
            if link_verify_enabled():
                try:
                    merge_page_links_into_registry(host.graph_root, path, content)
                except OSError:
                    logger.exception("Phase 2 cognitive lint link registry merge failed")
        cognitive_outcome: CognitiveLintOutcome | None = None
        prompt_session: PagePromptSession | None = None
        if host.bootstrap_complete and lint_config.any_enabled:
            cognitive_outcome, prompt_session = run_cognitive_lint_pipeline(
                host.graph_root,
                path,
                title,
                content,
                llm=host.llm_client,
                config=lint_config,
            )
            record_daemon_impact(state, cognitive=cognitive_outcome)
            if isinstance(host.llm_client, _DaemonInstructorLLMClient):
                host._absorb_token_logger_delta(
                    host.llm_client.token_logger,
                    baseline_prompt=prompt_before,
                    baseline_completion=completion_before,
                )
            host._sync_live_telemetry(
                state,
                cluster_id=cluster_id,
                mark_running=True,
            )
            host._save_cycle_checkpoint(state, path=path)
            if path.is_file():
                content = read_graph_file_text(path, host.graph_root, errors="replace")
                refreshed_mtime = occ_snapshot(path)
                if refreshed_mtime is not None:
                    baseline_mtime = refreshed_mtime
        alias_index = host._compiled_alias_index() if host.bootstrap_complete else None
        enable_semantic_routing = host.bootstrap_complete and lint_config.semantic_routing
        enable_backprop = host.bootstrap_complete and lint_config.backpropagate_links
        if baseline_mtime is not None and file_mtime_drifted(path, baseline_mtime):
            logger.warning(
                "OCC Conflict: User modified {} during inference. Aborting write.",
                path,
            )
            write_aborted = True
            return False
        if prompt_session is None and host.graph_root is not None:
            prompt_session = build_page_prompt_session(
                host.graph_root,
                title,
                content,
                config=lint_config,
                stable_system=build_semantic_lint_system_prompt(),
                page_path=path,
                alias_index=alias_index,
            )
        with host._telemetry_heartbeat_scope(state):
            result, usage = host.llm_client.index_page(
                title,
                content,
                page_path=path,
                graph_root=host.graph_root,
                alias_index=alias_index,
                enable_semantic_routing=enable_semantic_routing,
                prompt_session=prompt_session,
            )
        llm_called_from_usage = (
            int(usage.get("prompt_tokens", 0) or 0)
            + int(usage.get("completion_tokens", 0) or 0)
        ) > 0
        if baseline_mtime is not None and file_mtime_drifted(path, baseline_mtime):
            logger.warning(
                "OCC Conflict: User modified {} before apply. Aborting write.",
                path,
            )
            write_aborted = True
            return False
        lint_outcome = apply_semantic_page_result(
            host.graph_root,
            path,
            title,
            result,
            backpropagate=enable_backprop,
            alias_index=alias_index,
            disable_semantic_corrections=lint_config.disable_semantic_corrections,
            baseline_mtime=baseline_mtime,
        )
        record_daemon_impact(
            state,
            lint=lint_outcome,
            links_backpropagated=lint_outcome.links_backpropagated,
        )
        if lint_outcome.write_aborted:
            write_aborted = True
            llm_called_from_logger = (
                host.token_logger.session_prompt_tokens > prompt_before
                or host.token_logger.session_completion_tokens > completion_before
            )
            return llm_called_from_usage or llm_called_from_logger
        state.files[key] = FileState(
            mtime=path.stat().st_mtime,
            processed_at=datetime.now(tz=UTC).isoformat(),
            status="processed",
        )
        host._sync_catalog_after_page_write(path, title)
        run_dual_embedding_after_semantic_write(
            host.graph_root,
            path,
            title,
            host.llm_client,
        )
    except PageLockUnavailableError as exc:
        host.token_logger.log_structural_lint_warning(
            target_file=path,
            message=f"Page lock unavailable after retries: {exc}",
            malformed_refs=[],
        )
        _key, prior_rec = _lookup_file_state(host.graph_root, state, path)
        _record_page_lock_backoff(
            state,
            key=_key,
            mtime=mtime,
            message=str(exc),
            prior=prior_rec,
        )
    except Exception as exc:  # noqa: BLE001 - quarantine per-file; never abort cycle
        if is_malformed_block_ref_error(exc):
            protected_lines = compute_page_protected_line_indices(content)
            malformed_refs = find_malformed_block_refs(
                content,
                protected_lines=protected_lines,
            )
            quarantine_structural_lint(
                host,
                path=path,
                key=key,
                mtime=mtime,
                message=str(exc),
                malformed_refs=malformed_refs or [],
                state=state,
            )
        else:
            state.files[key] = FileState(
                mtime=mtime,
                processed_at=datetime.now(tz=UTC).isoformat(),
                status="error",
                error=str(exc),
            )
    finally:
        host._end_phase2_write()
        if cluster_id is not None:
            state.phase2_cluster_file_in_flight = False
        if reset_history_after and isinstance(host.llm_client, _DaemonInstructorLLMClient):
            host.llm_client.reset_execution_history()
    llm_called_from_logger = (
        host.token_logger.session_prompt_tokens > prompt_before
        or host.token_logger.session_completion_tokens > completion_before
    )
    llm_called = llm_called_from_usage or llm_called_from_logger
    if llm_called and host.bootstrap_complete and not write_aborted:
        state.phase2_llm_turns += 1
    if host.bootstrap_complete and not write_aborted:
        rec = state.files.get(key)
        if rec is not None and rec.status == "processed":
            vault_total = state.phase2_cognitive_total
            if vault_total > 0:
                state.phase2_cognitive_done = min(
                    vault_total,
                    state.phase2_cognitive_done + 1,
                )
            else:
                state.phase2_cognitive_done += 1
    host._mark_telemetry_dirty()
    host._save_cycle_checkpoint(state, path=path)
    return llm_called


__all__ = [
    "DaemonLLMCycleHost",
    "finalize_link_and_journey_pass",
    "process_llm_cycle_file",
    "quarantine_structural_lint",
    "record_daemon_impact",
    "settle_journal_structural_cycle_file",
    "settle_journey_journal_in_state",
    "try_fast_track_cycle_file",
]
