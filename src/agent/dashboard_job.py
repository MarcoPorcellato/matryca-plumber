"""Async dashboard admission and cooperative cancellation, without signal ownership."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field

import anyio
from loguru import logger

from ..config import MatrycaWikiConfig
from .dashboard_process import DashboardJobControl, run_dashboard_process
from .dashboard_protocol import DashboardIntent, DashboardLimits, DashboardOutcome

# Only the MCP branch sets this application context. CLI/direct reads retain
# their previous body-only output; no query or public option selects this flag.
dashboard_identity_owned: ContextVar[bool] = ContextVar("dashboard_identity_owned", default=False)


@dataclass
class _OwnedJob:
    control: DashboardJobControl
    intent: DashboardIntent
    done: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    outcome: DashboardOutcome | None = None


class _DashboardJobs:
    """One process-local permit; uncertain owners are retained until operator restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: _OwnedJob | None = None
        self._poisoned = False

    @staticmethod
    def _own(job: _OwnedJob, limits: DashboardLimits) -> None:
        try:
            job.outcome = run_dashboard_process(job.intent, limits=limits, control=job.control)
            outcome = job.outcome
            # A slow configured sink is I/O too: it must not block the async caller.
            logger.bind(
                operation="dashboard",
                request_id=job.intent.request_id,
                code=outcome.code,
                phase=outcome.last_phase,
                elapsed_ms=outcome.elapsed_ms,
                cleanup_verified=outcome.cleanup_verified,
            ).info("dashboard read finished")
        except BaseException:
            job.control.begin_cleanup("dashboard_worker_failed")
            if job.outcome is not None and job.outcome.code is None:
                job.outcome = job.outcome.model_copy(
                    update={"code": "dashboard_worker_failed", "markdown": None}
                )
        finally:
            job.done.set()

    @staticmethod
    async def _wait_owner(job: _OwnedJob) -> None:
        control = job.control
        while True:
            if job.done.is_set() and (job.thread is None or not job.thread.is_alive()):
                if job.thread is not None and job.thread.ident is not None:
                    job.thread.join(timeout=0)
                return
            now = time.monotonic()
            if now >= control.execution_deadline:
                control.begin_cleanup("dashboard_timeout")
            deadline = control.cleanup_deadline
            if deadline is not None and now >= deadline:
                return
            remaining = (deadline if deadline is not None else control.execution_deadline) - now
            await asyncio.sleep(min(0.02, max(0.0, remaining)))

    async def read(
        self, graph_path: str, wiki_config: MatrycaWikiConfig, limits: DashboardLimits
    ) -> str:
        with self._lock:
            if self._active is not None:
                return DashboardOutcome(
                    code="dashboard_cleanup_unverified" if self._poisoned else "dashboard_busy",
                    elapsed_ms=0,
                    cleanup_verified=False,
                ).public_text()
            control = DashboardJobControl(limits)
            job = _OwnedJob(
                control,
                DashboardIntent(
                    request_id=uuid.uuid4().hex,
                    raw_graph_path=graph_path,
                    wiki_config=wiki_config,
                    include_identity=dashboard_identity_owned.get(),
                ),
            )
            self._active = job
        cancelled: asyncio.CancelledError | None = None
        try:
            job.thread = threading.Thread(
                target=self._own, args=(job, limits), name="dashboard-owner", daemon=True
            )
            job.thread.start()
        except BaseException:
            control.request_cancel()
            job.done.set()
        try:
            await self._wait_owner(job)
        except asyncio.CancelledError as error:
            cancelled = error
            control.request_cancel()
            # MCP uses level cancellation. Shield its outer cancel scope while
            # preserving explicit repeated asyncio cancellations and the same deadline.
            with anyio.CancelScope(shield=True):
                while True:
                    try:
                        await self._wait_owner(job)
                        break
                    except asyncio.CancelledError:
                        control.request_cancel()
        joined = (
            job.done.is_set()
            and job.thread is not None
            and not job.thread.is_alive()
            and control.cleanup_deadline is not None
            and time.monotonic() < control.cleanup_deadline
        )
        outcome = job.outcome
        verified = joined and outcome is not None and outcome.cleanup_verified
        with self._lock:
            if verified:
                self._active = None
            else:
                self._poisoned = True
        if not verified or outcome is None:
            outcome = DashboardOutcome(
                code="dashboard_cleanup_unverified",
                cleanup_verified=False,
                last_phase=outcome.last_phase if outcome else None,
                elapsed_ms=max(0, int((time.monotonic() - control.started) * 1000)),
            )
        if cancelled is not None:
            raise cancelled
        return outcome.public_text()


_jobs = _DashboardJobs()


async def run_dashboard_read(
    graph_path: str, wiki_config: MatrycaWikiConfig, *, limits: DashboardLimits | None = None
) -> str:
    """Read a dashboard through the sole process-wide request admission state."""
    return await _jobs.read(graph_path, wiki_config, limits or DashboardLimits())
