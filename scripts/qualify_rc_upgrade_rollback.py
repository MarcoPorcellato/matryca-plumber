#!/usr/bin/env python3
"""Collect sanitized installed-wheel upgrade and rollback evidence for an RC."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from beta_evidence.core import EvidenceError, validate_output_directory
from beta_evidence.wheel import _markdown_fingerprint

_PACKAGE_VERSION = re.compile(r"\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?")
_RESULT_NAME = "rc-upgrade-rollback-result.json"
_PROCESS_TIMEOUT_SECONDS = 600
_PAGE_PARSE_TIMEOUT_SECONDS = 15

CommandRunner = Callable[
    [Sequence[str], Path, dict[str, str], int], subprocess.CompletedProcess[str]
]
ProbeRunner = Callable[[Path, Path, Path, str, int], dict[str, bool]]


def _require_package_version(value: str, *, category: str) -> str:
    if _PACKAGE_VERSION.fullmatch(value) is None:
        raise EvidenceError(category)
    return value


def _safe_environment(graph: Path, cache_root: Path) -> dict[str, str]:
    environment = {"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"}
    environment.update(
        {
            "LOGSEQ_GRAPH_PATH": str(graph),
            "MATRYCA_CACHE_PATH": str(cache_root),
            "MATRYCA_PAGE_PARSE_TIMEOUT_S": str(_PAGE_PARSE_TIMEOUT_SECONDS),
        }
    )
    return environment


def _resolve_source_vault(source_vault: Path, expected_source_file: Path) -> Path:
    try:
        source = source_vault.expanduser().resolve(strict=True)
        expected_lines = expected_source_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise EvidenceError("source_fingerprint_invalid") from exc
    if len(expected_lines) != 1 or not expected_lines[0]:
        raise EvidenceError("source_fingerprint_invalid")
    try:
        expected = Path(expected_lines[0]).expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("source_fingerprint_invalid") from exc
    if source != expected:
        raise EvidenceError("source_fingerprint_mismatch")
    if not source.is_dir() or not all(
        (source / name).is_dir() for name in ("pages", "journals", "logseq")
    ):
        raise EvidenceError("source_vault_invalid")
    if any(
        path.is_symlink()
        for directory in (source / "pages", source / "journals")
        for path in directory.rglob("*")
    ):
        raise EvidenceError("source_symlink_unsupported")
    return source


def _run_command(
    command: Sequence[str], cwd: Path, environment: dict[str, str], timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            list(command),
            cwd=cwd,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvidenceError("command_timeout") from exc
    except OSError as exc:
        raise EvidenceError("command_error") from exc


def _require_success(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode != 0:
        raise EvidenceError("command_failed")


def _installed_package_probe(python: Path, expected_package: str) -> bool:
    probe = (
        "from importlib.metadata import version\n"
        "from pathlib import Path\n"
        "import sys\n"
        "import src\n"
        "origin = Path(src.__file__ or '').resolve()\n"
        "prefix = Path(sys.prefix).resolve()\n"
        f"assert version('matryca-plumber') == {expected_package!r}\n"
        "assert origin.is_relative_to(prefix)\n"
        "assert any(part in ('site-packages', 'dist-packages') for part in origin.parts)\n"
    )
    try:
        completed = subprocess.run(  # noqa: S603
            [str(python), "-c", probe],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("installed_package_invalid") from exc
    return completed.returncode == 0


def _candidate_probe(
    python: Path, graph: Path, cache_root: Path, candidate_package: str, timeout: int
) -> dict[str, bool]:
    script = f"""
import hashlib
import json
import os
import sqlite3
from importlib.metadata import version
from pathlib import Path

graph = Path({str(graph)!r})
cache_root = Path({str(cache_root)!r})
def fingerprints(root, suffix=None):
    paths = sorted(root.rglob(f'*{{suffix}}')) if suffix else sorted(root.rglob('*'))
    return {{
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }}

before = fingerprints(graph, '.md')
graph_files_before = fingerprints(graph)
os.environ.pop('MATRYCA_SHADOW_DB_ENABLED', None)
os.environ.pop('MATRYCA_READ_ONLY', None)
os.environ['MATRYCA_CACHE_PATH'] = str(cache_root / 'default')
from src.shadow.bootstrap import (
    ensure_shadow_runtime_at_startup,
    reset_shadow_bootstrap_checked_for_tests,
)
from src.shadow.config import shadow_db_enabled
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.cache_location import resolve_shadow_cache_location
from src.agent.shadow_graph_repository import shadow_read_port_ready

reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
default_location = resolve_shadow_cache_location(graph)
default_on_ready = shadow_db_enabled() and resolve_shadow_health(graph) is ShadowHealthState.READY
external_cache_only = (
    default_location.database_path.is_relative_to(cache_root)
    and not default_location.database_path.is_relative_to(graph)
)

with sqlite3.connect(default_location.database_path) as connection:
    connection.execute(
        "UPDATE shadow_meta SET value = ? WHERE key = 'schema_version'", ('999999',)
    )
schema_mismatch_fallback = (
    resolve_shadow_health(graph) is not ShadowHealthState.READY
    and not shadow_read_port_ready(graph)
)
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
schema_mismatch_recovered = resolve_shadow_health(graph) is ShadowHealthState.READY

with sqlite3.connect(default_location.database_path) as connection:
    connection.execute(
        "UPDATE shadow_meta SET value = ? WHERE key = 'last_full_sync_completed'", ('false',)
    )
import src.shadow.bootstrap as bootstrap
original_rebuild = bootstrap.rebuild_shadow_from_graph
try:
    bootstrap.rebuild_shadow_from_graph = lambda _graph: (_ for _ in ()).throw(RuntimeError())
    reset_shadow_bootstrap_checked_for_tests()
    ensure_shadow_runtime_at_startup(graph)
finally:
    bootstrap.rebuild_shadow_from_graph = original_rebuild
failed_rebuild_fallback = (
    resolve_shadow_health(graph) is not ShadowHealthState.READY
    and not shadow_read_port_ready(graph)
)
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
failed_rebuild_recovered = resolve_shadow_health(graph) is ShadowHealthState.READY

os.environ['MATRYCA_SHADOW_DB_ENABLED'] = 'false'
os.environ['MATRYCA_CACHE_PATH'] = str(cache_root / 'opt-out')
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
explicit_false = (
    not shadow_db_enabled()
    and not any((cache_root / 'opt-out').rglob('shadow.sqlite'))
)

