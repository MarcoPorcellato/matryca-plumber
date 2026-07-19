"""v2.0-alpha hardening — Axis 5: CTE subtree (audit probes).

Read-only on ``src/`` — temporary vault fixtures exercise recursive CTE subtree
reads, depth/node/byte limits, cycle detection, ordering, and Markdown parity.
Findings feed tracking issue #261.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from src.agent.dispatch_read_handlers import handle_read_subtree
from src.agent.graph_tool_helpers import read_subtree_markdown
from src.agent.markdown_graph_repository import MarkdownGraphRepository, get_graph_read_port
from src.agent.shadow_graph_repository import ShadowGraphRepository
from src.config import MatrycaWikiConfig
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.connection import open_shadow_db
from src.shadow.runtime_state import mark_bootstrapping, reset_shadow_runtime_state_for_tests
from src.shadow.subtree import SubtreeQueryResult, SubtreeStatus, query_subtree_by_block_uuid
from src.shadow.sync import sync_page_into_connection, sync_page_to_shadow
from src.shadow.writer_lock import shadow_rebuild_lock

_TRUNCATION_MARKER = "[truncated: output byte limit exceeded]"


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _uuid(slot: int) -> str:
    head = f"{slot:08x}"
    return f"{head}-{head[:4]}-4111-8111-{slot:012x}"


def _linear_chain_body(depth: int) -> tuple[str, list[str]]:
    """Single-page outline ``depth`` blocks deep (cumulative indent).

    A trailing sibling under the deepest block ensures the leaf ``id::`` is
    indexed (Logseq parser quirk when a branch ends the page).
    """
    uuids = [_uuid(i + 1) for i in range(depth)]
    sentinel = _uuid(depth + 1000)
    parts: list[str] = []
    for i in range(depth):
        indent = "  " * i
        parts.append(f"{indent}- block-{i}\n{indent}  id:: {uuids[i]}\n")
    deepest = "  " * (depth - 1)
    parts.append(f"{deepest}- chain-tail\n{deepest}  id:: {sentinel}\n")
    return "".join(parts), uuids


def _subtree_query(page: str, block_uuid: str) -> str:
    return json.dumps({"page": page, "block_uuid": block_uuid})


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


def _assert_subtree_snapshot_coherent(
    result: SubtreeQueryResult,
    *,
    anchor_uuid: str,
    allowed_uuids: frozenset[str] | None = None,
) -> None:
    """Result is a valid anchor-rooted tree — never a torn hybrid snapshot."""
    if result.status in {SubtreeStatus.NOT_FOUND, SubtreeStatus.INCONSISTENT}:
        return
    assert result.nodes, "COMPLETE/TRUNCATED must include at least the anchor"
    assert result.nodes[0].block_uuid == anchor_uuid
    seen_rowids: set[int] = set()
    seen_uuids: set[str] = set()
    for index, node in enumerate(result.nodes):
        assert node.rowid not in seen_rowids, "duplicate rowid in subtree result"
        seen_rowids.add(node.rowid)
        assert node.block_uuid not in seen_uuids, "duplicate block_uuid in subtree result"
        seen_uuids.add(node.block_uuid)
        if allowed_uuids is not None:
            assert node.block_uuid in allowed_uuids, "hybrid snapshot: unexpected block_uuid"
        if node.depth == 0:
            assert index == 0
            continue
        assert node.parent_rowid is not None
        parent = next(
            (
                candidate
                for candidate in result.nodes[:index]
                if candidate.rowid == node.parent_rowid
            ),
            None,
        )
        assert parent is not None, "orphan node in subtree result (possible hybrid snapshot)"
        assert parent.depth == node.depth - 1


def _markdown_fingerprint(graph: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        if ".matryca_semantic_cache" in path.parts:
            continue
        digest.update(path.relative_to(graph).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _seed_three_level(graph: Path) -> tuple[str, str, str]:
    """Three-level page; trailing leaf sibling ensures deepest ``id::`` indexes."""
    root, child, leaf = _uuid(1), _uuid(2), _uuid(3)
    leaf_sib = _uuid(4)
    _write_page(
        graph,
        "pages/DepthProbe.md",
        (
            f"- root\n  id:: {root}\n"
            f"  - child\n    id:: {child}\n"
            f"    - leaf\n      id:: {leaf}\n"
            f"    - leaf-tail\n      id:: {leaf_sib}\n"
        ),
    )
    rebuild_shadow_from_graph(graph)
    return root, child, leaf


# --- A5-DEPTH ---


def test_a5_depth_01_linear_chain_complete_within_default_max(tmp_path: Path) -> None:
    """A5-DEPTH-01: 32-block chain returns COMPLETE under default max_depth."""
    graph = _minimal_graph(tmp_path)
    body, uuids = _linear_chain_body(32)
    _write_page(graph, "pages/DeepChain.md", body)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, uuids[0])
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 33
        assert result.nodes[31].block_uuid == uuids[31]
    finally:
        conn.close()


def test_a5_depth_02_leaf_anchor_single_node(tmp_path: Path) -> None:
    """A5-DEPTH-02: leaf anchor returns only itself."""
    graph = _minimal_graph(tmp_path)
    root, _, leaf = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, leaf)
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 1
        assert result.nodes[0].block_uuid == leaf
    finally:
        conn.close()
    _ = root


def test_a5_depth_03_root_anchor_includes_descendants(tmp_path: Path) -> None:
    """A5-DEPTH-03: root anchor returns full depth-first subtree."""
    graph = _minimal_graph(tmp_path)
    root, child, leaf = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        assert result.status is SubtreeStatus.COMPLETE
        uuids = [node.block_uuid for node in result.nodes]
        assert uuids[:3] == [root, child, leaf]
        assert len(uuids) >= 3
    finally:
        conn.close()


@pytest.mark.xfail(
    strict=True,
    reason="P2 #289: max_depth=1 should TRUNCATE when descendants exist (reports COMPLETE)",
)
def test_a5_depth_04_max_depth_one_with_child_truncated(tmp_path: Path) -> None:
    """A5-DEPTH-04: max_depth=1 with descendants → TRUNCATED, anchor only."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_depth=1)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 1
        assert result.nodes[0].block_uuid == root
    finally:
        conn.close()


