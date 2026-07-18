"""v2.0-alpha hardening — Axis 2: Shadow ↔ Markdown parity (audit probes).

Read-only on ``src/`` — temporary vault fixtures compare full rebuild vs
incremental/watcher paths. Findings feed tracking issue #261.

Workflow: minimal reproducer → ``xfail(strict=True)`` only after confirmation
→ child issue → surgical fix PR → remove xfail.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from src.graph.page_path import page_title_to_filename
from src.shadow.bootstrap import (
    handle_shadow_watchdog_change,
    rebuild_shadow_from_graph,
    reset_shadow_bootstrap_checked_for_tests,
)
from src.shadow.connection import open_shadow_db, shadow_db_path
from src.shadow.errors import ShadowSyncError
from src.shadow.runtime_state import (
    mark_bootstrapping,
    reset_shadow_runtime_state_for_tests,
)
from src.shadow.sync import reset_shadow_sync_bridge_for_tests, sync_page_to_shadow


@pytest.fixture(autouse=True)
def _shadow_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATRYCA_SHADOW_DB_ENABLED", "true")
    monkeypatch.setenv("MATRYCA_SHADOW_DB_BUSY_TIMEOUT_MS", "200")
    reset_shadow_runtime_state_for_tests()
    reset_shadow_bootstrap_checked_for_tests()
    reset_shadow_sync_bridge_for_tests()


@dataclass(frozen=True)
class BlockSnap:
    block_uuid: str
    parent_uuid: str | None
    sort_order: int
    indent_level: int
    content: str
    properties_json: str


@dataclass(frozen=True)
class PageSnap:
    title: str
    file_path: str
    is_journal: int
    properties_json: str
    blocks: tuple[BlockSnap, ...]


@dataclass(frozen=True)
class IncrementalOp:
    """Single incremental shadow mutation step (Markdown + sync/watcher)."""

    kind: Literal[
        "write_sync",
        "delete_sync",
        "watchdog_delete",
        "watchdog_modified",
        "rename_sync",
    ]
    rel: str
    body: str = ""
    dest_rel: str | None = None


def _minimal_graph(tmp_path: Path) -> Path:
    graph = tmp_path / "vault"
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    return graph


def _write_page(graph: Path, rel: str, body: str) -> Path:
    target = graph / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def _remove_shadow_db(graph: Path) -> None:
    db = shadow_db_path(graph)
    if db.is_file():
        db.unlink()
    reset_shadow_bootstrap_checked_for_tests()


def _rowid_to_uuid(conn: sqlite3.Connection, rowid: int | None) -> str | None:
    if rowid is None:
        return None
    row = conn.execute(
        "SELECT block_uuid FROM blocks WHERE rowid = ?",
        (rowid,),
    ).fetchone()
    return str(row[0]) if row else None


def capture_shadow_snapshot(graph: Path) -> tuple[PageSnap, ...]:
    """Structural snapshot: pages, blocks, parentage, order (no volatile meta)."""
    conn = open_shadow_db(graph)
    try:
        pages: list[PageSnap] = []
        page_rows = conn.execute(
            """
            SELECT page_id, title, file_path, is_journal, properties_json
            FROM pages
            ORDER BY file_path
            """
        ).fetchall()
        for page_id, title, file_path, is_journal, properties_json in page_rows:
            block_rows = conn.execute(
                """
                SELECT block_uuid, parent_rowid, sort_order, indent_level,
                       content, properties_json
                FROM blocks
                WHERE page_id = ?
                ORDER BY sort_order, rowid
                """,
                (page_id,),
            ).fetchall()
            blocks = tuple(
                BlockSnap(
                    block_uuid=str(block_uuid),
                    parent_uuid=_rowid_to_uuid(conn, parent_rowid),
                    sort_order=int(sort_order),
                    indent_level=int(indent_level),
                    content=str(content),
                    properties_json=str(properties_json),
                )
                for (
                    block_uuid,
                    parent_rowid,
                    sort_order,
                    indent_level,
                    content,
                    properties_json,
                ) in block_rows
            )
            pages.append(
                PageSnap(
                    title=str(title),
                    file_path=str(file_path),
                    is_journal=int(is_journal),
                    properties_json=str(properties_json),
                    blocks=blocks,
                )
            )
        return tuple(pages)
    finally:
        conn.close()


def _markdown_fingerprint(graph: Path) -> dict[str, str]:
    return {
        path.relative_to(graph).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(graph.rglob("*.md"))
    }


def _apply_markdown_ops(graph: Path, ops: Sequence[IncrementalOp]) -> None:
    """Apply filesystem mutations only (no shadow sync)."""
    for op in ops:
        path = graph / op.rel
        if op.kind in ("write_sync", "watchdog_modified"):
            _write_page(graph, op.rel, op.body)
        elif op.kind in ("delete_sync", "watchdog_delete"):
            if path.is_file():
                path.unlink()
        elif op.kind == "rename_sync":
            if op.dest_rel is None:
                msg = "rename_sync requires dest_rel"
                raise ValueError(msg)
            dest = graph / op.dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.rename(dest)
        else:
            msg = f"unknown op kind: {op.kind}"
            raise ValueError(msg)


def _apply_incremental_ops(graph: Path, ops: Sequence[IncrementalOp]) -> None:
    for op in ops:
        path = graph / op.rel
        if op.kind == "write_sync":
            _write_page(graph, op.rel, op.body)
            sync_page_to_shadow(graph, path)
        elif op.kind == "delete_sync":
            if path.is_file():
                path.unlink()
            sync_page_to_shadow(graph, path)
        elif op.kind == "watchdog_delete":
            if path.is_file():
                path.unlink()
            handle_shadow_watchdog_change(graph, path, "deleted")
        elif op.kind == "watchdog_modified":
            _write_page(graph, op.rel, op.body)
            handle_shadow_watchdog_change(graph, path, "modified")
        elif op.kind == "rename_sync":
            if op.dest_rel is None:
                msg = "rename_sync requires dest_rel"
                raise ValueError(msg)
            dest = graph / op.dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            path.rename(dest)
            sync_page_to_shadow(graph, dest)
            sync_page_to_shadow(graph, path)
        else:
            msg = f"unknown op kind: {op.kind}"
            raise ValueError(msg)


def assert_full_rebuild_matches_incremental(
    graph: Path,
    *,
    seed_files: dict[str, str],
    ops: Sequence[IncrementalOp],
) -> None:
    """Compare a full rebuild on final Markdown state vs incremental op sequence."""
    full_graph = graph.parent / f"{graph.name}-full"
    incr_graph = graph.parent / f"{graph.name}-incr"
    if full_graph.exists():
        shutil.rmtree(full_graph)
    if incr_graph.exists():
        shutil.rmtree(incr_graph)
    shutil.copytree(graph, full_graph)
    shutil.copytree(graph, incr_graph)

    for rel, body in seed_files.items():
        _write_page(full_graph, rel, body)
        _write_page(incr_graph, rel, body)

    _apply_markdown_ops(full_graph, ops)
    _remove_shadow_db(full_graph)
    rebuild_shadow_from_graph(full_graph)
    full_snap = capture_shadow_snapshot(full_graph)

    _remove_shadow_db(incr_graph)
    _apply_incremental_ops(incr_graph, ops)
    incr_snap = capture_shadow_snapshot(incr_graph)

    assert full_snap == incr_snap


def test_a2_parity_01_bootstrap_pages_blocks_parentage_order(tmp_path: Path) -> None:
    """A2-PARITY-01: full bootstrap preserves pages, blocks, parentage, and order."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Root.md",
        "- root\n"
        "  id:: 11111111-1111-4111-8111-111111111111\n"
        "  - child a\n"
        "    id:: 22222222-2222-4222-8222-222222222222\n"
        "  - child b\n"
        "    id:: 33333333-3333-4333-8333-333333333333\n",
    )
    _write_page(
        graph,
        "pages/Sibling.md",
        "- solo\n  id:: 44444444-4444-4444-8444-444444444444\n",
    )
    rebuild_shadow_from_graph(graph)

    snap = capture_shadow_snapshot(graph)
    assert len(snap) == 2
    root = next(page for page in snap if page.title == "Root")
    assert len(root.blocks) == 3
    root_block = next(block for block in root.blocks if block.block_uuid.endswith("1111"))
    child_a = next(block for block in root.blocks if block.block_uuid.endswith("2222"))
    child_b = next(block for block in root.blocks if block.block_uuid.endswith("3333"))
    assert root_block.parent_uuid is None
    assert child_a.parent_uuid == root_block.block_uuid
    assert child_b.parent_uuid == root_block.block_uuid
    assert child_a.sort_order < child_b.sort_order


