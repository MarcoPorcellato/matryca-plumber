"""Private storage, validation, issue, and report primitives for beta evidence."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import time
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 1
_CANDIDATE_DISPLAY = "2.0.0-beta.1"
_CANDIDATE_PACKAGE = "2.0.0b1"
_BASELINE_PACKAGE = "2.0.0a5"
_DISPLAY_VERSION = re.compile(
    r"^(?P<release>\d+\.\d+\.\d+)(?:-(?P<phase>alpha|beta|rc)\.(?P<serial>\d+))?$"
)
_PACKAGE_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:(?:a|b)\d+|rc\d+)?$")
_PHASE_TO_PACKAGE = {"alpha": "a", "beta": "b", "rc": "rc"}
_VALID_SEVERITIES = frozenset({"P0", "P1", "P2", "P3"})
_VALID_STATES = frozenset({"open", "closed"})
_VALID_DISPOSITION_STATUSES = frozenset({"accepted", "deferred", "fixed", "not_applicable"})
_VALID_AUDIT_STATUSES = frozenset({"PASS", "FAIL"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_GATES = ("preflight", "issues", "wheel", "soak", "final_code_audit")


class EvidenceError(Exception):
    """A bounded category that is safe to report in generated evidence."""

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


@dataclass(frozen=True)
class GateRecord:
    """A resumable gate result without environment-specific input details."""

    gate_id: str
    input_hash: str
    status: str
    details: dict[str, Any]


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def validate_output_directory(
    output: Path,
    *,
    repo_root: Path,
    protected_roots: Sequence[Path],
) -> Path:
    """Reject evidence destinations inside repository or supplied vault roots."""

    resolved_output = output.expanduser().resolve(strict=False)
    protected = [
        repo_root.expanduser().resolve(strict=False),
        *(root.expanduser().resolve(strict=False) for root in protected_roots),
    ]
    if any(_is_within(resolved_output, root) for root in protected):
        raise EvidenceError("output_unsafe")
    return resolved_output


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _atomic_write_json(path: Path, value: object) -> None:
    _atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _append_event(output: Path, event: dict[str, object]) -> None:
    event["timestamp_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with (output / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_json(path: Path, *, category: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(category) from exc
    if not isinstance(payload, dict):
        raise EvidenceError(category)
    return payload


def _empty_checkpoint() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "gates": {}, "metadata": {}}


def _load_checkpoint(output: Path) -> dict[str, Any]:
    path = output / "checkpoint.json"
    if not path.exists():
        return _empty_checkpoint()
    checkpoint = _load_json(path, category="checkpoint_invalid")
    if (
        checkpoint.get("schema_version") != SCHEMA_VERSION
        or not isinstance(checkpoint.get("gates"), dict)
        or not isinstance(checkpoint.get("metadata"), dict)
    ):
        raise EvidenceError("checkpoint_invalid")
    return checkpoint


def _load_evidence(output: Path) -> dict[str, Any]:
    path = output / "evidence.json"
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "gates": {}, "metadata": {}}
    evidence = _load_json(path, category="evidence_invalid")
    if evidence.get("schema_version") != SCHEMA_VERSION or not isinstance(
        evidence.get("gates"), dict
    ):
        raise EvidenceError("evidence_invalid")
    return evidence


def _record_gate(
    output: Path,
    record: GateRecord,
    *,
    metadata: dict[str, object] | None = None,
) -> GateRecord:
    checkpoint = _load_checkpoint(output)
    evidence = _load_evidence(output)
    existing = checkpoint["gates"].get(record.gate_id)
    if isinstance(existing, dict) and existing.get("input_hash") == record.input_hash:
        persisted = evidence["gates"].get(record.gate_id)
        expected = asdict(record)
        if not isinstance(persisted, dict) or existing != expected or persisted != expected:
            raise EvidenceError("evidence_invalid")
        _append_event(
            output, {"event": "gate_resumed", "gate_id": record.gate_id, "status": record.status}
        )
        return record

    output.mkdir(parents=True, exist_ok=True)
    checkpoint["gates"][record.gate_id] = asdict(record)
    if metadata:
        checkpoint["metadata"].update(metadata)
    _atomic_write_json(output / "checkpoint.json", checkpoint)
    evidence["gates"][record.gate_id] = asdict(record)
    if metadata:
        evidence.setdefault("metadata", {}).update(metadata)
    _atomic_write_json(output / "evidence.json", evidence)
    _append_event(
        output, {"event": "gate_recorded", "gate_id": record.gate_id, "status": record.status}
    )
    return record


def display_to_package_version(display: str) -> str:
    """Normalize a SemVer display prerelease to its Python package version."""

    match = _DISPLAY_VERSION.fullmatch(display)
    if not match:
        raise EvidenceError("candidate_display_invalid")
    phase = match.group("phase")
    if phase is None:
        return match.group("release")
    return f"{match.group('release')}{_PHASE_TO_PACKAGE[phase]}{match.group('serial')}"


def _validate_package_version(value: str, *, category: str) -> str:
    if not _PACKAGE_VERSION.fullmatch(value):
        raise EvidenceError(category)
    return value


def collect_preflight(
    output: Path,
    *,
    candidate_display: str,
    candidate_package: str,
    baseline_package: str,
) -> GateRecord:
    """Record release naming and sanitized host facts for a candidate release."""

    expected_package = display_to_package_version(candidate_display)
    _validate_package_version(candidate_package, category="candidate_package_invalid")
    _validate_package_version(baseline_package, category="baseline_package_invalid")
    status = (
        "PASS"
        if (
            candidate_display == _CANDIDATE_DISPLAY
            and candidate_package == _CANDIDATE_PACKAGE
            and baseline_package == _BASELINE_PACKAGE
            and candidate_package == expected_package
        )
        else "FAIL"
    )
    details = {
        "candidate_display": candidate_display,
        "candidate_package": candidate_package,
        "baseline_package": baseline_package,
        "candidate_matches_release": candidate_display == _CANDIDATE_DISPLAY,
        "package_matches_release": candidate_package == _CANDIDATE_PACKAGE,
        "baseline_matches_release": baseline_package == _BASELINE_PACKAGE,
        "formats_match": status == "PASS",
        "python": {
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
        },
        "platform": {"system": platform.system().lower(), "machine": platform.machine().lower()},
    }
    return _record_gate(
        output,
        GateRecord("preflight", _canonical_hash(details), status, details),
        metadata={
            "candidate_display": candidate_display,
            "candidate_package": candidate_package,
            "baseline_package": baseline_package,
        },
    )


def _parse_issues(payload: dict[str, Any]) -> list[dict[str, object]]:
    if (
        set(payload) != {"schema_version", "issues"}
        or payload.get("schema_version") != SCHEMA_VERSION
    ):
        raise EvidenceError("issues_input_invalid")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise EvidenceError("issues_input_invalid")
    normalized: list[dict[str, object]] = []
    seen: set[int] = set()
    for issue in issues:
        if not isinstance(issue, dict) or set(issue) != {"number", "severity", "state", "in_scope"}:
            raise EvidenceError("issues_input_invalid")
        number, severity, state, in_scope = (
            issue.get("number"),
            issue.get("severity"),
            issue.get("state"),
            issue.get("in_scope"),
        )
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number <= 0
            or number in seen
            or severity not in _VALID_SEVERITIES
            or state not in _VALID_STATES
            or not isinstance(in_scope, bool)
        ):
            raise EvidenceError("issues_input_invalid")
        seen.add(number)
        normalized.append(
            {"number": number, "severity": severity, "state": state, "in_scope": in_scope}
        )
    return sorted(normalized, key=lambda item: cast(int, item["number"]))


def _parse_dispositions(payload: dict[str, Any]) -> dict[int, str]:
    if (
        set(payload) != {"schema_version", "dispositions"}
        or payload.get("schema_version") != SCHEMA_VERSION
    ):
        raise EvidenceError("dispositions_input_invalid")
    dispositions = payload.get("dispositions")
    if not isinstance(dispositions, list):
        raise EvidenceError("dispositions_input_invalid")
    result: dict[int, str] = {}
    for disposition in dispositions:
        if not isinstance(disposition, dict) or set(disposition) != {"number", "status"}:
            raise EvidenceError("dispositions_input_invalid")
        number, status = disposition.get("number"), disposition.get("status")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or number <= 0
            or number in result
            or not isinstance(status, str)
            or status not in _VALID_DISPOSITION_STATUSES
        ):
            raise EvidenceError("dispositions_input_invalid")
        result[number] = status
    return result


def collect_issues(output: Path, *, issues_path: Path, dispositions_path: Path) -> GateRecord:
    """Fail closed on in-scope open P0/P1 or P2 without controlled disposition."""

    issues = _parse_issues(_load_json(issues_path, category="issues_input_unavailable"))
    dispositions = _parse_dispositions(
        _load_json(dispositions_path, category="dispositions_input_unavailable")
    )
    summaries: list[dict[str, object]] = []
    failed = False
    for issue in issues:
        number = cast(int, issue["number"])
        severity, state, in_scope = (
            str(issue["severity"]),
            str(issue["state"]),
            bool(issue["in_scope"]),
        )
        disposition_status = dispositions.get(number) if severity == "P2" else None
        if in_scope and state == "open" and severity in {"P0", "P1"}:
            failed = True
        if in_scope and state == "open" and severity == "P2" and disposition_status is None:
            failed = True
        summaries.append(
            {
                "number": number,
                "severity": severity,
                "state": state,
                "in_scope": in_scope,
                "disposition_status": disposition_status,
            }
        )
    return _record_gate(
        output,
        GateRecord(
            "issues",
            _canonical_hash({"issues": issues, "dispositions": dispositions}),
            "FAIL" if failed else "PASS",
            {"issues": summaries},
        ),
    )


def _parse_final_code_audit(payload: dict[str, Any]) -> dict[str, object]:
    expected = {
        "schema_version",
        "candidate_package",
        "wheel_sha256",
        "candidate_diff_sha256",
        "diff_verified",
        "build_verified",
        "ci_verified",
        "scope_verified",
        "audit_status",
        "blocking_findings",
        "advisory_findings",
    }
    if set(payload) != expected or payload.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceError("code_audit_input_invalid")
    candidate_package = payload.get("candidate_package")
    wheel_sha256 = payload.get("wheel_sha256")
    candidate_diff_sha256 = payload.get("candidate_diff_sha256")
    audit_status = payload.get("audit_status")
    boolean_fields = ("diff_verified", "build_verified", "ci_verified", "scope_verified")
    count_fields = ("blocking_findings", "advisory_findings")
    if (
        not isinstance(candidate_package, str)
        or _PACKAGE_VERSION.fullmatch(candidate_package) is None
        or not isinstance(wheel_sha256, str)
        or _SHA256.fullmatch(wheel_sha256) is None
        or not isinstance(candidate_diff_sha256, str)
        or _SHA256.fullmatch(candidate_diff_sha256) is None
        or audit_status not in _VALID_AUDIT_STATUSES
        or any(not isinstance(payload.get(field), bool) for field in boolean_fields)
        or any(
            not isinstance(payload.get(field), int)
            or isinstance(payload.get(field), bool)
            or payload[field] < 0
            for field in count_fields
        )
    ):
        raise EvidenceError("code_audit_input_invalid")
    return {
        "candidate_package": candidate_package,
        "wheel_sha256": wheel_sha256,
        "candidate_diff_sha256": candidate_diff_sha256,
        "diff_verified": payload["diff_verified"],
        "build_verified": payload["build_verified"],
        "ci_verified": payload["ci_verified"],
        "scope_verified": payload["scope_verified"],
        "audit_status": audit_status,
        "blocking_findings": payload["blocking_findings"],
        "advisory_findings": payload["advisory_findings"],
    }


def _code_audit_prerequisites(output: Path) -> tuple[str, str]:
    checkpoint, evidence = _load_checkpoint(output), _load_evidence(output)
    checkpoint_gates, evidence_gates = checkpoint["gates"], evidence["gates"]
    _validate_gate_records(checkpoint_gates)
    _validate_gate_records(evidence_gates)
    if checkpoint_gates != evidence_gates:
        raise EvidenceError("evidence_invalid")
    records = {gate_id: checkpoint_gates.get(gate_id) for gate_id in ("preflight", "wheel")}
    if any(
        not isinstance(record, dict) or record.get("status") != "PASS"
        for record in records.values()
    ):
        raise EvidenceError("code_audit_prerequisite_missing")
    preflight_details = cast(dict[str, Any], records["preflight"])["details"]
    wheel_details = cast(dict[str, Any], records["wheel"])["details"]
    candidate_package = preflight_details.get("candidate_package")
    wheel_sha256 = wheel_details.get("wheel_sha256")
    if (
        not isinstance(candidate_package, str)
        or _PACKAGE_VERSION.fullmatch(candidate_package) is None
        or not isinstance(wheel_sha256, str)
        or _SHA256.fullmatch(wheel_sha256) is None
    ):
        raise EvidenceError("code_audit_prerequisite_invalid")
    return candidate_package, wheel_sha256


def collect_final_code_audit(output: Path, *, audit_path: Path) -> GateRecord:
    """Record a sanitized, fail-closed code audit for the candidate wheel."""

    audit = _parse_final_code_audit(_load_json(audit_path, category="code_audit_input_unavailable"))
    candidate_package, wheel_sha256 = _code_audit_prerequisites(output)
    failure_reasons: list[str] = []
    if audit["candidate_package"] != candidate_package:
        failure_reasons.append("candidate_package_mismatch")
    if audit["wheel_sha256"] != wheel_sha256:
        failure_reasons.append("wheel_sha256_mismatch")
    if audit["diff_verified"] is not True:
        failure_reasons.append("diff_unverified")
    if audit["build_verified"] is not True:
        failure_reasons.append("build_unverified")
    if audit["ci_verified"] is not True:
        failure_reasons.append("ci_unverified")
    if audit["scope_verified"] is not True:
        failure_reasons.append("scope_unverified")
    if audit["audit_status"] != "PASS":
        failure_reasons.append("audit_not_passed")
    if audit["blocking_findings"] != 0:
        failure_reasons.append("blocking_findings_present")
    details = {**audit, "failure_reasons": failure_reasons}
    return _record_gate(
        output,
        GateRecord(
            "final_code_audit",
            _canonical_hash(audit),
            "FAIL" if failure_reasons else "PASS",
            details,
        ),
    )


def _validate_gate_records(gates: dict[str, Any]) -> None:
    for gate_id, record in gates.items():
        if (
            not isinstance(gate_id, str)
            or not isinstance(record, dict)
            or record.get("gate_id") != gate_id
            or not isinstance(record.get("input_hash"), str)
            or re.fullmatch(r"[0-9a-f]{64}", record["input_hash"]) is None
            or record.get("status") not in {"PASS", "FAIL"}
            or not isinstance(record.get("details"), dict)
        ):
            raise EvidenceError("evidence_invalid")


def render_summary(evidence: dict[str, Any]) -> str:
    """Render a path-free beta readiness summary from recorded gate evidence."""

    gates = evidence.get("gates", {})
    rows: list[tuple[str, str]] = []
    statuses: list[str] = []
    for gate_id in _REQUIRED_GATES:
        record = gates.get(gate_id)
        status = str(record.get("status")) if isinstance(record, dict) else "PENDING"
        rows.append((gate_id, status))
        statuses.append(status)
    readiness = (
        "READY" if statuses and all(status == "PASS" for status in statuses) else "NOT READY"
    )
    metadata = evidence.get("metadata", {})
    lines = [
        "# Beta readiness evidence",
        "",
        f"Schema version: {SCHEMA_VERSION}",
        f"Candidate display: {metadata.get('candidate_display', 'PENDING')}",
        f"Candidate package: {metadata.get('candidate_package', 'PENDING')}",
        f"Baseline package: {metadata.get('baseline_package', 'PENDING')}",
        "",
        "| Gate | Status |",
        "|---|---|",
        *(f"| {gate_id} | {status} |" for gate_id, status in rows),
        "",
        f"## Verdict: {readiness}",
        "",
        "Wheel installation, soak evidence, and final code audit remain pending "
        "until collected by dedicated commands.",
    ]
    return "\n".join(lines) + "\n"


def collect_report(output: Path) -> GateRecord:
    """Generate a summary; uncollected wheel, soak and code-audit gates remain pending."""

    checkpoint, evidence = _load_checkpoint(output), _load_evidence(output)
    checkpoint_gates, evidence_gates = checkpoint["gates"], evidence["gates"]
    _validate_gate_records(checkpoint_gates)
    _validate_gate_records(evidence_gates)
    if checkpoint_gates != evidence_gates:
        raise EvidenceError("evidence_invalid")
    summary = render_summary(evidence)
    _atomic_write(output / "summary.md", summary)
    record = _record_gate(
        output,
        GateRecord(
            "report",
            _canonical_hash(evidence.get("gates", {})),
            "PASS",
            {"required_gates": list(_REQUIRED_GATES), "ready": "## Verdict: READY" in summary},
        ),
    )
    _atomic_write(output / "summary.md", render_summary(_load_evidence(output)))
    return record
