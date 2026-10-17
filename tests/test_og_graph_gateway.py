"""Synthetic private descriptor and one-capture composition controls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import pytest
from matryca_plumber.graph_gateway.bootstrap import GatewayError
from matryca_plumber.graph_gateway.profile import LIMITS, _admit_descriptor, _load_descriptor
from matryca_plumber.graph_gateway.runtime import _snapshot

from tests.test_og_graph_gateway_wire import _inputs


def _descriptor() -> dict[str, Any]:
    """Hand-authored private test data, never a packaged descriptor or artifact identity."""
    return {
        "profile": "plumber.og.operational/v1",
        "qualification": "unqualified",
        "source_mode": "og_markdown",
        "operations": ["graph.identify", "graph.topology.snapshot.complete"],
        "wire": {
            "read": {"id": "read-1", "producer_profile_id": "rp", "consumer_profile_id": "rc"},
            "topology": {
                "id": "topology-1",
                "producer_profile_id": "tp",
                "consumer_profile_id": "tc",
            },
        },
        "bounds": dict(LIMITS),
        "matrix": [
            {"system": system, "machine": machine, "python": version, "state": "planned"}
            for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
            for version in ("3.12", "3.13")
        ],
        "dependencies": {"profile_id": "og-v1-parser-1.9.0", "parser": "1.9.0"},
        "schemas": {
            "read": "250438c57580c811c3e10b2a59089ffbb23ea2f1f66c4c53acc8ace0a9ee8569",
            "topology": "613f765376f2091b3dad2569ce19d9931f455b026f5ed495178526e87da1397a",
        },
        "resource_digests": {
            "manifest": "0" * 64,
            "dependency_profile": "0" * 64,
            "requirements": "0" * 64,
            "fixture_manifest": "0" * 64,
            "golden": "0" * 64,
            "tck_cases": "0" * 64,
        },
        "code_modules": [
            {"path": "consumer.py", "sha256": "0" * 64},
            {"path": "tck.py", "sha256": "0" * 64},
        ],
    }


def _bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_descriptor_admission_binds_original_bytes_not_reserialization() -> None:
    data = json.dumps(_descriptor(), indent=2).encode() + b"\n"
    expected = hashlib.sha256(data).hexdigest()
    profile = _admit_descriptor(data, expected)
    assert profile is not None, "descriptor admission missing"
    assert profile.descriptor_sha256 == expected
    assert profile.document == _descriptor()
    with pytest.raises(GatewayError, match="expectation_mismatch"):
        _admit_descriptor(data, "0" * 64)


@pytest.mark.parametrize(
    "data", [b"{}", b'{"profile":1,"profile":2}', b"{} {}", b"\xff", b"[1]", b"x" * 65_537]
)
def test_descriptor_rejects_malformed_duplicate_trailing_and_oversized_data(data: bytes) -> None:
    with pytest.raises(GatewayError):
        _admit_descriptor(data, None)


@pytest.mark.parametrize(
    "fault", ["unknown", "qualified", "db", "write", "bound", "bool", "matrix", "parser"]
)
def test_descriptor_cannot_widen_or_claim_qualified_support(fault: str) -> None:
    descriptor = _descriptor()
    if fault == "unknown":
        descriptor["secret"] = "PRIVATE-CANARY"
    elif fault == "qualified":
        descriptor["qualification"] = "qualified"
    elif fault == "db":
        descriptor["source_mode"] = "db"
    elif fault == "write":
        descriptor["operations"].append("page.write")
    elif fault == "bound":
        descriptor["bounds"]["max_nodes"] += 1
    elif fault == "bool":
        descriptor["bounds"]["max_files"] = True
    elif fault == "matrix":
        descriptor["matrix"][0]["system"] = "Windows"
    else:
        descriptor["dependencies"]["parser"] = "1.11.0"
    with pytest.raises(GatewayError) as failure:
        _admit_descriptor(_bytes(descriptor), None)
    assert "PRIVATE-CANARY" not in str(failure.value)


def test_production_descriptor_is_present_and_remains_unqualified() -> None:
    profile = _load_descriptor(None)
    assert profile.document["qualification"] == "unqualified"
    assert profile.document["source_mode"] == "og_markdown"
    assert profile.document["code_modules"] == [
        {"path": "consumer.py", "sha256": profile.document["code_modules"][0]["sha256"]},
        {"path": "tck.py", "sha256": profile.document["code_modules"][1]["sha256"]},
    ]


def test_gateway_delegates_exactly_one_capture_and_reuses_its_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.agent import og_topology_session_composition as composition
    from src.agent.og_topology_session_composition import OgGraphTopologySessionReader
    from src.graph.session_read_models import (
        GraphReadCapability,
        GraphSession,
        GraphSourceIdentity,
        GraphTopologyCapability,
    )
    from src.graph.session_read_service import GraphSessionReadService
    from src.graph.session_topology_models import GraphTopologyResult

    profile, versions, session_data, _, topology = _inputs()
    session = GraphSession.from_source(
        session_id=session_data["id"],
        source=GraphSourceIdentity(
            graph_id=session_data["graph_id"],
            source_revision=session_data["source_revision"],
        ),
        capabilities=frozenset(
            {
                GraphReadCapability.GRAPH_IDENTIFY,
                GraphTopologyCapability.GRAPH_TOPOLOGY_SNAPSHOT_COMPLETE,
            }
        ),
    )
    reader = GraphSessionReadService(
        session, topology=GraphTopologyResult.model_validate(topology["result"])
    )
    captures: list[Path] = []

    def create(graph_root: Path) -> OgGraphTopologySessionReader:
        captures.append(graph_root)
        return OgGraphTopologySessionReader(session, reader)

    monkeypatch.setattr(composition, "create_og_topology_session_reader", create)
    output = _snapshot(Path("/synthetic/not-opened"), profile, versions)
    assert isinstance(output, dict), "one-capture gateway composition missing"
    assert captures == [Path("/synthetic/not-opened")]
    assert output["read"]["session"]["id"] == output["topology"]["session"]["id"] == session.id


@pytest.mark.parametrize("code", ["source_rejected", "bounds_exceeded", "source_changed"])
def test_gateway_maps_typed_source_errors_without_matching_messages(
    monkeypatch: pytest.MonkeyPatch,
    code: Literal["source_rejected", "bounds_exceeded", "source_changed"],
) -> None:
    from src.agent import og_topology_session_composition as composition
    from src.agent.og_parser_identity_adapter import _OgSnapshotReadError

    def reject(graph_root: Path) -> None:
        raise _OgSnapshotReadError(code, "PRIVATE-CANARY /private/user/path")

    monkeypatch.setattr(composition, "create_og_topology_session_reader", reject)
    profile, versions, *_ = _inputs()
    with pytest.raises(GatewayError, match=code) as failure:
        _snapshot(Path("/synthetic/not-opened"), profile, versions)
    assert "PRIVATE-CANARY" not in str(failure.value)
