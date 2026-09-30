"""Frozen, source-bound focused pytest controls for release qualification."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO, Literal

import pytest
from _pytest.main import Session
from _pytest.reports import TestReport

from scripts.release_qualification import process as process_module

FocusedPlatform = Literal["linux", "macos", "windows"]

MAX_CAPTURE_BYTES = 64 * 1024
_TERMINATION_WAIT_SECONDS = 5.0
_LINUX_MACOS_NODES = (
    "tests/test_og_parser_identity_adapter.py::test_parser_receives_exact_admitted_snapshot_from_one_source_read",
    "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_oversize_snapshot_before_parser_invocation",
    "tests/test_og_parser_identity_adapter.py::test_adapter_rejects_same_size_replacement_inode_after_descriptor_read",
    "tests/test_og_topology_session_read.py::test_og_topology_uses_one_complete_parser_snapshot_without_content_leakage",
    "tests/test_og_topology_session_read.py::test_og_topology_rejects_unresolved_block_reference",
    "tests/test_og_topology_session_read.py::test_og_topology_rejects_title_collision",
    "tests/test_og_topology_session_read.py::test_og_topology_excludes_aggregate_page_property_refs",
    "tests/test_og_identity_session_read.py::test_consumer_receives_only_plumber_owned_identity_response",
    "tests/test_og_identity_session_read.py::test_close_is_idempotent_and_rejects_every_later_identity_read",
    "tests/test_og_identity_session_read.py::test_identity_rejects_foreign_graph_binding",
    "tests/test_logseq_db_official_host_capability_protocol.py::test_no_supported_fixture_is_committed_before_runtime_evidence",
    "tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker",
    "tests/test_bounded_page_parse.py::test_timeout_then_healthy_parse_gets_new_pid",
    "tests/test_bounded_page_parse.py::test_no_stale_result_after_timeout",
    "tests/test_bounded_page_parse.py::test_worker_crash_recovers_bounded",
    "tests/test_ast_cache_bounded_parse.py::test_bounded_timeout_does_not_publish_partial_graph",
    "tests/test_ast_cache_bounded_parse.py::test_incremental_timeout_preserves_exact_last_complete_graph",
)
_WINDOWS_NODES = (
    "tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker",
    "tests/test_bounded_page_parse.py::test_timeout_then_healthy_parse_gets_new_pid",
    "tests/test_bounded_page_parse.py::test_no_stale_result_after_timeout",
    "tests/test_bounded_page_parse.py::test_worker_survives_success_and_shuts_clean",
)
_PLATFORM_NAMES = ("linux", "macos", "windows")
_SOURCE_ID = re.compile(r"[0-9a-f]{40}\Z")
_PLUGIN_ENV = "MATRYCA_FOCUSED_EXPECTED_NODES"
_PLUGIN_ACTIVE_ENV = "MATRYCA_FOCUSED_ENFORCE"
_PLUGIN_REPO_ROOT = Path(__file__).resolve().parents[2]
_IS_WINDOWS = os.name == "nt"
_WindowsJob = process_module.WindowsJob
_WINDOWS_GATE_CODE = (
    "import subprocess,sys; "
    "token=sys.stdin.buffer.read(1); "
    "sys.exit(subprocess.run(sys.argv[1:], stdin=subprocess.DEVNULL, "
    "stdout=sys.stdout, stderr=sys.stderr).returncode) "
    "if token == b'G' else sys.exit(125)"
)


def focused_nodes(platform: FocusedPlatform) -> tuple[str, ...]:
    """Return the immutable, reviewed pytest node selection for one platform."""
    if platform not in _PLATFORM_NAMES:
        raise ValueError("Unsupported focused-test platform.")
    return _WINDOWS_NODES if platform == "windows" else _LINUX_MACOS_NODES


@dataclass(frozen=True)
class FocusedCounts:
    passed: int
    failed: int
    skipped: int


@dataclass(frozen=True)
class FocusedReceipt:
    source_commit: str
    platform: FocusedPlatform
    selected: int
    selected_nodes: tuple[str, ...]
    passed: int
    failed: int
    skipped: int

    def to_dict(self) -> dict[str, str | int | tuple[str, ...]]:
        """Return only sanitized source/platform/count evidence."""
        return asdict(self)


def _resolve_source_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not resolve the focused-test source commit.") from error


def _require_exact_clean_source(repo_root: Path, source_commit: str) -> None:
    """Bind focused execution to this checkout and reject tracked or untracked edits."""
    if repo_root.resolve() != _PLUGIN_REPO_ROOT.resolve():
        raise ValueError("Repository root does not match qualification source.")
    if _resolve_source_commit(repo_root) != source_commit:
        raise ValueError("Source commit changed during focused qualification.")
    try:
        status = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignore-submodules=none",
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("Could not verify focused-test source cleanliness.") from error
    if status.stdout:
        raise ValueError("Source checkout is not clean.")


def run_focused(repo_root: Path, platform: FocusedPlatform, source_commit: str) -> FocusedReceipt:
    """Run the frozen selection and return counts bound to the exact source SHA."""
    nodes = focused_nodes(platform)
    if _SOURCE_ID.fullmatch(source_commit) is None:
        raise ValueError("Source commit must be a lowercase full Git ID.")
    if _resolve_source_commit(repo_root) != source_commit:
        raise ValueError("Source commit does not match requested SHA.")
    _require_exact_clean_source(repo_root, source_commit)

    counts = _run_pytest(repo_root, nodes, source_commit)
    _require_exact_clean_source(repo_root, source_commit)
    if counts.passed != len(nodes) or counts.failed != 0 or counts.skipped != 0:
        raise ValueError("Focused tests did not all pass without skips.")
    return FocusedReceipt(
        source_commit=source_commit,
        platform=platform,
        selected=len(nodes),
        selected_nodes=nodes,
        passed=counts.passed,
        failed=counts.failed,
        skipped=counts.skipped,
    )


def _run_pytest(
    repo_root: Path, nodes: tuple[str, ...], source_commit: str | None = None
) -> FocusedCounts:
    """Require an exact successful collection, then execute without skip/xfail."""
    if not nodes or len(set(nodes)) != len(nodes):
        raise ValueError("Focused selection must contain unique test nodes.")
    if source_commit is not None:
        _require_exact_clean_source(repo_root, source_commit)

    collect_command = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-o",
        "addopts=",
        "-o",
        "xfail_strict=true",
        "--strict-markers",
        *nodes,
    ]
    collection = _run_command(
        collect_command,
        repo_root,
        "Focused test collection failed.",
        allow_usage_error=True,
    )
    if collection.returncode != 0:
        raise ValueError("Focused test collection did not match selection.")
    collected = tuple(
        line.strip()
        for line in collection.stdout.splitlines()
        if "::" in line and not line.lstrip().startswith(("E ", "="))
    )
    if collected != nodes:
        raise ValueError("Focused test collection did not match selection.")
    if source_commit is not None:
        _require_exact_clean_source(repo_root, source_commit)

    with tempfile.TemporaryDirectory(prefix="matryca-focused-") as report_dir:
        report_path = Path(report_dir) / "pytest.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-o",
            "xfail_strict=true",
            "-o",
            "junit_logging=none",
            "-o",
            "junit_log_passing_tests=false",
            "--strict-markers",
            "--junitxml",
            str(report_path),
            "-p",
            "scripts.release_qualification.focused",
            *nodes,
        ]
        environment = os.environ.copy()
        environment[_PLUGIN_ACTIVE_ENV] = "1"
        environment[_PLUGIN_ENV] = json.dumps(nodes, separators=(",", ":"))
        existing_path = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(_PLUGIN_REPO_ROOT), existing_path) if part
        )
        _run_command(
            command,
            repo_root,
            "Focused tests failed.",
            env=environment,
            watched_file=report_path,
        )
        if source_commit is not None:
            _require_exact_clean_source(repo_root, source_commit)
        counts = _read_counts(report_path)

    if counts.skipped:
        raise ValueError("Focused tests contained skip or xfail reports.")
    if counts.passed != len(nodes) or counts.failed != 0:
        raise ValueError("Focused tests did not all pass.")
    return counts


def _run_command(
    command: list[str],
    repo_root: Path,
    failure_message: str,
    *,
    env: dict[str, str] | None = None,
    allow_usage_error: bool = False,
    timeout: float = 300.0,
    watched_file: Path | None = None,
    watched_file_limit: int = MAX_CAPTURE_BYTES,
) -> subprocess.CompletedProcess[str]:
    """Drain both pipes concurrently with one bounded capture and owned process cleanup."""
    if watched_file_limit < 0:
        raise ValueError("Watched file limit must not be negative.")
    try:
        process, job = _spawn_process(command, repo_root, env)
    except OSError as error:
        raise ValueError(failure_message) from error
    owned = process_module.OwnedProcess(process, windows=_IS_WINDOWS, job=job)
    readers: list[threading.Thread] = []
    primary_error: BaseException | None = None
    try:
        result = _run_spawned_command(
            process,
            command,
            failure_message,
            allow_usage_error=allow_usage_error,
            timeout=timeout,
            watched_file=watched_file,
            watched_file_limit=watched_file_limit,
            readers=readers,
        )
        owned.require_empty()
        return result
    except BaseException as error:
        primary_error = error
        cleanup_error = _terminate_owned_process(process, job)
        if cleanup_error is not None:
            error.add_note(f"Owned process cleanup also failed: {type(cleanup_error).__name__}.")
        try:
            if not _join_readers(tuple(readers), timeout=1.0):
                error.add_note("Owned output reader threads remained active after cleanup.")
        except RuntimeError as join_error:
            error.add_note(f"Output reader join also failed: {type(join_error).__name__}.")
        raise
    finally:
        if job is not None:
            try:
                owned.close()
            except Exception as close_error:
                if primary_error is not None:
                    primary_error.add_note(
                        f"Windows Job Object close also failed: {type(close_error).__name__}."
                    )
                else:
                    raise ValueError(
                        "Could not close Windows qualification Job Object."
                    ) from close_error


def _run_spawned_command(
    process: subprocess.Popen[bytes],
    command: list[str],
    failure_message: str,
    *,
    allow_usage_error: bool,
    timeout: float,
    watched_file: Path | None,
    watched_file_limit: int,
    readers: list[threading.Thread],
) -> subprocess.CompletedProcess[str]:
    if process.stdout is None or process.stderr is None:
        raise ValueError("Focused subprocess pipes were unavailable.")

    capture = _BoundedCapture()
    reader_candidates = (
        threading.Thread(
            target=_drain_pipe,
            args=(process.stdout, capture, "stdout"),
            name="focused-stdout-drain",
            daemon=True,
        ),
        threading.Thread(
            target=_drain_pipe,
            args=(process.stderr, capture, "stderr"),
            name="focused-stderr-drain",
            daemon=True,
        ),
    )
    started_readers: list[threading.Thread] = []
    for reader in reader_candidates:
        reader.start()
        started_readers.append(reader)
        readers.append(reader)

    deadline = time.monotonic() + timeout
    while process.poll() is None:
        watched_file_error = _watched_file_error(watched_file, watched_file_limit)
        if watched_file_error is not None:
            raise ValueError(watched_file_error)
        if capture.overflow.is_set():
            raise ValueError("Focused command output exceeded limit.")
        if capture.reader_failed.is_set():
            raise ValueError("Focused command output reader failed.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Focused command timed out.")
        time.sleep(min(0.02, remaining))

    if not _join_readers(tuple(started_readers), timeout=0.2):
        raise ValueError("Focused descendant retained output pipe.")
    if capture.reader_failed.is_set():
        raise ValueError("Focused command output reader failed.")
    if capture.overflow.is_set():
        raise ValueError("Focused command output exceeded limit.")
    watched_file_error = _watched_file_error(watched_file, watched_file_limit)
    if watched_file_error is not None:
        raise ValueError(watched_file_error)

    stdout, stderr = capture.decode()
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    returncode = process.returncode
    if returncode != 0 and not (allow_usage_error and returncode == 4):
        raise ValueError(failure_message)
    return result


def _terminate_owned_process(
    process: subprocess.Popen[bytes], job: _WindowsJob | None
) -> BaseException | None:
    try:
        if job is None and _IS_WINDOWS:
            _terminate_process_tree(process)
        else:
            process_module.OwnedProcess(process, windows=_IS_WINDOWS, job=job).terminate(
                grace_seconds=0, immediate=True
            )
    except Exception as error:
        return error
    return None


def _spawn_process(
    command: list[str], repo_root: Path, env: dict[str, str] | None
) -> tuple[subprocess.Popen[bytes], _WindowsJob | None]:
    owned = process_module.start_process(
        command,
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        windows=_IS_WINDOWS,
        windows_job_factory=_WindowsJob,
        windows_gate_code=_WINDOWS_GATE_CODE if _IS_WINDOWS else None,
    )
    if owned.job is not None:
        owned.process.__dict__["_focused_windows_job"] = owned.job
    return owned.process, owned.job


def _watched_file_error(path: Path | None, limit: int) -> str | None:
    if path is None:
        return None
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return None
    except OSError as error:
        return f"Watched qualification report could not be inspected ({type(error).__name__})."
    if size > limit:
        return "JUnit report exceeded limit."
    return None


class _BoundedCapture:
    def __init__(self) -> None:
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.overflow = threading.Event()
        self.reader_failed = threading.Event()
        self._lock = threading.Lock()
        self._retained = 0

    def retain(self, stream_name: str, chunk: bytes) -> None:
        with self._lock:
            remaining = MAX_CAPTURE_BYTES - self._retained
            retained = min(len(chunk), remaining)
            if retained:
                target = self.stdout if stream_name == "stdout" else self.stderr
                target.extend(chunk[:retained])
                self._retained += retained
            if retained < len(chunk):
                self.overflow.set()

    def decode(self) -> tuple[str, str]:
        with self._lock:
            return (
                self.stdout.decode("utf-8", errors="replace"),
                self.stderr.decode("utf-8", errors="replace"),
            )


def _drain_pipe(stream: IO[bytes], capture: _BoundedCapture, stream_name: str) -> None:
    try:
        while chunk := os.read(stream.fileno(), 8192):
            capture.retain(stream_name, chunk)
    except Exception:
        capture.reader_failed.set()


def _join_readers(readers: tuple[threading.Thread, ...], *, timeout: float) -> bool:
    for reader in readers:
        reader.join(timeout=timeout)
    return not any(reader.is_alive() for reader in readers)


def _terminate_and_join(
    process: subprocess.Popen[bytes],
    readers: tuple[threading.Thread, ...],
    message: str,
) -> None:
    try:
        _terminate_process_tree(process)
    except (OSError, subprocess.TimeoutExpired, TimeoutError, ValueError) as error:
        _join_readers(readers, timeout=0.2)
        raise ValueError("Timed-out focused process-tree cleanup failed.") from error
    if not _join_readers(readers, timeout=_TERMINATION_WAIT_SECONDS):
        raise ValueError("Focused output readers did not stop after tree termination.")
    raise ValueError(message)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    owned = process_module.OwnedProcess(
        process,
        windows=_IS_WINDOWS,
        job=getattr(process, "_focused_windows_job", None),
    )
    owned.terminate(grace_seconds=0, immediate=True)


def _terminate_windows_process_tree(process: subprocess.Popen[bytes]) -> None:
    job = getattr(process, "_focused_windows_job", None)
    if not isinstance(job, _WindowsJob):
        raise ValueError("Windows qualification Job Object was unavailable.")
    try:
        process_module.OwnedProcess(process, windows=True, job=job).terminate(
            grace_seconds=0, immediate=True
        )
    finally:
        job.close()


def _read_counts(report_path: Path) -> FocusedCounts:
    try:
        with report_path.open("rb") as report_file:
            value = report_file.read(MAX_CAPTURE_BYTES + 1)
    except OSError as error:
        raise ValueError("Focused test result report was missing or malformed.") from error
    if len(value) > MAX_CAPTURE_BYTES:
        raise ValueError("Focused test result report exceeded limit.")
    try:
        root = ET.fromstring(value)
    except ET.ParseError as error:
        raise ValueError("Focused test result report was missing or malformed.") from error

    passed = 0
    failed = 0
    skipped = 0
    for case in root.iter("testcase"):
        if any(case.find(tag) is not None for tag in ("failure", "error")):
            failed += 1
        elif case.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1
    return FocusedCounts(passed=passed, failed=failed, skipped=skipped)


def pytest_collection_finish(session: Session) -> None:
    """Reject any runtime collection that differs from the reviewed list."""
    if os.environ.get(_PLUGIN_ACTIVE_ENV) != "1":
        return
    expected = _expected_plugin_nodes()
    actual = tuple(item.nodeid for item in session.items)
    if actual != expected:
        pytest.exit("Focused test collection did not match selection.", returncode=4)


def pytest_runtest_logreport(report: TestReport) -> None:
    """Convert every skip, xfail, or xpass into a failed test report."""
    if os.environ.get(_PLUGIN_ACTIVE_ENV) != "1":
        return
    if report.skipped or hasattr(report, "wasxfail"):
        report.outcome = "failed"
        report.longrepr = "Unexpected skip or xfail in focused qualification."


def _expected_plugin_nodes() -> tuple[str, ...]:
    try:
        value = json.loads(os.environ[_PLUGIN_ENV])
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError("Focused plugin selection was missing or malformed.") from error
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("Focused plugin selection was malformed.")
    return tuple(value)
