"""Synthetic controls for bounded OG capture and post-projection verification."""

from __future__ import annotations

import hashlib
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from src.agent import og_parser_topology_adapter as adapter
from src.agent import og_topology_snapshot as snapshot
from src.agent.og_topology_snapshot import capture_og_topology, verify_og_topology_capture
from src.graph.session_read_models import GraphSessionReadError


def _capture(root: Path) -> tuple[tuple[tuple[str, bytes, str], ...], str]:
    """Compare the private capture's immutable, byte-bound values."""
    capture = capture_og_topology(root)
    return (
        tuple((page.logical_path, page.content, page.sha256) for page in capture.pages),
        capture.source_revision,
    )


@pytest.mark.parametrize("resource", ["entries", "directories", "depth", "files"])
def test_capture_counts_entries_before_descent_and_acceptance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    resource: str,
) -> None:
    """Reject the first excess entry without materializing the remaining walk."""
    pages = tmp_path / "pages"
    pages.mkdir()
    maximum = {"entries": 8192, "directories": 1024, "depth": 32, "files": 1024}[resource]
    if resource == "depth":
        directory = pages
        for _ in range(33):
            directory = directory / "nested"
            directory.mkdir()
    else:
        for ordinal in range(maximum + 2):
            path = pages / f"item-{ordinal:05d}"
            if resource == "directories":
                path.mkdir()
            else:
                path.with_suffix(".md" if resource == "files" else ".ignored").touch()

    original_scandir = os.scandir
    visited = 0
    descended = 0

    class _CountingScan:
        def __init__(self, path: Any) -> None:
            nonlocal descended
            descended += 1
            self._iterator = original_scandir(path)

        def __enter__(self) -> _CountingScan:
            return self

        def __exit__(self, *args: Any) -> None:
            self._iterator.close()

        def __iter__(self) -> _CountingScan:
            return self

        def __next__(self) -> os.DirEntry[str]:
            nonlocal visited
            entry = next(self._iterator)
            visited += 1
            return entry

    monkeypatch.setattr(os, "scandir", _CountingScan)
    error: GraphSessionReadError | None = None
    try:
        _capture(tmp_path)
    except GraphSessionReadError as caught:
        error = caught
    if resource in {"entries", "files"}:
        assert visited <= maximum + 1, "excess entries were materialized before rejection"
    elif resource == "directories":
        assert descended <= maximum, "excess directories were descended before rejection"
    else:
        assert descended <= maximum, "excess directory depth was traversed"
    assert error is not None, "capture accepted an over-limit source"
    assert getattr(error, "code", None) == "bounds_exceeded"


@pytest.mark.parametrize(
    "source", ["missing", "root_link", "directory_link", "file_link", "fifo", "utf8"]
)
def test_capture_rejects_unsafe_and_invalid_utf8_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    """Reject unsafe sources without opening a FIFO or following an external link."""
    root = tmp_path / "graph"
    pages = root / "pages"
    pages.mkdir(parents=True)
    regular = pages / "Safe.md"
    regular.write_bytes(b"- safe\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Secret.md").write_bytes(b"- never admitted\n")
    if source == "missing":
        root = tmp_path / "absent"
    elif source == "root_link":
        link = tmp_path / "alias"
        link.symlink_to(root, target_is_directory=True)
        root = link
    elif source == "directory_link":
        (pages / "linked").symlink_to(outside, target_is_directory=True)
    elif source == "file_link":
        (pages / "Linked.md").symlink_to(outside / "Secret.md")
    elif source == "fifo":
        fifo = pages / "Blocked.md"
        os.mkfifo(fifo)
        original_open = os.open

        def _reject_fifo_open(path: Any, *args: Any, **kwargs: Any) -> int:
            candidate = Path(path)
            relative_target = (
                not candidate.is_absolute()
                and candidate.name == fifo.name
                and kwargs.get("dir_fd") is not None
            )
            assert candidate != fifo and not relative_target, (
                "FIFO reached potentially blocking descriptor open"
            )
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(os, "open", _reject_fifo_open)
    else:
        regular.write_bytes(b"\xff")
    with pytest.raises(GraphSessionReadError) as failure:
        _capture(root)
    assert getattr(failure.value, "code", None) == "source_rejected"
    assert "Secret" not in str(failure.value)


