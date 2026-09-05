"""Internal OG Parser adapter for content-free Plumber graph identity."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath

from logseq_matryca_parser import LogosParser

from ..graph.markdown_io import read_graph_page_text
from ..graph.path_sandbox import resolved_graph_root
from ..graph.ports.session_read import OgGraphIdentityPort
from ..graph.session_read_models import GraphSessionReadError, GraphSourceIdentity
from ..rag.matryca_hooks import resolve_logseq_page_md


def _validated_page_title(page_title: str) -> str:
    normalized = page_title.strip().replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if not normalized or normalized.startswith("/") or ".." in parts:
        raise GraphSessionReadError("invalid OG page reference")
    return normalized


def _opaque_digest(value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()[:32]


class ParserOgIdentityAdapter(OgGraphIdentityPort):
    """Use the locked public Parser API without exposing its objects past this edge."""

    def identify_og_graph(self, graph_root: Path, page_title: str) -> GraphSourceIdentity:
        title = _validated_page_title(page_title)
        root = resolved_graph_root(graph_root)
        if not root.is_dir():
            raise GraphSessionReadError("OG graph root unavailable")
        try:
            page_path = resolve_logseq_page_md(root, title)
            source_text = read_graph_page_text(page_path, root)
        except (OSError, ValueError) as exc:
            raise GraphSessionReadError("OG page resolution rejected") from exc
        try:
            parsed_page = LogosParser().parse_page_file(str(page_path))
        except Exception as exc:
            raise GraphSessionReadError("OG Parser identity read failed") from exc
        if parsed_page is None:
            raise GraphSessionReadError("OG Parser returned no page")
        return GraphSourceIdentity(
            graph_id=_opaque_digest(str(root)),
            source_revision=_opaque_digest(source_text),
        )


__all__ = ["ParserOgIdentityAdapter"]
