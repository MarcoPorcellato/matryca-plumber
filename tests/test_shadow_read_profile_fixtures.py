"""Frozen, content-free v1 Shadow read-profile fixture corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from src.shadow.state_api import ShadowDbStateResponse

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "shadow_read_profile"
FIXTURE_NAMES = {
    "healthy_v1.json",
    "malformed_payload.json",
    "unsupported_future_profile.json",
    "unhealthy_not_ready.json",
    "foreign_binding.json",
}
FORBIDDEN_KEYS = {"path", "content", "rows", "query", "sql", "secret"}


def _load(name: str) -> dict[str, object]:
    payload = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"fixture {name} must be a JSON object")
    return cast(dict[str, object], payload)


def test_fixture_corpus_is_complete_and_content_free() -> None:
    assert {path.name for path in FIXTURE_DIR.glob("*.json")} == FIXTURE_NAMES
    for name in FIXTURE_NAMES:
        payload = _load(name)
        assert not (set(payload) & FORBIDDEN_KEYS)
        profile = payload.get("read_profile")
        if isinstance(profile, dict):
            assert not (set(profile) & FORBIDDEN_KEYS)


def test_healthy_fixture_matches_closed_v1_contract() -> None:
    snapshot = ShadowDbStateResponse.model_validate(_load("healthy_v1.json"))

    assert snapshot.read_profile is not None
    assert snapshot.read_profile.profile == "shadow-read-profile"
    assert snapshot.read_profile.version == 1
    assert snapshot.read_profile.ready is True
    assert snapshot.read_profile.schema_compatible is True
    assert snapshot.read_profile.capabilities == ("state",)


@pytest.mark.parametrize(
    "fixture_name",
    ["malformed_payload.json", "unsupported_future_profile.json"],
)
def test_invalid_contract_fixtures_do_not_validate(fixture_name: str) -> None:
    with pytest.raises(ValidationError):
        ShadowDbStateResponse.model_validate(_load(fixture_name))


def test_unhealthy_and_foreign_fixtures_remain_explicit_admission_cases() -> None:
    unhealthy = ShadowDbStateResponse.model_validate(_load("unhealthy_not_ready.json"))
    foreign = ShadowDbStateResponse.model_validate(_load("foreign_binding.json"))

    assert unhealthy.read_profile is not None
    assert unhealthy.read_profile.ready is False
    assert foreign.read_profile is not None
    assert foreign.read_profile.graph_id != "v1-expected"
