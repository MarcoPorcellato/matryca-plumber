"""Tests for the deterministic Commit CI Preflight savings ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from scripts.ccp_savings_report import (
    LedgerError,
    load_records,
    promotion_status,
    render_markdown,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "ccp-savings"


def _load_fixture(name: str) -> dict[str, object]:
    loaded = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return cast(dict[str, object], loaded)


def _write_record(root: Path, name: str, record: dict[str, object]) -> None:
    observations = root / "observations"
    observations.mkdir(parents=True, exist_ok=True)
    (observations / name).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_valid_records_are_sorted_and_summarized_without_cherry_picking(tmp_path: Path) -> None:
    eligible = _load_fixture("valid-eligible-pr.json")
    fallback = _load_fixture("valid-fallback.json")
    failed = dict(eligible)
    failed.update(
        record_id="2026-08-25-pr-701-failed",
        classification="failed",
        captured_at="2026-08-25T14:00:00Z",
        pr_number=701,
        comparability="fail",
        estimated_avoided_hosted_seconds=None,
        estimated_net_hosted_seconds_saved=None,
    )
    _write_record(tmp_path, "z-failed.json", failed)
    _write_record(tmp_path, "b-fallback.json", fallback)
    _write_record(tmp_path, "a-eligible.json", eligible)

    records = load_records(tmp_path)
    assert [record.record_id for record in records] == sorted(
        record.record_id for record in records
    )
    summary = summarize(records)
    assert summary["record_count"] == 3
    assert summary["eligible_count"] == 1
    assert summary["fallback_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["candidate_hosted_seconds"] == 319
    assert summary["verifier_seconds"] == 50
    assert summary["net_estimated_seconds_saved"] == 269


def test_net_savings_is_clamped_at_zero_and_declared_value_must_match(tmp_path: Path) -> None:
    record = _load_fixture("valid-eligible-pr.json")
    record["observed_verifier_seconds"] = 400
    record["estimated_net_hosted_seconds_saved"] = 0
    _write_record(tmp_path, "valid-clamped.json", record)
    assert summarize(load_records(tmp_path))["net_estimated_seconds_saved"] == 0

    record["estimated_net_hosted_seconds_saved"] = -81
    _write_record(tmp_path, "invalid-negative.json", record)
    with pytest.raises(LedgerError, match="estimated_net_hosted_seconds_saved"):
        load_records(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_sha", "ABC", "source_sha"),
        ("pr_number", 0, "pr_number"),
        ("captured_at", "2026-08-24", "captured_at"),
        ("candidate_hosted_seconds", 90000, "candidate_hosted_seconds"),
    ],
)
def test_closed_validation_rejects_malformed_identity_and_bounds(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    record = _load_fixture("valid-eligible-pr.json")
    record[field] = value
    _write_record(tmp_path, "invalid.json", record)
    with pytest.raises(LedgerError, match=message):
        load_records(tmp_path)


def test_billing_claim_requires_independent_source_binding(tmp_path: Path) -> None:
    _write_record(tmp_path, "invalid-billing.json", _load_fixture("invalid-billing-claim.json"))
    with pytest.raises(LedgerError, match="billing_source"):
        load_records(tmp_path)


def test_render_is_byte_stable_and_keeps_baseline_separate() -> None:
    records = load_records(ROOT / "docs" / "quality" / "ccp-savings")
    first = render_markdown(records)
    second = render_markdown(list(reversed(records)))
    assert first == second
    assert first.endswith("\n")
    assert "Observed baseline records | 1" in first
    assert "Eligible saved-compute observations | 0" in first
    assert "Provider-confirmed billed minutes | Not available" in first
    assert "Promotion status | NOT READY" in first


def test_promotion_requires_window_fallbacks_and_all_negative_cases(tmp_path: Path) -> None:
    eligible = _load_fixture("valid-eligible-pr.json")
    for index in range(10):
        record = json.loads(json.dumps(eligible))
        day = 22 if index == 9 else index + 1
        record["record_id"] = f"2026-08-{day:02d}-pr-{800 + index}"
        record["captured_at"] = f"2026-08-{day:02d}T12:00:00Z"
        record["pr_number"] = 800 + index
        record["source_sha"] = f"{index + 1:040x}"
        ccp = cast(dict[str, object], record["ccp"])
        ccp["source_sha"] = record["source_sha"]
        _write_record(tmp_path, f"eligible-{index:02d}.json", record)

    assert promotion_status(load_records(tmp_path))["ready"] is False

    for offset, captured_at in enumerate(("2026-08-22T12:00:00Z", "2026-08-23T12:00:00Z")):
        record = _load_fixture("valid-fallback.json")
        record["record_id"] = f"2026-08-{22 + offset:02d}-fallback"
        record["captured_at"] = captured_at
        record["pr_number"] = 900 + offset
        record["source_sha"] = f"{100 + offset:040x}"
        _write_record(tmp_path, f"fallback-{offset}.json", record)

    for offset, case in enumerate(("missing", "stale", "corrupt", "wrong_sha")):
        record = _load_fixture("valid-fallback.json")
        record.update(
            record_id=f"2026-08-24-negative-{case}",
            classification="negative",
            captured_at=f"2026-08-24T12:0{offset}:00Z",
            pr_number=950 + offset,
            source_sha=f"{200 + offset:040x}",
            fallback_reason=None,
            negative_case=case,
        )
        _write_record(tmp_path, f"negative-{case}.json", record)

    status = promotion_status(load_records(tmp_path))
    assert status["ready"] is True
    assert status["eligible_count"] == 10
    assert status["window_days"] >= 21
    assert status["fallback_count"] == 2
    assert status["negative_cases"] == ["corrupt", "missing", "stale", "wrong_sha"]
