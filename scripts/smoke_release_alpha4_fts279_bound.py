#!/usr/bin/env python3
"""Operational FTS #279 smoke: overlong query bound via ``handle_search_bm25`` (wheel only).

Runs outside the repo checkout: tempfile vault + clean venv, ``PYTHONPATH`` cleared.
Expects ``dist/matryca_plumber-2.0.0a4-*.whl`` (build with ``uv build`` first).

    uv build -q
    uv run python scripts/smoke_release_alpha4_fts279_bound.py
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEEL_GLOB = "matryca_plumber-2.0.0a4-*.whl"
EXPECTED_VERSION = "2.0.0a4"
SEED_UUID = "11111111-1111-4111-8111-111111111111"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _ok(label: str) -> None:
    print(f"OK  {label}")


def _find_wheel() -> Path:
    wheels = sorted((ROOT / "dist").glob(WHEEL_GLOB))
    if not wheels:
        _fail(f"wheel not found under dist/ ({WHEEL_GLOB}); run uv build first")
    return wheels[-1]


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


def _install_wheel(wheel: Path, venv_dir: Path) -> Path:
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
    if proc.stdout.strip() != EXPECTED_VERSION:
        _fail(f"wheel metadata expected {EXPECTED_VERSION!r}, got {proc.stdout.strip()!r}")
    return py


def _run_py(
    py: Path, graph: Path, code: str, *, shadow: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(py), "-c", code],
        env=_env(graph, shadow=shadow),
        capture_output=True,
        text=True,
        cwd=tempfile.gettempdir(),
        timeout=180,
    )


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "pages" / "Seed.md").write_text(
        f"- needle baseline token\n  id:: {SEED_UUID}\n",
        encoding="utf-8",
    )


def _bootstrap(py: Path, graph: Path) -> None:
    code = f"""
from pathlib import Path
from src.shadow.bootstrap import rebuild_shadow_from_graph
from src.shadow.health import ShadowHealthState, resolve_shadow_health
g = Path({str(graph)!r})
rebuild_shadow_from_graph(g)
assert resolve_shadow_health(g) == ShadowHealthState.READY
print("ready")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"bootstrap: {proc.stderr or proc.stdout}")
    _ok("shadow bootstrap ready")


async def _check_overlong_validation(py: Path, graph: Path) -> None:
    overlong = "n" * 513
    code = f"""
import asyncio
from pathlib import Path
from unittest.mock import patch
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})
query = {overlong!r}

async def _run():
    with patch("src.shadow.fts_format.search_blocks_fts") as search_blocks_fts:
        out = await handle_search_bm25(str(g), query)
    search_blocks_fts.assert_not_called()
    return out

out = asyncio.run(_run())
assert "Invalid FTS query" in out, out
assert "512" in out, out
assert "## Ranked pages (BM25)" not in out, out
assert query not in out, "full query leaked"
print("bound")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"overlong bound: {proc.stderr or proc.stdout}")
    _ok("overlong query → validation error, search_blocks_fts not called, no generational fallback")


async def _check_at_limit_ok(py: Path, graph: Path) -> None:
    code = f"""
import asyncio
from pathlib import Path
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})
query = "n" * 512

async def _run():
    return await handle_search_bm25(str(g), query)

out = asyncio.run(_run())
assert "Invalid FTS query" not in out, out
assert "- **Matches:** 0" in out or "block `" in out, out
print("limit-ok")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"at-limit query: {proc.stderr or proc.stdout}")
    _ok("query at exact 512-char limit accepted (no validation error)")


def main() -> None:
    print("=== smoke: FTS #279 query bound via handle_search_bm25 (wheel only) ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-a4-bound-") as tmp:
        graph = Path(tmp) / "vault"
        venv_dir = Path(tmp) / "venv"
        _write_vault(graph)
        py = _install_wheel(wheel, venv_dir)
        _bootstrap(py, graph)
        asyncio.run(_check_overlong_validation(py, graph))
        asyncio.run(_check_at_limit_ok(py, graph))

    print("\n=== ALL FTS #279 BOUND SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
