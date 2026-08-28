"""Static and import-time boundaries for evaluation projection adapters."""

from __future__ import annotations

import ast
import builtins
import importlib
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_NETWORK_IMPORTS = frozenset({"httpx", "requests", "socket", "urllib"})


def _module_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
    return roots


def _forbidden_environment_reads(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        f"{node.lineno}:{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
        and node.attr in {"environ", "getenv"}
    ]


def test_runtime_source_never_imports_tools() -> None:
    violations = [
        str(path.relative_to(_REPOSITORY_ROOT))
        for path in sorted((_REPOSITORY_ROOT / "src").rglob("*.py"))
        if "tools" in _module_roots(path)
    ]

    assert violations == []


def test_distribution_discovery_excludes_maintainer_tools() -> None:
    with (_REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
        package_config = tomllib.load(stream)

    assert package_config["tool"]["setuptools"]["packages"]["find"]["where"] == ["."]
    assert package_config["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "src*",
        "frontend",
    ]


def test_projection_imports_without_mlflow(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "mlflow" or name.startswith("mlflow."):
            raise AssertionError("mlflow import forbidden in PR A")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    importlib.reload(importlib.import_module("tools.evaluation_projection"))


def test_projection_adapters_forbid_network_and_environment_configuration() -> None:
    adapter_paths = sorted((_REPOSITORY_ROOT / "tools" / "evaluation_projection").rglob("*.py"))
    network_violations = {
        str(path.relative_to(_REPOSITORY_ROOT)): sorted(_module_roots(path) & _NETWORK_IMPORTS)
        for path in adapter_paths
        if _module_roots(path) & _NETWORK_IMPORTS
    }
    environment_violations = {
        str(path.relative_to(_REPOSITORY_ROOT)): _forbidden_environment_reads(path)
        for path in adapter_paths
        if _forbidden_environment_reads(path)
    }
    dotenv_violations = [
        str(path.relative_to(_REPOSITORY_ROOT))
        for path in adapter_paths
        if "dotenv" in _module_roots(path)
    ]

    assert network_violations == {}
    assert environment_violations == {}
    assert dotenv_violations == []


def test_wrapper_bootstraps_from_an_unrelated_working_directory(tmp_path: Path) -> None:
    wrapper = _REPOSITORY_ROOT / "scripts" / "project_graph_outcome_evidence.py"

    completed = subprocess.run(
        [sys.executable, str(wrapper), "--unknown-option"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 2
    assert "usage:" in completed.stderr
