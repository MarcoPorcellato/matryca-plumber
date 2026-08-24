from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from src.contracts.pocket.bundle import render_schema_files

ROOT = Path(__file__).resolve().parents[3]


def _assert_closed(node: object) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
        for value in node.values():
            _assert_closed(value)
    elif isinstance(node, list):
        for value in node:
            _assert_closed(value)


def test_rendered_schemas_are_committed_closed_and_draft_2020_12() -> None:
    rendered = render_schema_files()
    assert set(rendered) == {
        "schemas/document.schema.json",
        "schemas/evidence.schema.json",
        "schemas/pack-manifest.schema.json",
    }
    for relative, raw in rendered.items():
        assert (ROOT / "contracts/pocket/v1" / relative).read_bytes() == raw
        schema = json.loads(raw)
        Draft202012Validator.check_schema(schema)
        _assert_closed(schema)
    assert "$defs" in json.loads(rendered["schemas/pack-manifest.schema.json"])