@pytest.mark.xfail(
    strict=True,
    reason="P2 #289: clamped max_depth=0 behaves like 1 but should TRUNCATE with descendants",
)
def test_a5_depth_05_max_depth_zero_clamped_truncated(tmp_path: Path) -> None:
    """A5-DEPTH-05: max_depth=0 clamps to 1; descendants → TRUNCATED."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_depth=0)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 1
    finally:
        conn.close()


def test_a5_depth_06_exact_depth_limit_on_chain(tmp_path: Path) -> None:
    """A5-DEPTH-06: max_depth matching chain length → COMPLETE."""
    graph = _minimal_graph(tmp_path)
    body, uuids = _linear_chain_body(5)
    _write_page(graph, "pages/Exact.md", body)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, uuids[0], max_depth=5)
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 6
    finally:
        conn.close()


def test_a5_depth_07_depth_limit_plus_one_truncated(tmp_path: Path) -> None:
    """A5-DEPTH-07: chain longer than max_depth → TRUNCATED."""
    graph = _minimal_graph(tmp_path)
    body, uuids = _linear_chain_body(6)
    _write_page(graph, "pages/PlusOne.md", body)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, uuids[0], max_depth=5)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 5
    finally:
        conn.close()


def test_a5_depth_08_default_cap_truncates_beyond_64_levels(tmp_path: Path) -> None:
    """A5-DEPTH-08: default max_depth=64 truncates a 66-block chain."""
    graph = _minimal_graph(tmp_path)
    body, uuids = _linear_chain_body(66)
    _write_page(graph, "pages/DeepDefault.md", body)
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, uuids[0])
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 64
    finally:
        conn.close()


@pytest.mark.xfail(
    strict=True,
    reason="P2 #289: clamped max_depth=-5 behaves like 1 but should TRUNCATE with descendants",
)
def test_a5_depth_09_negative_max_depth_clamped(tmp_path: Path) -> None:
    """A5-DEPTH-09: negative max_depth clamps to 1; descendants → TRUNCATED."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_depth=-5)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 1
        assert result.nodes[0].block_uuid == root
    finally:
        conn.close()


