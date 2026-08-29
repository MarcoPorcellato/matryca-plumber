"""Fail-closed privacy validation for evaluation projection dumps."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

_ALLOWED_KEYS = frozenset(
    {
        "artifacts",
        "cleanup_verified",
        "context_bytes",
        "context_tokens",
        "cost_microunits",
        "digest",
        "dimension",
        "dimensions",
        "elapsed_milliseconds",
        "executed_tool_ids",
        "failed_check_ids",
        "failure_codes",
        "final_canonical_fingerprint",
        "final_derived_fingerprint",
        "initial_canonical_fingerprint",
        "initial_derived_fingerprint",
        "kind",
        "metrics",
        "mutation_calls",
        "no_progress_cycles",
        "passed_check_ids",
        "peak_rss_bytes",
        "policy_mode",
        "projection_id",
        "projections",
        "protocol_schema_version",
        "receipt_id",
        "record_count",
        "rejected_tool_calls",
        "report_id",
        "retries",
        "retrieval_calls",
        "roots_distinct",
        "roots_outside_repository",
        "scenario",
        "schema_version",
        "source_revision",
        "status",
        "suite_id",
        "task_bundle_digest",
        "terminal_status",
        "tool_calls",
        "turns",
        "validation_status",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "answer",
        "annotation",
        "api_key",
        "authorization",
        "content",
        "cookie",
        "database_id",
        "endpoint",
        "environment",
        "hostname",
        "log",
        "model_output",
        "page_name",
        "password",
        "path",
        "prompt",
        "query",
        "raw_output",
        "run_id",
        "secret",
        "stack_trace",
        "timestamp",
        "token",
        "url",
        "username",
    }
)
_ABSOLUTE_POSIX = re.compile(r"^/")
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_CREDENTIAL = re.compile(r"(?i)(authorization|bearer|api[_-]?key|password|secret|token)\s*[:= ]")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
_DIGEST_KEYS = frozenset(
    {
        "digest",
        "final_canonical_fingerprint",
        "final_derived_fingerprint",
        "initial_canonical_fingerprint",
        "initial_derived_fingerprint",
        "projection_id",
        "receipt_id",
        "report_id",
        "suite_id",
        "task_bundle_digest",
    }
)
_BOOLEAN_KEYS = frozenset({"cleanup_verified", "roots_distinct", "roots_outside_repository"})
_INTEGER_KEYS = frozenset(
    {
        "context_bytes",
        "context_tokens",
        "cost_microunits",
        "elapsed_milliseconds",
        "mutation_calls",
        "no_progress_cycles",
        "peak_rss_bytes",
        "record_count",
        "rejected_tool_calls",
        "retries",
        "retrieval_calls",
        "tool_calls",
        "turns",
    }
)
_HEX_40 = re.compile(r"^[0-9a-fA-F]{40}$")
_HEX_64 = re.compile(r"^[0-9a-fA-F]{64}$")
_NON_SNAKE_CASE = re.compile(r"[^a-z0-9]+")
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class ProjectionPrivacyError(ValueError):
    """Stable, value-free privacy error for an unsafe projection dump."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _normalized_key(value: str) -> str:
    snake_case = _CAMEL_CASE_BOUNDARY.sub("_", value).lower()
    return _NON_SNAKE_CASE.sub("_", snake_case).strip("_")


def _reject_key(key: object) -> str:
    if not isinstance(key, str):
        raise ProjectionPrivacyError("privacy_type_forbidden")
    normalized = _normalized_key(key)
    if normalized in _FORBIDDEN_KEYS or normalized not in _ALLOWED_KEYS:
        raise ProjectionPrivacyError("privacy_key_forbidden")
    return normalized


def _assert_string_private(value: str, field: str | None) -> None:
    if (
        _ABSOLUTE_POSIX.match(value)
        or _WINDOWS_PATH.match(value)
        or _EMAIL.match(value)
        or _URI.match(value)
        or _CREDENTIAL.search(value)
        or _TIMESTAMP.match(value)
    ):
        raise ProjectionPrivacyError("privacy_value_forbidden")
    if _HEX_64.fullmatch(value) and field not in _DIGEST_KEYS:
        raise ProjectionPrivacyError("privacy_value_forbidden")
    if _HEX_40.fullmatch(value) and field != "source_revision":
        raise ProjectionPrivacyError("privacy_value_forbidden")


def _assert_projection_private(value: object, field: str | None) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            _assert_projection_private(nested_value, _reject_key(key))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _assert_projection_private(item, field)
        return
    if isinstance(value, (bytes, bytearray, Path)):
        raise ProjectionPrivacyError("privacy_type_forbidden")
    if isinstance(value, bool):
        if field not in _BOOLEAN_KEYS:
            raise ProjectionPrivacyError("privacy_type_forbidden")
        return
    if isinstance(value, int):
        if field not in _INTEGER_KEYS or value < 0:
            raise ProjectionPrivacyError("privacy_value_forbidden")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProjectionPrivacyError("privacy_value_forbidden")
        raise ProjectionPrivacyError("privacy_type_forbidden")
    if isinstance(value, str):
        _assert_string_private(value, field)
        return
    raise ProjectionPrivacyError("privacy_type_forbidden")


def assert_projection_private(value: object) -> None:
    """Reject data outside the closed, non-content evaluation projection contract."""
    _assert_projection_private(value, None)