os.environ.pop('MATRYCA_SHADOW_DB_ENABLED', None)
os.environ['MATRYCA_READ_ONLY'] = 'true'
os.environ['MATRYCA_CACHE_PATH'] = str(cache_root / 'read-only')
reset_shadow_bootstrap_checked_for_tests()
ensure_shadow_runtime_at_startup(graph)
read_only_location = resolve_shadow_cache_location(graph)
read_only_ready = resolve_shadow_health(graph) is ShadowHealthState.READY
read_only_external_cache = (
    read_only_location.database_path.is_relative_to(cache_root)
    and not read_only_location.database_path.is_relative_to(graph)
)
after = fingerprints(graph, '.md')
graph_files_after = fingerprints(graph)
print(json.dumps({{
    'candidate_version': version('matryca-plumber') == {candidate_package!r},
    'default_on_ready': default_on_ready,
    'explicit_false': explicit_false,
    'external_cache_only': external_cache_only,
    'schema_mismatch_fallback': schema_mismatch_fallback,
    'schema_mismatch_recovered': schema_mismatch_recovered,
    'failed_rebuild_fallback': failed_rebuild_fallback,
    'failed_rebuild_recovered': failed_rebuild_recovered,
    'read_only_ready': read_only_ready,
    'read_only_external_cache': read_only_external_cache,
    'markdown_unchanged': before == after,
    'graph_files_unchanged': graph_files_before == graph_files_after,
}}, sort_keys=True))
"""
    environment = _safe_environment(graph, cache_root)
    try:
        completed = subprocess.run(  # noqa: S603
            [str(python), "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvidenceError("candidate_probe_failed") from exc
    if completed.returncode != 0:
        raise EvidenceError("candidate_probe_failed")
    try:
        payload: object = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EvidenceError("candidate_probe_invalid") from exc
    expected = {
        "candidate_version",
        "default_on_ready",
        "explicit_false",
        "external_cache_only",
        "schema_mismatch_fallback",
        "schema_mismatch_recovered",
        "failed_rebuild_fallback",
        "failed_rebuild_recovered",
        "read_only_ready",
        "read_only_external_cache",
        "markdown_unchanged",
        "graph_files_unchanged",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != expected
        or not all(isinstance(value, bool) for value in payload.values())
    ):
        raise EvidenceError("candidate_probe_invalid")
    return payload


def _atomic_write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def collect_upgrade_rollback(
    output: Path,
    *,
    wheel: Path,
    candidate_package: str,
    baselines: Sequence[str],
    source_vault: Path,
    expected_source_file: Path,
    timeout_seconds: int = _PROCESS_TIMEOUT_SECONDS,
    command_runner: CommandRunner = _run_command,
    candidate_probe: ProbeRunner = _candidate_probe,
    installed_probe: Callable[[Path, str], bool] = _installed_package_probe,
) -> dict[str, Any]:
    """Collect one fail-closed upgrade/rollback result per published baseline."""
    candidate_package = _require_package_version(
        candidate_package, category="candidate_package_invalid"
    )
    normalized_baselines = tuple(
        _require_package_version(value, category="baseline_package_invalid") for value in baselines
    )
    if not normalized_baselines or len(set(normalized_baselines)) != len(normalized_baselines):
        raise EvidenceError("baseline_packages_invalid")
    if not 1 <= timeout_seconds <= _PROCESS_TIMEOUT_SECONDS:
        raise EvidenceError("timeout_invalid")
    source = _resolve_source_vault(source_vault, expected_source_file)
    try:
        candidate_wheel = wheel.expanduser().resolve(strict=True)
    except OSError as exc:
        raise EvidenceError("input_invalid") from exc
    if not source.is_dir() or not candidate_wheel.is_file() or candidate_wheel.suffix != ".whl":
        raise EvidenceError("input_invalid")
    resolved_output = validate_output_directory(
        output, repo_root=Path(__file__).resolve().parents[1], protected_roots=[source]
    )
    resolved_output.mkdir(parents=True, exist_ok=True)
    source_before = _markdown_fingerprint(source)
    result: dict[str, Any] = {
        "schema_version": 1,
        "candidate_package": candidate_package,
        "candidate_wheel_sha256": hashlib.sha256(candidate_wheel.read_bytes()).hexdigest(),
        "source_unchanged": True,
        "baselines": [],
        "status": "FAIL",
    }
    temporary_root = Path(tempfile.mkdtemp(prefix="matryca-rc-upgrade-", dir=resolved_output))
    try:
        for baseline in normalized_baselines:
            working_vault = temporary_root / baseline / "vault"
            cache_root = temporary_root / baseline / "cache"
            venv = temporary_root / baseline / "venv"
            shutil.copytree(
                source, working_vault, ignore=shutil.ignore_patterns(".matryca_semantic_cache")
            )
            environment = _safe_environment(working_vault, cache_root)
            python = venv / "bin" / "python"
            for command in (
                ("uv", "venv", str(venv)),
                ("uv", "pip", "install", "--python", str(python), f"matryca-plumber=={baseline}"),
            ):
                _require_success(
                    command_runner(command, temporary_root, environment, timeout_seconds)
                )
            baseline_installed = installed_probe(python, baseline)
            _require_success(
                command_runner(
                    (
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        str(python),
                        "--reinstall",
                        str(candidate_wheel),
                    ),
                    temporary_root,
                    environment,
                    timeout_seconds,
                )
            )
            candidate = candidate_probe(
                python, working_vault, cache_root, candidate_package, timeout_seconds
            )
            _require_success(
                command_runner(
                    (
                        "uv",
                        "pip",
                        "install",
                        "--python",
                        str(python),
                        "--reinstall",
                        f"matryca-plumber=={baseline}",
                    ),
                    temporary_root,
                    environment,
                    timeout_seconds,
                )
            )
            rollback_installed = installed_probe(python, baseline)
            result["baselines"].append(
                {
                    "package": baseline,
                    "baseline_installed": baseline_installed,
                    "candidate": candidate,
                    "rollback_installed": rollback_installed,
                    "working_markdown_unchanged": _markdown_fingerprint(working_vault)
                    == _markdown_fingerprint(source),
                }
            )
        result["source_unchanged"] = _markdown_fingerprint(source) == source_before
        result["status"] = (
            "PASS"
            if result["source_unchanged"]
            and all(
                row["baseline_installed"]
                and row["rollback_installed"]
                and row["working_markdown_unchanged"]
                and all(row["candidate"].values())
                for row in result["baselines"]
            )
            else "FAIL"
        )
    except EvidenceError as exc:
        result["failure_category"] = exc.category
        result["source_unchanged"] = _markdown_fingerprint(source) == source_before
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
    _atomic_write_json(resolved_output / _RESULT_NAME, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--candidate-package", required=True)
    parser.add_argument("--baseline", action="append", required=True)
    parser.add_argument("--source-vault", required=True)
    parser.add_argument("--expected-source-realpath-file", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=_PROCESS_TIMEOUT_SECONDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = collect_upgrade_rollback(
            Path(args.output),
            wheel=Path(args.wheel),
            candidate_package=args.candidate_package,
            baselines=args.baseline,
            source_vault=Path(args.source_vault),
            expected_source_file=Path(args.expected_source_realpath_file),
            timeout_seconds=args.timeout_seconds,
        )
    except EvidenceError as exc:
        print(f"rc upgrade rollback: {exc.category}", file=sys.stderr)
        return 2
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
