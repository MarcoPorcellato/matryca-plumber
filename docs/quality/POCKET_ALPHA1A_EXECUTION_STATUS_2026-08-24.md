---
type: Runbook
title: Pocket Alpha 1A execution status
description: Maintained execution envelope for the bounded Pocket Alpha 1A contract work.
status: active
classification: active
audience: [maintainer, contributor]
owner: core-runtime
supersedes: []
related: []
---

# Pocket Alpha 1A execution status — 2026-08-24

| Field | Recorded value |
| --- | --- |
| Status | Alpha 1A execution envelope |
| Approved design | `7849017b91b830cb94271d606763697a0aebf336` |
| Implementation base | `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e` |
| Upstream snapshot | `af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e` |
| Branch | `feat/pocket-alpha1a-contracts` |
| Pre-code documentation HEAD | `2794b831827eba0dc1a31823d4d4df26a5de03a1` |
| Allowed repositories | `matryca-plumber` only |
| Allowed production paths | `src/contracts/pocket`, `scripts/build_pocket_contract_bundle.py` |
| Allowed artifact paths | `contracts/pocket/v1`, `tests/contracts/pocket`, `docs/contracts/POCKET_V1.md` |
| Dependency policy | no `pyproject.toml` or `uv.lock` change |
| Locked validator evidence | `pydantic` `2.13.4`; `jsonschema` `4.26.0` |
| Knowledge projection | `degraded: sources.toml unresolved` — `matryca_status`: `[Errno 2] No such file or directory: 'sources.toml'` |
| Remote Git authority | none |
| Next gate | canonical JSON RED test |

## Task 2 checkpoint ledger

Task 1 checkpoint: `375947dacfa48210103a91e81fd7935e08bb862f`.

The current gate is canonical JSON RED. The required RED command was:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_canonical.py -q --no-cov
```

It failed at collection with `ModuleNotFoundError: No module named 'src.contracts'`, as expected before the leaf package existed.

Task 2 intended commit subject: `feat(contracts): add Pocket canonical JSON`.
The resulting Task 2 SHA must be appended by Task 3; this task cannot record its own SHA.

R8–R10 recovery ruling corrected the plan's canonical digest vectors to
`5542d7da4dc43e39c1a568dedf22af565304b575c871db738c4a9a2718df75ba`. The
original missing-module RED evidence remains valid above. The exact focused
GREEN commands and terminal outcomes were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_canonical.py -q --no-cov
......                                                                   [100%]
6 passed in 0.03s

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff format src/contracts tests/contracts
6 files left unchanged

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check src/contracts tests/contracts
All checks passed!

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run mypy src/contracts tests/contracts
Success: no issues found in 6 source files
```

## Task 3 checkpoint ledger

Task 2 implementation checkpoint: `275bd1845945cc89d1585c46baedd4fc27746729`.
Task 2 evidence checkpoint: `9e9c607e6e4ee9e446ac75b6b8b316b30514ac47`.

The current gate is manifest-model RED. The required RED command is:

```text
rtk uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
```

The direct command could not initialize the sandbox-denied default uv cache at
`/Users/marco1/.cache/uv`. Re-running with the approved temporary cache reached
collection and produced the required RED receipt:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
ModuleNotFoundError: No module named 'src.contracts.pocket.models'
1 error in 0.10s
```

The manifest-model implementation adds closed, frozen source/file/manifest
records; validates canonical scalar and path invariants; rejects malformed
UUIDv7 values with `invalid_pack_id`; rejects duplicate source revisions with
`duplicate_source_revision`; and binds the inventory to its canonical content
root. The focused GREEN and static receipts were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_canonical.py tests/contracts/pocket/test_models.py -q --no-cov
................................                                         [100%]
32 passed in 0.08s

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff format src/contracts tests/contracts
8 files left unchanged

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check src/contracts tests/contracts
All checks passed!

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run mypy src/contracts tests/contracts
Success: no issues found in 8 source files
```