# --- A5-ORDER ---


def test_a5_order_01_siblings_follow_sort_order(tmp_path: Path) -> None:
    """A5-ORDER-01: siblings ordered by sort_order ascending."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    children = [_uuid(2), _uuid(3), _uuid(4)]
    _write_page(
        graph,
        "pages/Siblings.md",
        (
            f"- root\n  id:: {root}\n"
            f"  - first\n    id:: {children[0]}\n"
            f"  - second\n    id:: {children[1]}\n"
            f"  - third\n    id:: {children[2]}\n"
        ),
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        child_uuids = [node.block_uuid for node in result.nodes if node.depth == 1]
        assert child_uuids == children
    finally:
        conn.close()


def test_a5_order_02_depth_first_preorder(tmp_path: Path) -> None:
    """A5-ORDER-02: nested subtree is depth-first pre-order."""
    graph = _minimal_graph(tmp_path)
    root, child, leaf = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, child)
        uuids = [node.block_uuid for node in result.nodes]
        assert uuids[0] == child
        assert leaf in uuids
        assert [node.depth for node in result.nodes] == [0, 1, 1]
    finally:
        conn.close()
    _ = root


def test_a5_order_03_stable_across_connections(tmp_path: Path) -> None:
    """A5-ORDER-03: ordering stable across separate connections."""
    graph = _minimal_graph(tmp_path)
    root, child, leaf = _seed_three_level(graph)

    def _uuids() -> list[str]:
        conn = open_shadow_db(graph)
        try:
            result = query_subtree_by_block_uuid(conn, child)
            return [node.block_uuid for node in result.nodes]
        finally:
            conn.close()

    first = _uuids()
    second = _uuids()
    assert first == second
    assert first[0] == child and leaf in first
    _ = root


def test_a5_order_04_full_rebuild_matches_incremental(tmp_path: Path) -> None:
    """A5-ORDER-04: incremental update preserves subtree order vs full rebuild."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    child = _uuid(2)
    page = _write_page(
        graph,
        "pages/Sched.md",
        f"- root\n  id:: {root}\n  - first\n    id:: {child}\n",
    )
    rebuild_shadow_from_graph(graph)
    page.write_text(
        (
            f"- root\n  id:: {root}\n"
            f"  - first\n    id:: {child}\n"
            f"  - second\n    id:: {_uuid(3)}\n"
            f"  - third\n    id:: {_uuid(4)}\n"
        ),
        encoding="utf-8",
    )
    sync_page_to_shadow(graph, page)

    incr_conn = open_shadow_db(graph)
    try:
        incr_order = [n.block_uuid for n in query_subtree_by_block_uuid(incr_conn, root).nodes]
    finally:
        incr_conn.close()

    rebuild_shadow_from_graph(graph)
    full_conn = open_shadow_db(graph)
    try:
        full_order = [n.block_uuid for n in query_subtree_by_block_uuid(full_conn, root).nodes]
    finally:
        full_conn.close()

    assert incr_order == full_order


# --- A5-NODES ---


def test_a5_nodes_01_max_nodes_one_returns_anchor_only(tmp_path: Path) -> None:
    """A5-NODES-01: max_nodes=1 returns anchor only when descendants exist."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_nodes=1)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 1
        assert result.nodes[0].block_uuid == root
    finally:
        conn.close()


def test_a5_nodes_02_exact_node_limit_complete(tmp_path: Path) -> None:
    """A5-NODES-02: max_nodes equal to subtree size → COMPLETE."""
    graph = _minimal_graph(tmp_path)
    root, child, leaf = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_nodes=4)
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 4
    finally:
        conn.close()
    _ = (child, leaf)


def test_a5_nodes_03_node_limit_plus_one_truncated(tmp_path: Path) -> None:
    """A5-NODES-03: max_nodes below subtree size → TRUNCATED."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_nodes=2)
        assert result.status is SubtreeStatus.TRUNCATED
        assert len(result.nodes) == 2
    finally:
        conn.close()


