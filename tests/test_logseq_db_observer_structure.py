"""TDD specification for the pure Logseq DB observer structural boundary."""

from __future__ import annotations

import hashlib
import importlib
import json
from typing import Any

import pytest


def _fixture_payload() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": "plumber.logseq-db.fixture-structure/v1",
        "graph_id": "synthetic-graph",
        "page_id": "synthetic-page",
        "root_block_id": "root",
        "source_revision": "synthetic-revision-1",
        "page": {"title": "Synthetic page"},
        "nodes": [
            {"id": "root", "parent_id": None, "ordinal": 0, "text": "Root"},
            {"id": "child", "parent_id": "root", "ordinal": 0, "text": "Child"},
        ],
        "property_declarations": [
            {"key": "status", "wire_type": "text", "cardinality": "one", "scope": "page"}
        ],
    }
    _bind_fixture_digest(payload)
    return payload


def _bind_fixture_digest(payload: dict[str, object]) -> None:
    payload.pop("semantic_sha256", None)
    canonical = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload["semantic_sha256"] = hashlib.sha256(canonical).hexdigest()


def _observer_envelope(fixture: Any) -> dict[str, object]:
    manifest = fixture.manifest
    return {
        "schema": "plumber.logseq-db.observer-structure/v1",
        "static_record_sha256": "a" * 64,
        "signer_fingerprint": "caller-supplied-signer",
        "signature": "signature-looking-but-unverified",
        "artifact": {
            "dmg_sha256": "b" * 64,
            "app_asar_sha256": "c" * 64,
            "archived_entry_path": "js/logseq-cli.js",
            "archive_offset": 80054483,
            "archive_size": 817565,
            "entry_sha256": "d" * 64,
        },
        "launcher": {
            "identity": "packaged-interpreter",
            "sha256": "e" * 64,
            "argv_prefix": ["interpreter", "js/logseq-cli.js"],
        },
        "db0_policy": "forbidden_state_changes:all",
        "protected_roots": [
            {"kind": kind, "state": "absent", "reference": f"{kind}-declared"}
            for kind in (
                "user_graph",
                "default_logseq",
                "account",
                "sync",
                "config",
                "working_directory",
            )
        ],
        "fixture": {
            "semantic_sha256": manifest.semantic_sha256,
            "graph_id": manifest.graph_id,
            "page_id": manifest.page_id,
            "root_block_id": manifest.root_block_id,
            "source_revision": manifest.source_revision,
        },
        "observer_sha256": "f" * 64,
        "config_sha256": "0" * 64,
        "limits": {
            "max_fixture_bytes": manifest.raw_byte_length,
            "max_nodes": len(manifest.nodes),
            "max_depth": manifest.max_depth,
        },
        "commands": [
            "property_inventory",
            "graph_info",
            "page_show",
            "root_show",
            "server_list",
        ],
    }


def test_parses_a_digest_bound_ordered_synthetic_fixture() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")

    candidate = module.parse_fixture_structure_bytes(
        json.dumps(_fixture_payload(), ensure_ascii=True).encode("utf-8")
    )

    assert candidate.manifest.graph_id == "synthetic-graph"
    assert candidate.manifest.nodes[1].parent_id == "root"
    assert candidate.manifest.nodes[1].text == "Child"


def test_parses_only_an_unverified_structural_observer_envelope() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    fixture = module.parse_fixture_structure_bytes(
        json.dumps(_fixture_payload(), ensure_ascii=True).encode("utf-8")
    )
    envelope = _observer_envelope(fixture)

    candidate = module.parse_observer_structure_bytes(
        json.dumps(envelope, ensure_ascii=True).encode("utf-8"), fixture
    )

    assert candidate.authentication_state == "unverified"
    assert candidate.signer_fingerprint == "caller-supplied-signer"


