#!/usr/bin/env python3
"""Operational upgrade smoke: PyPI a2 → local a3 wheel on one vault.

Run from repo root after ``uv build`` (wheel ``2.0.0a3``):
    uv run python scripts/smoke_release_alpha3_upgrade.py
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
PYPI_SPEC = "matryca-plumber==2.0.0a2"
WHEEL_GLOB = "matryca_plumber-2.0.0a3-*.whl"
BLOCK_UUID = "11111111-1111-4111-8111-111111111111"
CHILD_UUID = "22222222-2222-4222-8222-222222222222"
RENAME_UUID = "50505050-5050-4050-8050-505050505050"


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
    if proc.stdout.strip() != "2.0.0a2":
        _fail(f"PyPI bootstrap expected 2.0.0a2, got {proc.stdout.strip()!r}")
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
    if proc.stdout.strip() != "2.0.0a3":
        _fail(f"wheel expected 2.0.0a3, got {proc.stdout.strip()!r}")
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
import src.shadow.query as q
root = Path({str(ROOT)!r}).resolve()
mod = Path(q.__file__).resolve()
assert str(root) not in str(mod), (root, mod)
assert "site-packages" in str(mod), mod
print(mod)
"""
    proc = _run_py(py, Path(tempfile.gettempdir()), code, shadow=False)
    if proc.returncode != 0:
        _fail(f"import provenance: {proc.stderr or proc.stdout}")
    _ok(f"imports from wheel ({proc.stdout.strip()})")


def _bootstrap_a2(py: Path, graph: Path) -> str:
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
        _fail(f"a2 bootstrap: {proc.stderr or proc.stdout}")
    generation = proc.stdout.strip()
    if not generation:
        _fail("missing generation after a2 bootstrap")
    _ok(f"PyPI a2 bootstrap (generation={generation})")
    return generation


def _check_health_fts_cte(py: Path, graph: Path) -> None:
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

async def _bm25():
    out = await handle_search_bm25(str(g), "state-of-the-art")
    return out

# hyphen probe page not seeded here — only check shadow path works
async def _shadow_term():
    out = await handle_search_bm25(str(g), "shadow")
    assert "block `" in out, out
    assert "Alpha.md" in out, out

asyncio.run(_shadow_term())
print("fts-cte")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"FTS/CTE/BM25: {proc.stderr or proc.stdout}")
    _ok("health ready + FTS bm25 + CTE subtree via a3 wheel")


def _check_markdown_read(py: Path, graph: Path) -> None:
    code = f"""
import asyncio
from pathlib import Path
from src.agent.dispatch_read_handlers import handle_read_page
from src.config import MatrycaWikiConfig

async def _run():
    out = await handle_read_page(MatrycaWikiConfig(), str(Path({str(graph)!r})), "Alpha")
    assert isinstance(out, str) and len(out) > 0

asyncio.run(_run())
print("md")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"markdown read: {proc.stderr or proc.stdout}")
    _ok("Markdown read unchanged via installed wheel")


def main() -> None:
    print("=== smoke: PyPI a2 → local a3 wheel upgrade ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-a3-upgrade-") as tmp:
        graph = Path(tmp) / "vault"
        _write_vault(graph)
        baseline_md = _markdown_fingerprint(graph)

        print("\n-- phase 1: PyPI 2.0.0a2 bootstrap --")
        venv_a2 = Path(tmp) / "venv-a2"
        py_a2 = _install_pypi_venv(venv_a2)
        generation_a2 = _bootstrap_a2(py_a2, graph)
        db = _shadow_db(graph)
        if not db.is_file():
            _fail("shadow.sqlite missing after a2 bootstrap")

        print("\n-- phase 2: wheel 2.0.0a3 upgrade --")
        venv_a3 = Path(tmp) / "venv-a3"
        py_a3 = _install_wheel_venv(wheel, venv_a3)
        _assert_import_provenance(py_a3)

        warm = _run_py(
            py_a3,
            graph,
            f"""
from pathlib import Path
from src.shadow.bootstrap import ensure_shadow_runtime_at_startup
ensure_shadow_runtime_at_startup(Path({str(graph)!r}))
print("warm")
""",
        )
        if warm.returncode != 0:
            _fail(f"a3 warm startup: {warm.stderr or warm.stdout}")

        meta_a3 = _read_meta(db)
        if meta_a3.get("generation") != generation_a2:
            _fail(
                f"generation changed after upgrade: {generation_a2} → {meta_a3.get('generation')}"
            )
        _ok("generation/meta preserved across a2→a3")

        _check_health_fts_cte(py_a3, graph)
        _check_markdown_read(py_a3, graph)

        after_md = _markdown_fingerprint(graph)
        if baseline_md != after_md:
            _fail("markdown fingerprint drift after upgrade smoke")

        _ok("markdown vault bytes unchanged")

    print("\n=== ALL A2→A3 UPGRADE SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
