"""Finite protocol behavior, independent of OS process semantics."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from src.agent.dashboard_protocol import (
    DashboardFrame,
    DashboardIntent,
    DashboardLimits,
    DashboardOutcome,
    DashboardRequest,
    PhaseReader,
    decode_document,
    decode_frame,
)
from src.config import MatrycaWikiConfig

REQUEST = "a" * 32
PHASES = ["discover", "stat", "load_ast", "ids", "refs", "format", "complete"]


@pytest.mark.parametrize("value", [True, 0.0, -1.0, float("nan"), float("inf"), 1801.0])
def test_limits_reject_invalid_execution_budget(value: object) -> None:
    with pytest.raises(ValidationError):
        DashboardLimits.model_validate({"execution_s": value})


def test_limits_are_immutable_and_reject_larger_or_coerced_output_limits() -> None:
    limits = DashboardLimits()
    with pytest.raises(ValidationError):
        limits.execution_s = 4.0
    for value in (True, "256", 262145):
        with pytest.raises(ValidationError):
            DashboardLimits.model_validate({"stdout_bytes": value})


@pytest.mark.parametrize("document", [b"{}{}", b'{"x":1,"x":2}', b"NaN", b'"\xff"'])
def test_wire_rejects_duplicate_multiple_nonfinite_and_invalid_utf8(document: bytes) -> None:
    with pytest.raises(ValueError):
        decode_document(document)


def test_protocol_rejects_command_injection_and_bool_version() -> None:
    for extra in ({"command": "anything"}, {"schema_version": True}):
        with pytest.raises(ValidationError):
            DashboardRequest.model_validate(
                {"request_id": REQUEST, "graph_root": "/synthetic", "wiki_config": {}, **extra}
            )


def test_dashboard_protocol_rejects_mismatched_or_duplicate_terminal() -> None:
    data = DashboardFrame(request_id=REQUEST, kind="ok", markdown="- outline").model_dump_json()
    with pytest.raises(ValueError):
        decode_frame(data.encode(), "b" * 32, complete=True)
    with pytest.raises(ValueError):
        decode_frame((data + data).encode(), REQUEST, complete=True)
    with pytest.raises(ValueError):
        decode_frame(data.encode(), REQUEST, complete=False)


@pytest.mark.parametrize("sequence", [["stat"], ["discover", "discover"], PHASES + ["complete"]])
def test_phase_reader_rejects_unknown_duplicate_or_out_of_order(sequence: list[str]) -> None:
    reader = PhaseReader()
    with pytest.raises(ValueError):
        for phase in sequence:
            reader.feed(json.dumps({"phase": phase}).encode() + b"\n")


def test_phase_records_are_incremental_bounded_and_complete_only_at_eof() -> None:
    reader = PhaseReader()
    data = b"".join(json.dumps({"phase": phase}).encode() + b"\n" for phase in PHASES)
    for byte in data:
        reader.feed(bytes([byte]))
    assert reader.complete
    assert reader.last_phase == "complete"
    reader.feed(b" ")
    with pytest.raises(ValueError):
        reader.finish()
    with pytest.raises(ValueError):
        PhaseReader().feed(b"x" * 1025)


def test_dashboard_public_diagnostics_are_content_free() -> None:
    marker = "/private/synthetic-secret"
    intent = DashboardIntent(
        request_id=REQUEST, raw_graph_path=marker, wiki_config=MatrycaWikiConfig()
    )
    outcome = DashboardOutcome(
        code="dashboard_timeout",
        last_phase="refs",
        elapsed_ms=120000,
        cleanup_verified=True,
        markdown=marker,
    )
    assert marker not in repr(intent)
    assert marker not in repr(outcome)
    body = outcome.public_text()
    assert marker not in body
    assert len(body.encode()) < 4096
    assert json.loads(body) == {
        "ok": False,
        "code": "dashboard_timeout",
        "last_phase": "refs",
        "elapsed_ms": 120000,
        "cleanup_verified": True,
    }
