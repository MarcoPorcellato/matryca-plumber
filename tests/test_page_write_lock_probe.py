"""Non-blocking page lock probe before expensive LLM work."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.io_retry import PageLockUnavailableError
from src.graph.page_write_lock import (
    clear_page_write_locks,
    page_rmw_lock,
    probe_page_rmw_lock,
    sweep_matryca_lock_sidecars,
)
from src.graph.safety.write_policy import GraphReadOnlyError


@pytest.fixture(autouse=True)
def _clear_lock_registry() -> Iterator[None]:
    clear_page_write_locks()
    yield
    clear_page_write_locks()


def test_probe_page_rmw_lock_succeeds_when_unlocked(tmp_path: Path) -> None:
    target = tmp_path / "pages" / "Open.md"
    target.parent.mkdir(parents=True)
    target.write_text("- open\n", encoding="utf-8")
    probe_page_rmw_lock(target)


def test_probe_page_rmw_lock_fails_when_thread_lock_held(tmp_path: Path) -> None:
    target = tmp_path / "pages" / "Busy.md"
    target.parent.mkdir(parents=True)
    target.write_text("- busy\n", encoding="utf-8")
    acquired = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with page_rmw_lock(target):
            acquired.set()
            release.wait(timeout=2.0)

    thread = threading.Thread(target=holder)
    thread.start()
    assert acquired.wait(timeout=2.0)
    try:
        with pytest.raises(PageLockUnavailableError):
            probe_page_rmw_lock(target)
    finally:
        release.set()
        thread.join(timeout=2.0)


def test_probe_page_rmw_lock_blocks_before_locking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "pages" / "ReadOnly.md"
    target.parent.mkdir(parents=True)
    target.write_text("- read only\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with pytest.raises(GraphReadOnlyError), monkeypatch.context() as ctx:
        ctx.setattr(
            "src.graph.page_write_lock._lock_for_key",
            lambda _key: (_ for _ in ()).throw(AssertionError("lock")),
        )
        ctx.setattr(
            "src.graph.page_write_lock.probe_exclusive_flock",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("flock")),
        )
        probe_page_rmw_lock(target)


def test_page_rmw_lock_blocks_before_locking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "pages" / "ReadOnly.md"
    target.parent.mkdir(parents=True)
    target.write_text("- read only\n", encoding="utf-8")
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with pytest.raises(GraphReadOnlyError), monkeypatch.context() as ctx:
        ctx.setattr(
            "src.graph.page_write_lock._lock_for_key",
            lambda _key: (_ for _ in ()).throw(AssertionError("lock")),
        )
        ctx.setattr(
            "src.graph.page_write_lock._cross_process_file_lock",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("flock")),
        )
        with page_rmw_lock(target):
            pass


def test_page_lock_symlink_containment_blocks_in_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    target = graph / "pages" / "Live.md"
    target.parent.mkdir(parents=True)
    target.write_text("- live\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    alias = outside / "Alias.md"
    try:
        alias.symlink_to(target)
    except (AttributeError, NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(graph))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with pytest.raises(GraphReadOnlyError):
        probe_page_rmw_lock(alias)


def test_sweep_matryca_lock_sidecars_blocks_before_unlinking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / ".ReadOnly.md.matryca.lock").write_text("lock", encoding="utf-8")
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with (
        patch("src.graph.page_write_lock.Path.unlink", side_effect=AssertionError("unlink")),
        pytest.raises(GraphReadOnlyError),
    ):
        sweep_matryca_lock_sidecars(tmp_path)
