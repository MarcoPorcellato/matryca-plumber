"""Owned source-only children; these are not installed producer qualification."""

from __future__ import annotations

import selectors
import subprocess
import sys
import time
from io import BufferedReader
from pathlib import Path
from types import SimpleNamespace
from typing import IO, cast
from unittest.mock import Mock

import pytest
from matryca_plumber.graph_gateway.bootstrap import (
    DENIED_EVENTS,
    GatewayError,
    _admit_dependencies,
    _admit_platform,
    _parse_arguments,
)

# Independent T1 oracle: never derive this tuple from the implementation.
EXPECTED_AUDIT_EVENTS = (
    "subprocess.Popen",
    "os.fork",
    "os.forkpty",
    "os.posix_spawn",
    "os.spawn",
    "os.exec",
    "os.system",
    "socket.__new__",
    "socket.connect",
    "socket.bind",
    "socket.sendto",
    "socket.sendmsg",
    "socket.getaddrinfo",
)


def _source_child(code: str) -> tuple[int, bytes, bytes]:
    """Capture finite output and finalize this helper's direct child on every outcome."""
    root = Path(__file__).resolve().parents[1]
    preamble = f"""
import importlib.machinery, pathlib, sys
root = pathlib.Path({str(root)!r})
assert sys.flags.isolated == 1 and sys.dont_write_bytecode
for name, search, file in (
    ('matryca_plumber', root, root / 'matryca_plumber/__init__.py'),
    ('matryca_plumber.graph_gateway', root / 'matryca_plumber',
     root / 'matryca_plumber/graph_gateway/__init__.py'),
):
    spec = importlib.machinery.PathFinder.find_spec(name, [str(search)])
    assert spec is not None and pathlib.Path(spec.origin).resolve() == file
sys.path.insert(0, str(root))
import matryca_plumber, matryca_plumber.graph_gateway
for module, file in (
    (matryca_plumber, root / 'matryca_plumber/__init__.py'),
    (matryca_plumber.graph_gateway, root / 'matryca_plumber/graph_gateway/__init__.py'),
):
    assert pathlib.Path(module.__file__).resolve() == file
    assert pathlib.Path(module.__spec__.origin).resolve() == file
"""
    process = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", preamble + code],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    selection: selectors.BaseSelector | None = None
    primary: BaseException | None = None
    captured: tuple[int, bytes, bytes] | None = None
    cleanup_errors: list[tuple[str, BaseException]] = []
    try:
        assert process.stdout is not None and process.stderr is not None
        streams: dict[IO[bytes], bytearray] = {
            process.stdout: bytearray(),
            process.stderr: bytearray(),
        }
        deadline = time.monotonic() + 10.0
        selection = selectors.DefaultSelector()
        for stream in streams:
            selection.register(stream, selectors.EVENT_READ)
        while selection.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                raise RuntimeError("nested diagnostic deadline exceeded")
            for key, _ in selection.select(0.05):
                stream = cast(BufferedReader, key.fileobj)
                chunk = stream.read1(4096)
                if not chunk:
                    selection.unregister(stream)
                elif len(streams[stream]) + len(chunk) > 65_536:
                    raise RuntimeError("nested diagnostic output limit exceeded")
                else:
                    streams[stream].extend(chunk)
        result = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        captured = result, bytes(streams[process.stdout]), bytes(streams[process.stderr])
    except BaseException as error:
        primary = error
    finally:
        # A direct child only: never signal the caller's process group.
        cleanup_deadline: float | None = None
        try:
            cleanup_deadline = time.monotonic() + 3.0
        except BaseException as error:
            cleanup_errors.append(("cleanup_clock", error))

        def remaining() -> float:
            if cleanup_deadline is None:
                return 0.0
            return max(0.0, cleanup_deadline - time.monotonic())

        running = True
        try:
            running = process.poll() is None
        except BaseException as error:
            cleanup_errors.append(("poll_before_terminate", error))
        if running:
            try:
                process.terminate()
            except BaseException as error:
                cleanup_errors.append(("terminate", error))
            else:
                try:
                    process.wait(timeout=min(0.25, remaining()))
                except subprocess.TimeoutExpired:
                    pass  # Escalate to kill within the same cleanup budget.
                except BaseException as error:
                    cleanup_errors.append(("terminate_wait", error))
            running = True
            try:
                running = process.poll() is None
            except BaseException as error:
                cleanup_errors.append(("poll_before_kill", error))
            if running:
                try:
                    process.kill()
                except BaseException as error:
                    cleanup_errors.append(("kill", error))
        # Reaping remains mandatory even if terminate, kill or a prior wait failed.
        try:
            process.wait(timeout=remaining())
        except BaseException as error:
            cleanup_errors.append(("reap", error))
        try:
            if process.poll() is None:
                raise RuntimeError("owned direct child remains running")
        except BaseException as error:
            cleanup_errors.append(("final_child_check", error))
        if selection is not None:
            try:
                selection.close()
            except BaseException as error:
                cleanup_errors.append(("selector_close", error))
        for label, stream in (("stdout_close", process.stdout), ("stderr_close", process.stderr)):
            if stream is not None:
                try:
                    stream.close()
                except BaseException as error:
                    cleanup_errors.append((label, error))
        try:
            if cleanup_deadline is None or time.monotonic() > cleanup_deadline:
                raise RuntimeError("nested diagnostic cleanup budget exceeded")
        except BaseException as error:
            cleanup_errors.append(("cleanup_budget", error))
    cleanup = (
        BaseExceptionGroup(
            "nested diagnostic cleanup failed: " + ", ".join(label for label, _ in cleanup_errors),
            [error for _, error in cleanup_errors],
        )
        if cleanup_errors
        else None
    )
    if primary is not None:
        if cleanup is not None:
            raise primary from cleanup
        raise primary
    if cleanup is not None:
        raise RuntimeError("nested diagnostic cleanup uncertain") from cleanup
    assert captured is not None
    return captured


