"""Pure mapping and bounded serialization for the existing read/topology schemas."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any, cast

from .bootstrap import GatewayError
from .profile import LIMITS, PROFILE_ID, _Profile

_READ = "plumber.graph.read/v1"
_TOPOLOGY = "plumber.graph.topology/v1"
_OPERATIONS = {"graph.identify", "graph.topology.snapshot.complete"}
_OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


def _object(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise GatewayError("source_rejected")
    return cast(dict[str, Any], value)


def _token(value: object) -> str:
    if type(value) is not str or len(value) > 128 or _OPAQUE.fullmatch(value) is None:
        raise GatewayError("source_rejected")
    return value


def _schema(value: object) -> None:
    if type(value) is not int or value != 1:
        raise GatewayError("source_rejected")


def _nodes(value: object) -> list[dict[str, Any]]:
    """Verify complete preorder with an open-ancestor stack and sibling counters."""
    if type(value) is not list:
        raise GatewayError("source_rejected")
    if len(value) > LIMITS["max_nodes"]:
        raise GatewayError("bounds_exceeded")
    seen: set[str] = set()
    ancestors: list[str] = []
    ordinals: dict[str | None, int] = {}
    result: list[dict[str, Any]] = []
    for raw in value:
        node = _object(raw, {"id", "kind", "parent_id", "ordinal"})
        identifier = _token(node["id"])
        parent = node["parent_id"]
        ordinal = node["ordinal"]
        if identifier in seen or type(ordinal) is not int or ordinal < 0:
            raise GatewayError("source_rejected")
        if node["kind"] == "page":
            if parent is not None:
                raise GatewayError("source_rejected")
            ancestors.clear()
        elif node["kind"] == "block":
            parent = _token(parent)
            if parent not in ancestors:
                raise GatewayError("source_rejected")
            del ancestors[ancestors.index(parent) + 1 :]
            if len(ancestors) > LIMITS["max_block_depth"]:
                raise GatewayError("bounds_exceeded")
        else:
            raise GatewayError("source_rejected")
        if ordinal != ordinals.get(parent, 0):
            raise GatewayError("source_rejected")
        ordinals[parent] = ordinal + 1
        seen.add(identifier)
        ancestors.append(identifier)
        result.append(
            {"id": identifier, "kind": node["kind"], "parent_id": parent, "ordinal": ordinal}
        )
    return result


def _edges(value: object, nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    if type(value) is not list:
        raise GatewayError("source_rejected")
    if len(value) > LIMITS["max_edges"]:
        raise GatewayError("bounds_exceeded")
    identifiers = {node["id"] for node in nodes}
    previous: tuple[str, str, str] | None = None
    result: list[dict[str, str]] = []
    for raw in value:
        edge = _object(raw, {"kind", "source_id", "target_id"})
        source, target = _token(edge["source_id"]), _token(edge["target_id"])
        ordered = ("reference", source, target)
        if (
            edge["kind"] != "reference"
            or source not in identifiers
            or target not in identifiers
            or (previous is not None and ordered <= previous)
        ):
            raise GatewayError("source_rejected")
        previous = ordered
        result.append({"kind": "reference", "source_id": source, "target_id": target})
    return result


def _response(
    value: object, session: dict[str, Any], *, contract: str, operation: str, reason: str
) -> dict[str, Any]:
    response = _object(
        value,
        {
            "contract_id",
            "schema_version",
            "session_id",
            "graph_id",
            "source_revision",
            "operation",
            "outcome",
            "reason",
            "result",
        },
    )
    _schema(response["schema_version"])
    if (
        response["contract_id"] != contract
        or response["session_id"] != session["id"]
        or response["graph_id"] != session["graph_id"]
        or response["source_revision"] != session["source_revision"]
        or response["operation"] != operation
        or response["outcome"] != "pass"
        or response["reason"] != reason
    ):
        raise GatewayError("source_rejected")
    return response


def _snapshot_document(
    profile: _Profile,
    versions: Mapping[str, str],
    session: Mapping[str, Any],
    identity: Mapping[str, Any],
    topology: Mapping[str, Any],
) -> dict[str, Any]:
    """Supply unchanged operation-result envelopes without exposing semantic content."""
    session_value = _object(
        session,
        {
            "contract_id",
            "schema_version",
            "id",
            "graph_id",
            "source_revision",
            "mode",
            "capabilities",
            "state",
            "expires_at_monotonic",
        },
    )
    _schema(session_value["schema_version"])
    for key in ("id", "graph_id", "source_revision"):
        _token(session_value[key])
    capabilities = session_value["capabilities"]
    if (
        session_value["contract_id"] != _READ
        or session_value["mode"] != "og"
        or session_value["state"] != "active"
        or session_value["expires_at_monotonic"] is not None
        or type(capabilities) is not list
        or len(capabilities) != 2
        or any(type(item) is not str for item in capabilities)
        or set(capabilities) != _OPERATIONS
    ):
        raise GatewayError("source_rejected")
    version_values = _object(versions, {"plumber", "parser", "python"})
    if (
        any(
            type(value) is not str
            or len(value) > 128
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*", value) is None
            for value in version_values.values()
        )
        or version_values["parser"] != "1.9.0"
    ):
        raise GatewayError("source_rejected")
    if re.fullmatch(r"3\.(12|13)\.[0-9]+", version_values["python"]) is None:
        raise GatewayError("source_rejected")
    if re.fullmatch(r"[0-9a-f]{64}", profile.descriptor_sha256) is None:
        raise GatewayError("source_rejected")
    for identifier in (
        profile.read_id,
        profile.topology_id,
        profile.read_producer_id,
        profile.read_consumer_id,
        profile.topology_producer_id,
        profile.topology_consumer_id,
    ):
        _token(identifier)
    read = _response(
        identity,
        session_value,
        contract=_READ,
        operation="graph.identify",
        reason="og-parser-identity",
    )
    read_result = _object(read["result"], {"graph_id"})
    if read_result["graph_id"] != session_value["graph_id"]:
        raise GatewayError("source_rejected")
    complete = _response(
        topology,
        session_value,
        contract=_TOPOLOGY,
        operation="graph.topology.snapshot.complete",
        reason="og-parser-snapshot",
    )
    result = _object(
        complete["result"],
        {"topology_id", "complete", "nodes", "edges", "provenance"},
    )
    topology_id = _token(result["topology_id"])
    if result["complete"] is not True:
        raise GatewayError("source_rejected")
    provenance = _object(
        result["provenance"],
        {"kind", "source_contract_id", "source_schema_version", "source_revision"},
    )
    _schema(provenance["source_schema_version"])
    if (
        provenance["kind"] != "derived-structural"
        or provenance["source_contract_id"] != _READ
        or provenance["source_revision"] != session_value["source_revision"]
    ):
        raise GatewayError("source_rejected")
    nodes = _nodes(result["nodes"])
    edges = _edges(result["edges"], nodes)
    common = {
        "fixture_kind": "operation-result",
        "schema_version": 1,
        "graph_id": session_value["graph_id"],
        "source_revision": session_value["source_revision"],
        "outcome": "pass",
    }
    return {
        "profile": PROFILE_ID,
        "descriptor_sha256": profile.descriptor_sha256,
        "versions": dict(version_values),
        "read": {
            **common,
            "id": profile.read_id,
            "contract_id": _READ,
            "producer_profile_id": profile.read_producer_id,
            "consumer_profile_id": profile.read_consumer_id,
            "session": {"id": session_value["id"], "state": "active"},
            "operation": "graph.identify",
            "reason": read["reason"],
            "result": {"graph_id": session_value["graph_id"]},
        },
        "topology": {
            **common,
            "id": profile.topology_id,
            "contract_id": _TOPOLOGY,
            "producer_profile_id": profile.topology_producer_id,
            "consumer_profile_id": profile.topology_consumer_id,
            "request": {"session_id": session_value["id"], "graph_id": session_value["graph_id"]},
            "session": {
                "contract_id": _READ,
                "schema_version": 1,
                "id": session_value["id"],
                "state": "active",
            },
            "operation": "graph.topology.snapshot.complete",
            "reason": complete["reason"],
            "result": {
                "topology_id": topology_id,
                "complete": True,
                "nodes": nodes,
                "edges": edges,
                "provenance": dict(provenance),
            },
        },
    }


def _encode(value: object, *, max_bytes: int = 4_194_304) -> bytes:
    """Check finite structure first, then enforce an incremental UTF-8 byte ceiling."""
    if type(max_bytes) is not int or not 0 < max_bytes <= LIMITS["max_stdout_bytes"]:
        raise GatewayError("bounds_exceeded")
    stack: list[tuple[object, int, bool]] = [(value, 0, False)]
    active: set[int] = set()
    items = 0
    characters = 0
    while stack:
        current, depth, leaving = stack.pop()
        if leaving:
            active.remove(id(current))
            continue
        items += 1
        if items > 65_536 or depth > 64:
            raise GatewayError("bounds_exceeded")
        if type(current) is dict or type(current) is list:
            if id(current) in active:
                raise GatewayError("source_rejected")
            if items + len(current) + len(stack) > 65_536:
                raise GatewayError("bounds_exceeded")
            active.add(id(current))
            stack.append((current, depth, True))
            if type(current) is dict:
                for key, child in current.items():
                    if type(key) is not str:
                        raise GatewayError("source_rejected")
                    characters += len(key)
                    stack.append((child, depth + 1, False))
            else:
                stack.extend((child, depth + 1, False) for child in current)
        elif type(current) is str:
            characters += len(current)
        elif type(current) is int:
            if current.bit_length() > 64:
                raise GatewayError("bounds_exceeded")
        elif type(current) is float:
            if not math.isfinite(current):
                raise GatewayError("source_rejected")
        elif current is not None and type(current) is not bool:
            raise GatewayError("source_rejected")
        if characters > max_bytes:
            raise GatewayError("bounds_exceeded")
    encoded = bytearray()
    try:
        encoder = json.JSONEncoder(
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        for chunk in encoder.iterencode(value):
            data = chunk.encode("utf-8")
            if len(encoded) + len(data) + 1 > max_bytes:
                raise GatewayError("bounds_exceeded")
            encoded.extend(data)
    except GatewayError:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise GatewayError("source_rejected") from None
    encoded.extend(b"\n")
    return bytes(encoded)