def test_rejects_a_fixture_whose_selected_root_is_missing() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    payload["root_block_id"] = "missing"
    _bind_fixture_digest(payload)

    with pytest.raises(module.FixtureStructureError, match="root"):
        module.parse_fixture_structure_bytes(json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def test_rejects_oversized_fixture_bytes_before_json_decoding() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")

    with pytest.raises(module.FixtureStructureError, match="byte limit"):
        module.parse_fixture_structure_bytes(b"x" * (262_144 + 1))


def test_rejects_nonfinite_json_literals_before_schema_validation() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    payload["nodes"] = [{"id": "root", "parent_id": None, "ordinal": float("nan"), "text": "Root"}]
    _bind_fixture_digest(payload)
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=True).encode("utf-8")

    with pytest.raises(module.FixtureStructureError, match="non-finite"):
        module.parse_fixture_structure_bytes(raw)


def test_rejects_floating_point_json_numbers_before_schema_validation() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    payload["nodes"] = [{"id": "root", "parent_id": None, "ordinal": 0.0, "text": "Root"}]
    _bind_fixture_digest(payload)

    with pytest.raises(module.FixtureStructureError, match="floating-point"):
        module.parse_fixture_structure_bytes(json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def test_rejects_subtree_that_reenters_a_closed_preorder_branch() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    payload["nodes"] = [
        {"id": "root", "parent_id": None, "ordinal": 0, "text": "Root"},
        {"id": "left", "parent_id": "root", "ordinal": 0, "text": "Left"},
        {"id": "right", "parent_id": "root", "ordinal": 1, "text": "Right"},
        {"id": "left-child", "parent_id": "left", "ordinal": 0, "text": "Late child"},
    ]
    _bind_fixture_digest(payload)

    with pytest.raises(module.FixtureStructureError, match="depth-first"):
        module.parse_fixture_structure_bytes(json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def test_accepts_identifiers_by_unicode_characters_and_text_by_utf8_bytes() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    payload["graph_id"] = "é" * 128
    payload["page"] = {"title": "é" * 2_000}
    payload["nodes"] = [{"id": "root", "parent_id": None, "ordinal": 0, "text": "x" * 16_384}]
    _bind_fixture_digest(payload)

    candidate = module.parse_fixture_structure_bytes(
        json.dumps(payload, ensure_ascii=True).encode("utf-8")
    )

    assert candidate.manifest.graph_id == "é" * 128
    assert candidate.manifest.page_title == "é" * 2_000


def test_rejects_observer_limits_smaller_than_the_bound_fixture() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    fixture = module.parse_fixture_structure_bytes(
        json.dumps(_fixture_payload(), ensure_ascii=True).encode("utf-8")
    )
    envelope = _observer_envelope(fixture)
    envelope["limits"] = {
        "max_fixture_bytes": fixture.manifest.raw_byte_length,
        "max_nodes": 1,
        "max_depth": fixture.manifest.max_depth,
    }

    with pytest.raises(module.ObserverStructureError, match="max_nodes"):
        module.parse_observer_structure_bytes(
            json.dumps(envelope, ensure_ascii=True).encode("utf-8"), fixture
        )


def test_observer_decode_failure_uses_observer_error_domain() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    fixture = module.parse_fixture_structure_bytes(
        json.dumps(_fixture_payload(), ensure_ascii=True).encode("utf-8")
    )

    with pytest.raises(module.ObserverStructureError):
        module.parse_observer_structure_bytes(b'{"schema":', fixture)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":"one","schema":"two"}',
        b'{"schema":"plumber.logseq-db.observer-structure/v1"} {}',
    ],
)
def test_observer_duplicate_or_trailing_json_uses_observer_error_domain(raw: bytes) -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    fixture = module.parse_fixture_structure_bytes(
        json.dumps(_fixture_payload(), ensure_ascii=True).encode("utf-8")
    )

    with pytest.raises(module.ObserverStructureError):
        module.parse_observer_structure_bytes(raw, fixture)


def test_rejects_fixture_beyond_depth_ceiling() -> None:
    module = importlib.import_module("src.graph.logseq_db_observer_structure")
    payload = _fixture_payload()
    nodes: list[dict[str, object]] = []
    parent_id: str | None = None
    for index in range(65):
        node_id = f"node-{index}"
        nodes.append({"id": node_id, "parent_id": parent_id, "ordinal": 0, "text": node_id})
        parent_id = node_id
    payload["root_block_id"] = "node-0"
    payload["nodes"] = nodes
    _bind_fixture_digest(payload)

    with pytest.raises(module.FixtureStructureError, match="depth"):
        module.parse_fixture_structure_bytes(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
