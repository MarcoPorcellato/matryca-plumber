"""Parser adapter behavior for the OG identity-only session slice."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any, cast

import pytest
from src.agent import og_parser_identity_adapter
from src.agent.og_parser_identity_adapter import ParserOgIdentityAdapter
from src.graph.session_read_models import GraphSessionReadError


def test_parser_receives_exact_admitted_snapshot_from_one_source_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if identity hashes different bytes or Parser opens the selected source again."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    snapshot = "- caf\u00e9\n".encode("utf-8")
    page.write_bytes(snapshot)
    source_read_count = 0
    parser_inputs: list[tuple[str, str]] = []
    original_os_open = cast(Any, os.open)

    class _ParsedPage:
        title = "Selected"

    class _Parser:
        def parse_page_file(self, path: str) -> _ParsedPage:
            with Path(path).open("rb") as handle:
                handle.read()
            return _ParsedPage()

        def parse(self, text: str, page_title: str = "untitled") -> _ParsedPage:
            parser_inputs.append((text, page_title))
            return _ParsedPage()

    def _counting_open(path: str | Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal source_read_count
        if Path(path) == page:
            source_read_count += 1
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)
    monkeypatch.setattr(os, "open", _counting_open)

    identity = ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")

    assert parser_inputs == [("- caf\u00e9\n", "Selected")]
    assert source_read_count == 1
    assert identity.source_revision == hashlib.sha256(snapshot).hexdigest()


def test_adapter_rejects_oversize_snapshot_before_parser_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a page over the hard byte ceiling reaches Parser."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Selected.md").write_bytes(b"x" * (1024 * 1024 + 1))

    class _Parser:
        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise AssertionError("oversize snapshot reached Parser")

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)

    with pytest.raises(GraphSessionReadError, match="OG snapshot exceeds byte ceiling"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")


def test_adapter_rejects_non_regular_source_before_descriptor_open_or_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a FIFO-like source can reach descriptor open or Parser on any platform."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    page.write_bytes(b"- root\n")
    original_lstat = Path.lstat
    opened = False

    class _Parser:
        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise AssertionError("non-regular source reached Parser")

    def _fifo_like_lstat(path: Path) -> os.stat_result:
        metadata = original_lstat(path)
        if path == page:
            return os.stat_result((stat.S_IFIFO | stat.S_IRUSR, *metadata[1:]))
        return metadata

    def _unexpected_open(*args: Any, **kwargs: Any) -> Any:
        nonlocal opened
        opened = True
        raise AssertionError("non-regular source reached descriptor open")

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)
    monkeypatch.setattr(Path, "lstat", _fifo_like_lstat)
    monkeypatch.setattr(os, "open", _unexpected_open)

    with pytest.raises(GraphSessionReadError, match="OG snapshot source rejected"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")

    assert not opened


def test_adapter_rejects_snapshot_that_grows_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if post-read size growth can validate a stale identity snapshot."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    page.write_bytes(b"- root\n")
    original_fdopen = cast(Any, os.fdopen)
    grew = False

    class _ParsedPage:
        title = "Selected"

    class _Parser:
        def parse_page_file(self, path: str) -> _ParsedPage:
            return _ParsedPage()

        def parse(self, text: str, page_title: str = "untitled") -> _ParsedPage:
            return _ParsedPage()

    class _GrowingRead:
        def __init__(self, handle: Any) -> None:
            self._handle = handle

        def __enter__(self) -> _GrowingRead:
            self._handle.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self._handle.__exit__(*args)

        def read(self, *args: Any) -> str | bytes:
            nonlocal grew
            snapshot = cast(str | bytes, self._handle.read(*args))
            if not grew:
                grew = True
                raw = snapshot.encode("utf-8") if isinstance(snapshot, str) else snapshot
                page.write_bytes(raw + b"x")
            return snapshot

        def __getattr__(self, name: str) -> Any:
            return getattr(self._handle, name)

    def _growing_fdopen(fd: int, *args: Any, **kwargs: Any) -> Any:
        return _GrowingRead(original_fdopen(fd, *args, **kwargs))

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)
    monkeypatch.setattr(os, "fdopen", _growing_fdopen)

    with pytest.raises(GraphSessionReadError, match="OG snapshot changed during read"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")


def test_adapter_rejects_same_size_external_symlink_swapped_after_containment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if an external symlink can replace the validated regular page before open."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    page.write_bytes(b"- root\n")
    external = tmp_path / "external.md"
    external.write_bytes(b"- next\n")
    original_os_open = cast(Any, os.open)
    swapped = False

    class _Parser:
        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise AssertionError("external symlink reached Parser")

    def _swap_to_symlink_then_open(path: str | Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal swapped
        if Path(path) == page and not swapped:
            swapped = True
            page.unlink()
            page.symlink_to(external)
        return original_os_open(path, *args, **kwargs)

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)
    monkeypatch.setattr(os, "open", _swap_to_symlink_then_open)

    with pytest.raises(GraphSessionReadError, match="OG snapshot") as exc_info:
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")

    assert "external.md" not in str(exc_info.value)


def test_adapter_rejects_same_size_replacement_inode_after_descriptor_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a same-size pathname replacement can pass post-read verification."""
    pages = tmp_path / "pages"
    pages.mkdir()
    page = pages / "Selected.md"
    page.write_bytes(b"- root\n")
    replacement = tmp_path / "replacement.md"
    replacement.write_bytes(b"- next\n")
    original_fdopen = cast(Any, os.fdopen)
    replaced = False

    class _Parser:
        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise AssertionError("replaced source reached Parser")

    class _ReplaceOnRead:
        def __init__(self, handle: Any) -> None:
            self._handle = handle

        def __enter__(self) -> _ReplaceOnRead:
            self._handle.__enter__()
            return self

        def __exit__(self, *args: Any) -> Any:
            return self._handle.__exit__(*args)

        def read(self, *args: Any) -> bytes:
            nonlocal replaced
            snapshot = cast(bytes, self._handle.read(*args))
            if not replaced:
                replaced = True
                os.replace(replacement, page)
            return snapshot

        def __getattr__(self, name: str) -> Any:
            return getattr(self._handle, name)

    def _replace_after_read(fd: int, *args: Any, **kwargs: Any) -> Any:
        return _ReplaceOnRead(original_fdopen(fd, *args, **kwargs))

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)
    monkeypatch.setattr(os, "fdopen", _replace_after_read)

    with pytest.raises(GraphSessionReadError, match="OG snapshot changed during read"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")


def test_adapter_rejects_invalid_utf8_snapshot_before_parser_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if invalid UTF-8 is replaced or reaches Parser as altered text."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Selected.md").write_bytes(b"\xff")

    class _Parser:
        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise AssertionError("invalid UTF-8 snapshot reached Parser")

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _Parser)

    with pytest.raises(GraphSessionReadError, match="OG snapshot decoding rejected"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")


def test_parser_adapter_rejects_path_traversal_before_parsing(tmp_path: Path) -> None:
    """Breaks if an unsafe page reference reaches Parser file access."""
    with pytest.raises(GraphSessionReadError, match="invalid OG page reference"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "../outside")


def test_parser_adapter_normalizes_parser_failures_to_a_closed_boundary_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a Parser implementation exception escapes the Plumber boundary."""
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "Selected.md").write_text("- root\n", encoding="utf-8")

    class _FailingParser:
        def parse_page_file(self, path: str) -> object:
            return object()

        def parse(self, text: str, page_title: str = "untitled") -> None:
            raise RuntimeError("parser internals")

    monkeypatch.setattr(og_parser_identity_adapter, "LogosParser", _FailingParser)

    with pytest.raises(GraphSessionReadError, match="OG Parser identity read failed"):
        ParserOgIdentityAdapter().identify_og_graph(tmp_path, "Selected")
