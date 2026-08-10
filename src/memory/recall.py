"""Deterministic, read-only canonical recall envelope for Memory P0 (#186)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..graph.path_sandbox import PathTraversalSecurityError, resolved_graph_root
from ..shadow.connection import open_shadow_db_query_only
from ..shadow.freshness import ShadowFreshnessError, ensure_shadow_page_fresh
from ..shadow.fts_validation import (
    MAX_FTS_MATCH_QUERY_CHARS,
    FtsQueryValidationError,
    validate_fts_match_query,
)
from ..shadow.health import ShadowHealthState, resolve_shadow_health
from ..shadow.meta import META_GENERATION, get_meta
from ..shadow.query import BlockHit, search_blocks_fts
from ..shadow.schema import SHADOW_SCHEMA_VERSION
from .config import memory_graph_enabled

RECALL_SCHEMA_VERSION = "recall-bundle.v1"
RECALL_INSTRUCTION_VERSION = "recall-v1"
RECALL_INDEX_VERSION = f"shadow-fts5/schema-{SHADOW_SCHEMA_VERSION}"
MAX_RECALL_RESULTS_PER_TURN = 50
MAX_RECALL_REQUEST_CHARS = 4_096
MAX_RECALL_FILTER_ENTRIES = 16
MAX_RECALL_FILTER_KEY_CHARS = 128
MAX_RECALL_FILTER_VALUE_CHARS = 256

RecallState = Literal["completed", "disabled", "unavailable"]


class RecallResultRef(BaseModel):
    """Content-free identity of one recalled canonical block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    block_uuid: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecallVolatileMetadata(BaseModel):
    """Observability only; excluded from the reusable fingerprint prefix."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank_scores: tuple[float, ...] = ()
    elapsed_ms: float = Field(ge=0)


class RecallBundle(BaseModel):
    """Provider-neutral result envelope with a deterministic cache identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = RECALL_SCHEMA_VERSION
    state: RecallState
    code: str
    graph_generation: int | None = Field(default=None, ge=0)
    normalized_query: str
    method: Literal["recall"] = "recall"
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(ge=1, le=MAX_RECALL_RESULTS_PER_TURN)
    embedding_index_version: str = RECALL_INDEX_VERSION
    retrieval_instruction_version: str = RECALL_INSTRUCTION_VERSION
    results: tuple[RecallResultRef, ...] = ()
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    no_progress_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    per_turn_expansion_budget: int = Field(ge=1, le=MAX_RECALL_RESULTS_PER_TURN)
    volatile: RecallVolatileMetadata | None = None

    def cache_stable_prefix(self) -> dict[str, Any]:
        """Return the exact content-addressed fields that define reusable recall."""
        return {
            "schema_version": self.schema_version,
            "state": self.state,
            "code": self.code,
            "graph_generation": self.graph_generation,
            "normalized_query": self.normalized_query,
            "method": self.method,
            "filters": self.filters,
            "limit": self.limit,
            "embedding_index_version": self.embedding_index_version,
            "retrieval_instruction_version": self.retrieval_instruction_version,
            "results": [item.model_dump(mode="json") for item in self.results],
            "per_turn_expansion_budget": self.per_turn_expansion_budget,
        }


@dataclass(frozen=True, slots=True)
class RecallRequest:
    """Validated request controls that must bind the recall fingerprint."""

    normalized_query: str
    filters: dict[str, Any]
    limit: int


def normalize_recall_query(query: str) -> str:
    """Conservatively normalize only whitespace; FTS syntax and case are preserved."""
    return " ".join(query.split())


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _bundle(
    *,
    state: RecallState,
    code: str,
    request: RecallRequest,
    graph_generation: int | None = None,
    results: tuple[RecallResultRef, ...] = (),
    volatile: RecallVolatileMetadata | None = None,
) -> RecallBundle:
    stable = {
        "schema_version": RECALL_SCHEMA_VERSION,
        "state": state,
        "code": code,
        "graph_generation": graph_generation,
        "normalized_query": request.normalized_query,
        "method": "recall",
        "filters": request.filters,
        "limit": request.limit,
        "embedding_index_version": RECALL_INDEX_VERSION,
        "retrieval_instruction_version": RECALL_INSTRUCTION_VERSION,
        "results": [item.model_dump(mode="json") for item in results],
        "per_turn_expansion_budget": MAX_RECALL_RESULTS_PER_TURN,
    }
    fingerprint = _digest(stable)
    return RecallBundle(
        schema_version=RECALL_SCHEMA_VERSION,
        state=state,
        code=code,
        graph_generation=graph_generation,
        normalized_query=request.normalized_query,
        filters=request.filters,
        limit=request.limit,
        embedding_index_version=RECALL_INDEX_VERSION,
        retrieval_instruction_version=RECALL_INSTRUCTION_VERSION,
        results=results,
        fingerprint=fingerprint,
        no_progress_signature=_digest(
            {"protocol": "recall-no-progress.v1", "fingerprint": fingerprint}
        ),
        per_turn_expansion_budget=MAX_RECALL_RESULTS_PER_TURN,
        volatile=volatile,
    )


