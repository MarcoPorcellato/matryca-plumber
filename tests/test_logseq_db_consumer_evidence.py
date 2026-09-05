"""Executable admission tests for the outer Logseq DB consumer-evidence policy.

The assessor is test-only. It references the Trama contract authority without
deserializing or redefining Trama's request/result wire DTOs.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[1]
PROFILE = ROOT / "tests/compatibility/logseq_db/consumer-evidence-profile-v1.json"
FIXTURES = ROOT / "tests/compatibility/logseq_db/fixtures"
HEX_40 = re.compile(r"[0-9a-f]{40}")
HEX_64 = re.compile(r"[0-9a-f]{64}")


def load(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast(dict[str, Any], loaded)


def digest_for(basis: str) -> str:
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def commit_for(basis: str) -> str:
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:40]


def code(profile: dict[str, Any], name: str) -> str:
    return str(profile["reason_codes"][name])


def is_hex(value: object, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def safe_identifier(value: object, profile: dict[str, Any]) -> bool:
    admission = profile["admission"]
    if not isinstance(value, str) or not value or len(value) > admission["maximum_string_length"]:
        return False
    if re.fullmatch(admission["safe_identifier_pattern"], value) is None:
        return False
    lowered = value.lower()
    return not any(
        fragment in lowered for fragment in admission["forbidden_text_fragments"]
    ) and not any(lowered.startswith(prefix) for prefix in admission["forbidden_text_prefixes"])


def bounded_identifiers(value: object, profile: dict[str, Any]) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= profile["admission"]["maximum_array_items"]
        and all(safe_identifier(item, profile) for item in value)
    )


def safe_synthetic_basis(value: object, profile: dict[str, Any]) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > profile["admission"]["maximum_string_length"]
    ):
        return False
    lowered = value.lower()
    return (
        "/" not in value
        and "\\" not in value
        and not any(
            fragment in lowered for fragment in profile["admission"]["forbidden_text_fragments"]
        )
        and not any(
            lowered.startswith(prefix) for prefix in profile["admission"]["forbidden_text_prefixes"]
        )
    )


def synthetic_operation(
    profile: dict[str, Any],
    candidate_name: str,
    operation: str,
    graph_binding: str,
    source_reference: str,
) -> dict[str, Any]:
    basis = f"task-3 synthetic result v2: {candidate_name}:{operation}"
    evidence_digest = digest_for(basis)
    result_producer = "synthetic-result-producer"
    record: dict[str, Any] = {
        "operation": operation,
        "outcome": "success",
        "result_producer": result_producer,
        "result_capabilities": profile["required_operations"],
        "graph_binding": graph_binding,
        "trama_result_provenance": {
            "source_mode": "db_native",
            "authority": "logseq_db_native",
            "source_reference": source_reference,
            "producer": result_producer,
            "exercised_capabilities": [operation],
            "evidence_digest": evidence_digest,
        },
        "result_sha256": evidence_digest,
        "synthetic_result_basis": basis,
    }
    if operation == "block.subtree.read.complete":
        record["subtree_observation"] = {
            "complete": True,
            "ordered_parentage": True,
            "top_level_only": False,
        }
    return record


def synthetic_supported(profile: dict[str, Any], transport_kind: str = "cli") -> dict[str, Any]:
    """Build the only admitted case in memory; no supported fixture is committed."""

    candidate_name = "supported-candidate"
    fixture_basis = f"task-3 synthetic fixture v2: {candidate_name}"
    artifact_basis = f"task-3 synthetic artifact v2: {candidate_name}"
    trama_commit_basis = f"task-3 synthetic commit v2: {candidate_name}:trama"
    probe_commit_basis = f"task-3 synthetic commit v2: {candidate_name}:probe"
    graph_binding = "graph:synthetic-supported"
    source_reference = "profile:synthetic-supported-db-read"
    transport = {"kind": transport_kind}
    transport[profile["transport_identity"][transport_kind]] = (
        f"synthetic-{transport_kind}-identity"
    )
    return {
        "qualification_state": "supported",
        "scope": profile["admission"]["scope"],
        "direct_database_access": profile["admission"]["direct_database_access"],
        "source": {
            "contract_id": profile["trama_contract_reference"]["contract_id"],
            "accepted_contract_major": profile["trama_contract_reference"][
                "accepted_contract_major"
            ],
            "source_reference": profile["trama_authority_pin"]["commit"],
        },
        "limits": {"max_items": 1, "max_depth": 1, "timeout_seconds": 1},
        "uncertainty": [],
        "session": {
            "identity": "synthetic-session",
            "lifecycle": profile["admission"]["required_session_lifecycle"],
            "foreign": False,
            "stale": False,
        },
        "host": {
            "identity": "synthetic-session",
            "selected": True,
            "artifact_build_digest": digest_for(artifact_basis),
            "trama_commit": commit_for(trama_commit_basis),
            "probe_commit": commit_for(probe_commit_basis),
        },
        "synthetic_commit_bases": {
            "trama_commit": trama_commit_basis,
            "probe_commit": probe_commit_basis,
        },
        "synthetic_artifact_basis": artifact_basis,
        "synthetic_fixture_basis": fixture_basis,
        "fixture_digest": digest_for(fixture_basis),
        "graph_binding": graph_binding,
        "operation_evidence": [
            synthetic_operation(profile, candidate_name, operation, graph_binding, source_reference)
            for operation in profile["required_operations"]
        ],
        "transport": transport,
        "forbidden_actions": [],
        "forbidden_state_change": False,
    }


def assess_operation(
    record: object, evidence: dict[str, Any], profile: dict[str, Any]
) -> str | None:
    if not isinstance(record, dict):
        return code(profile, "operation_evidence")
    operation = record.get("operation")
    if (
        not safe_identifier(operation, profile)
        or record.get("outcome") != "success"
        or not safe_identifier(record.get("result_producer"), profile)
        or not bounded_identifiers(record.get("result_capabilities"), profile)
        or operation not in record["result_capabilities"]
        or record.get("graph_binding") != evidence.get("graph_binding")
        or not safe_identifier(record.get("graph_binding"), profile)
    ):
        return code(profile, "operation_evidence")

    provenance = record.get("trama_result_provenance")
    required = profile["admission"]["required_provenance_fields"]
    if not isinstance(provenance, dict) or any(name not in provenance for name in required):
        return code(profile, "operation_evidence")
    exercised = provenance["exercised_capabilities"]
    if (
        provenance["source_mode"] not in profile["admission"]["accepted_source_modes"]
        or provenance["authority"] not in profile["admission"]["accepted_authorities"]
        or not safe_identifier(provenance["source_reference"], profile)
        or provenance["producer"] != record["result_producer"]
        or not safe_identifier(provenance["producer"], profile)
        or not bounded_identifiers(exercised, profile)
        or not exercised
        or operation not in exercised
        or not set(exercised).issubset(record["result_capabilities"])
        or not is_hex(provenance["evidence_digest"], HEX_64)
    ):
        return code(profile, "operation_evidence")
    if record.get("result_sha256") != provenance["evidence_digest"]:
        return code(profile, "result_digest")
    result_basis = record.get("synthetic_result_basis")
    if result_basis is not None and (
        not safe_synthetic_basis(result_basis, profile)
        or digest_for(result_basis) != provenance["evidence_digest"]
    ):
        return code(profile, "operation_evidence")
    if operation == "block.subtree.read.complete":
        if record.get("subtree_observation") != {
            "complete": True,
            "ordered_parentage": True,
            "top_level_only": False,
        }:
            return code(profile, "subtree")
    elif "subtree_observation" in record:
        return code(profile, "operation_evidence")
    return None


def assess(evidence: dict[str, Any], profile: dict[str, Any]) -> str:
    """Return profile-declared stable reason codes; only supported evidence admits."""

    state = evidence.get("qualification_state")
    if state not in profile["allowed_qualification_states"] or state in {"deferred", "unverified"}:
        return code(profile, "qualification_state")
    admission = profile["admission"]
    source = evidence.get("source")
    if not isinstance(source, dict) or any(
        name not in source for name in admission["required_source_fields"]
    ):
        return code(profile, "contract")
    if (
        source["contract_id"] != profile["trama_contract_reference"]["contract_id"]
        or source["accepted_contract_major"]
        != profile["trama_contract_reference"]["accepted_contract_major"]
    ):
        return code(profile, "contract")
    if source["source_reference"] != profile["trama_authority_pin"]["commit"] or not is_hex(
        source["source_reference"], HEX_40
    ):
        return code(profile, "source")
    if evidence.get("scope") != admission["scope"]:
        return code(profile, "scope")
    if evidence.get("direct_database_access") is not admission["direct_database_access"]:
        return code(profile, "direct_database")

    limits = evidence.get("limits")
    limit_profile = admission["limits"]
    if not isinstance(limits, dict) or set(limits) != set(limit_profile):
        return code(profile, "limits")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > limit_profile[name]["maximum"]
        for name, value in limits.items()
    ):
        return code(profile, "limits")
    if not bounded_identifiers(evidence.get("uncertainty"), profile):
        return code(profile, "uncertainty")

    session = evidence.get("session")
    if (
        not isinstance(session, dict)
        or not safe_identifier(session.get("identity"), profile)
        or session.get("lifecycle") != admission["required_session_lifecycle"]
        or session.get("foreign") is not False
        or session.get("stale") is not False
    ):
        return code(profile, "session")
    forbidden_actions = evidence.get("forbidden_actions")
    if not isinstance(forbidden_actions, list):
        return code(profile, "forbidden_operation")
    if (
        not bounded_identifiers(forbidden_actions, profile)
        or any(action not in admission["forbidden_operations"] for action in forbidden_actions)
        or forbidden_actions
        or evidence.get("forbidden_state_change") is not False
    ):
        return code(profile, "forbidden_operation")

    host = evidence.get("host")
    if (
        not isinstance(host, dict)
        or host.get("identity") != session["identity"]
        or host.get("selected") is not True
        or not is_hex(host.get("artifact_build_digest"), HEX_64)
    ):
        return code(profile, "host")
    if not is_hex(host.get("trama_commit"), HEX_40) or not is_hex(host.get("probe_commit"), HEX_40):
        return code(profile, "future_commit")
    commit_bases = evidence.get("synthetic_commit_bases")
    if commit_bases is not None and (
        not isinstance(commit_bases, dict)
        or not safe_synthetic_basis(commit_bases.get("trama_commit"), profile)
        or not safe_synthetic_basis(commit_bases.get("probe_commit"), profile)
        or host["trama_commit"] != commit_for(commit_bases["trama_commit"])
        or host["probe_commit"] != commit_for(commit_bases["probe_commit"])
    ):
        return code(profile, "future_commit")
    artifact_basis = evidence.get("synthetic_artifact_basis")
    if artifact_basis is not None and (
        not safe_synthetic_basis(artifact_basis, profile)
        or host["artifact_build_digest"] != digest_for(artifact_basis)
    ):
        return code(profile, "artifact_digest")

    if not is_hex(evidence.get("fixture_digest"), HEX_64):
        return code(profile, "fixture_digest")
    fixture_basis = evidence.get("synthetic_fixture_basis")
    if fixture_basis is not None and (
        not safe_synthetic_basis(fixture_basis, profile)
        or evidence["fixture_digest"] != digest_for(fixture_basis)
    ):
        return code(profile, "fixture_digest")
    if not safe_identifier(evidence.get("graph_binding"), profile):
        return code(profile, "operation_evidence")

    records = evidence.get("operation_evidence")
    if not isinstance(records, list) or len(records) != len(profile["required_operations"]):
        return code(profile, "operation_set")
    operations = [record.get("operation") for record in records if isinstance(record, dict)]
    if len(operations) != len(records) or set(operations) != set(profile["required_operations"]):
        return code(profile, "operation_set")
    for record in records:
        failure = assess_operation(record, evidence, profile)
        if failure is not None:
            return failure

    transport = evidence.get("transport")
    if (
        not isinstance(transport, dict)
        or transport.get("kind") not in profile["transport_identity"]
    ):
        return code(profile, "transport")
    identity_key = profile["transport_identity"][transport["kind"]]
    if not safe_identifier(transport.get(identity_key), profile):
        return code(profile, "transport")
    if state != "supported":
        return code(profile, "qualification_state")
    return "accepted"


def mutate(candidate: dict[str, Any], path: str, value: Any) -> None:
    target: Any = candidate
    for name in path.split(".")[:-1]:
        target = target[int(name)] if name.isdigit() else target[name]
    target[path.split(".")[-1]] = value


def test_synthetic_supported_candidate_is_admitted_for_each_transport() -> None:
    profile = load(PROFILE)
    for transport_kind in profile["transport_identity"]:
        assert assess(synthetic_supported(profile, transport_kind), profile) == "accepted"


@pytest.mark.parametrize(
    ("path", "value", "reason_name"),
    [
        ("qualification_state", "unknown", "qualification_state"),
        ("source.accepted_contract_major", 2, "contract"),
        ("source.source_reference", "0" * 40, "source"),
        ("scope", "read-write", "scope"),
        ("direct_database_access", True, "direct_database"),
        ("limits", {}, "limits"),
        ("limits.max_items", 1001, "limits"),
        ("limits.max_items", True, "limits"),
        ("limits.max_items", "10", "limits"),
        ("uncertainty", [""], "uncertainty"),
        ("uncertainty", [1], "uncertainty"),
        ("uncertainty", ["x" * 97], "uncertainty"),
        ("uncertainty", ["file:private"], "uncertainty"),
        ("uncertainty", ["bounded"] * 9, "uncertainty"),
        ("session.foreign", True, "session"),
        ("session.stale", True, "session"),
        ("session.lifecycle", "closed", "session"),
        ("forbidden_actions", ["mutation"], "forbidden_operation"),
        ("forbidden_actions", [1], "forbidden_operation"),
        ("forbidden_actions", ["sync"] * 9, "forbidden_operation"),
        ("forbidden_state_change", True, "forbidden_operation"),
        ("host.identity", "other-session", "host"),
        ("host.selected", False, "host"),
        ("host.artifact_build_digest", "f" * 64, "artifact_digest"),
        ("host.probe_commit", "z" * 40, "future_commit"),
        ("fixture_digest", "f" * 64, "fixture_digest"),
        ("graph_binding", "profile:synthetic-supported-db-read", "operation_evidence"),
        ("operation_evidence", [], "operation_set"),
        ("operation_evidence.0.operation", "page.read", "operation_set"),
        ("operation_evidence.0.outcome", "unsupported", "operation_evidence"),
        ("operation_evidence.0.result_producer", "", "operation_evidence"),
        ("operation_evidence.0.result_capabilities", ["page.read"], "operation_evidence"),
        (
            "operation_evidence.0.trama_result_provenance.producer",
            "other-producer",
            "operation_evidence",
        ),
        (
            "operation_evidence.0.trama_result_provenance.exercised_capabilities",
            [],
            "operation_evidence",
        ),
        (
            "operation_evidence.0.trama_result_provenance.exercised_capabilities",
            ["page.read"],
            "operation_evidence",
        ),
        (
            "operation_evidence.0.trama_result_provenance.source_reference",
            "file:private",
            "operation_evidence",
        ),
        ("operation_evidence.0.graph_binding", "graph:other", "operation_evidence"),
        ("operation_evidence.0.result_sha256", "f" * 64, "result_digest"),
        (
            "operation_evidence.0.trama_result_provenance.evidence_digest",
            "f" * 64,
            "result_digest",
        ),
        ("operation_evidence.2.subtree_observation.complete", False, "subtree"),
        ("operation_evidence.2.subtree_observation.ordered_parentage", False, "subtree"),
        ("operation_evidence.2.subtree_observation.top_level_only", True, "subtree"),
    ],
)
def test_each_required_policy_condition_rejects_a_proven_admitted_candidate(
    path: str, value: Any, reason_name: str
) -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    assert assess(candidate, profile) == "accepted"
    mutate(candidate, path, value)
    assert assess(candidate, profile) == code(profile, reason_name)


@pytest.mark.parametrize("transport_kind", ["cli", "sdk", "mcp_stdio"])
def test_transport_identity_is_conditional_and_required(transport_kind: str) -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile, transport_kind)
    assert assess(candidate, profile) == "accepted"
    candidate["transport"].pop(profile["transport_identity"][transport_kind])
    assert assess(candidate, profile) == code(profile, "transport")


def test_same_trama_and_probe_commit_can_admit() -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    candidate.pop("synthetic_commit_bases")
    candidate["host"]["trama_commit"] = profile["trama_authority_pin"]["commit"]
    candidate["host"]["probe_commit"] = profile["trama_authority_pin"]["commit"]
    assert assess(candidate, profile) == "accepted"


def test_historical_contract_pin_can_be_recorded_as_a_future_source_commit() -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    candidate.pop("synthetic_commit_bases")
    candidate["host"]["trama_commit"] = profile["trama_authority_pin"]["commit"]
    assert assess(candidate, profile) == "accepted"


def test_provenance_source_reference_may_equal_graph_binding() -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    for record in candidate["operation_evidence"]:
        record["trama_result_provenance"]["source_reference"] = candidate["graph_binding"]
    assert assess(candidate, profile) == "accepted"


def test_missing_result_producer_rejects() -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    candidate["operation_evidence"][0].pop("result_producer")
    assert assess(candidate, profile) == code(profile, "operation_evidence")


def test_arbitrary_valid_operation_digest_still_fails_its_synthetic_basis() -> None:
    profile = load(PROFILE)
    candidate = synthetic_supported(profile)
    record = candidate["operation_evidence"][0]
    record["trama_result_provenance"]["evidence_digest"] = "f" * 64
    record["result_sha256"] = "f" * 64
    assert assess(candidate, profile) == code(profile, "operation_evidence")


def test_committed_fixtures_have_exact_rejection_reasons() -> None:
    profile = load(PROFILE)
    declared_reasons = set(profile["reason_codes"].values())
    expected = {
        "unverified-db-baseline.json": code(profile, "qualification_state"),
        "rejected-incomplete-subtree.json": code(profile, "subtree"),
        "rejected-direct-database.json": code(profile, "direct_database"),
    }
    for name, reason in expected.items():
        evidence = load(FIXTURES / name)
        assert assess(evidence, profile) == reason
        if evidence["qualification_state"] == "rejected":
            assert evidence["rejection_reason"] == reason
            assert evidence["rejection_reason"] in declared_reasons
        else:
            assert "rejection_reason" not in evidence


def test_committed_rejections_have_only_the_declared_runtime_blocking_condition() -> None:
    profile = load(PROFILE)
    incomplete = load(FIXTURES / "rejected-incomplete-subtree.json")
    incomplete["operation_evidence"][2]["subtree_observation"] = {
        "complete": True,
        "ordered_parentage": True,
        "top_level_only": False,
    }
    assert assess(incomplete, profile) == code(profile, "qualification_state")

    direct_database = load(FIXTURES / "rejected-direct-database.json")
    direct_database["direct_database_access"] = False
    assert assess(direct_database, profile) == code(profile, "qualification_state")


def test_committed_synthetic_digests_are_distinct_and_reproducible() -> None:
    for name in (
        "unverified-db-baseline.json",
        "rejected-incomplete-subtree.json",
        "rejected-direct-database.json",
    ):
        evidence = load(FIXTURES / name)
        assert evidence["fixture_digest"] == digest_for(evidence["synthetic_fixture_basis"])
        if evidence["qualification_state"] == "unverified":
            assert evidence["operation_evidence"] == []
            continue
        digests = {evidence["fixture_digest"]}
        for record in evidence["operation_evidence"]:
            provenance = record["trama_result_provenance"]
            assert record["result_sha256"] == provenance["evidence_digest"]
            assert provenance["evidence_digest"] == digest_for(record["synthetic_result_basis"])
            assert provenance["source_mode"] == "db_native"
            assert provenance["authority"] == "logseq_db_native"
            digests.add(provenance["evidence_digest"])
        assert len(digests) == 4
