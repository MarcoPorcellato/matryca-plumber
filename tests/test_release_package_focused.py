from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

import pytest
from scripts import qualify_release_package as release_cli
from scripts.release_qualification import focused, process

LINUX_MACOS_NODES = (
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

WINDOWS_NODES = (
    "tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker",
    "tests/test_bounded_page_parse.py::test_timeout_then_healthy_parse_gets_new_pid",
    "tests/test_bounded_page_parse.py::test_no_stale_result_after_timeout",
    "tests/test_bounded_page_parse.py::test_worker_survives_success_and_shuts_clean",
)


def test_cli_run_focused_emits_only_sanitized_source_bound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_commit = "a" * 40
    receipt = focused.FocusedReceipt(
        source_commit=source_commit,
        platform="macos",
        selected=17,
        selected_nodes=LINUX_MACOS_NODES,
        passed=17,
        failed=0,
        skipped=0,
    )
    calls: list[tuple[Path, str, str]] = []

    def _run(repo_root: Path, platform: str, expected_commit: str) -> focused.FocusedReceipt:
        calls.append((repo_root, platform, expected_commit))
        return receipt

    monkeypatch.setattr(release_cli, "run_focused", _run)

    assert (
        release_cli.main(
            [
                "run-focused",
                "--repo-root",
                str(tmp_path),
                "--platform",
                "macos",
                "--source-commit",
                source_commit,
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert calls == [(tmp_path, "macos", source_commit)]
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "failed": 0,
        "passed": 17,
        "platform": "macos",
        "selected": 17,
        "selected_nodes": list(LINUX_MACOS_NODES),
        "skipped": 0,
        "source_commit": source_commit,
    }
    assert str(tmp_path) not in captured.out


def test_cli_run_focused_requires_platform_and_source_commit() -> None:
    with pytest.raises(SystemExit, match="2"):
        release_cli.main(["run-focused", "--platform", "linux"])


def test_cli_run_focused_rejects_malformed_source_before_pytest(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="2"):
        release_cli.main(
            [
                "run-focused",
                "--repo-root",
                str(tmp_path),
                "--platform",
                "linux",
                "--source-commit",
                "not-a-full-git-id",
            ]
        )


def test_focused_nodes_freeze_exact_platform_selections() -> None:
    assert focused.focused_nodes("linux") == LINUX_MACOS_NODES
    assert focused.focused_nodes("macos") == LINUX_MACOS_NODES
    assert focused.focused_nodes("windows") == WINDOWS_NODES


def test_windows_selection_checks_timeout_recovery_without_unix_sigkill() -> None:
    nodes = focused.focused_nodes("windows")
    assert nodes[:2] == (
        "tests/test_bounded_page_parse.py::test_controlled_hanging_child_times_out_and_kills_worker",
        "tests/test_bounded_page_parse.py::test_timeout_then_healthy_parse_gets_new_pid",
    )
    assert "tests/test_bounded_page_parse.py::test_worker_crash_recovers_bounded" not in nodes
    assert "tests/test_bounded_page_parse.py::test_worker_survives_success_and_shuts_clean" in nodes


def test_focused_runner_uses_shared_windows_gate() -> None:
    assert focused._WINDOWS_GATE_CODE == process.WINDOWS_GATE_CODE


def test_unknown_platform_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported focused-test platform"):
        focused.focused_nodes("freebsd")  # type: ignore[arg-type]


def test_run_rejects_source_sha_mismatch_without_running_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(focused, "_resolve_source_commit", lambda _root: "a" * 40)
    monkeypatch.setattr(
        focused,
        "_run_pytest",
        lambda *_args, **_kwargs: pytest.fail("pytest must not run for a mismatched source"),
    )

    with pytest.raises(ValueError, match="Source commit does not match requested SHA"):
        focused.run_focused(tmp_path, "linux", "b" * 40)


def _initialize_git_repo(repo_root: Path) -> str:
    (repo_root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_root, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=repo_root, check=True
    )
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo_root, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()


def test_run_rejects_foreign_repository_root_before_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_commit = _initialize_git_repo(tmp_path)
    monkeypatch.setattr(
        focused,
        "_run_pytest",
        lambda *_args, **_kwargs: pytest.fail("pytest must not run for a foreign repository"),
    )

    with pytest.raises(ValueError, match="Repository root does not match qualification source"):
        focused.run_focused(tmp_path, "linux", source_commit)


@pytest.mark.parametrize("dirty_kind", ["tracked", "untracked"])
def test_run_rejects_dirty_source_before_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dirty_kind: str
) -> None:
    source_commit = _initialize_git_repo(tmp_path)
    monkeypatch.setattr(focused, "_PLUGIN_REPO_ROOT", tmp_path.resolve())
    if dirty_kind == "tracked":
        (tmp_path / "tracked.txt").write_text("changed\n", encoding="utf-8")
    else:
        (tmp_path / "untracked.txt").write_text("uncommitted\n", encoding="utf-8")
    monkeypatch.setattr(
        focused,
        "_run_pytest",
        lambda *_args, **_kwargs: pytest.fail("pytest must not run for a dirty source"),
    )

    with pytest.raises(ValueError, match="Source checkout is not clean"):
        focused.run_focused(tmp_path, "linux", source_commit)


def test_run_rejects_source_mutation_during_execution_before_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_commit = _initialize_git_repo(tmp_path)
    monkeypatch.setattr(focused, "_PLUGIN_REPO_ROOT", tmp_path.resolve())
    plugin_repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            part for part in (str(plugin_repo_root), os.environ.get("PYTHONPATH", "")) if part
        ),
    )
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "test_sample.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "test"], cwd=tmp_path, check=True)
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    monkeypatch.setattr(focused, "focused_nodes", lambda _platform: ("test_sample.py::test_ok",))
    original_run_command = focused._run_command

    def _mutating_run_command(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = args[0]
        result = original_run_command(*args, **kwargs)  # type: ignore[arg-type]
        if isinstance(command, list) and "--junitxml" in command:
            (tmp_path / "created-during-test.txt").write_text("mutation\n", encoding="utf-8")
        return result

    monkeypatch.setattr(focused, "_run_command", _mutating_run_command)
    monkeypatch.setattr(
        focused,
        "_read_counts",
        lambda _path: pytest.fail("receipt counts must not be read for a changed source"),
    )

    with pytest.raises(ValueError, match="Source checkout is not clean"):
        focused.run_focused(tmp_path, "linux", source_commit)


def test_run_emits_sanitized_counts_bound_to_source_and_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_commit = _initialize_git_repo(tmp_path)
    monkeypatch.setattr(focused, "_PLUGIN_REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        focused,
        "_run_pytest",
        lambda *_args: focused.FocusedCounts(passed=17, failed=0, skipped=0),
    )

    result = focused.run_focused(tmp_path, "linux", source_commit)

    assert result.to_dict() == {
        "source_commit": source_commit,
        "platform": "linux",
        "selected": 17,
        "selected_nodes": LINUX_MACOS_NODES,
        "passed": 17,
        "failed": 0,
        "skipped": 0,
    }


def test_runner_rejects_missing_selected_node(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "def test_present():\n    assert True\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Focused test collection did not match selection"):
        focused._run_pytest(tmp_path, ("test_sample.py::test_missing",))


def test_runner_rejects_collection_error(tmp_path: Path) -> None:
    (tmp_path / "test_broken.py").write_text("def test_broken(:\n    pass\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Focused test collection"):
        focused._run_pytest(tmp_path, ("test_broken.py::test_broken",))


@pytest.mark.parametrize(
    ("body", "node"),
    [
        (
            "import pytest\n\ndef test_skip():\n    pytest.skip('not qualified')\n",
            "test_sample.py::test_skip",
        ),
        (
            "import pytest\n\n"
            "@pytest.mark.xfail(reason='not qualified')\n"
            "def test_xfail():\n    assert False\n",
            "test_sample.py::test_xfail",
        ),
        (
            "import pytest\n\n"
            "@pytest.mark.xfail(reason='not qualified')\n"
            "def test_xpass():\n    assert True\n",
            "test_sample.py::test_xpass",
        ),
    ],
)
def test_runner_rejects_skip_and_xfail_reports(tmp_path: Path, body: str, node: str) -> None:
    (tmp_path / "test_sample.py").write_text(body, encoding="utf-8")

    with pytest.raises(ValueError, match="Focused tests"):
        focused._run_pytest(tmp_path, (node,))


def test_runner_returns_pass_counts_for_exact_collected_nodes(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "def test_first():\n    assert True\n\ndef test_second():\n    assert True\n",
        encoding="utf-8",
    )

    counts = focused._run_pytest(
        tmp_path,
        ("test_sample.py::test_first", "test_sample.py::test_second"),
    )

    assert counts == focused.FocusedCounts(passed=2, failed=0, skipped=0)


def test_command_timeout_kills_descendants_then_allows_healthy_command(tmp_path: Path) -> None:
    pid_path = tmp_path / "descendant.pid"
    child_code = "import time; time.sleep(30)"
    parent_code = (
        "import subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
        f"open({str(pid_path)!r}, 'w', encoding='utf-8').write(str(child.pid)); "
        "time.sleep(30)"
    )

    started = time.monotonic()
    with pytest.raises(ValueError, match="timed out"):
        focused._run_command(
            [sys.executable, "-c", parent_code],
            tmp_path,
            "Focused command failed.",
            timeout=2.0,
        )
    elapsed = time.monotonic() - started

    assert elapsed < 4.0
    descendant_pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    if sys.platform == "win32":
        while time.monotonic() < deadline:
            listing = subprocess.check_output(
                ["tasklist.exe", "/FI", f"PID eq {descendant_pid}", "/FO", "CSV", "/NH"],
                text=True,
            )
            if str(descendant_pid) not in listing:
                break
            time.sleep(0.05)
        assert str(descendant_pid) not in listing
    else:
        while time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Timed-out subprocess descendant is still alive.")

    healthy = focused._run_command(
        [sys.executable, "-c", "print('healthy')"],
        tmp_path,
        "Healthy command failed.",
        timeout=3.0,
    )
    assert healthy.stdout.strip() == "healthy"


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_command_output_capture_is_bounded(tmp_path: Path, stream: str) -> None:
    write = "sys.stdout.write" if stream == "stdout" else "sys.stderr.write"
    code = f"import sys; {write}('x' * ({focused.MAX_CAPTURE_BYTES} + 1))"

    with pytest.raises(ValueError, match="output exceeded limit"):
        focused._run_command(
            [sys.executable, "-c", code],
            tmp_path,
            "Focused command failed.",
            timeout=3.0,
        )


def test_combined_stdout_and_stderr_share_one_capture_limit(tmp_path: Path) -> None:
    half = focused.MAX_CAPTURE_BYTES // 2 + 1
    code = (
        "import sys; "
        f"sys.stdout.write('o' * {half}); sys.stdout.flush(); "
        f"sys.stderr.write('e' * {half}); sys.stderr.flush()"
    )

    with pytest.raises(ValueError, match="output exceeded limit"):
        focused._run_command(
            [sys.executable, "-c", code],
            tmp_path,
            "Focused command failed.",
            timeout=3.0,
        )


def test_output_overflow_terminates_sleeping_process_quickly(tmp_path: Path) -> None:
    code = (
        "import sys, time; "
        f"sys.stdout.write('x' * ({focused.MAX_CAPTURE_BYTES} + 8192)); "
        "sys.stdout.flush(); time.sleep(30)"
    )

    started = time.monotonic()
    with pytest.raises(ValueError, match="output exceeded limit"):
        focused._run_command(
            [sys.executable, "-c", code],
            tmp_path,
            "Focused command failed.",
            timeout=1.5,
        )
    assert time.monotonic() - started < 3.0


def test_watched_junit_overflow_terminates_sleeping_process_quickly(tmp_path: Path) -> None:
    report_path = tmp_path / "pytest.xml"
    code = (
        "import pathlib, sys, time; "
        "pathlib.Path(sys.argv[1]).write_bytes(b'x' * 1025); "
        "time.sleep(30)"
    )

    started = time.monotonic()
    with pytest.raises(ValueError, match="JUnit report exceeded limit"):
        focused._run_command(
            [sys.executable, "-c", code, str(report_path)],
            tmp_path,
            "Focused command failed.",
            timeout=5.0,
            watched_file=report_path,
            watched_file_limit=1024,
        )
    assert time.monotonic() - started < 3.0
    assert report_path.stat().st_size == 1025


def test_watched_junit_overflow_is_rechecked_after_quick_exit(tmp_path: Path) -> None:
    report_path = tmp_path / "pytest.xml"
    code = "import pathlib, sys; pathlib.Path(sys.argv[1]).write_bytes(b'x' * 1025)"

    with pytest.raises(ValueError, match="JUnit report exceeded limit"):
        focused._run_command(
            [sys.executable, "-c", code, str(report_path)],
            tmp_path,
            "Focused command failed.",
            timeout=3.0,
            watched_file=report_path,
            watched_file_limit=1024,
        )


def test_post_exit_junit_error_terminates_closed_stdio_descendant_and_closes_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = tmp_path / "pytest.xml"
    pid_path = tmp_path / "descendant.pid"
    child_code = (
        "import os, sys, time; "
        "open(sys.argv[1], 'w', encoding='utf-8').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    parent_code = (
        "import pathlib, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, {str(pid_path)!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "deadline=time.monotonic()+3\n"
        f"pid_file=pathlib.Path({str(pid_path)!r})\n"
        "while not pid_file.exists() and time.monotonic() < deadline:\n"
        "    time.sleep(0.01)\n"
        f"pathlib.Path({str(report_path)!r}).write_bytes(b'x'*1025)\n"
    )

    class _FakeJob:
        def __init__(self, process_group: int) -> None:
            self.process_group = process_group
            self.terminated = False
            self.closed = False

        def terminate(self) -> None:
            with suppress(ProcessLookupError):
                os.killpg(self.process_group, 9)
            self.terminated = True

        def active_processes(self) -> int:
            return 0 if self.terminated else 1

        def require_empty(self) -> None:
            if self.active_processes():
                self.terminate()
                raise ValueError("job was not empty")

        def close(self) -> None:
            self.closed = True

    process_holder: list[subprocess.Popen[bytes]] = []
    job_holder: list[_FakeJob] = []

    def _spawn(
        command: list[str], cwd: Path, env: dict[str, str] | None
    ) -> tuple[subprocess.Popen[bytes], _FakeJob]:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        job = _FakeJob(process.pid)
        process.__dict__["_focused_windows_job"] = job
        process_holder.append(process)
        job_holder.append(job)
        return process, job

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", _FakeJob)
    monkeypatch.setattr(focused, "_spawn_process", _spawn)

    try:
        with pytest.raises(ValueError, match="JUnit report exceeded limit"):
            focused._run_command(
                [sys.executable, "-c", parent_code],
                tmp_path,
                "Focused command failed.",
                timeout=5.0,
                watched_file=report_path,
                watched_file_limit=1024,
            )
        assert job_holder[0].terminated is True
        assert job_holder[0].closed is True
        _assert_process_stopped(int(pid_path.read_text(encoding="utf-8")))
    finally:
        if pid_path.exists():
            _kill_test_process(int(pid_path.read_text(encoding="utf-8")))


def test_parent_exit_with_descendant_holding_pipe_fails_quickly(tmp_path: Path) -> None:
    pid_path = tmp_path / "pipe-holder.pid"
    child_code = (
        "import os, sys, time; "
        "open(sys.argv[1], 'w', encoding='utf-8').write(str(os.getpid())); "
        "time.sleep(30)"
    )
    parent_code = (
        "import subprocess, sys; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, {str(pid_path)!r}])"
    )

    started = time.monotonic()
    try:
        with pytest.raises(ValueError, match="retained output pipe"):
            focused._run_command(
                [sys.executable, "-c", parent_code],
                tmp_path,
                "Focused command failed.",
                timeout=3.0,
            )
        assert time.monotonic() - started < 3.0
        _assert_process_stopped(int(pid_path.read_text(encoding="utf-8")))
    finally:
        if pid_path.exists():
            _kill_test_process(int(pid_path.read_text(encoding="utf-8")))


def test_normal_command_captures_both_streams(tmp_path: Path) -> None:
    result = focused._run_command(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        tmp_path,
        "Focused command failed.",
        timeout=3.0,
    )

    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_pipe_reader_error_terminates_child_and_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail_reader(_stream: object, capture: focused._BoundedCapture, _stream_name: str) -> None:
        capture.reader_failed.set()

    monkeypatch.setattr(focused, "_drain_pipe", _fail_reader)

    with pytest.raises(ValueError, match="output reader failed"):
        focused._run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            tmp_path,
            "Focused command failed.",
            timeout=3.0,
        )


