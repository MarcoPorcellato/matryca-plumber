"""Shadow FTS validation layering — leaf module must not depend on query/format."""

from __future__ import annotations

from pathlib import Path


def test_query_module_does_not_import_fts_format() -> None:
    query_path = Path(__file__).resolve().parents[1] / "src" / "shadow" / "query.py"
    text = query_path.read_text(encoding="utf-8")
    assert "fts_format" not in text


def test_fts_validation_leaf_has_no_query_or_format_imports() -> None:
    validation_path = Path(__file__).resolve().parents[1] / "src" / "shadow" / "fts_validation.py"
    text = validation_path.read_text(encoding="utf-8")
    forbidden = (
        "from .query",
        "from src.shadow.query",
        "from .fts_format",
        "from src.shadow.fts_format",
    )
    offenders = [needle for needle in forbidden if needle in text]
    assert offenders == []
