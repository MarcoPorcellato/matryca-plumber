"""Parity and safety tests for shadow recursive CTE subtree reads (#253)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository
from src.shadow.connection import open_shadow_db
from src.shadow.subtree import SubtreeStatus, query_subtree_by_block_uuid
from src.shadow.sync import sync_page_into_connection, sync_page_to_shadow


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _sync(graph: Path, rel: str) -> None:
    sync_page_to_shadow(graph, graph / rel)


def _extract_excerpt(markdown: str) -> str:
    marker = "```markdown\n"
    start = markdown.find(marker)
    if start == -1:
        return markdown
    start += len(marker)
    end = markdown.find("\n```", start)
    if end == -1:
        return markdown[start:]
    return markdown[start:end]


def _normalize_excerpt(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def _parity_query(page: str, block_uuid: str) -> str:
    return json.dumps({"page": page, "block_uuid": block_uuid})


def test_subtree_root_matches_markdown_repository(tmp_path: Path) -> None:
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(
        tmp_path,
        "pages/Demo.md",
        f"- Root line\n  id:: {block_id}\n  - child one\n  - child two\n",
    )
    _sync(tmp_path, "pages/Demo.md")

    query = _parity_query("Demo", block_id)
    expected = _extract_excerpt(read_subtree_markdown(str(tmp_path), query))

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, block_id)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.COMPLETE
    assert _normalize_excerpt(result.excerpt_markdown) == _normalize_excerpt(expected)
    assert [node.block_uuid for node in result.nodes][0] == block_id
    assert "child one" in result.excerpt_markdown


def test_subtree_nested_children_order(tmp_path: Path) -> None:
    root = "11111111-1111-4111-8111-111111111111"
    child_a = "22222222-2222-4222-8222-222222222222"
    child_b = "33333333-3333-4333-8333-333333333333"
    grand = "44444444-4444-4444-8444-444444444444"
    _write_page(
        tmp_path,
        "pages/Nested.md",
        (
            f"- root\n  id:: {root}\n"
            f"  - alpha\n    id:: {child_a}\n"
            f"    - grand\n      id:: {grand}\n"
            f"  - beta\n    id:: {child_b}\n"
        ),
    )
    _sync(tmp_path, "pages/Nested.md")

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, root)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.COMPLETE
    uuids = [node.block_uuid for node in result.nodes]
    assert uuids == [root, child_a, grand, child_b]


def test_subtree_leaf_block(tmp_path: Path) -> None:
    root = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    leaf = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    _write_page(
        tmp_path,
        "pages/Leaf.md",
        f"- root\n  id:: {root}\n  - leaf only\n    id:: {leaf}\n",
    )
    _sync(tmp_path, "pages/Leaf.md")

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, leaf)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.COMPLETE
    assert len(result.nodes) == 1
    assert result.nodes[0].block_uuid == leaf
    assert "leaf only" in result.excerpt_markdown


def test_subtree_not_found(tmp_path: Path) -> None:
    _write_page(tmp_path, "pages/Empty.md", "- solo\n  id:: abcdef01-2345-4678-89ab-cdef01234567\n")
    _sync(tmp_path, "pages/Empty.md")

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, "00000000-0000-4000-8000-000000000001")
    finally:
        conn.close()

    assert result.status == SubtreeStatus.NOT_FOUND
    assert result.nodes == ()


def test_subtree_max_depth_applied_in_query(tmp_path: Path) -> None:
    ids = [
        "10000000-0000-4000-8000-000000000001",
        "20000000-0000-4000-8000-000000000002",
        "30000000-0000-4000-8000-000000000003",
    ]
    _write_page(
        tmp_path,
        "pages/Depth.md",
        (
            f"- d0\n  id:: {ids[0]}\n"
            f"  - d1\n    id:: {ids[1]}\n"
            f"    - d2\n      id:: {ids[2]}\n"
        ),
    )
    _sync(tmp_path, "pages/Depth.md")

    conn = open_shadow_db(tmp_path)
    try:
        shallow = query_subtree_by_block_uuid(conn, ids[0], max_depth=2)
        deep = query_subtree_by_block_uuid(conn, ids[0], max_depth=3)
    finally:
        conn.close()

    assert shallow.status == SubtreeStatus.TRUNCATED
    assert [node.block_uuid for node in shallow.nodes] == ids[:2]
    assert deep.status == SubtreeStatus.COMPLETE
    assert len(deep.nodes) == 3
    assert [node.depth for node in deep.nodes] == [0, 1, 2]


def test_subtree_max_nodes_applied_in_query(tmp_path: Path) -> None:
    lines = ["- root\n  id:: root-uuid-1111-4111-8111-111111111111\n"]
    for index in range(4):
        lines.append(f"  - child {index}\n    id:: {index:08x}-1111-4111-8111-111111111111\n")
    _write_page(tmp_path, "pages/Many.md", "".join(lines))
    _sync(tmp_path, "pages/Many.md")

    conn = open_shadow_db(tmp_path)
    try:
        limited = query_subtree_by_block_uuid(
            conn,
            "root-uuid-1111-4111-8111-111111111111",
            max_nodes=3,
        )
        full = query_subtree_by_block_uuid(
            conn,
            "root-uuid-1111-4111-8111-111111111111",
            max_nodes=10,
        )
    finally:
        conn.close()

    assert limited.status == SubtreeStatus.TRUNCATED
    assert len(limited.nodes) == 3
    assert full.status == SubtreeStatus.COMPLETE
    assert len(full.nodes) == 5


def test_subtree_max_output_bytes_truncates_on_node_boundary(tmp_path: Path) -> None:
    root = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(
        tmp_path,
        "pages/Bytes.md",
        (
            f"- root {'x' * 40}\n  id:: {root}\n"
            "  - child one padding text\n"
            "  - child two padding text\n"
        ),
    )
    _sync(tmp_path, "pages/Bytes.md")

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=80)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.TRUNCATED
    assert "[truncated: output byte limit exceeded]" in result.excerpt_markdown
    assert len(result.nodes) >= 1
    assert "child two" not in result.excerpt_markdown


def test_subtree_detects_cross_page_inconsistency(tmp_path: Path) -> None:
    root = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(tmp_path, "pages/A.md", f"- root\n  id:: {root}\n")
    _write_page(tmp_path, "pages/B.md", "- other\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n")
    _sync(tmp_path, "pages/A.md")
    _sync(tmp_path, "pages/B.md")

    conn = open_shadow_db(tmp_path)
    try:
        anchor_row = conn.execute(
            "SELECT rowid, page_id FROM blocks WHERE block_uuid = ?",
            (root,),
        ).fetchone()
        assert anchor_row is not None
        foreign = conn.execute(
            "SELECT rowid, page_id FROM blocks WHERE block_uuid = ?",
            ("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",),
        ).fetchone()
        assert foreign is not None
        conn.execute(
            "UPDATE blocks SET parent_rowid = ? WHERE rowid = ?",
            (int(anchor_row[0]), int(foreign[0])),
        )
        conn.commit()

        result = query_subtree_by_block_uuid(conn, root)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.INCONSISTENT
    assert result.nodes == ()


def test_subtree_detects_cycle_inconsistency(tmp_path: Path) -> None:
    a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    _write_page(
        tmp_path,
        "pages/Cycle.md",
        f"- a\n  id:: {a}\n  - b\n    id:: {b}\n",
    )
    _sync(tmp_path, "pages/Cycle.md")

    conn = open_shadow_db(tmp_path)
    try:
        rows = {
            uuid: int(
                conn.execute(
                    "SELECT rowid FROM blocks WHERE block_uuid = ?",
                    (uuid,),
                ).fetchone()[0]
            )
            for uuid in (a, b)
        }
        conn.execute(
            "UPDATE blocks SET parent_rowid = ? WHERE block_uuid = ?",
            (rows[b], a),
        )
        conn.commit()

        result = query_subtree_by_block_uuid(conn, a)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.INCONSISTENT


def test_subtree_sort_order_tie_breaks_on_rowid(tmp_path: Path) -> None:
    page = _write_page(
        tmp_path,
        "pages/Tie.md",
        "- root\n  id:: root-uuid-1111-4111-8111-111111111111\n",
    )
    conn = open_shadow_db(tmp_path)
    try:
        sync_page_into_connection(conn, tmp_path, page)
        root_row = conn.execute(
            "SELECT rowid, page_id FROM blocks WHERE block_uuid = ?",
            ("root-uuid-1111-4111-8111-111111111111",),
        ).fetchone()
        assert root_row is not None
        page_id = int(root_row[1])
        conn.executemany(
            """
            INSERT INTO blocks (
                block_uuid, page_id, parent_rowid, sort_order,
                indent_level, content, properties_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'test')
            """,
        [
            (
                "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                page_id,
                int(root_row[0]),
                5,
                1,
                "first by rowid",
                "{}",
            ),
            (
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                page_id,
                int(root_row[0]),
                5,
                1,
                "second by rowid",
                "{}",
            ),
        ],
        )
        conn.commit()

        result = query_subtree_by_block_uuid(
            conn,
            "root-uuid-1111-4111-8111-111111111111",
        )
        child_uuids = [node.block_uuid for node in result.nodes if node.depth == 1]
    finally:
        conn.close()

    assert child_uuids == [
        "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    ]


def test_markdown_repository_fixture_parity(tmp_path: Path) -> None:
    block_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(
        tmp_path,
        "pages/Repo.md",
        f"- Root\n  id:: {block_id}\n  - child\n",
    )
    _sync(tmp_path, "pages/Repo.md")
    query = _parity_query("Repo", block_id)

    repo = MarkdownGraphRepository()
    via_repo = _extract_excerpt(repo.read_subtree_markdown(tmp_path, query))

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, block_id)
    finally:
        conn.close()

    assert result.status == SubtreeStatus.COMPLETE
    assert _normalize_excerpt(result.excerpt_markdown) == _normalize_excerpt(via_repo)


def test_subtree_path_key_is_non_ambiguous(tmp_path: Path) -> None:
    root = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _write_page(
        tmp_path,
        "pages/Path.md",
        f"- root\n  id:: {root}\n  - one\n  - two\n",
    )
    _sync(tmp_path, "pages/Path.md")

    conn = open_shadow_db(tmp_path)
    try:
        result = query_subtree_by_block_uuid(conn, root)
    finally:
        conn.close()

    keys = [node.path_key for node in result.nodes]
    assert len(keys) == len(set(keys))
    assert keys == sorted(keys)
    assert all(re.fullmatch(r"[\d,/]+", key) for key in keys)
