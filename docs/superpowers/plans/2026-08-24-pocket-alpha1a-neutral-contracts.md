# Pocket Alpha 1A Neutral Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Plumber's closed, content-free, deterministic Pocket V1 contract bundle for future signed Mobile Knowledge Pack producers and offline Android consumers.

**Architecture:** Add a leaf `src/contracts/pocket` package containing strict Pydantic records, a bounded canonical JSON profile, schema rendering, cross-record validation, and deterministic filesystem bundle assembly. Commit language-neutral schemas, synthetic conformance cases, and golden vectors under `contracts/pocket/v1`; keep the command-line script thin and leave Knowledge, Pocket, runtime routes, network, persistence, signing operations, and real content untouched.

**Tech Stack:** Python 3.12, Pydantic v2 already declared by Plumber, locked `jsonschema` test validation when available in the exact environment, standard-library `json`, `hashlib`, `pathlib`, `tempfile`, and `shutil`, pytest, Ruff, mypy, uv.

**Spec:** [`docs/superpowers/specs/2026-08-24-pocket-alpha1a-neutral-contracts-design.md`](../specs/2026-08-24-pocket-alpha1a-neutral-contracts-design.md)

## Global Constraints

- The approved design commit is `7849017b91b830cb94271d606763697a0aebf336`; the design base is Plumber `origin/main@48eae93b1152c9fe7d1f19d63de3f781b686932e`.
- During planning, `origin/main` advanced to `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e`. Do not implement on this now-diverged planning branch. Task 1 must fetch again, start a fresh implementation branch/worktree from the then-current `origin/main`, transplant the approved design and plan documentation, resolve only documentation/generated-metadata conflicts, and requalify the result before code.
- Work only in an isolated worktree whose exact clean base is recorded before the first implementation edit; preserve the dirty canonical Plumber checkout without stash, reset, clean, checkout, or reinterpretation.
- Plumber is the sole authority for Pocket V1 schemas, content-free fixtures, canonical vectors, and the contract-bundle builder.
- Public top-level contracts are `PackManifestV1`, `DocumentV1`, and `EvidenceV1`; `SourceRevisionV1` and `PackFileV1` are closed nested definitions, with `SourceRevisionV1` also exposed as a Python domain record.
- Models are frozen and recursively closed; unknown fields, unsafe paths, duplicate identifiers, noncanonical order, broken references, invalid Unicode, invalid commits, invalid digests, and numeric overflow fail closed.
- Validation has two explicit layers. JSON Schema owns structural shape, types, limits, declared patterns, and closed objects. The complete contract validator owns those checks plus NFC, safe paths, canonical order, digest recomputation, uniqueness, and cross-record references. Every fixture declares separate `schema_status` and `contract_status`; only invariants specified for both layers require matching outcomes.
- Pocket Canonical JSON V1 admits only NFC strings, ASCII snake-case object keys, booleans, non-negative signed 64-bit integers, lists, and objects; it rejects floats and `null` and emits UTF-8 without BOM, whitespace, or trailing newline.
- No real Matryca content, citation, credential, secret, key material, usable signature, pack, SQLite schema, FTS, Atlas, graph, model, Android code, network access, download, source refresh, runtime route, database write, or consumer-repository edit enters Alpha 1A.
- `signature_algorithm="ed25519"` and bounded `key_id` are structural metadata only; cryptographic operations remain outside this plan.
- Do not add or edit a dependency declaration or lock entry. `pyproject.toml` and `uv.lock` must remain byte-unchanged; if locked `jsonschema` is not importable, stop and report the dependency gate instead of changing them.
- All shell commands in this plan use the required `rtk` prefix.
- Before editing an existing symbol, run the configured code-audit impact query. Before every commit, run diff-level `detect_changes` against the branch base, inspect every reported flow, and stop on HIGH or CRITICAL unexpected impact.
- Every commit stages explicit paths, carries maintainer-only authorship, and follows a fresh focused GREEN gate. Push, PR, merge, release, and announcement remain separate user authorization gates.
- The Matryca Knowledge MCP freshness check must be retried once during Task 1. If `sources.toml` remains unavailable, record `degraded` and continue from live source repositories without refreshing or repairing the derived plane.

---

## File Map

### New production files

- `src/contracts/__init__.py` — package boundary only; no runtime registration.
- `src/contracts/pocket/__init__.py` — narrow exports for the Pocket V1 contract surface.
- `src/contracts/pocket/canonical.py` — admitted JSON-domain validation, canonical bytes, line bytes, and SHA-256 helpers.
- `src/contracts/pocket/models.py` — closed Pydantic records, scalar invariants, content-root calculation, and cross-record validation.
- `src/contracts/pocket/bundle.py` — schema rendering, contract-bundle manifest, build, self-verification, and content-free receipt.
- `scripts/build_pocket_contract_bundle.py` — thin `argparse` adapter for build and verify operations.

### New contract artifacts

- `contracts/pocket/v1/schemas/pack-manifest.schema.json`
- `contracts/pocket/v1/schemas/document.schema.json`
- `contracts/pocket/v1/schemas/evidence.schema.json`
- `contracts/pocket/v1/vectors/canonical-json.json`
- `contracts/pocket/v1/fixtures/valid/minimal/*`
- `contracts/pocket/v1/fixtures/valid/unicode-citation/*`
- `contracts/pocket/v1/fixtures/invalid/*`

Each fixture case contains exactly `manifest.json`, `documents.jsonl`, `evidence.jsonl`, and `expectation.json`.

### New tests

- `tests/contracts/__init__.py`
- `tests/contracts/pocket/__init__.py`
- `tests/contracts/pocket/test_canonical.py`
- `tests/contracts/pocket/test_models.py`
- `tests/contracts/pocket/test_schemas.py`
- `tests/contracts/pocket/test_fixtures.py`
- `tests/contracts/pocket/test_bundle.py`
- `tests/contracts/pocket/test_cli.py`

### Documentation and generated metadata

- `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md` — exact base, gates, commits, checks, blockers, and next action.
- `docs/contracts/POCKET_V1.md` — public consumer contract and non-goals.
- `CHANGELOG.md` — replace the design-only Alpha 1A bullet with the implemented contract-bundle scope only after final GREEN.
- `docs/knowledge/inventory.json` and `docs/knowledge/inventory.md` — generated registration for the execution ledger, plan, and contract documentation.

