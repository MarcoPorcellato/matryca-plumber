"""Installed-only, bounded black-box checks for the unqualified OG package."""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import stat
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from .bootstrap import ERROR_EXITS
from .consumer import ChildFailure, ChildResult, _run_child
from .resources import (
    PackageResourceError,
    PackageResources,
    _document,
    _load_package_resources,
    _verify_package_resources,
)

_MAX_REPORT_BYTES = 262_144
_MAX_FIXTURE_FILES = 32
_MAX_FIXTURE_BYTES = 1_048_576
_MAX_DISTRIBUTIONS = 1_024
_MAX_EXECUTABLE_BYTES = 67_108_864
_MAX_ENVIRONMENT_ENTRIES = 100_000
_MAX_ENVIRONMENT_FILE_BYTES = 67_108_864
_MAX_ENVIRONMENT_FILES_TOTAL = 536_870_912
_UUID = re.compile(rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class TCKFailure(RuntimeError):
    """A fixed, path-free TCK failure reason."""

    def __init__(
        self,
        reason: str,
        *,
        cleanup_status: str = "not_applicable",
        cleanup_events: tuple[str, ...] = (),
        child: ChildResult | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.cleanup_status = cleanup_status
        self.cleanup_events = cleanup_events
        self.completed_checks: tuple[str, ...] = ()
        self.child_failure: dict[str, int | str] | None = None
        if child is not None:
            self.child_failure = {
                "returncode": child.returncode,
                "stderr": "unclassified" if child.stderr else "empty",
            }
            try:
                document = _document(child.stderr, 512)
            except PackageResourceError:
                pass
            else:
                for code, expected_exit in ERROR_EXITS.items():
                    if document == {"error": code} and child.returncode == expected_exit:
                        self.child_failure["stderr"] = "gateway_error"
                        self.child_failure["error"] = code
                        break


@dataclass(frozen=True, slots=True)
class _TreeInventory:
    """Typed bounded inventory for one private graph or owned work root."""

    state: str
    sha256: str
    entries: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _InvocationInventory:
    """Before/after evidence for graph input and complete TCK-owned workspace."""

    graph_root: _TreeInventory
    owned_work_root: _TreeInventory


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_installed_origin(
    module_origin: Path, spec_origin: Path, direct_url: dict[str, Any] | None
) -> bool:
    """Reject source/editable execution and origins outside installed package directories."""
    try:
        actual = module_origin.resolve(strict=True)
        expected = spec_origin.resolve(strict=True)
    except OSError:
        return False
    if actual != expected or not actual.is_file():
        return False
    if not {"site-packages", "dist-packages"}.intersection(actual.parts):
        return False
    if direct_url is not None:
        if type(direct_url) is not dict:
            return False
        directory = direct_url.get("dir_info")
        if directory is not None and (
            type(directory) is not dict or directory.get("editable") is True
        ):
            return False
    return True


def _installed_identity() -> dict[str, Any]:
    spec = importlib.util.find_spec("matryca_plumber.graph_gateway.tck")
    if spec is None or not isinstance(spec.origin, str):
        return {"installed_origin": False, "editable": False}
    try:
        distribution = importlib.metadata.distribution("matryca-plumber")
        raw_direct_url = distribution.read_text("direct_url.json")
        direct_url = json.loads(raw_direct_url) if raw_direct_url else None
    except (importlib.metadata.PackageNotFoundError, json.JSONDecodeError, OSError):
        return {"installed_origin": False, "editable": False}
    origin = Path(spec.origin)
    installed = _is_installed_origin(Path(__file__), origin, direct_url)
    try:
        origin.resolve(strict=True).relative_to(Path(sys.prefix).resolve(strict=True))
    except (OSError, ValueError):
        installed = False
    editable = bool(
        isinstance(direct_url, dict)
        and isinstance(direct_url.get("dir_info"), dict)
        and direct_url["dir_info"].get("editable") is True
    )
    return {"installed_origin": installed, "editable": editable}


def _strict_document(payload: bytes) -> dict[str, Any]:
    try:
        return _document(payload, 4_194_304)
    except PackageResourceError:
        raise TCKFailure("invalid_json") from None


def _validate_topology_structure(result: dict[str, Any], package: PackageResources) -> None:
    """Check complete preorder, parentage, ordinals, edges, and fixture counts."""
    if result.get("complete") is not True or type(result.get("nodes")) is not list:
        raise TCKFailure("topology_structure")
    if type(result.get("edges")) is not list:
        raise TCKFailure("topology_structure")

    seen: dict[str, dict[str, Any]] = {}
    next_ordinal: dict[str | None, int] = {}
    stack: list[str] = []
    page_nodes = 0
    block_nodes = 0
    for node in result["nodes"]:
        node_id = node["id"]
        kind = node["kind"]
        parent_id = node["parent_id"]
        ordinal = node["ordinal"]
        if node_id in seen:
            raise TCKFailure("topology_structure")
        if kind == "page":
            if parent_id is not None or ordinal != page_nodes:
                raise TCKFailure("topology_structure")
            page_nodes += 1
            stack = [node_id]
        else:
            if parent_id is None or parent_id not in seen:
                raise TCKFailure("topology_structure")
            while stack and stack[-1] != parent_id:
                stack.pop()
            if not stack or seen[parent_id]["kind"] not in {"page", "block"}:
                raise TCKFailure("topology_structure")
            block_nodes += 1

        expected_ordinal = next_ordinal.get(parent_id, 0)
        if ordinal != expected_ordinal:
            raise TCKFailure("topology_structure")
        next_ordinal[parent_id] = expected_ordinal + 1
        seen[node_id] = node
        if kind == "block":
            stack.append(node_id)

    edge_keys: list[tuple[str, str, str]] = []
    for edge in result["edges"]:
        source_id = edge["source_id"]
        target_id = edge["target_id"]
        kind = edge["kind"]
        if source_id not in seen or target_id not in seen:
            raise TCKFailure("topology_structure")
        edge_keys.append((kind, source_id, target_id))
    if edge_keys != sorted(set(edge_keys)):
        raise TCKFailure("topology_structure")

    fixture_manifest = _document(package.assets["fixture-manifest.json"], 131_072)
    expected = fixture_manifest["independent_expectations"]
    counts = {
        "page_nodes": page_nodes,
        "block_nodes": block_nodes,
        "reference_edges": len(edge_keys),
        "result_complete": result["complete"],
    }
    if any(counts[key] != expected[key] for key in counts):
        raise TCKFailure("topology_expectations")


def _assert_repeat_response(first: dict[str, Any], repeated: dict[str, Any]) -> None:
    """Require new session identity while keeping source and topology stable."""
    if first["read"]["session"]["id"] == repeated["read"]["session"]["id"]:
        raise TCKFailure("repeat_session_reused")
    if (
        repeated["read"]["graph_id"] != first["read"]["graph_id"]
        or repeated["read"]["source_revision"] != first["read"]["source_revision"]
        or repeated["topology"]["result"] != first["topology"]["result"]
    ):
        raise TCKFailure("repeat_mismatch")


def _assert_fresh_session(response: dict[str, Any], previous_ids: set[str]) -> None:
    """Require every successful child invocation to use a globally new session ID."""
    session_id = response["read"]["session"]["id"]
    if type(session_id) is not str or not session_id or session_id in previous_ids:
        raise TCKFailure("session_reused")


def _assert_source_change(original: dict[str, Any], changed: dict[str, Any]) -> None:
    """Require source mutation to alter revision and deterministic topology bytes."""
    if (
        changed["read"]["graph_id"] != original["read"]["graph_id"]
        or changed["read"]["source_revision"] == original["read"]["source_revision"]
        or changed["topology"]["result"] == original["topology"]["result"]
    ):
        raise TCKFailure("source_change_missed")


def _validate_success_response(
    payload: bytes,
    package: PackageResources,
    *,
    require_golden: bool = True,
) -> dict[str, Any]:
    """Validate strict response shape, both existing schemas, and bound topology bytes."""
    document = _strict_document(payload)
    if set(document) != {"profile", "descriptor_sha256", "versions", "read", "topology"}:
        raise TCKFailure("response_shape")
    if (
        document["profile"] != package.descriptor["profile"]
        or document["descriptor_sha256"] != package.descriptor_sha256
        or type(document["versions"]) is not dict
        or set(document["versions"]) != {"plumber", "parser", "python"}
        or document["versions"].get("plumber")
        != json.loads(package.assets["dependency-profile.json"])["project"]["version"]
        or document["versions"].get("parser") != "1.9.0"
        or type(document["versions"].get("python")) is not str
        or re.fullmatch(r"3\.(12|13)\.[0-9]+", document["versions"]["python"]) is None
    ):
        raise TCKFailure("response_binding")

    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

        for key in ("read", "topology"):
            schema = _document(package.schema_bytes[key], 131_072)
            errors = list(Draft202012Validator(schema).iter_errors(document[key]))
            if errors:
                raise TCKFailure(f"{key}_schema")
    except ImportError:
        raise TCKFailure("schema_validator_unavailable") from None
    except PackageResourceError:
        raise TCKFailure("schema_resource_invalid") from None

    read = document["read"]
    topology = document["topology"]
    read_wire = package.descriptor["wire"]["read"]
    topology_wire = package.descriptor["wire"]["topology"]
    if (
        read["outcome"] != "pass"
        or topology["outcome"] != "pass"
        or read["id"] != read_wire["id"]
        or read["producer_profile_id"] != read_wire["producer_profile_id"]
        or read["consumer_profile_id"] != read_wire["consumer_profile_id"]
        or read["contract_id"] != "plumber.graph.read/v1"
        or read["operation"] != package.descriptor["operations"][0]
        or topology["id"] != topology_wire["id"]
        or topology["producer_profile_id"] != topology_wire["producer_profile_id"]
        or topology["consumer_profile_id"] != topology_wire["consumer_profile_id"]
        or topology["contract_id"] != "plumber.graph.topology/v1"
        or topology["operation"] != package.descriptor["operations"][1]
        or read["graph_id"] != topology["graph_id"]
        or read["result"]["graph_id"] != read["graph_id"]
        or read["source_revision"] != topology["source_revision"]
        or read["session"]["id"] != topology["request"]["session_id"]
        or topology["request"]["graph_id"] != read["graph_id"]
        or topology["session"]["id"] != topology["request"]["session_id"]
        or read["session"]["state"] != "active"
        or topology["session"]["state"] != "active"
        or topology["result"]["provenance"]["source_revision"] != topology["source_revision"]
    ):
        raise TCKFailure("response_binding")
    result = topology["result"]
    _validate_topology_structure(result, package)
    if require_golden:
        golden = _document(package.assets["golden/topology.result.json"], 131_072)
        if result != golden:
            raise TCKFailure("topology_golden")
    return document


def _check_error_response(result: ChildResult, *, reason: str, exit_code: int) -> None:
    if (
        result.cleanup_ok is not True
        or result.returncode != exit_code
        or result.stdout != b""
        or result.stderr != json.dumps({"error": reason}, separators=(",", ":")).encode() + b"\n"
    ):
        raise TCKFailure("strict_error_response")


def _fixture_files(package: PackageResources) -> dict[str, bytes]:
    manifest = _document(package.assets["fixture-manifest.json"], 131_072)
    if (
        set(manifest)
        != {
            "fixture_profile",
            "license",
            "files",
            "independent_expectations",
            "privacy_canaries",
            "schema_version",
        }
        or manifest["fixture_profile"] != "og-v1-synthetic-structure"
        or manifest["license"] != "Apache-2.0"
        or type(manifest["schema_version"]) is not int
        or manifest["schema_version"] != 1
        or type(manifest["files"]) is not dict
        or not 0 < len(manifest["files"]) <= _MAX_FIXTURE_FILES
    ):
        raise TCKFailure("fixture_manifest")
    files: dict[str, bytes] = {}
    for name, record in manifest["files"].items():
        path = PurePosixPath(name)
        if (
            not isinstance(name, str)
            or path.is_absolute()
            or str(path) != name
            or any(part in {"", ".", ".."} for part in path.parts)
            or type(record) is not dict
            or set(record) != {"sha256"}
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        ):
            raise TCKFailure("fixture_manifest")
        resource_name = f"fixtures/{name}"
        data = package.assets.get(resource_name)
        if data is None or len(data) > _MAX_FIXTURE_BYTES or _digest(data) != record["sha256"]:
            raise TCKFailure("fixture_resource")
        files[name] = data
    expected_assets = {f"fixtures/{name}" for name in files}
    actual_assets = {name for name in package.assets if name.startswith("fixtures/")}
    if actual_assets != expected_assets:
        raise TCKFailure("fixture_inventory")
    _fixture_privacy_canary_values(manifest, files)
    return files


def _fixture_privacy_canary_values(
    manifest: dict[str, Any], files: dict[str, bytes]
) -> tuple[str, str]:
    """Require declared privacy markers to occupy real block and property positions."""
    canaries = manifest.get("privacy_canaries")
    if (
        type(canaries) is not dict
        or set(canaries) != {"block_text", "property_value"}
        or type(canaries.get("block_text")) is not dict
        or type(canaries.get("property_value")) is not dict
    ):
        raise TCKFailure("fixture_manifest")
    block = canaries["block_text"]
    property_value = canaries["property_value"]
    if (
        set(block) != {"fixture", "value"}
        or set(property_value) != {"fixture", "property", "value"}
        or any(type(block[key]) is not str or not block[key] for key in block)
        or any(
            type(property_value[key]) is not str or not property_value[key]
            for key in property_value
        )
        or len(block["value"]) > 128
        or len(property_value["value"]) > 128
        or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", property_value["property"]) is None
    ):
        raise TCKFailure("fixture_manifest")
    block_bytes = files.get(block["fixture"])
    property_bytes = files.get(property_value["fixture"])
    if (
        block_bytes is None
        or property_bytes is None
        or not any(
            line.startswith(b"- ") and block["value"].encode() in line
            for line in block_bytes.splitlines()
        )
        or f"{property_value['property']}:: {property_value['value']}".encode()
        not in property_bytes.splitlines()
    ):
        raise TCKFailure("fixture_manifest")
    return block["value"], property_value["value"]


def _copy_private_fixtures(package: PackageResources, root: Path) -> None:
    fixture_files = _fixture_files(package)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(root, 0o700)
    for name, data in fixture_files.items():
        destination = root.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(destination.parent, 0o700)
        with destination.open("xb") as handle:
            handle.write(data)
        os.chmod(destination, 0o600)


def _fingerprint_tree(root: Path) -> _TreeInventory:
    records: dict[str, str] = {}
    entries_seen = 0

    def visit(directory: Path, prefix: str) -> None:
        nonlocal entries_seen
        try:
            if not stat.S_ISDIR(directory.lstat().st_mode):
                raise TCKFailure("fixture_tree")
            records[f"d:{prefix or '.'}"] = "directory"
        except TCKFailure:
            raise
        except OSError:
            raise TCKFailure("fixture_read") from None
        try:
            children = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries_seen += 1
                    if entries_seen > _MAX_FIXTURE_FILES * 4:
                        raise TCKFailure("fixture_bounds")
                    children.append(entry)
            children.sort(key=lambda entry: entry.name)
        except TCKFailure:
            raise
        except OSError:
            raise TCKFailure("fixture_read") from None
        for entry in children:
            name = f"{prefix}/{entry.name}" if prefix else entry.name
            if not name or "\\" in name or entry.is_symlink():
                raise TCKFailure("fixture_tree")
            path = directory / entry.name
            if entry.is_dir(follow_symlinks=False):
                visit(path, name)
            elif entry.is_file(follow_symlinks=False):
                try:
                    with path.open("rb") as handle:
                        data = handle.read(_MAX_FIXTURE_BYTES + 1)
                except OSError:
                    raise TCKFailure("fixture_read") from None
                if len(data) > _MAX_FIXTURE_BYTES:
                    raise TCKFailure("fixture_bounds")
                records[f"f:{name}"] = _digest(data)
            else:
                raise TCKFailure("fixture_tree")

    visit(root, "")
    entries = tuple(sorted(records.items()))
    canonical = json.dumps(entries, separators=(",", ":")).encode()
    return _TreeInventory("present", _digest(canonical), entries)


def _fingerprint_optional_tree(root: Path) -> _TreeInventory:
    """Record an expected absent source root without conflating it with unreadable state."""
    try:
        mode = root.lstat().st_mode
    except FileNotFoundError:
        return _TreeInventory("missing", _digest(b"missing"), ())
    except OSError:
        raise TCKFailure("fixture_read") from None
    if not stat.S_ISDIR(mode):
        raise TCKFailure("fixture_tree")
    return _fingerprint_tree(root)


def _invocation_inventory(root: Path, work_root: Path) -> _InvocationInventory:
    """Bind graph and complete private-work-tree state before or after each child."""
    try:
        owned = work_root.resolve(strict=True)
        graph = root.resolve(strict=False)
        graph.relative_to(owned)
        if graph == owned:
            raise TCKFailure("fixture_tree")
    except TCKFailure:
        raise
    except (OSError, ValueError):
        raise TCKFailure("fixture_tree") from None
    return _InvocationInventory(
        graph_root=_fingerprint_optional_tree(root),
        owned_work_root=_fingerprint_tree(work_root),
    )


def _check_fixture_no_leak(
    payload: bytes, root: Path, files: dict[str, bytes], package: PackageResources
) -> None:
    forbidden = [str(root).encode()]
    manifest_data = b"\n".join(files.values())
    forbidden.extend(match.group(0) for match in _UUID.finditer(manifest_data))
    package_manifest = _document(package.assets["fixture-manifest.json"], 131_072)
    forbidden.extend(
        value.encode() for value in _fixture_privacy_canary_values(package_manifest, files)
    )
    if any(value and value in payload for value in forbidden):
        raise TCKFailure("fixture_content_leak")


def _invoke_child(
    argv: tuple[str, ...],
    root: Path,
    work_root: Path,
    package: PackageResources,
    *,
    expected_environment_sha256: str,
    execution_timeout: float = 180.0,
    cleanup_budget: float = 5.0,
    max_stdout_bytes: int = 4_194_304,
    max_stderr_bytes: int = 512,
) -> ChildResult:
    before_inventory = _invocation_inventory(root, work_root)
    before = _environment_fingerprint(package)
    if before != expected_environment_sha256:
        raise TCKFailure("environment_changed")
    child: ChildResult | None = None
    child_failure: ChildFailure | None = None
    child_unexpected = False
    try:
        child = _run_child(
            argv,
            cwd=work_root,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
            execution_timeout=execution_timeout,
            cleanup_budget=cleanup_budget,
            max_stdout_bytes=max_stdout_bytes,
            max_stderr_bytes=max_stderr_bytes,
        )
    except ChildFailure as error:
        child_failure = error
    except BaseException:
        child_unexpected = True

    after_inventory: _InvocationInventory | None = None
    inventory_unavailable = False
    try:
        after_inventory = _invocation_inventory(root, work_root)
    except BaseException:
        inventory_unavailable = True

    after_environment: str | None = None
    environment_unavailable = False
    try:
        after_environment = _environment_fingerprint(package)
    except BaseException:
        environment_unavailable = True

    if child_failure is not None:
        events = list(child_failure.cleanup_events)
        cleanup_uncertain = not child_failure.cleanup_ok
        if inventory_unavailable or after_inventory is None:
            events.append("owned_inventory_unavailable")
            cleanup_uncertain = True
        elif after_inventory != before_inventory:
            events.append("owned_inventory_changed")
        if environment_unavailable or after_environment is None:
            events.append("environment_inventory_unavailable")
        elif after_environment != before:
            events.append("environment_fingerprint_changed")
        raise TCKFailure(
            child_failure.reason,
            cleanup_status="uncertain" if cleanup_uncertain else "verified",
            cleanup_events=tuple(dict.fromkeys(events)),
        ) from None
    if child_unexpected:
        events = ["child_cleanup_unverified"]
        if inventory_unavailable or after_inventory is None:
            events.append("owned_inventory_unavailable")
        elif after_inventory != before_inventory:
            events.append("owned_inventory_changed")
        if environment_unavailable or after_environment is None:
            events.append("environment_inventory_unavailable")
        elif after_environment != before:
            events.append("environment_fingerprint_changed")
        raise TCKFailure(
            "child_invocation_error",
            cleanup_status="uncertain",
            cleanup_events=tuple(dict.fromkeys(events)),
        ) from None
    if inventory_unavailable or after_inventory is None:
        events = ["owned_inventory_unavailable"]
        if child is not None and not child.cleanup_ok:
            events.extend(child.cleanup_events)
            events.append("child_cleanup_unverified")
        if environment_unavailable or after_environment is None:
            events.append("environment_inventory_unavailable")
        raise TCKFailure(
            "owned_inventory_unavailable",
            cleanup_status="uncertain",
            cleanup_events=tuple(dict.fromkeys(events)),
        ) from None
    if after_inventory != before_inventory:
        raise TCKFailure("invocation_tree_changed", cleanup_status="verified")
    if environment_unavailable or after_environment is None:
        status = "uncertain" if child is not None and not child.cleanup_ok else "verified"
        events = ["environment_inventory_unavailable"]
        if child is not None and not child.cleanup_ok:
            events = [*child.cleanup_events, "child_cleanup_unverified", *events]
        raise TCKFailure(
            "environment_inventory_unavailable",
            cleanup_status=status,
            cleanup_events=tuple(dict.fromkeys(events)),
        ) from None
    if child is None:
        raise TCKFailure("child_invocation_error", cleanup_status="uncertain")
    if not child.cleanup_ok:
        raise TCKFailure(
            "child_cleanup_unverified",
            cleanup_status="uncertain",
            cleanup_events=child.cleanup_events,
        )
    if after_environment != before:
        raise TCKFailure("environment_changed", cleanup_status="verified")
    return child


def _invoke_snapshot(
    root: Path,
    work_root: Path,
    package: PackageResources,
    *,
    expected_environment_sha256: str,
) -> ChildResult:
    """Run one gateway snapshot under the shared child and inventory boundary."""
    return _invoke_child(
        (
            sys.executable,
            "-I",
            "-B",
            "-m",
            "matryca_plumber.graph_gateway",
            "snapshot",
            "--graph-root",
            str(root),
            "--expect-descriptor-sha256",
            package.descriptor_sha256,
        ),
        root,
        work_root,
        package,
        expected_environment_sha256=expected_environment_sha256,
    )


def _expect_native_child_failure(
    case_id: str,
    argv: tuple[str, ...],
    root: Path,
    work_root: Path,
    package: PackageResources,
    environment_sha256: str,
    expected_reason: str,
    *,
    execution_timeout: float = 3.0,
    cleanup_budget: float = 1.0,
    max_stdout_bytes: int = 4_194_304,
    max_stderr_bytes: int = 512,
    observe_kill_escalation: bool = False,
) -> dict[str, str]:
    observed_kill_groups: list[int] = []
    real_killpg = os.killpg

    def observe_killpg(group_id: int, signum: int) -> None:
        if signum == signal.SIGKILL:
            observed_kill_groups.append(group_id)
        real_killpg(group_id, signum)

    if observe_kill_escalation:
        os.killpg = observe_killpg
    try:
        try:
            _invoke_child(
                argv,
                root,
                work_root,
                package,
                expected_environment_sha256=environment_sha256,
                execution_timeout=execution_timeout,
                cleanup_budget=cleanup_budget,
                max_stdout_bytes=max_stdout_bytes,
                max_stderr_bytes=max_stderr_bytes,
            )
        except TCKFailure as error:
            if (
                error.reason != expected_reason
                or error.cleanup_status != "verified"
                or error.cleanup_events
            ):
                raise TCKFailure(
                    case_id,
                    cleanup_status=error.cleanup_status,
                    cleanup_events=error.cleanup_events,
                ) from None
        else:
            raise TCKFailure(case_id)
    finally:
        if observe_kill_escalation:
            os.killpg = real_killpg
    if observe_kill_escalation and not observed_kill_groups:
        raise TCKFailure(case_id)
    evidence = "native_synthetic_child"
    if observe_kill_escalation:
        evidence += "; SIGKILL observed for owned group"
    return {"id": case_id, "status": "pass", "evidence": evidence}


def _run_interrupted_cleanup_control(
    root: Path,
    work_root: Path,
    package: PackageResources,
    environment_sha256: str,
) -> dict[str, str]:
    """Inject one private finalizer interruption and independently verify fallback."""
    from . import consumer as consumer_module

    mutable_consumer: Any = cast(Any, consumer_module)
    real_popen = mutable_consumer.subprocess.Popen
    real_cleanup = mutable_consumer._cleanup_group
    children: list[Any] = []

    def capture_child(*args: Any, **kwargs: Any) -> Any:
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child

    def interrupt_group_cleanup(*_args: Any, **_kwargs: Any) -> bool:
        raise KeyboardInterrupt("synthetic cleanup interruption")

    mutable_consumer.subprocess.Popen = capture_child
    mutable_consumer._cleanup_group = interrupt_group_cleanup
    failure: TCKFailure | None = None
    invocation_unexpected = False
    try:
        try:
            _invoke_child(
                (sys.executable, "-I", "-B", "-c", "import time;time.sleep(30)"),
                root,
                work_root,
                package,
                expected_environment_sha256=environment_sha256,
                execution_timeout=0.1,
                cleanup_budget=1.0,
            )
        except TCKFailure as error:
            failure = error
        except BaseException:
            invocation_unexpected = True
    finally:
        mutable_consumer._cleanup_group = real_cleanup
        mutable_consumer.subprocess.Popen = real_popen

    observation_events: list[str] = []
    observation_uncertain = False
    if len(children) != 1:
        observation_events.append("child_count_mismatch")
    if not children:
        observation_events.append("child_handle_unavailable")
        observation_uncertain = True
    for child in children:
        try:
            if child.poll() is None:
                observation_events.append("child_not_reaped")
                observation_uncertain = True
        except BaseException:
            observation_events.append("child_poll_unavailable")
            observation_uncertain = True
        try:
            if mutable_consumer._group_state(child.pid) is not False:
                observation_events.append("group_not_verified_gone")
                observation_uncertain = True
        except BaseException:
            observation_events.append("group_state_unavailable")
            observation_uncertain = True
        for stream_name in ("stdout", "stderr"):
            try:
                stream = getattr(child, stream_name)
                if stream is None or stream.closed is not True:
                    observation_events.append(f"{stream_name}_not_closed")
                    observation_uncertain = True
            except BaseException:
                observation_events.append(f"{stream_name}_state_unavailable")
                observation_uncertain = True

    expected_failure = (
        not invocation_unexpected
        and failure is not None
        and failure.reason == "timeout"
        and failure.cleanup_status == "uncertain"
        and failure.cleanup_events == ("group_finalize_failed",)
        and len(children) == 1
    )
    if not expected_failure or observation_uncertain:
        events = list(failure.cleanup_events) if failure is not None else []
        if failure is None:
            events.append("expected_child_failure_missing")
        elif failure.reason != "timeout":
            events.append("child_failure_mismatch")
        if invocation_unexpected:
            events.append("control_interrupted")
        events.extend(observation_events)
        raise TCKFailure(
            "injected_cleanup_fallback_unverified"
            if expected_failure
            else "injected_cleanup_interruption",
            cleanup_status="uncertain" if observation_uncertain else "verified",
            cleanup_events=tuple(dict.fromkeys(events)),
        ) from None
    return {
        "id": "injected-cleanup-interruption-fallback",
        "status": "pass",
        "evidence": "injected_finalizer_fault; child, group, and pipes independently verified",
    }


def _run_lifecycle_controls(
    root: Path,
    work_root: Path,
    package: PackageResources,
    environment_sha256: str,
) -> list[dict[str, str]]:
    """Exercise bounded native child failures through the production process reader."""
    base = (sys.executable, "-I", "-B", "-c")
    controls = [
        _expect_native_child_failure(
            "native-timeout-cleanup",
            (*base, "import time;time.sleep(30)"),
            root,
            work_root,
            package,
            environment_sha256,
            "timeout",
            execution_timeout=0.1,
        ),
        _expect_native_child_failure(
            "native-stdout-overflow-cleanup",
            (*base, "import os;os.write(1,b'x'*65536)"),
            root,
            work_root,
            package,
            environment_sha256,
            "stdout_overflow",
            max_stdout_bytes=32,
        ),
        _expect_native_child_failure(
            "native-stderr-overflow-cleanup",
            (*base, "import os;os.write(2,b'x'*4096)"),
            root,
            work_root,
            package,
            environment_sha256,
            "stderr_overflow",
            max_stderr_bytes=32,
        ),
    ]
    ready = str(work_root / ".survivor-ready")
    grandchild = (
        "import pathlib,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"pathlib.Path({ready!r}).write_bytes(b'1');time.sleep(30)"
    )
    survivor = (
        "import pathlib,subprocess,sys,time\n"
        f"marker=pathlib.Path({ready!r})\n"
        f"subprocess.Popen([sys.executable,'-I','-B','-c',{grandchild!r}],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        "deadline=time.monotonic()+1.0\n"
        "while not marker.exists() and time.monotonic()<deadline:\n"
        " time.sleep(0.01)\n"
        "marker.unlink(missing_ok=True)\n"
    )
    controls.append(
        _expect_native_child_failure(
            "native-same-group-survivor-kill-escalation",
            (*base, survivor),
            root,
            work_root,
            package,
            environment_sha256,
            "surviving_process_group",
            cleanup_budget=2.0,
            observe_kill_escalation=True,
        )
    )
    controls.append(_run_interrupted_cleanup_control(root, work_root, package, environment_sha256))
    return controls


def _run_controls(package: PackageResources, environment_sha256: str) -> list[dict[str, str]]:
    fixture_files = _fixture_files(package)
    work_root = Path(tempfile.mkdtemp(prefix="og-operational-tck-"))
    checks: list[dict[str, str]] = []
    failure: TCKFailure | None = None
    retain_work_root = False
    try:
        work_root = work_root.resolve(strict=True)
        os.chmod(work_root, 0o700)
        mutated_module_bytes = dict(package.module_bytes)
        first_module = next(iter(mutated_module_bytes))
        mutated_module_bytes[first_module] += b"\n# mutation\n"
        try:
            _verify_package_resources(
                package.descriptor_bytes,
                package.manifest_bytes,
                package.assets,
                package.package_paths,
                package.schema_bytes,
                mutated_module_bytes,
            )
        except PackageResourceError:
            pass
        else:
            raise TCKFailure("resource_mutation_accepted")
        checks.append({"id": "resource-and-code-byte-authentication", "status": "pass"})
        first_root = work_root / "first"
        relocated_root = work_root / "relocated"
        _copy_private_fixtures(package, first_root)
        first_inventory = _fingerprint_tree(first_root)
        first_tree = {
            name.removeprefix("f:"): digest
            for name, digest in first_inventory.entries
            if name.startswith("f:")
        }
        expected_tree = {name: _digest(payload) for name, payload in fixture_files.items()}
        if first_tree != expected_tree:
            raise TCKFailure("fixture_copy")
        first_fingerprint = first_inventory.sha256
        first_child = _invoke_snapshot(
            first_root,
            work_root,
            package,
            expected_environment_sha256=environment_sha256,
        )
        if first_child.returncode != 0 or first_child.stderr != b"":
            raise TCKFailure("snapshot_failed", cleanup_status="verified", child=first_child)
        first = _validate_success_response(first_child.stdout, package)
        successful_session_ids: set[str] = set()
        _assert_fresh_session(first, successful_session_ids)
        successful_session_ids.add(first["read"]["session"]["id"])
        _check_fixture_no_leak(first_child.stdout, first_root, fixture_files, package)
        if _fingerprint_tree(first_root).sha256 != first_fingerprint:
            raise TCKFailure("fixture_unexpected_mutation")
        checks.append({"id": "schema-golden-bindings", "status": "pass"})

        repeated_child = _invoke_snapshot(
            first_root,
            work_root,
            package,
            expected_environment_sha256=environment_sha256,
        )
        if repeated_child.returncode != 0 or repeated_child.stderr != b"":
            raise TCKFailure("repeat_failed", cleanup_status="verified", child=repeated_child)
        repeated = _validate_success_response(repeated_child.stdout, package)
        _assert_fresh_session(repeated, successful_session_ids)
        successful_session_ids.add(repeated["read"]["session"]["id"])
        _assert_repeat_response(first, repeated)
        checks.append({"id": "same-root-repeatability", "status": "pass"})

        _copy_private_fixtures(package, relocated_root)
        relocated_fingerprint = _fingerprint_tree(relocated_root).sha256
        relocated_child = _invoke_snapshot(
            relocated_root,
            work_root,
            package,
            expected_environment_sha256=environment_sha256,
        )
        if relocated_child.returncode != 0 or relocated_child.stderr != b"":
            raise TCKFailure("relocation_failed", cleanup_status="verified", child=relocated_child)
        relocated = _validate_success_response(relocated_child.stdout, package)
        _assert_fresh_session(relocated, successful_session_ids)
        successful_session_ids.add(relocated["read"]["session"]["id"])
        _check_fixture_no_leak(relocated_child.stdout, relocated_root, fixture_files, package)
        if (
            relocated_fingerprint != first_fingerprint
            or relocated["read"]["graph_id"] == first["read"]["graph_id"]
            or relocated["read"]["source_revision"] != first["read"]["source_revision"]
            or relocated["topology"]["result"] != first["topology"]["result"]
        ):
            raise TCKFailure("relocation_mismatch")
        checks.append({"id": "relocation-invariance", "status": "pass"})

        changed_path = relocated_root / "pages" / "B.md"
        original_bytes = changed_path.read_bytes()
        changed_bytes = original_bytes.replace(b"Alpha parent", b"Altered parent", 1)
        if changed_bytes == original_bytes:
            raise TCKFailure("source_mutation_unavailable")
        changed_path.write_bytes(changed_bytes)
        changed_fingerprint = _fingerprint_tree(relocated_root).sha256
        changed_child = _invoke_snapshot(
            relocated_root,
            work_root,
            package,
            expected_environment_sha256=environment_sha256,
        )
        if changed_child.returncode != 0 or changed_child.stderr != b"":
            raise TCKFailure("source_change_failed", cleanup_status="verified", child=changed_child)
        changed = _validate_success_response(changed_child.stdout, package, require_golden=False)
        _assert_fresh_session(changed, successful_session_ids)
        successful_session_ids.add(changed["read"]["session"]["id"])
        if changed_fingerprint == relocated_fingerprint:
            raise TCKFailure("source_change_missed")
        _assert_source_change(relocated, changed)
        checks.append({"id": "source-change-sensitivity", "status": "pass"})
        checks.append({"id": "globally-unique-success-session-identities", "status": "pass"})

        missing_child = _invoke_snapshot(
            work_root / "not-present",
            work_root,
            package,
            expected_environment_sha256=environment_sha256,
        )
        _check_error_response(missing_child, reason="source_rejected", exit_code=4)
        checks.append({"id": "strict-invalid-root-error", "status": "pass"})
        checks.extend(_run_lifecycle_controls(first_root, work_root, package, environment_sha256))
    except TCKFailure as error:
        failure = error
        retain_work_root = error.cleanup_status == "uncertain"
    except BaseException:
        failure = TCKFailure(
            "control_interrupted",
            cleanup_status="uncertain",
            cleanup_events=("control_interrupted",),
        )
        retain_work_root = True
    if not retain_work_root:
        try:
            shutil.rmtree(work_root)
        except BaseException:
            retain_work_root = True
            if failure is None:
                failure = TCKFailure(
                    "fixture_cleanup",
                    cleanup_status="uncertain",
                    cleanup_events=("owned_work_root_cleanup_failed",),
                )
            else:
                failure.cleanup_status = "uncertain"
                failure.cleanup_events = tuple(
                    dict.fromkeys((*failure.cleanup_events, "owned_work_root_cleanup_failed"))
                )
        else:
            if failure is not None:
                failure.cleanup_status = "verified"
    if failure is not None:
        failure.completed_checks = tuple(check["id"] for check in checks)
        raise failure
    return checks


def _resource_report(package: PackageResources) -> dict[str, Any]:
    return {
        "assets": [
            {"path": name, "sha256": _digest(payload)}
            for name, payload in sorted(package.assets.items())
        ],
        "code_modules": [
            {"path": path, "sha256": _digest(payload)}
            for path, payload in sorted(package.module_bytes.items())
        ],
        "descriptor_sha256": package.descriptor_sha256,
        "manifest_sha256": package.manifest_sha256,
    }


def _environment_bytecode_roots() -> tuple[Path, ...]:
    """Resolve distinct installed-package roots inside the active interpreter prefix."""
    try:
        prefix = Path(sys.prefix).resolve(strict=True)
        paths = sysconfig.get_paths()
        roots = []
        for name in ("purelib", "platlib"):
            value = paths.get(name)
            if type(value) is not str or not value:
                raise TCKFailure("environment_unreadable")
            root = Path(value).resolve(strict=True)
            root.relative_to(prefix)
            if not root.is_dir():
                raise TCKFailure("environment_unreadable")
            if root not in roots:
                roots.append(root)
    except TCKFailure:
        raise
    except BaseException:
        raise TCKFailure("environment_unreadable") from None
    return tuple(roots)


def _environment_artifact_fingerprint(roots: tuple[Path, ...]) -> str:
    """Hash bounded regular files and directory names under exact package roots."""
    entries_seen = 0
    bytes_seen = 0
    records: list[tuple[str, str]] = []

    def visit(root_index: int, root: Path, directory: Path, prefix: str) -> None:
        nonlocal entries_seen, bytes_seen
        try:
            if not stat.S_ISDIR(directory.lstat().st_mode):
                raise TCKFailure("environment_path")
            records.append((f"{root_index}/{prefix or '.'}/", "directory"))
        except TCKFailure:
            raise
        except BaseException:
            raise TCKFailure("environment_unreadable") from None
        try:
            children = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    entries_seen += 1
                    if entries_seen > _MAX_ENVIRONMENT_ENTRIES:
                        raise TCKFailure("environment_bounds")
                    children.append(entry)
            children.sort(key=lambda entry: entry.name)
        except TCKFailure:
            raise
        except BaseException:
            raise TCKFailure("environment_unreadable") from None

        for entry in children:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            if not relative or "\\" in entry.name:
                raise TCKFailure("environment_path")
            path = directory / entry.name
            try:
                if entry.is_symlink():
                    raise TCKFailure("environment_symlink")
                if entry.is_dir(follow_symlinks=False):
                    visit(root_index, root, path, relative)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    raise TCKFailure("environment_path")
                before = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(before.st_mode):
                    raise TCKFailure("environment_path")
                size = before.st_size
                if size < 0 or size > _MAX_ENVIRONMENT_FILE_BYTES:
                    raise TCKFailure("environment_bounds")
                bytes_seen += size
                if bytes_seen > _MAX_ENVIRONMENT_FILES_TOTAL:
                    raise TCKFailure("environment_bounds")
                digest = hashlib.sha256()
                read_size = 0
                no_follow = getattr(os, "O_NOFOLLOW", None)
                if os.name != "posix" or no_follow is None:
                    raise TCKFailure("environment_unreadable")
                descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | no_follow)
                try:
                    opened = os.fstat(descriptor)
                    if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (
                        opened.st_dev,
                        opened.st_ino,
                    ):
                        raise TCKFailure("environment_changed")
                    handle = os.fdopen(descriptor, "rb")
                    descriptor = -1
                    with handle:
                        while chunk := handle.read(65_536):
                            read_size += len(chunk)
                            if read_size > _MAX_ENVIRONMENT_FILE_BYTES:
                                raise TCKFailure("environment_bounds")
                            digest.update(chunk)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                if read_size != size:
                    raise TCKFailure("environment_changed")
                records.append((f"{root_index}/{relative}", digest.hexdigest()))
            except TCKFailure:
                raise
            except BaseException:
                raise TCKFailure("environment_unreadable") from None

    for index, root in enumerate(roots):
        try:
            resolved = root.resolve(strict=True)
            if resolved != root or not resolved.is_dir():
                raise TCKFailure("environment_unreadable")
        except TCKFailure:
            raise
        except BaseException:
            raise TCKFailure("environment_unreadable") from None
        visit(index, root, root, "")

    encoded = json.dumps(sorted(records), separators=(",", ":")).encode()
    return _digest(encoded)


def _environment_fingerprint(package: PackageResources) -> str:
    """Bind child invocations to bounded metadata and import-affecting package bytes."""
    records: list[tuple[str, str]] = []
    try:
        for distribution in importlib.metadata.distributions():
            if len(records) >= _MAX_DISTRIBUTIONS:
                raise TCKFailure("environment_bounds")
            name = distribution.metadata.get("Name")
            version = distribution.version
            if type(name) is not str or not name or type(version) is not str or not version:
                raise TCKFailure("environment_bounds")
            records.append((name.casefold(), version))
    except TCKFailure:
        raise
    except BaseException:
        raise TCKFailure("environment_unreadable") from None

    try:
        executable = Path(sys.executable).resolve(strict=True)
        if not executable.is_file() or executable.stat().st_size > _MAX_EXECUTABLE_BYTES:
            raise TCKFailure("environment_bounds")
        executable_digest = hashlib.sha256()
        with executable.open("rb") as handle:
            while chunk := handle.read(65_536):
                executable_digest.update(chunk)
        installed = _load_package_resources()
        bytecode_digest = _environment_artifact_fingerprint(_environment_bytecode_roots())
    except TCKFailure:
        raise
    except BaseException:
        raise TCKFailure("environment_unreadable") from None

    resource_bytes = json.dumps(
        _resource_report(installed), sort_keys=True, separators=(",", ":")
    ).encode()
    document = {
        "architecture": platform.machine(),
        "distribution_records": sorted(records),
        "operating_system": platform.system(),
        "package_resources_sha256": _digest(resource_bytes),
        "environment_artifacts_sha256": bytecode_digest,
        "python_executable_sha256": executable_digest.hexdigest(),
        "python_version": sys.version,
        "runtime_fingerprint_scope": (
            "distribution names and versions; all regular file bytes and directory names under "
            "resolved purelib and platlib roots within finite entry and byte caps; Python "
            "executable; authenticated package bytes"
        ),
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return _digest(encoded)


def _environment(identity: dict[str, Any], package: PackageResources) -> dict[str, Any]:
    try:
        plumber = importlib.metadata.version("matryca-plumber")
        parser = importlib.metadata.version("logseq-matryca-parser")
    except importlib.metadata.PackageNotFoundError:
        plumber = "missing"
        parser = "missing"
    return {
        **identity,
        "architecture": platform.machine(),
        "operating_system": platform.system(),
        "parser_version": parser,
        "plumber_version": plumber,
        "python_version": platform.python_version(),
        "sha256": _environment_fingerprint(package),
        "fingerprint_scope": (
            "distribution names and versions; all regular file bytes and directory names under "
            "resolved purelib and platlib roots within finite entry and byte caps; Python "
            "executable; authenticated package bytes"
        ),
    }


def _planned_row(package: PackageResources) -> bool:
    version = ".".join(platform.python_version_tuple()[:2])
    return any(
        row["system"] == platform.system()
        and row["machine"] == platform.machine()
        and row["python"] == version
        and row["state"] == "planned"
        for row in package.descriptor["matrix"]
    )


def _write_report(path: Path, report: dict[str, Any]) -> None:
    payload = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(payload) > _MAX_REPORT_BYTES:
        raise TCKFailure("report_bounds")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(path, 0o600)
    except OSError:
        raise TCKFailure("report_write_failed") from None


def _execute(report_path: Path) -> tuple[int, dict[str, Any]]:
    report: dict[str, Any] = {
        "checks": [],
        "evidence_limits": {
            "matrix": "planned-only; TCK execution does not qualify other rows",
            "source_unit_controls": {},
            "t3": "unqualified operational package; no public-artifact or Trama admission",
        },
        "qualification": "unqualified",
        "schema_version": 1,
        "status": "failed",
    }
    package: PackageResources | None = None
    try:
        package = _load_package_resources()
        report["profile"] = package.descriptor["profile"]
        report["resources"] = _resource_report(package)
        cases = _document(package.assets["tck-cases.json"], 131_072)
        report["evidence_limits"]["source_unit_controls"] = {
            "status": "mapped_not_executed_by_installed_tck",
            "tests": cases["source_unit_controls"],
        }
        report["evidence_limits"]["environment_inventory"] = {
            "limits": cases["environment_inventory"],
            "scope": (
                "fingerprinted before and after every child invocation; unknown state fails closed"
            ),
        }
        report["evidence_limits"]["consumer_lifecycle_controls"] = {
            "controls": cases["consumer_lifecycle_controls"],
            "source_diagnostic_is_not_installed_qualification": True,
        }
        identity = _installed_identity()
        if identity["installed_origin"] and not identity["editable"]:
            try:
                Path(__file__).resolve(strict=True).relative_to(
                    Path(sys.prefix).resolve(strict=True)
                )
            except (OSError, ValueError):
                identity["installed_origin"] = False
        if not identity["installed_origin"] or identity["editable"]:
            report["environment"] = {
                **identity,
                "sha256": None,
                "fingerprint_scope": "not collected: execution origin rejected",
            }
            report["status"] = "not_run"
            report["reason"] = "not_installed"
            return 2, report
        report["environment"] = _environment(identity, package)
        if not _planned_row(package):
            report["reason"] = "outside_planned_matrix"
            return 1, report
        if identity["editable"]:
            report["reason"] = "editable_install"
            return 1, report

        checks: list[dict[str, str]] = report["checks"]
        checks.append({"id": "installed-origin", "status": "pass"})
        checks.extend(_run_controls(package, report["environment"]["sha256"]))
        report["checks"] = checks
        report["cleanup"] = {"status": "verified", "retained_owned_synthetic_root": False}
        report["status"] = "pass"
        report["reason"] = "black_box_controls_passed"
        return 0, report
    except (PackageResourceError, TCKFailure):
        error = sys.exception()
        report["reason"] = error.reason if isinstance(error, TCKFailure) else "resource_rejected"
        if isinstance(error, TCKFailure):
            report["checks"].extend(
                {"id": check, "status": "pass"} for check in error.completed_checks
            )
            if error.child_failure is not None:
                report["child_failure"] = dict(error.child_failure)
        if isinstance(error, TCKFailure) and error.cleanup_status != "not_applicable":
            report["cleanup"] = {
                "status": error.cleanup_status,
                "primary_failure": error.reason,
                "events": list(error.cleanup_events),
                "retained_owned_synthetic_root": error.cleanup_status == "uncertain",
            }
        report["resources"] = _resource_report(package) if package is not None else {}
        return 1, report
    except BaseException:
        report["reason"] = "tck_internal"
        report["resources"] = _resource_report(package) if package is not None else {}
        return 1, report


def main(arguments: list[str] | None = None) -> int:
    """Run only the explicit ``--report FILE`` interface and emit path-free JSON."""
    values = sys.argv[1:] if arguments is None else arguments
    if len(values) != 2 or values[0] != "--report" or not values[1] or "\x00" in values[1]:
        sys.stdout.buffer.write(b'{"error":"usage"}\n')
        return 2
    report_path = Path(values[1])
    code, report = _execute(report_path)
    try:
        _write_report(report_path, report)
    except TCKFailure:
        sys.stdout.buffer.write(b'{"error":"report_write_failed"}\n')
        return 3
    public = {key: report[key] for key in ("qualification", "reason", "status") if key in report}
    sys.stdout.buffer.write(
        (json.dumps(public, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
