# MLflow Evaluation Projection PR A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, content-free, source-bound projection of the four synthetic graph-outcome scenarios without adding, importing, or contacting MLflow.

**Architecture:** A maintainer-only outer adapter under `tools/evaluation_projection/` consumes validated `EpisodeRun` values but never changes canonical Matryca contracts. Closed Pydantic models, a recursive privacy guard, exact Git provenance, and atomic output produce one byte-stable suite document; a thin script is the only command surface. Production modules under `src/` never import the adapter, and a future publisher may consume only the closed suite after a separate design gate.

**Tech Stack:** Python 3.12+, Pydantic 2, pytest, standard-library `hashlib`, `json`, `os`, `pathlib`, `subprocess`, and `tempfile`; no new dependency and no MLflow import.

**Spec:** [`docs/superpowers/specs/2026-08-26-mlflow-evaluation-projection-design.md`](../specs/2026-08-26-mlflow-evaluation-projection-design.md)

## Global Constraints

- PR A accepts only synthetic graph-outcome `EpisodeRun` evidence; `BenchmarkRunReport`, real vaults, Shadow databases, providers, models, and arbitrary input files are excluded.
- Canonical task, report, receipt, validator, bytes, IDs, and statuses remain unchanged.
- Schema IDs are exactly `matryca-graph-outcome-evaluation-projection.v1` and `matryca-graph-outcome-evaluation-projection-suite.v1`.
- Protocol schema v1 is exactly `graph-outcome-protocol.v1`; unsupported schema or protocol versions reject rather than entering the identity domain.
- Source revisions are lowercase full 40-character hexadecimal commits.
- Projection and suite identities are lowercase SHA-256 values over canonical JSON payload bytes without their identity field or trailing newline.
- Final emitted JSON uses ASCII escaping, recursive key sorting, compact separators, and exactly one trailing newline.
- No timestamps, generated IDs, paths, usernames, hostnames, credentials, arbitrary metadata, raw logs, prompts, answers, or graph content may enter output.
- The canonical bounded `elapsed_milliseconds` duration is allowed; generated-at, start/end, timezone, and framework timestamps are forbidden.
- File output validates the complete suite before writing, refuses overwrite by default, rejects symlink destinations, and never leaves partial output.
- MLflow remains absent from default/dev dependencies, imports, processes, network activity, and documentation claims of completed integration.
- Public files and commit metadata use maintainer voice only and contain no assistant or local-tool attribution.
- Every code task follows red-green-refactor TDD and ends in one signed local commit.

---

### Task 1: Closed projection schema and deterministic identities

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/evaluation_projection/__init__.py`
- Create: `tools/evaluation_projection/schema.py`
- Create: `tests/tools/evaluation_projection/__init__.py`
- Create: `tests/tools/evaluation_projection/test_schema.py`

**Interfaces:**
- Consumes: closed literal types from `src.memory.graph_outcome_protocol`.
- Produces: `ProjectionDimension`, `ProjectionMetrics`, `ProjectionArtifact`, `GraphOutcomeProjectionPayload`, `GraphOutcomeEvaluationProjection`, `GraphOutcomeSuitePayload`, `GraphOutcomeEvaluationSuite`, `canonical_projection_bytes()`, `canonical_suite_bytes()`, `build_projection(payload: GraphOutcomeProjectionPayload)`, and `build_suite(payload: GraphOutcomeSuitePayload)`.

- [ ] **Step 1: Write failing schema and identity tests**

Create fixtures that use only fixed lowercase digests and identifiers. Cover:

```python
def test_projection_and_suite_have_stable_canonical_identities() -> None:
    first = build_projection(_payload())
    second = build_projection(_payload())
    suite = build_suite(GraphOutcomeSuitePayload(
        source_revision=_REVISION,
        protocol_schema_version="graph-outcome-protocol.v1",
        projections=_four_projections(),
    ))

    assert first == second
    assert len(first.projection_id) == 64
    assert canonical_projection_bytes(first).endswith(b"\n")
    assert len(suite.suite_id) == 64
    assert canonical_suite_bytes(suite).endswith(b"\n")


def test_reordered_closed_collections_are_byte_identical() -> None:
    original = build_projection(_payload())
    reordered = build_projection(_reordered_payload())
    assert canonical_projection_bytes(original) == canonical_projection_bytes(reordered)


def test_changed_allowlisted_value_invalidates_identity() -> None:
    original = build_projection(_payload())
    changed = build_projection(_payload(source_revision="b" * 40))
    assert original.projection_id != changed.projection_id


def test_closed_models_reject_unknown_fields_and_invalid_hashes() -> None:
    with pytest.raises(ValidationError):
        ProjectionArtifact.model_validate(
            {"kind": "tool_ledger", "digest": "bad", "record_count": 1, "extra": "x"}
        )