def test_a5_nodes_04_wide_subtree_many_siblings(tmp_path: Path) -> None:
    """A5-NODES-04: wide sibling set returns all children in order."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    lines = [f"- root\n  id:: {root}\n"]
    child_ids = []
    for index in range(12):
        child_ids.append(_uuid(index + 2))
        lines.append(f"  - child {index}\n    id:: {child_ids[-1]}\n")
    _write_page(graph, "pages/Wide.md", "".join(lines))
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 13
        assert [n.block_uuid for n in result.nodes[1:]] == child_ids
    finally:
        conn.close()


def test_a5_nodes_05_truncation_status_when_node_limited(tmp_path: Path) -> None:
    """A5-NODES-05: node-limit truncation sets TRUNCATED status."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_nodes=1)
        assert result.status is SubtreeStatus.TRUNCATED
    finally:
        conn.close()


def test_a5_nodes_06_no_duplicate_nodes_in_result(tmp_path: Path) -> None:
    """A5-NODES-06: result nodes are unique by block_uuid."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        uuids = [node.block_uuid for node in result.nodes]
        assert len(uuids) == len(set(uuids))
    finally:
        conn.close()


# --- A5-BYTES ---


def test_a5_bytes_01_under_limit_complete(tmp_path: Path) -> None:
    """A5-BYTES-01: generous byte limit → COMPLETE excerpt."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=50_000)
        assert result.status is SubtreeStatus.COMPLETE
        assert _TRUNCATION_MARKER not in result.excerpt_markdown
    finally:
        conn.close()


def test_a5_bytes_02_over_limit_truncates_on_block_boundary(tmp_path: Path) -> None:
    """A5-BYTES-02: low byte limit truncates without splitting a block mid-line."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(
        graph,
        "pages/Bytes.md",
        (f"- root {'x' * 40}\n  id:: {root}\n  - child one padding\n  - child two padding\n"),
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=80)
        assert result.status is SubtreeStatus.TRUNCATED
        assert _TRUNCATION_MARKER in result.excerpt_markdown
        assert "child two" not in result.excerpt_markdown
    finally:
        conn.close()


def test_a5_bytes_03_utf8_multibyte_valid_after_truncation(tmp_path: Path) -> None:
    """A5-BYTES-03: excerpt remains valid UTF-8 after byte truncation."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(
        graph,
        "pages/Unicode.md",
        f"- {'é' * 12}\n  id:: {root}\n  - {'€' * 8}\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=40)
        encoded = result.excerpt_markdown.encode("utf-8")
        decoded = encoded.decode("utf-8")
        assert decoded == result.excerpt_markdown
    finally:
        conn.close()


def test_a5_bytes_04_emoji_codepoints_not_split(tmp_path: Path) -> None:
    """A5-BYTES-04: emoji blocks are kept whole (no invalid UTF-8)."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(graph, "pages/Emoji.md", f"- {'🎉' * 6}\n  id:: {root}\n  - tail\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=30)
        result.excerpt_markdown.encode("utf-8").decode("utf-8")
        assert "🎉" in result.excerpt_markdown or _TRUNCATION_MARKER in result.excerpt_markdown
    finally:
        conn.close()


def test_a5_bytes_05_deterministic_excerpt_across_calls(tmp_path: Path) -> None:
    """A5-BYTES-05: byte-limited excerpt is deterministic."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        first = query_subtree_by_block_uuid(conn, root, max_output_bytes=60).excerpt_markdown
        second = query_subtree_by_block_uuid(conn, root, max_output_bytes=60).excerpt_markdown
        assert first == second
    finally:
        conn.close()


def test_a5_bytes_06_truncation_notice_documented_soft_budget(tmp_path: Path) -> None:
    """A5-BYTES-06: truncation notice may extend past max_output_bytes (block-boundary contract)."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(graph, "pages/Soft.md", f"- {'x' * 20}\n  id:: {root}\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        limit = 25
        result = query_subtree_by_block_uuid(conn, root, max_output_bytes=limit)
        assert result.status is SubtreeStatus.TRUNCATED
        assert _TRUNCATION_MARKER in result.excerpt_markdown
        # Block-boundary policy: first block may exceed limit; marker appended after.
        assert len(result.excerpt_markdown.encode("utf-8")) >= limit
    finally:
        conn.close()


# --- A5-INTEGRITY ---


def test_a5_integrity_01_missing_anchor_uuid(tmp_path: Path) -> None:
    """A5-INTEGRITY-01: unknown UUID → NOT_FOUND."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, _uuid(99))
        assert result.status is SubtreeStatus.NOT_FOUND
        assert result.nodes == ()
    finally:
        conn.close()
    _ = root