---

### Task 1: Freeze the execution envelope and baseline

**Files:**
- Create: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: approved spec commit `7849017b91b830cb94271d606763697a0aebf336`, the exact implementation worktree HEAD, live `origin/main`, repository policy, and the locked Python environment.
- Produces: a durable execution ledger that every later task updates with exact commits and terminal checks.

- [ ] **Step 1: Reconcile the approved documentation onto fresh upstream**

Fetch `origin`, record its exact new SHA, and confirm whether it still equals the planning-time observation `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e`. Create a new named implementation branch and linked worktree directly from the freshly fetched `origin/main`; do not rebase, merge, clean, reset, stash, or edit the current planning worktree or canonical checkout.

Transplant the two local documentation commits from `docs/pocket-alpha1a-contract-design` onto that new branch. Resolve conflicts only in `CHANGELOG.md` and generated documentation inventories. The design file must equal commit `7849017b91b830cb94271d606763697a0aebf336` except for the explicitly approved two-layer validation correction in Sections 9-11; the plan file must equal the planning branch version byte-for-byte. Inspect both diffs, regenerate inventories, and run `rtk make docs-check`, `rtk make agents-check`, and `rtk git diff --check`. Stop before implementation if upstream changed the contract boundary or if preservation cannot be demonstrated.

- [ ] **Step 2: Verify isolation, branch, base, and canonical-checkout preservation**

Run in the implementation worktree:

```bash
rtk git rev-parse --git-dir
rtk git rev-parse --git-common-dir
rtk git rev-parse --show-toplevel
rtk git branch --show-current
rtk git rev-parse HEAD
rtk git rev-parse origin/main
rtk git status --short --branch
```

Run read-only in the canonical Plumber checkout:

```bash
rtk git status --short --branch
```

Expected: the implementation checkout is a linked, clean worktree on a named branch based on the freshly fetched upstream and containing the approved spec and plan; the canonical checkout still contains only its pre-existing user changes. Record every exact SHA and status line in the ledger.

- [ ] **Step 3: Verify the no-dependency gate**

Run:

```bash
rtk uv run python -c 'import importlib.metadata; print(importlib.metadata.version("pydantic")); print(importlib.metadata.version("jsonschema"))'
rtk git diff --exit-code origin/main...HEAD -- pyproject.toml uv.lock
```

Expected: both imports print versions from the existing lock graph and the dependency diff exits 0. If `jsonschema` is unavailable, stop with `BLOCKED: locked JSON Schema validator unavailable`; do not edit dependency files.

- [ ] **Step 4: Retry the read-only coordination freshness check once**

Call `matryca_status()` through the configured Matryca Knowledge MCP. Record its exact terminal state in the ledger. If it again reports missing `sources.toml`, record `degraded: sources.toml unresolved`; do not run a refresh, shell substitute, or registry repair.

- [ ] **Step 5: Confirm the new leaf-module insertion point**

Use the configured code-audit query for `closed immutable contracts canonical JSON bundle` and inspect current `src/memory/benchmark_protocol.py`, `src/memory/evidence_models.py`, and `scripts/run_interop_tck.py`. Record that `src/contracts/pocket` is new, imports no runtime surface, and does not modify an existing symbol. If code-audit data is stale or unavailable, record it and stop before a commit; do not re-index without separate authority.

- [ ] **Step 6: Create the execution ledger**

Write a maintained Markdown table containing these exact fields and the literal live values captured above. The committed ledger must contain no descriptive stand-ins for SHAs or branch names:

```markdown
| Field | Recorded value |
| --- | --- |
| Status | Alpha 1A execution envelope |
| Approved design | `7849017b91b830cb94271d606763697a0aebf336` |
| Implementation base | recorded 40-character worktree base SHA |
| Upstream snapshot | recorded 40-character `origin/main` SHA |
| Branch | recorded implementation branch name |
| Allowed repositories | `matryca-plumber` only |
| Allowed production paths | `src/contracts/pocket`, `scripts/build_pocket_contract_bundle.py` |
| Allowed artifact paths | `contracts/pocket/v1`, `tests/contracts/pocket`, `docs/contracts/POCKET_V1.md` |
| Dependency policy | no `pyproject.toml` or `uv.lock` change |
| Knowledge projection | exact `matryca_status` terminal state |
| Remote Git authority | none |
| Next gate | canonical JSON RED test |
```

Replace every `recorded` description with the observed literal value before staging. Add the approved stop conditions from the spec verbatim below the table, and fail a ledger test if any `recorded` marker remains.

- [ ] **Step 7: Register and verify the ledger**

Run:

```bash
rtk make docs-inventory-sync
rtk make docs-inventory-md
rtk make docs-check
rtk make agents-check
rtk git diff --check
```

Expected: every command exits 0 and the inventory contains the ledger as active maintainer documentation.

- [ ] **Step 8: Review and commit the envelope**

Call diff-level `detect_changes` against the recorded implementation base. Expected: documentation-only changes and no runtime flow. Then run:

```bash
rtk git add docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md docs/knowledge/inventory.json docs/knowledge/inventory.md
rtk git diff --cached --check
rtk git commit -m "docs(contracts): authorize Pocket Alpha 1A execution"
```

Update the ledger's next task only in the following task's commit; never amend this checkpoint after later code exists.

---

### Task 2: Implement Pocket Canonical JSON V1

**Files:**
- Create: `src/contracts/__init__.py`
- Create: `src/contracts/pocket/__init__.py`
- Create: `src/contracts/pocket/canonical.py`
- Create: `tests/contracts/__init__.py`
- Create: `tests/contracts/pocket/__init__.py`
- Create: `tests/contracts/pocket/test_canonical.py`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: built-in JSON-compatible Python values already bounded by callers.
- Produces: `PocketContractError`, `JsonValue`, `canonical_json_bytes(value) -> bytes`, `canonical_json_line(value) -> bytes`, and `canonical_json_sha256(value) -> str`.

- [ ] **Step 1: Write the failing canonical-byte tests**

Create `tests/contracts/pocket/test_canonical.py` with these assertions:

