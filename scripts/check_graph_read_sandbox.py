#!/usr/bin/env python3
"""Fail CI when graph markdown reads bypass the path sandbox helper."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    REPO_ROOT / "src" / "graph",
    REPO_ROOT / "src" / "agent",
    REPO_ROOT / "src" / "rag",
    REPO_ROOT / "src" / "semantic",
    REPO_ROOT / "matryca_plumber",
)

# Files allowed to call Path.read_text directly (sandbox primitives or non-markdown I/O).
# Subset requires inline ``# sandbox-read-ok`` on each read_text line (line-stable marker).
_MARKER_READ_TEXT_ALLOWLIST = frozenset(
    {
        "src/agent/maintenance_daemon.py",
        "src/agent/daemon_process_lock.py",
    },
)

ALLOWLIST = frozenset(
    {
        "src/graph/path_sandbox.py",
        "src/graph/markdown_io.py",
        "src/agent/plumber_modules/property_hygiene.py",  # repo-local YAML rules
        "src/agent/maintenance_daemon.py",  # daemon pid/lock sidecars only (marker-gated)
        "src/agent/daemon_process_lock.py",  # pid/lock sidecars (marker-gated)
        "src/utils/bounded_json.py",
        "src/utils/config_paths.py",
        "src/utils/provision_l1.py",
        "src/utils/runtime_bootstrap.py",
        "src/cli/ui_server.py",
        "src/config.py",
    },
)

# maintenance_daemon.py: only reads tagged with this inline marker are allowlisted.
# Using a marker (instead of hardcoded line numbers) keeps the check stable when
# the daemon module is edited and lines shift.
_DAEMON_ALLOW_MARKER = "sandbox-read-ok"

_READ_TEXT_RE = re.compile(r"\.read_text\s*\(")


def _attribute_path(expression: ast.expr) -> str | None:
    parts: list[str] = []
    while isinstance(expression, ast.Attribute):
        parts.append(expression.attr)
        expression = expression.value
    if not isinstance(expression, ast.Name):
        return None
    parts.append(expression.id)
    return ".".join(reversed(parts))


def _assignment_value(statement: ast.stmt) -> tuple[str, ast.expr] | None:
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            return target.id, statement.value
    if (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.value is not None
    ):
        return statement.target.id, statement.value
    return None


def _distribution_factory_binding(statement: ast.stmt) -> tuple[str, ast.Call] | None:
    assigned = _assignment_value(statement)
    if assigned is None:
        return None
    name, value = assigned
    if not isinstance(value, ast.Call) or _attribute_path(value.func) != (
        "importlib.metadata.distribution"
    ):
        return None
    if (
        len(value.args) != 1
        or value.keywords
        or not isinstance(value.args[0], ast.Constant)
        or type(value.args[0].value) is not str
        or value.args[0].value != "matryca-plumber"
    ):
        return None
    return name, value


def _read_text_assignment(statement: ast.stmt, receiver: str) -> ast.Call | None:
    if isinstance(statement, ast.Expr):
        value = statement.value
    else:
        assigned = _assignment_value(statement)
        if assigned is None:
            return None
        _, value = assigned
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == "read_text"
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == receiver
        and len(value.args) == 1
        and not value.keywords
        and isinstance(value.args[0], ast.Constant)
        and type(value.args[0].value) is str
        and value.args[0].value == "direct_url.json"
    ):
        return value
    return None


def _straight_line_blocks(statements: list[ast.stmt]) -> list[list[ast.stmt]]:
    blocks = [statements]
    for statement in statements:
        if isinstance(statement, ast.Try):
            blocks.extend(_straight_line_blocks(statement.body))
    return blocks


def _inside_except_handler_type(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        parent = parents[current]
        if isinstance(parent, ast.ExceptHandler):
            return parent.type is not None and any(
                descendant is node for descendant in ast.walk(parent.type)
            )
        current = parent
    return False


def _metadata_identity_read_exceptions(tree: ast.Module) -> set[ast.Call]:
    metadata_imports = [
        (index, statement)
        for index, statement in enumerate(tree.body)
        if isinstance(statement, ast.Import)
        and any(alias.name == "importlib.metadata" for alias in statement.names)
    ]
    if len(metadata_imports) != 1:
        return set()
    import_index, import_statement = metadata_imports[0]
    if any(
        alias.name == "importlib.metadata" and alias.asname is not None
        for alias in import_statement.names
    ):
        return set()

    module_imports = {id(statement) for statement in tree.body if isinstance(statement, ast.Import)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname == "importlib":
                    return set()
                if alias.name.split(".", maxsplit=1)[0] == "importlib" and (
                    id(node) not in module_imports
                    or alias.name not in {"importlib.metadata", "importlib.util"}
                    or alias.asname is not None
                ):
                    return set()
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".", maxsplit=1)[0] == "importlib" or any(
                alias.name == "*" or alias.name == "importlib" or alias.asname == "importlib"
                for alias in node.names
            ):
                return set()
        elif (
            (
                isinstance(node, ast.Name)
                and node.id == "importlib"
                and isinstance(node.ctx, (ast.Store, ast.Del))
            )
            or (isinstance(node, ast.arg) and node.arg == "importlib")
            or (isinstance(node, (ast.Global, ast.Nonlocal)) and "importlib" in node.names)
            or (isinstance(node, ast.ExceptHandler) and node.name == "importlib")
        ):
            return set()
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "importlib":
                return set()
        elif (
            (isinstance(node, ast.MatchAs) and node.name == "importlib")
            or (isinstance(node, ast.MatchStar) and node.name == "importlib")
            or (isinstance(node, ast.MatchMapping) and node.rest == "importlib")
        ):
            return set()

    blocks: list[list[ast.stmt]] = _straight_line_blocks(tree.body)
    for index, statement in enumerate(tree.body):
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and index > import_index:
            blocks.extend(_straight_line_blocks(statement.body))

    factory_calls: set[ast.Call] = set()
    exceptions: set[ast.Call] = set()
    factory_receivers: set[str] = set()
    for block in blocks:
        for index, statement in enumerate(block[:-1]):
            binding = _distribution_factory_binding(statement)
            if binding is None:
                continue
            receiver, factory_call = binding
            if (factory_call.lineno, factory_call.col_offset) <= (
                import_statement.lineno,
                import_statement.col_offset,
            ):
                continue
            read_call = _read_text_assignment(block[index + 1], receiver)
            if read_call is not None:
                factory_calls.add(factory_call)
                factory_receivers.add(receiver)
                exceptions.add(read_call)
    if not factory_calls:
        return set()
    if any(isinstance(node, ast.arg) and node.arg in factory_receivers for node in ast.walk(tree)):
        return set()

    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    safe_attribute_paths = {
        "importlib.metadata.distribution",
        "importlib.metadata.distributions",
        "importlib.metadata.version",
        "importlib.metadata.PackageNotFoundError",
        "importlib.util.find_spec",
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "read_text"
            and not isinstance(node.ctx, ast.Load)
        ):
            return set()
        if not isinstance(node, ast.Attribute):
            continue
        path = _attribute_path(node)
        if path is None or not path.startswith("importlib."):
            continue
        if not isinstance(node.ctx, ast.Load):
            return set()
        parent = parents.get(node)
        if path in safe_attribute_paths:
            if path == "importlib.metadata.distribution":
                if parent not in factory_calls:
                    return set()
            elif path == "importlib.metadata.PackageNotFoundError":
                if not _inside_except_handler_type(node, parents):
                    return set()
            elif not (isinstance(parent, ast.Call) and parent.func is node):
                return set()
        elif path in {"importlib.metadata", "importlib.util"}:
            if not isinstance(parent, ast.Attribute) or _attribute_path(parent) not in (
                safe_attribute_paths
            ):
                return set()
        else:
            return set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "importlib" and isinstance(node.ctx, ast.Load):
            parent = parents.get(node)
            if not isinstance(parent, ast.Attribute) or _attribute_path(parent) not in {
                "importlib.metadata",
                "importlib.util",
            }:
                return set()

    return exceptions


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main() -> int:
    violations: list[str] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = _rel(path)
            if rel in ALLOWLIST:
                if rel in _MARKER_READ_TEXT_ALLOWLIST:
                    lines = path.read_text(encoding="utf-8").splitlines()
                    for lineno, line in enumerate(lines, start=1):
                        if _DAEMON_ALLOW_MARKER in line:
                            continue
                        if _READ_TEXT_RE.search(line):
                            violations.append(f"{rel}:{lineno}: {line.strip()}")
                continue
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=rel)
            except SyntaxError as exc:
                violations.append(f"{rel}:{exc.lineno or 1}: could not parse Python source")
                continue
            lines = text.splitlines()
            exceptions = _metadata_identity_read_exceptions(tree)
            read_calls = sorted(
                (
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "read_text"
                ),
                key=lambda node: (node.lineno, node.col_offset),
            )
            for call in read_calls:
                if call in exceptions:
                    continue
                line = lines[call.lineno - 1].strip()
                violations.append(f"{rel}:{call.lineno}: {line}")

    if violations:
        print("Direct Path.read_text() on graph paths is forbidden outside the sandbox allowlist:")
        for item in violations:
            print(f"  - {item}")
        print(
            "Use read_graph_file_text() / read_graph_page_text() from path_sandbox / markdown_io."
        )
        return 1

    print("sandbox-read-check: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