```

Define `_REVISION = "a" * 40`, `_DIGEST = "1" * 64`, and `_SCENARIOS` as the exact four scenario literals. `_payload()` returns `GraphOutcomeProjectionPayload` with five dimension entries, every metrics field, nine required artifact kinds, four fingerprints, and the approved scalar/tuple fields. `_reordered_payload()` reverses dimensions, artifacts, tool IDs, failure codes, and check IDs without changing their values. `_four_projections()` calls `build_projection(_payload(scenario=name))` once per scenario. Parameterize identity invalidation across every accepted variable top-level scalar, tuple member, dimension field, metrics field, artifact field, and source revision. Assert construction rejects false isolation/cleanup invariants, incomplete or duplicate dimensions/artifacts, invalid dimension check combinations, inconsistent metric counts, unsupported projection/suite/protocol schema versions, and over-limit identifier collections. Assert suite construction rejects a missing scenario, duplicate scenario, unsupported scenario, mixed source revision, and mixed protocol version.

- [ ] **Step 2: Run the schema tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_schema.py
```

Expected: collection fails because `tools.evaluation_projection.schema` does not exist.

- [ ] **Step 3: Implement the closed models and canonical serializer**

Use one frozen base model and explicit field models:

```python
PROJECTION_SCHEMA_VERSION = "matryca-graph-outcome-evaluation-projection.v1"
SUITE_SCHEMA_VERSION = "matryca-graph-outcome-evaluation-projection-suite.v1"
ProjectionScenario = Literal[
    "corrupt-derived-state",
    "stale-unverified-mutation",
    "strict-read-only-success",
    "unauthorized-tool-request",
]


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectionDimension(_ClosedModel):
    dimension: DimensionName
    status: DimensionStatus
    passed_check_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    failed_check_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)


class ProjectionMetrics(_ClosedModel):
    turns: int = Field(ge=0, le=1_000)
    tool_calls: int = Field(ge=0, le=10_000)
    rejected_tool_calls: int = Field(ge=0, le=10_000)
    retrieval_calls: int = Field(ge=0, le=10_000)
    mutation_calls: int = Field(ge=0, le=1_000)
    retries: int = Field(ge=0, le=100)
    no_progress_cycles: int = Field(ge=0, le=1_000)
    context_tokens: int = Field(ge=0, le=10_000_000)
    context_bytes: int = Field(ge=0, le=10**10)
    elapsed_milliseconds: int = Field(ge=0, le=86_400_000)
    peak_rss_bytes: int = Field(ge=0, le=10**13)
    cost_microunits: int = Field(ge=0, le=10**12)


class ProjectionArtifact(_ClosedModel):
    kind: OutcomeArtifactKind
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    record_count: int = Field(ge=0, le=10_000_000)


class GraphOutcomeProjectionPayload(_ClosedModel):
    schema_version: Literal["matryca-graph-outcome-evaluation-projection.v1"] = (
        "matryca-graph-outcome-evaluation-projection.v1"
    )
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_schema_version: Literal["graph-outcome-protocol.v1"]
    scenario: ProjectionScenario
    policy_mode: PolicyMode
    task_bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    report_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    terminal_status: TerminalStatus
    validation_status: Literal["passed", "rejected"]
    failure_codes: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    executed_tool_ids: tuple[ClosedIdentifier, ...] = Field(max_length=10_000)
    dimensions: tuple[ProjectionDimension, ...] = Field(min_length=5, max_length=5)
    metrics: ProjectionMetrics
    initial_canonical_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_canonical_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    initial_derived_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    final_derived_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    roots_distinct: Literal[True]
    roots_outside_repository: Literal[True]
    cleanup_verified: Literal[True]
    artifacts: tuple[ProjectionArtifact, ...] = Field(min_length=9, max_length=9)


class GraphOutcomeEvaluationProjection(GraphOutcomeProjectionPayload):
    projection_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class GraphOutcomeSuitePayload(_ClosedModel):
    schema_version: Literal["matryca-graph-outcome-evaluation-projection-suite.v1"] = (
        "matryca-graph-outcome-evaluation-projection-suite.v1"
    )
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    protocol_schema_version: Literal["graph-outcome-protocol.v1"]
    projections: tuple[GraphOutcomeEvaluationProjection, ...]


class GraphOutcomeEvaluationSuite(GraphOutcomeSuitePayload):
    suite_id: str = Field(pattern=r"^[0-9a-f]{64}$")
```

