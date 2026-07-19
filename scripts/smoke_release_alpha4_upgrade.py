#!/usr/bin/env python3
"""Operational upgrade smoke: PyPI a3 → local a4 wheel on one vault.

Run from repo root after ``uv build`` (wheel ``2.0.0a4``):
    uv run python scripts/smoke_release_alpha4_upgrade.py
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPI_SPEC = "matryca-plumber==2.0.0a3"
WHEEL_GLOB = "matryca_plumber-2.0.0a4-*.whl"
BLOCK_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _env(graph: Path, *, shadow: bool) -> dict[str, str]:
    env = _clean_env()
    env["LOGSEQ_GRAPH_PATH"] = str(graph)
    env["MATRYCA_MCP_ENABLED"] = "false"
    if shadow:
        env["MATRYCA_SHADOW_DB_ENABLED"] = "true"
    else:
        env.pop("MATRYCA_SHADOW_DB_ENABLED", None)
    return env


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    (graph / "pages" / "Alpha.md").write_text(
        f"- alpha shadow term\n  id:: {BLOCK_UUID}\n  - child block\n    id:: {CHILD_UUID}\n",
        encoding="utf-8",
    )
    (graph / "journals" / "2026_07_19.md").write_text(
        "- journal entry\n  id:: 33333333-3333-4333-8333-333333333333\n",
        encoding="utf-8",
    )


def _markdown_fingerprint(graph: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(graph.rglob("*.md")):
        rel = path.relative_to(graph).as_posix()
        if ".matryca_semantic_cache" in path.parts:
            continue
        h.update(rel.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def _find_wheel() -> Path:
    wheels = sorted((ROOT / "dist").glob(WHEEL_GLOB))
    if not wheels:
        _fail(f"wheel not found ({WHEEL_GLOB}); run uv build first")
    return wheels[-1]


def _install_pypi_venv(venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    py = venv_dir / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=tempfile.gettempdir())
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), PYPI_SPEC],
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    )
    proc = subprocess.run(
        [str(py), "-c", "import importlib.metadata as m; print(m.version('matryca-plumber'))"],
        capture_output=True,
        text=True,
        check=True,
        env=_clean_env(),
        cwd=tempfile.gettempdir(),
    )
    if proc.stdout.strip() != "2.0.0a3":
        _fail(f"PyPI bootstrap expected 2.0.0a3, got {proc.stdout.strip()!r}")
    return py


def _install_wheel_venv(wheel: Path, venv_dir: Path) -> Path:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    py = venv_dir / "bin" / "python"
    subprocess.run(["uv", "venv", str(venv_dir)], check=True, cwd=tempfile.gettempdir())
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), str(wheel)],
        check=True,
        cwd=tempfile.gettempdir(),
        env=_clean_env(),
    )
    proc = subprocess.run(
        [str(py), "-c", "import importlib.metadata as m; print(m.version('matryca-plumber'))"],
        capture_output=True,
        text=True,
        check=True,
        env=_clean_env(),
        cwd=tempfile.gettempdir(),
    )
    if proc.stdout.strip() != "2.0.0a4":
        _fail(f"wheel expected 2.0.0a4, got {proc.stdout.strip()!r}")
    return py


def _run_py(
    py: Path,
    graph: Path,
    code: str,
    *,
    shadow: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(py), "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        timeout=180,
    )


def _shadow_db(graph: Path) -> Path:
    return graph / ".matryca_semantic_cache" / "shadow.sqlite"


def _read_meta(db: Path) -> dict[str, str]:
    conn = sqlite3.connect(db)
    try:
        return {str(k): str(v) for k, v in conn.execute("SELECT key, value FROM shadow_meta")}
    finally:
        conn.close()


def _assert_import_provenance(py: Path) -> None:
    code = f"""
