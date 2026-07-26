"""Convert a Tana workspace graph into Logseq ``OutlineNode`` import plans."""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from ...outline_models import OutlineNode
from .graph import TanaWorkspaceGraph
from .html import plain_text_from_tana_html
from .journal import resolve_journal_path
from .provenance import (
    PROP_TANA_DEPTH_SPLIT,
    block_provenance_properties,
    iso_export_timestamp,
    page_provenance_properties,
)
from .schema import NodeDump
from .tags import LogseqPropertyLine, TanaTagsExtractor

DEFAULT_MAX_DEPTH = 8
DEFAULT_NAMESPACE = "Tana"
_DAY_SUPERTAG = "day"
_SPLIT_NAMESPACE = "Split"
_UNTITLED = "Untitled"
_FIELD_FALLBACK_PREFIX = "field"


@dataclass(frozen=True, slots=True)
class ConvertedPagePlan:
    """One Logseq page to create under ``pages/``."""

    page_title: str
    page_properties: dict[str, str]
    outline_roots: list[OutlineNode]


@dataclass(frozen=True, slots=True)
class ConvertedJournalPlan:
    """One journal file append target."""

    page_title: str
    relative_path: str
    outline_roots: list[OutlineNode]


@dataclass
class TanaConvertResult:
    """Full hybrid placement output from a workspace graph."""

    pages: list[ConvertedPagePlan] = field(default_factory=list)
    journals: list[ConvertedJournalPlan] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    depth_splits: int = 0
    property_key_collisions: int = 0


