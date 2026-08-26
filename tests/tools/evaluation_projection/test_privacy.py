"""Tests for the evaluation-projection privacy boundary."""

from __future__ import annotations

import pytest
from tools.evaluation_projection.privacy import (
    ProjectionPrivacyError,
    assert_projection_private,
)


@pytest.mark.parametrize(
    "payload",
    [
        {"content": "private note"},
        {"nested": {"prompt": "secret prompt"}},
        {"nested": [{"path": "/private/tmp/graph"}]},
        {"nested": {"value": "file:///Users/example/graph.md"}},
        {"nested": {"value": "person@example.com"}},
        {"nested": {"value": "Authorization: Bearer secret"}},
        {"nested": {"timestamp": "2026-08-26T10:00:00Z"}},
    ],
)
def test_guard_rejects_nested_forbidden_content_without_echo(payload: object) -> None:
    """Reject keys and values that can carry private evaluation content."""
    with pytest.raises(ProjectionPrivacyError) as caught:
        assert_projection_private(payload)

    assert str(caught.value) in {"privacy_key_forbidden", "privacy_value_forbidden"}
    assert "secret" not in str(caught.value)
    assert "/private/" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"source_revision": "a" * 40},
        {"digest": "b" * 64},
        {"failure_codes": ["first-failure"]},
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