def test_a2_parity_02_full_rebuild_matches_incremental_create_sequence(tmp_path: Path) -> None:
    """A2-PARITY-02: incremental creates match an equivalent full rebuild."""
    graph = _minimal_graph(tmp_path)
    seed: dict[str, str] = {}
    ops = [
        IncrementalOp(
            "write_sync",
            "pages/Alpha.md",
            "- alpha\n  id:: aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa\n",
        ),
        IncrementalOp(
            "write_sync",
            "pages/Beta.md",
            "- beta\n  id:: bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb\n",
        ),
        IncrementalOp(
            "write_sync",
            "journals/2026_07_18.md",
            "- journal\n  id:: cccccccc-cccc-4ccc-8ccc-cccccccccccc\n",
        ),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files=seed, ops=ops)


def test_a2_parity_03_full_rebuild_matches_incremental_mutations(tmp_path: Path) -> None:
    """A2-PARITY-03: modify/delete/recreate sequence matches full rebuild."""
    graph = _minimal_graph(tmp_path)
    ops = [
        IncrementalOp(
            "write_sync",
            "pages/Lifecycle.md",
            "- v1\n  id:: dddddddd-dddd-4ddd-8ddd-dddddddddddd\n",
        ),
        IncrementalOp(
            "write_sync",
            "pages/Lifecycle.md",
            "- v2\n  id:: eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee\n",
        ),
        IncrementalOp("delete_sync", "pages/Lifecycle.md"),
        IncrementalOp(
            "write_sync",
            "pages/Lifecycle.md",
            "- v3\n  id:: ffffffff-ffff-4fff-8fff-ffffffffffff\n",
        ),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_parity_04_shadow_never_writes_markdown(tmp_path: Path) -> None:
    """A2-PARITY-04: shadow sync/rebuild must not mutate Markdown on disk."""
    graph = _minimal_graph(tmp_path)
    page = _write_page(
        graph,
        "pages/ReadOnly.md",
        "- readonly\n  id:: 10101010-1010-4010-8010-101010101010\n",
    )
    before = _markdown_fingerprint(graph)
    rebuild_shadow_from_graph(graph)
    sync_page_to_shadow(graph, page)
    handle_shadow_watchdog_change(graph, page, "modified")
    assert _markdown_fingerprint(graph) == before


def test_a2_watch_01_watchdog_crud_matches_incremental_sync(tmp_path: Path) -> None:
    """A2-WATCH-01: watchdog create/modify/delete parity with direct sync."""
    graph = _minimal_graph(tmp_path)
    ops = [
        IncrementalOp(
            "watchdog_modified",
            "pages/Watch.md",
            "- created\n  id:: 30303030-3030-4030-8030-303030303030\n",
        ),
        IncrementalOp(
            "watchdog_modified",
            "pages/Watch.md",
            "- modified\n  id:: 40404040-4040-4040-8040-404040404040\n",
        ),
        IncrementalOp("watchdog_delete", "pages/Watch.md"),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_watch_02_rename_file_path_parity(tmp_path: Path) -> None:
    """A2-WATCH-02: rename on disk converges to same shadow state as full rebuild."""
    graph = _minimal_graph(tmp_path)
    block_uuid = "50505050-5050-4050-8050-505050505050"
    ops = [
        IncrementalOp(
            "write_sync",
            "pages/OldName.md",
            f"- body\n  id:: {block_uuid}\n",
        ),
        IncrementalOp(
            "rename_sync",
            "pages/OldName.md",
            dest_rel="pages/NewName.md",
        ),
    ]

    expected_graph = graph.parent / f"{graph.name}-expected"
    if expected_graph.exists():
        shutil.rmtree(expected_graph)
    shutil.copytree(graph, expected_graph)
    _apply_markdown_ops(expected_graph, ops)
    _remove_shadow_db(expected_graph)
    rebuild_shadow_from_graph(expected_graph)
    expected = capture_shadow_snapshot(expected_graph)
    assert len(expected) == 1
    assert expected[0].title == "NewName"
    assert expected[0].file_path == "pages/NewName.md"
    assert len(expected[0].blocks) == 1
    assert expected[0].blocks[0].block_uuid == block_uuid

    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_watch_03_modify_during_bootstrap_replays(tmp_path: Path) -> None:
    """A2-WATCH-03: edits during bootstrap replay into shadow after rebuild."""
    graph = _minimal_graph(tmp_path)
    _write_page(
        graph,
        "pages/Seed.md",
        "- seed\n  id:: 60606060-6060-4060-8060-606060606060\n",
    )
    rebuild_shadow_from_graph(graph)

    mark_bootstrapping(graph)
    late = _write_page(
        graph,
        "pages/Late.md",
        "- late\n  id:: 70707070-7070-4070-8070-707070707070\n",
    )
    sync_page_to_shadow(graph, late)
    rebuild_shadow_from_graph(graph)

    snap = capture_shadow_snapshot(graph)
    titles = {page.title for page in snap}
    assert {"Seed", "Late"} <= titles


def test_a2_parse_01_journal_and_encoded_page_title(tmp_path: Path) -> None:
    """A2-PARSE-01: journals and Logseq-encoded page titles round-trip in shadow."""
    graph = _minimal_graph(tmp_path)
    encoded = page_title_to_filename("namespace/encoded")
    ops = [
        IncrementalOp(
            "write_sync",
            "journals/2026_07_18.md",
            "- journal entry\n  id:: 80808080-8080-4080-8080-808080808080\n",
        ),
        IncrementalOp(
            "write_sync",
            f"pages/{encoded}",
            "- namespaced\n  id:: 90909090-9090-4090-8090-909090909090\n",
        ),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)

    _write_page(
        graph,
        "journals/2026_07_18.md",
        "- journal entry\n  id:: 80808080-8080-4080-8080-808080808080\n",
    )
    _write_page(
        graph,
        f"pages/{encoded}",
        "- namespaced\n  id:: 90909090-9090-4090-8090-909090909090\n",
    )
    rebuild_shadow_from_graph(graph)
    snap = capture_shadow_snapshot(graph)
    journal = next(page for page in snap if page.is_journal == 1)
    encoded_page = next(page for page in snap if page.title == "namespace/encoded")
    assert journal.file_path == "journals/2026_07_18.md"
    assert encoded_page.file_path == f"pages/{encoded}"


def test_a2_parse_02_unicode_multiline_and_page_properties(tmp_path: Path) -> None:
    """A2-PARSE-02: Unicode, multiline content, and page properties are preserved."""
    graph = _minimal_graph(tmp_path)
    body = (
        "tags:: shadow, αβγ\n"
        "alias:: Café\n"
        "- café — 日本語\n"
        "  id:: a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1\n"
        "  multiline:: |\n"
        "    line one\n"
        "    line two\n"
    )
    ops = [IncrementalOp("write_sync", "pages/Unicode.md", body)]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_parse_03_empty_and_minimal_markdown(tmp_path: Path) -> None:
    """A2-PARSE-03: empty or whitespace-only pages index without blocks."""
    graph = _minimal_graph(tmp_path)
    ops = [
        IncrementalOp("write_sync", "pages/Empty.md", ""),
        IncrementalOp("write_sync", "pages/Whitespace.md", "   \n\n"),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_parse_04_malformed_outline_still_parity(tmp_path: Path) -> None:
    """A2-PARSE-04: parser-tolerant outline still matches full vs incremental."""
    graph = _minimal_graph(tmp_path)
    body = "- no id line\n- parent\n  id:: b1b1b1b1-b1b1-4b1b-8b1b-b1b1b1b1b1b1\n  orphan indent\n"
    ops = [IncrementalOp("write_sync", "pages/Malformed.md", body)]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_parse_05_duplicate_block_uuid_raises(tmp_path: Path) -> None:
    """A2-PARSE-05: intra-page duplicate block UUID is rejected (no silent dedup)."""
    graph = _minimal_graph(tmp_path)
    body = (
        "- first\n  id:: c1c1c1c1-c1c1-4c1c-8c1c-c1c1c1c1c1c1\n"
        "- second\n  id:: c1c1c1c1-c1c1-4c1c-8c1c-c1c1c1c1c1c1\n"
    )
    page = _write_page(graph, "pages/Dup.md", body)
    with pytest.raises(ShadowSyncError):
        sync_page_to_shadow(graph, page)


def test_a2_parse_06_delete_and_recreate_same_title(tmp_path: Path) -> None:
    """A2-PARSE-06: delete then recreate same page title matches full rebuild."""
    graph = _minimal_graph(tmp_path)
    ops = [
        IncrementalOp(
            "write_sync",
            "pages/Reborn.md",
            "- first\n  id:: d1d1d1d1-d1d1-4d1d-8d1d-d1d1d1d1d1d1\n",
        ),
        IncrementalOp("delete_sync", "pages/Reborn.md"),
        IncrementalOp(
            "write_sync",
            "pages/Reborn.md",
            "- second\n  id:: d2d2d2d2-d2d2-4d2d-8d2d-d2d2d2d2d2d2\n",
        ),
    ]
    assert_full_rebuild_matches_incremental(graph, seed_files={}, ops=ops)


def test_a2_parity_05_equivalent_op_permutations_match_full_rebuild(
    tmp_path: Path,
) -> None:
    """A2-PARITY-05: permuted incremental schedules with identical final Markdown match rebuild."""

    def _scenario(
        graph: Path, ops_builder: Callable[[], Sequence[IncrementalOp]]
    ) -> tuple[PageSnap, ...]:
        work = graph.parent / f"{graph.name}-work"
        if work.exists():
            shutil.rmtree(work)
        shutil.copytree(graph, work)
        _remove_shadow_db(work)
        _apply_incremental_ops(work, ops_builder())
        return capture_shadow_snapshot(work)

    graph = _minimal_graph(tmp_path)
    base_ops: list[IncrementalOp] = [
        IncrementalOp(
            "write_sync",
            "pages/One.md",
            "- one\n  id:: e1e1e1e1-e1e1-4e1e-8e1e-e1e1e1e1e1e1\n",
        ),
        IncrementalOp(
            "write_sync",
            "pages/Two.md",
            "- two\n  id:: e2e2e2e2-e2e2-4e2e-8e2e-e2e2e2e2e2e2\n",
        ),
        IncrementalOp(
            "write_sync",
            "pages/One.md",
            "- one v2\n  id:: e3e3e3e3-e3e3-4e3e-8e3e-e3e3e3e3e3e3\n",
        ),
    ]
    snap_a = _scenario(graph, lambda: base_ops)
    snap_b = _scenario(
        graph,
        lambda: [
            base_ops[0],
            IncrementalOp(
                "write_sync",
                "pages/One.md",
                "- one v2\n  id:: e3e3e3e3-e3e3-4e3e-8e3e-e3e3e3e3e3e3\n",
            ),
            base_ops[1],
        ],
    )

    full_graph = graph.parent / f"{graph.name}-final"
    if full_graph.exists():
        shutil.rmtree(full_graph)
    shutil.copytree(graph, full_graph)
    for op in base_ops:
        if op.kind == "write_sync":
            _write_page(full_graph, op.rel, op.body)
    _remove_shadow_db(full_graph)
    rebuild_shadow_from_graph(full_graph)
    snap_full = capture_shadow_snapshot(full_graph)

    assert snap_a == snap_full
    assert snap_b == snap_full