class TanaConverter:
    """Build ``OutlineNode`` trees with hybrid placement, depth split, and provenance."""

    def __init__(
        self,
        graph: TanaWorkspaceGraph,
        *,
        namespace: str | None = None,
        max_depth: int | None = None,
        journal_page_title_format: str = "yyyy-MM-dd",
        journal_file_name_format: str | None = None,
        vault_path: str | Path | None = None,
        export_file: str | None = None,
        export_ts: str | None = None,
    ) -> None:
        self._graph = graph
        env_ns = os.environ.get("MATRYCA_TANA_IMPORT_NAMESPACE")
        self._namespace = (namespace or env_ns or DEFAULT_NAMESPACE).strip("/")
        env_depth = os.environ.get("MATRYCA_TANA_DEPTH_LIMIT", "").strip()
        parsed_depth = int(env_depth) if env_depth.isdigit() else DEFAULT_MAX_DEPTH
        self._max_depth = max_depth if max_depth is not None else parsed_depth
        self._journal_title_format = journal_page_title_format
        self._journal_file_format = journal_file_name_format
        self._vault_path = (
            Path(vault_path).expanduser()
            if vault_path is not None
            # Unconfigured fallback: a fixed /tmp path is predictable and races with
            # other local users on shared machines, so mint a private temp dir instead.
            else Path(tempfile.mkdtemp(prefix="matryca-tana-vault-"))
        )
        self._export_file = export_file
        self._export_ts = export_ts or iso_export_timestamp()
        self._tags = TanaTagsExtractor(graph, journal_page_title_format=journal_page_title_format)
        self._used_page_titles: set[str] = set()
        self._field_key_counts: dict[str, int] = {}
        self._entity_titles: dict[str, str] = {}

    def convert(self) -> TanaConvertResult:
        result = TanaConvertResult()
        entity_ids = [
            node_id
            for node_id in self._graph.nodes
            if self._graph.classify_entity(node_id).is_entity and not self._is_day_node(node_id)
        ]
        day_ids = [node_id for node_id in self._graph.nodes if self._is_day_node(node_id)]

        self._entity_titles = {
            node_id: self._allocate_page_title(self._entity_page_title(node_id))
            for node_id in entity_ids
        }

        for node_id in entity_ids:
            title = self._entity_titles[node_id]
            page = self._convert_entity_page(node_id, result, page_title=title)
            result.pages.append(page)

        for node_id in day_ids:
            journal = self._convert_day_journal(node_id, result)
            if journal is not None:
                result.journals.append(journal)

        return result

    def _convert_entity_page(
        self,
        node_id: str,
        result: TanaConvertResult,
        *,
        page_title: str,
    ) -> ConvertedPagePlan:
        node = self._graph.nodes[node_id]
        fields = self._tags.extract_for_node(node_id)
        result.warnings.extend(fields.warnings)
        label = _node_label(node) or _UNTITLED
        page_props = page_provenance_properties(
            node_id,
            node,
            export_ts=self._export_ts,
            export_file=self._export_file,
            tags=fields.supertag_names,
        )
        if fields.supertag_names:
            page_props["type"] = fields.supertag_names[0]

        root = self._node_to_outline(
            node_id,
            depth=0,
            inline_tags_on_block=False,
            page_tags=fields.supertag_names,
            override_text=label,
            result=result,
        )
        child_nodes, split_pages, splits = self._convert_children(node_id, depth=0, result=result)
        root.children = child_nodes
        result.pages.extend(split_pages)
        result.depth_splits += splits
        return ConvertedPagePlan(
            page_title=page_title,
            page_properties=page_props,
            outline_roots=[root],
        )

    def _convert_day_journal(
        self,
        node_id: str,
        result: TanaConvertResult,
    ) -> ConvertedJournalPlan | None:
        node = self._graph.nodes[node_id]
        fields = self._tags.extract_for_node(node_id)
        result.warnings.extend(fields.warnings)
        day = _resolve_day_date(node, fields)
        if day is None:
            result.warnings.append(f"could not resolve calendar date for day node {node_id}")
            return None
        journal = resolve_journal_path(
            self._vault_path,
            day,
            page_title_format=self._journal_title_format,
            file_name_format=self._journal_file_format or self._journal_title_format,
        )
        root = self._node_to_outline(node_id, depth=0, inline_tags_on_block=True, result=result)
        child_nodes, split_pages, splits = self._convert_children(node_id, depth=0, result=result)
        root.children = child_nodes
        result.pages.extend(split_pages)
        result.depth_splits += splits
        return ConvertedJournalPlan(
            page_title=journal.page_title,
            relative_path=journal.relative_path,
            outline_roots=[root],
        )

    def _convert_children(
        self,
        parent_id: str,
        *,
        depth: int,
        result: TanaConvertResult,
    ) -> tuple[list[OutlineNode], list[ConvertedPagePlan], int]:
        outlines: list[OutlineNode] = []
        split_pages: list[ConvertedPagePlan] = []
        splits = 0
        for child_id in self._graph.children_by_parent.get(parent_id, []):
            if self._should_skip_node(child_id):
                continue
            if self._graph.classify_entity(child_id).is_entity and not self._is_day_node(child_id):
                link_title = self._entity_titles.get(
                    child_id,
                    self._allocate_page_title(self._entity_page_title(child_id)),
                )
                outlines.append(
                    OutlineNode(
                        text=f"[[{link_title}]]",
                        properties=block_provenance_properties(
                            child_id,
                            self._graph.nodes[child_id],
                            export_ts=self._export_ts,
                            export_file=self._export_file,
                        ),
                    )
                )
                continue
            child_depth = depth + 1
            if child_depth >= self._max_depth:
                split_page, link_outline = self._split_subtree(child_id, result)
                split_pages.append(split_page)
                outlines.append(link_outline)
                splits += 1
                continue
            child_outline = self._node_to_outline(
                child_id,
                depth=child_depth,
                inline_tags_on_block=True,
                result=result,
            )
            grandchildren, grand_pages, grand_splits = self._convert_children(
                child_id,
                depth=child_depth,
                result=result,
            )
            child_outline.children = grandchildren
            outlines.append(child_outline)
            split_pages.extend(grand_pages)
            splits += grand_splits
        return outlines, split_pages, splits

    def _split_subtree(
        self,
        node_id: str,
        result: TanaConvertResult,
    ) -> tuple[ConvertedPagePlan, OutlineNode]:
        node = self._graph.nodes[node_id]
        label = _node_label(node) or _UNTITLED
        split_title = self._allocate_page_title(f"{self._namespace}/{_SPLIT_NAMESPACE}/{label}")
        page_props = page_provenance_properties(
            node_id,
            node,
            export_ts=self._export_ts,
            export_file=self._export_file,
            depth_split=True,
        )
        root = self._node_to_outline(node_id, depth=0, inline_tags_on_block=True, result=result)
        children, split_pages, splits = self._convert_children(node_id, depth=0, result=result)
        root.children = children
        result.pages.extend(split_pages)
        result.depth_splits += splits
        page = ConvertedPagePlan(
            page_title=split_title,
            page_properties=page_props,
            outline_roots=[root],
        )
        link = OutlineNode(
            text=f"[[{split_title}]]",
            properties={
                **block_provenance_properties(
                    node_id,
                    node,
                    export_ts=self._export_ts,
                    export_file=self._export_file,
                ),
                PROP_TANA_DEPTH_SPLIT: "true",
            },
        )
        return page, link

    def _node_to_outline(
        self,
        node_id: str,
        *,
        depth: int,
        inline_tags_on_block: bool,
        page_tags: list[str] | None = None,
        override_text: str | None = None,
        result: TanaConvertResult | None = None,
    ) -> OutlineNode:
        node = self._graph.nodes[node_id]
        fields = self._tags.extract_for_node(node_id)
        text = override_text if override_text is not None else _node_label(node)
        text = f"{_task_prefix(node)}{text}".strip() or _UNTITLED
        if inline_tags_on_block:
            for tag in fields.supertag_names:
                token = f"#{tag}"
                if token not in text:
                    text = f"{text} {token}".strip()
        props = block_provenance_properties(
            node_id,
            node,
            export_ts=self._export_ts,
            export_file=self._export_file,
        )
        props.update(self._field_properties(fields.properties, node_id=node_id, result=result))
        if page_tags:
            props.setdefault("type", page_tags[0])
        return OutlineNode(text=text, properties=props)

    def _field_properties(
        self,
        field_props: list[LogseqPropertyLine],
        *,
        node_id: str,
        result: TanaConvertResult | None = None,
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in field_props:
            key = line.key.strip()
            if not key:
                key = self._fallback_field_key(node_id)
            if key in out:
                if result is not None:
                    result.property_key_collisions += 1
                self._field_key_counts[key] = self._field_key_counts.get(key, 1) + 1
                key = f"{key}-{self._field_key_counts[key]}"
            out[key] = line.value
        return out

    def _fallback_field_key(self, node_id: str) -> str:
        count = self._field_key_counts.get(_FIELD_FALLBACK_PREFIX, 0) + 1
        self._field_key_counts[_FIELD_FALLBACK_PREFIX] = count
        suffix = "" if count == 1 else f"-{count}"
        return f"{_FIELD_FALLBACK_PREFIX}{suffix}"

    def _entity_page_title(self, node_id: str, supertags: list[str] | None = None) -> str:
        node = self._graph.nodes[node_id]
        label = _node_label(node) or _UNTITLED
        if supertags is not None:
            tags = supertags
        else:
            tags = self._tags.extract_for_node(node_id).supertag_names
        primary = tags[0] if tags else None
        if primary:
            return f"{self._namespace}/{primary}/{label}"
        return f"{self._namespace}/{label}"

    def _allocate_page_title(self, base_title: str) -> str:
        if base_title not in self._used_page_titles:
            self._used_page_titles.add(base_title)
            return base_title
        suffix = 2
        while f"{base_title} ({suffix})" in self._used_page_titles:
            suffix += 1
        unique = f"{base_title} ({suffix})"
        self._used_page_titles.add(unique)
        return unique

    def _is_day_node(self, node_id: str) -> bool:
        tags = self._tags.extract_for_node(node_id).supertag_names
        return any(tag.casefold() == _DAY_SUPERTAG for tag in tags)

    def _should_skip_node(self, node_id: str) -> bool:
        if self._graph.is_system_node(node_id):
            return True
        if node_id == self._graph.stash_root_id:
            return True
        return node_id == self._graph.schema_root_id


def convert_tana_graph(
    graph: TanaWorkspaceGraph,
    *,
    vault_path: str | Path | None = None,
    max_depth: int | None = None,
    journal_page_title_format: str = "yyyy-MM-dd",
    journal_file_name_format: str | None = None,
    namespace: str | None = None,
    export_file: str | None = None,
) -> TanaConvertResult:
    """Convert an indexed Tana graph into page/journal ``OutlineNode`` plans."""
    converter = TanaConverter(
        graph,
        namespace=namespace,
        max_depth=max_depth,
        journal_page_title_format=journal_page_title_format,
        journal_file_name_format=journal_file_name_format,
        vault_path=vault_path,
        export_file=export_file,
    )
    return converter.convert()


def _node_label(node: NodeDump) -> str:
    raw = node.props.get("name")
    if isinstance(raw, str):
        return plain_text_from_tana_html(raw)
    return ""


def _task_prefix(node: NodeDump) -> str:
    done = node.props.get("_done")
    if done is True or (isinstance(done, (int, float)) and done and not isinstance(done, bool)):
        return "DONE "
    if node.props.get("done") is True:
        return "DONE "
    if done is False or node.props.get("done") is False:
        return "TODO "
    return ""


def _resolve_day_date(node: NodeDump, fields: object) -> date | None:
    created = node.props.get("created")
    if isinstance(created, (int, float)) and created > 0:
        return datetime.fromtimestamp(created / 1000, tz=UTC).date()
    label = _node_label(node)
    for token in re.findall(r"\d{4}-\d{2}-\d{2}", label):
        try:
            return date.fromisoformat(token)
        except ValueError:
            continue
    return None


__all__ = [
    "ConvertedJournalPlan",
    "ConvertedPagePlan",
    "DEFAULT_MAX_DEPTH",
    "TanaConvertResult",
    "TanaConverter",
    "convert_tana_graph",
]