def test_gateway_parent_packages_and_bootstrap_are_inert() -> None:
    result, output, errors = _source_child(
        """
import json
from matryca_plumber.graph_gateway import bootstrap
assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
assert 'logseq_matryca_parser' not in sys.modules
assert 'pydantic' not in sys.modules and 'loguru' not in sys.modules
print(json.dumps({'inert': True}))
"""
    )
    assert (result, output, errors) == (0, b'{"inert": true}\n', b"")


def test_gateway_rejects_every_declared_audit_event_in_owned_child() -> None:
    assert DENIED_EVENTS == EXPECTED_AUDIT_EVENTS
    result, output, errors = _source_child(
        f"""
import json
from matryca_plumber.graph_gateway.bootstrap import _install_audit_hook
expected_events = {EXPECTED_AUDIT_EVENTS!r}
installed = _install_audit_hook()
denied = []
for event in expected_events:
    try:
        sys.audit(event)
    except PermissionError:
        denied.append(event)
print(json.dumps({{'installed': installed, 'denied': len(denied), 'total': len(expected_events)}}))
"""
    )
    assert result == 0 and errors == b"", "child setup or lifecycle failed"
    assert output == b'{"installed": true, "denied": 13, "total": 13}\n'


def test_gateway_silent_hook_refusal_stops_before_application_imports() -> None:
    result, output, errors = _source_child(
        """
sys.addaudithook = lambda hook: None
from matryca_plumber.graph_gateway.bootstrap import main
result = main(['snapshot', '--graph-root', 'PRIVATE-CANARY',
               '--expect-descriptor-sha256', 'a' * 64])
assert 'src' not in sys.modules and 'logseq_matryca_parser' not in sys.modules
raise SystemExit(result)
"""
    )
    assert result == 9, "silent audit registration refusal must reject before admission"
    assert output == b"" and errors == b'{"error":"audit_hook_unavailable"}\n'