def test_reader_start_failure_terminates_process_and_closes_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeJob:
        def __init__(self, process_group: int) -> None:
            self.process_group = process_group
            self.terminated = False
            self.closed = False

        def terminate(self) -> None:
            with suppress(ProcessLookupError):
                os.killpg(self.process_group, 9)
            self.terminated = True

        def active_processes(self) -> int:
            return 0 if self.terminated else 1

        def require_empty(self) -> None:
            if self.active_processes():
                raise ValueError("job was not empty")

        def close(self) -> None:
            self.closed = True

    process_holder: list[subprocess.Popen[bytes]] = []
    job_holder: list[_FakeJob] = []

    def _spawn(
        command: list[str], cwd: Path, env: dict[str, str] | None
    ) -> tuple[subprocess.Popen[bytes], _FakeJob]:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        job = _FakeJob(process.pid)
        process.__dict__["_focused_windows_job"] = job
        process_holder.append(process)
        job_holder.append(job)
        return process, job

    original_start = threading.Thread.start
    starts = 0

    def _fail_second_start(thread: threading.Thread) -> None:
        nonlocal starts
        starts += 1
        if starts == 2:
            raise RuntimeError("simulated reader startup failure")
        original_start(thread)

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", _FakeJob)
    monkeypatch.setattr(focused, "_spawn_process", _spawn)
    monkeypatch.setattr(threading.Thread, "start", _fail_second_start)

    with pytest.raises(RuntimeError, match="reader startup failure"):
        focused._run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            tmp_path,
            "Focused command failed.",
            timeout=5.0,
        )

    assert job_holder[0].terminated is True
    assert job_holder[0].closed is True
    assert process_holder[0].poll() is not None