```python
from __future__ import annotations

import pytest

from src.contracts.pocket.canonical import (
    PocketContractError,
    canonical_json_bytes,
    canonical_json_line,
    canonical_json_sha256,
)


def test_canonical_json_has_exact_utf8_bytes_and_digest() -> None:
    value = {
        "title": "Città",
        "contract_version": "matryca-pocket-contract.v1",
    }
    expected = (
        b'{"contract_version":"matryca-pocket-contract.v1",'
        b'"title":"Citt\xc3\xa0"}'
    )

    assert canonical_json_bytes(value) == expected
    assert canonical_json_line(value) == expected + b"\n"
    assert canonical_json_sha256(value) == (
        "e9da76aa87d7b6c0c02dc6680c7a5ad0c34e82e7d779a0737ef078fcbdfb07c4"
    )


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ({"title": "Citta\u0300"}, "non_nfc_string"),
        ({"bad-key": "value"}, "invalid_object_key"),
        ({"score": 1.5}, "unsupported_json_type"),
        ({"value": None}, "unsupported_json_type"),
        ({"count": 2**63}, "integer_out_of_range"),
    ],
)
def test_canonical_json_rejects_values_outside_the_profile(
    value: object,
    code: str,
) -> None:
    with pytest.raises(PocketContractError, match=code):
        canonical_json_bytes(value)
```

- [ ] **Step 2: Run the canonical tests and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_canonical.py -q --no-cov
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src.contracts'`.

- [ ] **Step 3: Implement the minimal canonical module**

Create empty package initializers and implement this public surface in `canonical.py`:

```python
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | bool
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_INT = 2**63 - 1


class PocketContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _validate_json_value(value: object) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if not 0 <= value <= _MAX_INT:
            raise PocketContractError("integer_out_of_range")
        return
    if isinstance(value, str):
        if not unicodedata.is_normalized("NFC", value):
            raise PocketContractError("non_nfc_string")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or _KEY.fullmatch(key) is None:
                raise PocketContractError("invalid_object_key")
            _validate_json_value(item)
        return
    raise PocketContractError("unsupported_json_type")


def canonical_json_bytes(value: JsonValue) -> bytes:
    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json_line(value: JsonValue) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def canonical_json_sha256(value: JsonValue) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
```

Do not import Pydantic, filesystem code, CLI code, or any Matryca runtime module.

- [ ] **Step 4: Run focused tests, formatting, lint, and typing**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_canonical.py -q --no-cov
rtk uv run ruff format src/contracts tests/contracts
rtk uv run ruff check src/contracts tests/contracts
rtk uv run mypy src/contracts tests/contracts
```

Expected: every command exits 0; canonical tests report all cases passed.

- [ ] **Step 5: Review, update the ledger, and commit**

Record the RED and GREEN commands plus the exact resulting commit field in the execution ledger. Call diff-level `detect_changes`; expected impact is the new leaf package and its tests only. Then run:

```bash
rtk git add src/contracts tests/contracts docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "feat(contracts): add Pocket canonical JSON"
```

---

### Task 3: Add closed scalar and inventory models

**Files:**
- Create: `src/contracts/pocket/models.py`
- Create: `tests/contracts/pocket/test_models.py`
- Modify: `src/contracts/pocket/__init__.py`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: `canonical_json_sha256` from Task 2.
- Produces: `SourceRevisionV1`, `PackFileV1`, `PackManifestV1`, `payload_content_root(files) -> str`, and exact scalar constants shared by later records.

- [ ] **Step 1: Write failing closed-model tests**

Add factory helpers and these behaviors to `test_models.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.contracts.pocket.models import (
    PackFileV1,
    PackManifestV1,
    SourceRevisionV1,
    payload_content_root,
)

_A = "a" * 40
_B = "b" * 40
_DIGEST = "c" * 64


def _source(source_id: str = "knowledge") -> SourceRevisionV1:
    return SourceRevisionV1(
        source_id=source_id,
        repository_slug="Example/Knowledge",
        source_commit=_A,
    )


def _file(path: str = "payload/documents.jsonl") -> PackFileV1:
    return PackFileV1(
        path=path,
        media_type="application/x-ndjson",
        size_bytes=17,
        sha256=_DIGEST,
        record_count=1,
    )


def _valid_manifest_payload() -> dict[str, object]:
    files = (_file(),)
    return {
        "format_version": "matryca-pocket-pack.v1",
        "contract_version": "matryca-pocket-contract.v1",
        "pack_id": "01890f3e-7b2a-7cc3-98c4-dc0c0c07398f",
        "created_at": "2026-08-24T12:00:00Z",
        "generator_id": "matryca-knowledge",
        "generator_commit": _B,
        "signature_algorithm": "ed25519",
        "key_id": "alpha1-test-key",
        "sources": [_source().model_dump()],
        "files": [item.model_dump() for item in files],
        "content_root": payload_content_root(files),
    }


def _manifest() -> PackManifestV1:
    return PackManifestV1.model_validate(_valid_manifest_payload())


def test_manifest_is_closed_frozen_sorted_and_content_bound() -> None:
    files = (_file(),)
    manifest = PackManifestV1(
        format_version="matryca-pocket-pack.v1",
        contract_version="matryca-pocket-contract.v1",
        pack_id="01890f3e-7b2a-7cc3-98c4-dc0c0c07398f",
        created_at="2026-08-24T12:00:00Z",
        generator_id="matryca-knowledge",
        generator_commit=_B,
        signature_algorithm="ed25519",
        key_id="alpha1-test-key",
        sources=(_source(),),
        files=files,
        content_root=payload_content_root(files),
    )

    assert manifest.content_root == payload_content_root(files)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PackManifestV1.model_validate({**manifest.model_dump(), "secret": "forbidden"})
    with pytest.raises(ValidationError, match="frozen"):
        manifest.key_id = "changed"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("source_commit", "ABC", "invalid_source_commit"),
        ("repository_slug", "missing-slash", "invalid_repository_slug"),
        ("source_id", "UPPER", "invalid_source_id"),
    ],
)
def test_source_revision_rejects_invalid_scalars(
    field: str,
    value: str,
    code: str,
) -> None:
    payload = _source().model_dump()
    payload[field] = value
    with pytest.raises(ValueError, match=code):
        SourceRevisionV1.model_validate(payload)


