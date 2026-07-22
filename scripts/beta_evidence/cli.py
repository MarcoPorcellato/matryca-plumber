"""CLI orchestration for the private beta-evidence package."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import (
    EvidenceError,
    GateRecord,
    _repo_root_from_script,
    collect_final_code_audit,
    collect_issues,
    collect_preflight,
    collect_report,
    validate_output_directory,
)
from .soak import (
    _DEFAULT_DURATION_SECONDS,
    _DEFAULT_INTERVAL_SECONDS,
    _DEFAULT_MAX_CYCLES,
    collect_soak,
)
from .wheel import _WHEEL_TIMEOUT_SECONDS, collect_wheel, wheel_probe_main


def _protected_roots(args: argparse.Namespace) -> list[Path]:
    return [
        Path(value)
        for name in ("vault_root", "source_root")
        if (value := getattr(args, name, None)) is not None
    ]


def _prepare_output(args: argparse.Namespace) -> Path:
    return validate_output_directory(
        Path(args.output),
        repo_root=_repo_root_from_script(),
        protected_roots=_protected_roots(args),
    )


def _run_preflight(args: argparse.Namespace, output: Path) -> GateRecord:
    return collect_preflight(
        output,
        candidate_display=args.candidate_display,
        candidate_package=args.candidate_package,
        baseline_package=args.baseline_package,
    )


def _require_success(record: GateRecord) -> None:
    if record.status != "PASS":
        raise EvidenceError("gate_failed")


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        required=True,
        help="Explicit evidence directory outside repository and vault roots.",
    )
    parser.add_argument("--vault-root", help="Protected vault root; output may not be inside it.")
    parser.add_argument(
        "--source-root", help="Protected source-copy root; output may not be inside it."
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser while keeping private probes out of normal help."""
    parser = argparse.ArgumentParser(
        description="Collect deterministic, sanitized beta readiness evidence."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    preflight = subcommands.add_parser(
        "preflight", help="Record release naming and sanitized host evidence."
    )
    _add_output_arguments(preflight)
    preflight.add_argument(
        "--candidate-display", required=True, help="SemVer display version, e.g. 2.0.0-beta.1."
    )
    preflight.add_argument(
        "--candidate-package", required=True, help="Python package version, e.g. 2.0.0b1."
    )
    preflight.add_argument(
        "--baseline-package",
        required=True,
        help="Installed baseline package version, e.g. 2.0.0a5.",
    )
    issues = subcommands.add_parser(
        "issues", help="Evaluate sanitized issue severity and disposition input."
    )
    _add_output_arguments(issues)
    issues.add_argument(
        "--issues-json", required=True, help="Path to the documented schema-version 1 issue input."
    )
    issues.add_argument(
        "--p2-dispositions",
        required=True,
        help="Path to the documented schema-version 1 P2 disposition input.",
    )
    report = subcommands.add_parser(
        "report", help="Generate a path-free summary from collected evidence."
    )
    _add_output_arguments(report)
    wheel = subcommands.add_parser(
        "wheel", help="Collect isolated PyPI-to-wheel upgrade evidence from a copied vault."
    )
    _add_output_arguments(wheel)
    wheel.add_argument(
        "--wheel", required=True, help="Explicit candidate .whl outside the source vault."
    )
    wheel.add_argument(
        "--source-vault", required=True, help="Daily Logseq vault copied for the probe."
    )
    wheel.add_argument(
        "--expected-source-realpath-file",
        required=True,
        help="Private one-line file containing the resolved daily-vault path.",
    )
    wheel.add_argument(
        "--timeout-seconds",
        type=int,
        default=_WHEEL_TIMEOUT_SECONDS,
        help="Per-subprocess timeout, bounded to 1-600 seconds.",
    )
    wheel.add_argument(
        "--page-parse-timeout-seconds",
        required=True,
        type=int,
        help="Required child page-parse deadline, bounded to 2-120 seconds.",
    )
    soak = subcommands.add_parser(
        "soak", help="Collect resumable, sanitized Shadow DB evidence from a durable vault copy."
    )
    _add_output_arguments(soak)
    soak.add_argument(
        "--candidate-python", required=True, help="Explicit candidate virtualenv Python."
    )
    soak.add_argument("--source-vault", required=True, help="Explicit read-only source vault.")
    soak.add_argument(
        "--expected-source-realpath-file",
        required=True,
        help="Private one-line file containing the resolved source-vault path.",
    )
    soak.add_argument(
        "--working-root",
        required=True,
        help=(
            "Empty durable working-copy directory outside source, repository, and evidence output."
        ),
    )
    soak.add_argument(
        "--duration-seconds",
        type=int,
        default=_DEFAULT_DURATION_SECONDS,
        help="Bounded total collection duration, default 24 hours (maximum 7 days).",
    )
    soak.add_argument(
        "--max-cycles",
        type=int,
        default=_DEFAULT_MAX_CYCLES,
        help=f"Bounded probe cycles, default {_DEFAULT_MAX_CYCLES}.",
    )
    soak.add_argument(
        "--interval-seconds",
        type=int,
        default=_DEFAULT_INTERVAL_SECONDS,
        help="Delay between cycles, default 600 seconds.",
    )
    soak.add_argument(
        "--page-parse-timeout-seconds",
        required=True,
        type=int,
        help="Required child page-parse deadline, bounded to 2-120 seconds.",
    )
    code_audit = subcommands.add_parser(
        "code-audit", help="Record sanitized final code audit evidence for the candidate wheel."
    )
    _add_output_arguments(code_audit)
    code_audit.add_argument(
        "--audit-json",
        required=True,
        help="Path to the documented schema-version 1 code audit input.",
    )
    run = subcommands.add_parser(
        "run", help="Run preflight, issue evaluation, and report in order."
    )
    _add_output_arguments(run)
    run.add_argument(
        "--candidate-display", required=True, help="SemVer display version, e.g. 2.0.0-beta.1."
    )
    run.add_argument(
        "--candidate-package", required=True, help="Python package version, e.g. 2.0.0b1."
    )
    run.add_argument(
        "--baseline-package",
        required=True,
        help="Installed baseline package version, e.g. 2.0.0a5.",
    )
    run.add_argument(
        "--issues-json", required=True, help="Path to the documented schema-version 1 issue input."
    )
    run.add_argument(
        "--p2-dispositions",
        required=True,
        help="Path to the documented schema-version 1 P2 disposition input.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a stable privacy-safe exit status."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "_wheel-probe":
        probe = argparse.ArgumentParser(add_help=False)
        probe.add_argument("_wheel_probe")
        probe.add_argument("--vault", required=True)
        probe.add_argument("--phase", required=True, choices=("baseline", "candidate"))
        args = probe.parse_args(arguments)
        try:
            return wheel_probe_main(Path(args.vault), args.phase)
        except (EvidenceError, OSError):
            return 2
    args = build_parser().parse_args(arguments)
    try:
        output = _prepare_output(args)
        if args.command == "preflight":
            _require_success(_run_preflight(args, output))
        elif args.command == "issues":
            _require_success(
                collect_issues(
                    output,
                    issues_path=Path(args.issues_json),
                    dispositions_path=Path(args.p2_dispositions),
                )
            )
        elif args.command == "report":
            collect_report(output)
        elif args.command == "wheel":
            _require_success(
                collect_wheel(
                    output,
                    wheel_path=Path(args.wheel),
                    source_vault=Path(args.source_vault),
                    expected_source_file=Path(args.expected_source_realpath_file),
                    page_parse_timeout_seconds=args.page_parse_timeout_seconds,
                    timeout_seconds=args.timeout_seconds,
                )
            )
        elif args.command == "soak":
            _require_success(
                collect_soak(
                    output,
                    candidate_python=Path(args.candidate_python),
                    source_vault=Path(args.source_vault),
                    expected_source_file=Path(args.expected_source_realpath_file),
                    working_root=Path(args.working_root),
                    duration_seconds=args.duration_seconds,
                    max_cycles=args.max_cycles,
                    interval_seconds=args.interval_seconds,
                    page_parse_timeout_seconds=args.page_parse_timeout_seconds,
                )
            )
        elif args.command == "code-audit":
            _require_success(collect_final_code_audit(output, audit_path=Path(args.audit_json)))
        elif args.command == "run":
            preflight = _run_preflight(args, output)
            issues = collect_issues(
                output,
                issues_path=Path(args.issues_json),
                dispositions_path=Path(args.p2_dispositions),
            )
            report = collect_report(output)
            _require_success(preflight)
            _require_success(issues)
            if report.details.get("ready") is not True:
                raise EvidenceError("readiness_incomplete")
        else:
            raise EvidenceError("command_invalid")
    except EvidenceError as exc:
        print(f"beta evidence: {exc.category}", file=sys.stderr)
        return 2
    except OSError:
        print("beta evidence: storage_error", file=sys.stderr)
        return 2
    return 0