def test_job_close_failure_prevents_successful_command_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process_holder: list[subprocess.Popen[bytes]] = []

    class _CloseFailureJob:
        def require_empty(self) -> None:
            return None

        def close(self) -> None:
            raise OSError("simulated handle close failure")

    job = _CloseFailureJob()

    def _spawn(
        command: list[str], cwd: Path, env: dict[str, str] | None
    ) -> tuple[subprocess.Popen[bytes], _CloseFailureJob]:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        process.__dict__["_focused_windows_job"] = job
        process_holder.append(process)
        return process, job

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", _CloseFailureJob)
    monkeypatch.setattr(focused, "_spawn_process", _spawn)

    with pytest.raises(ValueError, match="Could not close Windows qualification Job Object"):
        focused._run_command(
            [sys.executable, "-c", "print('healthy')"],
            tmp_path,
            "Focused command failed.",
            timeout=3.0,
        )
    assert process_holder[0].returncode == 0


def test_windows_job_creation_failure_does_not_launch_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launches: list[bool] = []

    class _UnavailableJob:
        def __init__(self) -> None:
            raise ValueError("Windows Job Objects are unavailable.")

    def _popen(*_args: object, **_kwargs: object) -> subprocess.Popen[bytes]:
        launches.append(True)
        raise AssertionError("The command must not launch without a Job Object.")

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", _UnavailableJob)
    monkeypatch.setattr(subprocess, "Popen", _popen)

    with pytest.raises(ValueError, match="Job Objects are unavailable"):
        focused._spawn_process(["pytest"], tmp_path, None)
    assert launches == []


