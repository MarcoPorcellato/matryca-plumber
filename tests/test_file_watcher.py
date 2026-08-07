"""Tests for debounced graph file watcher."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict
from pathlib import Path

from src.daemon.file_watcher import GraphFileWatcher, _DebouncedMarkdownHandler


def test_debounce_coalesces_rapid_events(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    path = pages / "note.md"
    path.write_text("- a\n", encoding="utf-8")

    events: list[tuple[Path, str]] = []
    lock = threading.Lock()

    def on_fire(p: Path, kind: str) -> None:
        with lock:
            events.append((p, kind))

    handler = _DebouncedMarkdownHandler(
        tmp_path,
        debounce_s=0.05,
        on_debounced=on_fire,
    )

    class _Ev:
        is_directory = False
        event_type = "modified"
        src_path = str(path)

    handler.on_modified(_Ev())  # type: ignore[arg-type]
    handler.on_modified(_Ev())  # type: ignore[arg-type]
    pending = handler.diagnostics_snapshot()
    assert pending.pending_count == 1
    assert pending.scheduled_count == 2
    assert pending.coalesced_count == 1
    assert pending.dispatched_count == 0
    assert pending.oldest_pending_age_ns >= 0
    time.sleep(0.2)
    handler.cancel_all()

    with lock:
        assert len(events) == 1
        assert events[0][1] == "modified"

    complete = handler.diagnostics_snapshot()
    assert complete.schema_version == 1
    assert complete.pending_count == 0
    assert complete.dispatched_count == 1
    assert complete.callback_failure_count == 0
    assert complete.last_convergence_latency_ns > 0
    assert complete.max_convergence_latency_ns == complete.last_convergence_latency_ns
    assert complete.stopped is True
    assert not ({"path", "graph_root", "query", "content"} & asdict(complete).keys())


def test_watcher_diagnostics_are_empty_before_start(tmp_path: Path) -> None:
    watcher = GraphFileWatcher(tmp_path, on_debounced_change=lambda _path, _kind: None)

    snapshot = watcher.diagnostics_snapshot()

    assert snapshot.pending_count == 0
    assert snapshot.scheduled_count == 0
    assert snapshot.coalesced_count == 0
    assert snapshot.dispatched_count == 0
    assert snapshot.callback_failure_count == 0
    assert snapshot.oldest_pending_age_ns == 0
    assert snapshot.last_convergence_latency_ns == 0
    assert snapshot.max_convergence_latency_ns == 0
    assert snapshot.stopped is True