def test_manifest_rejects_unsafe_paths_noncanonical_order_and_bad_root() -> None:
    with pytest.raises(ValueError, match="unsafe_bundle_path"):
        _file("../secret")
    with pytest.raises(ValueError, match="noncanonical_order"):
        PackManifestV1.model_validate(
            {
                **_valid_manifest_payload(),
                "files": [_file("payload/z").model_dump(), _file("payload/a").model_dump()],
            }
        )
    with pytest.raises(ValueError, match="content_root_mismatch"):
        PackManifestV1.model_validate({**_valid_manifest_payload(), "content_root": "0" * 64})
```

Keep `_valid_manifest_payload()` as the complete literal payload above; it may use the separately tested content-root helper but must not call manifest validation to manufacture the expected result.

- [ ] **Step 2: Run the model tests and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
```

Expected: import fails because `src.contracts.pocket.models` does not exist.

- [ ] **Step 3: Implement scalar helpers and closed nested records**

Implement in `models.py`:

```python
from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import PurePosixPath
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import JsonValue, PocketContractError, canonical_json_sha256

MAX_ID_LENGTH: Final[int] = 64
MAX_PATH_BYTES: Final[int] = 4_096
MAX_TITLE_CHARACTERS: Final[int] = 1_024
MAX_CITED_TEXT_CHARACTERS: Final[int] = 16_384
MAX_SOURCES: Final[int] = 128
MAX_FILES: Final[int] = 4_096
MAX_RECORDS: Final[int] = 1_000_000
MAX_FILE_BYTES: Final[int] = 2**31

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*$")
_UTC_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SourceRevisionV1(_ClosedModel):
    source_id: str = Field(max_length=MAX_ID_LENGTH)
    repository_slug: str = Field(max_length=200)
    source_commit: str = Field(json_schema_extra={"pattern": _GIT_COMMIT.pattern})


class PackFileV1(_ClosedModel):
    path: str
    media_type: str = Field(max_length=127)
    size_bytes: int = Field(ge=0, le=MAX_FILE_BYTES)
    sha256: str
    record_count: int = Field(ge=0, le=MAX_RECORDS)
```

Add model validators that reject with the stable codes from the tests. Put structural patterns required of both layers into `json_schema_extra` while retaining the explicit Pydantic validators that produce contract error codes; do not use custom JSON Schema keywords. Safe paths must use `PurePosixPath`, contain at least two segments, reject absolute paths, `.`, `..`, backslashes, controls, non-NFC text, paths over `MAX_PATH_BYTES`, and any first segment other than `payload`.

- [ ] **Step 4: Implement content root and manifest invariants**

Add:

```python
def payload_content_root(files: tuple[PackFileV1, ...]) -> str:
    payload = {"files": [item.model_dump(mode="json") for item in files]}
    return canonical_json_sha256(cast(JsonValue, payload))


class PackManifestV1(_ClosedModel):
    format_version: Literal["matryca-pocket-pack.v1"]
    contract_version: Literal["matryca-pocket-contract.v1"]
    pack_id: str
    created_at: str
    generator_id: str = Field(max_length=MAX_ID_LENGTH)
    generator_commit: str
    signature_algorithm: Literal["ed25519"]
    key_id: str = Field(max_length=MAX_ID_LENGTH)
    sources: tuple[SourceRevisionV1, ...] = Field(min_length=1, max_length=MAX_SOURCES)
    files: tuple[PackFileV1, ...] = Field(max_length=MAX_FILES)
    content_root: str

    @model_validator(mode="after")
    def _validate_manifest(self) -> "PackManifestV1":
        if str(uuid.UUID(self.pack_id)) != self.pack_id or uuid.UUID(self.pack_id).version != 7:
            raise PocketContractError("invalid_pack_id")
        if _UTC_SECOND.fullmatch(self.created_at) is None:
            raise PocketContractError("invalid_created_at")
        if tuple(sorted(self.sources, key=lambda item: item.source_id)) != self.sources:
            raise PocketContractError("noncanonical_order")
        if len({item.source_id for item in self.sources}) != len(self.sources):
            raise PocketContractError("duplicate_source_id")
        if tuple(sorted(self.files, key=lambda item: item.path)) != self.files:
            raise PocketContractError("noncanonical_order")
        if len({item.path for item in self.files}) != len(self.files):
            raise PocketContractError("duplicate_file_path")
        if payload_content_root(self.files) != self.content_root:
            raise PocketContractError("content_root_mismatch")
        return self
```

Validate generator ID, key ID, generator commit, SHA-256, media type, repository slug, NFC, and identifier fields with shared helpers; do not normalize invalid input.

- [ ] **Step 5: Export and run the focused gate**

Export only the public contract types and helpers from `src/contracts/pocket/__init__.py`. Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_canonical.py tests/contracts/pocket/test_models.py -q --no-cov
rtk uv run ruff format src/contracts tests/contracts
rtk uv run ruff check src/contracts tests/contracts
rtk uv run mypy src/contracts tests/contracts
```

Expected: every command exits 0.

- [ ] **Step 6: Review and commit the models**

Update the ledger with RED/GREEN evidence. Call diff-level `detect_changes`; expected impact remains the new contract package. Then run:

```bash
rtk git add src/contracts/pocket tests/contracts/pocket/test_models.py docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "feat(contracts): add Pocket V1 manifest models"
```

---

### Task 4: Add document, evidence, and cross-record validation

**Files:**
- Modify: `src/contracts/pocket/models.py`
- Modify: `src/contracts/pocket/__init__.py`
- Modify: `tests/contracts/pocket/test_models.py`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: `PackManifestV1` from Task 3.
- Produces: `DocumentV1`, `EvidenceV1`, `LocatorKind`, and `validate_record_set(manifest, documents, evidence) -> None`.

- [ ] **Step 1: Write failing document/evidence tests**

Add:

```python
from src.contracts.pocket.models import DocumentV1, EvidenceV1, validate_record_set


def _document() -> DocumentV1:
    return DocumentV1(
        document_id="doc-001",
        source_id="knowledge",
        title="Documento sintetico",
        source_path="docs/example.md",
        media_type="text/markdown",
    )


def _evidence() -> EvidenceV1:
    return EvidenceV1(
        evidence_id="evidence-001",
        document_id="doc-001",
        locator_kind="line_range",
        locator_start=10,
        locator_end=12,
        cited_text="Contenuto sintetico verificabile.",
    )


