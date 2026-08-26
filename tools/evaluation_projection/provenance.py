"""Bind an evaluation projection to one exact clean Git source tree."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_GIT_TIMEOUT_SECONDS = 5
_REVISION = re.compile(r"^[0-9a-f]{40}$")


class SourceBindingError(RuntimeError):
    """A stable source-binding failure code."""


@dataclass(frozen=True)
class SourceBinding:
    """Exact source state that may be used for a projection."""

    repository_root: Path
    revision: str
    branch: str


def _run_git(repository_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        raise SourceBindingError("source_repository_unavailable") from None
    return completed.stdout.strip()


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve(strict=True)
    except OSError:
        raise SourceBindingError("source_repository_unavailable") from None


def _named_branch(repository_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        raise SourceBindingError("source_repository_unavailable") from None
    if completed.returncode == 1:
        raise SourceBindingError("source_head_detached")
    if completed.returncode != 0:
        raise SourceBindingError("source_repository_unavailable")
    branch = completed.stdout.strip()
    if not branch:
        raise SourceBindingError("source_repository_unavailable")
    return branch


def resolve_source_binding(
    repository_root: Path,
    asserted_revision: str | None = None,
) -> SourceBinding:
    """Return the named, clean, exact source state rooted at ``repository_root``."""
    supplied_root = _resolved_path(repository_root)
    top_level = _run_git(supplied_root, "rev-parse", "--show-toplevel")
    if not top_level or _resolved_path(Path(top_level)) != supplied_root:
        raise SourceBindingError("source_repository_unavailable")

    revision = _run_git(supplied_root, "rev-parse", "--verify", "HEAD^{commit}")
    if not _REVISION.fullmatch(revision):
        raise SourceBindingError("source_repository_unavailable")

    branch = _named_branch(supplied_root)

    status = _run_git(
        supplied_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise SourceBindingError("source_tree_dirty")

    if asserted_revision is not None:
        if not _REVISION.fullmatch(asserted_revision):
            raise SourceBindingError("source_revision_invalid")
        if asserted_revision != revision:
            raise SourceBindingError("source_revision_mismatch")

    return SourceBinding(
        repository_root=supplied_root,
        revision=revision,
        branch=branch,
    )
