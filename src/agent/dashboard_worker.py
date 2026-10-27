"""One-shot dashboard computation, confined to its request-owned process group."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

from ..graph.bounded_page_parse import get_bounded_page_parse_worker
from ..graph.dashboard import DashboardPhase, build_dashboard_markdown
from .dashboard_protocol import DashboardFrame, DashboardLimits, DashboardRequest, decode_document
from .llm_context_payload import cap_llm_payload_chars


def _emit_phase(phase: DashboardPhase) -> None:
    import json

    record = json.dumps({"phase": phase}, separators=(",", ":")).encode("ascii") + b"\n"
    sys.stderr.buffer.write(record)
    sys.stderr.buffer.flush()


def main() -> int:
    """Consume one bounded request; shut down private parsing before any result."""
    logger.remove()
    os.environ["MATRYCA_READ_ONLY"] = "true"
    os.environ["MATRYCA_DEBUG"] = "false"
    limits = DashboardLimits()
    request: DashboardRequest | None = None
    frame: DashboardFrame | None = None
    failed = False
    try:
        raw = sys.stdin.buffer.read(limits.request_bytes + 1)
        if len(raw) > limits.request_bytes:
            return 2
        request = DashboardRequest.model_validate(decode_document(raw))
        root = Path(request.graph_root)
        if not root.is_absolute() or root.resolve(strict=True) != root or not root.is_dir():
            return 2
        os.environ["LOGSEQ_GRAPH_PATH"] = str(root)
        markdown = build_dashboard_markdown(root, request.wiki_config, on_phase=_emit_phase)
        from ..daemon.config_layer import append_identity_to_mcp_payload

        # Preserve the established body-cap-then-identity order inside this job.
        markdown = cap_llm_payload_chars(markdown)
        if request.include_identity:
            with_identity = append_identity_to_mcp_payload(markdown)
            if not isinstance(with_identity, str):
                raise ValueError("invalid dashboard identity result")
            markdown = with_identity
        frame = DashboardFrame(request_id=request.request_id, kind="ok", markdown=markdown)
    except BaseException:
        failed = True
    finally:
        # This singleton belongs to this disposable process, never the MCP parent.
        try:
            get_bounded_page_parse_worker().shutdown()
        except BaseException:
            failed = True
    if request is None:
        return 2
    if failed or frame is None:
        frame = DashboardFrame(
            request_id=request.request_id, kind="error", code="dashboard_worker_failed"
        )
    encoded = frame.model_dump_json(exclude_none=True).encode("utf-8")
    if len(encoded) > limits.stdout_bytes:
        encoded = (
            DashboardFrame(
                request_id=request.request_id, kind="error", code="dashboard_output_overflow"
            )
            .model_dump_json(exclude_none=True)
            .encode("utf-8")
        )
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
