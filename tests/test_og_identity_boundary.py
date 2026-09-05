"""Architecture guards for Parser isolation in the OG identity slice."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE_MODULES = (
    ROOT / "src" / "graph" / "session_read_models.py",
    ROOT / "src" / "graph" / "session_read_service.py",
    ROOT / "src" / "graph" / "ports" / "session_read.py",
    ROOT / "src" / "agent" / "og_session_read_composition.py",
    ROOT / "src" / "agent" / "og_parser_identity_adapter.py",
)


def _parser_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                alias.name for alias in node.names if alias.name.startswith("logseq_matryca_parser")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("logseq_matryca_parser")
        ):
            imports.add(node.module)
    return imports


def test_parser_import_is_confined_to_internal_adapter() -> None:
    """Breaks if a DTO, port, service, or composition root imports Parser directly."""
    observed = {path.name: _parser_imports(path) for path in SLICE_MODULES}

    assert observed == {
        "session_read_models.py": set(),
        "session_read_service.py": set(),
        "session_read.py": set(),
        "og_session_read_composition.py": set(),
        "og_parser_identity_adapter.py": {"logseq_matryca_parser"},
    }