from pathlib import Path
import src.shadow.fts_validation as v
root = Path({str(ROOT)!r}).resolve()
mod = Path(v.__file__).resolve()
assert str(root) not in str(mod), (root, mod)
assert "site-packages" in str(mod), mod
print(mod)
"""
    proc = _run_py(py, Path(tempfile.gettempdir()), code, shadow=False)
    if proc.returncode != 0:
        _fail(f"import provenance: {proc.stderr or proc.stdout}")
    _ok(f"imports from wheel ({proc.stdout.strip()})")


def _bootstrap_a3(py: Path, graph: Path) -> str:
    code = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.health import ShadowHealthState, resolve_shadow_health
g = Path({str(graph)!r})
rebuild_shadow_from_graph(g)
assert resolve_shadow_health(g) == ShadowHealthState.READY
from src.shadow.meta import get_meta, META_GENERATION
from src.shadow.connection import open_shadow_db
conn = open_shadow_db(g)
try:
    gen = get_meta(conn, META_GENERATION)
finally:
    conn.close()
print(gen)
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"a3 bootstrap: {proc.stderr or proc.stdout}")
    generation = proc.stdout.strip()
    if not generation:
        _fail("missing generation after a3 bootstrap")
    _ok(f"PyPI a3 bootstrap (generation={generation})")
    return generation


def _check_health_fts_bound(py: Path, graph: Path) -> None:
    code = f"""
import asyncio
from pathlib import Path
from src.shadow.connection import open_shadow_db
from src.shadow.health import ShadowHealthState, resolve_shadow_health
from src.shadow.query import search_blocks_fts
from src.shadow.subtree import query_subtree_by_block_uuid
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})
assert resolve_shadow_health(g) == ShadowHealthState.READY
conn = open_shadow_db(g)
try:
    hits = search_blocks_fts(conn, "shadow", limit=10)
    assert hits, "FTS zero hits"
    subtree = query_subtree_by_block_uuid(conn, {BLOCK_UUID!r})
    uuids = {{node.block_uuid for node in subtree.nodes}}
    assert {CHILD_UUID!r} in uuids, subtree
finally:
    conn.close()

async def _bound():
    out = await handle_search_bm25(str(g), "n" * 513)
    assert "Invalid FTS query" in out, out
    assert "## Ranked pages (BM25)" not in out, out

asyncio.run(_bound())
print("fts-bound-cte")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"FTS bound/CTE/BM25: {proc.stderr or proc.stdout}")
    _ok("health ready + FTS bound + CTE subtree via a4 wheel")


def main() -> None:
    print("=== smoke: PyPI a3 → local a4 wheel upgrade ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-a4-upgrade-") as tmp:
        graph = Path(tmp) / "vault"
        _write_vault(graph)
        baseline_md = _markdown_fingerprint(graph)

        print("\n-- phase 1: PyPI 2.0.0a3 bootstrap --")
        venv_a3 = Path(tmp) / "venv-a3"
        py_a3 = _install_pypi_venv(venv_a3)
        generation_a3 = _bootstrap_a3(py_a3, graph)
        db = _shadow_db(graph)
        if not db.is_file():
            _fail("shadow.sqlite missing after a3 bootstrap")

        print("\n-- phase 2: wheel 2.0.0a4 upgrade --")
        venv_a4 = Path(tmp) / "venv-a4"
        py_a4 = _install_wheel_venv(wheel, venv_a4)
        _assert_import_provenance(py_a4)

        warm = _run_py(
            py_a4,
            graph,
            f"""
from pathlib import Path
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup
ensure_shadow_runtime_at_startup(Path({str(graph)!r}))
print("warm")
""",
        )
        if warm.returncode != 0:
            _fail(f"a4 warm startup: {warm.stderr or warm.stdout}")

        meta_a4 = _read_meta(db)
        if meta_a4.get("generation") != generation_a3:
            _fail(
                f"generation changed after upgrade: {generation_a3} → {meta_a4.get('generation')}"
            )
        _ok("generation/meta preserved across a3→a4")

        _check_health_fts_bound(py_a4, graph)

        after_md = _markdown_fingerprint(graph)
        if baseline_md != after_md:
            _fail("markdown fingerprint drift after upgrade smoke")

        _ok("markdown vault bytes unchanged")

    print("\n=== ALL A3→A4 UPGRADE SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
