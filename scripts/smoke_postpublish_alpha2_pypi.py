#!/usr/bin/env python3
"""Post-publish smoke for PyPI ``matryca-plumber==2.0.0a2`` on a real vault copy.

Usage (from any directory):
    uv run python /path/to/scripts/smoke_postpublish_alpha2_pypi.py /path/to/vault

Uses only the published wheel (no local checkout). Does not auto-repair vault data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

PYPI_SPEC = "matryca-plumber==2.0.0a2"
RENAME_UUID = "a4a4a4a4-a4a4-4a4a-8a4a-a4a4a4a4a4a4"
OLD_REL = "pages/MatrycaSmokeRenameOld.md"
NEW_REL = "pages/MatrycaSmokeRenameNew.md"


def _fail(msg: str) -> NoReturn:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _env(graph: Path, *, shadow: bool | None) -> dict[str, str]:
    env = os.environ.copy()
    env["LOGSEQ_GRAPH_PATH"] = str(graph)
    env["MATRYCA_MCP_ENABLED"] = "false"
    if shadow is True:
        env["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    elif shadow is False:
        env.pop("MATRYCA_SHADOW_DB_ENABLED", None)
    return env


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _read_meta(db: Path) -> dict[str, str]:
    conn = sqlite3.connect(db)
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM shadow_meta")}
    finally:
        conn.close()


def _markdown_fingerprint(
    graph: Path,
    *,
    extra_ignore: set[str] | None = None,
    skip_rels: set[str] | None = None,
) -> str:
    ignore_parts = {".matryca_semantic_cache", ".git"} | (extra_ignore or set())
    skip = skip_rels or set()
    h = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        rel = path.relative_to(graph).as_posix()
        if rel in skip:
            continue
        if any(part in ignore_parts for part in path.parts):
            continue
        h.update(rel.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _install_pypi_venv(venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run(["uv", "venv", str(venv_dir)], check=True)
    subprocess.run(
        ["uv", "pip", "install", PYPI_SPEC],
        check=True,
        env={**os.environ, "VIRTUAL_ENV": str(venv_dir)},
    )
    py = venv_dir / "bin" / "python"
    proc = subprocess.run(
        [str(py), "-c", "import importlib.metadata as m; print(m.version('matryca-plumber'))"],
        capture_output=True,
        text=True,
        check=True,
    )
    if proc.stdout.strip() != "2.0.0a2":
        _fail(f"expected PyPI 2.0.0a2, got {proc.stdout.strip()!r}")
    return py


def _run_py(
    py: Path, graph: Path, code: str, *, shadow: bool | None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(py), "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        timeout=900,
    )


def _smallest_page_title(graph: Path) -> str:
    pages_dir = graph / "pages"
    smallest: tuple[int, str] | None = None
    for path in pages_dir.glob("*.md"):
        size = path.stat().st_size
        title = path.stem
        if smallest is None or size < smallest[0]:
            smallest = (size, title)
    if smallest is None:
        _fail("no pages/*.md found for markdown read probe")
    return smallest[1]


def _markdown_read_probe(py: Path, graph: Path, *, shadow: bool) -> None:
    title = _smallest_page_title(graph)
    code = f"""
import asyncio
from pathlib import Path
from src.agent.dispatch_read_handlers import handle_read_page
from src.config import MatrycaWikiConfig

async def _run():
    out = await handle_read_page(
        MatrycaWikiConfig(),
        str(Path({str(graph)!r})),
        {title!r},
    )
    assert isinstance(out, str)
    assert len(out) > 0

asyncio.run(_run())
"""
    proc = _run_py(py, graph, code, shadow=shadow)
    if proc.returncode != 0:
        _fail(f"markdown read ({title!r}): {proc.stderr or proc.stdout}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path, help="Path to Logseq graph root (copy recommended)")
    args = parser.parse_args()
    graph = args.vault.expanduser().resolve()
    if not (graph / "pages").is_dir():
        _fail(f"missing pages/: {graph}")

    work = Path(tempfile.mkdtemp(prefix="mp-pypi-smoke-"))
    venv_dir = work / "venv"
    py = _install_pypi_venv(venv_dir)
    _ok(f"PyPI package installed ({PYPI_SPEC})")

    baseline_md = _markdown_fingerprint(graph)
    rename_paths = {OLD_REL, NEW_REL}

    # 1) flag false
    print("\n-- 1 flag false --")
    if _shadow_db(graph).exists():
        _fail("unexpected pre-existing shadow.sqlite for flag-false baseline")
    code = f"""
