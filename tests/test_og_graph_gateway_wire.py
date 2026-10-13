"""Synthetic controls for strict, content-free gateway wire mapping."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from matryca_plumber.graph_gateway.bootstrap import GatewayError
from matryca_plumber.graph_gateway.profile import _Profile
from matryca_plumber.graph_gateway.wire import _encode, _snapshot_document


def _inputs() -> tuple[_Profile, dict[str, str], dict[str, Any], dict[str, Any], dict[str, Any]]:
    profile = _Profile({}, "a" * 64, "read-1", "topology-1", "rp", "rc", "tp", "tc")
    versions = {"plumber": "2.0.1rc4", "parser": "1.9.0", "python": "3.12.13"}
    session = {
        "contract_id": "plumber.graph.read/v1",
        "schema_version": 1,
        "id": "session-1",
        "graph_id": "graph-1",
        "source_revision": "revision-1",
        "mode": "og",
        "capabilities": ["graph.identify", "graph.topology.snapshot.complete"],
        "state": "active",
        "expires_at_monotonic": None,
    }
    identity = {
        "contract_id": "plumber.graph.read/v1",
        "schema_version": 1,
        "session_id": "session-1",
        "graph_id": "graph-1",
        "source_revision": "revision-1",
        "operation": "graph.identify",
        "outcome": "pass",
        "reason": "og-parser-identity",
        "result": {"graph_id": "graph-1"},
    }
    topology = {
        **identity,
        "contract_id": "plumber.graph.topology/v1",
        "operation": "graph.topology.snapshot.complete",
        "reason": "og-parser-snapshot",
        "result": {
            "topology_id": "topology-1",
            "complete": True,
            "nodes": [
                {"id": "p", "kind": "page", "parent_id": None, "ordinal": 0},
                {"id": "b", "kind": "block", "parent_id": "p", "ordinal": 0},
                {"id": "c", "kind": "block", "parent_id": "b", "ordinal": 0},
                {"id": "d", "kind": "block", "parent_id": "p", "ordinal": 1},
            ],
            "edges": [{"kind": "reference", "source_id": "d", "target_id": "b"}],
            "provenance": {
                "kind": "derived-structural",
                "source_contract_id": "plumber.graph.read/v1",
                "source_schema_version": 1,
                "source_revision": "revision-1",
            },
        },
    }
    return profile, versions, session, identity, topology


def test_wire_supplies_required_existing_schema_fields() -> None:
    output = _snapshot_document(*_inputs())
    assert isinstance(output, dict), "missing complete schema-preserving gateway response"
    assert set(output) == {"profile", "descriptor_sha256", "versions", "read", "topology"}
    for contract, key in (("read", "read"), ("topology", "topology")):
        schema_path = (
            Path(__file__).resolve().parents[1]
            / "contracts"
            / f"plumber.graph.{contract}"
            / "v1/schema.json"
        )
        with schema_path.open(encoding="utf-8") as handle:
            schema = json.load(handle)
        assert list(Draft202012Validator(schema).iter_errors(output[key])) == []
    assert output["read"]["session"]["id"] == output["topology"]["request"]["session_id"]
    assert output["topology"]["session"]["contract_id"] == "plumber.graph.read/v1"


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("identity", "session_id", "foreign"),
        ("identity", "graph_id", "foreign"),
        ("identity", "source_revision", "foreign"),
        ("identity", "schema_version", True),
        ("topology", "session_id", "foreign"),
        ("topology", "graph_id", "foreign"),
        ("topology", "source_revision", "foreign"),
        ("topology", "outcome", "unsupported"),
        ("session", "state", "closed"),
        ("session", "mode", "db"),
        ("session", "expires_at_monotonic", 1.0),
    ],
)
def test_wire_rejects_binding_or_contract_mismatch(section: str, field: str, value: object) -> None:
    profile, versions, session, identity, topology = _inputs()
    {"session": session, "identity": identity, "topology": topology}[section][field] = value
    with pytest.raises(GatewayError, match="source_rejected"):
        _snapshot_document(profile, versions, session, identity, topology)


@pytest.mark.parametrize("location", ["session", "identity", "result", "node", "edge"])
def test_wire_rejects_canary_semantic_fields(location: str) -> None:
    profile, versions, session, identity, topology = _inputs()
    targets = {
        "session": session,
        "identity": identity,
        "result": topology["result"],
        "node": topology["result"]["nodes"][0],
        "edge": topology["result"]["edges"][0],
    }
    targets[location]["text"] = "PRIVATE-CANARY-DO-NOT-EMIT"
    with pytest.raises(GatewayError) as failure:
        _snapshot_document(profile, versions, session, identity, topology)
    assert "PRIVATE-CANARY" not in str(failure.value)


@pytest.mark.parametrize(
    "fault", ["closed-subtree", "ordinal-bool", "gap", "duplicate", "orphan", "page-parent"]
)
def test_wire_requires_stack_verified_complete_preorder(fault: str) -> None:
    values = _inputs()
    nodes = values[4]["result"]["nodes"]
    if fault == "closed-subtree":
        nodes.append({"id": "e", "kind": "block", "parent_id": "b", "ordinal": 1})
    elif fault == "ordinal-bool":
        nodes[0]["ordinal"] = False
    elif fault == "gap":
        nodes[3]["ordinal"] = 2
    elif fault == "duplicate":
        nodes[3]["id"] = "b"
    elif fault == "orphan":
        nodes[1]["parent_id"] = "missing"
    else:
        nodes[0]["parent_id"] = "b"
    with pytest.raises(GatewayError, match="source_rejected"):
        _snapshot_document(*values)


@pytest.mark.parametrize("fault", ["incomplete", "truthy", "provenance", "unknown-edge", "repeat"])
def test_wire_requires_complete_bound_topology_and_unique_edges(fault: str) -> None:
    values = _inputs()
    result = values[4]["result"]
    if fault == "incomplete":
        result["complete"] = False
    elif fault == "truthy":
        result["complete"] = 1
    elif fault == "provenance":
        result["provenance"]["source_revision"] = "other"
    elif fault == "unknown-edge":
        result["edges"][0]["target_id"] = "other"
    else:
        result["edges"] *= 2
    with pytest.raises(GatewayError, match="source_rejected"):
        _snapshot_document(*values)


def test_wire_node_limit_is_inclusive_and_never_truncates() -> None:
    values = _inputs()
    result = values[4]["result"]
    result["nodes"] = [
        {"id": f"p{i}", "kind": "page", "parent_id": None, "ordinal": i} for i in range(1024)
    ]
    result["edges"] = []
    assert isinstance(_snapshot_document(*values), dict), "inclusive node limit rejected"
    result["nodes"].append({"id": "overflow", "kind": "page", "parent_id": None, "ordinal": 1024})
    with pytest.raises(GatewayError, match="bounds_exceeded"):
        _snapshot_document(*values)


def test_wire_canonical_encoding_counts_utf8_and_terminal_newline() -> None:
    value = {"z": "é", "a": [True, None, 1]}
    expected = b'{"a":[true,null,1],"z":"\xc3\xa9"}\n'
    assert _encode(value, max_bytes=len(expected)) == expected
    with pytest.raises(GatewayError, match="bounds_exceeded"):
        _encode(value, max_bytes=len(expected) - 1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, {"bad": object()}])
def test_wire_rejects_non_json_values_without_exception_text(value: object) -> None:
    with pytest.raises(GatewayError):
        _encode(value)


def test_wire_golden_excludes_session_and_graph_location() -> None:
    first = _inputs()
    second = copy.deepcopy(first)
    second[2]["id"] = second[3]["session_id"] = second[4]["session_id"] = "session-2"
    second[2]["graph_id"] = second[3]["graph_id"] = second[4]["graph_id"] = "graph-2"
    second[3]["result"]["graph_id"] = "graph-2"
    encoded = []
    for inputs in (first, second):
        document = _snapshot_document(*inputs)
        assert isinstance(document, dict), "mapper missing"
        payload = _encode(document["topology"]["result"])
        assert isinstance(payload, bytes), "canonical encoding missing"
        encoded.append(payload)
    assert (
        hashlib.sha256(encoded[0][:-1]).hexdigest() == hashlib.sha256(encoded[1][:-1]).hexdigest()
    )


def test_wire_edge_limit_is_inclusive_and_never_truncates() -> None:
    values = _inputs()
    result = values[4]["result"]
    result["nodes"] = [
        {"id": f"p{i:02}", "kind": "page", "parent_id": None, "ordinal": i} for i in range(65)
    ]
    result["edges"] = [
        {"kind": "reference", "source_id": f"p{i:02}", "target_id": f"p{j:02}"}
        for i in range(64)
        for j in range(64)
    ]
    assert isinstance(_snapshot_document(*values), dict), "inclusive reference edge limit rejected"
    result["edges"].append({"kind": "reference", "source_id": "p64", "target_id": "p00"})
    with pytest.raises(GatewayError, match="bounds_exceeded"):
        _snapshot_document(*values)


def test_wire_block_depth_limit_is_inclusive_and_never_truncates() -> None:
    values = _inputs()
    result = values[4]["result"]
    result["nodes"] = [{"id": "p", "kind": "page", "parent_id": None, "ordinal": 0}]
    result["edges"] = []
    for i in range(64):
        parent = "p" if i == 0 else f"b{i - 1}"
        result["nodes"].append({"id": f"b{i}", "kind": "block", "parent_id": parent, "ordinal": 0})
    assert isinstance(_snapshot_document(*values), dict), "inclusive block depth limit rejected"
    result["nodes"].append({"id": "overflow", "kind": "block", "parent_id": "b63", "ordinal": 0})
    with pytest.raises(GatewayError, match="bounds_exceeded"):
        _snapshot_document(*values)