def test_a5_integrity_02_empty_anchor_uuid(tmp_path: Path) -> None:
    """A5-INTEGRITY-02: empty UUID → NOT_FOUND."""
    graph = _minimal_graph(tmp_path)
    _seed_three_level(graph)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, "   ")
        assert result.status is SubtreeStatus.NOT_FOUND
    finally:
        conn.close()


def test_a5_integrity_03_cross_page_child_inconsistent(tmp_path: Path) -> None:
    """A5-INTEGRITY-03: cross-page parent edge → INCONSISTENT."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    foreign = _uuid(2)
    _write_page(graph, "pages/A.md", f"- root\n  id:: {root}\n")
    _write_page(graph, "pages/B.md", f"- other\n  id:: {foreign}\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        anchor_row = conn.execute(
            "SELECT rowid FROM blocks WHERE block_uuid = ?",
            (root,),
        ).fetchone()
        foreign_row = conn.execute(
            "SELECT rowid FROM blocks WHERE block_uuid = ?",
            (foreign,),
        ).fetchone()
        assert anchor_row and foreign_row
        conn.execute(
            "UPDATE blocks SET parent_rowid = ? WHERE rowid = ?",
            (int(anchor_row[0]), int(foreign_row[0])),
        )
        conn.commit()
        result = query_subtree_by_block_uuid(conn, root)
        assert result.status is SubtreeStatus.INCONSISTENT
        assert result.nodes == ()
    finally:
        conn.close()


def test_a5_integrity_04_parent_cycle_inconsistent(tmp_path: Path) -> None:
    """A5-INTEGRITY-04: parent_rowid cycle → INCONSISTENT."""
    graph = _minimal_graph(tmp_path)
    a, b = _uuid(1), _uuid(2)
    _write_page(graph, "pages/Cycle.md", f"- a\n  id:: {a}\n  - b\n    id:: {b}\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        rows = {
            uuid: int(
                conn.execute("SELECT rowid FROM blocks WHERE block_uuid = ?", (uuid,)).fetchone()[0]
            )
            for uuid in (a, b)
        }
        conn.execute("UPDATE blocks SET parent_rowid = ? WHERE block_uuid = ?", (rows[b], a))
        conn.commit()
        result = query_subtree_by_block_uuid(conn, a)
        assert result.status is SubtreeStatus.INCONSISTENT
    finally:
        conn.close()


def test_a5_integrity_05_self_cycle_inconsistent(tmp_path: Path) -> None:
    """A5-INTEGRITY-05: block parent_rowid points to itself → INCONSISTENT."""
    graph = _minimal_graph(tmp_path)
    solo = _uuid(1)
    _write_page(graph, "pages/Solo.md", f"- solo\n  id:: {solo}\n")
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        rowid = int(
            conn.execute("SELECT rowid FROM blocks WHERE block_uuid = ?", (solo,)).fetchone()[0]
        )
        conn.execute("UPDATE blocks SET parent_rowid = ? WHERE rowid = ?", (rowid, rowid))
        conn.commit()
        result = query_subtree_by_block_uuid(conn, solo)
        assert result.status is SubtreeStatus.INCONSISTENT
    finally:
        conn.close()


def test_a5_integrity_06_orphan_parent_rowid_excluded_from_walk(tmp_path: Path) -> None:
    """A5-INTEGRITY-06: dangling parent_rowid on anchor — CTE still returns anchor only."""
    graph = _minimal_graph(tmp_path)
    solo = _uuid(1)
    tail = _uuid(2)
    _write_page(
        graph,
        "pages/Orphan.md",
        f"- solo\n  id:: {solo}\n  - tail\n    id:: {tail}\n",
    )
    rebuild_shadow_from_graph(graph)
    conn = open_shadow_db(graph)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("UPDATE blocks SET parent_rowid = ? WHERE block_uuid = ?", (999_999, solo))
        conn.commit()
        result = query_subtree_by_block_uuid(conn, solo)
        assert result.status is SubtreeStatus.COMPLETE
        assert len(result.nodes) == 2
        assert {node.block_uuid for node in result.nodes} == {solo, tail}
    finally:
        conn.close()


# --- A5-PARITY ---


def test_a5_parity_01_shadow_excerpt_matches_markdown_repository(tmp_path: Path) -> None:
    """A5-PARITY-01: shadow excerpt matches MarkdownGraphRepository for same anchor."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(
        graph,
        "pages/Parity.md",
        f"- Root\n  id:: {root}\n  - child\n    id:: {_uuid(2)}\n",
    )
    rebuild_shadow_from_graph(graph)
    query = _subtree_query("Parity", root)
    repo = MarkdownGraphRepository()
    expected = _normalize_excerpt(_extract_excerpt(repo.read_subtree_markdown(graph, query)))
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        assert result.status is SubtreeStatus.COMPLETE
        assert _normalize_excerpt(result.excerpt_markdown) == expected
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_a5_parity_02_not_found_no_markdown_fallback(tmp_path: Path) -> None:
    """A5-PARITY-02: NOT_FOUND → error envelope, no Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    missing = _uuid(50)
    query = _subtree_query("DepthProbe", missing)
    with patch.object(MarkdownGraphRepository, "read_subtree_markdown") as markdown_read:
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)
    markdown_read.assert_not_called()
    assert "not found" in out.lower()


def test_a5_parity_03_inconsistent_shadow_falls_back_to_markdown(tmp_path: Path) -> None:
    """A5-PARITY-03: INCONSISTENT shadow → Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    query = _subtree_query("DepthProbe", root)
    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        return_value=type(
            "R",
            (),
            {
                "status": SubtreeStatus.INCONSISTENT,
                "excerpt_markdown": "",
                "nodes": (),
            },
        )(),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)
    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