Define `ClosedIdentifier` as an `Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{0,95}$")]`. Define the projection with every approved top-level field from the specification. Define the suite with `schema_version`, `suite_id`, shared source/protocol values, and exactly four projections. Normalize identifier tuples, dimensions, artifacts, and projections in `model_validator(mode="after")`; reject duplicates before sorting. Require exactly the five canonical `DimensionName` values and all nine canonical `OutcomeArtifactKind` values. Reproduce the canonical dimension invariants (no check in both outcomes; passing has no failures; failing has at least one failure; not-applicable has no checks) and process-metric count relationships (`rejected_tool_calls`, `retrieval_calls`, and `mutation_calls` never exceed `tool_calls`).

Use one internal serializer for identity and final bytes:

```python
def _canonical_bytes(value: BaseModel, *, exclude: set[str] = frozenset()) -> bytes:
    payload = value.model_dump(mode="json", exclude=exclude)
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_projection_bytes(value: GraphOutcomeEvaluationProjection) -> bytes:
    return _canonical_bytes(value) + b"\n"


def canonical_suite_bytes(value: GraphOutcomeEvaluationSuite) -> bytes:
    return _canonical_bytes(value) + b"\n"
```

`build_projection(payload)` normalizes and validates the identity-free closed payload, computes `sha256(_canonical_bytes(payload)).hexdigest()`, and constructs the final projection from the normalized payload fields. `build_suite(payload)` sorts by scenario, validates exact scenario membership and shared provenance, computes the suite hash from the normalized identity-free suite payload, and returns the final suite.

- [ ] **Step 4: Run focused schema tests and confirm GREEN**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_schema.py
uv run ruff check tools/evaluation_projection/schema.py tests/tools/evaluation_projection/test_schema.py
uv run mypy tools/evaluation_projection/schema.py tests/tools/evaluation_projection/test_schema.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Record reviewed golden IDs and commit**

Replace the initially computed golden constants with literal reviewed SHA-256 values, rerun Step 4, then:

```bash
git add tools/__init__.py tools/evaluation_projection/__init__.py tools/evaluation_projection/schema.py tests/tools/evaluation_projection/__init__.py tests/tools/evaluation_projection/test_schema.py
git commit -S -m "feat(evaluation): add closed projection schema"
```

---

### Task 2: Recursive fail-closed privacy guard

**Files:**
- Create: `tools/evaluation_projection/privacy.py`
- Create: `tests/tools/evaluation_projection/test_privacy.py`
- Modify: `tools/evaluation_projection/schema.py`

**Interfaces:**
- Consumes: a validated projection/suite dump or an adversarial nested object in direct guard tests.
- Produces: `ProjectionPrivacyError(code: str)` and `assert_projection_private(value: object) -> None`; schema builders invoke the guard before calculating identities.

- [ ] **Step 1: Write adversarial failing tests**

Test direct and nested inputs without ever asserting the forbidden value in an exception message:

```python
@pytest.mark.parametrize(
    "payload",
    [
        {"content": "private note"},
        {"nested": {"prompt": "secret prompt"}},
        {"nested": [{"path": "/private/tmp/graph"}]},
        {"nested": {"value": "file:///Users/example/graph.md"}},
        {"nested": {"value": "person@example.com"}},
        {"nested": {"value": "Authorization: Bearer secret"}},
        {"nested": {"timestamp": "2026-08-26T10:00:00Z"}},
    ],
)
def test_guard_rejects_nested_forbidden_content_without_echo(payload: object) -> None:
    with pytest.raises(ProjectionPrivacyError) as caught:
        assert_projection_private(payload)
    assert str(caught.value) in {"privacy_key_forbidden", "privacy_value_forbidden"}
    assert "secret" not in str(caught.value)
    assert "/private/" not in str(caught.value)
```

Add positive tests for every approved scalar family: 40-hex source revision, 64-hex digests, closed scenario/tool/check identifiers, booleans, bounded integers including `elapsed_milliseconds`, schema versions, policy mode, terminal/dimension/validation status, and artifact kind.

