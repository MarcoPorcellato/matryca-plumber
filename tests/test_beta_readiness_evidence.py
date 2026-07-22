"""Contract tests for the local, privacy-safe beta evidence harness."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[1] / "scripts" / "beta_readiness_evidence.py"
_SCRIPTS = _SCRIPT.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _module() -> ModuleType:
    return importlib.import_module("beta_evidence")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _inputs(
    tmp_path: Path, *, issues: list[dict[str, object]], dispositions: list[dict[str, object]]
) -> tuple[Path, Path]:
    issues_path = tmp_path / "issues.json"
    dispositions_path = tmp_path / "dispositions.json"
    _write_json(issues_path, {"schema_version": 1, "issues": issues})
    _write_json(dispositions_path, {"schema_version": 1, "dispositions": dispositions})
    return issues_path, dispositions_path


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *arguments], check=False, text=True, capture_output=True
    )


def test_output_rejects_repo_and_vault_containment(tmp_path: Path) -> None:
    module = _module()
    repo = tmp_path / "repo"
    vault = tmp_path / "vault"
    repo.mkdir()
    vault.mkdir()
    with pytest.raises(module.EvidenceError, match="output_unsafe"):
        module.validate_output_directory(repo / "evidence", repo_root=repo, protected_roots=[vault])
    with pytest.raises(module.EvidenceError, match="output_unsafe"):
        module.validate_output_directory(
            vault / "evidence", repo_root=repo, protected_roots=[vault]
        )
    assert module.validate_output_directory(
        tmp_path / "outside", repo_root=repo, protected_roots=[vault]
    ) == (tmp_path / "outside")


@pytest.mark.parametrize(
    ("display", "package"),
    [("2.0.0-beta.1", "2.0.0b1"), ("2.0.0-alpha.5", "2.0.0a5"), ("2.0.0-rc.2", "2.0.0rc2")],
)
def test_display_versions_normalize_to_python_packages(display: str, package: str) -> None:
    assert _module().display_to_package_version(display) == package


def test_atomic_resume_is_idempotent(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    first = module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    checkpoint_before = (output / "checkpoint.json").read_text(encoding="utf-8")
    second = module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    assert first == second
    assert (output / "checkpoint.json").read_text(encoding="utf-8") == checkpoint_before
    assert "gate_resumed" in (output / "events.jsonl").read_text(encoding="utf-8")


def test_preflight_requires_the_explicit_beta_candidate(tmp_path: Path) -> None:
    record = _module().collect_preflight(
        tmp_path / "evidence",
        candidate_display="2.0.0-alpha.5",
        candidate_package="2.0.0a5",
        baseline_package="2.0.0a5",
    )
    assert record.status == "FAIL"
    assert record.details["candidate_matches_release"] is False


def test_corrupted_checkpoint_fails_closed(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    output.mkdir()
    (output / "checkpoint.json").write_text("not-json", encoding="utf-8")
    result = _run(
        "preflight",
        "--output",
        str(output),
        "--candidate-display",
        "2.0.0-beta.1",
        "--candidate-package",
        "2.0.0b1",
        "--baseline-package",
        "2.0.0a5",
    )
    assert result.returncode == 2
    assert result.stderr.strip() == "beta evidence: checkpoint_invalid"


def test_corrupted_evidence_fails_closed_on_resume(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    (output / "evidence.json").write_text("not-json", encoding="utf-8")
    with pytest.raises(module.EvidenceError, match="evidence_invalid"):
        module.collect_preflight(
            output,
            candidate_display="2.0.0-beta.1",
            candidate_package="2.0.0b1",
            baseline_package="2.0.0a5",
        )


def test_tampered_checkpoint_fails_closed_on_resume(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    checkpoint = json.loads((output / "checkpoint.json").read_text(encoding="utf-8"))
    checkpoint["gates"]["preflight"]["details"]["platform"]["system"] = "untrusted"
    _write_json(output / "checkpoint.json", checkpoint)
    with pytest.raises(module.EvidenceError, match="evidence_invalid"):
        module.collect_preflight(
            output,
            candidate_display="2.0.0-beta.1",
            candidate_package="2.0.0b1",
            baseline_package="2.0.0a5",
        )


def test_open_p0_or_p1_fails_gate(tmp_path: Path) -> None:
    module = _module()
    issues_path, dispositions_path = _inputs(
        tmp_path,
        issues=[{"number": 1, "severity": "P1", "state": "open", "in_scope": True}],
        dispositions=[],
    )
    record = module.collect_issues(
        tmp_path / "evidence", issues_path=issues_path, dispositions_path=dispositions_path
    )
    assert record.status == "FAIL"


def test_open_p2_needs_disposition_and_then_passes(tmp_path: Path) -> None:
    module = _module()
    issues = [{"number": 2, "severity": "P2", "state": "open", "in_scope": True}]
    missing, empty = _inputs(tmp_path / "missing", issues=issues, dispositions=[])
    missing_record = module.collect_issues(
        tmp_path / "missing-evidence", issues_path=missing, dispositions_path=empty
    )
    assert missing_record.status == "FAIL"
    issue_path, disposition_path = _inputs(
        tmp_path / "accepted", issues=issues, dispositions=[{"number": 2, "status": "accepted"}]
    )
    accepted = module.collect_issues(
        tmp_path / "accepted-evidence", issues_path=issue_path, dispositions_path=disposition_path
    )
    assert accepted.status == "PASS"
    stored = json.loads(
        (tmp_path / "accepted-evidence" / "evidence.json").read_text(encoding="utf-8")
    )
    assert stored["gates"]["issues"]["details"]["issues"] == [
        {
            "number": 2,
            "severity": "P2",
            "state": "open",
            "in_scope": True,
            "disposition_status": "accepted",
        }
    ]


def test_report_stays_not_ready_without_wheel_soak_and_final_audit(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    issue_path, disposition_path = _inputs(tmp_path, issues=[], dispositions=[])
    module.collect_issues(output, issues_path=issue_path, dispositions_path=disposition_path)
    module.collect_report(output)
    summary = (output / "summary.md").read_text(encoding="utf-8")
    assert "| wheel | PENDING |" in summary
    assert "| soak | PENDING |" in summary
    assert "| final_code_audit | PENDING |" in summary
    assert "## Verdict: NOT READY" in summary


def test_report_rejects_pass_gates_injected_only_into_evidence(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    issue_path, disposition_path = _inputs(tmp_path, issues=[], dispositions=[])
    module.collect_issues(output, issues_path=issue_path, dispositions_path=disposition_path)
    module.collect_report(output)
    evidence_path = output / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    for gate_id in ("wheel", "soak", "final_code_audit"):
        evidence["gates"][gate_id] = {
            "gate_id": gate_id,
            "input_hash": "0" * 64,
            "status": "PASS",
            "details": {},
        }
    _write_json(evidence_path, evidence)
    with pytest.raises(module.EvidenceError, match="evidence_invalid"):
        module.collect_report(output)
    assert "## Verdict: READY" not in (output / "summary.md").read_text(encoding="utf-8")


def test_cli_storage_error_for_non_directory_output(tmp_path: Path) -> None:
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("x", encoding="utf-8")
    result = _run("report", "--output", str(output_file))
    assert result.returncode == 2
    assert result.stderr.strip() == "beta evidence: storage_error"


def test_publishable_artifacts_contain_no_absolute_paths(tmp_path: Path) -> None:
    module = _module()
    output = tmp_path / "evidence"
    issue_path, disposition_path = _inputs(tmp_path, issues=[], dispositions=[])
    assert (
        module.main(
            [
                "run",
                "--output",
                str(output),
                "--candidate-display",
                "2.0.0-beta.1",
                "--candidate-package",
                "2.0.0b1",
                "--baseline-package",
                "2.0.0a5",
                "--issues-json",
                str(issue_path),
                "--p2-dispositions",
                str(disposition_path),
            ]
        )
        == 2
    )
    forbidden = {str(tmp_path), str(output), str(issue_path), str(disposition_path)}
    for artifact in ("evidence.json", "checkpoint.json", "events.jsonl", "summary.md"):
        text = (output / artifact).read_text(encoding="utf-8")
        assert not any(value in text for value in forbidden)


def test_cli_exit_codes_for_success_and_failed_issues(tmp_path: Path) -> None:
    issue_path, disposition_path = _inputs(
        tmp_path,
        issues=[{"number": 3, "severity": "P0", "state": "open", "in_scope": True}],
        dispositions=[],
    )
    failed = _run(
        "run",
        "--output",
        str(tmp_path / "failed"),
        "--candidate-display",
        "2.0.0-beta.1",
        "--candidate-package",
        "2.0.0b1",
        "--baseline-package",
        "2.0.0a5",
        "--issues-json",
        str(issue_path),
        "--p2-dispositions",
        str(disposition_path),
    )
    assert failed.returncode == 2
    assert failed.stderr.strip() == "beta evidence: gate_failed"
    assert (tmp_path / "failed" / "summary.md").exists()
    _write_json(issue_path, {"schema_version": 1, "issues": []})
    passed = _run(
        "run",
        "--output",
        str(tmp_path / "passed"),
        "--candidate-display",
        "2.0.0-beta.1",
        "--candidate-package",
        "2.0.0b1",
        "--baseline-package",
        "2.0.0a5",
        "--issues-json",
        str(issue_path),
        "--p2-dispositions",
        str(disposition_path),
    )
    assert passed.returncode == 2
    assert passed.stderr.strip() == "beta evidence: readiness_incomplete"
    assert "## Verdict: NOT READY" in (tmp_path / "passed" / "summary.md").read_text(
        encoding="utf-8"
    )


def test_cli_rejects_repo_root_override(tmp_path: Path) -> None:
    result = _run(
        "report",
        "--output",
        str(tmp_path / "evidence"),
        "--repo-root",
        str(tmp_path),
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --repo-root" in result.stderr


def _wheel_source(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "daily-vault"
    for directory in ("pages", "journals", "logseq"):
        (source / directory).mkdir(parents=True, exist_ok=True)
    (source / "pages" / "daily.md").write_text("- daily note\n", encoding="utf-8")
    fingerprint = tmp_path / "daily-vault.realpath"
    fingerprint.write_text(f"{source.resolve()}\n", encoding="utf-8")
    wheel = tmp_path / "matryca_plumber-2.0.0b1-py3-none-any.whl"
    wheel.write_bytes(b"wheel-fixture")
    return source, fingerprint, wheel


def _probe_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "baseline": {"ready": True, "generation_hash": "a" * 64, "duration_ms": 1},
        "candidate": {
            "metadata_version_ok": True,
            "import_from_site_packages": True,
            "warm_ready": True,
            "generation_preserved": True,
            "fts_ok": True,
            "cte_ok": True,
            "flag_off_noop": True,
            "schema_recovery_ok": True,
            "duplicate_failure_non_ready": True,
            "duplicate_fallback_ok": True,
            "duplicate_preserved_generation": True,
            "duplicate_recovery_ok": True,
            "working_markdown_unchanged": True,
            "duration_ms": 1,
        },
    }


def _successful_command(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], 0, stdout="", stderr="")


def test_wheel_requires_exact_daily_source_fingerprint(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    other = tmp_path / "other-vault"
    other.mkdir()
    fingerprint.write_text(f"{other.resolve()}\n", encoding="utf-8")
    with pytest.raises(module.EvidenceError, match="source_fingerprint_mismatch"):
        module.collect_wheel(
            tmp_path / "evidence",
            wheel_path=wheel,
            source_vault=source,
            expected_source_file=fingerprint,
            page_parse_timeout_seconds=60,
        )


def test_wheel_rejects_source_symlinks(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    external = tmp_path / "external.md"
    external.write_text("- external\n", encoding="utf-8")
    try:
        (source / "pages" / "linked.md").symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(module.EvidenceError, match="source_symlink_unsupported"):
        module.collect_wheel(
            tmp_path / "evidence",
            wheel_path=wheel,
            source_vault=source,
            expected_source_file=fingerprint,
            page_parse_timeout_seconds=60,
        )


def test_safe_environment_uses_allowlist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    wheel_module = importlib.import_module("beta_evidence.wheel")
    monkeypatch.setenv("PATH", "/safe/bin")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("PYTHONPATH", "/unsafe/import")
    environment = wheel_module._safe_environment(
        tmp_path, enabled=True, page_parse_timeout_seconds=60
    )
    assert environment["PATH"] == "/safe/bin"
    assert environment["LOGSEQ_GRAPH_PATH"] == str(tmp_path)
    assert environment["MATRYCA_SHADOW_DB_ENABLED"] == "1"
    assert environment["MATRYCA_PAGE_PARSE_TIMEOUT_S"] == "60"
    assert "LLM_API_KEY" not in environment
    assert "GITHUB_TOKEN" not in environment
    assert "PYTHONPATH" not in environment
    assert set(environment).isdisjoint({"LLM_API_KEY", "GITHUB_TOKEN", "PYTHONPATH"})


def test_wheel_records_only_sanitized_pass_and_keeps_source_untouched(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    source_before = module._markdown_fingerprint(source)
    record = module.collect_wheel(
        tmp_path / "evidence",
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        command_runner=_successful_command,
        probe_runner=lambda *_args, **_kwargs: _probe_payload(),
    )
    assert record.status == "PASS"
    assert module._markdown_fingerprint(source) == source_before
    evidence = (tmp_path / "evidence" / "evidence.json").read_text(encoding="utf-8")
    assert str(source) not in evidence
    assert "daily note" not in evidence
    assert "9c1ca0c6" not in evidence
    module.collect_report(tmp_path / "evidence")
    assert "| wheel | PASS |" in (tmp_path / "evidence" / "summary.md").read_text(encoding="utf-8")
    assert "## Verdict: NOT READY" in (tmp_path / "evidence" / "summary.md").read_text(
        encoding="utf-8"
    )


def _code_audit_prerequisites(
    tmp_path: Path,
) -> tuple[ModuleType, Path, Path, Path, str]:
    module = _module()
    output = tmp_path / "evidence"
    module.collect_preflight(
        output,
        candidate_display="2.0.0-beta.1",
        candidate_package="2.0.0b1",
        baseline_package="2.0.0a5",
    )
    source, fingerprint, wheel = _wheel_source(tmp_path)
    record = module.collect_wheel(
        output,
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        command_runner=_successful_command,
        probe_runner=lambda *_args, **_kwargs: _probe_payload(),
    )
    assert record.status == "PASS"
    evidence = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
    wheel_sha256 = evidence["gates"]["wheel"]["details"]["wheel_sha256"]
    return module, output, source, fingerprint, wheel_sha256


def _code_audit_payload(wheel_sha256: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "candidate_package": "2.0.0b1",
        "wheel_sha256": wheel_sha256,
        "candidate_diff_sha256": "d" * 64,
        "diff_verified": True,
        "build_verified": True,
        "ci_verified": True,
        "scope_verified": True,
        "audit_status": "PASS",
        "blocking_findings": 0,
        "advisory_findings": 0,
    }
    payload.update(overrides)
    return payload


def test_code_audit_requires_valid_preflight_and_wheel_evidence(tmp_path: Path) -> None:
    module = _module()
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, _code_audit_payload("a" * 64))
    with pytest.raises(module.EvidenceError, match="code_audit_prerequisite_missing"):
        module.collect_final_code_audit(tmp_path / "evidence", audit_path=audit_path)


def test_code_audit_rejects_malformed_input(tmp_path: Path) -> None:
    module, output, _source, _fingerprint, wheel_sha256 = _code_audit_prerequisites(tmp_path)
    audit_path = tmp_path / "audit.json"
    malformed = _code_audit_payload(wheel_sha256)
    del malformed["ci_verified"]
    _write_json(audit_path, malformed)
    with pytest.raises(module.EvidenceError, match="code_audit_input_invalid"):
        module.collect_final_code_audit(output, audit_path=audit_path)


def test_code_audit_records_sanitized_pass_and_resumes(tmp_path: Path) -> None:
    module, output, _source, _fingerprint, wheel_sha256 = _code_audit_prerequisites(tmp_path)
    audit_path = tmp_path / "audit.json"
    payload = _code_audit_payload(wheel_sha256)
    _write_json(audit_path, payload)
    first = module.collect_final_code_audit(output, audit_path=audit_path)
    checkpoint_before = (output / "checkpoint.json").read_text(encoding="utf-8")
    second = module.collect_final_code_audit(output, audit_path=audit_path)
    expected = {key: value for key, value in payload.items() if key != "schema_version"}
    assert first.status == "PASS"
    assert first == second
    assert first.details == {**expected, "failure_reasons": []}
    assert (output / "checkpoint.json").read_text(encoding="utf-8") == checkpoint_before
    evidence = (output / "evidence.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in evidence
    assert "audit.json" not in evidence
    assert "gate_resumed" in (output / "events.jsonl").read_text(encoding="utf-8")


def test_code_audit_records_mismatch_as_failed_gate_and_cli_fails(tmp_path: Path) -> None:
    module, output, _source, _fingerprint, wheel_sha256 = _code_audit_prerequisites(tmp_path)
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, _code_audit_payload(wheel_sha256, build_verified=False))
    record = module.collect_final_code_audit(output, audit_path=audit_path)
    assert record.status == "FAIL"
    assert record.details["failure_reasons"] == ["build_unverified"]
    assert (
        module.main(["code-audit", "--output", str(output), "--audit-json", str(audit_path)]) == 2
    )


def test_report_is_ready_after_collected_code_audit_and_soak(tmp_path: Path) -> None:
    module, output, source, fingerprint, wheel_sha256 = _code_audit_prerequisites(tmp_path)
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, _code_audit_payload(wheel_sha256))
    assert module.collect_final_code_audit(output, audit_path=audit_path).status == "PASS"
    ticks = iter((0.0, 1.0))
    assert (
        module.collect_soak(
            output,
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "soak-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=1,
            max_cycles=1,
            interval_seconds=0,
            candidate_verifier=lambda _: "e" * 64,
            probe_runner=lambda *_args: _soak_payload(),
            clock=lambda: next(ticks),
            sleeper=lambda _: None,
        ).status
        == "PASS"
    )
    issue_path, disposition_path = _inputs(tmp_path, issues=[], dispositions=[])
    module.collect_issues(output, issues_path=issue_path, dispositions_path=disposition_path)
    module.collect_report(output)
    assert "## Verdict: READY" in (output / "summary.md").read_text(encoding="utf-8")


def test_wheel_timeout_and_malformed_probe_record_safe_failures(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)

    def timeout(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise module.EvidenceError("command_timeout")

    timed_out = module.collect_wheel(
        tmp_path / "timeout",
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        command_runner=timeout,
    )
    assert timed_out.status == "FAIL"
    assert timed_out.details["failure_category"] == "command_timeout"
    assert timed_out.details["page_parse_timeout_seconds"] == 60
    malformed = module.collect_wheel(
        tmp_path / "malformed",
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        command_runner=_successful_command,
        probe_runner=lambda *_args, **_kwargs: {"schema_version": 1},
    )
    assert malformed.status == "FAIL"
    assert malformed.details["failure_category"] == "probe_invalid"


def test_wheel_cli_fails_closed_on_source_mismatch(tmp_path: Path) -> None:
    source, fingerprint, wheel = _wheel_source(tmp_path)
    other = tmp_path / "not-daily"
    for directory in ("pages", "journals", "logseq"):
        (other / directory).mkdir(parents=True, exist_ok=True)
    fingerprint.write_text(f"{other.resolve()}\n", encoding="utf-8")
    result = _run(
        "wheel",
        "--output",
        str(tmp_path / "evidence"),
        "--wheel",
        str(wheel),
        "--source-vault",
        str(source),
        "--expected-source-realpath-file",
        str(fingerprint),
        "--page-parse-timeout-seconds",
        "60",
    )
    assert result.returncode == 2
    assert result.stderr.strip() == "beta evidence: source_fingerprint_mismatch"


def test_wheel_cli_requires_an_explicit_page_parse_deadline(tmp_path: Path) -> None:
    source, fingerprint, wheel = _wheel_source(tmp_path)
    result = _run(
        "wheel",
        "--output",
        str(tmp_path / "evidence"),
        "--wheel",
        str(wheel),
        "--source-vault",
        str(source),
        "--expected-source-realpath-file",
        str(fingerprint),
    )
    assert result.returncode == 2
    assert "--page-parse-timeout-seconds" in result.stderr


def test_soak_cli_requires_an_explicit_page_parse_deadline() -> None:
    cli = importlib.import_module("beta_evidence.cli")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            [
                "soak",
                "--output",
                "/evidence",
                "--candidate-python",
                "/candidate/python",
                "--source-vault",
                "/source",
                "--expected-source-realpath-file",
                "/source.realpath",
                "--working-root",
                "/working",
            ]
        )


def _soak_payload() -> dict[str, object]:
    return {
        "flag_off": True,
        "flag_on": True,
        "restart_health": True,
        "fts": True,
        "subtree": "PASS",
        "synthetic_crud": "PASS",
        "recovery": True,
        "source_count": 3,
        "indexed_count": 3,
        "rss_kib": 128,
        "elapsed_ms": 12.5,
    }


def test_soak_persists_only_sanitized_trends_after_explicit_short_duration(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)
    source_before = module._markdown_fingerprint(source)
    ticks = iter((0.0, 0.4, 1.2))
    record = module.collect_soak(
        tmp_path / "evidence",
        candidate_python=Path(sys.executable),
        source_vault=source,
        expected_source_file=fingerprint,
        working_root=tmp_path / "durable-copy",
        page_parse_timeout_seconds=60,
        duration_seconds=1,
        max_cycles=2,
        interval_seconds=0,
        probe_runner=lambda *_args: _soak_payload(),
        candidate_verifier=lambda _python: "candidate-digest",
        clock=lambda: next(ticks),
    )
    assert record.status == "PASS"
    assert source_before == module._markdown_fingerprint(source)
    state = json.loads((tmp_path / "evidence" / "soak-state.json").read_text(encoding="utf-8"))
    assert state["completed_cycles"] == 2
    assert len(state["trends"]) == 2
    assert [trend["elapsed_ms"] for trend in state["trends"]] == [12.5, 12.5]
    assert state["source_copy_snapshot_fingerprint"] == source_before
    assert state["source_unchanged_during_copy"] is True
    assert state["page_parse_timeout_seconds"] == 60
    for artifact in (
        "checkpoint.json",
        "evidence.json",
        "soak-heartbeat.json",
        "soak-result.json",
        "soak-state.json",
        "soak-summary.md",
    ):
        evidence = (tmp_path / "evidence" / artifact).read_text(encoding="utf-8")
        assert str(source) not in evidence
        assert "daily note" not in evidence
        assert "9c1ca0c6" not in evidence
    assert "RSS KiB range" in (tmp_path / "evidence" / "soak-summary.md").read_text(
        encoding="utf-8"
    )
    assert record.details["beta_qualified"] is False
    assert record.details["page_parse_timeout_seconds"] == 60
    result = json.loads((tmp_path / "evidence" / "soak-result.json").read_text(encoding="utf-8"))
    assert result["page_parse_timeout_seconds"] == 60
    assert "Page parse timeout seconds: 60" in (
        tmp_path / "evidence" / "soak-summary.md"
    ).read_text(encoding="utf-8")


def test_soak_rejects_source_symlinks_and_never_creates_working_copy(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)
    target = source / "pages" / "target.md"
    target.write_text("- private\n", encoding="utf-8")
    (source / "pages" / "linked.md").symlink_to(target)
    work = tmp_path / "durable-copy"
    with pytest.raises(module.EvidenceError, match="source_symlink_unsupported"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=work,
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=1,
            interval_seconds=0,
            probe_runner=lambda *_args: _soak_payload(),
        )
    assert not work.exists()


def test_soak_accepts_source_change_between_interrupted_runs(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=1,
            max_cycles=2,
            interval_seconds=1,
            probe_runner=lambda *_args: _soak_payload(),
            candidate_verifier=lambda _python: "candidate-digest",
            clock=iter((0.0, 0.1)).__next__,
            sleeper=interrupt,
        )
    (source / "pages" / "daily.md").write_text("- changed outside soak\n", encoding="utf-8")
    record = module.collect_soak(
        tmp_path / "evidence",
        candidate_python=Path(sys.executable),
        source_vault=source,
        expected_source_file=fingerprint,
        working_root=tmp_path / "durable-copy",
        page_parse_timeout_seconds=60,
        duration_seconds=1,
        max_cycles=2,
        interval_seconds=1,
        probe_runner=lambda *_args: _soak_payload(),
        candidate_verifier=lambda _python: "candidate-digest",
        clock=iter((0.0, 1.0)).__next__,
    )
    assert record.status == "PASS"
    assert record.details["source_unchanged_during_copy"] is True


def test_soak_rejects_source_change_during_copy_before_probe(tmp_path: Path) -> None:
    module = _module()
    soak = importlib.import_module("beta_evidence.soak")
    source, fingerprint, _wheel = _wheel_source(tmp_path)
    probe_calls = 0

    def changing_copier(source_root: Path, destination: Path) -> None:
        soak._copy_vault_without_cache(source_root, destination)
        (source_root / "pages" / "daily.md").write_text(
            "- legitimate concurrent edit\n", encoding="utf-8"
        )

    def probe(*_args: object) -> dict[str, object]:
        nonlocal probe_calls
        probe_calls += 1
        return _soak_payload()

    with pytest.raises(module.EvidenceError, match="source_changed_during_copy"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=1,
            max_cycles=1,
            interval_seconds=0,
            probe_runner=probe,
            copier=changing_copier,
            candidate_verifier=lambda _python: "candidate-digest",
        )
    assert probe_calls == 0


def test_soak_rejects_working_copy_drift_after_probe(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)

    def mutate_work(
        _python: Path, work: Path, _timeout: int, _page_parse_timeout: int, _cycle: int
    ) -> dict[str, object]:
        (work / "pages" / "daily.md").write_text("- leaked fixture\n", encoding="utf-8")
        return _soak_payload()

    with pytest.raises(module.EvidenceError, match="working_copy_changed"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=1,
            interval_seconds=0,
            probe_runner=mutate_work,
            candidate_verifier=lambda _python: "candidate-digest",
        )


def test_soak_rejects_candidate_version_mismatch_before_copy(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)
    work = tmp_path / "durable-copy"

    def reject_candidate(_python: Path) -> str:
        raise module.EvidenceError("candidate_version_mismatch")

    with pytest.raises(module.EvidenceError, match="candidate_version_mismatch"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=work,
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=1,
            interval_seconds=0,
            candidate_verifier=reject_candidate,
        )
    assert not work.exists()


def test_soak_rejects_candidate_provenance_change_on_resume(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=2,
            interval_seconds=1,
            probe_runner=lambda *_args: _soak_payload(),
            candidate_verifier=lambda _python: "first-candidate-digest",
            clock=iter((0.0, 0.1)).__next__,
            sleeper=interrupt,
        )
    with pytest.raises(module.EvidenceError, match="soak_resume_mismatch"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=2,
            interval_seconds=1,
            candidate_verifier=lambda _python: "replacement-candidate-digest",
        )


def test_soak_does_not_pass_before_configured_duration(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)
    with pytest.raises(module.EvidenceError, match="duration_incomplete"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=1,
            interval_seconds=0,
            probe_runner=lambda *_args: _soak_payload(),
            candidate_verifier=lambda _python: "candidate-digest",
            clock=iter((0.0, 0.1)).__next__,
        )
    state = json.loads((tmp_path / "evidence" / "soak-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "RUNNING"
    assert state["last_failure_category"] == "duration_incomplete"


def test_soak_runs_flag_on_before_non_vacuous_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    soak = importlib.import_module("beta_evidence.soak")
    calls: list[bool] = []

    def fake_process(
        _python: Path,
        _graph: Path,
        _code: str,
        *,
        cycle: int,
        enabled: bool,
        timeout_seconds: int,
        page_parse_timeout_seconds: int,
    ) -> dict[str, object]:
        assert cycle == 0
        assert timeout_seconds == 1
        assert page_parse_timeout_seconds == 60
        calls.append(enabled)
        if enabled:
            return _soak_payload()
        return {"flag_off": True, "rss_kib": 1}

    monkeypatch.setattr(soak, "_run_process", fake_process)
    soak._run_soak_probe(Path(sys.executable), Path("/unused"), 1, 60, 0)
    assert calls == [True, False]


def test_wheel_deadline_is_hashed_recorded_and_cannot_change_on_resume(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    output = tmp_path / "evidence"
    record = module.collect_wheel(
        output,
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        command_runner=_successful_command,
        probe_runner=lambda *_args, **_kwargs: _probe_payload(),
    )
    assert record.details["page_parse_timeout_seconds"] == 60
    with pytest.raises(module.EvidenceError, match="gate_resume_mismatch"):
        module.collect_wheel(
            output,
            wheel_path=wheel,
            source_vault=source,
            expected_source_file=fingerprint,
            page_parse_timeout_seconds=61,
            command_runner=_successful_command,
            probe_runner=lambda *_args, **_kwargs: _probe_payload(),
        )


def test_wheel_keeps_page_parse_and_subprocess_deadlines_distinct(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    command_timeouts: list[int] = []
    probe_deadlines: list[tuple[int, int]] = []

    def command(
        *_args: object, timeout_seconds: int, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command_timeouts.append(timeout_seconds)
        return _successful_command()

    def probe(
        *_args: object,
        timeout_seconds: int,
        page_parse_timeout_seconds: int,
        **_kwargs: object,
    ) -> dict[str, object]:
        probe_deadlines.append((timeout_seconds, page_parse_timeout_seconds))
        return _probe_payload()

    record = module.collect_wheel(
        tmp_path / "evidence",
        wheel_path=wheel,
        source_vault=source,
        expected_source_file=fingerprint,
        page_parse_timeout_seconds=60,
        timeout_seconds=19,
        command_runner=command,
        probe_runner=probe,
    )
    assert record.status == "PASS"
    assert command_timeouts == [19, 19, 19]
    assert probe_deadlines == [(19, 60), (19, 60)]


@pytest.mark.parametrize("value", (1, 121))
def test_collectors_reject_page_parse_deadlines_outside_bounds(tmp_path: Path, value: int) -> None:
    module = _module()
    source, fingerprint, wheel = _wheel_source(tmp_path)
    with pytest.raises(module.EvidenceError, match="page_parse_timeout_invalid"):
        module.collect_wheel(
            tmp_path / "wheel-evidence",
            wheel_path=wheel,
            source_vault=source,
            expected_source_file=fingerprint,
            page_parse_timeout_seconds=value,
        )
    with pytest.raises(module.EvidenceError, match="page_parse_timeout_invalid"):
        module.collect_soak(
            tmp_path / "soak-evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=value,
        )


def test_soak_deadline_change_rejects_an_interrupted_resume(tmp_path: Path) -> None:
    module = _module()
    source, fingerprint, _wheel = _wheel_source(tmp_path)

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=60,
            duration_seconds=60,
            max_cycles=2,
            interval_seconds=1,
            probe_runner=lambda *_args: _soak_payload(),
            candidate_verifier=lambda _python: "candidate-digest",
            clock=iter((0.0, 0.1)).__next__,
            sleeper=interrupt,
        )
    with pytest.raises(module.EvidenceError, match="soak_resume_mismatch"):
        module.collect_soak(
            tmp_path / "evidence",
            candidate_python=Path(sys.executable),
            source_vault=source,
            expected_source_file=fingerprint,
            working_root=tmp_path / "durable-copy",
            page_parse_timeout_seconds=61,
            duration_seconds=60,
            max_cycles=2,
            interval_seconds=1,
            candidate_verifier=lambda _python: "candidate-digest",
        )
