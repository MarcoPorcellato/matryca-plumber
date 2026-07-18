#!/usr/bin/env python3
"""Operational upgrade smoke: a1 (uvx) → a2 (local wheel) on one vault.

Run from repo root after ``uv build``:
    uv run python scripts/smoke_release_alpha2_upgrade.py
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALPHA1_SPEC = "matryca-plumber@2.0.0-alpha.1"
BLOCK_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"
RENAME_UUID = "50505050-5050-4050-8050-505050505050"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text(
        f"- alpha shadow term\n  id:: {BLOCK_UUID}\n  - child block\n    id:: {CHILD_UUID}\n",
        encoding="utf-8",
    )
    (graph / "journals" / "2026_07_18.md").write_text(
        "- journal entry\n  id:: 33333333-3333-4333-8333-333333333333\n",
        encoding="utf-8",
    )


def _env(graph: Path, *, shadow: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["LOGSEQ_GRAPH_PATH"] = str(graph)
    env["MATRYCA_MCP_ENABLED"] = "false"
    if shadow:
        env["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    else:
        env.pop("MATRYCA_SHADOW_DB_ENABLED", None)
    return env


def _run_uvx_alpha1(graph: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["uvx", ALPHA1_SPEC, *args]
    return subprocess.run(
        cmd,
        env=_env(graph, shadow=True),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _find_wheel() -> Path:
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("matryca_plumber-2.0.0a2-*.whl"))
    if not wheels:
        _fail(f"wheel not found under {dist}; run uv build first")
    return wheels[-1]


def _install_wheel_venv(wheel: Path, venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=ROOT)
    subprocess.run(
        ["uv", "pip", "install", str(wheel)],
        check=True,
        cwd=ROOT,
        env={**os.environ, "VIRTUAL_ENV": str(venv_dir)},
    )
    exe = venv_dir / "bin" / "matryca-plumber"
    if not exe.exists():
        _fail(f"missing console script: {exe}")
    return exe


def _run_wheel(
    exe: Path, graph: Path, *args: str, shadow: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(exe), *args],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
        cwd=ROOT,
    )


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _read_meta(db: Path) -> dict[str, str]:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT key, value FROM shadow_meta").fetchall()
        return {str(k): str(v) for k, v in rows}
    finally:
        conn.close()


def _wheel_python(exe: Path) -> list[str]:
    return [str(exe.parent / "python")]


def _wheel_version(exe: Path) -> str:
    py = _wheel_python(exe)
    proc = subprocess.run(
        [*py, "-c", "import importlib.metadata as m; print(m.version('matryca-plumber'))"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _run_py(
    graph: Path,
    py: list[str],
    code: str,
    *,
    shadow: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*py, "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=180,
    )


def _check_health_ready(graph: Path, py: list[str]) -> None:
    code = f"""
from pathlib import Path
from src.shadow.health import ShadowHealthState, resolve_shadow_health
g = Path({str(graph)!r})
h = resolve_shadow_health(g)
assert h == ShadowHealthState.READY, h
print("ready")
"""
    proc = _run_py(graph, py, code)
    if proc.returncode != 0:
        _fail(f"health ready: {proc.stderr or proc.stdout}")
    _ok("health ready after wheel upgrade")


def _check_fts_cte(graph: Path, py: list[str]) -> None:
    code = f"""
from pathlib import Path
from src.shadow.connection import open_shadow_db
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import query_subtree_by_block_uuid

graph = Path({str(graph)!r})
root_uuid = {BLOCK_UUID!r}
child_uuid = {CHILD_UUID!r}

conn = open_shadow_db(graph)
try:
    hits = search_blocks_fts(conn, "shadow", limit=10)
    assert hits, "FTS zero hits"
    subtree = query_subtree_by_block_uuid(conn, root_uuid)
    uuids = {{node.block_uuid for node in subtree.nodes}}
    assert child_uuid in uuids, subtree
finally:
    conn.close()
print("fts-cte")
"""
    proc = _run_py(graph, py, code)
    if proc.returncode != 0:
        _fail(f"FTS/CTE via wheel package: {proc.stderr or proc.stdout}")
    _ok("FTS bm25 + CTE subtree via installed wheel (Python API)")


def _check_rename_stale_owner(graph: Path, py: list[str]) -> None:
    old_rel = "pages/OldName.md"
    new_rel = "pages/NewName.md"
    old_path = graph / old_rel
    new_path = graph / new_rel
    old_path.write_text(
        f"- rename body\n  id:: {RENAME_UUID}\n",
        encoding="utf-8",
    )
    code_seed = f"""
from pathlib import Path
from src.shadow.sync import sync_page_to_shadow
graph = Path({str(graph)!r})
sync_page_to_shadow(graph, graph / {old_rel!r})
"""
    proc = _run_py(graph, py, code_seed)
    if proc.returncode != 0:
        _fail(f"seed rename page: {proc.stderr or proc.stdout}")

    old_path.rename(new_path)
    code_rename = f"""
from pathlib import Path
from src.shadow.sync import sync_page_to_shadow
graph = Path({str(graph)!r})
sync_page_to_shadow(graph, graph / {new_rel!r})
"""
    proc = _run_py(graph, py, code_rename)
    if proc.returncode != 0:
        _fail(f"incremental rename sync: {proc.stderr or proc.stdout}")

    code_verify = f"""
from pathlib import Path
from src.shadow.connection import open_shadow_db
from src.shadow.bootstrap import rebuild_shadow_from_graph

