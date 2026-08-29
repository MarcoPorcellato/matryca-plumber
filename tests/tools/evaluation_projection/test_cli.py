"""Contract tests for the maintainer-only evaluation projection CLI."""

from __future__ import annotations

import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from tools.evaluation_projection.atomic_output import AtomicOutputError
from tools.evaluation_projection.privacy import ProjectionPrivacyError
from tools.evaluation_projection.projector import ProjectionEvidenceError
from tools.evaluation_projection.provenance import SourceBinding, SourceBindingError

from tools.evaluation_projection import cli

_REVISION = "a" * 40


def _binding(root: Path) -> SourceBinding:
    return SourceBinding(repository_root=root, revision=_REVISION, branch="main")


def _default_run() -> SimpleNamespace:
    return SimpleNamespace(episodes=(object(),))


def _fail_if_called() -> None:
    raise AssertionError("harness must not run after source rejection")


def _raise_dirty(*_: object) -> SourceBinding:
    raise SourceBindingError("source_tree_dirty")


def test_dirty_source_rejects_before_harness(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "resolve_source_binding", _raise_dirty)
    monkeypatch.setattr(cli, "run_default_scenarios", _fail_if_called)

    assert cli.main([], repository_root=Path.cwd()) == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: source_tree_dirty\n"


def test_stdout_success_is_canonical_and_has_no_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    marker = object()
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: marker)
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda value: b'{"suite":true}\n')

    assert cli.main([], repository_root=tmp_path) == 0

    captured = capsys.readouterr()
    assert captured.out == '{"suite":true}\n'
    assert captured.err == ""


@pytest.mark.parametrize("failure", ("write", "short_write", "flush"))
def test_stdout_output_failures_are_content_free_and_exit_six(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    failure: str,
) -> None:
    class FailingBuffer:
        def write(self, payload: bytes) -> int:
            if failure == "write":
                raise OSError("synthetic output failure: /private/example")
            if failure == "short_write":
                return len(payload) - 1
            return len(payload)

        def flush(self) -> None:
            if failure == "flush":
                raise OSError("synthetic flush failure: /private/example")

    class FailingStdout:
        buffer = FailingBuffer()

    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda _value: b"canonical\n")
    monkeypatch.setattr("tools.evaluation_projection.cli.sys.stdout", FailingStdout())

    assert cli.main([], repository_root=tmp_path) == 6

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: output_failed\n"
    assert "/private/example" not in captured.err


def test_file_success_installs_only_the_canonical_bytes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    installed: list[tuple[Path, bytes, bool]] = []
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda _value: b"canonical\n")
    monkeypatch.setattr(
        cli,
        "write_projection_bytes",
        lambda path, payload, *, overwrite: installed.append((path, payload, overwrite)),
    )
    destination = tmp_path / "suite.json"

    assert cli.main(["--output", str(destination), "--overwrite"], repository_root=tmp_path) == 0

    assert installed == [(destination, b"canonical\n", True)]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_explicit_matching_source_assertion_reaches_the_harness(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    received_assertions: list[str | None] = []

    def bind(_root: Path, assertion: str | None) -> SourceBinding:
        received_assertions.append(assertion)
        return _binding(tmp_path)

    monkeypatch.setattr(
        cli,
        "resolve_source_binding",
        bind,
    )
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda _value: b"canonical\n")

    assert cli.main(["--source-revision", _REVISION], repository_root=tmp_path) == 0

    assert received_assertions == [_REVISION]
    assert capsys.readouterr().err == ""


def test_source_mismatch_is_content_free_and_stops_before_harness(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    supplied_revision = "b" * 40

    def raise_mismatch(*_: object) -> SourceBinding:
        raise SourceBindingError("source_revision_mismatch")

    monkeypatch.setattr(cli, "resolve_source_binding", raise_mismatch)
    monkeypatch.setattr(cli, "run_default_scenarios", _fail_if_called)

    assert cli.main(["--source-revision", supplied_revision], repository_root=tmp_path) == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: source_revision_mismatch\n"
    assert supplied_revision not in captured.err


@pytest.mark.parametrize(
    "message",
    (
        "source_revision_mismatch: /private/example",
        "fatal: not a git repository: /private/example",
    ),
)
def test_unknown_or_malformed_source_binding_errors_are_content_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    message: str,
) -> None:
    def reject_source(*_: object) -> SourceBinding:
        raise SourceBindingError(message)

    monkeypatch.setattr(cli, "resolve_source_binding", reject_source)
    monkeypatch.setattr(cli, "run_default_scenarios", _fail_if_called)

    assert cli.main([], repository_root=tmp_path) == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: source_repository_unavailable\n"
    assert message not in captured.err
    assert "/private/example" not in captured.err