- [ ] **Step 2: Run privacy tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_privacy.py
```

Expected: collection fails because `privacy.py` does not exist.

- [ ] **Step 3: Implement path-aware recursive guarding**

Use an exact allowed-key set matching the schema and exact forbidden key families:

```python
_ALLOWED_KEYS = frozenset(
    {
        "artifacts", "cleanup_verified", "context_bytes", "context_tokens",
        "cost_microunits", "digest", "dimension", "dimensions",
        "elapsed_milliseconds", "executed_tool_ids", "failed_check_ids",
        "failure_codes", "final_canonical_fingerprint",
        "final_derived_fingerprint", "initial_canonical_fingerprint",
        "initial_derived_fingerprint", "kind", "mutation_calls",
        "no_progress_cycles", "passed_check_ids", "peak_rss_bytes",
        "policy_mode", "projection_id", "projections",
        "protocol_schema_version", "receipt_id", "record_count",
        "rejected_tool_calls", "report_id", "retries", "retrieval_calls",
        "roots_distinct", "roots_outside_repository", "scenario",
        "schema_version", "source_revision", "status", "suite_id",
        "task_bundle_digest", "terminal_status", "tool_calls", "turns",
        "validation_status",
    }
)
_FORBIDDEN_KEYS = frozenset(
    {
        "answer", "annotation", "api_key", "authorization", "content",
        "cookie", "database_id", "endpoint", "environment", "hostname",
        "log", "model_output", "page_name", "password", "path", "prompt",
        "query", "raw_output", "run_id", "secret", "stack_trace",
        "timestamp", "token", "url", "username",
    }
)
_ABSOLUTE_POSIX = re.compile(r"^/")
_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_CREDENTIAL = re.compile(
    r"(?i)(authorization|bearer|api[_-]?key|password|secret|token)\s*[:= ]"
)
_DIGEST_KEYS = frozenset(
    {
        "digest", "final_canonical_fingerprint", "final_derived_fingerprint",
        "initial_canonical_fingerprint", "initial_derived_fingerprint",
        "projection_id", "receipt_id", "report_id", "suite_id",
        "task_bundle_digest",
    }
)
```

Walk mappings and sequences recursively while retaining the current field key.
Normalize keys to lowercase snake case before exact allowed/forbidden
comparison. Permit a 64-character digest-shaped scalar only under
`_DIGEST_KEYS` and a 40-character revision only under `source_revision`; reject
those shapes under every other key. Reject unexpected scalar types, non-finite
floats, path objects, bytes, and any string matching a forbidden
high-confidence pattern. Errors contain only `privacy_key_forbidden`,
`privacy_value_forbidden`, or `privacy_type_forbidden`.

The guard is defense in depth: closed models remain the primary allowlist. Call it from `build_projection()` and `build_suite()` on `model_dump(mode="json")` before each identity calculation.

- [ ] **Step 4: Prove positive and negative privacy behavior**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_privacy.py tests/tools/evaluation_projection/test_schema.py
uv run ruff check tools/evaluation_projection/privacy.py tools/evaluation_projection/schema.py tests/tools/evaluation_projection/test_privacy.py
uv run mypy tools/evaluation_projection/privacy.py tools/evaluation_projection/schema.py tests/tools/evaluation_projection/test_privacy.py
```

Expected: all commands exit `0`; golden schema bytes remain unchanged unless the guard exposed a previously invalid field.

- [ ] **Step 5: Commit the privacy boundary**

```bash
git add tools/evaluation_projection/privacy.py tools/evaluation_projection/schema.py tests/tools/evaluation_projection/test_privacy.py
git commit -S -m "feat(evaluation): enforce projection privacy boundary"
```

---

### Task 3: Canonical `EpisodeRun` projector and validation replay

**Files:**
- Create: `tools/evaluation_projection/projector.py`
- Create: `tests/tools/evaluation_projection/test_projector.py`
- Modify: `tools/evaluation_projection/__init__.py`

**Interfaces:**
- Consumes: `project_episode(run: EpisodeRun, *, source_revision: str) -> GraphOutcomeEvaluationProjection` and `project_suite(episodes: tuple[EpisodeRun, ...], *, source_revision: str) -> GraphOutcomeEvaluationSuite`.
- Produces: closed projections only after replaying canonical validation and receipt identity checks; raises `ProjectionEvidenceError` with stable content-free codes.

- [ ] **Step 1: Write failing evidence-mapping tests**

Cover all default scenarios and canonical preservation:

```python
def test_default_episodes_project_without_changing_canonical_evidence() -> None:
    episodes = run_default_scenarios().episodes
    before = tuple(
        (
            canonical_task_bundle_bytes(run.task),
            canonical_episode_report_bytes(run.report),
            canonical_outcome_receipt_bytes(run.receipt),
        )
        for run in episodes
    )

    suite = project_suite(episodes, source_revision=_REVISION)

    after = tuple(
        (
            canonical_task_bundle_bytes(run.task),
            canonical_episode_report_bytes(run.report),
            canonical_outcome_receipt_bytes(run.receipt),
        )
        for run in episodes
    )
    assert before == after
    assert tuple(item.scenario for item in suite.projections) == tuple(sorted(_SCENARIOS))
```

Assert the unauthorized-tool scenario projects `validation_status="rejected"` and exactly `("tool_not_allowed_by_task",)` while the other three project `passed`. Assert the projected metrics, dimensions, artifacts, fingerprints, tool IDs, policy mode, report ID, receipt ID, and cleanup/isolation booleans equal the typed source fields.

Add a parameterized closed-input test that passes a generic mapping, a
`BenchmarkRunReport`, and an `EpisodeRun` subclass or subclass-like adversarial
object through a runtime cast. Every value must reject with the stable code
`episode_type_unsupported`; no mapping conversion or attribute duck typing is
allowed.

