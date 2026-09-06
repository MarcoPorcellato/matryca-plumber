"""DB-0 protocol and fixture-boundary tests for the official Logseq host."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "tests" / "compatibility" / "logseq_db_native"


def _manifest() -> dict[str, Any]:
    payload = json.loads((CONTRACT_ROOT / "manifest.json").read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)


def test_manifest_freezes_read_only_transport_and_outcomes() -> None:
    manifest = _manifest()
    assert manifest["profile_id"] == "plumber.logseq.db.native.capability-discovery/v1"
    assert manifest["status"] == "test_only/unbound"
    assert (
        manifest["tracking_issue"]
        == "https://github.com/MarcoPorcellato/matryca-plumber/issues/491"
    )
    assert manifest["gateway"] == "matryca-plumber"
    assert manifest["transport_order"] == ["bundled_cli", "plugin_sdk", "mcp_stdio"]
    assert manifest["blocked_transports"] == ["mcp_http"]
    assert manifest["terminal_outcomes"] == [
        "supported",
        "capability_no_go",
        "upstream_blocked",
    ]
    assert manifest["required_operations"] == [
        "graph_identification",
        "page_read",
        "complete_ordered_block_subtree_read",
    ]
    assert manifest["upstream_http_issue"] == "https://github.com/logseq/db-test/issues/1101"


def test_manifest_binds_exact_artifact_source_fixture_and_probe_fields() -> None:
    manifest = _manifest()
    for field in ("artifact", "source", "fixture_set", "probe", "bindings"):
        assert isinstance(manifest[field], dict)
        assert manifest[field]
    assert manifest["artifact"]["sha256"] is None
    assert manifest["source"]["repository"] == "logseq/logseq"
    assert manifest["fixture_set"]["status"] == "synthetic_only"
    assert manifest["probe"]["status"] == "not_executed"
    assert manifest["bindings"] == {
        "host_release": None,
        "host_version": None,
        "artifact_digest": None,
        "embedded_revision": None,
        "platform": "macos-arm64",
        "probe_commit": None,
        "fixture_digest": None,
        "graph": None,
        "source_revision": None,
        "session_identity": None,
    }


def test_manifest_forbids_unsafe_scope_expansion() -> None:
    manifest = _manifest()
    assert manifest["forbidden_scope"] == [
        "internal_sqlite",
        "parser_db_path",
        "markdown_fallback",
        "graph_switch",
        "server_replacement",
        "writes",
        "events",
        "shadow",
        "sync",
        "import_export",
    ]
    assert manifest["subtree_requirements"] == [
        "stable_ids",
        "parentage",
        "sibling_order",
        "content",
        "supported_typed_properties",
    ]
    assert manifest["bounds"] == {
        "max_nodes": None,
        "max_output_bytes": None,
        "forbidden_state_changes": "all",
    }


@pytest.mark.parametrize(
    "fixture_name",
    [
        "rejected-missing-required-operation-v1.json",
        "rejected-http-transport-v1.json",
        "rejected-direct-internal-db-v1.json",
        "rejected-missing-artifact-identity-v1.json",
    ],
)
def test_negative_fixtures_are_explicit_and_content_free(fixture_name: str) -> None:
    fixture = json.loads((CONTRACT_ROOT / "fixtures" / fixture_name).read_text(encoding="utf-8"))
    assert set(fixture) == {
        "fixture_id",
        "classification",
        "reason_code",
        "evidence_status",
        "operation_results",
        "reason",
    }
    assert fixture["classification"] == "rejected_candidate"
    assert fixture["evidence_status"] == "synthetic_only"
    assert "content" not in fixture
    assert set(fixture["operation_results"]) == {
        "graph_identification",
        "page_read",
        "complete_ordered_block_subtree_read",
    }
    assert fixture["reason"]
    assert fixture["reason_code"]


def test_all_manifest_fixtures_are_enumerated_and_unique() -> None:
    manifest = _manifest()
    fixture_paths = manifest["fixture_set"]["fixtures"]
    assert len(fixture_paths) == len(set(fixture_paths))
    assert set(fixture_paths) == {
        "fixtures/rejected-missing-required-operation-v1.json",
        "fixtures/rejected-http-transport-v1.json",
        "fixtures/rejected-direct-internal-db-v1.json",
        "fixtures/rejected-missing-artifact-identity-v1.json",
    }
    actual_fixture_paths = {
        f"fixtures/{path.name}" for path in (CONTRACT_ROOT / "fixtures").glob("*.json")
    }
    assert actual_fixture_paths == set(fixture_paths)
    expected = {
        "rejected-missing-required-operation-v1.json": "missing_required_operation",
        "rejected-http-transport-v1.json": "http_transport_blocked",
        "rejected-direct-internal-db-v1.json": "internal_db_forbidden",
        "rejected-missing-artifact-identity-v1.json": "artifact_identity_missing",
    }
    for path in fixture_paths:
        payload = json.loads((CONTRACT_ROOT / path).read_text(encoding="utf-8"))
        assert payload["classification"] == "rejected_candidate"
        assert "outcome" not in payload
        assert payload["reason_code"] == expected[Path(path).name]


def test_no_supported_fixture_is_committed_before_runtime_evidence() -> None:
    manifest = _manifest()
    assert manifest["fixture_set"]["supported_fixture"] is None
    assert manifest["probe"]["status"] == "not_executed"
