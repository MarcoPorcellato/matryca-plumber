"""Reactive daemon infrastructure: AST cache, file watching, post-write git audit."""

from __future__ import annotations

from pathlib import Path

from .ast_cache import clear_graph_ast_cache, get_graph_ast_cache
from .config_layer import refresh_identity_config
from .file_watcher import GraphFileWatcher
from .git_audit import robot_git_commit, robot_git_commit_enabled
from .post_write_hooks import (
    PostWriteEvent,
    clear_post_write_hooks,
    emit_post_write_commit,
    register_post_write_hook,
)


def register_daemon_post_write_hooks(graph_root: Path) -> None:
    """Wire surgical git commits, identity refresh, and shadow sync after writes."""
    from ..shadow.sync import ensure_shadow_sync_bridge

    ensure_shadow_sync_bridge()
    root = graph_root.expanduser().resolve(strict=False)

    def _on_commit(event: PostWriteEvent) -> None:
        if event.path.suffix.lower() != ".md" or not event.summary:
            return
        robot_git_commit(root, [event.path], event.summary)

    def _on_identity_refresh(event: PostWriteEvent) -> None:
        if event.path.suffix.lower() != ".md":
            return
        refresh_identity_config(root, event.path)

    register_post_write_hook(_on_commit)
    register_post_write_hook(_on_identity_refresh)


__all__ = [
    "GraphFileWatcher",
    "PostWriteEvent",
    "clear_graph_ast_cache",
    "clear_post_write_hooks",
    "emit_post_write_commit",
    "get_graph_ast_cache",
    "refresh_identity_config",
    "register_daemon_post_write_hooks",
    "register_post_write_hook",
    "robot_git_commit",
    "robot_git_commit_enabled",
]
