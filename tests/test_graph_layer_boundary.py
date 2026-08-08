"""AST-enforced dependency direction for the graph layer."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True, slots=True)
class _BoundaryImport:
    path: str
    module: str
    names: tuple[str, ...]


_KNOWN_EXCEPTIONS: dict[_BoundaryImport, str] = {
    _BoundaryImport(
        "src/graph/generational_cache.py",
        "src.rag.local_query",
        ("tokenize",),
    ): "#394: expires when lexical tokenization moves to a graph-owned leaf module",
    _BoundaryImport(
        "src/graph/insights/prompts.py",
        "src.agent.prompts.core",
        ("PromptContext", "compile_tier1a_prompt"),
    ): "#394: expires when shared prompt compilation moves below agent and graph",
}
_FORBIDDEN_LAYERS = frozenset({"agent", "daemon", "rag"})


def _package_for_path(path: Path, src_dir: Path) -> tuple[str, ...]:
    relative = path.relative_to(src_dir).with_suffix("")
    module = ("src", *relative.parts)
    return module if path.name == "__init__.py" else module[:-1]


def _resolve_from_module(node: ast.ImportFrom, package: tuple[str, ...]) -> str:
    imported = tuple((node.module or "").split(".")) if node.module else ()
    if node.level == 0:
        return ".".join(imported)
    retained = len(package) - node.level + 1
    if retained < 0:
        return ""
    return ".".join((*package[:retained], *imported))


def _imports_from_source(
    source: str,
    *,
    package: tuple[str, ...],
    relative_path: str,
) -> set[_BoundaryImport]:
    imports: set[_BoundaryImport] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            imports.add(
                _BoundaryImport(
                    relative_path,
                    _resolve_from_module(node, package),
                    tuple(alias.name for alias in node.names),
                )
            )
        elif isinstance(node, ast.Import):
            imports.update(_BoundaryImport(relative_path, alias.name, ()) for alias in node.names)
    return imports


def _forbidden_layer(module: str) -> str | None:
    parts = module.split(".")
    if parts and parts[0] in _FORBIDDEN_LAYERS:
        return parts[0]
    if len(parts) >= 2 and parts[0] == "src" and parts[1] in _FORBIDDEN_LAYERS:
        return parts[1]
    return None


def _graph_boundary_imports(graph_dir: Path) -> set[_BoundaryImport]:
    src_dir = graph_dir.parent
    imports: set[_BoundaryImport] = set()
    for path in sorted(graph_dir.rglob("*.py")):
        relative_path = path.relative_to(src_dir.parent).as_posix()
        imports.update(
            _imports_from_source(
                path.read_text(encoding="utf-8"),
                package=_package_for_path(path, src_dir),
                relative_path=relative_path,
            )
        )
    return {item for item in imports if _forbidden_layer(item.module) is not None}


def _format_import(item: _BoundaryImport) -> str:
    imported = f" import {', '.join(item.names)}" if item.names else ""
    return f"{item.path}: {item.module}{imported}"


def test_ast_import_resolution_covers_absolute_and_relative_forms() -> None:
    source = """
from src.agent.absolute import alpha
from ...daemon.relative import beta
import src.rag.local_query
import rag
text = 'from src.agent.not_an_import import ignored'
"""

    imports = _imports_from_source(
        source,
        package=("src", "graph", "nested"),
        relative_path="src/graph/nested/example.py",
    )

    assert {item.module for item in imports} == {
        "src.agent.absolute",
        "src.daemon.relative",
        "src.rag.local_query",
        "rag",
    }


def test_graph_layer_import_boundaries_are_ast_enforced() -> None:
    graph_dir = Path(__file__).resolve().parents[1] / "src" / "graph"
    observed = _graph_boundary_imports(graph_dir)
    expected = set(_KNOWN_EXCEPTIONS)
    unexpected = sorted(observed - expected)
    stale = sorted(expected - observed)

    assert unexpected == [], (
        "src/graph must not import agent, daemon, or rag. Unexpected imports:\n"
        + "\n".join(_format_import(item) for item in unexpected)
    )
    assert stale == [], (
        "Remove resolved graph-boundary exceptions and their expiry notes:\n"
        + "\n".join(f"{_format_import(item)} — {_KNOWN_EXCEPTIONS[item]}" for item in stale)
    )
