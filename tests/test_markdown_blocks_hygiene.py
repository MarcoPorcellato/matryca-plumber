"""Tests for atomic write hygiene and dangling temp sweeper."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from src.graph.markdown_blocks import (
    atomic_write_bytes,
    atomic_write_bytes_if_unchanged,
    file_mtime_drifted,
    occ_snapshot,
    sweep_dangling_atomic_tmp_files,
)
from src.graph.safety.write_policy import GraphReadOnlyError


def test_occ_snapshot_returns_mtime_ns(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("- note\n", encoding="utf-8")
    assert occ_snapshot(page) == page.stat().st_mtime_ns


def test_file_mtime_drifted_detects_one_nanosecond_change(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("- stable\n", encoding="utf-8")
    baseline = page.stat().st_mtime_ns
    os.utime(page, ns=(baseline + 1, baseline + 1))
    assert file_mtime_drifted(page, baseline)
    assert not file_mtime_drifted(page, baseline + 1)


def test_file_mtime_drifted_accepts_legacy_second_baseline(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("- stable\n", encoding="utf-8")
    seconds = page.stat().st_mtime
    assert not file_mtime_drifted(page, seconds)


def test_atomic_write_unlinks_temp_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.graph.markdown_blocks.IO_RETRY_ATTEMPTS", 1)
    target = tmp_path / "page.md"
    temps_before = list(tmp_path.glob(".*.tmp"))

    def boom(src: Path, dst: Path) -> None:
        msg = "simulated replace failure"
        raise OSError(msg)

    with (
        patch("src.graph.markdown_blocks.os.replace", side_effect=boom),
        pytest.raises(OSError, match="simulated replace failure"),
    ):
        atomic_write_bytes(target, b"payload", graph_root=tmp_path)

    assert not target.exists()
    assert list(tmp_path.glob(".page.md.*.tmp")) == []
    assert temps_before == []


def test_atomic_write_bytes_blocks_early_when_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    target = tmp_path / "pages" / "Blocked.md"
    target.parent.mkdir(parents=True)

    with (
        patch("src.graph.markdown_blocks.tempfile.mkstemp", side_effect=AssertionError("mkstemp")),
        patch("src.graph.markdown_blocks.os.replace", side_effect=AssertionError("replace")),
        patch("src.graph.markdown_blocks.Path.mkdir", side_effect=AssertionError("mkdir")),
        pytest.raises(GraphReadOnlyError),
    ):
        atomic_write_bytes(target, b"payload", graph_root=tmp_path)


def test_atomic_write_bytes_if_unchanged_blocks_before_delegate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")
    target = tmp_path / "pages" / "Blocked.md"

    with (
        patch(
            "src.graph.markdown_blocks.atomic_write_bytes",
            side_effect=AssertionError("delegate"),
        ),
        pytest.raises(GraphReadOnlyError),
    ):
        atomic_write_bytes_if_unchanged(
            target,
            b"payload",
            graph_root=tmp_path,
            baseline_mtime=0,
        )


def test_atomic_write_bytes_blocks_symlink_containment_in_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = tmp_path / "graph"
    target_dir = graph / "pages"
    target_dir.mkdir(parents=True)
    target = target_dir / "Live.md"
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

    with (
        patch("src.graph.markdown_blocks.tempfile.mkstemp", side_effect=AssertionError("mkstemp")),
        pytest.raises(GraphReadOnlyError),
    ):
        atomic_write_bytes(alias, b"payload", graph_root=graph)


def test_sweep_dangling_atomic_tmp_files_removes_orphans(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    journals = tmp_path / "journals"
    pages.mkdir()
    journals.mkdir()
    orphan_page = pages / ".Note.md.deadbeef.tmp"
    orphan_journal = journals / ".2026_05_19.md.cafebabe.tmp"
    keep_page = pages / "Note.md"
    orphan_page.write_bytes(b"stale")
    orphan_journal.write_bytes(b"stale")
    keep_page.write_text("live", encoding="utf-8")

    removed = sweep_dangling_atomic_tmp_files(tmp_path)
    assert removed == 2
    assert not orphan_page.exists()
    assert not orphan_journal.exists()
    assert keep_page.read_text(encoding="utf-8") == "live"


def test_sweep_dangling_atomic_tmp_files_blocks_when_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = tmp_path / "pages"
    journals = tmp_path / "journals"
    pages.mkdir()
    journals.mkdir()
    (pages / ".Note.md.deadbeef.tmp").write_bytes(b"stale")

    monkeypatch.setenv("LOGSEQ_GRAPH_PATH", str(tmp_path))
    monkeypatch.setenv("MATRYCA_READ_ONLY", "true")

    with (
        patch("src.graph.markdown_blocks.Path.unlink", side_effect=AssertionError("unlink")),
        pytest.raises(GraphReadOnlyError),
    ):
        sweep_dangling_atomic_tmp_files(tmp_path)


def test_sweep_ignores_unrelated_hidden_files(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    unrelated = pages / ".gitkeep"
    unrelated.write_text("", encoding="utf-8")
    assert sweep_dangling_atomic_tmp_files(tmp_path) == 0
    assert unrelated.is_file()