Use `dataclasses.replace()` and closed-model copies to create mismatches for validation token/error/failure codes, report ID, task digest, receipt bytes, scenario, root isolation, cleanup, and source revision. Each must raise one stable code such as `validation_replay_mismatch`, `receipt_report_mismatch`, `receipt_task_mismatch`, `receipt_bytes_mismatch`, `scenario_mismatch`, `episode_isolation_unproven`, or `source_revision_invalid`.

- [ ] **Step 2: Run projector tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_projector.py
```

Expected: collection fails because `projector.py` does not exist.

- [ ] **Step 3: Implement exact validation replay**

Reject unsupported input types before reading any fields, then replay success
and expected rejection explicitly:

```python
if type(run) is not EpisodeRun:
    raise ProjectionEvidenceError("episode_type_unsupported")


def _validation_status(run: EpisodeRun) -> Literal["passed", "rejected"]:
    try:
        replayed_token = validate_episode_against_task(run.report, run.task)
    except EvidenceContractError as exc:
        code = str(exc)
        if (
            run.validation_token is not None
            or run.validation_error != code
            or run.failure_codes != (code,)
        ):
            raise ProjectionEvidenceError("validation_replay_mismatch") from None
        return "rejected"
    if (
        run.validation_token != replayed_token
        or run.validation_error is not None
        or run.failure_codes
    ):
        raise ProjectionEvidenceError("validation_replay_mismatch")
    return "passed"
```

Then require canonical receipt bytes, receipt/report/task IDs, root isolation, and cleanup. Map every output field explicitly; do not pass unrestricted `model_dump()` values into a generic mapping. Use closed schema constructors for dimensions, metrics, and artifacts.

- [ ] **Step 4: Implement suite projection without scenario reinterpretation**

```python
def project_suite(
    episodes: tuple[EpisodeRun, ...], *, source_revision: str
) -> GraphOutcomeEvaluationSuite:
    projections = tuple(
        project_episode(run, source_revision=source_revision) for run in episodes
    )
    return build_suite(
        GraphOutcomeSuitePayload(
            source_revision=source_revision,
            protocol_schema_version=GRAPH_OUTCOME_PROTOCOL_SCHEMA_VERSION,
            projections=projections,
        )
    )
```

Do not add aggregate pass/fail, reset-isolation interpretation, timing, or scenario aliases.

- [ ] **Step 5: Run projector, harness, and protocol regressions**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_projector.py tests/test_graph_outcome_harness.py tests/test_graph_outcome_protocol.py tests/test_run_graph_outcome_harness.py
uv run ruff check tools/evaluation_projection/projector.py tests/tools/evaluation_projection/test_projector.py
uv run mypy tools/evaluation_projection/projector.py tests/tools/evaluation_projection/test_projector.py
```

Expected: all commands exit `0`; existing report-runner golden behavior remains unchanged.

- [ ] **Step 6: Commit the canonical adapter**

```bash
git add tools/evaluation_projection/projector.py tools/evaluation_projection/__init__.py tests/tools/evaluation_projection/test_projector.py
git commit -S -m "feat(evaluation): project canonical outcome evidence"
```

---

### Task 4: Exact clean Git provenance binding

**Files:**
- Create: `tools/evaluation_projection/provenance.py`
- Create: `tests/tools/evaluation_projection/test_provenance.py`

**Interfaces:**
- Consumes: a repository root `Path` and optional asserted revision.
- Produces: frozen `SourceBinding(repository_root: Path, revision: str, branch: str)` from `resolve_source_binding(repository_root: Path, asserted_revision: str | None = None) -> SourceBinding`; raises `SourceBindingError` with a stable code only.

- [ ] **Step 1: Write real disposable-repository tests**

Build each fixture repository under `tmp_path` with fixed Git commands and commit signing disabled only inside the disposable test repository:

```python
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test Maintainer")
    _git(repo, "config", "user.email", "maintainer@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "test: initialize repository")
    return repo
```

Cover clean named branch, modified tracked file, untracked file, detached HEAD, invalid assertion, mismatched assertion, non-repository, empty/failed Git output, and subprocess timeout. Assert errors contain only one of: `source_repository_unavailable`, `source_revision_invalid`, `source_tree_dirty`, `source_head_detached`, or `source_revision_mismatch`.

- [ ] **Step 2: Run provenance tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_provenance.py
```

Expected: collection fails because `provenance.py` does not exist.

- [ ] **Step 3: Implement fixed-argv Git probes**

Use only fixed executable/argument lists and a five-second timeout:

```python
_GIT_TIMEOUT_SECONDS = 5
_REVISION = re.compile(r"^[0-9a-f]{40}$")


