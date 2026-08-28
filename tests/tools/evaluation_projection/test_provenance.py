"""Contract tests for exact clean Git source provenance binding."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tools.evaluation_projection.provenance import (
    SourceBindingError,
    resolve_source_binding,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test Maintainer")
    _git(repo, "config", "user.email", "maintainer@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "test: initialize repository")
    return repo


def _error_code(callable_: object, *args: object) -> str:
    with pytest.raises(SourceBindingError) as raised:
        assert callable(callable_)
        callable_(*args)
    return str(raised.value)


def test_resolves_clean_named_branch_with_full_lowercase_revision(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    binding = resolve_source_binding(repo)

    assert binding.repository_root == repo.resolve()
    assert binding.revision == _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert binding.branch == "main"


def test_accepts_matching_asserted_revision(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    revision = _git(repo, "rev-parse", "HEAD").stdout.strip()

    binding = resolve_source_binding(repo, revision)

    assert binding.revision == revision


@pytest.mark.parametrize("change", ["modified", "untracked"])
def test_rejects_dirty_worktree(tmp_path: Path, change: str) -> None:
    repo = _repository(tmp_path)
    target = repo / ("tracked.txt" if change == "modified" else "untracked.txt")
    target.write_text("changed\n", encoding="utf-8")

    assert _error_code(resolve_source_binding, repo) == "source_tree_dirty"


def test_rejects_detached_head(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _git(repo, "checkout", "--detach")

    assert _error_code(resolve_source_binding, repo) == "source_head_detached"


@pytest.mark.parametrize("assertion", ["", "not-a-revision", "A" * 40, "f" * 39])
def test_rejects_invalid_asserted_revision(tmp_path: Path, assertion: str) -> None:
    repo = _repository(tmp_path)

    assert _error_code(resolve_source_binding, repo, assertion) == "source_revision_invalid"


def test_rejects_mismatched_asserted_revision(tmp_path: Path) -> None:
    repo = _repository(tmp_path)

    assert _error_code(resolve_source_binding, repo, "0" * 40) == "source_revision_mismatch"


def test_rejects_non_repository(tmp_path: Path) -> None:
    non_repository = tmp_path / "not-a-repository"
    non_repository.mkdir()

    assert _error_code(resolve_source_binding, non_repository) == "source_repository_unavailable"


def test_rejects_empty_git_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repository(tmp_path)

    def empty_output(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(["git"], 0, stdout="\n", stderr="")

    monkeypatch.setattr("tools.evaluation_projection.provenance.subprocess.run", empty_output)

    assert _error_code(resolve_source_binding, repo) == "source_repository_unavailable"


def test_rejects_failed_git_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repository(tmp_path)

    def failed_probe(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(1, ["git", "rev-parse"])

    monkeypatch.setattr("tools.evaluation_projection.provenance.subprocess.run", failed_probe)

    assert _error_code(resolve_source_binding, repo) == "source_repository_unavailable"


def test_rejects_git_probe_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repository(tmp_path)

    def timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(["git", "rev-parse"], 5)

    monkeypatch.setattr("tools.evaluation_projection.provenance.subprocess.run", timeout)

    assert _error_code(resolve_source_binding, repo) == "source_repository_unavailable"