def test_a5_parity_04_sqlite_error_falls_back_to_markdown(tmp_path: Path) -> None:
    """A5-PARITY-04: SQLite failure → Markdown fallback."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    query = _subtree_query("DepthProbe", root)
    with patch(
        "src.agent.shadow_graph_repository.query_subtree_by_block_uuid",
        side_effect=sqlite3.OperationalError("database is locked"),
    ):
        out = ShadowGraphRepository().read_subtree_markdown(graph, query)
    expected = read_subtree_markdown(str(graph), query)
    assert _extract_excerpt(out).rstrip("\n") == _extract_excerpt(expected).rstrip("\n")


@pytest.mark.asyncio
async def test_a5_parity_05_handler_matches_port(tmp_path: Path) -> None:
    """A5-PARITY-05: MCP/CLI handler matches GraphReadPort envelope."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    query = _subtree_query("DepthProbe", root)
    port = get_graph_read_port(graph)
    via_port = port.read_subtree_markdown(graph, query)
    via_handler = await handle_read_subtree(MatrycaWikiConfig(), str(graph), query)
    assert _extract_excerpt(via_port).rstrip("\n") == _extract_excerpt(via_handler).rstrip("\n")


def test_a5_parity_06_flag_false_uses_markdown_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A5-PARITY-06: flag off → Markdown subtree port (no shadow.sqlite read)."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(graph, "pages/FlagOff.md", f"- needle\n  id:: {root}\n")
    monkeypatch.delenv("MATRYCA_SHADOW_DB_ENABLED", raising=False)
    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)
    query = _subtree_query("FlagOff", root)
    out = port.read_subtree_markdown(graph, query)
    assert "needle" in _extract_excerpt(out)


# --- A5-CONCURRENCY ---