GitNexus is indexed only through `2794b831827eba0dc1a31823d4d4df26a5de03a1`,
three commits behind the implementation HEAD. No re-index was performed under
this envelope; live bounded source inspection supplied the current contract
context. The required `detect_changes` comparison against
`af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e`, scoped to this worktree, reported
`risk_level: low`, `affected_count: 0`, and no affected processes. Its changed
symbol inventory omitted the new models because the index predates Task 2; this
is an index limitation, not a zero-impact proof. No HIGH or CRITICAL finding
appeared. Task 4, not this task, must append this task's final SHA.

### Task 3 fix round 1: stable unknown-field code

The RED coverage changed the manifest unknown-field assertion and added direct
negative coverage for `SourceRevisionV1`, `PackFileV1`, and `PackManifestV1`.
The required RED command and terminal outcome were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov -k unknown_fields
FFF                                                                      [100%]
3 failed, 26 deselected in 0.07s
```

Each failure exposed Pydantic `extra_forbidden` text instead of the required
`unexpected_fields` stable contract code. The shared `_ClosedModel` now has a
single before-validator that checks mapping keys against `cls.model_fields`,
raises `PocketContractError("unexpected_fields")` before Pydantic's extra-field
handler, and retains `extra="forbid"`. Pydantic wraps that validator exception
in its public `ValidationError`, whose diagnostic contains the stable code.

The GREEN/static receipts were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
.............................                                            [100%]
29 passed in 0.08s

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff format src/contracts tests/contracts
8 files left unchanged

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check src/contracts tests/contracts
All checks passed!

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run mypy src/contracts tests/contracts
Success: no issues found in 8 source files
```

No GitNexus re-index was performed. `mcp__gitnexus__detect_changes`, compared
against `4c0ff6b96c7de00772a2b25935b73f6f73072c9e` in this worktree, reported
`changed_files: 3`, `changed_count: 0`, `affected_count: 0`, no affected
processes, and `risk_level: low`. The empty symbol inventory reflects the
known stale index and is not a zero-impact proof; no HIGH or CRITICAL finding
appeared. Task 4, not this fix round, must append this fix commit's final SHA.

## Task 4 checkpoint ledger

Task 3 implementation checkpoint: `4c0ff6b96c7de00772a2b25935b73f6f73072c9e`.
Task 3 evidence checkpoint: `a5d5495f7363ee09c4a8846d95bdb68c6fc10c6e`.

The current gate is document/evidence model RED. The required RED command is:

```text
rtk uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
```

The direct command could not initialize the sandbox-denied default uv cache at
`/Users/marco1/.cache/uv`. Re-running with the approved temporary cache reached
collection and produced the required RED receipt:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
ImportError: cannot import name 'DocumentV1' from 'src.contracts.pocket.models'
1 error in 0.11s
```

The implementation adds closed, frozen `DocumentV1` and `EvidenceV1` records,
the `LocatorKind` literal, and `validate_record_set`. The records reuse the
existing identifier, NFC, safe-path, and media-type helpers; source paths are
safe relative paths without a `payload` prefix requirement. The validator
enforces record bounds, sorted and unique identifiers, source/document
references, and evidence locator ordering. The focused GREEN and static
receipts were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
........................................................                 [100%]
56 passed in 0.10s

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff format src/contracts tests/contracts
8 files left unchanged

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check src/contracts tests/contracts
All checks passed!

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run mypy src/contracts tests/contracts
Success: no issues found in 8 source files
```

`mcp__gitnexus__impact` could not resolve `_ClosedModel` in the known-stale
index, so live bounded source inspection was used without re-indexing. Before
the commit, `mcp__gitnexus__detect_changes`, compared against
`af939e7e14e8f7f2e4dd5783bd3a72a1433adf1e` in this worktree, reported
`risk_level: low`, `affected_count: 0`, and no affected processes. Its broad
base comparison contains pre-existing historical symbols because the index
predates the Task 3/Task 4 leaves; it is not a zero-impact proof. No HIGH or
CRITICAL finding appeared. Task 5, not this task, must append this task's final
SHA.

### Task 4 fix round 1: source paths and media-type helper