def test_canonicalization_rejection_has_stable_content_free_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())

    def reject_canonicalization(_: object) -> bytes:
        raise ValueError("synthetic content must not escape: /private/example")

    monkeypatch.setattr(cli, "canonical_suite_bytes", reject_canonicalization)

    assert cli.main([], repository_root=tmp_path) == 4

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: evidence_rejected\n"
    assert "synthetic content" not in captured.err
    assert "/private/example" not in captured.err


@pytest.mark.parametrize(
    "error",
    (
        ProjectionEvidenceError("synthetic evidence /private/example"),
        ProjectionPrivacyError("synthetic privacy /private/example"),
    ),
)
def test_evidence_and_privacy_rejections_are_content_free(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    error: Exception,
) -> None:
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)

    def reject_projection(*_: object, **__: object) -> object:
        raise error

    monkeypatch.setattr(cli, "project_suite", reject_projection)

    assert cli.main([], repository_root=tmp_path) == 4

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: evidence_rejected\n"
    assert "/private/example" not in captured.err
    assert "synthetic" not in captured.err


def test_invalid_arguments_are_content_free_and_keep_exit_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret = "Authorization: Bearer private-token"

    assert cli.main(["--unknown-option", secret]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: invalid_arguments\n"
    assert secret not in captured.err
    assert "usage:" not in captured.err


def test_unexpected_pre_output_failure_is_content_free_and_keeps_exit_four(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    secret = "api_key=private-token /private/example"
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))

    def fail_harness() -> SimpleNamespace:
        raise RuntimeError(secret)

    monkeypatch.setattr(cli, "run_default_scenarios", fail_harness)

    assert cli.main([], repository_root=tmp_path) == 4

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: evidence_rejected\n"
    assert secret not in captured.err
    assert "Traceback" not in captured.err


def test_existing_output_is_preserved_and_reported(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    destination = tmp_path / "suite.json"
    destination.write_bytes(b"preserve")

    assert cli.main(["--output", str(destination)], repository_root=repository) == 5

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: output_exists\n"
    assert destination.read_bytes() == b"preserve"


@pytest.mark.parametrize(
    "error, expected_code",
    (
        (AtomicOutputError("output_install_failed"), "output_install_failed"),
        (
            AtomicOutputError("output_directory_sync_failed", installed=True),
            "output_directory_sync_failed",
        ),
    ),
)
def test_output_failures_have_stable_exit_six(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    error: AtomicOutputError,
    expected_code: str,
) -> None:
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda _value: b"canonical\n")

    def reject_output(*_: object, **__: object) -> None:
        raise error

    monkeypatch.setattr(cli, "write_projection_bytes", reject_output)

    assert cli.main(["--output", str(tmp_path / "suite.json")], repository_root=tmp_path) == 6

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"evaluation_projection: {expected_code}\n"


def test_unrecognized_atomic_output_code_is_content_free(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    secret = "credential=private-token /private/example"
    monkeypatch.setattr(cli, "resolve_source_binding", lambda *_: _binding(tmp_path))
    monkeypatch.setattr(cli, "run_default_scenarios", _default_run)
    monkeypatch.setattr(cli, "project_suite", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "canonical_suite_bytes", lambda _value: b"canonical\n")

    def reject_output(*_: object, **__: object) -> None:
        raise AtomicOutputError(secret)

    monkeypatch.setattr(cli, "write_projection_bytes", reject_output)

    assert cli.main(["--output", str(tmp_path / "suite.json")], repository_root=tmp_path) == 6

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: output_failed\n"
    assert secret not in captured.err


def test_success_uses_fixed_git_harness_and_projection_without_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    repository = _repository(tmp_path)
    destination = tmp_path / "suite.json"

    def forbid_socket(*_: object, **__: object) -> socket.socket:
        raise AssertionError("network access forbidden")

    monkeypatch.setattr(socket, "socket", forbid_socket)

    assert cli.main(["--output", str(destination)], repository_root=repository) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert destination.read_bytes().endswith(b"\n")


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "Test Maintainer")
    _git(repository, "config", "user.email", "maintainer@example.invalid")
    _git(repository, "config", "commit.gpgsign", "false")
    (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repository, "add", "tracked.txt")
    _git(repository, "commit", "-m", "test: initialize repository")
    return repository


def _git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
