"""Tests for post-write surgical git commits."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from src.daemon.git_audit import path_is_sensitive_for_git, robot_git_commit


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not installed",
)
def test_robot_git_commit_stages_only_target_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Matryca Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@matryca.local")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Matryca Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@matryca.local")
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    pages = tmp_path / "pages"
    pages.mkdir()
    target = pages / "a.md"
    target.write_text("- hello\n", encoding="utf-8")
    other = pages / "b.md"
    other.write_text("- other\n", encoding="utf-8")
    _git(["add", "-A"], tmp_path)
    _git(["commit", "-m", "init"], tmp_path)

    target.write_text("- hello world\n", encoding="utf-8")
    other.write_text("- other changed\n", encoding="utf-8")
    _git(["add", "pages/b.md"], tmp_path)

    result = robot_git_commit(tmp_path, [target], "updated page a")
    assert result.get("committed") is True

    committed_paths = subprocess.run(
        ["git", "show", "--format=", "--name-only", "HEAD"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert committed_paths.stdout.splitlines() == ["pages/a.md"]

    staged_paths = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        check=True,
    )
    assert staged_paths.stdout.splitlines() == ["pages/b.md"]


def test_path_is_sensitive_for_git() -> None:
    assert path_is_sensitive_for_git(".env")
    assert not path_is_sensitive_for_git("pages/Note.md")


def test_robot_git_commit_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MATRYCA_GIT_ROBOT_COMMIT", "false")
    result = robot_git_commit(tmp_path, [tmp_path / "pages" / "x.md"], "test")
    assert result.get("skipped") is True