@pytest.fixture
def owned_child_controls(monkeypatch: pytest.MonkeyPatch) -> tuple[Mock, Mock, Mock]:
    """Replace only this test module's subprocess, selector and clock references."""
    process = Mock()
    process.stdout = Mock(spec=BufferedReader)
    process.stderr = Mock(spec=BufferedReader)
    process.stdout.closed = process.stderr.closed = False
    process.stdout.close.side_effect = lambda: setattr(process.stdout, "closed", True)
    process.stderr.close.side_effect = lambda: setattr(process.stderr, "closed", True)
    process.poll.return_value = None

    def reap(*, timeout: float) -> int:
        assert 0 <= timeout <= 10.0
        process.poll.return_value = 0
        return 0

    process.wait.side_effect = reap
    selection = Mock(spec=selectors.BaseSelector)
    selection.get_map.return_value = {1: object()}
    selection.select.return_value = [(SimpleNamespace(fileobj=process.stdout), 1)]
    selection.closed = False
    selection.close.side_effect = lambda: setattr(selection, "closed", True)
    clock = Mock(return_value=0.0)
    module = sys.modules[__name__]
    monkeypatch.setattr(
        module,
        "subprocess",
        SimpleNamespace(
            Popen=Mock(return_value=process),
            DEVNULL=subprocess.DEVNULL,
            PIPE=subprocess.PIPE,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )
    monkeypatch.setattr(
        module,
        "selectors",
        SimpleNamespace(DefaultSelector=Mock(return_value=selection), EVENT_READ=selectors.EVENT_READ),
    )
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=clock))
    return process, selection, clock


@pytest.mark.parametrize(
    "failure", ["deadline", "stdout", "stderr", "read", "selector", "interruption"]
)
def test_source_child_failure_finalizes_owned_child(
    owned_child_controls: tuple[Mock, Mock, Mock], failure: str
) -> None:
    process, selection, clock = owned_child_controls
    primary: BaseException | None = None
    if failure == "deadline":
        clock.side_effect = lambda: 0.0 if clock.call_count == 1 else 11.0
        expected: type[BaseException] = RuntimeError
        message = "nested diagnostic deadline exceeded"
    elif failure in {"stdout", "stderr"}:
        stream = process.stdout if failure == "stdout" else process.stderr
        selection.select.return_value = [(SimpleNamespace(fileobj=stream), 1)]
        stream.read1.side_effect = [b"x" * 4096] * 17
        expected = RuntimeError
        message = "nested diagnostic output limit exceeded"
    else:
        if failure == "read":
            primary = OSError("synthetic read failure")
            process.stdout.read1.side_effect = primary
        elif failure == "selector":
            primary = ValueError("synthetic selector failure")
            selection.select.side_effect = primary
        else:
            primary = KeyboardInterrupt("synthetic interruption")
            selection.select.side_effect = primary
        expected, message = type(primary), str(primary)
    with pytest.raises(expected, match=message) as caught:
        _source_child("pass")
    if primary is not None:
        assert caught.value is primary
    process.terminate.assert_called_once()
    assert process.wait.call_count >= 1
    assert process.poll() == 0, "the owned child must be reaped before returning the primary error"
    assert process.stdout.closed is True and process.stderr.closed is True
    assert selection.closed is True


def test_source_child_kills_after_bounded_terminate_wait(
    owned_child_controls: tuple[Mock, Mock, Mock],
) -> None:
    process, selection, _ = owned_child_controls
    primary = OSError("synthetic read failure")
    process.stdout.read1.side_effect = primary
    original_reap = process.wait.side_effect
    calls = 0

    def delayed_reap(*, timeout: float) -> int:
        nonlocal calls
        calls += 1
        assert 0 <= timeout <= 3.0
        if calls == 1:
            raise subprocess.TimeoutExpired("owned-child", timeout)
        return cast(int, original_reap(timeout=timeout))

    process.wait.side_effect = delayed_reap
    with pytest.raises(OSError) as caught:
        _source_child("pass")
    assert caught.value is primary
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.poll() == 0
    assert process.stdout.closed is True and process.stderr.closed is True
    assert selection.closed is True