def test_capture_preserves_revision_framing(tmp_path: Path) -> None:
    """Keep the byte-bound revision independent of enumeration and Parser decoding."""
    inputs = {
        "pages/subA.md": b"- fourth\n",
        "pages/sub/x.md": b"- third\n",
        "pages/a.md": "- caf\u00e9\r\n".encode(),
        "pages/B.md": b"- first\n",
        "journals/2026_10_08.md": b"- journal\n",
    }
    for logical_path, content in inputs.items():
        path = tmp_path / logical_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    captured, revision = _capture(tmp_path)
    ordered = sorted(inputs, key=lambda item: item.encode("utf-8"))
    expected = hashlib.sha256()
    for logical_path in ordered:
        logical_bytes = logical_path.encode("utf-8")
        content = inputs[logical_path]
        expected.update(len(logical_bytes).to_bytes(4, "big"))
        expected.update(logical_bytes)
        expected.update(len(content).to_bytes(8, "big"))
        expected.update(content)
    assert [item[0] for item in captured] == ordered
    assert [(item[0], item[1]) for item in captured] == [(key, inputs[key]) for key in ordered]
    assert all(item[2] == hashlib.sha256(item[1]).hexdigest() for item in captured)
    assert revision == expected.hexdigest()


@pytest.mark.parametrize("mutation", ["same_size", "addition", "removal"])
def test_verification_rejects_same_size_edit_addition_and_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    """Never return complete topology after a mutation of the captured synthetic source."""
    pages = tmp_path / "pages"
    pages.mkdir()
    selected = pages / "Selected.md"
    selected.write_bytes(b"- before\n")
    original_projection = adapter._project_topology
    projected = False

    def _mutate_after_projection(*args: Any, **kwargs: Any) -> Any:
        nonlocal projected
        result = original_projection(*args, **kwargs)
        projected = True
        if mutation == "same_size":
            selected.write_bytes(b"- change\n")
        elif mutation == "addition":
            (pages / "Added.md").write_bytes(b"- added\n")
        else:
            selected.unlink()
        return result

    monkeypatch.setattr(adapter, "_project_topology", _mutate_after_projection)
    with pytest.raises(GraphSessionReadError) as failure:
        adapter.ParserOgTopologyAdapter().snapshot_og_graph(tmp_path)
    assert projected
    assert getattr(failure.value, "code", None) == "source_changed"


@pytest.mark.parametrize("resource", ["entries", "directories", "depth", "files"])
def test_capture_accepts_inclusive_walk_limits(tmp_path: Path, resource: str) -> None:
    """The root and admitted subtree entries have explicit inclusive accounting."""
    pages = tmp_path / "pages"
    pages.mkdir()
    if resource == "depth":
        directory = pages
        for _ in range(31):
            directory = directory / "nested"
            directory.mkdir()
    elif resource == "directories":
        for ordinal in range(1022):
            (pages / f"directory-{ordinal}").mkdir()
    else:
        count = 1024 if resource == "files" else 8191
        suffix = ".md" if resource == "files" else ".ignored"
        for ordinal in range(count):
            (pages / f"item-{ordinal}{suffix}").touch()
    captured = capture_og_topology(tmp_path)
    assert len(captured.pages) == (1024 if resource == "files" else 0)


@pytest.mark.parametrize(
    ("resource", "excess"),
    [("file", False), ("file", True), ("total", False), ("total", True)],
)
def test_capture_enforces_inclusive_byte_limits(
    tmp_path: Path, resource: str, excess: bool
) -> None:
    """Bytes are bounded before acceptance, independently of file/node counts."""
    pages = tmp_path / "pages"
    pages.mkdir()
    if resource == "file":
        (pages / "Selected.md").write_bytes(b"x" * (1024 * 1024 + int(excess)))
    else:
        for ordinal in range(16):
            (pages / f"Selected-{ordinal:02d}.md").write_bytes(b"x" * (1024 * 1024))
        if excess:
            (pages / "Excess.md").write_bytes(b"x")
    if excess:
        with pytest.raises(GraphSessionReadError) as failure:
            capture_og_topology(tmp_path)
        assert getattr(failure.value, "code", None) == "bounds_exceeded"
    else:
        capture = capture_og_topology(tmp_path)
        assert sum(len(page.content) for page in capture.pages) == (
            (1 if resource == "file" else 16) * 1024 * 1024
        )


