"""Daemon page queue — pending-file selection and scan metrics (issue #58 slice)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from ..graph.alias_index import iter_alias_source_paths
from ..graph.global_fence_scanner import compute_page_protected_line_indices
from ..graph.logseq_uuid import find_malformed_block_refs
from ..graph.path_sandbox import read_graph_file_text
from .daemon_semantic_write import _page_title_from_path, _semantic_index_section_present
from .daemon_state import (
    DaemonState,
    _daemon_file_key,
    _lock_backoff_active,
    _lookup_file_state,
)
from .plumber_modules._shared import is_journal_page_path

MATRYCA_GENERATED_PAGE_TITLES = frozenset(
    {"Matryca Master Index", "Matryca Graph Insights"},
)


@dataclass(frozen=True)
class ScanMetrics:
    """Graph scan counters for the TUI."""

    total: int
    processed: int
    pending: int

    @property
    def percent_complete(self) -> float:
        if self.total == 0:
            return 100.0
        return round(100.0 * self.processed / self.total, 1)


def _mtime_matches(stored: float, current: float) -> bool:
    """Return whether a checkpoint mtime still matches the on-disk value."""
    if stored == current:
        return True
    # JSON checkpoint round-trip can shave sub-microsecond float precision.
    return math.isclose(stored, current, rel_tol=0.0, abs_tol=1e-6)


def _read_page_content(path: Path, graph_root: Path) -> str:
    try:
        return read_graph_file_text(path, graph_root, errors="replace")
    except OSError:
        return ""


def _page_is_terminal_skip(content: str) -> bool:
    """Pages that should never enter the LLM queue (empty or structurally unsafe)."""
    if not content.strip():
        return True
    protected_lines = compute_page_protected_line_indices(content)
    return bool(find_malformed_block_refs(content, protected_lines=protected_lines))


def page_needs_phase2_cognitive(
    graph_root: Path,
    path: Path,
    state: DaemonState,
    *,
    content: str | None = None,
) -> bool:
    """Return whether a page still needs the Phase 2 cognitive pass."""
    title = _page_title_from_path(graph_root, path)
    if title in MATRYCA_GENERATED_PAGE_TITLES:
        return False

    text = content if content is not None else _read_page_content(path, graph_root)
    if _page_is_terminal_skip(text):
        return False

    if is_journal_page_path(graph_root, path):
        _key, rec = _lookup_file_state(graph_root, state, path)
        mtime = path.stat().st_mtime
        if rec is None:
            return True
        if not _mtime_matches(rec.mtime, mtime):
            return True
        if rec.status == "error":
            return False
        if _lock_backoff_active(rec):
            return False
        return False

    _key, rec = _lookup_file_state(graph_root, state, path)
    mtime = path.stat().st_mtime
    if rec is None:
        return True
    if not _mtime_matches(rec.mtime, mtime):
        return True
    if rec.status == "processed":
        return False
    if rec.status == "error":
        return False
    if _lock_backoff_active(rec):
        return False
    if rec.status == "skipped":
        return _semantic_index_section_present(text)
    return True


def compute_phase2_progress_metrics(
    graph_root: Path,
    state: DaemonState,
) -> tuple[int, int, int, int]:
    """Return total, cognitive_done, cognitive_pending, terminal_skipped page counts."""
    total = 0
    cognitive_done = 0
    cognitive_pending = 0
    terminal_skipped = 0
    for path in iter_alias_source_paths(graph_root):
        title = _page_title_from_path(graph_root, path)
        if title in MATRYCA_GENERATED_PAGE_TITLES:
            continue
        if is_journal_page_path(graph_root, path):
            continue
        total += 1
        _key, rec = _lookup_file_state(graph_root, state, path)
        mtime = path.stat().st_mtime if path.is_file() else 0.0
        if rec is not None and _mtime_matches(rec.mtime, mtime) and rec.status == "processed":
            cognitive_done += 1
        elif page_needs_phase2_cognitive(graph_root, path, state):
            cognitive_pending += 1
        else:
            terminal_skipped += 1
    return total, cognitive_done, cognitive_pending, terminal_skipped


def compute_scan_metrics(graph_root: Path, state: DaemonState) -> ScanMetrics:
    files = iter_alias_source_paths(graph_root)
    total = len(files)
    processed = 0
    pending = 0
    for path in files:
        _key, rec = _lookup_file_state(graph_root, state, path)
        mtime = path.stat().st_mtime if path.is_file() else 0.0
        if rec is not None and _mtime_matches(rec.mtime, mtime):
            if rec.status == "processed":
                processed += 1
            elif rec.status in {"skipped", "error"}:
                pass
            else:
                pending += 1
        else:
            pending += 1
    return ScanMetrics(total=total, processed=processed, pending=pending)


def clear_phase1_error_backoff(state: DaemonState) -> int:
    """Drop Phase 1 error records so unchanged files can retry after daemon restart."""
    cleared = 0
    for key, rec in list(state.files.items()):
        if rec.status == "error":
            del state.files[key]
            cleared += 1
    return cleared


def list_pending_files(
    graph_root: Path,
    state: DaemonState,
    *,
    bootstrap_complete: bool | None = None,
) -> list[Path]:
    pending: list[Path] = []
    phase2 = state.bootstrap_complete if bootstrap_complete is None else bootstrap_complete
    settled_statuses = frozenset({"processed", "skipped"})
    for path in iter_alias_source_paths(graph_root):
        title = _page_title_from_path(graph_root, path)
        if title in MATRYCA_GENERATED_PAGE_TITLES:
            continue
        if phase2:
            if page_needs_phase2_cognitive(graph_root, path, state):
                pending.append(path)
            continue
        _key, rec = _lookup_file_state(graph_root, state, path)
        mtime = path.stat().st_mtime
        if rec is not None and _mtime_matches(rec.mtime, mtime):
            if rec.status in settled_statuses:
                continue
            if rec.status == "error":
                continue
            if _lock_backoff_active(rec):
                continue
        pending.append(path)
    return pending


def prune_stale_daemon_file_entries(state: DaemonState, graph_root: Path) -> int:
    """Remove ghost paths from daemon state (deleted or renamed markdown files)."""
    live_keys = {_daemon_file_key(graph_root, path) for path in iter_alias_source_paths(graph_root)}
    ghosts = [key for key in state.files if key not in live_keys]
    for key in ghosts:
        del state.files[key]
    return len(ghosts)


__all__ = [
    "MATRYCA_GENERATED_PAGE_TITLES",
    "ScanMetrics",
    "clear_phase1_error_backoff",
    "compute_phase2_progress_metrics",
    "compute_scan_metrics",
    "list_pending_files",
    "page_needs_phase2_cognitive",
    "prune_stale_daemon_file_entries",
]