def _request_from_query(query: str) -> RecallRequest:
    raw = query.strip()
    if len(raw) > MAX_RECALL_REQUEST_CHARS:
        raise ValueError("recall request exceeds the bounded input size")
    options: dict[str, Any] = {}
    if raw.startswith("{"):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise TypeError("recall query JSON must be an object")
        options = parsed
    text = str(options.get("query", options.get("keyword", raw))).strip()
    filters = options.get("filters", {})
    if not isinstance(filters, dict):
        raise TypeError("recall filters must be an object")
    if len(filters) > MAX_RECALL_FILTER_ENTRIES:
        raise ValueError("recall filters exceed the bounded entry count")
    for key, value in filters.items():
        if not isinstance(key, str) or len(key) > MAX_RECALL_FILTER_KEY_CHARS:
            raise TypeError("recall filter keys must be bounded strings")
        if not isinstance(value, (str, int, bool)) and value is not None:
            raise TypeError("recall filter values must be scalar")
        if isinstance(value, str) and len(value) > MAX_RECALL_FILTER_VALUE_CHARS:
            raise ValueError("recall filter values must be bounded strings")
    raw_limit = options.get("limit", 15)
    if type(raw_limit) is not int:
        raise TypeError("recall limit must be an integer")
    limit = raw_limit
    if not 1 <= limit <= MAX_RECALL_RESULTS_PER_TURN:
        raise ValueError(f"recall limit must be between 1 and {MAX_RECALL_RESULTS_PER_TURN}")
    normalized_query = normalize_recall_query(text)
    if len(normalized_query) > MAX_FTS_MATCH_QUERY_CHARS:
        raise ValueError("recall query exceeds the FTS input limit")
    return RecallRequest(normalized_query=normalized_query, filters=filters, limit=limit)


def _safe_request(query: str) -> RecallRequest:
    """Produce a bounded identity even when a disabled request is malformed."""
    return RecallRequest(
        normalized_query=normalize_recall_query(query[:MAX_RECALL_REQUEST_CHARS]),
        filters={},
        limit=15,
    )


def _require_generation(connection: sqlite3.Connection) -> int:
    """Read a persisted generation without silently repairing malformed metadata."""
    raw = get_meta(connection, META_GENERATION)
    if raw is None or not raw.isdecimal():
        raise ValueError("recall generation metadata is invalid")
    return int(raw)


def _unavailable(code: str, request: RecallRequest) -> RecallBundle:
    return _bundle(state="unavailable", code=code, request=request)


def _completed_bundle(
    request: RecallRequest,
    generation: int,
    hits: list[BlockHit],
    elapsed_ms: float,
) -> RecallBundle:
    ordered = sorted(hits, key=lambda hit: (hit.rank, hit.block_uuid))
    refs = tuple(
        RecallResultRef(
            block_uuid=hit.block_uuid,
            content_hash=hashlib.sha256(hit.content.encode("utf-8")).hexdigest(),
        )
        for hit in ordered
    )
    return _bundle(
        state="completed",
        code="recall_completed",
        request=request,
        graph_generation=generation,
        results=refs,
        volatile=RecallVolatileMetadata(
            rank_scores=tuple(hit.rank for hit in ordered),
            elapsed_ms=elapsed_ms,
        ),
    )


def recall_from_existing_retrieval(graph_path: str, query: str = "") -> RecallBundle:
    """Build a gated canonical envelope from the existing read-only Shadow FTS path.

    P0 deliberately never changes retrieval method: an unavailable Shadow cache,
    stale source row, empty result, or unsupported filter returns an explicit state
    instead of falling back to page-level BM25 or a provider/model path.
    """
    if not memory_graph_enabled():
        return _bundle(state="disabled", code="recall_disabled", request=_safe_request(query))
    try:
        request = _request_from_query(query)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _unavailable("recall_invalid_request", _safe_request(query))
    if not request.normalized_query:
        return _unavailable("recall_query_required", request)
    if request.filters:
        return _unavailable("recall_filters_unsupported", request)
    if not graph_path.strip():
        return _unavailable("recall_graph_unavailable", request)
    try:
        root = resolved_graph_root(graph_path)
        if resolve_shadow_health(root) is not ShadowHealthState.READY:
            return _unavailable("recall_shadow_unavailable", request)
        validate_fts_match_query(request.normalized_query)
        started = time.perf_counter()
        conn = open_shadow_db_query_only(root)
        try:
            generation = _require_generation(conn)
            hits = search_blocks_fts(conn, request.normalized_query, limit=request.limit)
            if not hits:
                return _unavailable("recall_empty_result_unproven", request)
            for page_id in sorted({hit.page_id for hit in hits}):
                ensure_shadow_page_fresh(conn, root, page_id=page_id)
        finally:
            conn.close()
    except FtsQueryValidationError:
        return _unavailable("recall_query_invalid", request)
    except (ShadowFreshnessError, ValueError):
        return _unavailable("recall_freshness_unproven", request)
    except (OSError, RuntimeError, sqlite3.Error, PathTraversalSecurityError):
        return _unavailable("recall_shadow_unavailable", request)
    return _completed_bundle(request, generation, hits, (time.perf_counter() - started) * 1_000)


__all__ = [
    "MAX_RECALL_RESULTS_PER_TURN",
    "MAX_RECALL_REQUEST_CHARS",
    "RECALL_INDEX_VERSION",
    "RECALL_INSTRUCTION_VERSION",
    "RECALL_SCHEMA_VERSION",
    "RecallBundle",
    "RecallRequest",
    "RecallResultRef",
    "RecallVolatileMetadata",
    "normalize_recall_query",
    "recall_from_existing_retrieval",
]