def test_windows_job_assignment_failure_does_not_release_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _AssignmentFailureJob:
        def __init__(self) -> None:
            self.closed = False

        def assign(self, _handle: int) -> None:
            raise OSError("assignment rejected")

        def terminate(self) -> None:
            raise RuntimeError("simulated Job Object termination failure")

        def close(self) -> None:
            self.closed = True

    class _Process:
        class _Pipe:
            def __init__(self) -> None:
                self.payload = bytearray()
                self.closed = False

            def write(self, payload: bytes) -> int:
                self.payload.extend(payload)
                return len(payload)

            def close(self) -> None:
                self.closed = True

        stdin = _Pipe()
        stdout = None
        stderr = None

        class _Handle:
            def Close(self) -> None:
                pass

        _handle = _Handle()
        kill_attempted = False
        wait_attempted = False

        def kill(self) -> None:
            self.kill_attempted = True
            raise RuntimeError("simulated gate kill failure")

        def wait(self, timeout: float | None = None) -> int:
            self.wait_attempted = True
            raise subprocess.TimeoutExpired("gate", timeout or 1.0)

    process = _Process()
    job = _AssignmentFailureJob()
    captured: list[list[str]] = []

    def _popen(command: list[str], **_kwargs: object) -> _Process:
        captured.append(command)
        return process

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", lambda: job)
    monkeypatch.setattr(subprocess, "Popen", _popen)

    with pytest.raises(OSError, match="assignment rejected") as failure:
        focused._spawn_process(["pytest", "-q"], tmp_path, None)

    assert captured[0][:5] == [
        sys.executable,
        "-I",
        "-S",
        "-c",
        focused._WINDOWS_GATE_CODE,
    ]
    assert process.stdin.payload == b""
    assert process.stdin.closed is True
    assert process.kill_attempted is True
    assert process.wait_attempted is True
    assert job.closed is True
    assert len(failure.value.__notes__) == 3


