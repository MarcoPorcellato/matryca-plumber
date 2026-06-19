"""OCC-safe writes for Matryca-generated hub pages (Master Index, Graph Insights)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .markdown_blocks import (
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    file_mtime_drifted,
    occ_snapshot,
)
from .page_write_lock import page_rmw_lock
from .path_sandbox import graph_safe_page_path


@dataclass(frozen=True)
class GeneratedHubWriteResult:
    """Outcome of a daemon hub-page compile write."""

    path: Path
    written: bool


def write_generated_hub_page(
    graph_root: Path,
    page_title: str,
    markdown: str,
    *,
    baseline_mtime: int | None = None,
    robot_commit_summary: str,
) -> GeneratedHubWriteResult:
    """Write a compiled hub page under ``page_rmw_lock`` with OCC guards.

    ``baseline_mtime`` should be captured **before** expensive markdown generation
    so edits during compile are detected. On drift, logs a graceful skip and returns
    ``written=False`` (caller may retry on the next daemon cycle).
    """
    path = graph_safe_page_path(graph_root, page_title)
    path.parent.mkdir(parents=True, exist_ok=True)
    pre_mtime = baseline_mtime if baseline_mtime is not None else occ_snapshot(path)

    with page_rmw_lock(path):
        if path.is_file():
            if pre_mtime is not None and file_mtime_drifted(path, pre_mtime):
                logger.info(
                    "Graceful skip: hub page {} edited during compile (mtime drift)",
                    page_title,
                )
                return GeneratedHubWriteResult(path, False)
            current_mtime = occ_snapshot(path)
            if current_mtime is None:
                logger.info(
                    "Graceful skip: hub page {} missing on disk under lock",
                    page_title,
                )
                return GeneratedHubWriteResult(path, False)
            if not atomic_write_bytes_if_unchanged(
                path,
                markdown.encode("utf-8"),
                graph_root=graph_root,
                baseline_mtime=current_mtime,
                validate_block_refs=False,
                robot_commit_summary=robot_commit_summary,
            ):
                logger.info(
                    "Graceful skip: hub page {} OCC abort at commit",
                    page_title,
                )
                return GeneratedHubWriteResult(path, False)
            return GeneratedHubWriteResult(path, True)

        atomic_write_bytes(
            path,
            markdown.encode("utf-8"),
            graph_root=graph_root,
            validate_block_refs=False,
            robot_commit_summary=robot_commit_summary,
        )
        return GeneratedHubWriteResult(path, True)


__all__ = ["GeneratedHubWriteResult", "write_generated_hub_page"]
