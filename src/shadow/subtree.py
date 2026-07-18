"""Recursive CTE subtree reads from ``shadow.sqlite`` (v2 PR-C1 / #253)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

_DEFAULT_MAX_DEPTH = 64
_DEFAULT_MAX_NODES = 500
_DEFAULT_MAX_OUTPUT_BYTES = 256_000
_TRUNCATION_NOTICE = "\n… [truncated: output byte limit exceeded]\n"


class SubtreeStatus(StrEnum):
    """Outcome of a shadow subtree query."""

    NOT_FOUND = "not_found"
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    INCONSISTENT = "inconsistent"


@dataclass(frozen=True, slots=True)
class SubtreeBlock:
    """One block row in depth-first subtree order."""

    rowid: int
    block_uuid: str
    page_id: int
    parent_rowid: int | None
    sort_order: int
    indent_level: int
    content: str
    properties_json: str
    depth: int
    path_key: str


@dataclass(frozen=True, slots=True)
class SubtreeQueryResult:
    """Result of ``query_subtree_by_block_uuid``."""

    status: SubtreeStatus
    anchor_uuid: str
    page_id: int | None
    nodes: tuple[SubtreeBlock, ...]
    excerpt_markdown: str
    detail: str | None = None


def _clamp_limits(
    *,
    max_depth: int,
    max_nodes: int,
    max_output_bytes: int,
) -> tuple[int, int, int]:
    depth = max(1, min(int(max_depth), 256))
    nodes = max(1, min(int(max_nodes), 10_000))
    output_bytes = max(1, min(int(max_output_bytes), 10_000_000))
    return depth, nodes, output_bytes


def _fetch_anchor(
    connection: sqlite3.Connection,
    block_uuid: str,
) -> sqlite3.Row | None:
    row = connection.execute(
        """
        SELECT rowid, block_uuid, page_id, parent_rowid, sort_order,
               indent_level, content, properties_json
        FROM blocks
        WHERE block_uuid = ?
        """,
        (block_uuid,),
    ).fetchone()
    return cast(sqlite3.Row | None, row)


def _has_cross_page_edge(
    connection: sqlite3.Connection,
    *,
    anchor_rowid: int,
    page_id: int,
) -> bool:
    row = connection.execute(
        """
        WITH RECURSIVE walk(rowid, page_id) AS (
            SELECT rowid, page_id FROM blocks WHERE rowid = ?
            UNION ALL
            SELECT child.rowid, child.page_id
            FROM blocks AS child
            INNER JOIN walk ON child.parent_rowid = walk.rowid
            WHERE child.page_id = walk.page_id
        )
        SELECT 1
        FROM blocks AS child
        INNER JOIN walk ON child.parent_rowid = walk.rowid
        WHERE child.page_id != ?
        LIMIT 1
        """,
        (anchor_rowid, page_id),
    ).fetchone()
    return row is not None


def _has_cycle_in_subtree(
    connection: sqlite3.Connection,
    *,
    anchor_rowid: int,
    page_id: int,
) -> bool:
    path: set[int] = set()

    def dfs(rowid: int) -> bool:
        if rowid in path:
            return True
        path.add(rowid)
        children = connection.execute(
            """
            SELECT rowid
            FROM blocks
            WHERE parent_rowid = ? AND page_id = ?
            ORDER BY sort_order, rowid
            """,
            (rowid, page_id),
        ).fetchall()
        for (child_rowid,) in children:
            if dfs(int(child_rowid)):
                return True
        path.remove(rowid)
        return False

    return dfs(anchor_rowid)


def _count_subtree_nodes(
    connection: sqlite3.Connection,
    *,
    anchor_rowid: int,
    page_id: int,
    max_depth: int,
) -> int:
    depth_cap = max_depth - 1
    row = connection.execute(
        """
        WITH RECURSIVE subtree(
            rowid, depth, visited
        ) AS (
            SELECT rowid, 0, CAST(rowid AS TEXT)
            FROM blocks
            WHERE rowid = ?
            UNION ALL
            SELECT
                child.rowid,
                subtree.depth + 1,
                subtree.visited || ',' || CAST(child.rowid AS TEXT)
            FROM blocks AS child
            INNER JOIN subtree ON child.parent_rowid = subtree.rowid
            WHERE child.page_id = ?
              AND subtree.depth < ?
              AND instr(',' || subtree.visited || ',', ',' || CAST(child.rowid AS TEXT) || ',') = 0
        )
        SELECT COUNT(*) FROM subtree
        """,
        (anchor_rowid, page_id, depth_cap),
    ).fetchone()
    return int(row[0]) if row is not None else 0


def _fetch_subtree_rows(
    connection: sqlite3.Connection,
    *,
    anchor_rowid: int,
    page_id: int,
    max_depth: int,
    max_nodes: int,
) -> list[sqlite3.Row]:
    depth_cap = max_depth - 1
    return connection.execute(
        """
        WITH RECURSIVE subtree(
            rowid,
            block_uuid,
            page_id,
            parent_rowid,
            sort_order,
            indent_level,
            content,
            properties_json,
            depth,
            path_key,
            visited
        ) AS (
            SELECT
                rowid,
                block_uuid,
                page_id,
                parent_rowid,
                sort_order,
                indent_level,
                content,
                properties_json,
                0,
                printf('%020d,%020d', sort_order, rowid),
                CAST(rowid AS TEXT)
            FROM blocks
            WHERE rowid = ?
            UNION ALL
            SELECT
                child.rowid,
                child.block_uuid,
                child.page_id,
                child.parent_rowid,
                child.sort_order,
                child.indent_level,
                child.content,
                child.properties_json,
                subtree.depth + 1,
                subtree.path_key || '/' || printf('%020d,%020d', child.sort_order, child.rowid),
                subtree.visited || ',' || CAST(child.rowid AS TEXT)
            FROM blocks AS child
            INNER JOIN subtree ON child.parent_rowid = subtree.rowid
            WHERE child.page_id = ?
              AND subtree.depth < ?
              AND instr(',' || subtree.visited || ',', ',' || CAST(child.rowid AS TEXT) || ',') = 0
        )
        SELECT
            rowid,
            block_uuid,
            page_id,
            parent_rowid,
            sort_order,
            indent_level,
            content,
            properties_json,
            depth,
            path_key
        FROM subtree
        ORDER BY path_key
        LIMIT ?
        """,
        (
            anchor_rowid,
            page_id,
            depth_cap,
            max_nodes,
        ),
    ).fetchall()


def _rows_to_blocks(rows: list[sqlite3.Row]) -> tuple[SubtreeBlock, ...]:
    blocks: list[SubtreeBlock] = []
    for row in rows:
        blocks.append(
            SubtreeBlock(
                rowid=int(row[0]),
                block_uuid=str(row[1]),
                page_id=int(row[2]),
                parent_rowid=int(row[3]) if row[3] is not None else None,
                sort_order=int(row[4]),
                indent_level=int(row[5]),
                content=str(row[6]),
                properties_json=str(row[7]),
                depth=int(row[8]),
                path_key=str(row[9]),
            )
        )
    return tuple(blocks)


def _render_block_lines(block: SubtreeBlock) -> list[str]:
    unit = "  "
    prefix = unit * block.indent_level
    lines = [f"{prefix}- {block.content}\n"]
    props: dict[str, Any] = {}
    if block.properties_json:
        try:
            loaded = json.loads(block.properties_json)
            if isinstance(loaded, dict):
                props = loaded
        except json.JSONDecodeError:
            props = {}
    block_id = str(props.get("id", "")).strip()
    if block_id:
        lines.append(f"{prefix}  id:: {block_id}\n")
    return lines


def _apply_output_byte_limit(
    blocks: tuple[SubtreeBlock, ...],
    *,
    max_output_bytes: int,
) -> tuple[tuple[SubtreeBlock, ...], str, bool]:
    if not blocks:
        return blocks, "", False

    selected: list[SubtreeBlock] = []
    parts: list[str] = []
    used = 0
    truncated = False

    for block in blocks:
        rendered = "".join(_render_block_lines(block))
        chunk = rendered.encode("utf-8")
        if not selected:
            selected.append(block)
            parts.append(rendered)
            used = len(chunk)
            if used > max_output_bytes:
                truncated = True
            continue
        if used + len(chunk) > max_output_bytes:
            truncated = True
            break
        selected.append(block)
        parts.append(rendered)
        used += len(chunk)

    excerpt = "".join(parts)
    if truncated:
        if excerpt:
            excerpt = excerpt.rstrip("\n") + _TRUNCATION_NOTICE
        else:
            excerpt = _TRUNCATION_NOTICE.lstrip("\n")
    return tuple(selected), excerpt, truncated


def _has_depth_or_node_truncation(
    connection: sqlite3.Connection,
    *,
    anchor_rowid: int,
    page_id: int,
    max_depth: int,
    max_nodes: int,
    fetched_count: int,
) -> bool:
    if fetched_count >= max_nodes:
        total = _count_subtree_nodes(
            connection,
            anchor_rowid=anchor_rowid,
            page_id=page_id,
            max_depth=max_depth,
        )
        if total > fetched_count:
            return True
    if max_depth <= 1:
        return False
    deepest = max_depth - 1
    row = connection.execute(
        """
        WITH RECURSIVE at_depth(rowid, depth) AS (
            SELECT rowid, 0 FROM blocks WHERE rowid = ?
            UNION ALL
            SELECT child.rowid, at_depth.depth + 1
            FROM blocks AS child
            INNER JOIN at_depth ON child.parent_rowid = at_depth.rowid
            WHERE child.page_id = ?
              AND at_depth.depth < ?
        )
        SELECT 1
        FROM blocks AS child
        INNER JOIN at_depth ON child.parent_rowid = at_depth.rowid
        WHERE child.page_id = ?
          AND at_depth.depth = ?
        LIMIT 1
        """,
        (anchor_rowid, page_id, deepest, page_id, deepest),
    ).fetchone()
    return row is not None


def query_subtree_by_block_uuid(
    connection: sqlite3.Connection,
    block_uuid: str,
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    max_nodes: int = _DEFAULT_MAX_NODES,
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
) -> SubtreeQueryResult:
    """Return the anchor block and descendants in deterministic depth-first order."""
    anchor_uuid = block_uuid.strip()
    if not anchor_uuid:
        return SubtreeQueryResult(
            status=SubtreeStatus.NOT_FOUND,
            anchor_uuid=anchor_uuid,
            page_id=None,
            nodes=(),
            excerpt_markdown="",
            detail="block_uuid is empty",
        )

    depth_limit, node_limit, byte_limit = _clamp_limits(
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_output_bytes=max_output_bytes,
    )

    anchor = _fetch_anchor(connection, anchor_uuid)
    if anchor is None:
        return SubtreeQueryResult(
            status=SubtreeStatus.NOT_FOUND,
            anchor_uuid=anchor_uuid,
            page_id=None,
            nodes=(),
            excerpt_markdown="",
            detail=f"block `{anchor_uuid}` not found in shadow blocks",
        )

    anchor_rowid = int(anchor[0])
    page_id = int(anchor[2])

    if _has_cross_page_edge(
        connection,
        anchor_rowid=anchor_rowid,
        page_id=page_id,
    ):
        return SubtreeQueryResult(
            status=SubtreeStatus.INCONSISTENT,
            anchor_uuid=anchor_uuid,
            page_id=page_id,
            nodes=(),
            excerpt_markdown="",
            detail="subtree contains a child block on a different page_id",
        )

    if _has_cycle_in_subtree(
        connection,
        anchor_rowid=anchor_rowid,
        page_id=page_id,
    ):
        return SubtreeQueryResult(
            status=SubtreeStatus.INCONSISTENT,
            anchor_uuid=anchor_uuid,
            page_id=page_id,
            nodes=(),
            excerpt_markdown="",
            detail="subtree contains a parent_rowid cycle",
        )

    rows = _fetch_subtree_rows(
        connection,
        anchor_rowid=anchor_rowid,
        page_id=page_id,
        max_depth=depth_limit,
        max_nodes=node_limit,
    )
    blocks = _rows_to_blocks(rows)
    limited_blocks, excerpt, byte_truncated = _apply_output_byte_limit(
        blocks,
        max_output_bytes=byte_limit,
    )

    truncated = byte_truncated or _has_depth_or_node_truncation(
        connection,
        anchor_rowid=anchor_rowid,
        page_id=page_id,
        max_depth=depth_limit,
        max_nodes=node_limit,
        fetched_count=len(blocks),
    )
    status = SubtreeStatus.TRUNCATED if truncated else SubtreeStatus.COMPLETE

    return SubtreeQueryResult(
        status=status,
        anchor_uuid=anchor_uuid,
        page_id=page_id,
        nodes=limited_blocks,
        excerpt_markdown=excerpt,
        detail=None if status == SubtreeStatus.COMPLETE else "subtree limits exceeded",
    )


__all__ = [
    "SubtreeBlock",
    "SubtreeQueryResult",
    "SubtreeStatus",
    "query_subtree_by_block_uuid",
]
