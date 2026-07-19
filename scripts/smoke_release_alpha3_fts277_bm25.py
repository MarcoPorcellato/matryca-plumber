#!/usr/bin/env python3
"""Operational FTS #277 smoke via public ``handle_search_bm25`` (installed wheel only).

Runs outside the repo checkout: tempfile vault + clean venv, ``PYTHONPATH`` cleared.
Expects ``dist/matryca_plumber-2.0.0a3-*.whl`` (build with ``uv build`` first).

    uv build -q
    uv run python scripts/smoke_release_alpha3_fts277_bm25.py
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
WHEEL_GLOB = "matryca_plumber-2.0.0a3-*.whl"
EXPECTED_VERSION = "2.0.0a3"
HYPHEN_UUID = "66666666-6666-4666-8666-666666666666"
UNICODE_UUID = "68686868-6868-4686-8686-686868686868"
OR_ALPHA_UUID = "70707070-7070-4707-8707-707070707070"
OR_BETA_UUID = "71717171-7171-4717-8717-717171717171"
PREFIX_UUID = "78787878-7878-4787-8787-787878787878"
NEG_ALPHA_UUID = "79797979-7979-4797-8797-797979797979"
NEG_BETA_UUID = "80808080-8080-4080-8080-808080808080"
FALLBACK_UUID = "81818181-8181-4181-8181-818181818181"


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


async def _bm25(py: Path, graph: Path, query: str, *, shadow: bool = True) -> str:
    code = f"""
import asyncio
from pathlib import Path
from src.agent.dispatch_search_handlers import handle_search_bm25

async def _run():
    return await handle_search_bm25({str(graph)!r}, {query!r})

print(asyncio.run(_run()))
"""
    proc = _run_py(py, graph, code, shadow=shadow)
    if proc.returncode != 0:
        _fail(f"handle_search_bm25({query!r}): {proc.stderr or proc.stdout}")
    return proc.stdout


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
    _ok(f"imports from wheel site-packages ({proc.stdout.strip()})")


def _write_vault(graph: Path) -> None:
    (graph / "pages").mkdir(parents=True)
    (graph / "journals").mkdir(parents=True)
    pages = {
        "Hyphen.md": (f"- state-of-the-art needle\n  id:: {HYPHEN_UUID}\n"),
        "HyphenUnicode.md": (f"- state–of–the–art token\n  id:: {UNICODE_UUID}\n"),
        "OrHyphen.md": (
            f"- alpha state-of-the-art token\n  id:: {OR_ALPHA_UUID}\n"
            f"- beta plain token\n  id:: {OR_BETA_UUID}\n"
        ),
        "Prefix.md": (f"- prefixneedle token\n  id:: {PREFIX_UUID}\n"),
        "Negation.md": (
            f"- alpha only token\n  id:: {NEG_ALPHA_UUID}\n"
            f"- beta noise token\n  id:: {NEG_BETA_UUID}\n"
        ),
        "FallbackHyphen.md": (f"- state-of-the-art fallback marker\n  id:: {FALLBACK_UUID}\n"),
        "Seed.md": ("- needle baseline token\n  id:: 99999999-9999-4999-8999-999999999999\n"),
    }
    for name, body in pages.items():
        (graph / "pages" / name).write_text(body, encoding="utf-8")


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


def _assert_no_operational_leak(out: str, label: str) -> None:
    forbidden = ("OperationalError", "no such column", "syntax error near")
    for frag in forbidden:
        if frag.lower() in out.lower():
            _fail(f"{label}: leaked backend error fragment {frag!r} in output")


async def _check_hyphenated_hit(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "state-of-the-art")
    _assert_no_operational_leak(out, "hyphenated")
    if "block `" not in out or "Hyphen.md" not in out:
        _fail(f"hyphenated shadow hit missing: {out[:400]}")
    if "Invalid FTS query" in out or "## Ranked pages (BM25)" not in out:
        _fail("hyphenated query fell back to generational envelope")
    _ok("state-of-the-art → shadow FTS hit via BM25 (no generational fallback)")


async def _check_unicode_dash(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "state–of–the–art")
    _assert_no_operational_leak(out, "unicode dash")
    if "block `" not in out or "HyphenUnicode.md" not in out:
        _fail(f"unicode dash compound miss: {out[:400]}")
    _ok("Unicode dash hyphenated token → shadow hit")


async def _check_or_operator(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "state-of-the-art OR beta")
    _assert_no_operational_leak(out, "OR operator")
    if out.count("block `") < 2:
        _fail(f"OR operator expected two shadow hits: {out[:500]}")
    _ok("explicit OR operator unchanged (two shadow hits)")


async def _check_prefix_query(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "prefix*")
    _assert_no_operational_leak(out, "prefix")
    if "block `" not in out or "Prefix.md" not in out:
        _fail(f"prefix query miss: {out[:400]}")
    _ok("prefix query unchanged (prefix* shadow hit)")


async def _check_intentional_negation(py: Path, graph: Path) -> None:
    code = """