def test_record_set_accepts_complete_references() -> None:
    validate_record_set(_manifest(), (_document(),), (_evidence(),))


def test_record_set_rejects_missing_source_and_document_references() -> None:
    missing_source = DocumentV1.model_validate(
        {**_document().model_dump(), "source_id": "missing"}
    )
    with pytest.raises(ValueError, match="missing_source_reference"):
        validate_record_set(_manifest(), (missing_source,), ())

    missing_document = EvidenceV1.model_validate(
        {**_evidence().model_dump(), "document_id": "missing"}
    )
    with pytest.raises(ValueError, match="missing_document_reference"):
        validate_record_set(_manifest(), (_document(),), (missing_document,))


def test_evidence_rejects_reversed_locator_and_non_nfc_text() -> None:
    with pytest.raises(ValueError, match="invalid_locator_range"):
        EvidenceV1.model_validate(
            {**_evidence().model_dump(), "locator_start": 12, "locator_end": 10}
        )
    with pytest.raises(ValueError, match="non_nfc_string"):
        EvidenceV1.model_validate({**_evidence().model_dump(), "cited_text": "Citta\u0300"})
```

All mutated records above use fresh constructor validation; Pydantic copies do not revalidate by default.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
```

Expected: import fails for `DocumentV1`.

- [ ] **Step 3: Implement the records and reference validator**

Add:

```python
LocatorKind = Literal["line_range", "page", "record"]


class DocumentV1(_ClosedModel):
    document_id: str = Field(max_length=MAX_ID_LENGTH)
    source_id: str = Field(max_length=MAX_ID_LENGTH)
    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARACTERS)
    source_path: str
    media_type: str = Field(max_length=127)


class EvidenceV1(_ClosedModel):
    evidence_id: str = Field(max_length=MAX_ID_LENGTH)
    document_id: str = Field(max_length=MAX_ID_LENGTH)
    locator_kind: LocatorKind
    locator_start: int = Field(ge=1, le=MAX_RECORDS)
    locator_end: int = Field(ge=1, le=MAX_RECORDS)
    cited_text: str = Field(min_length=1, max_length=MAX_CITED_TEXT_CHARACTERS)

    @model_validator(mode="after")
    def _validate_locator(self) -> "EvidenceV1":
        if self.locator_end < self.locator_start:
            raise PocketContractError("invalid_locator_range")
        return self


def validate_record_set(
    manifest: PackManifestV1,
    documents: tuple[DocumentV1, ...],
    evidence: tuple[EvidenceV1, ...],
) -> None:
    if len(documents) > MAX_RECORDS or len(evidence) > MAX_RECORDS:
        raise PocketContractError("too_many_records")
    source_ids = {item.source_id for item in manifest.sources}
    document_ids = [item.document_id for item in documents]
    evidence_ids = [item.evidence_id for item in evidence]
    if document_ids != sorted(document_ids) or evidence_ids != sorted(evidence_ids):
        raise PocketContractError("noncanonical_order")
    if len(set(document_ids)) != len(document_ids):
        raise PocketContractError("duplicate_document_id")
    if len(set(evidence_ids)) != len(evidence_ids):
        raise PocketContractError("duplicate_evidence_id")
    if any(item.source_id not in source_ids for item in documents):
        raise PocketContractError("missing_source_reference")
    known_documents = set(document_ids)
    if any(item.document_id not in known_documents for item in evidence):
        raise PocketContractError("missing_document_reference")
```

Reuse scalar helpers for identifiers, source-relative paths, media types, NFC, and UTF-8 byte limits. `source_path` rejects absolute paths, backslashes, controls, `.`, and `..` but does not require the `payload` prefix used by `PackFileV1`.