import asyncio
from pathlib import Path
from src.shadow.config import shadow_db_enabled
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.connection import shadow_db_path
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})
assert shadow_db_enabled() is False
assert resolve_shadow_health(g) == ShadowHealthState.DISABLED
assert not shadow_db_path(g).exists()

async def _bm25():
    out = await handle_search_bm25(str(g), "test")
    assert isinstance(out, str)
    assert "Invalid FTS query" not in out

asyncio.run(_bm25())
"""
    proc = _run_py(py, graph, code, shadow=False)
    if proc.returncode != 0:
        _fail(f"flag false: {proc.stderr or proc.stdout}")
    _markdown_read_probe(py, graph, shadow=False)
    if _shadow_db(graph).exists():
        _fail("shadow.sqlite created while flag false")
    _ok("flag false — disabled, no shadow DB, generational BM25 + Markdown read")

    # 2) flag true bootstrap
    print("\n-- 2 flag true bootstrap --")
    boot = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph
rebuild_shadow_from_graph(Path({str(graph)!r}))
"""
    proc = _run_py(py, graph, boot, shadow=True)
    if proc.returncode != 0:
        _fail(f"bootstrap: {proc.stderr or proc.stdout}")
    db = _shadow_db(graph)
    if not db.is_file():
        _fail("shadow.sqlite missing after bootstrap")
    meta = _read_meta(db)
    generation = meta.get("generation")
    if not generation:
        _fail(f"missing generation: {meta}")
    if meta.get("last_full_sync_completed") != "true":
        _fail(f"bootstrap incomplete: {meta}")
    indexed = int(meta.get("indexed_page_count", "-1"))
    source = int(meta.get("source_page_count", "-1"))
    conn = sqlite3.connect(db)
    try:
        actual = int(conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0])
    finally:
        conn.close()
    if indexed != actual or source != actual:
        _fail(f"meta/pages mismatch indexed={indexed} source={source} actual={actual}")
    fts_cte = f"""
from pathlib import Path
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import query_subtree_by_block_uuid

g = Path({str(graph)!r})
assert resolve_shadow_health(g) == ShadowHealthState.READY
conn = open_shadow_db(g)
try:
    hits = search_blocks_fts(conn, "matryca", limit=5)
    assert isinstance(hits, list)
    if hits:
        subtree = query_subtree_by_block_uuid(conn, hits[0].block_uuid)
        assert subtree.status.value in ("complete", "truncated")
finally:
    conn.close()
"""
    proc = _run_py(py, graph, fts_cte, shadow=True)
    if proc.returncode != 0:
        _fail(f"FTS/CTE: {proc.stderr or proc.stdout}")
    _ok(f"flag true — ready, generation={generation}, pages={actual}, FTS+CTE OK")

    # 3) second startup idempotent (no explicit rebuild)
    print("\n-- 3 second startup --")
    second_start = f"""
from pathlib import Path
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup, shadow_needs_bootstrap
from src.shadow.connection import open_shadow_db
from src.shadow.meta import get_meta, META_GENERATION

g = Path({str(graph)!r})
assert shadow_needs_bootstrap(g) is False
ensure_shadow_runtime_at_startup(g)
ensure_shadow_runtime_at_startup(g)
conn = open_shadow_db(g)
try:
    assert get_meta(conn, META_GENERATION) == {generation!r}
finally:
    conn.close()
"""
    proc = _run_py(py, graph, second_start, shadow=True)
    if proc.returncode != 0:
        _fail(f"second startup: {proc.stderr or proc.stdout}")
    meta2 = _read_meta(db)
    if meta2.get("generation") != generation:
        _fail(f"generation changed: {generation} -> {meta2.get('generation')}")
    _ok("second startup — generation unchanged, no rebuild")

    # 4) controlled rename
    print("\n-- 4 rename probe --")
    old_path = graph / OLD_REL
    new_path = graph / NEW_REL
    old_path.write_text(
        f"- matryca smoke rename token\n  id:: {RENAME_UUID}\n",
        encoding="utf-8",
    )
    sync_old = f"""
from pathlib import Path
from src.shadow.sync import sync_page_to_shadow
sync_page_to_shadow(Path({str(graph)!r}), Path({str(old_path)!r}))
"""
    proc = _run_py(py, graph, sync_old, shadow=True)
    if proc.returncode != 0:
        _fail(f"sync old rename page: {proc.stderr or proc.stdout}")
    old_path.rename(new_path)
    sync_new = f"""
from pathlib import Path
from src.shadow.sync import sync_page_to_shadow
sync_page_to_shadow(Path({str(graph)!r}), Path({str(new_path)!r}))
"""
    proc = _run_py(py, graph, sync_new, shadow=True)
    if proc.returncode != 0:
        _fail(f"sync renamed page: {proc.stderr or proc.stdout}")
    verify = f"""
from pathlib import Path
from src.shadow.connection import open_shadow_db
conn = open_shadow_db(Path({str(graph)!r}))
try:
    stale = conn.execute(
        "SELECT file_path FROM pages WHERE file_path = ?",
        ({OLD_REL!r},),
    ).fetchall()
    assert stale == []
    rows = conn.execute(
        "SELECT file_path FROM pages WHERE title = ?", ("MatrycaSmokeRenameNew",)
    ).fetchall()
    assert len(rows) == 1 and rows[0][0] == {NEW_REL!r}
    dup = conn.execute(
        "SELECT COUNT(*) FROM blocks WHERE block_uuid = ?", ({RENAME_UUID!r},)
    ).fetchone()[0]
    assert dup == 1
    hits = conn.execute(
        "SELECT rowid FROM blocks_fts WHERE blocks_fts MATCH 'smoke'"
    ).fetchall()
    assert len(hits) >= 1
finally:
    conn.close()
"""
    proc = _run_py(py, graph, verify, shadow=True)
    if proc.returncode != 0:
        _fail(f"rename verify: {proc.stderr or proc.stdout}")
    _ok("rename — no stale row, single UUID, FTS indexed")

    # 5) flag off with existing DB
    print("\n-- 5 flag off existing DB --")
    meta_before_off = _read_meta(db)
    counts_before = (
        int(meta_before_off.get("indexed_page_count", "0")),
        int(meta_before_off.get("source_page_count", "0")),
    )
    flag_off = f"""
import asyncio
from pathlib import Path
from src.shadow.config import shadow_db_enabled
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})
assert shadow_db_enabled() is False
assert resolve_shadow_health(g) == ShadowHealthState.DISABLED

async def _run():
    out = await handle_search_bm25(str(g), "matryca")
    assert "block `" not in out

asyncio.run(_run())
"""
    proc = _run_py(py, graph, flag_off, shadow=False)
    if proc.returncode != 0:
        _fail(f"flag off existing db: {proc.stderr or proc.stdout}")
    meta_after_off = _read_meta(db)
    counts_after = (
        int(meta_after_off.get("indexed_page_count", "0")),
        int(meta_after_off.get("source_page_count", "0")),
    )
    if counts_before != counts_after or meta_after_off.get("generation") != meta_before_off.get(
        "generation"
    ):
        _fail("meta/counts changed while flag false")
    _ok("flag off — meta preserved, no shadow read path")

    # 6) markdown integrity
    print("\n-- 6 markdown integrity --")
    after_md = _markdown_fingerprint(graph, skip_rels=rename_paths)
    if baseline_md != after_md:
        _fail("unexpected markdown fingerprint drift beyond rename probe")
    _ok("markdown unchanged except explicit rename probe pages")

    summary = {
        "package": PYPI_SPEC,
        "vault_pages": len(list((graph / "pages").glob("*.md"))),
        "generation": generation,
        "indexed_pages": actual,
        "rename_probe": NEW_REL,
        "markdown_fingerprint_ok": True,
    }
    print("\n=== SMOKE SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\n=== ALL POST-PUBLISH CHECKS PASSED ===")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
