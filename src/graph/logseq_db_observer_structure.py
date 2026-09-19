"""Pure structural candidates for a future Logseq DB observer.

This module accepts in-memory JSON bytes only. It does not authenticate an
admission, inspect paths, or launch a host process.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_MAX_IDENTIFIER_CHARS = 128
_MAX_PAGE_TITLE_BYTES = 4_096
_MAX_BLOCK_TEXT_BYTES = 16_384
_MAX_NODES = 500
_MAX_DEPTH = 64
_MAX_PROPERTIES_PER_SCOPE = 64
_MAX_PROPERTY_KEY_BYTES = 128
_PROPERTY_WIRE_TYPES = {"text", "number", "boolean", "date", "url", "node-reference"}
_MAX_INPUT_BYTES = 262_144


class FixtureStructureError(ValueError):
    """Raised when a synthetic fixture does not meet the structural contract."""


class ObserverStructureError(ValueError):
    """Raised when an observer envelope does not meet the structural contract."""


class _Page(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    title: str


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    id: str
    parent_id: str | None
    ordinal: int
    text: str


class _PropertyDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    key: str
    wire_type: str
    cardinality: str
    scope: str


class _FixtureManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_id: str = Field(alias="schema")
    graph_id: str
    page_id: str
    root_block_id: str
    source_revision: str
    page: _Page
    nodes: list[_Node]
    property_declarations: list[_PropertyDeclaration]
    semantic_sha256: str


class _Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    dmg_sha256: str
    app_asar_sha256: str
    archived_entry_path: Literal["js/logseq-cli.js"]
    archive_offset: int
    archive_size: int
    entry_sha256: str


class _Launcher(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    identity: str
    sha256: str
    argv_prefix: list[str]


class _ProtectedRoot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: Literal[
        "user_graph",
        "default_logseq",
        "account",
        "sync",
        "config",
        "working_directory",
    ]
    state: Literal["present", "absent"]
    reference: str


class _FixtureBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    semantic_sha256: str
    graph_id: str
    page_id: str
    root_block_id: str
    source_revision: str


class _Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_fixture_bytes: int
    max_nodes: int
    max_depth: int


class _ObserverStructure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_id: str = Field(alias="schema")
    static_record_sha256: str
    signer_fingerprint: str
    signature: str
    artifact: _Artifact
    launcher: _Launcher
    db0_policy: Literal["forbidden_state_changes:all"]
    protected_roots: list[_ProtectedRoot]
    fixture: _FixtureBinding
    observer_sha256: str
    config_sha256: str
    limits: _Limits
    commands: list[str]


@dataclass(frozen=True, slots=True)
class FixtureNode:
    """One exact synthetic block declaration."""

    id: str
    parent_id: str | None
    ordinal: int
    text: str


@dataclass(frozen=True, slots=True)
class FixturePropertyDeclaration:
    """One declared payload-compatible property shape, never a host value."""

    key: str
    wire_type: str
    cardinality: str
    scope: str


@dataclass(frozen=True, slots=True)
class FixtureManifest:
    """Immutable structural fixture declaration; not runtime fixture evidence."""

    graph_id: str
    page_id: str
    root_block_id: str
    source_revision: str
    page_title: str
    nodes: tuple[FixtureNode, ...]
    property_declarations: tuple[FixturePropertyDeclaration, ...]
    semantic_sha256: str
    raw_byte_length: int
    max_depth: int


@dataclass(frozen=True, slots=True)
class FixtureStructureCandidate:
    """A structurally valid candidate with no authentication or runtime meaning."""

    manifest: FixtureManifest


@dataclass(frozen=True, slots=True)
class ObserverStructureCandidate:
    """A structural candidate that explicitly grants no authenticated authority."""

    signer_fingerprint: str
    authentication_state: Literal["unverified"]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureStructureError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonfinite_json_literal(_: str) -> None:
    raise FixtureStructureError("non-finite JSON literals are not allowed")


def _reject_floating_point_json_literal(_: str) -> None:
    raise FixtureStructureError("floating-point JSON numbers are not allowed")


def _decode_fixture(raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_INPUT_BYTES:
        raise FixtureStructureError("fixture exceeds the structural byte limit")
    try:
        decoded = raw.decode("utf-8")
        value = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_json_literal,
            parse_float=_reject_floating_point_json_literal,
        )
    except FixtureStructureError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FixtureStructureError("fixture must be one valid UTF-8 JSON value") from exc
    if not isinstance(value, dict):
        raise FixtureStructureError("fixture root must be an object")
    return value


def _decode_observer(raw: bytes) -> dict[str, Any]:
    try:
        return _decode_fixture(raw)
    except FixtureStructureError as exc:
        raise ObserverStructureError(str(exc)) from exc


def _semantic_payload(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "semantic_sha256"}


def _require_sha256(value: str, field: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ObserverStructureError(f"{field} must be lowercase SHA-256")


def _require_identifier(value: str, field: str) -> None:
    if not value or len(value) > _MAX_IDENTIFIER_CHARS:
        raise FixtureStructureError(f"{field} is outside its structural bound")


def _require_nonempty_utf8_bytes(value: str, field: str, byte_limit: int) -> None:
    if not value or len(value.encode("utf-8")) > byte_limit:
        raise FixtureStructureError(f"{field} is outside its structural bound")


def _validate_fixture_topology(parsed: _FixtureManifest) -> int:
    _require_identifier(parsed.graph_id, "graph_id")
    _require_identifier(parsed.page_id, "page_id")
    _require_identifier(parsed.root_block_id, "root_block_id")
    _require_identifier(parsed.source_revision, "source_revision")
    _require_nonempty_utf8_bytes(parsed.page.title, "page.title", _MAX_PAGE_TITLE_BYTES)
    if not parsed.nodes or len(parsed.nodes) > _MAX_NODES:
        raise FixtureStructureError("fixture node count is outside the structural ceiling")
    seen_depth: dict[str, int] = {}
    next_ordinal: dict[str | None, int] = {None: 0}
    open_ancestry: list[str] = []
    max_depth = 0
    for position, node in enumerate(parsed.nodes):
        _require_identifier(node.id, "node.id")
        if len(node.text.encode("utf-8")) > _MAX_BLOCK_TEXT_BYTES:
            raise FixtureStructureError("node.text is outside its structural bound")
        if node.id in seen_depth:
            raise FixtureStructureError("fixture node IDs must be unique")
        if position == 0:
            if node.id != parsed.root_block_id or node.parent_id is not None or node.ordinal != 0:
                raise FixtureStructureError("selected root must be the first root node")
            depth = 1
            open_ancestry.append(node.id)
        else:
            if node.parent_id is None or node.parent_id not in seen_depth:
                raise FixtureStructureError("each non-root node must reference an earlier parent")
            while open_ancestry and open_ancestry[-1] != node.parent_id:
                open_ancestry.pop()
            if not open_ancestry:
                raise FixtureStructureError("fixture nodes must use depth-first preorder")
            depth = len(open_ancestry) + 1
        if depth > _MAX_DEPTH:
            raise FixtureStructureError("fixture depth is outside the structural ceiling")
        max_depth = max(max_depth, depth)
        expected = next_ordinal.get(node.parent_id, 0)
        if node.ordinal != expected:
            raise FixtureStructureError("sibling ordinals must be contiguous")
        next_ordinal[node.parent_id] = expected + 1
        seen_depth[node.id] = depth
        if position > 0:
            open_ancestry.append(node.id)
    declared: set[tuple[str, str]] = set()
    by_scope: dict[str, int] = {"page": 0, "block": 0}
    for declaration in parsed.property_declarations:
        _require_nonempty_utf8_bytes(declaration.key, "property key", _MAX_PROPERTY_KEY_BYTES)
        if declaration.wire_type not in _PROPERTY_WIRE_TYPES:
            raise FixtureStructureError("property declaration has an unsupported wire type")
        if declaration.cardinality not in {"one", "many"} or declaration.scope not in by_scope:
            raise FixtureStructureError("property declaration has an invalid shape")
        identity = (declaration.scope, declaration.key)
        if identity in declared:
            raise FixtureStructureError("property declarations must be unique per scope")
        declared.add(identity)
        by_scope[declaration.scope] += 1
        if by_scope[declaration.scope] > _MAX_PROPERTIES_PER_SCOPE:
            raise FixtureStructureError("property declarations exceed the structural ceiling")
    return max_depth


def parse_fixture_structure_bytes(raw: bytes) -> FixtureStructureCandidate:
    """Parse one digest-bound fixture declaration from in-memory bytes only."""

    value = _decode_fixture(raw)
    try:
        parsed = _FixtureManifest.model_validate(value)
    except ValidationError as exc:
        raise FixtureStructureError("fixture does not match the structural schema") from exc
    if parsed.schema_id != "plumber.logseq-db.fixture-structure/v1":
        raise FixtureStructureError("unsupported fixture schema")
    digest = hashlib.sha256(_canonical_json_bytes(_semantic_payload(value))).hexdigest()
    if parsed.semantic_sha256 != digest:
        raise FixtureStructureError("fixture semantic digest mismatch")
    max_depth = _validate_fixture_topology(parsed)
    nodes = tuple(
        FixtureNode(id=node.id, parent_id=node.parent_id, ordinal=node.ordinal, text=node.text)
        for node in parsed.nodes
    )
    return FixtureStructureCandidate(
        manifest=FixtureManifest(
            graph_id=parsed.graph_id,
            page_id=parsed.page_id,
            root_block_id=parsed.root_block_id,
            source_revision=parsed.source_revision,
            page_title=parsed.page.title,
            nodes=nodes,
            property_declarations=tuple(
                FixturePropertyDeclaration(
                    key=declaration.key,
                    wire_type=declaration.wire_type,
                    cardinality=declaration.cardinality,
                    scope=declaration.scope,
                )
                for declaration in parsed.property_declarations
            ),
            semantic_sha256=parsed.semantic_sha256,
            raw_byte_length=len(raw),
            max_depth=max_depth,
        )
    )


def parse_observer_structure_bytes(
    raw: bytes, fixture: FixtureStructureCandidate
) -> ObserverStructureCandidate:
    """Parse structural claims only; this function never authenticates an admission."""

    try:
        parsed = _ObserverStructure.model_validate(_decode_observer(raw))
    except ValidationError as exc:
        raise ObserverStructureError(
            "observer envelope does not match the structural schema"
        ) from exc
    if parsed.schema_id != "plumber.logseq-db.observer-structure/v1":
        raise ObserverStructureError("unsupported observer envelope schema")
    for field, digest in (
        ("static_record_sha256", parsed.static_record_sha256),
        ("artifact.dmg_sha256", parsed.artifact.dmg_sha256),
        ("artifact.app_asar_sha256", parsed.artifact.app_asar_sha256),
        ("artifact.entry_sha256", parsed.artifact.entry_sha256),
        ("launcher.sha256", parsed.launcher.sha256),
        ("fixture.semantic_sha256", parsed.fixture.semantic_sha256),
        ("observer_sha256", parsed.observer_sha256),
        ("config_sha256", parsed.config_sha256),
    ):
        _require_sha256(digest, field)
    if parsed.artifact.archive_offset < 0 or parsed.artifact.archive_size < 1:
        raise ObserverStructureError("archive containment facts are invalid")
    if not parsed.launcher.identity or not parsed.launcher.argv_prefix:
        raise ObserverStructureError("launcher identity and argument prefix are required")
    expected_roots = {
        "user_graph",
        "default_logseq",
        "account",
        "sync",
        "config",
        "working_directory",
    }
    if {root.kind for root in parsed.protected_roots} != expected_roots:
        raise ObserverStructureError("protected-root declarations are incomplete")
    if len(parsed.protected_roots) != len(expected_roots):
        raise ObserverStructureError("protected-root declarations must be unique")
    if tuple(parsed.commands) != (
        "property_inventory",
        "graph_info",
        "page_show",
        "root_show",
        "server_list",
    ):
        raise ObserverStructureError("observer command grammar is not DB-0")
    if parsed.limits.max_fixture_bytes < 1 or parsed.limits.max_fixture_bytes > 262_144:
        raise ObserverStructureError("fixture byte limit is outside the structural ceiling")
    if parsed.limits.max_nodes < 1 or parsed.limits.max_nodes > 500:
        raise ObserverStructureError("node limit is outside the structural ceiling")
    if parsed.limits.max_depth < 1 or parsed.limits.max_depth > 64:
        raise ObserverStructureError("depth limit is outside the structural ceiling")
    manifest = fixture.manifest
    if (
        parsed.fixture.semantic_sha256 != manifest.semantic_sha256
        or parsed.fixture.graph_id != manifest.graph_id
        or parsed.fixture.page_id != manifest.page_id
        or parsed.fixture.root_block_id != manifest.root_block_id
        or parsed.fixture.source_revision != manifest.source_revision
    ):
        raise ObserverStructureError(
            "observer fixture binding does not match the structural fixture"
        )
    if parsed.limits.max_fixture_bytes < manifest.raw_byte_length:
        raise ObserverStructureError("max_fixture_bytes cannot truncate the bound fixture")
    if parsed.limits.max_nodes < len(manifest.nodes):
        raise ObserverStructureError("max_nodes cannot truncate the bound fixture")
    if parsed.limits.max_depth < manifest.max_depth:
        raise ObserverStructureError("max_depth cannot truncate the bound fixture")
    return ObserverStructureCandidate(
        signer_fingerprint=parsed.signer_fingerprint,
        authentication_state="unverified",
    )
