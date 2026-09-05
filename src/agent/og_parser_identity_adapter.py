"""Internal OG Parser adapter for content-free Plumber graph identity."""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import suppress
from pathlib import Path, PurePosixPath

from logseq_matryca_parser import LogosParser

from ..graph.path_sandbox import resolved_graph_root
from ..graph.ports.session_read import OgGraphIdentityPort
from ..graph.session_read_models import GraphSessionReadError, GraphSourceIdentity
from ..rag.matryca_hooks import resolve_logseq_page_md

MAX_OG_IDENTITY_SNAPSHOT_BYTES = 1024 * 1024


def _validated_page_title(page_title: str) -> str:
    normalized = page_title.strip().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not normalized or normalized.startswith("/") or ".." in parts:
        raise GraphSessionReadError("invalid OG page reference")
    return normalized


def _opaque_digest(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()[:32]


def _file_identity(metadata: os.stat_result) -> tuple[int, int, int]:
    """Return the device, inode, and size binding for one regular source file."""
    return (metadata.st_dev, metadata.st_ino, metadata.st_size)


def _require_regular_source(metadata: os.stat_result) -> None:
    """Reject links and non-regular files before they can become an identity source."""
    if not stat.S_ISREG(metadata.st_mode):
        raise GraphSessionReadError("OG snapshot source rejected")


def _read_bounded_snapshot(page_path: Path) -> bytes:
    """Read one stable, bounded snapshot through a descriptor bound to its lstat identity."""
    descriptor = -1
    try:
        before = page_path.lstat()
        _require_regular_source(before)
        if before.st_size > MAX_OG_IDENTITY_SNAPSHOT_BYTES:
            raise GraphSessionReadError("OG snapshot exceeds byte ceiling")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(page_path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            descriptor_metadata = os.fstat(handle.fileno())
            _require_regular_source(descriptor_metadata)
            if _file_identity(before) != _file_identity(descriptor_metadata):
                raise GraphSessionReadError("OG snapshot changed during read")
            if descriptor_metadata.st_size > MAX_OG_IDENTITY_SNAPSHOT_BYTES:
                raise GraphSessionReadError("OG snapshot exceeds byte ceiling")
            snapshot = handle.read(MAX_OG_IDENTITY_SNAPSHOT_BYTES + 1)
        after = page_path.lstat()
        _require_regular_source(after)
    except GraphSessionReadError:
        raise
    except OSError as exc:
        raise GraphSessionReadError("OG snapshot read rejected") from exc
    finally:
        if descriptor != -1:
            with suppress(OSError):
                os.close(descriptor)
    if (
        len(snapshot) > MAX_OG_IDENTITY_SNAPSHOT_BYTES
        or after.st_size > MAX_OG_IDENTITY_SNAPSHOT_BYTES
    ):
        raise GraphSessionReadError("OG snapshot exceeds byte ceiling")
    if _file_identity(descriptor_metadata) != _file_identity(after):
        raise GraphSessionReadError("OG snapshot changed during read")
    return snapshot


class ParserOgIdentityAdapter(OgGraphIdentityPort):
    """Use the locked public Parser API without exposing its objects past this edge."""

    def identify_og_graph(self, graph_root: Path, page_title: str) -> GraphSourceIdentity:
        title = _validated_page_title(page_title)
        root = resolved_graph_root(graph_root)
        if not root.is_dir():
            raise GraphSessionReadError("OG graph root unavailable")
        try:
            page_path = resolve_logseq_page_md(root, title)
            snapshot = _read_bounded_snapshot(page_path)
        except GraphSessionReadError:
            raise
        except (OSError, ValueError) as exc:
            raise GraphSessionReadError("OG page resolution rejected") from exc
        try:
            source_text = snapshot.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GraphSessionReadError("OG snapshot decoding rejected") from exc
        try:
            parsed_page = LogosParser().parse(source_text, page_title=title)
        except Exception as exc:
            raise GraphSessionReadError("OG Parser identity read failed") from exc
        if parsed_page is None:
            raise GraphSessionReadError("OG Parser returned no page")
        return GraphSourceIdentity(
            graph_id=_opaque_digest(str(root)),
            source_revision=hashlib.sha256(snapshot).hexdigest(),
        )


__all__ = ["MAX_OG_IDENTITY_SNAPSHOT_BYTES", "ParserOgIdentityAdapter"]