def test_source_child_preserves_primary_when_cleanup_steps_fail(
    owned_child_controls: tuple[Mock, Mock, Mock],
) -> None:
    process, selection, _ = owned_child_controls
    primary = OSError("synthetic read failure")
    process.stdout.read1.side_effect = primary
    process.terminate.side_effect = KeyboardInterrupt("synthetic terminate interruption")
    selection.close.side_effect = ValueError("synthetic selector close failure")
    process.stdout.close.side_effect = SystemExit("synthetic pipe close interruption")
    with pytest.raises(OSError) as caught:
        _source_child("pass")
    assert caught.value is primary
    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    assert "terminate" in str(caught.value.__cause__)
    assert "selector_close" in str(caught.value.__cause__)
    assert "stdout_close" in str(caught.value.__cause__)
    process.kill.assert_called_once()
    assert process.poll() == 0
    selection.close.assert_called_once()
    process.stdout.close.assert_called_once()
    assert process.stderr.closed is True, "one pipe's BaseException must not skip the other close"


def test_source_child_reports_cleanup_only_failure(
    owned_child_controls: tuple[Mock, Mock, Mock],
) -> None:
    process, selection, _ = owned_child_controls
    selection.get_map.return_value = {}
    process.poll.return_value = 0
    selection.close.side_effect = OSError("synthetic selector close failure")
    with pytest.raises(RuntimeError, match="nested diagnostic cleanup uncertain") as caught:
        _source_child("pass")
    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    assert "selector_close" in str(caught.value.__cause__)
    assert process.poll() == 0
    assert process.stdout.closed is True and process.stderr.closed is True
    process.terminate.assert_not_called()
    process.kill.assert_not_called()


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["unknown"],
        ["describe", "--graph-root", "private"],
        ["snapshot"],
        ["snapshot", "--graph-root", "private"],
        ["snapshot", "--graph-root", "private", "--expect-descriptor-sha256", "wrong"],
        ["snapshot", "--graph-root", "a", "--graph-root", "b"],
        ["snapshot", "--graph-root", "a\x00b", "--expect-descriptor-sha256", "a" * 64],
    ],
)
def test_gateway_rejects_invalid_or_implicit_arguments(arguments: list[str]) -> None:
    with pytest.raises(GatewayError, match="usage"):
        _parse_arguments(arguments)


def test_gateway_accepts_only_explicit_snapshot_and_describe() -> None:
    assert _parse_arguments(["describe"]) == ("describe", None, None)
    assert _parse_arguments(
        ["snapshot", "--expect-descriptor-sha256", "a" * 64, "--graph-root", "/synthetic/graph"]
    ) == ("snapshot", "/synthetic/graph", "a" * 64)


@pytest.mark.parametrize(
    ("system", "machine", "python"),
    [
        ("Windows", "AMD64", (3, 12)),
        ("Linux", "aarch64", (3, 12)),
        ("Darwin", "x86_64", (3, 12)),
        ("Linux", "x86_64", (3, 14)),
    ],
)
def test_gateway_rejects_unplanned_platforms(
    system: str, machine: str, python: tuple[int, int]
) -> None:
    with pytest.raises(GatewayError, match="unsupported_platform"):
        _admit_platform(system, machine, python)


@pytest.mark.parametrize("parser", ["1.10.0", "1.11.0", "", "1.9.0+unknown"])
def test_gateway_rejects_unqualified_dependency_metadata(parser: str) -> None:
    with pytest.raises(GatewayError, match="unsupported_dependency"):
        _admit_dependencies("2.0.1rc4", parser)


def test_gateway_nonce_mismatch_rejects_before_internal_imports() -> None:
    result, output, errors = _source_child(
        """
original_audit = sys.audit
def changed_nonce(event, *arguments):
    return original_audit(event, object())
sys.audit = changed_nonce
from matryca_plumber.graph_gateway.bootstrap import main
result = main(['describe'])
assert 'src' not in sys.modules and 'logseq_matryca_parser' not in sys.modules
raise SystemExit(result)
"""
    )
    assert result == 9, "a different nonce cannot establish the gateway hook"
    assert output == b"" and errors == b'{"error":"audit_hook_unavailable"}\n'
