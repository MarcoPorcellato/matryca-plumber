"""Surgical post-write git commits for robot-modified markdown files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from git import Repo

_SENSITIVE_GIT_PATH_MARKERS = (
    ".env",
    "credentials",
    "secrets",
    ".pem",
    "id_rsa",
    "private_key",
)


def path_is_sensitive_for_git(rel_path: str) -> bool:
    """Return whether a relative path must never be robot-committed."""
    lowered = rel_path.lower()
    return any(marker in lowered for marker in _SENSITIVE_GIT_PATH_MARKERS)


def robot_git_commit_enabled() -> bool:
    """Return False only when ``MATRYCA_GIT_ROBOT_COMMIT`` is explicitly disabled."""
    raw = os.environ.get("MATRYCA_GIT_ROBOT_COMMIT", "").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _open_robot_commit_repo(root: Path) -> tuple[Repo | None, dict[str, object] | None]:
    """Return ``(repo, None)`` on success, or ``(None, skip_result)`` on any guard failure."""
    try:
        from git import InvalidGitRepositoryError, Repo
    except ImportError:
        logger.error("GitPython is not installed; skipping robot git commit")
        return None, {"committed": False, "skipped": True, "reason": "GitPython missing"}

    try:
        repo = Repo(str(root))
    except InvalidGitRepositoryError:
        return None, {"committed": False, "skipped": True, "reason": "invalid git repository"}

    if repo.bare:
        return None, {"committed": False, "skipped": True, "reason": "bare repository"}

    return repo, None


def _relative_committable_paths(md_paths: list[Path], root: Path) -> list[str]:
    """Resolve ``md_paths`` to graph-relative posix strings, dropping unsafe ones."""
    rel_paths: list[str] = []
    for path in md_paths:
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            logger.warning("Skipping git stage for path outside graph root: {}", path)
            continue
        if path_is_sensitive_for_git(rel):
            logger.warning("Skipping robot git commit for sensitive path: {}", rel)
            continue
        rel_paths.append(rel)
    return rel_paths


def robot_git_commit(
    graph_root: str | Path,
    paths: list[Path],
    summary: str,
) -> dict[str, object]:
    """Stage only ``paths`` and commit with a ``robot(matryca):`` message.

    Never raises; failures are logged and returned in the result dict.
    """
    if not robot_git_commit_enabled():
        return {"committed": False, "skipped": True, "reason": "MATRYCA_GIT_ROBOT_COMMIT disabled"}

    root = Path(graph_root).expanduser().resolve(strict=False)
    if not (root / ".git").is_dir():
        return {"committed": False, "skipped": True, "reason": "no .git at graph root"}

    md_paths = [p for p in paths if p.suffix.lower() == ".md" and p.is_file()]
    if not md_paths:
        return {"committed": False, "skipped": True, "reason": "no markdown paths"}

    repo, skip_result = _open_robot_commit_repo(root)
    if skip_result is not None or repo is None:
        return skip_result or {
            "committed": False,
            "skipped": True,
            "reason": "invalid git repository",
        }

    rel_paths = _relative_committable_paths(md_paths, root)
    if not rel_paths:
        return {"committed": False, "skipped": True, "reason": "no paths under graph root"}

    message = f"robot(matryca): AI auto-update - {summary.strip() or 'updated markdown'}"

    try:
        repo.index.add(rel_paths)
        if not repo.index.diff("HEAD", paths=tuple(rel_paths)):
            return {
                "committed": False,
                "skipped": True,
                "reason": "no changes to commit for staged paths",
            }
        repo.git.commit("--only", "-m", message, "--", *rel_paths)
    except Exception as exc:  # noqa: BLE001 - never crash writers
        logger.error("Robot git commit failed under {}: {}", root, exc)
        return {
            "committed": False,
            "skipped": False,
            "reason": str(exc)[:500],
        }

    logger.bind(paths=rel_paths, message=message).info("Robot git commit recorded")
    return {
        "committed": True,
        "skipped": False,
        "reason": "ok",
        "message": message,
        "paths": rel_paths,
    }


__all__ = ["robot_git_commit", "robot_git_commit_enabled"]