The fix RED coverage adds a one-segment safe-relative `DocumentV1.source_path`
case (`README.md`) and explicit empty, `.`, and `..` negative cases. The
required RED command and terminal outcome were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov -k one_segment_safe_source_path
F                                                                        [100%]
1 failed, 56 deselected in 0.06s
```

The failure was `unsafe_bundle_path`: `_validate_safe_path` applied its
two-segment rule even when `payload_only=False`. The minimum correction keeps
that rule within the `payload_only` branch, preserving `PackFileV1`'s
`payload/...` boundary while allowing a valid one-segment document source path.
Empty, dot, dot-dot, absolute, backslash, control, non-NFC, and overlong paths
remain rejected. A single `_validate_media_type` helper now supplies the
existing NFC, regex, and `invalid_media_type` behavior to both `PackFileV1` and
`DocumentV1`, with no validation behavior change.

The focused GREEN and static receipts were:

```text
rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run pytest tests/contracts/pocket/test_models.py -q --no-cov
............................................................             [100%]
60 passed in 0.11s

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff format src/contracts tests/contracts
8 files left unchanged

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run ruff check src/contracts tests/contracts
All checks passed!

rtk env UV_CACHE_DIR=/private/tmp/uv-cache uv run mypy src/contracts tests/contracts
Success: no issues found in 8 source files
```

`mcp__gitnexus__impact` could not resolve `_validate_safe_path` in the
known-stale index. No re-index was performed; bounded inspection of the current
model and tests supplied the live context.

## Isolation and baseline evidence

The implementation checkout is a clean linked worktree on the recorded branch,
sharing the repository common Git directory. At envelope capture it was two
commits ahead of `origin/main`: design transplant
`68060eaac8b70eff31363927ed22fc4d858d99f4` and plan transplant
`2794b831827eba0dc1a31823d4d4df26a5de03a1`. The dependency diff against
`origin/main...HEAD` for `pyproject.toml` and `uv.lock` was empty.

The canonical checkout remains unmodified by this task. Its observed status was
`main...origin/main [behind 14]` with modified `docs/knowledge/inventory.json`,
modified `docs/knowledge/inventory.md`, untracked `.worktrees/`, and untracked
`docs/quality/REPOSITORY_GOVERNANCE_AND_AAIF_READINESS_PROGRAMME_2026-08-19.md`.

## Leaf-module and graph-audit boundary

Bounded source inspection found no `src/contracts/pocket` path at the recorded
base. The inspected existing modules are `src/memory/benchmark_protocol.py`,
`src/memory/evidence_models.py`, and `scripts/run_interop_tck.py`; this task
does not modify their symbols or introduce a runtime import surface.

The user-authorized `rtk gitnexus analyze` exited 0 at the pre-code
documentation HEAD, with no embeddings flag and no cleanup. `rtk gitnexus
status` then reported the implementation repository indexed and current at
`2794b831827eba0dc1a31823d4d4df26a5de03a1` (the full pre-code documentation
HEAD). The fresh GitNexus query for `closed immutable contracts canonical JSON
bundle`, scoped to `matryca-plumber-alpha1a-impl`, returned existing canonical
contract surfaces including `canonical_event_bytes` in
`src/memory/evidence_models.py` and no `src/contracts/pocket` definition or
runtime flow. This fresh code-audit evidence permits the documentation-only
Task 1 checkpoint; it does not authorize production changes.

## Checkpoint identity

Intended subject: `docs(contracts): authorize Pocket Alpha 1A execution`.
This checkpoint cannot contain its own SHA. The next task must append the actual
Task 1 checkpoint SHA only after a fresh code-audit gate permits its commit.

## Approved stop conditions

Stop without an implementation commit if:

- the base differs from the approved execution envelope;
- a new dependency becomes necessary without separate admission;
- structural JSON Schema and Pydantic validation disagree on an invariant both
  layers are specified to enforce;
- canonical vectors differ across two runs;
- any real content, secret, key material, network access, or out-of-scope
  repository change appears;
- the full required verification cannot finish green.