def test_a5_concurrency_01_bootstrapping_uses_markdown_port(tmp_path: Path) -> None:
    """A5-CONCURRENCY-01: bootstrapping health → Markdown port, not partial shadow."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    _write_page(graph, "pages/Boot.md", f"- boot needle\n  id:: {root}\n")
    rebuild_shadow_from_graph(graph)
    mark_bootstrapping(graph)
    port = get_graph_read_port(graph)
    assert isinstance(port, MarkdownGraphRepository)
    query = _subtree_query("Boot", root)
    out = port.read_subtree_markdown(graph, query)
    assert "boot needle" in _extract_excerpt(out)


def test_a5_concurrency_02_incremental_sync_then_query_consistent(tmp_path: Path) -> None:
    """A5-CONCURRENCY-02 (sequential): post-incremental sync query sees new blocks."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    page = _write_page(graph, "pages/Live.md", f"- root\n  id:: {root}\n")
    rebuild_shadow_from_graph(graph)
    new_child = _uuid(2)
    page.write_text(
        f"- root\n  id:: {root}\n  - added\n    id:: {new_child}\n",
        encoding="utf-8",
    )
    sync_page_to_shadow(graph, page)
    conn = open_shadow_db(graph)
    try:
        result = query_subtree_by_block_uuid(conn, root)
        assert result.status is SubtreeStatus.COMPLETE
        assert new_child in {node.block_uuid for node in result.nodes}
    finally:
        conn.close()


def test_a5_concurrency_03_shadow_reads_do_not_mutate_markdown(tmp_path: Path) -> None:
    """A5-CONCURRENCY-03: subtree queries leave vault Markdown bytes unchanged."""
    graph = _minimal_graph(tmp_path)
    root, _, _ = _seed_three_level(graph)
    before = _markdown_fingerprint(graph)
    conn = open_shadow_db(graph)
    try:
        for _ in range(3):
            query_subtree_by_block_uuid(conn, root, max_nodes=2, max_output_bytes=40)
    finally:
        conn.close()
    assert _markdown_fingerprint(graph) == before


