"""Debounced watchdog observer for Logseq ``pages/`` and ``journals/``."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..graph.alias_index import is_scannable_graph_markdown
from ..graph.path_sandbox import assert_path_within_graph


class _FilesystemObserver(Protocol):
    """Subset of ``watchdog.observers.Observer`` used by ``GraphFileWatcher``."""

    def schedule(
        self,
        event_handler: FileSystemEventHandler,
        path: str,
        *,
        recursive: bool = False,
    ) -> object: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


FileEventKind = Literal["created", "modified", "deleted"]

_DEFAULT_DEBOUNCE_MS = 750
_MIN_DEBOUNCE_MS = 500
_MAX_DEBOUNCE_MS = 1000


@dataclass(frozen=True, slots=True)
class WatcherDiagnosticsSnapshot:
    """Content-free process-lifetime debounce diagnostics."""

    schema_version: int
    pending_count: int
    scheduled_count: int
    coalesced_count: int
    dispatched_count: int
    callback_failure_count: int
    oldest_pending_age_ns: int
    last_convergence_latency_ns: int
    max_convergence_latency_ns: int
    stopped: bool


def _debounce_ms_from_env() -> float:
    raw = os.environ.get("MATRYCA_WATCH_DEBOUNCE_MS", str(_DEFAULT_DEBOUNCE_MS)).strip()
    try:
        ms = int(raw)
    except ValueError:
        ms = _DEFAULT_DEBOUNCE_MS
    return float(max(_MIN_DEBOUNCE_MS, min(_MAX_DEBOUNCE_MS, ms)) / 1000.0)


def _event_kind(event: FileSystemEvent) -> FileEventKind | None:
    if event.is_directory:
        return None
    if event.event_type == "created":
        return "created"
    if event.event_type == "modified":
        return "modified"
    if event.event_type == "deleted":
        return "deleted"
    return None


class _DebouncedMarkdownHandler(FileSystemEventHandler):
    def __init__(
        self,
        graph_root: Path,
        *,
        debounce_s: float,
        on_debounced: Callable[[Path, FileEventKind], None],
    ) -> None:
        super().__init__()
        self._graph_root = graph_root
        self._debounce_s = debounce_s
        self._on_debounced = on_debounced
        # Single background scheduler with per-file monotonic deadlines, instead of one
        # threading.Timer per file: a bulk change (sync-client re-download, mass tag
        # rewrite) touching thousands of files would otherwise spawn thousands of OS
        # threads at once (F5, TRIZ Principle 20: continuous action / partial-excessive).
        self._pending: dict[str, tuple[float, float, Path, FileEventKind]] = {}
        self._lock = threading.Lock()
        self._wake = threading.Condition(self._lock)
        self._stopped = False
        self._scheduled_count = 0
        self._coalesced_count = 0
        self._dispatched_count = 0
        self._callback_failure_count = 0
        self._last_convergence_latency_ns = 0
        self._max_convergence_latency_ns = 0
        self._worker = threading.Thread(
            target=self._run, name="matryca-watch-debounce", daemon=True
        )
        self._worker.start()

    def _schedule(self, path: Path, kind: FileEventKind) -> None:
        key = str(path)
        now = time.monotonic()
        deadline = now + self._debounce_s
        with self._wake:
            previous = self._pending.get(key)
            first_seen = previous[1] if previous is not None else now
            self._scheduled_count += 1
            if previous is not None:
                self._coalesced_count += 1
            self._pending[key] = (deadline, first_seen, path, kind)
            self._wake.notify_all()

    def _run(self) -> None:
        with self._wake:
            while not self._stopped:
                if not self._pending:
                    self._wake.wait()
                    continue
                now = time.monotonic()
                next_deadline = min(deadline for deadline, _, _, _ in self._pending.values())
                if next_deadline > now:
                    self._wake.wait(timeout=next_deadline - now)
                    continue
                due = [
                    (key, first_seen, path, kind)
                    for key, (deadline, first_seen, path, kind) in self._pending.items()
                    if deadline <= now
                ]
                for key, _, _, _ in due:
                    del self._pending[key]
                if not due:
                    continue
                self._wake.release()
                completed: list[tuple[int, bool]] = []
                try:
                    for _, first_seen, path, kind in due:
                        failed = False
                        try:
                            self._on_debounced(path, kind)
                        except Exception:  # noqa: BLE001
                            failed = True
                            logger.exception("Debounced file watcher callback failed for {}", path)
                        finally:
                            latency_ns = max(0, int((time.monotonic() - first_seen) * 1e9))
                            completed.append((latency_ns, failed))
                finally:
                    self._wake.acquire()
                    for latency_ns, failed in completed:
                        self._dispatched_count += 1
                        self._callback_failure_count += int(failed)
                        self._last_convergence_latency_ns = latency_ns
                        self._max_convergence_latency_ns = max(
                            self._max_convergence_latency_ns, latency_ns
                        )

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._handle_path(getattr(event, "src_path", None), "deleted")
        self._handle_path(getattr(event, "dest_path", None), "created")

    def _handle(self, event: FileSystemEvent) -> None:
        kind = _event_kind(event)
        if kind is None:
            return
        self._handle_path(getattr(event, "src_path", None), kind)

    def _handle_path(self, src: str | None, kind: FileEventKind) -> None:
        if not src:
            return
        path = Path(src)
        if path.suffix.lower() != ".md":
            return
        try:
            safe = assert_path_within_graph(path, self._graph_root)
        except Exception:  # noqa: BLE001
            return
        if kind != "deleted" and not is_scannable_graph_markdown(safe, self._graph_root):
            return
        self._schedule(safe, kind)

    def cancel_all(self) -> None:
        with self._wake:
            self._stopped = True
            self._pending.clear()
            self._wake.notify_all()
        self._worker.join(timeout=2.0)

    def diagnostics_snapshot(self) -> WatcherDiagnosticsSnapshot:
        """Return a path-free snapshot under the existing scheduler lock."""
        now = time.monotonic()
        with self._wake:
            oldest_age_ns = max(
                (
                    max(0, int((now - first_seen) * 1e9))
                    for _, first_seen, _, _ in self._pending.values()
                ),
                default=0,
            )
            return WatcherDiagnosticsSnapshot(
                schema_version=1,
                pending_count=len(self._pending),
                scheduled_count=self._scheduled_count,
                coalesced_count=self._coalesced_count,
                dispatched_count=self._dispatched_count,
                callback_failure_count=self._callback_failure_count,
                oldest_pending_age_ns=oldest_age_ns,
                last_convergence_latency_ns=self._last_convergence_latency_ns,
                max_convergence_latency_ns=self._max_convergence_latency_ns,
                stopped=self._stopped,
            )


class GraphFileWatcher:
    """Watch ``pages/`` and ``journals/`` under a Logseq graph root."""

    def __init__(
        self,
        graph_root: Path,
        *,
        on_debounced_change: Callable[[Path, FileEventKind], None],
        debounce_s: float | None = None,
    ) -> None:
        self._graph_root = graph_root.expanduser().resolve(strict=False)
        self._on_debounced_change = on_debounced_change
        self._debounce_s = debounce_s if debounce_s is not None else _debounce_ms_from_env()
        self._observer: _FilesystemObserver | None = None
        self._handler: _DebouncedMarkdownHandler | None = None

    def start(self) -> None:
        if self._observer is not None:
            return
        handler = _DebouncedMarkdownHandler(
            self._graph_root,
            debounce_s=self._debounce_s,
            on_debounced=self._on_debounced_change,
        )
        observer = Observer()
        for subdir in ("pages", "journals"):
            watch_path = self._graph_root / subdir
            if watch_path.is_dir():
                observer.schedule(handler, str(watch_path), recursive=True)
                logger.bind(path=str(watch_path)).info("Watching graph markdown directory")
        observer.start()
        self._handler = handler
        self._observer = observer

    def stop(self) -> None:
        if self._handler is not None:
            self._handler.cancel_all()
            self._handler = None
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

    def diagnostics_snapshot(self) -> WatcherDiagnosticsSnapshot:
        """Return current debounce diagnostics without exposing graph paths."""
        if self._handler is None:
            return WatcherDiagnosticsSnapshot(1, 0, 0, 0, 0, 0, 0, 0, 0, True)
        return self._handler.diagnostics_snapshot()


__all__ = ["FileEventKind", "GraphFileWatcher", "WatcherDiagnosticsSnapshot"]
