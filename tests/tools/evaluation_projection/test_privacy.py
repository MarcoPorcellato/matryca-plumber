"""Tests for the evaluation-projection privacy boundary."""

from __future__ import annotations

import pytest
from tools.evaluation_projection.privacy import (
    ProjectionPrivacyError,
    assert_projection_private,
)


@pytest.mark.parametrize(
    ("payload", "expected_code", "private_value"),
    [
        ({"content": "private note"}, "privacy_key_forbidden", "private note"),
        (
            {"metrics": {"context_bytes": "/private/tmp/graph"}},
            "privacy_value_forbidden",
            "/private/tmp/graph",
        ),
        (
            {"metrics": {"context_bytes": "file:///Users/example/graph.md"}},
            "privacy_value_forbidden",
            "file:///Users/example/graph.md",
        ),
        (
            {"metrics": {"context_bytes": "person@example.com"}},
            "privacy_value_forbidden",
            "person@example.com",
        ),
        (
            {"metrics": {"context_bytes": "Authorization: Bearer secret"}},
            "privacy_value_forbidden",
            "Authorization: Bearer secret",
        ),
        (
            {"metrics": {"context_bytes": "2026-08-26T10:00:00Z"}},
            "privacy_value_forbidden",
            "2026-08-26T10:00:00Z",
        ),
    ],
)
def test_guard_rejects_nested_forbidden_content_without_echo(
    payload: object, expected_code: str, private_value: str
) -> None:
    """Reject keys and values that can carry private evaluation content."""
    with pytest.raises(ProjectionPrivacyError) as caught:
        assert_projection_private(payload)

    assert str(caught.value) == expected_code
    assert private_value not in str(caught.value)
    assert "secret" not in str(caught.value)
    assert "/private/" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"source_revision": "a" * 40},
        {"digest": "b" * 64},
        {"scenario": "strict-read-only-success"},
        {"failure_codes": ["first-failure"]},
        {"executed_tool_ids": ["read.graph"]},
        {"passed_check_ids": ["hermeticity.read"]},
        {"failed_check_ids": ["canonical-outcome-failed"]},
        {"roots_distinct": True},
        {"elapsed_milliseconds": 86_400_000},
        {"metrics": {"elapsed_milliseconds": 86_400_000}},
        {"schema_version": "matryca-graph-outcome-evaluation-projection.v1"},
        {"policy_mode": "strict_read_only"},
        {"terminal_status": "completed"},
        {"dimension": "hermeticity"},
        {"validation_status": "passed"},
        {"kind": "outcome-report"},
    ],
)
def test_guard_allows_approved_scalar_families(payload: object) -> None:
    """Preserve schema-approved, non-content scalar families."""
    assert_projection_private(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"unapproved_field": "value"},
        {"scenario": "a" * 64},
        {"digest": "a" * 40},
        {"turns": float("inf")},
        {"turns": b"1"},
    ],
)
def test_guard_fails_closed_for_unapproved_keys_values_and_types(payload: object) -> None:
    """Reject shape escapes that closed Pydantic models might not receive directly."""
    with pytest.raises(ProjectionPrivacyError) as caught:
        assert_projection_private(payload)

    assert str(caught.value) in {
        "privacy_key_forbidden",
        "privacy_type_forbidden",
        "privacy_value_forbidden",
    }