graph = Path({str(graph)!r})
conn = open_shadow_db(graph)
try:
    rows = conn.execute(
        "SELECT file_path FROM pages WHERE title = ?",
        ("NewName",),
    ).fetchall()
    assert len(rows) == 1, rows
    assert rows[0][0] == {new_rel!r}
    stale = conn.execute(
        "SELECT file_path FROM pages WHERE file_path = ?",
        ({old_rel!r},),
    ).fetchall()
    assert stale == [], stale
    dup = conn.execute(
        "SELECT COUNT(*) FROM blocks WHERE block_uuid = ?",
        ({RENAME_UUID!r},),
    ).fetchone()[0]
    assert dup == 1, dup
finally:
    conn.close()

rebuild_shadow_from_graph(graph)
conn = open_shadow_db(graph)
try:
  count = conn.execute("SELECT COUNT(*) FROM pages WHERE title = ?", ("NewName",)).fetchone()[0]
  assert count == 1
finally:
  conn.close()
print("rename-ok")
"""
    proc = _run_py(graph, py, code_verify)
    if proc.returncode != 0:
        _fail(f"rename stale-owner parity: {proc.stderr or proc.stdout}")
    _ok("incremental rename without stale page row (#272)")


def _check_fallback_when_not_ready(graph: Path, py: list[str]) -> None:
    db = _shadow_db(graph)
    conn = sqlite3.connect(db)
    try:
        conn.execute("UPDATE shadow_meta SET value = 'stale' WHERE key = 'last_sync_error'")
        conn.commit()
    finally:
        conn.close()

    code = f"""
from pathlib import Path
from src.agent.dispatch_search_handlers import handle_search_bm25
import asyncio

graph = Path({str(graph)!r})

async def _run():
    out = await handle_search_bm25(str(graph), "shadow")
    assert "block `" not in out, out
    assert "Alpha.md" in out, out

asyncio.run(_run())
print("fallback")
"""
    proc = _run_py(graph, py, code)
    if proc.returncode != 0:
        _fail(f"BM25 fallback when not ready: {proc.stderr or proc.stdout}")
    _ok("generational BM25 fallback when shadow not ready")


def _check_flag_false_no_shadow_access(graph: Path, py: list[str]) -> None:
    code = f"""
from pathlib import Path
import os
os.environ.pop("MATRYCA_SHADOW_DB_ENABLED", None)
from src.shadow.config import shadow_db_enabled
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup
from src.shadow.connection import shadow_db_path

g = Path({str(graph)!r})
assert shadow_db_enabled() is False
before = shadow_db_path(g).stat().st_mtime_ns
ensure_shadow_runtime_at_startup(g)
after = shadow_db_path(g).stat().st_mtime_ns
assert before == after
print("no-touch")
"""
    proc = _run_py(graph, py, code, shadow=False)
    if proc.returncode != 0:
        _fail(f"flag false no shadow access: {proc.stderr or proc.stdout}")
    _ok("flag false → shadow runtime no-op (mtime unchanged)")


def main() -> None:
    print("=== smoke: a1 uvx → a2 wheel upgrade ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-alpha2-") as tmp:
        graph = Path(tmp) / "vault"
        _write_vault(graph)
        venv_dir = Path(tmp) / "venv-a2"

        print("\n-- phase 1: uvx @2.0.0-alpha.1 bootstrap --")
        boot = _run_uvx_alpha1(graph, "read", "page", "Alpha")
        if boot.returncode != 0:
            _fail(f"uvx alpha1 bootstrap/read failed: {boot.stderr}")
        db = _shadow_db(graph)
        if not db.is_file():
            _fail("shadow.sqlite not created by uvx alpha1")
        meta_a1 = _read_meta(db)
        generation_a1 = meta_a1.get("generation")
        if not generation_a1:
            _fail(f"missing generation in meta: {meta_a1}")
        if meta_a1.get("last_full_sync_completed") != "true":
            _fail(f"bootstrap incomplete: {meta_a1}")
        _ok(f"uvx alpha1 bootstrap (generation={generation_a1})")

        print("\n-- phase 2: wheel 2.0.0a2 upgrade --")
        exe = _install_wheel_venv(wheel, venv_dir)
        version = _wheel_version(exe)
        if version != "2.0.0a2":
            _fail(f"wheel version expected 2.0.0a2, got {version!r}")
        _ok(f"wheel installed (PyPI metadata {version})")

        warm = _run_wheel(exe, graph, "read", "page", "Alpha")
        if warm.returncode != 0:
            _fail(f"wheel warm read failed: {warm.stderr}")
        meta_a2 = _read_meta(db)
        if meta_a2.get("generation") != generation_a1:
            _fail(
                f"generation changed after upgrade: {generation_a1} → {meta_a2.get('generation')}"
            )
        _ok("generation/meta preserved across a1→a2")

        py = _wheel_python(exe)
        _check_health_ready(graph, py)
        _check_fts_cte(graph, py)
        _check_rename_stale_owner(graph, py)
        _check_fallback_when_not_ready(graph, py)

        rebuild = _run_py(
            graph,
            py,
            (
                "from pathlib import Path\n"
                "from src.shadow.bootstrap import rebuild_shadow_from_graph\n"
                f"rebuild_shadow_from_graph(Path({str(graph)!r}))"
            ),
        )
        if rebuild.returncode != 0:
            _fail(f"rebuild after fallback test: {rebuild.stderr}")
        _check_flag_false_no_shadow_access(graph, py)

    print("\n=== ALL SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
