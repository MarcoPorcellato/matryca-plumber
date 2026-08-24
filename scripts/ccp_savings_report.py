#!/usr/bin/env python3
"""Validate and render the immutable CCP hosted-CI savings ledger."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import re
import statistics
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MAX_SECONDS = 86_400
SHA_RE = re.compile(r"[0-9a-f]{40}")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}")
ID_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
CLASSIFICATIONS = {
    "observed_baseline",
    "eligible",
    "fallback",
    "negative",
    "failed",
    "cancelled",
    "excluded",
}
COMPARABILITY = {"pass", "fail", "not_applicable"}
NEGATIVE_CASES = {"missing", "stale", "corrupt", "wrong_sha"}
EXPECTED_FIELDS = {
    "schema_version",
    "record_id",
    "classification",
    "captured_at",
    "supersedes",
    "repository",
    "pr_number",
    "source_sha",
    "eligibility_reason",
    "comparability",
    "workflow_runs",
    "ccp",
    "verifier",
    "fallback_reason",
    "negative_case",
    "candidate_hosted_seconds",
    "estimated_avoided_hosted_seconds",
    "observed_verifier_seconds",
    "estimated_net_hosted_seconds_saved",
    "provider_confirmed_billed_minutes",
    "provider_confirmed_cost",
    "billing_source",
    "limitations",
    "source_urls",
}


class LedgerError(ValueError):
    """Raised when a ledger record violates the closed evidence contract."""


@dataclasses.dataclass(frozen=True)
class Record:
    """Validated immutable ledger record."""

    record_id: str
    classification: str
    captured_at: dt.datetime
    supersedes: str | None
    pr_number: int | None
    source_sha: str
    comparability: str
    candidate_hosted_seconds: int | None
    observed_verifier_seconds: int | None
    estimated_net_hosted_seconds_saved: int | None
    fallback_reason: str | None
    negative_case: str | None
    raw: Mapping[str, Any]


def _error(path: Path, field: str, detail: str) -> LedgerError:
    return LedgerError(f"{path}: {field}: {detail}")


def _utc(value: object, path: Path, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise _error(path, field, "must be an RFC 3339 UTC timestamp ending in Z")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise _error(path, field, "invalid timestamp") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise _error(path, field, "must be UTC")
    return parsed


def _optional_seconds(value: object, path: Path, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SECONDS:
        raise _error(path, field, f"must be null or an integer between 0 and {MAX_SECONDS}")
    return value


def _positive_int_or_none(value: object, path: Path, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _error(path, field, "must be null or a positive integer")
    return value


def _required_text(value: object, path: Path, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _error(path, field, "must be a non-empty string")
    return value


def _validate_workflow_runs(value: object, path: Path) -> None:
    if not isinstance(value, list) or not value:
        raise _error(path, "workflow_runs", "must be a non-empty list")
    expected = {
        "run_id",
        "job_id",
        "job_name",
        "conclusion",
        "source_sha",
        "started_at",
        "completed_at",
        "elapsed_seconds",
    }
    for index, item in enumerate(value):
        field = f"workflow_runs[{index}]"
        if not isinstance(item, dict) or set(item) != expected:
            raise _error(path, field, "has missing or unknown fields")
        _positive_int_or_none(item["run_id"], path, f"{field}.run_id")
        _positive_int_or_none(item["job_id"], path, f"{field}.job_id")
        _required_text(item["job_name"], path, f"{field}.job_name")
        _required_text(item["conclusion"], path, f"{field}.conclusion")
        if not isinstance(item["source_sha"], str) or not SHA_RE.fullmatch(item["source_sha"]):
            raise _error(path, f"{field}.source_sha", "must be exact lowercase 40-hex")
        if item["started_at"] is not None:
            _utc(item["started_at"], path, f"{field}.started_at")
        if item["completed_at"] is not None:
            _utc(item["completed_at"], path, f"{field}.completed_at")
        _optional_seconds(item["elapsed_seconds"], path, f"{field}.elapsed_seconds")


def _validate_ccp(value: object, path: Path, source_sha: str) -> None:
    if value is None:
        return
    expected = {
        "receipt_digest",
        "source_sha",
        "configuration_digest",
        "policy_digest",
        "runtime_ids",
        "conclusion",
        "local_elapsed_seconds",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise _error(path, "ccp", "has missing or unknown fields")
    for field in ("receipt_digest", "configuration_digest", "policy_digest"):
        if not isinstance(value[field], str) or not DIGEST_RE.fullmatch(value[field]):
            raise _error(path, f"ccp.{field}", "must be an exact SHA-256 digest")
    if value["source_sha"] != source_sha:
        raise _error(path, "ccp.source_sha", "must match source_sha")
    runtime_ids = value["runtime_ids"]
    if (
        not isinstance(runtime_ids, list)
        or not runtime_ids
        or runtime_ids != sorted(set(runtime_ids))
        or not all(isinstance(item, str) and ID_RE.fullmatch(item) for item in runtime_ids)
    ):
        raise _error(path, "ccp.runtime_ids", "must be a sorted unique identifier list")
    _required_text(value["conclusion"], path, "ccp.conclusion")
    _optional_seconds(value["local_elapsed_seconds"], path, "ccp.local_elapsed_seconds")


def _validate_verifier(value: object, path: Path) -> None:
    if value is None:
        return
    expected = {"run_id", "conclusion", "started_at", "completed_at", "elapsed_seconds"}
    if not isinstance(value, dict) or set(value) != expected:
        raise _error(path, "verifier", "has missing or unknown fields")
    _positive_int_or_none(value["run_id"], path, "verifier.run_id")
    _required_text(value["conclusion"], path, "verifier.conclusion")
    for field in ("started_at", "completed_at"):
        if value[field] is not None:
            _utc(value[field], path, f"verifier.{field}")
    _optional_seconds(value["elapsed_seconds"], path, "verifier.elapsed_seconds")


def _validate_billing(record: Mapping[str, Any], path: Path) -> None:
    minutes = record["provider_confirmed_billed_minutes"]
    cost = record["provider_confirmed_cost"]
    source = record["billing_source"]
    has_claim = minutes is not None or cost is not None
    if has_claim:
        if not isinstance(source, dict) or set(source) != {"url", "export_digest"}:
            raise _error(path, "billing_source", "is required for provider-confirmed claims")
        if not isinstance(source["url"], str) or not source["url"].startswith("https://"):
            raise _error(path, "billing_source.url", "must be HTTPS")
        if not isinstance(source["export_digest"], str) or not DIGEST_RE.fullmatch(
            source["export_digest"]
        ):
            raise _error(path, "billing_source.export_digest", "must be an exact SHA-256 digest")
    elif source is not None:
        raise _error(path, "billing_source", "must be null when no billing claim exists")
    if minutes is not None and (
        isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes < 0
    ):
        raise _error(path, "provider_confirmed_billed_minutes", "must be non-negative")
    if cost is not None and (
        isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0
    ):
        raise _error(path, "provider_confirmed_cost", "must be non-negative")


def _validate_record(raw: object, path: Path) -> Record:
    if not isinstance(raw, dict) or set(raw) != EXPECTED_FIELDS:
        missing = sorted(EXPECTED_FIELDS - set(raw) if isinstance(raw, dict) else EXPECTED_FIELDS)
        unknown = sorted(set(raw) - EXPECTED_FIELDS) if isinstance(raw, dict) else []
        detail = f"closed fields mismatch; missing={missing}, unknown={unknown}"
        raise _error(path, "record", detail)
    if raw["schema_version"] != SCHEMA_VERSION:
        raise _error(path, "schema_version", f"must equal {SCHEMA_VERSION}")
    record_id = _required_text(raw["record_id"], path, "record_id")
    if not ID_RE.fullmatch(record_id):
        raise _error(path, "record_id", "must be a lowercase stable identifier")
    classification = _required_text(raw["classification"], path, "classification")
    if classification not in CLASSIFICATIONS:
        raise _error(path, "classification", "is unsupported")
    captured_at = _utc(raw["captured_at"], path, "captured_at")
    supersedes = raw["supersedes"]
    if supersedes is not None and (
        not isinstance(supersedes, str) or not ID_RE.fullmatch(supersedes)
    ):
        raise _error(path, "supersedes", "must be null or a stable record identifier")
    if raw["repository"] != "MarcoPorcellato/matryca-plumber":
        raise _error(path, "repository", "must identify this repository")
    pr_number = _positive_int_or_none(raw["pr_number"], path, "pr_number")
    source_sha = _required_text(raw["source_sha"], path, "source_sha")
    if not SHA_RE.fullmatch(source_sha):
        raise _error(path, "source_sha", "must be exact lowercase 40-hex")
    _required_text(raw["eligibility_reason"], path, "eligibility_reason")
    comparability = _required_text(raw["comparability"], path, "comparability")
    if comparability not in COMPARABILITY:
        raise _error(path, "comparability", "is unsupported")
    _validate_workflow_runs(raw["workflow_runs"], path)
    _validate_ccp(raw["ccp"], path, source_sha)
    _validate_verifier(raw["verifier"], path)
    fallback_reason = raw["fallback_reason"]
    if fallback_reason is not None:
        fallback_reason = _required_text(fallback_reason, path, "fallback_reason")
    negative_case = raw["negative_case"]
    if negative_case is not None and negative_case not in NEGATIVE_CASES:
        raise _error(path, "negative_case", "is unsupported")
    if classification == "negative" and negative_case is None:
        raise _error(path, "negative_case", "is required for negative evidence")
    if classification == "fallback" and fallback_reason is None:
        raise _error(path, "fallback_reason", "is required for fallback evidence")

    candidate = _optional_seconds(raw["candidate_hosted_seconds"], path, "candidate_hosted_seconds")
    avoided = _optional_seconds(
        raw["estimated_avoided_hosted_seconds"], path, "estimated_avoided_hosted_seconds"
    )
    verifier = _optional_seconds(
        raw["observed_verifier_seconds"], path, "observed_verifier_seconds"
    )
    net = _optional_seconds(
        raw["estimated_net_hosted_seconds_saved"],
        path,
        "estimated_net_hosted_seconds_saved",
    )
    if classification == "eligible":
        if comparability != "pass":
            raise _error(path, "comparability", "eligible records require pass")
        if None in (candidate, avoided, verifier, net):
            raise _error(
                path,
                "estimated_net_hosted_seconds_saved",
                "eligible record is incomplete",
            )
        if raw["ccp"] is None or raw["ccp"]["conclusion"] != "PASS":
            raise _error(path, "ccp.conclusion", "eligible records require PASS")
        if raw["verifier"] is None or raw["verifier"]["conclusion"] != "success":
            raise _error(path, "verifier.conclusion", "eligible records require success")
    if (
        candidate is not None
        and verifier is not None
        and net is not None
        and net != max(0, candidate - verifier)
    ):
        raise _error(
            path,
            "estimated_net_hosted_seconds_saved",
            "does not equal max(0, candidate - verifier)",
        )
    if avoided is not None and candidate is not None and avoided > candidate:
        raise _error(path, "estimated_avoided_hosted_seconds", "cannot exceed candidate seconds")
    _validate_billing(raw, path)

    limitations = raw["limitations"]
    if (
        not isinstance(limitations, list)
        or not limitations
        or not all(isinstance(item, str) and item.strip() for item in limitations)
    ):
        raise _error(path, "limitations", "must be a non-empty string list")
    source_urls = raw["source_urls"]
    if (
        not isinstance(source_urls, list)
        or not source_urls
        or not all(isinstance(item, str) and item.startswith("https://") for item in source_urls)
    ):
        raise _error(path, "source_urls", "must be a non-empty HTTPS URL list")
    return Record(
        record_id=record_id,
        classification=classification,
        captured_at=captured_at,
        supersedes=supersedes,
        pr_number=pr_number,
        source_sha=source_sha,
        comparability=comparability,
        candidate_hosted_seconds=candidate,
        observed_verifier_seconds=verifier,
        estimated_net_hosted_seconds_saved=net,
        fallback_reason=fallback_reason,
        negative_case=negative_case,
        raw=raw,
    )


def _record_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    paths: list[Path] = []
    for directory in (root / "baseline", root / "observations"):
        if directory.is_dir():
            paths.extend(directory.glob("*.json"))
    return sorted(paths)


def load_records(root: Path) -> list[Record]:
    """Load, strictly validate, de-duplicate, and sort ledger records."""

    records: list[Record] = []
    identifiers: set[str] = set()
    for path in _record_paths(root):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _error(path, "record", "cannot read canonical JSON") from exc
        record = _validate_record(raw, path)
        if record.record_id in identifiers:
            raise _error(path, "record_id", "duplicate record identifier")
        identifiers.add(record.record_id)
        records.append(record)
    if not records:
        raise LedgerError(f"{root}: no ledger records found")
    superseded = {record.supersedes for record in records if record.supersedes is not None}
    unknown = superseded - identifiers
    if unknown:
        raise LedgerError(f"{root}: supersedes unknown records: {sorted(unknown)}")
    return sorted(records, key=lambda item: item.record_id)


def _active(records: Iterable[Record]) -> list[Record]:
    records = list(records)
    superseded = {record.supersedes for record in records if record.supersedes is not None}
    return [record for record in records if record.record_id not in superseded]


def _quartiles(values: Sequence[int]) -> tuple[float | None, float | None]:
    if len(values) < 2:
        return None, None
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q3


def summarize(records: Iterable[Record]) -> dict[str, int | float | None]:
    """Summarize active evidence without counting excluded outcomes as savings."""

    active = _active(records)
    eligible = [
        record
        for record in active
        if record.classification == "eligible" and record.comparability == "pass"
    ]
    candidate = [record.candidate_hosted_seconds or 0 for record in eligible]
    verifier = [record.observed_verifier_seconds or 0 for record in eligible]
    net = [record.estimated_net_hosted_seconds_saved or 0 for record in eligible]
    q1, q3 = _quartiles(net)
    return {
        "record_count": len(active),
        "baseline_count": sum(record.classification == "observed_baseline" for record in active),
        "eligible_count": len(eligible),
        "fallback_count": sum(record.classification == "fallback" for record in active),
        "negative_count": sum(record.classification == "negative" for record in active),
        "failed_count": sum(record.classification == "failed" for record in active),
        "cancelled_count": sum(record.classification == "cancelled" for record in active),
        "excluded_count": sum(record.classification == "excluded" for record in active),
        "candidate_hosted_seconds": sum(candidate),
        "verifier_seconds": sum(verifier),
        "net_estimated_seconds_saved": sum(net),
        "median_net_seconds_saved": statistics.median(net) if net else None,
        "net_q1_seconds": q1,
        "net_q3_seconds": q3,
    }


def promotion_status(records: Iterable[Record]) -> dict[str, Any]:
    """Evaluate the conservative public case-study promotion threshold."""

    active = _active(records)
    eligible = sorted(
        (
            record
            for record in active
            if record.classification == "eligible" and record.comparability == "pass"
        ),
        key=lambda item: item.captured_at,
    )
    window_days = (
        (eligible[-1].captured_at.date() - eligible[0].captured_at.date()).days
        if len(eligible) >= 2
        else 0
    )
    fallback_count = sum(record.classification == "fallback" for record in active)
    negative_cases = sorted(
        {record.negative_case for record in active if record.negative_case is not None}
    )
    ready = (
        len(eligible) >= 10
        and window_days >= 21
        and fallback_count >= 2
        and set(negative_cases) == NEGATIVE_CASES
    )
    return {
        "schema_version": "1.0",
        "ready": ready,
        "eligible_count": len(eligible),
        "window_days": window_days,
        "fallback_count": fallback_count,
        "negative_cases": negative_cases,
    }


def _display_number(value: int | float | None) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render_markdown(records: Iterable[Record]) -> str:
    """Render a byte-stable public-safe case-study status document."""

    ordered = sorted(records, key=lambda item: item.record_id)
    summary = summarize(ordered)
    promotion = promotion_status(ordered)
    captured = max(record.captured_at.date() for record in ordered).isoformat()
    fingerprint = hashlib.sha256(
        json.dumps(
            [record.raw for record in ordered], sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    lines = [
        "---",
        "type: Audit",
        "title: Commit CI Preflight GitHub Actions savings case study",
        "description: Deterministic status generated from immutable Matryca "
        "Plumber hybrid-CI observations.",
        "status: draft",
        "classification: active",
        "audience: [maintainer, contributor, operator]",
        "owner: quality",
        f"last_verified: {captured}",
        "stale_after: 2027-02-20",
        "---",
        "",
        "# Commit CI Preflight GitHub Actions Savings Case Study",
        "",
        "This document is generated from the immutable JSON ledger under",
        "`docs/quality/ccp-savings/`. It separates observed elapsed seconds from",
        "provider billing and never converts estimates into monetary claims.",
        "",
        "## Current evidence",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Active records | {summary['record_count']} |",
        f"| Observed baseline records | {summary['baseline_count']} |",
        f"| Eligible saved-compute observations | {summary['eligible_count']} |",
        f"| Hosted fallbacks | {summary['fallback_count']} |",
        f"| Negative receipt cases | {summary['negative_count']} |",
        f"| Failed observations | {summary['failed_count']} |",
        f"| Cancelled observations | {summary['cancelled_count']} |",
        f"| Excluded observations | {summary['excluded_count']} |",
        f"| Candidate hosted seconds | {summary['candidate_hosted_seconds']} |",
        f"| Remote verifier seconds | {summary['verifier_seconds']} |",
        f"| Net estimated hosted seconds saved | {summary['net_estimated_seconds_saved']} |",
        f"| Median net seconds saved | {_display_number(summary['median_net_seconds_saved'])} |",
        "| Provider-confirmed billed minutes | Not available |",
        "| Provider-confirmed monetary savings | Not available |",
        f"| Promotion status | {'READY' if promotion['ready'] else 'NOT READY'} |",
        "",
        "## Promotion gate",
        "",
        f"- Eligible observations: `{promotion['eligible_count']}` / `10`.",
        f"- Eligible observation window: `{promotion['window_days']}` / `21` days.",
        f"- Hosted fallbacks: `{promotion['fallback_count']}` / `2`.",
        "- Negative receipt cases: "
        + (", ".join(f"`{item}`" for item in promotion["negative_cases"]) or "none"),
        "",
        "## Evidence boundary",
        "",
        "The historical baseline is not counted as an activated saving. Failed,",
        "cancelled, fallback, excluded, non-comparable, and superseded records remain",
        "visible but never enter the saved-compute numerator. Local execution cost,",
        "maintenance effort, billing, energy, and money require independent evidence.",
        "",
        f"Ledger fingerprint: `sha256:{fingerprint}`.",
        "",
    ]
    return "\n".join(lines)


def _write_new_or_replace_generated(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "render", "check", "promotion-status"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--root", type=Path, required=True)
        if command in {"render", "check"}:
            subparser.add_argument("--output", type=Path, required=True)
        if command == "promotion-status":
            subparser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        records = load_records(args.root)
        if args.command == "validate":
            print(f"PASS: {len(records)} CCP savings record(s) validated")
            return 0
        if args.command == "render":
            _write_new_or_replace_generated(args.output, render_markdown(records))
            print(f"WROTE: {args.output}")
            return 0
        if args.command == "check":
            expected = render_markdown(records)
            if not args.output.is_file() or args.output.read_text(encoding="utf-8") != expected:
                print(f"FAIL: generated report drift: {args.output}", file=sys.stderr)
                return 1
            print(f"PASS: generated report is current: {args.output}")
            return 0
        status = promotion_status(records)
        if args.json:
            print(json.dumps(status, sort_keys=True, separators=(",", ":")))
        else:
            print("READY" if status["ready"] else "NOT READY")
        return 0 if status["ready"] else 1
    except LedgerError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