- [ ] **Step 4: Run focused tests and static checks**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
rtk uv run ruff format src/contracts tests/contracts
rtk uv run ruff check src/contracts tests/contracts
rtk uv run mypy src/contracts tests/contracts
```

Expected: every command exits 0.

- [ ] **Step 5: Review and commit cross-record validation**

Update the ledger and run diff-level `detect_changes`. Inspect the contract-package-only result, then run:

```bash
rtk git add src/contracts/pocket tests/contracts/pocket/test_models.py docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "feat(contracts): validate Pocket evidence records"
```

---

### Task 5: Render closed schemas and commit the conformance corpus

**Files:**
- Create: `src/contracts/pocket/bundle.py`
- Create: `tests/contracts/pocket/test_schemas.py`
- Create: `tests/contracts/pocket/test_fixtures.py`
- Create: `contracts/pocket/v1/schemas/pack-manifest.schema.json`
- Create: `contracts/pocket/v1/schemas/document.schema.json`
- Create: `contracts/pocket/v1/schemas/evidence.schema.json`
- Create: `contracts/pocket/v1/vectors/canonical-json.json`
- Create: `contracts/pocket/v1/fixtures/valid/minimal/*`
- Create: `contracts/pocket/v1/fixtures/valid/unicode-citation/*`
- Create: `contracts/pocket/v1/fixtures/invalid/*`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: canonicalization and all models from Tasks 2-4; locked `jsonschema.Draft202012Validator` in tests only.
- Produces: `render_schema_files() -> dict[str, bytes]`, committed schema bytes, canonical vectors, and deterministic valid/invalid cases. Fixture loading and JSON Schema execution remain test-only helpers.

- [ ] **Step 1: Write failing schema-rendering tests**

Create `test_schemas.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.contracts.pocket.bundle import render_schema_files

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = ROOT / "contracts/pocket/v1/schemas"


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
```

- [ ] **Step 2: Run the schema test and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_schemas.py -q --no-cov
```

Expected: import fails because `src.contracts.pocket.bundle` does not exist.

- [ ] **Step 3: Implement deterministic schema rendering**

Add this initial surface to `bundle.py`:

```python
from __future__ import annotations

from typing import cast

from pydantic import BaseModel

from .canonical import JsonValue, canonical_json_bytes
from .models import DocumentV1, EvidenceV1, PackManifestV1

_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "schemas/document.schema.json": DocumentV1,
    "schemas/evidence.schema.json": EvidenceV1,
    "schemas/pack-manifest.schema.json": PackManifestV1,
}


def render_schema_files() -> dict[str, bytes]:
    return {
        path: canonical_json_bytes(
            cast(
                JsonValue,
                model.model_json_schema(
                    mode="validation",
                    ref_template="#/$defs/{model}",
                ),
            )
        )
        for path, model in sorted(_SCHEMA_MODELS.items())
    }
```

Generate the three schema files from this function once, then commit the exact output. Do not hand-edit generated schemas; tests enforce regeneration parity.

- [ ] **Step 4: Add canonical golden vectors**

Commit `vectors/canonical-json.json` as canonical JSON describing cases with `name`, admitted JSON `value`, exact UTF-8 text, and SHA-256. Include at least:

```json
{"cases":[{"canonical_text":"{\"contract_version\":\"matryca-pocket-contract.v1\",\"title\":\"Città\"}","name":"italian-nfc","sha256":"e9da76aa87d7b6c0c02dc6680c7a5ad0c34e82e7d779a0737ef078fcbdfb07c4","value":{"contract_version":"matryca-pocket-contract.v1","title":"Città"}}]}
```

Add test cases for the empty file inventory, booleans, `0`, `2**63 - 1`, nested objects, and array order. Add rejection vectors for decomposed Unicode, `null`, float, non-snake-case key, negative integer, and `2**63`; rejection vectors name an error code and omit canonical bytes.

- [ ] **Step 5: Commit valid fixture cases**

Use this exact minimal manifest content, with canonical key order and no trailing newline:

```json
{"content_root":"602e35a92eec4bc0a2ec6ae113f07bfc6933322fb69fe8dee416e5a67217e2a2","contract_version":"matryca-pocket-contract.v1","created_at":"2026-08-24T12:00:00Z","files":[],"format_version":"matryca-pocket-pack.v1","generator_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","generator_id":"matryca-knowledge","key_id":"alpha1-test-key","pack_id":"01890f3e-7b2a-7cc3-98c4-dc0c0c07398f","signature_algorithm":"ed25519","sources":[{"repository_slug":"Example/Knowledge","source_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","source_id":"knowledge"}]}
```

For `valid/minimal`, commit one canonical document row, one canonical evidence row, and `{"contract_status":"valid","schema_status":"valid"}`. For `valid/unicode-citation`, use NFC Italian title `Città della conoscenza` and cited text `È una citazione sintetica.`; keep IDs sorted and all provenance synthetic. Both valid cases must pass both layers.

- [ ] **Step 6: Commit the exact invalid-case matrix**

Create one directory per row. Each case mutates only the named invariant from `valid/minimal`. A structural case uses canonical `{"contract_error_code":"CODE","contract_status":"invalid","schema_status":"invalid"}`. A semantic case uses canonical `{"contract_error_code":"CODE","contract_status":"invalid","schema_status":"valid"}`. JSON Schema diagnostics are not a stable public error-code surface.

| Case directory | Exact mutation | Schema | Contract code |
| --- | --- | --- | --- |
| `unknown-field` | add manifest field `secret` | invalid | `unexpected_fields` |
| `invalid-commit` | set source commit to uppercase `A` repeated 40 times | invalid | `invalid_source_commit` |
| `unsafe-path` | set document `source_path` to `../secret.md` | valid | `unsafe_source_path` |
| `non-nfc-title` | set title to `Citta\u0300` | valid | `non_nfc_string` |
| `duplicate-source` | repeat the same manifest source | valid | `duplicate_source_id` |
| `noncanonical-files` | add `payload/z` before `payload/a` with valid metadata | valid | `noncanonical_order` |
| `missing-source-reference` | set document `source_id` to `missing` | valid | `missing_source_reference` |
| `missing-document-reference` | set evidence `document_id` to `missing` | valid | `missing_document_reference` |
| `invalid-locator-range` | set locator start `12` and end `10` | valid | `invalid_locator_range` |
| `content-root-mismatch` | set `content_root` to 64 zeroes | valid | `content_root_mismatch` |

- [ ] **Step 7: Implement the test-only fixture harness and layer assertions**

Define only in `test_fixtures.py`:

```python
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FixtureExpectation:
    schema_status: str
    contract_status: str
    contract_error_code: str | None


def load_expectation(path: Path) -> FixtureExpectation:
    raw = json.loads(path.read_bytes())
    assert set(raw) in (
        {"contract_status", "schema_status"},
        {"contract_error_code", "contract_status", "schema_status"},
    )
    return FixtureExpectation(**raw)
```

In the same test module, implement bounded helpers that read each file with explicit byte limits and parse JSONL row-by-row. Run the three committed schemas through `Draft202012Validator`, then independently validate Pydantic models and call `validate_record_set`. Compare each observed layer with its declared status and compare only the complete contract failure with `contract_error_code`. Assert structural cases fail both layers, semantic cases pass schema and fail contract, and valid cases pass both. Production `bundle.py` must not import `jsonschema` or fixture-test helpers.

- [ ] **Step 8: Run schema and fixture gates**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_canonical.py tests/contracts/pocket/test_models.py tests/contracts/pocket/test_schemas.py tests/contracts/pocket/test_fixtures.py -q --no-cov
rtk uv run ruff format src/contracts tests/contracts
rtk uv run ruff check src/contracts tests/contracts
rtk uv run mypy src/contracts tests/contracts
```

Expected: all schemas pass Draft 2020-12 meta-validation; valid fixtures pass both layers; structural invalid cases fail both; semantic invalid cases pass schema and fail the complete contract validator with their declared code; static checks exit 0.

- [ ] **Step 9: Review and commit schemas and fixtures**

Update the ledger with case counts and exact checks. Call diff-level `detect_changes`; inspect the new leaf package, schemas, and content-free fixtures. Then run:

```bash
rtk git add src/contracts/pocket/bundle.py contracts/pocket/v1 tests/contracts/pocket/test_schemas.py tests/contracts/pocket/test_fixtures.py docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "feat(contracts): add Pocket V1 conformance corpus"
```

---

### Task 6: Build and verify deterministic contract bundles

**Files:**
- Modify: `src/contracts/pocket/bundle.py`
- Create: `tests/contracts/pocket/test_bundle.py`
- Modify: `src/contracts/pocket/__init__.py`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: committed `contracts/pocket/v1` source tree and canonical helpers.
- Produces: `BundleFileV1`, `ContractBundleManifestV1`, `BundleReceipt`, `build_contract_bundle(source_root, output_dir) -> BundleReceipt`, and `verify_contract_bundle(bundle_dir) -> BundleReceipt`.

- [ ] **Step 1: Write failing deterministic-build tests**

Create `test_bundle.py` with:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.contracts.pocket.bundle import (
    build_contract_bundle,
    verify_contract_bundle,
)
from src.contracts.pocket.canonical import PocketContractError

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "contracts/pocket/v1"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_two_builds_are_byte_identical_and_self_verifying(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_receipt = build_contract_bundle(SOURCE, first)
    second_receipt = build_contract_bundle(SOURCE, second)

    assert first_receipt == second_receipt
    assert _tree_digest(first) == _tree_digest(second)
    assert verify_contract_bundle(first) == first_receipt


def test_tamper_extra_file_and_nonempty_destination_fail_closed(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_contract_bundle(SOURCE, bundle)
    schema = bundle / "schemas/document.schema.json"
    schema.write_bytes(schema.read_bytes() + b" ")
    with pytest.raises(PocketContractError, match="bundle_digest_mismatch"):
        verify_contract_bundle(bundle)

    extra = tmp_path / "extra"
    build_contract_bundle(SOURCE, extra)
    (extra / "unexpected").write_text("x", encoding="utf-8")
    with pytest.raises(PocketContractError, match="unexpected_bundle_file"):
        verify_contract_bundle(extra)

    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "keep").write_text("keep", encoding="utf-8")
    with pytest.raises(PocketContractError, match="output_not_empty"):
        build_contract_bundle(SOURCE, occupied)
```

Add symlink, FIFO/non-regular file where supported, missing file, unsafe relative name, interrupted staging cleanup, and bundle-manifest mutation tests. Skip only platform-impossible FIFO creation with an explicit pytest platform condition; never skip path or symlink cases.

- [ ] **Step 2: Run bundle tests and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_bundle.py -q --no-cov
```

Expected: import fails for `build_contract_bundle`.

- [ ] **Step 3: Implement internal bundle models**

Add frozen internal records with no timestamps:

```python
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _ClosedBundleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BundleFileV1(_ClosedBundleModel):
    path: str
    size_bytes: int = Field(ge=0, le=2**31)
    sha256: str


class ContractBundleManifestV1(_ClosedBundleModel):
    bundle_version: Literal["matryca-pocket-contract-bundle.v1"]
    files: tuple[BundleFileV1, ...]
    content_root: str


@dataclass(frozen=True, slots=True)
class BundleReceipt:
    bundle_digest: str
    content_root: str
    file_count: int
```

Compute `content_root` from canonical `{"files": FILES}` bytes and `bundle_digest` from canonical bundle-manifest bytes. Validate sorted unique paths, lowercase digests, bounded file count, and content-root equality.

- [ ] **Step 4: Implement safe collection and verification**

Implement `_collect_source_files` returning `tuple[BundleFileV1, ...]`, `_write_bundle_manifest` returning `bytes`, `build_contract_bundle` returning `BundleReceipt`, and `verify_contract_bundle` returning `BundleReceipt`. All path parameters are `Path`. Keep the first two helpers private and export only the build/verify functions and receipt.

Required behavior:

- resolve neither user path through a symlink;
- require `source_root` to be an existing directory and every collected entry to be a regular non-symlink file;
- reject `bundle-manifest.json` in source input;
- use lexical POSIX paths and the same traversal/control/NFC rules as the spec;
- cap source file count at 4,096, individual size at 32 MiB, and total bundle size at 256 MiB before reading bytes;
- build in a sibling directory created by `tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent)`;
- copy bytes without preserving host timestamps or modes as contract data;
- write canonical `bundle-manifest.json`, self-verify staging, then rename staging to the absent or empty destination;
- remove staging on every exception and leave the requested destination absent or unchanged;
- compare the observed regular-file set exactly during verification;
- return only digests and count; never include absolute paths or fixture content in errors or receipts.

- [ ] **Step 5: Run focused bundle and static gates**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_bundle.py -q --no-cov
rtk uv run pytest tests/contracts/pocket -q --no-cov
rtk uv run ruff format src/contracts tests/contracts
rtk uv run ruff check src/contracts tests/contracts
rtk uv run mypy src/contracts tests/contracts
```

Expected: deterministic and adversarial bundle tests pass; all prior contract tests remain green.

- [ ] **Step 6: Review and commit the bundle core**

Update the ledger with deterministic digests from the test receipt and exact checks. Call diff-level `detect_changes`, inspect bundle filesystem paths and error surfaces, then run:

```bash
rtk git add src/contracts/pocket tests/contracts/pocket/test_bundle.py docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "feat(contracts): build deterministic Pocket bundles"
```

---

### Task 7: Add the thin CLI and public contract documentation

**Files:**
- Create: `scripts/build_pocket_contract_bundle.py`
- Create: `tests/contracts/pocket/test_cli.py`
- Create: `docs/contracts/POCKET_V1.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`

**Interfaces:**
- Consumes: `build_contract_bundle` and `verify_contract_bundle` from Task 6.
- Produces: repository-only build/verify command and maintained consumer documentation; no installed console entry point.

- [ ] **Step 1: Write failing CLI tests**

Create `test_cli.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/build_pocket_contract_bundle.py"
SOURCE = ROOT / "contracts/pocket/v1"


def test_cli_builds_and_verifies_without_absolute_path_output(tmp_path: Path) -> None:
    output = tmp_path / "bundle"
    built = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "build",
            "--source-dir",
            str(SOURCE),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    build_receipt = json.loads(built.stdout)
    assert set(build_receipt) == {"bundle_digest", "content_root", "file_count"}
    assert str(tmp_path) not in built.stdout

    verified = subprocess.run(
        [sys.executable, str(SCRIPT), "verify", "--bundle-dir", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(verified.stdout) == build_receipt
```

Add tests for nonempty output and tampered verification. Assert nonzero exit, stable code on stderr, empty stdout, unchanged existing files, and no absolute path disclosure.

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```bash
rtk uv run pytest tests/contracts/pocket/test_cli.py -q --no-cov
```

Expected: subprocess exits nonzero because the script is absent.

- [ ] **Step 3: Implement the thin script**

Use this shape without adding a `[project.scripts]` entry:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from src.contracts.pocket.bundle import build_contract_bundle, verify_contract_bundle
from src.contracts.pocket.canonical import PocketContractError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify Pocket V1 contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source-dir", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        receipt = (
            build_contract_bundle(args.source_dir, args.output_dir)
            if args.command == "build"
            else verify_contract_bundle(args.bundle_dir)
        )
    except PocketContractError as exc:
        print(exc.code, file=sys.stderr)
        return 2
    print(json.dumps(asdict(receipt), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Resolve no path solely for display. Production error handling prints only the stable code.

- [ ] **Step 4: Write the public Pocket V1 documentation**

`docs/contracts/POCKET_V1.md` must document:

- authority and the exact V1 model names;
- scalar limits and stable error-code table;
- manifest content-root formula and bundle content-root formula;
- canonical JSON admitted subset and exact vector location;
- fixture directory contract and synthetic-only status;
- build and verify commands using explicit local paths;
- pinning rule: consumer records Plumber commit and bundle digest, copies only manifest-listed files, and never fetches a moving branch;
- signature metadata versus deferred cryptographic operations;
- explicit non-goals for real packs, Knowledge, Pocket, network, persistence, models, and release qualification.

Use these command examples:

```bash
rtk uv run python scripts/build_pocket_contract_bundle.py build --source-dir contracts/pocket/v1 --output-dir /private/tmp/pocket-contract-v1
rtk uv run python scripts/build_pocket_contract_bundle.py verify --bundle-dir /private/tmp/pocket-contract-v1
```

- [ ] **Step 5: Update changelog, inventory, and ledger**

Replace the current design-only Alpha 1A changelog bullet with one `### Added` bullet that states the implemented result precisely: closed content-free models, schemas, canonical vectors, synthetic fixtures, deterministic build/verify command, and no pack/runtime/consumer behavior. Do not claim Alpha 1B, Alpha 1C, real content, signing qualification, or release readiness.

Update the ledger to list every commit, focused check, remaining full-CI gate, exact bundle digest from two builds, and next action `final qualification`.

Run:

```bash
rtk make docs-inventory-sync
rtk make docs-inventory-md
rtk make docs-check
rtk make agents-check
```

Expected: all commands exit 0 and both new maintained documents are present in the generated inventory.

- [ ] **Step 6: Run focused CLI and contract gates**

Run:

```bash
rtk uv run pytest tests/contracts/pocket -q --no-cov
rtk uv run ruff format scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk uv run ruff check scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk uv run mypy scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk git diff --exit-code origin/main...HEAD -- pyproject.toml uv.lock
rtk git diff --check
```

Expected: all commands exit 0 and dependency files remain unchanged.

- [ ] **Step 7: Review and commit CLI and docs**

Call diff-level `detect_changes`, inspect the repository-only script surface and confirm no installed CLI/MCP/runtime path changed. Then run:

```bash
rtk git add scripts/build_pocket_contract_bundle.py tests/contracts/pocket/test_cli.py docs/contracts/POCKET_V1.md CHANGELOG.md docs/knowledge/inventory.json docs/knowledge/inventory.md docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md
rtk git diff --cached --check
rtk git commit -m "docs(contracts): publish Pocket V1 bundle contract"
```

---

### Task 8: Qualify the exact Alpha 1A implementation commit

**Files:**
- Modify: `docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md`
- Modify: `docs/knowledge/inventory.json` only if the ledger metadata changes require regeneration
- Modify: `docs/knowledge/inventory.md` only through its generator

**Interfaces:**
- Consumes: every Task 1-7 commit on one exact implementation branch.
- Produces: a terminal `ALPHA 1A PASS` or an evidence-bounded blocked result; no remote action.

- [ ] **Step 1: Run the full local qualification**

Run from a clean worktree:

```bash
rtk git status --short --branch
rtk uv run pytest tests/contracts/pocket -q --no-cov
rtk uv run ruff format --check scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk uv run ruff check scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk uv run mypy scripts/build_pocket_contract_bundle.py src/contracts tests/contracts
rtk make docs-check
rtk make agents-check
rtk git diff --exit-code origin/main...HEAD -- pyproject.toml uv.lock
rtk git diff --check
rtk make ci
```

Expected: every command exits 0. `make ci` is the terminal repository gate; focused checks do not substitute for it.

- [ ] **Step 2: Produce two exact bundle receipts**

Use two new empty directories and run the repository-only command twice. Verify both. Record the exact command lines, output directories, `bundle_digest`, `content_root`, `file_count`, Python version, Pydantic version, jsonschema version, branch, and HEAD in the ledger. Compare every manifest-listed file digest; equal receipt JSON alone is insufficient if file comparison was not run.

Expected: both bundle trees, bundle manifests, receipts, and per-file hashes are byte-identical.

- [ ] **Step 3: Run the final code-audit gate**

Call `detect_changes` against the recorded implementation base, inspect every affected symbol and execution flow, and record the terminal result. Expected: only the new leaf contract package, repository-only script, content-free artifacts, tests, and docs. Any unexpected MCP, CLI entry point, graph, Shadow, daemon, network, persistence, or packaging route is a stop condition.

- [ ] **Step 4: Finalize the ledger and re-run documentation checks**

Set the ledger status to `ALPHA 1A PASS` only when Tasks 1-3 are terminal green. Otherwise record the exact blocked check and leave status non-PASS. List these broader gates as explicitly unproven: Alpha 1B pack production/signing, real Knowledge content, Alpha 1C Android admission/search, Pixel qualification, production trust, push, PR, merge, and release.

Run:

```bash
rtk make docs-inventory-sync
rtk make docs-inventory-md
rtk make docs-check
rtk git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 5: Review and create the local qualification checkpoint**

Call `detect_changes` once more after the ledger edit. Stage only the ledger and mechanically updated inventory files:

```bash
rtk git add docs/quality/POCKET_ALPHA1A_EXECUTION_STATUS_2026-08-24.md docs/knowledge/inventory.json docs/knowledge/inventory.md
rtk git diff --cached --check
rtk git commit -m "docs(contracts): qualify Pocket Alpha 1A"
rtk git status --short --branch
rtk git rev-parse HEAD
```

Expected: the worktree is clean and the final command prints the exact local Alpha 1A qualification commit. Stop there. Do not push, open a PR, merge, tag, release, or start Alpha 1B without separate user authorization.