def test_a5_concurrency_04_reader_transaction_isolates_incremental_sync(tmp_path: Path) -> None:
    """A5-CONCURRENCY-04: open reader txn sees pre-sync snapshot; fresh conn sees post-sync."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    child_old = _uuid(2)
    child_new = _uuid(3)
    old_tail = _uuid(4)
    new_tail = _uuid(5)
    page = _write_page(
        graph,
        "pages/Live.md",
        (
            f"- root\n  id:: {root}\n"
            f"  - old\n    id:: {child_old}\n"
            f"  - old-tail\n    id:: {old_tail}\n"
        ),
    )
    rebuild_shadow_from_graph(graph)
    page.write_text(
        (
            f"- root\n  id:: {root}\n"
            f"  - old\n    id:: {child_old}\n"
            f"  - added\n    id:: {child_new}\n"
            f"  - added-tail\n    id:: {new_tail}\n"
        ),
        encoding="utf-8",
    )

    old_uuids = frozenset({root, child_old, old_tail})
    new_uuids = frozenset({root, child_old, child_new, new_tail})

    reader = open_shadow_db(graph)
    reader.execute("BEGIN DEFERRED")
    try:
        baseline = query_subtree_by_block_uuid(reader, root)
        _assert_subtree_snapshot_coherent(baseline, anchor_uuid=root, allowed_uuids=old_uuids)
        assert child_new not in {node.block_uuid for node in baseline.nodes}

        sync_errors: list[BaseException] = []

        def _run_sync() -> None:
            try:
                sync_page_to_shadow(graph, page)
            except BaseException as exc:  # noqa: BLE001
                sync_errors.append(exc)

        worker = threading.Thread(target=_run_sync)
        worker.start()
        worker.join(timeout=10)
        assert not sync_errors

        during = query_subtree_by_block_uuid(reader, root)
        _assert_subtree_snapshot_coherent(during, anchor_uuid=root, allowed_uuids=old_uuids)
        assert frozenset(node.block_uuid for node in during.nodes) == old_uuids
        assert child_new not in {node.block_uuid for node in during.nodes}
        assert [node.block_uuid for node in during.nodes] == [
            node.block_uuid for node in baseline.nodes
        ]
    finally:
        reader.close()

    fresh = open_shadow_db(graph)
    try:
        updated = query_subtree_by_block_uuid(fresh, root)
        _assert_subtree_snapshot_coherent(updated, anchor_uuid=root, allowed_uuids=new_uuids)
        assert child_new in {node.block_uuid for node in updated.nodes}
    finally:
        fresh.close()


def test_a5_concurrency_05_query_during_uncommitted_rebuild_never_hybrid(tmp_path: Path) -> None:
    """A5-CONCURRENCY-05: query during rebuild writer window sees committed snapshot only."""
    graph = _minimal_graph(tmp_path)
    root = _uuid(1)
    child_a = _uuid(2)
    child_b = _uuid(3)
    page = _write_page(
        graph,
        "pages/Rebuild.md",
        (f"- root\n  id:: {root}\n  - alpha\n    id:: {child_a}\n  - beta\n    id:: {child_b}\n"),
    )
    rebuild_shadow_from_graph(graph)

    child_g = _uuid(10)
    child_d = _uuid(11)
    page.write_text(
        (f"- root\n  id:: {root}\n  - gamma\n    id:: {child_g}\n  - delta\n    id:: {child_d}\n"),
        encoding="utf-8",
    )

    old_uuids = frozenset({root, child_a, child_b})
    new_uuids = frozenset({root, child_g, child_d})

    writer_ready = threading.Event()
    reader_opened = threading.Event()
    query_done = threading.Event()
    writer_errors: list[BaseException] = []
    query_errors: list[BaseException] = []
    query_results: list[SubtreeQueryResult] = []

    def _hold_rebuild_window() -> None:
        try:
            assert reader_opened.wait(timeout=5)
            with shadow_rebuild_lock(graph):
                conn = open_shadow_db(graph)
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("DELETE FROM pages")
                    writer_ready.set()
                    assert query_done.wait(timeout=5)
                    sync_page_into_connection(conn, graph, page)
                    conn.commit()
                except BaseException as exc:  # noqa: BLE001
                    writer_errors.append(exc)
                    conn.rollback()
                finally:
                    conn.close()
        except BaseException as exc:  # noqa: BLE001
            writer_errors.append(exc)

    def _query_during_window() -> None:
        conn = open_shadow_db(graph)
        reader_opened.set()
        try:
            assert writer_ready.wait(timeout=5)
            result = query_subtree_by_block_uuid(conn, root)
            query_results.append(result)
        except BaseException as exc:  # noqa: BLE001
            query_errors.append(exc)
        finally:
            conn.close()
            query_done.set()

    reader = threading.Thread(target=_query_during_window)
    writer = threading.Thread(target=_hold_rebuild_window)
    reader.start()
    writer.start()
    writer.join(timeout=10)
    reader.join(timeout=10)
    assert not writer_errors
    assert not query_errors
    assert len(query_results) == 1

    during = query_results[0]
    _assert_subtree_snapshot_coherent(during, anchor_uuid=root, allowed_uuids=old_uuids)
    assert frozenset(node.block_uuid for node in during.nodes) == old_uuids

    after = open_shadow_db(graph)
    try:
        committed = query_subtree_by_block_uuid(after, root)
        _assert_subtree_snapshot_coherent(committed, anchor_uuid=root, allowed_uuids=new_uuids)
        assert frozenset(node.block_uuid for node in committed.nodes) == new_uuids
    finally:
        after.close()


def test_a5_concurrency_06_reader_sees_committed_generation_during_writer_lock(
    tmp_path: Path,
) -> None:
    """A5-CONCURRENCY-06: reader opened before ``BEGIN IMMEDIATE`` sees committed subtree."""
    graph = _minimal_graph(tmp_path)
    root, child, leaf = _seed_three_level(graph)
    reader = open_shadow_db(graph)
    holder = open_shadow_db(graph)
    holder.execute("BEGIN IMMEDIATE")
    try:
        result = query_subtree_by_block_uuid(reader, root)
        _assert_subtree_snapshot_coherent(result, anchor_uuid=root)
        assert result.status is SubtreeStatus.COMPLETE
        assert leaf in {node.block_uuid for node in result.nodes}
    finally:
        holder.rollback()
        holder.close()
        reader.close()
