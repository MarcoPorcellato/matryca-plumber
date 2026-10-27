"""Finite, content-private protocol for the request-owned dashboard worker."""

from __future__ import annotations

import json
import math
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..config import MatrycaWikiConfig
from ..graph.dashboard import DashboardPhase

DashboardCode = Literal[
    "dashboard_timeout",
    "dashboard_busy",
    "dashboard_worker_failed",
    "dashboard_protocol_error",
    "dashboard_output_overflow",
    "dashboard_cleanup_unverified",
    "dashboard_platform_unsupported",
]
PHASES: tuple[DashboardPhase, ...] = (
    "discover",
    "stat",
    "load_ast",
    "ids",
    "refs",
    "format",
    "complete",
)


class DashboardLimits(BaseModel):
    """Production ceilings; only internal tests may inject smaller budgets."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    execution_s: float = Field(default=1800.0, gt=0, le=1800)
    cleanup_s: float = Field(default=5.0, gt=0, le=5)
    poll_s: float = Field(default=0.05, gt=0, le=0.1)
    request_bytes: int = Field(default=65_536, gt=0, le=65_536)
    stdout_bytes: int = Field(default=262_144, gt=0, le=262_144)
    stderr_bytes: int = Field(default=4_096, gt=0, le=4_096)

    @field_validator("execution_s", "cleanup_s", "poll_s", mode="before")
    @classmethod
    def finite_duration(cls, value: object) -> object:
        if (
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
        ):
            raise ValueError("invalid dashboard duration")
        return value


class DashboardIntent(BaseModel):
    """Data only: construction performs no graph I/O or serialization."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    raw_graph_path: str = Field(repr=False)
    wiki_config: MatrycaWikiConfig = Field(repr=False)
    include_identity: bool = False


class DashboardRequest(BaseModel):
    """One bounded canonical-root projection, never executable instructions."""

    model_config = ConfigDict(strict=True, extra="forbid")
    schema_version: Literal[1] = 1
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    graph_root: str = Field(min_length=1, repr=False)
    wiki_config: MatrycaWikiConfig = Field(repr=False)
    include_identity: bool = False

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("invalid protocol version type")
        return value


class DashboardFrame(BaseModel):
    """Exactly one correlated terminal frame; no raw exception payloads."""

    model_config = ConfigDict(strict=True, extra="forbid")
    schema_version: Literal[1] = 1
    request_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    kind: Literal["ok", "error"]
    markdown: str | None = Field(default=None, repr=False)
    code: DashboardCode | None = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        return DashboardRequest.integer_version(value)

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if self.kind == "ok":
            if self.markdown is None or self.code is not None:
                raise ValueError("invalid success frame")
        elif self.markdown is not None or self.code is None:
            raise ValueError("invalid failure frame")
        return self


class DashboardOutcome(BaseModel):
    """Content-free lifecycle result, with private successful content."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    code: DashboardCode | None = None
    last_phase: DashboardPhase | None = None
    elapsed_ms: int = Field(ge=0)
    cleanup_verified: bool
    markdown: str | None = Field(default=None, repr=False)

    def public_text(self) -> str:
        """Return content only after complete success; failures have fixed fields."""
        if self.code is None and self.cleanup_verified and self.markdown is not None:
            return self.markdown
        return json.dumps(
            {
                "ok": False,
                "code": self.code or "dashboard_cleanup_unverified",
                "last_phase": self.last_phase,
                "elapsed_ms": self.elapsed_ms,
                "cleanup_verified": self.cleanup_verified,
            },
            separators=(",", ":"),
        )


def decode_document(data: bytes) -> object:
    """Decode one JSON value, rejecting duplicate keys and non-finite numbers."""

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate protocol field")
            result[key] = value
        return result

    def reject_constant(_value: str) -> object:
        raise ValueError("non-finite protocol value")

    return json.loads(
        data.decode("utf-8", errors="strict"),
        object_pairs_hook=unique,
        parse_constant=reject_constant,
    )


def decode_frame(data: bytes, request_id: str, *, complete: bool) -> DashboardFrame:
    """Verify correlation and stage completion after bounded capture and EOF."""
    frame = DashboardFrame.model_validate(decode_document(data))
    if frame.request_id != request_id or (frame.kind == "ok" and not complete):
        raise ValueError("uncorrelated or incomplete dashboard response")
    return frame


class PhaseReader:
    """Incrementally validate the bounded stderr stage-entry channel."""

    def __init__(self) -> None:
        self.pending = bytearray()
        self.count = 0

    @property
    def last_phase(self) -> DashboardPhase | None:
        return PHASES[self.count - 1] if self.count else None

    @property
    def complete(self) -> bool:
        return self.count == len(PHASES) and not self.pending

    def feed(self, data: bytes) -> None:
        self.pending.extend(data)
        while b"\n" in self.pending:
            line, _, rest = self.pending.partition(b"\n")
            self.pending = bytearray(rest)
            if len(line) > 1024 or self.count >= len(PHASES):
                raise ValueError("invalid phase record bound")
            if decode_document(bytes(line)) != {"phase": PHASES[self.count]}:
                raise ValueError("invalid phase sequence")
            self.count += 1
        if len(self.pending) > 1024:
            raise ValueError("invalid phase record bound")

    def finish(self) -> None:
        if self.pending:
            raise ValueError("truncated phase record")