def test_capture_values_are_immutable_and_reverify_identically(tmp_path: Path) -> None:
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Selected.md").write_bytes(b"- root\n")
    capture = capture_og_topology(tmp_path)
    for target, attribute, replacement in (
        (capture, "source_revision", "changed"),
        (capture.pages[0], "content", b"changed"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(target, attribute, replacement)
    verify_og_topology_capture(tmp_path, capture)


@pytest.mark.parametrize("replacement", ["directory_link", "file_link", "fifo"])
def test_capture_rejects_parent_or_leaf_swap_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    """No-follow parent-relative opens reject a post-stat link/FIFO replacement."""
    root = tmp_path / "graph"
    directory = root / "pages/nested"
    directory.mkdir(parents=True)
    selected = directory / "Selected.md"
    selected.write_bytes(b"- safe\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Selected.md").write_bytes(b"- external\n")
    original_open = os.open
    swapped = False

    def _swap_before_open(path: str | Path, *args: Any, **kwargs: Any) -> int:
        nonlocal swapped
        name = "nested" if replacement == "directory_link" else "Selected.md"
        if str(path) == name and not swapped:
            swapped = True
            if replacement == "directory_link":
                directory.rename(root / "detached")
                directory.symlink_to(outside, target_is_directory=True)
            else:
                selected.unlink()
                if replacement == "file_link":
                    selected.symlink_to(outside / "Selected.md")
                else:
                    os.mkfifo(selected)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", _swap_before_open)
    with pytest.raises(GraphSessionReadError) as failure:
        capture_og_topology(root)
    assert swapped
    assert getattr(failure.value, "code", None) == "source_rejected"
    assert (outside / "Selected.md").read_bytes() == b"- external\n"


@pytest.mark.parametrize("root_kind", ["symlink_parent", "expansion"])
def test_capture_rejects_root_interpretation_divergence_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_kind: str
) -> None:
    """A lexical source must not be admitted under another expanded or physical root."""
    lexical = tmp_path / ("lexical" if root_kind == "symlink_parent" else "~") / "graph"
    physical = tmp_path / "physical/graph"
    for root, content in ((lexical, b"- lexical\n"), (physical, b"- physical\n")):
        (root / "pages").mkdir(parents=True)
        (root / "pages/Selected.md").write_bytes(content)
    if root_kind == "symlink_parent":
        target = tmp_path / "physical/sub"
        target.mkdir()
        link = tmp_path / "lexical/link"
        link.symlink_to(target, target_is_directory=True)
        selected = link / ".." / "graph"
    else:
        monkeypatch.chdir(tmp_path)
        selected = Path("~/graph")
        original_expanduser = Path.expanduser

        def _synthetic_expansion(path: Path) -> Path:
            return physical if path == selected else original_expanduser(path)

        monkeypatch.setattr(Path, "expanduser", _synthetic_expansion)
    original_page = snapshot._capture_page
    page_reads = 0

    def _record_page(*args: Any, **kwargs: Any) -> Any:
        nonlocal page_reads
        page_reads += 1
        return original_page(*args, **kwargs)

    monkeypatch.setattr(snapshot, "_capture_page", _record_page)
    failure: GraphSessionReadError | None = None
    try:
        capture_og_topology(selected)
    except GraphSessionReadError as caught:
        failure = caught
    assert failure is not None, "capture accepted divergent root interpretations"
    assert getattr(failure, "code", None) == "source_rejected"
    assert page_reads == 0, "ambiguous root reached Markdown capture"
    assert str(tmp_path) not in str(failure)