from src.shadow.query import prepare_fts_user_query
assert prepare_fts_user_query("-needle") == "-needle"
print("prepare-negation")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"leading hyphen prepare contract: {proc.stderr or proc.stdout}")
    out = await _bm25(py, graph, "alpha NOT beta")
    _assert_no_operational_leak(out, "NOT negation")
    if "block `" not in out or NEG_ALPHA_UUID not in out:
        _fail(f"NOT negation shadow hit missing alpha block: {out[:500]}")
    if NEG_BETA_UUID in out:
        _fail("NOT beta should exclude beta block from shadow hits")
    _ok("intentional NOT negation unchanged (alpha NOT beta shadow path)")


async def _check_invalid_validation(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, '"unclosed')
    if "Invalid FTS query" not in out:
        _fail(f"invalid syntax should validation-error: {out[:300]}")
    if "## Ranked pages (BM25)" in out:
        _fail("invalid syntax must not return generational BM25 envelope")
    _ok("invalid FTS query → validation error (no fallback)")


async def _check_zero_hits_shadow(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "zzznomatchzz")
    if "- **Matches:** 0" not in out or "_No lexical overlap" not in out:
        _fail(f"zero hits shadow envelope missing: {out[:300]}")
    if "block `" in out:
        _fail("zero hits must not use generational block listing")
    _ok("zero FTS hits → empty shadow envelope (no generational fallback)")


async def _check_backend_failure_fallback(py: Path, graph: Path) -> None:
    code = f"""
import asyncio
import sqlite3
from unittest.mock import patch
from pathlib import Path
from src.agent.dispatch_search_handlers import handle_search_bm25

g = Path({str(graph)!r})

async def _run():
    with patch(
        "src.shadow.fts_format.search_blocks_fts",
        side_effect=sqlite3.OperationalError("database is locked"),
    ):
        return await handle_search_bm25(str(g), "state-of-the-art")

out = asyncio.run(_run())
assert "FallbackHyphen.md" in out, out
assert "database is locked" not in out
assert "block `" not in out
print("fallback")
"""
    proc = _run_py(py, graph, code)
    if proc.returncode != 0:
        _fail(f"backend failure fallback: {proc.stderr or proc.stdout}")
    _ok("real backend failure → generational BM25 fallback")


async def _check_flag_false_generational(py: Path, graph: Path) -> None:
    out = await _bm25(py, graph, "needle", shadow=False)
    if "block `" in out:
        _fail("flag false must not use shadow block envelope")
    if "Seed.md" not in out and "needle" not in out.lower():
        _fail(f"flag false generational path empty: {out[:300]}")
    _ok("flag false → generational BM25 path")


async def main_async(py: Path, graph: Path) -> None:
    _assert_import_provenance(py)
    _bootstrap(py, graph)
    await _check_hyphenated_hit(py, graph)
    await _check_unicode_dash(py, graph)
    await _check_or_operator(py, graph)
    await _check_prefix_query(py, graph)
    await _check_intentional_negation(py, graph)
    await _check_invalid_validation(py, graph)
    await _check_zero_hits_shadow(py, graph)
    await _check_backend_failure_fallback(py, graph)
    await _check_flag_false_generational(py, graph)


def main() -> None:
    print("=== smoke: FTS #277 via handle_search_bm25 (wheel only) ===")
    subprocess.run(["uv", "build", "-q"], check=True, cwd=ROOT)
    wheel = _find_wheel()
    _ok(f"built wheel {wheel.name}")

    with tempfile.TemporaryDirectory(prefix="mp-smoke-a3-fts-") as tmp:
        graph = Path(tmp) / "vault"
        venv_dir = Path(tmp) / "venv"
        _write_vault(graph)
        py = _install_wheel(wheel, venv_dir)
        asyncio.run(main_async(py, graph))

    print("\n=== ALL FTS #277 BM25 SMOKE CHECKS PASSED ===")


if __name__ == "__main__":
    main()