def _run_git(repository_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        raise SourceBindingError("source_repository_unavailable") from None
    return completed.stdout.strip()
```

Resolve in this order: `rev-parse --show-toplevel`, `rev-parse --verify
HEAD^{commit}`, `symbolic-ref --quiet --short HEAD`, and `status
--porcelain=v1 --untracked-files=all`. Probe `symbolic-ref` separately with
`check=False`: return code `1` maps to `source_head_detached`; any other
non-zero result or execution failure maps to `source_repository_unavailable`.
Require the resolved top level to equal the supplied root after
`resolve(strict=True)`. Reject dirty state before comparing the optional
assertion. Never include command output, branch value, revision value, or path
in an error.

- [ ] **Step 4: Run focused provenance quality gates**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_provenance.py
uv run ruff check tools/evaluation_projection/provenance.py tests/tools/evaluation_projection/test_provenance.py
uv run mypy tools/evaluation_projection/provenance.py tests/tools/evaluation_projection/test_provenance.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit the provenance gate**

```bash
git add tools/evaluation_projection/provenance.py tests/tools/evaluation_projection/test_provenance.py
git commit -S -m "feat(evaluation): bind projections to clean source"
```

---

### Task 5: Atomic, non-destructive output installation

**Files:**
- Create: `tools/evaluation_projection/atomic_output.py`
- Create: `tests/tools/evaluation_projection/test_atomic_output.py`

**Interfaces:**
- Consumes: `write_projection_bytes(destination: Path, payload: bytes, *, overwrite: bool = False) -> None`.
- Produces: a complete regular file or `AtomicOutputError(code: str, installed: bool = False)`; never returns partial success.

- [ ] **Step 1: Write failure-injection tests**

Cover new output, default refusal, explicit overwrite, destination symlink, parent symlink, missing parent, non-directory parent, write failure, no-overwrite race, replacement failure, temporary cleanup, supported parent-directory sync failure, and unsupported parent-directory sync.

The post-replacement sync test must encode the real filesystem boundary:

```python
def test_directory_sync_failure_keeps_complete_new_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "projection.json"
    output.write_bytes(b"old\n")
    real_fsync = os.fsync
    calls = 0

    def fail_second_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory sync failed")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fail_second_fsync)
    with pytest.raises(AtomicOutputError) as caught:
        write_projection_bytes(output, b"new\n", overwrite=True)
    assert caught.value.code == "output_directory_sync_failed"
    assert caught.value.installed
    assert output.read_bytes() == b"new\n"
    assert not tuple(tmp_path.glob(".projection.json.*.tmp"))
```

For all failures before installation, assert the prior destination bytes are preserved and owned temporary files are absent.
Add a separate test where directory `fsync` raises `EINVAL` or `ENOTSUP` after
installation; treat those documented unsupported-platform results as
best-effort success and preserve the complete new file. A supported I/O failure
such as `EIO` must retain the `output_directory_sync_failed` result above with
`installed=True`.

- [ ] **Step 2: Run atomic-output tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_atomic_output.py
```

Expected: collection fails because `atomic_output.py` does not exist.

- [ ] **Step 3: Implement same-directory private temporary output**

Use `tempfile.mkstemp()` in the existing parent, write bytes, flush, and `fsync`:

```python
fd, temporary_name = tempfile.mkstemp(
    prefix=f".{destination.name}.",
    suffix=".tmp",
    dir=str(destination.parent),
)
temporary = Path(temporary_name)
installed = False
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    if overwrite:
        _require_regular_or_absent_destination(destination)
        os.replace(temporary, destination)
    else:
        os.link(temporary, destination)
        temporary.unlink()
    installed = True
    _fsync_directory(destination.parent)
finally:
    temporary.unlink(missing_ok=True)
```

Before creating the temporary file, require an existing directory parent whose strict resolved path equals its normalized absolute path; this rejects a symlink parent or symlinked ancestor. Reject any destination that exists or is a symlink unless overwrite is explicit. With overwrite, require an existing destination to be a non-symlink regular file. Translate `FileExistsError` races to `output_exists` and pre-install I/O failures to `output_install_failed`. `_fsync_directory()` may suppress only `EINVAL`, `ENOTSUP`, or the platform-equivalent `EOPNOTSUPP` when the directory operation is unsupported; every other directory-sync error becomes `output_directory_sync_failed` with `installed=True`. Do not create parents or echo paths.

- [ ] **Step 4: Run atomic-output quality gates**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_atomic_output.py
uv run ruff check tools/evaluation_projection/atomic_output.py tests/tools/evaluation_projection/test_atomic_output.py
uv run mypy tools/evaluation_projection/atomic_output.py tests/tools/evaluation_projection/test_atomic_output.py
```

Expected: all commands exit `0`.

- [ ] **Step 5: Commit the output boundary**

```bash
git add tools/evaluation_projection/atomic_output.py tests/tools/evaluation_projection/test_atomic_output.py
git commit -S -m "feat(evaluation): install projection output atomically"
```

---

### Task 6: Maintainer CLI, suite orchestration, and package boundary

**Files:**
- Create: `tools/evaluation_projection/cli.py`
- Create: `scripts/project_graph_outcome_evidence.py`
- Create: `tests/tools/evaluation_projection/test_cli.py`
- Create: `tests/tools/evaluation_projection/test_import_boundary.py`
- Modify: `tools/evaluation_projection/__init__.py`

**Interfaces:**
- Consumes: `main(argv: Sequence[str] | None = None, *, repository_root: Path | None = None) -> int`.
- Produces: one canonical suite on stdout or one explicitly installed file; stable exits `0`, `2`, `3`, `4`, `5`, and `6`.

- [ ] **Step 1: Write CLI failure-order and output tests**

Use dependency injection or monkeypatching to prove provenance runs before the harness:

```python
def test_dirty_source_rejects_before_harness(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "resolve_source_binding", _raise_dirty)
    monkeypatch.setattr(cli, "run_default_scenarios", _fail_if_called)
    assert cli.main([], repository_root=Path.cwd()) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "evaluation_projection: source_tree_dirty\n"
```

Cover stdout-only success, file-only success, explicit source assertion, mismatch, expected canonical rejection inside a successful suite, privacy/evidence rejection, output exists, output failure, post-install directory-sync failure, and argparse usage exit `2`. Assert no stderr message contains input values, paths, exception text, Git output, or synthetic content.

- [ ] **Step 2: Write import and distribution-boundary tests**

Parse every `src/**/*.py` with `ast` and reject imports whose root module is `tools`. Parse `pyproject.toml` with `tomllib` and assert package discovery includes only `src*` and `frontend`. Block MLflow imports during a fresh adapter import:

```python
def test_projection_imports_without_mlflow(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "mlflow" or name.startswith("mlflow."):
            raise AssertionError("mlflow import forbidden in PR A")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.reload(importlib.import_module("tools.evaluation_projection"))
```

Also parse `tools/evaluation_projection/**/*.py` and reject network/client imports (`httpx`, `requests`, `socket`, `urllib`) and environment/config reads (`os.environ`, `os.getenv`, `dotenv`). In the CLI success test, monkeypatch `socket.socket` to raise if constructed; the fixed Git subprocess and projection must still complete. Invoke the wrapper from an unrelated temporary working directory to prove its repository bootstrap is independent of the caller's current directory. Test invalid CLI syntax through that wrapper subprocess and assert process exit `2` without requiring `main()` to catch argparse's `SystemExit`.

- [ ] **Step 3: Run CLI/boundary tests and confirm RED**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection/test_cli.py tests/tools/evaluation_projection/test_import_boundary.py
```

Expected: collection fails because `cli.py` and the wrapper do not exist.

- [ ] **Step 4: Implement the thin CLI**

Create a parser with only `--source-revision`, `--output`, and `--overwrite`.
When `repository_root` is not injected, resolve it deterministically as
`Path(__file__).resolve().parents[2]` from `cli.py`; do not infer it from the
current working directory. Perform operations in this exact order:

```python
binding = resolve_source_binding(repository_root, args.source_revision)
default_run = run_default_scenarios()
suite = project_suite(default_run.episodes, source_revision=binding.revision)
payload = canonical_suite_bytes(suite)
if args.output is None:
    sys.stdout.buffer.write(payload)
else:
    write_projection_bytes(args.output, payload, overwrite=args.overwrite)
```

Catch source errors as exit `3`, evidence/privacy/schema errors as `4`, `output_exists` as `5`, and all other output errors as `6`. Print exactly `evaluation_projection: <stable_code>\n` to stderr. Do not catch `KeyboardInterrupt` or `SystemExit` from argparse.

The wrapper contains only repository import bootstrap plus delegation:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.evaluation_projection.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run CLI, boundary, and full focused projection tests**

Run:

```bash
uv run pytest -q --no-cov tests/tools/evaluation_projection tests/test_graph_outcome_harness.py tests/test_graph_outcome_protocol.py tests/test_run_graph_outcome_harness.py
uv run ruff check tools/evaluation_projection scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection
uv run mypy tools/evaluation_projection scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection
```

Expected: all commands exit `0`.

- [ ] **Step 6: Perform one disposable CLI smoke**

From a clean named-branch worktree, run stdout mode twice and compare hashes; then run file mode into a newly created external temporary directory. Verify byte equality between stdout and file output, then remove only the disposable directory. Record the exact source commit and output SHA-256 in the implementation handoff, not in public documentation.

- [ ] **Step 7: Commit the maintainer surface**

```bash
git add tools/evaluation_projection/cli.py tools/evaluation_projection/__init__.py scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection/test_cli.py tests/tools/evaluation_projection/test_import_boundary.py
git commit -S -m "feat(evaluation): add deterministic projection command"
```

---

### Task 7: Maintainer runbook, changelog, inventory, and exact-head qualification

**Files:**
- Create: `docs/quality/GRAPH_OUTCOME_EVALUATION_PROJECTION_RUNBOOK.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Modify: `docs/superpowers/plans/2026-08-26-mlflow-evaluation-projection.md` only to mark completed checkboxes and record terminal commands without local paths or transient IDs

**Interfaces:**
- Consumes: the final PR A command and exact schema/exit contracts.
- Produces: current operator guidance, discoverable documentation, one Unreleased capability entry, and terminal exact-head evidence.

- [ ] **Step 1: Write the maintainer runbook**

Use standard Matryca frontmatter:

```yaml
---
type: Runbook
title: Graph-outcome evaluation projection runbook
description: Maintainer procedure for generating, verifying, retaining, reconstructing, and deleting deterministic content-free graph-outcome projection suites.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-26
stale_after: 2026-11-24
---
```

Document: authority classes; prerequisites; stdout and explicit-file commands; source assertion; overwrite behavior; stable exit table; privacy boundary; reconstruction and safe deletion; failure handling; limitations; exact statement that PR A contains no MLflow integration, service, import, or dependency; PR B entry gate. Do not include local absolute paths, hostnames, user names, raw output, generated projection IDs, or a README claim.

- [ ] **Step 2: Add the Unreleased changelog entry**

Under `## [Unreleased]` → `### Added`, add exactly one concise bullet:

```markdown
- **Deterministic graph-outcome evaluation projection** — add a maintainer-only,
  source-bound, privacy-checked JSON projection of the four synthetic outcome
  scenarios with canonical identities and atomic explicit output; it adds no
  tracking dependency, network activity, real-vault execution, or product path.
```

- [ ] **Step 3: Synchronize and curate the documentation inventory**

Run:

```bash
uv run python scripts/docs_knowledge_check.py inventory-sync
uv run python scripts/docs_knowledge_check.py inventory-md
```

Review the new runbook and plan entries. Set type, title, description, classification, full audience, owner `quality`, action `keep`, and accurate evidence-gated notes. Regenerate `inventory.md` after manual curation.

- [ ] **Step 4: Run documentation and focused source gates**

Run:

```bash
make docs-check
make docs-audit
make agents-check
uv run ruff format --check tools/evaluation_projection scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection
uv run ruff check tools/evaluation_projection scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection
uv run mypy tools/evaluation_projection scripts/project_graph_outcome_evidence.py tests/tools/evaluation_projection
uv run pytest -q --no-cov tests/tools/evaluation_projection tests/test_graph_outcome_harness.py tests/test_graph_outcome_protocol.py tests/test_run_graph_outcome_harness.py
```

Expected: all commands exit `0` with zero documentation findings and zero test failures.

- [ ] **Step 5: Commit documentation and inventory**

```bash
git add CHANGELOG.md docs/quality/GRAPH_OUTCOME_EVALUATION_PROJECTION_RUNBOOK.md docs/knowledge/inventory.json docs/knowledge/inventory.md docs/superpowers/plans/2026-08-26-mlflow-evaluation-projection.md
git commit -S -m "docs(evaluation): document projection operations"
```

- [ ] **Step 6: Build and inspect one wheel in a disposable directory**

Build from the exact clean commit created in Step 5 into a new external disposable directory. Inspect the wheel ZIP member list and prove that no member begins with `tools/` and no package metadata declares MLflow. Preserve only the bounded terminal result in the handoff; remove the disposable build directory after inspection.

- [ ] **Step 7: Run exact-head repository qualification**

On the clean signed commit from Step 5:

```bash
make ci
make docs-audit
git diff --check HEAD^..HEAD
git status --short --branch
```

Then verify every commit signature, compare the complete branch against its exact base, run the repository's local change-impact check, and confirm:

- only the approved PR A files changed;
- no default/dev dependency or lock entry mentions MLflow;
- no `src` import points to `tools`;
- no README or product-runtime claim was added;
- every acceptance criterion in the specification has terminal evidence;
- the worktree is clean and the branch remains unpushed until separately authorized.

If any gate fails, preserve the exact failure, fix only within its owning task, rerun the narrowest failing test first, and rerun this exact-head qualification. Do not create or publish a PR from partial, skipped, dirty, or mismatched evidence.