def test_windows_tree_cleanup_uses_owned_job_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Process:
        pid = 417
        waited = False
        _focused_windows_job: object

        def wait(self, timeout: float | None = None) -> int:
            self.waited = True
            return 0

    class _Job:
        closed = False

        def terminate(self) -> None:
            return None

        def active_processes(self) -> int:
            return 0

        def close(self) -> None:
            self.closed = True

    process = _Process()
    job = _Job()
    process._focused_windows_job = job

    monkeypatch.setattr(focused, "_IS_WINDOWS", True)
    monkeypatch.setattr(focused, "_WindowsJob", _Job)

    focused._terminate_windows_process_tree(process)  # type: ignore[arg-type]

    assert process.waited is True
    assert job.closed is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object integration proof")
def test_windows_job_kills_descendant_that_closed_stdio(tmp_path: Path) -> None:
    pid_path = tmp_path / "stdio-closed-child.pid"
    child_code = "import time; time.sleep(30)"
    parent_code = (
        "import os, subprocess, sys, time\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}], "
        "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"open({str(pid_path)!r}, 'w', encoding='utf-8').write(str(child.pid))\n"
        "deadline = time.monotonic() + 2.0\n"
        f"while not os.path.exists({str(pid_path)!r}):\n"
        "    if time.monotonic() >= deadline:\n"
        "        sys.exit(126)\n"
        "    time.sleep(0.01)\n"
    )

    started = time.monotonic()
    descendant_pid: int | None = None
    try:
        with pytest.raises(ValueError, match="Job Object retained active processes"):
            focused._run_command(
                [sys.executable, "-c", parent_code],
                tmp_path,
                "Focused command failed.",
                timeout=3.0,
            )
        assert time.monotonic() - started < 3.0
        descendant_pid = int(pid_path.read_text(encoding="utf-8"))
        _assert_process_stopped(descendant_pid)
    finally:
        if descendant_pid is None and pid_path.is_file():
            descendant_pid = int(pid_path.read_text(encoding="utf-8"))
        if descendant_pid is not None:
            _kill_test_process(descendant_pid)
            _assert_process_stopped(descendant_pid)


def _assert_process_stopped(pid: int) -> None:
    deadline = time.monotonic() + 2.0
    if sys.platform == "win32":
        while time.monotonic() < deadline:
            listing = subprocess.check_output(
                ["tasklist.exe", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
            )
            if str(pid) not in listing:
                return
            time.sleep(0.05)
        pytest.fail("Timed-out subprocess descendant is still alive.")
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    pytest.fail("Timed-out subprocess descendant is still alive.")


def _kill_test_process(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5.0,
        )
    else:
        with suppress(ProcessLookupError):
            os.kill(pid, 9)
