"""Private data boundary; no operational descriptor is shipped by this phase."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from .bootstrap import GatewayError

PROFILE_ID = "plumber.og.operational/v1"
MAX_DESCRIPTOR_BYTES = 65_536
LIMITS = {
    "max_files": 1_024,
    "max_file_bytes": 1_048_576,
    "max_source_bytes": 16_777_216,
    "max_nodes": 1_024,
    "max_edges": 4_096,
    "max_entries": 8_192,
    "max_directories": 1_024,
    "max_directory_depth": 32,
    "max_block_depth": 64,
    "max_stdout_bytes": 4_194_304,
    "max_stderr_bytes": 512,
}


@dataclass(frozen=True, slots=True)
class _Profile:
    """Admitted private descriptor view; declared roles are not compatibility evidence."""

    document: dict[str, Any]
    descriptor_sha256: str
    read_id: str
    topology_id: str
    read_producer_id: str
    read_consumer_id: str
    topology_producer_id: str
    topology_consumer_id: str


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise GatewayError("internal")
        result[key] = value
    return result


def _role(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value) is None
    ):
        raise GatewayError("internal")
    return value


def _admit_descriptor(data: bytes, expected_digest: str | None) -> _Profile:
    """Validate a finite private descriptor and bind its original bytes."""
    if type(data) is not bytes or len(data) > MAX_DESCRIPTOR_BYTES:
        raise GatewayError("bounds_exceeded")
    digest = hashlib.sha256(data).hexdigest()
    if expected_digest is not None and expected_digest != digest:
        raise GatewayError("expectation_mismatch")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        raise GatewayError("internal") from None
    if (
        not isinstance(document, dict)
        or set(document)
        != {
            "profile",
            "qualification",
            "source_mode",
            "operations",
            "wire",
            "bounds",
            "matrix",
            "dependencies",
        }
        or document["profile"] != PROFILE_ID
        or document["qualification"] != "unqualified"
        or document["source_mode"] != "og_markdown"
        or document["operations"] != ["graph.identify", "graph.topology.snapshot.complete"]
    ):
        raise GatewayError("internal")
    bounds = document["bounds"]
    if (
        not isinstance(bounds, dict)
        or set(bounds) != set(LIMITS)
        or any(
            type(bounds[key]) is not int or bounds[key] != value for key, value in LIMITS.items()
        )
    ):
        raise GatewayError("internal")
    matrix = [
        {"system": system, "machine": machine, "python": version, "state": "planned"}
        for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
        for version in ("3.12", "3.13")
    ]
    if document["matrix"] != matrix or document["dependencies"] != {
        "profile_id": "og-v1-parser-1.9.0",
        "parser": "1.9.0",
    }:
        raise GatewayError("internal")
    wire = document["wire"]
    if not isinstance(wire, dict) or set(wire) != {"read", "topology"}:
        raise GatewayError("internal")
    roles: list[str] = []
    for operation in ("read", "topology"):
        values = wire[operation]
        if not isinstance(values, dict) or set(values) != {
            "id",
            "producer_profile_id",
            "consumer_profile_id",
        }:
            raise GatewayError("internal")
        roles.extend(
            _role(values[key]) for key in ("id", "producer_profile_id", "consumer_profile_id")
        )
    return _Profile(document, digest, roles[0], roles[3], roles[1], roles[2], roles[4], roles[5])


def _load_descriptor(expected_digest: str | None) -> _Profile:
    """Read only the reserved package resource; never fall back to synthetic data."""
    try:
        resource = files("matryca_plumber.graph_gateway").joinpath(
            "resources", "og-v1", "descriptor.json"
        )
        with resource.open("rb") as handle:
            data = handle.read(MAX_DESCRIPTOR_BYTES + 1)
    except (OSError, TypeError):
        raise GatewayError("internal") from None
    return _admit_descriptor(data, expected_digest)
