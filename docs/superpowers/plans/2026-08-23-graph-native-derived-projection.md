---
type: Roadmap
title: Graph-native derived projection implementation plan
description: M0-M6 execution plan for a backend-neutral projection contract, SQLite compatibility, deterministic PQK, offline Ladybug qualification, and an evidence-bound terminal decision.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: shadow-runtime
last_verified: 2026-08-23
stale_after: 2027-02-19
---

# Graph-Native Derived Projection Implementation Plan

> Execute this plan task by task with isolated implementation and review checkpoints. Update each checkbox only after its exact evidence gate is terminal.

**Goal:** Qualify an optional graph-native derived projection without changing Markdown authority, SQLite's stable default, or any v2.0 runtime route.

**Architecture:** Normalize parser output into immutable graph-domain records, expose three segregated projection ports, and preserve current SQLite behavior behind compatibility facades. A deterministic Projection Qualification Kit (PQK) first establishes SQLite evidence and then evaluates an offline, single-owner LadybugDB adapter; no runtime selector or online owner service is part of this plan.

**Tech Stack:** Python 3.12+, frozen dataclasses, `typing.Protocol`, `sqlite3`/FTS5, `logseq-matryca-parser`, optional `ladybug==0.19.1`, Pydantic v2 receipts, pytest, Ruff, mypy, uv.

**Spec:** [`docs/superpowers/specs/2026-08-22-graph-native-derived-projection-design.md`](../specs/2026-08-22-graph-native-derived-projection-design.md)

## Global Constraints

- Logseq Markdown is authoritative for graph content; approval/evidence authorities remain separate and explicit.
- SQLite remains the stable, default, supported Shadow backend for every task in this plan.
- LadybugDB is optional, experimental, offline-only, single-process, and single-owner.
- The approved dependency candidate is exactly `ladybug==0.19.1`; dependency admission must revalidate package identity, license, provenance, wheel support, and digest before lockfile mutation.
- No product runtime selector, environment variable, daemon route, MCP route, installed console command, `src/cli` route, UI route, or online owner service is added. Repository-only qualification scripts are test infrastructure, are not packaged as product commands, and cannot select the production backend.
- No normal execution may issue `INSTALL <extension>` or perform a network download.
- The `llm` extension is prohibited; vector probes use deterministic repository-owned vectors.
- `recall-bundle.v1` and `shadow-fts5/schema-1` remain SQLite-specific and unchanged.
- PQK and the neutral TCK owned by #519 remain distinct in names, schemas, fixtures, evidence, and claims.
- Structural conformance, retrieval-contract conformance, retrieval quality, graph-native value, performance, and operational safety are separate evidence classes.
- Graph-native traversal and vector search remain separately approved capability slices; Task 9 cannot execute either probe merely because Tasks 1-8 passed.
- Negative results, unsupported capabilities, deferral, and `rejected_with_evidence` are valid terminal outcomes.
- Public files use English, vendor-neutral tooling language, and maintainer-only authorship.
- Every symbol edit requires a current upstream impact review; every commit requires the repository's diff-level change detector (`detect_changes()`), review of every affected flow, and the narrowest relevant deterministic tests.
- Commit, push, PR creation, readiness, merge, dependency publication, release, and announcement are distinct authorization gates.

---

## Verified Planning Anchors

- Approved design commit: `7a83e97e6e39a219dc015134fe77674a4a7bde5a`.
- Design base: `main@505cfb0da805fce2dc2a7497b911846d857bbd39`.
- Stable product baseline: `v2.0.0@987446b8337f7abd308a9efe4abb834ce1acdc1b`.
- Local code-audit index: exact design commit, 10,235 nodes, 30,140 edges, 479 clusters, 300 flows.
- Current programme authorities verified on 2026-08-23: #178, #446, #452, #483, #519, and #520 are open; #448 and #449 are closed evidence foundations.
- The read-only Matryca Knowledge projection was unavailable during planning because its status call could not resolve `sources.toml`; Task 1 records this as a coordination gap and does not reinterpret it as source-repository failure.
- Official package evidence on 2026-08-23: PyPI publishes `ladybug==0.19.1` for CPython 3.12 and 3.13 on macOS, Linux, and Windows, requires Python `>=3.10,<3.15`, uses trusted publishing, and identifies an MIT-licensed upstream. Revalidate this exact evidence during Task 8.

## Authority Matrix

| Data class | Authority | Derived copies | Failure rule |
| --- | --- | --- | --- |
| Logseq page/block content | Markdown under the canonical graph root | parser objects, SQLite, LadybugDB | Derived state never overwrites Markdown. |
| Evidence artifacts | governed evidence archive and exact receipt binding | indexes, summaries, dashboards | Missing binding means unproven. |
| Approval/rejection state | owning lifecycle contract | issue/PR summaries | A projection cannot promote a candidate. |
| Projection schema/capabilities | versioned adapter contract and decision record | runtime diagnostics | Unknown capability fails closed. |
| Search score | backend-local query result | PQK observations | Never canonical or cross-backend fingerprint input. |
| Embedding vector | deterministic fixture or separately governed embedding artifact | vector index | Missing model/artifact provenance means unsupported. |
| Graph projection | selected derived backend | PQK snapshot | Rebuildable and disposable. |
| Health/generation | projection-local operational state | diagnostics and receipts | Stale, corrupt, or incompatible state is not served. |
| Neutral memory conformance | #519 TCK authority | product reports | Database choice remains non-normative. |

## Delivery Topology

Each task is one reviewable vertical slice. Tasks 1-2 establish M0 truth and governance; Tasks 3-4 freeze M1 behavior and contract; Tasks 5-6 implement M2; Task 7 implements M3; Task 8 implements M4; Tasks 9-10 implement M5; Task 11 publishes M6. A task may be a separate stacked branch/PR, but its child is retargeted and requalified only after its parent is integrated.

The primary orchestrator retains architecture, dependency admission, concurrency/safety decisions, evidence interpretation, integration, remote actions, and terminal promotion. Lower-cost workers may own bounded fixture work, isolated mechanical implementation, deterministic test execution, documentation generation from settled facts, and independent review. One writer owns each file group; overlapping writes are serialized.

The durable execution ledger is `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`. At every task boundary it records branch, base, exact HEAD, files, terminal checks, unproven gates, retained artifact paths, blockers, and next task.

### Task 1: M0 current truth, authority, roadmap, and durable ledger

**Files:**
- Modify: `docs/knowledge/architecture/system-overview.md:154,199,208`
- Modify: `docs/knowledge/architecture/shadow-db.md:29-162`
- Modify: `docs/knowledge/architecture/index.md:9`
- Create: `docs/knowledge/architecture/projection-authority.md`
- Create: `docs/roadmaps/ROADMAP_GRAPH_NATIVE_PROJECTION.md`
- Create: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Test: `tests/test_docs_knowledge_check.py`

**Interfaces:**
- Consumes: approved design at `7a83e97` and the authority matrix above.
- Produces: current v2.0 documentation truth, one maintained authority concept, one execution roadmap, and one interruption-safe ledger.

- [ ] **Step 1: Write the documentation regression assertion**

Add a parameterized check to `tests/test_docs_knowledge_check.py` that reads the maintained architecture files and asserts all of these phrases are absent:

```python
@pytest.mark.parametrize(
    "relative_path,stale_phrase",
    [
        ("docs/knowledge/architecture/index.md", "Opt-in SQLite read cache"),
        ("docs/knowledge/architecture/system-overview.md", "No auxiliary database for the default read path"),
        ("docs/knowledge/architecture/system-overview.md", "Shadow DB read cache (opt-in)"),
    ],
)
def test_v2_shadow_current_truth_has_no_opt_in_drift(
    relative_path: str,
    stale_phrase: str,
) -> None:
    assert stale_phrase not in (ROOT / relative_path).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `uv run pytest tests/test_docs_knowledge_check.py::test_v2_shadow_current_truth_has_no_opt_in_drift -q`

Expected: FAIL on the three current stale phrases.

- [ ] **Step 3: Correct the maintained v2.0 truth**

Replace the stale overview language with this invariant:

```markdown
**Invariant:** one content system of record — `LOGSEQ_GRAPH_PATH`. The default read
path may use the external, disposable SQLite Shadow projection; Markdown remains
authoritative, and unhealthy or disabled projection state falls back to Markdown or
resident BM25 without creating a second mutation authority.
```

Update the architecture index entry to:

```markdown
- [Shadow DB](shadow-db.md) — Default-on external SQLite derived read cache,
  synchronization, health, routing, Strict Read Only compatibility, and fallback.
```

- [ ] **Step 4: Create the authority concept and roadmap**

`projection-authority.md` must reproduce the authority matrix in this plan and state that projection records are transport objects, not new authorities. `ROADMAP_GRAPH_NATIVE_PROJECTION.md` must list M0-M6, their dependencies, exact exit evidence, the PQK/TCK separation, and the terminal outcomes from the design.

- [ ] **Step 5: Create the execution ledger**

Initialize the ledger with:

```markdown
| Field | Value |
| --- | --- |
| Status | M0 planning checkpoint |
| Approved design | `7a83e97e6e39a219dc015134fe77674a4a7bde5a` |
| Stable baseline | `v2.0.0@987446b8337f7abd308a9efe4abb834ce1acdc1b` |
| Current task | M0 documentation truth |
| Proven gates | Design approved; documentation plan validated |
| Unproven gates | M0 implementation and every runtime/PQK gate |
| Knowledge projection | Degraded: `sources.toml` unresolved; source repositories remain authority |
| Next task | M1 SQLite characterization after M0 integration |
```

- [ ] **Step 6: Regenerate and verify documentation metadata**

Run:

```bash
make docs-inventory-sync
make docs-inventory-md
make docs-check
make agents-check
git diff --check
```

Expected: all commands exit 0; inventory contains the three new documents with curated type, owner, audience, classification, and action.

- [ ] **Step 7: Run diff-level review and commit**

Run the local diff-level code audit for all changes, confirm no runtime symbol is affected, then commit:

```bash
git add docs/knowledge/architecture/system-overview.md \
  docs/knowledge/architecture/shadow-db.md \
  docs/knowledge/architecture/index.md \
  docs/knowledge/architecture/projection-authority.md \
  docs/roadmaps/ROADMAP_GRAPH_NATIVE_PROJECTION.md \
  docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md \
  docs/knowledge/inventory.json docs/knowledge/inventory.md \
  tests/test_docs_knowledge_check.py
git commit -m "docs(architecture): reconcile projection authority"
```

### Task 2: M0 public product epic and incremental issue control plane

**Files:**
- Create: `docs/quality/issue-bodies/graph-native-projection-epic.md`
- Create: `docs/quality/issue-bodies/graph-native-projection-m1-characterization.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: merged Task 1 documentation authority and explicit GitHub mutation authorization.
- Produces: one product sub-epic under #178 and only the next actionable M1 child issue; remaining children are created after their dependency gate passes.

- [ ] **Step 1: Write the epic body**

Use this exact structure in `graph-native-projection-epic.md`:

```markdown
## Problem Description
Matryca Plumber needs evidence to decide whether a graph-native derived projection
adds enough value to justify a second backend, without changing canonical Markdown
authority or SQLite's stable default.

## Proposed Architectural Solution
Qualify whether an optional graph-native derived projection adds enough measured
value to Matryca Plumber to justify its complexity, without changing Markdown
authority or SQLite's stable default.

### Governing design
- Approved specification: `docs/superpowers/specs/2026-08-22-graph-native-derived-projection-design.md`
- Execution plan: `docs/superpowers/plans/2026-08-23-graph-native-derived-projection.md`

### Gates
M0 current truth → M1 SQLite characterization → M2 contracts and SQLite adapter →
M3 PQK → M4 offline LadybugDB → M5 comparative/operational evidence → M6 terminal decision.

### Non-goals
- No stable backend replacement.
- No runtime selector or online database owner.
- No database requirement in the #519 neutral contract.
- No claim beyond exact public evidence.

### Terminal outcomes
`preferred_candidate`, `supported_optional_candidate`, `experimental_continue`,
`deferred_upstream_or_packaging`, or `rejected_with_evidence`.

## Estimated Impact
Documentation, characterization, internal projection contracts, optional offline
qualification infrastructure, retained evidence, and a terminal decision. Stable
v2.0 runtime behavior remains unchanged.

## Files Involved
See the governing specification and execution plan; each child issue owns one
bounded file set.

---
**Epic link:** #178
_Closes only after M6 publishes one reviewed terminal outcome with exact evidence._
```

- [ ] **Step 2: Write the M1 child body**

The child issue must use the same mandatory headings—`Problem Description`, `Proposed Architectural Solution`, `Estimated Impact`, and `Files Involved`—plus an epic footer. It must require: synthetic fixture digest, full/incremental parity, health/generation accounting, delete/rename/replay, subtree ordering, lexical ordering, quarantine, interruption preservation, and a reviewed M1 contract decision before M2 starts.

- [ ] **Step 3: Validate documents before remote mutation**

Run `make docs-inventory-sync`, `make docs-inventory-md`, `make docs-check`, `make agents-check`, and `git diff --check`.

- [ ] **Step 4: Create GitHub artifacts only with fresh authorization**

Search open and closed issues by exact title before mutation. Create or reuse the lowercase `experiment` label, then create the epic titled `[Experiment] Qualify a graph-native derived projection backend` and the child titled `[Experiment] Freeze the SQLite projection baseline`. Assign both the `experiment` label and milestone `v2.1.0 — Memory & Logseq DB Safe-Sync`; link #178/#446/#448/#483/#519/#520 from the epic. Do not create M2-M6 children yet.

- [ ] **Step 5: Verify and record exact issue URLs**

Read both issues back through the GitHub API, verify titles, state, milestone, body links, and parent/child references, record URLs in the ledger, and commit the two issue-body documents with message `docs(quality): stage graph-native projection governance`.

### Task 3: M1 freeze the SQLite characterization baseline

**Files:**
- Create: `tests/projection/__init__.py`
- Create: `tests/projection/snapshot.py`
- Create: `tests/projection/test_sqlite_characterization.py`
- Create: `tests/fixtures/projection_pqk/v1/manifest.json`
- Create: `tests/fixtures/projection_pqk/v1/pages/alpha.md`
- Create: `tests/fixtures/projection_pqk/v1/pages/beta.md`
- Create: `tests/fixtures/projection_pqk/v1/journals/2026_08_23.md`
- Create: `tests/fixtures/projection_pqk/v1/expected-snapshot.json`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`

**Interfaces:**
- Consumes: current public functions `rebuild_shadow_from_graph`, `sync_page_to_shadow`, `resolve_shadow_health`, `search_blocks_fts`, and `query_subtree_by_block_uuid`.
- Produces: `capture_sqlite_projection(graph_root: Path) -> ProjectionSnapshot` for tests only, plus a digest-bound v1 corpus that defines actual SQLite behavior before abstraction.

- [ ] **Step 1: Define test-only snapshot records**

Create in `tests/projection/snapshot.py`:

```python
@dataclass(frozen=True, slots=True)
class BlockSnapshot:
    block_uuid: str
    parent_uuid: str | None
    sort_order: int
    indent_level: int
    content: str
    properties_json: str

@dataclass(frozen=True, slots=True)
class PageSnapshot:
    title: str
    file_path: str
    is_journal: bool
    properties_json: str
    blocks: tuple[BlockSnapshot, ...]

@dataclass(frozen=True, slots=True)
class ProjectionSnapshot:
    generation: int
    source_count: int
    indexed_count: int
    quarantined_count: int
    pages: tuple[PageSnapshot, ...]
```

`capture_sqlite_projection` must resolve parents by UUID, sort pages by `file_path`, sort blocks by `(sort_order, rowid)`, and omit timestamps, rowids, absolute paths, and BM25 scores.

- [ ] **Step 2: Build the deterministic fixture corpus**

The corpus must contain nested blocks, explicit UUIDs, Unicode, page properties, wikilinks, tags, block references, duplicate lexical terms, a journal, and one rename target. The manifest records SHA-256 for every fixture and declares `fixture_schema_version: "projection-fixture.v1"`.

- [ ] **Step 3: Write characterization tests**

Add tests with these exact names:

- `test_sqlite_full_rebuild_matches_frozen_snapshot`
- `test_sqlite_incremental_sequence_matches_full_rebuild`
- `test_sqlite_delete_rename_and_replay_preserve_accounting`
- `test_sqlite_subtree_order_and_limits_are_frozen`
- `test_sqlite_lexical_identity_and_tie_break_are_frozen`
- `test_sqlite_quarantine_is_counted_but_not_served`
- `test_sqlite_interrupted_rebuild_preserves_last_generation`
- `test_sqlite_block_refs_table_is_schema_only_baseline`

The final test asserts `SELECT COUNT(*) FROM block_refs` is zero after rebuild, documenting current behavior rather than claiming reference support.

- [ ] **Step 4: Run the characterization suite**

Run:

```bash
uv run pytest tests/projection/test_sqlite_characterization.py -q
uv run pytest tests/test_shadow_hardening_axis2_parity.py tests/test_shadow_bootstrap.py \
  tests/test_shadow_sync.py tests/test_shadow_subtree.py tests/test_shadow_fts.py -q
```

Expected: all tests pass without editing `src/`.

- [ ] **Step 5: Verify fixture and source immutability**

Run a script inside the test that hashes fixture files before and after every projection operation and asserts equality. Confirm `git diff -- src` is empty.

- [ ] **Step 6: Review and commit M1 evidence**

Update the ledger with exact test counts, fixture manifest digest, and the observed zero-row `block_refs` baseline. Run diff-level review and commit:

```bash
git add tests/projection tests/fixtures/projection_pqk/v1 \
  docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md
git commit -m "test(shadow): freeze SQLite projection behavior"
```

### Task 4: M1 contract-review gate before DTO freeze

**Files:**
- Create: `docs/decisions/2026-08-23-projection-contract-v1.md`
- Modify: `docs/decisions/index.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: exact M1 snapshot, fixture manifest digest, and observed current capabilities.
- Produces: reviewed `projection-contract.v1` field list and capability vocabulary; Task 5 is blocked until this decision is approved.

- [ ] **Step 1: Write the decision record from M1 facts**

The record must contain `Context`, `Observed SQLite baseline`, `Authority`, `Decision`, `Rejected alternatives`, `Consequences`, and `Approval`. Freeze these core records unless M1 evidence proves a named field incorrect:

```text
ProjectionPage(title, file_path, file_mtime_ns, file_size, is_journal,
               properties_json, blocks)
ProjectionBlock(block_uuid, parent_uuid, sort_order, indent_level, content,
                properties_json, references)
ProjectionReference(source_block_uuid, target_identity, kind)
ProjectionGeneration(generation, source_count, indexed_count, quarantined_count)
ProjectionHit(block_uuid, content, content_hash, page_identity, stable_order, score)
ProjectionHealth(state, reason, generation, schema_compatible, accounting_valid)
ProjectionCapabilities(backend, contract_version, values)
ProjectionSubtree(status, anchor_uuid, nodes, detail)
```

The record must explicitly note that `ProjectionSubtree` is an M1-informed addition needed to avoid importing `src.shadow.subtree` into the graph domain.

- [ ] **Step 2: Freeze capability semantics**

Use these closed v1 identifiers:

```text
generation-state
lexical-search
subtree-read
reference-lookup
```

SQLite may advertise `reference-lookup` only after Task 6 writes and queries `block_refs`. A schema-only table is not a capability.

- [ ] **Step 3: Record the DTO falsification rule**

State that an M1 mismatch changes this decision record and the approved design ledger before Task 5. Do not make a DTO field optional merely to hide an unexplained mismatch.

- [ ] **Step 4: Run documentation gates**

Run `make docs-inventory-sync`, `make docs-inventory-md`, `make docs-check`, `make agents-check`, and `git diff --check`.

- [ ] **Step 5: Obtain the M1 decision approval**

Present the observed capability matrix, every DTO refinement, and any negative result. Do not start Task 5 until the decision record is explicitly approved.

- [ ] **Step 6: Commit the approved decision**

Run diff-level review and commit with message `docs(architecture): freeze projection contract v1`.

### Task 5: M2 pure records, segregated ports, and parser normalization

**Files:**
- Create: `src/graph/projection/__init__.py`
- Create: `src/graph/projection/models.py`
- Create: `src/graph/projection/ports.py`
- Create: `src/graph/projection/normalize.py`
- Create: `tests/projection/test_projection_models.py`
- Create: `tests/projection/test_projection_ports.py`
- Create: `tests/projection/test_projection_normalize.py`
- Modify: `tests/test_graph_layer_boundary.py:77-134`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`

**Interfaces:**
- Consumes: approved `projection-contract.v1` decision and `logseq_matryca_parser.LogseqPage`/`LogseqNode`.
- Produces: immutable records, `ProjectionIngestPort`, `ProjectionReadPort`, `ProjectionStatePort`, and `normalize_projection_page`.

- [ ] **Step 1: Write failing record and immutability tests**

Test construction, frozen mutation refusal, deterministic tuple ordering, non-negative counters, closed enum values, and rejection of absolute `file_path` values. Include this boundary assertion:

```python
def test_projection_models_reject_absolute_source_paths() -> None:
    with pytest.raises(ValueError, match="graph-relative"):
        ProjectionPage(
            title="Alpha",
            file_path="/private/alpha.md",
            file_mtime_ns=1,
            file_size=1,
            is_journal=False,
            properties_json="{}",
            blocks=(),
        )
```

- [ ] **Step 2: Run model tests and verify RED**

Run: `uv run pytest tests/projection/test_projection_models.py -q`

Expected: collection fails because `src.graph.projection` does not exist.

- [ ] **Step 3: Implement exact record vocabulary**

Use frozen, slotted dataclasses and closed string enums. The core shape in `models.py` is:

```python
class ProjectionCapability(StrEnum):
    GENERATION_STATE = "generation-state"
    LEXICAL_SEARCH = "lexical-search"
    SUBTREE_READ = "subtree-read"
    REFERENCE_LOOKUP = "reference-lookup"

class ProjectionHealthState(StrEnum):
    DISABLED = "disabled"
    BOOTSTRAPPING = "bootstrapping"
    READY = "ready"
    STALE = "stale"
    ERROR = "error"

class ProjectionReferenceKind(StrEnum):
    WIKILINK = "wikilink"
    BLOCK_REF = "block_ref"
    TAG = "tag"

@dataclass(frozen=True, slots=True)
class ProjectionReference:
    source_block_uuid: str
    target_identity: str
    kind: ProjectionReferenceKind

@dataclass(frozen=True, slots=True)
class ProjectionBlock:
    block_uuid: str
    parent_uuid: str | None
    sort_order: int
    indent_level: int
    content: str
    properties_json: str
    references: tuple[ProjectionReference, ...] = ()

@dataclass(frozen=True, slots=True)
class ProjectionPage:
    title: str
    file_path: str
    file_mtime_ns: int
    file_size: int
    is_journal: bool
    properties_json: str
    blocks: tuple[ProjectionBlock, ...]
```

Add the remaining decision-record fields exactly. `ProjectionHit.content` is bounded caller content, `content_hash` is the stable content identity, `stable_order` is the deterministic tie-break value, and `score` is backend-local and excluded from cross-backend fingerprints. Validate in `__post_init__` without importing storage, daemon, CLI, MCP, UI, or agent modules.

- [ ] **Step 4: Write failing protocol-shape tests**

Create small fake adapters and assert runtime protocol conformance separately for ingest, read, and state. Assert there is no `MemoryProjectionBackend` or aggregate port export.

- [ ] **Step 5: Implement segregated protocols**

Use these signatures in `ports.py`:

```python
@runtime_checkable
class ProjectionIngestPort(Protocol):
    def replace_all(self, pages: Sequence[ProjectionPage]) -> ProjectionGeneration: ...
    def upsert_page(self, page: ProjectionPage) -> bool: ...
    def delete_page(self, file_path: str) -> None: ...

@runtime_checkable
class ProjectionReadPort(Protocol):
    def search_blocks(self, query: str, *, limit: int) -> tuple[ProjectionHit, ...]: ...
    def read_subtree(
        self,
        block_uuid: str,
        *,
        max_depth: int,
        max_nodes: int,
        max_output_bytes: int,
    ) -> ProjectionSubtree: ...
    def references_to(self, target_identity: str) -> tuple[ProjectionReference, ...]: ...

@runtime_checkable
class ProjectionStatePort(Protocol):
    def health(self) -> ProjectionHealth: ...
    def generation(self) -> ProjectionGeneration: ...
    def capabilities(self) -> ProjectionCapabilities: ...
```

The ellipses above are protocol bodies, not unfinished implementation.

- [ ] **Step 6: Write failing normalization tests**

Parse the v1 fixture pages and assert deterministic page/block/reference records. Verify `wikilinks`, `tags`, and `block_refs` become distinct `ProjectionReferenceKind` values, duplicate references collapse by `(source_block_uuid, target_identity, kind)`, and block order follows the parser outline.

- [ ] **Step 7: Implement the pure normalizer**

Use this signature:

```python
def normalize_projection_page(
    page: LogseqPage,
    *,
    file_path: str,
    file_mtime_ns: int,
    file_size: int,
    is_journal: bool,
) -> ProjectionPage:
```

The caller supplies filesystem metadata and a sandboxed graph-relative path. The function performs no I/O and imports no backend module.

- [ ] **Step 8: Enforce dependency direction**

Extend `tests/test_graph_layer_boundary.py` so every module under `src/graph/projection/` rejects imports rooted at `src.shadow`, `src.agent`, `src.cli`, `src.ui`, `src.daemon`, `sqlite3`, `ladybug`, `mcp`, `fastmcp`, or `fastapi`.

- [ ] **Step 9: Run focused and architecture tests**

Run:

```bash
uv run pytest tests/projection/test_projection_models.py \
  tests/projection/test_projection_ports.py \
  tests/projection/test_projection_normalize.py \
  tests/test_graph_layer_boundary.py -q
uv run mypy src/graph/projection
uv run ruff check src/graph/projection tests/projection
```

Expected: all commands exit 0.

- [ ] **Step 10: Review and commit**

Run impact review before each existing boundary-symbol edit, run diff-level review, update the ledger, and commit with message `feat(graph): define projection contract v1`.

### Task 6: M2 SQLite adapter behind stable compatibility facades

**Files:**
- Create: `src/shadow/projection_adapter.py`
- Create: `tests/projection/test_sqlite_projection_adapter.py`
- Modify: `src/shadow/sync.py:148-317`
- Modify: `src/shadow/bootstrap.py:72-135`
- Modify: `src/shadow/query.py:17-128`
- Modify: `src/shadow/subtree.py:17-51`
- Modify: `src/shadow/health.py:25-115`
- Modify: `src/shadow/__init__.py`
- Modify: `tests/test_shadow_hardening_axis2_parity.py`
- Modify: `tests/test_canonical_recall.py`
- Modify: `CHANGELOG.md` only if the repository changelog decision gate finds a changed developer-facing contract
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`

**Interfaces:**
- Consumes: Task 5 records/ports and existing SQLite functions.
- Produces: `SQLiteProjectionAdapter` implementing all three ports while preserving every existing public function, type, default, fallback, schema version, and recall identity.

- [ ] **Step 1: Run impact analysis before existing-symbol edits**

Review upstream blast radius for `sync_page_into_connection`, `rebuild_shadow_from_graph`, `search_blocks_fts`, `query_subtree_by_block_uuid`, and `resolve_shadow_health`. Stop and report before editing if any result is HIGH or CRITICAL.

- [ ] **Step 2: Write failing adapter contract tests**

Tests must prove protocol conformance with a real temporary SQLite database:

```python
def test_sqlite_adapter_satisfies_three_segregated_ports(tmp_path: Path) -> None:
    graph_root = tmp_path / "graph"
    graph_root.mkdir()
    connection = open_shadow_db(graph_root)
    adapter = SQLiteProjectionAdapter.for_graph(
        graph_root,
        connection=connection,
    )
    assert isinstance(adapter, ProjectionIngestPort)
    assert isinstance(adapter, ProjectionReadPort)
    assert isinstance(adapter, ProjectionStatePort)
```

Also test rebuild/upsert/delete, rollback preservation, generation/accounting, explicit query normalization, lexical stable-order/UUID tie-breaking, subtree status mapping, reference persistence/query, and capabilities.

- [ ] **Step 3: Run adapter tests and verify RED**

Run: `uv run pytest tests/projection/test_sqlite_projection_adapter.py -q`

Expected: collection fails because `SQLiteProjectionAdapter` does not exist.

- [ ] **Step 4: Implement the SQLite adapter**

`SQLiteProjectionAdapter` owns one caller-managed `sqlite3.Connection` and one resolved graph root. It maps normalized records to existing tables, writes `block_refs` from `ProjectionBlock.references`, and advertises exactly:

```python
frozenset(
    {
        ProjectionCapability.GENERATION_STATE,
        ProjectionCapability.LEXICAL_SEARCH,
        ProjectionCapability.SUBTREE_READ,
        ProjectionCapability.REFERENCE_LOOKUP,
    }
)
```

No new DDL or `SHADOW_SCHEMA_VERSION` bump is permitted because `block_refs` already exists. If current SQLite constraints cannot preserve the reference contract, stop and return to the Task 4 decision gate.

- [ ] **Step 5: Convert existing functions into compatibility facades**

Keep exact signatures and return types for:

```text
open_shadow_db
open_shadow_db_query_only
rebuild_shadow_from_graph
sync_page_into_connection
sync_page_to_shadow
delete_shadow_page_by_file_path
resolve_shadow_health
search_blocks_fts
query_subtree_by_block_uuid
```

Facade tests compare old `BlockHit`, `SubtreeQueryResult`, and `ShadowHealthState` outputs with adapter outputs. Existing callers must not import graph-domain projection records.

- [ ] **Step 6: Prove no recall contract drift**

Assert the constants remain exact:

```python
assert RECALL_SCHEMA_VERSION == "recall-bundle.v1"
assert RECALL_INDEX_VERSION == "shadow-fts5/schema-1"
```

Run all canonical recall tests and verify byte-stable fingerprints are unchanged.

- [ ] **Step 7: Run focused compatibility gates**

Run:

```bash
uv run pytest tests/projection/test_sqlite_projection_adapter.py \
  tests/projection/test_sqlite_characterization.py \
  tests/test_shadow_bootstrap.py tests/test_shadow_sync.py tests/test_shadow_subtree.py \
  tests/test_shadow_fts.py tests/test_shadow_read_port.py \
  tests/test_shadow_hardening_axis2_parity.py tests/test_canonical_recall.py -q
uv run mypy src/graph/projection src/shadow
uv run ruff check src/graph/projection src/shadow tests/projection
```

- [ ] **Step 8: Run full repository CI**

Use the current resource-admission contract before the guarded runner. Proceed only on an explicit admit decision with no conflicting active run, then run `make ci`. Expected: terminal exit 0 on the exact task HEAD.

- [ ] **Step 9: Apply the changelog decision gate**

Evaluate the completed diff under the repository changelog policy. The expected result for a behavior-preserving internal compatibility refactor is no entry. Add one concise Unreleased entry only if review proves that a developer-facing extension contract changed; record the decision either way in the ledger.

- [ ] **Step 10: Review and commit**

Run diff-level review against `main`, confirm affected flows are limited to expected Shadow lifecycle/read paths, update the ledger, and commit with message `refactor(shadow): adapt SQLite to projection contract`.

### Task 7: M3 deterministic Projection Qualification Kit and SQLite reference receipt

**Files:**
- Create: `scripts/projection_pqk.py`
- Create: `tests/projection/test_projection_pqk.py`
- Create: `tests/projection/pqk_schemas/projection-pqk-manifest.v1.schema.json`
- Create: `tests/projection/pqk_schemas/projection-pqk-receipt.v1.schema.json`
- Create: `tests/fixtures/projection_pqk/v1/cases.json`
- Create: `docs/quality/PROJECTION_QUALIFICATION_KIT.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Modify: `Makefile`

**Interfaces:**
- Consumes: the M1 corpus, the approved v1 projection ports, and an explicitly supplied adapter factory.
- Produces: deterministic `projection-pqk-receipt.v1` JSON plus raw per-case artifacts; it never selects or promotes a runtime backend.

- [ ] **Step 1: Define the manifest and receipt schemas before runner code**

The manifest must bind fixture schema, every fixture SHA-256, ordered case IDs, expected evidence class, and required capability. The receipt must bind:

```text
schema_version, matryca_commit, dirty_state, backend_name, backend_version,
projection_contract_version, python_version, os, architecture,
fixture_manifest_sha256, extension_artifacts, selected_capabilities,
started_at, completed_at, cases, raw_artifact_root, receipt_fingerprint
```

Case status is one of `pass`, `partial`, `unsupported`, `no-serve`, `error`, or `not-applicable`. Each case has exactly one evidence class: `structural`, `retrieval`, `operational`, `packaging`, or `observation`.

- [ ] **Step 2: Write schema and determinism tests first**

Tests must reject unknown fields, unknown statuses, absolute/private source paths, missing fixture digests, duplicated case IDs, and fingerprints that include timestamps, raw scores, or absolute artifact roots. Run the focused tests and verify RED because the runner does not exist.

- [ ] **Step 3: Implement a network-free, LLM-free runner**

`scripts/projection_pqk.py` owns immutable manifest/receipt records, canonical JSON encoding, SHA-256 calculation, capability-aware case dispatch, and content-safe diagnostics. It exposes a typed test-harness API:

```python
def run_projection_pqk(
    config: ProjectionPqkRunConfig,
    *,
    adapter_factory: ProjectionAdapterFactory,
) -> ProjectionPqkReceipt:
```

`ProjectionPqkRunConfig` contains the fixture manifest, disposable output root, exact source commit, and a development-only dirty-state flag. The function refuses a dirty checkout unless that flag is explicitly set, refuses output inside a Logseq graph, and never discovers or selects a backend. The caller supplies one adapter factory directly. There is no argument parser, installed command, backend selector, network, model, daemon, MCP, product CLI, or UI path.

- [ ] **Step 4: Implement the minimum M3 case families**

Run normalization, initial ingest, full rebuild, incremental upsert/delete/rename/replay, malformed/quarantine, generation/accounting, subtree, reference lookup, explicit lexical query normalization and ordering, empty-result behavior, missing fixture/artifact refusal, stale/schema/corrupt no-serve, rollback, checkpoint, and close cases. Performance fields remain observations and cannot change structural pass/fail.

- [ ] **Step 5: Add a local make target**

Add `projection-pqk-sqlite` as a fixed test target that invokes only the SQLite qualification test and writes beneath pytest's disposable temporary root. It exposes no backend or path selector, and must not install dependencies, contact a registry, or alter the repository fixture corpus.

- [ ] **Step 6: Prove deterministic output**

Run the SQLite PQK twice from fresh disposable roots at the same exact clean commit. Compare canonical case payloads and receipt fingerprints; only start/end timestamps and absolute raw-artifact locations may differ outside the fingerprint. A receipt produced with `--allow-dirty` is development evidence only and is ineligible as the SQLite reference, promotion, PR, or release receipt.

- [ ] **Step 7: Publish the SQLite reference receipt metadata**

Keep raw artifacts outside Git. Add a content-safe evidence-index row containing exact commit, fixture-manifest digest, backend identity, receipt fingerprint, case counts, limitations, and external retained-artifact location. Do not publish private paths or fixture content in the index.

- [ ] **Step 8: Run gates and commit**

Run focused PQK tests, the exact SQLite PQK twice, `make docs-check`, `make agents-check`, `git diff --check`, and diff-level review. Update the ledger and commit with message `feat(quality): add projection qualification kit`.

### Task 8: M4 exact optional dependency and offline Ladybug adapter

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `src/experimental/__init__.py`
- Create: `src/experimental/projection/__init__.py`
- Create: `src/experimental/projection/ladybug_adapter.py`
- Create: `tests/projection/test_ladybug_projection_adapter.py`
- Create: `tests/projection/test_ladybug_dependency_boundary.py`
- Create: `tests/fixtures/projection_pqk/v1/ladybug-extension-manifest.example.json`
- Modify: `scripts/projection_pqk.py`
- Modify: `tests/test_graph_layer_boundary.py`
- Modify: `tests/test_packaging_manifest.py`
- Modify: `docs/quality/PROJECTION_QUALIFICATION_KIT.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `CHANGELOG.md` only if the repository changelog decision gate finds a shipped developer-facing contract

**Interfaces:**
- Consumes: the three v1 projection ports and an isolated disposable database path.
- Produces: `LadybugProjectionAdapter` for offline PQK execution only. No stable runtime surface imports this package.

- [ ] **Step 1: Revalidate the exact candidate before editing dependencies**

Verify the official package metadata for `ladybug==0.19.1`: Python compatibility, supported wheel platforms/architectures, license, source repository, release commit, artifact names, and SHA-256 values. Record the dated result in the execution ledger. If the exact release is unavailable, yanked, incompatible, differently licensed, or lacks a required platform artifact, stop and return to design review instead of selecting a newer version implicitly.

- [ ] **Step 2: Add an exact, isolated optional dependency group**

Add:

```toml
projection-ladybug = [
    "ladybug==0.19.1",
]
```

The package must remain absent from default dependencies and from the `dev` group. Lock resolution is performed once under an explicit network-enabled preparation step; later PQK runs use the exact lock and admitted artifacts offline.

- [ ] **Step 3: Write failing dependency-boundary and adapter tests**

Prove all of the following before implementation:

- importing stable Matryca modules does not import `ladybug`;
- importing `src.experimental.projection` without the optional package gives a typed unsupported result rather than breaking startup;
- the adapter refuses `shadow.sqlite`, a path inside the source graph, and a non-disposable output root;
- one adapter owns one `Database` object and closes it once;
- transaction failure leaves the prior committed generation queryable;
- capabilities exclude lexical or vector search unless exact local extension evidence is admitted;
- Markdown and the SQLite Shadow file remain byte-identical through every Ladybug case.

Run the focused tests and verify RED because the package and adapter do not exist.

- [ ] **Step 4: Implement the smallest offline adapter**

Create node types for projection metadata, pages, blocks, and references. Use explicit relationships for page ownership, parent-child structure, and block references. Preserve graph-relative source identity, stable UUIDs, deterministic order, generation/accounting, and quarantine state. `replace_all`, `upsert_page`, and `delete_page` execute in explicit transactions. Subtree and reference queries must be bounded and deterministically ordered.

The module may import `ladybug` only behind its optional boundary. It must not import daemon, MCP, CLI-product, UI, agent, mutation-plane, or SQLite implementation modules.

- [ ] **Step 5: Make extension admission explicit and offline**

The adapter accepts an optional extension manifest containing extension name, version, source URL, platform, architecture, local artifact path, and SHA-256. It validates every field before `LOAD`. It never executes `INSTALL`. Missing or mismatched evidence removes the related capability and yields `unsupported` or `no-serve`; it never downloads an artifact.

The `llm` extension is forbidden. Any later vector probe uses repository-defined deterministic vectors and a separately admitted vector extension artifact.

- [ ] **Step 6: Exercise Ladybug through the typed PQK API**

Create an adapter-specific qualification test that imports `LadybugProjectionAdapter` explicitly and passes its factory to `run_projection_pqk`. The test creates both database and output roots beneath one pytest-owned disposable root. There is no backend registry, string selector, argument parser, installed command, or fallback to another backend. Stable SQLite runtime behavior remains unchanged.

- [ ] **Step 7: Run focused structural qualification**

Run adapter tests and the structural/reference/state PQK families from fresh disposable roots with networking disabled. Record exact Matryca commit, `ladybug` version and distribution digest, Python, OS, architecture, fixture manifest digest, capabilities, receipt fingerprint, negative cases, and limitations.

- [ ] **Step 8: Run packaging and import gates**

Build the default wheel and prove it imports and starts without the optional package. Build a qualification environment from the exact lock and prove the optional adapter imports. Hosted package matrices remain a separate gate; local success is not cross-platform qualification.

- [ ] **Step 9: Run full compatibility gates**

Run the SQLite PQK again, existing Shadow/read-only/recall suites, architecture tests, typing, lint, default wheel smoke, documentation checks, and guarded `make ci`. Confirm there is no runtime selector, environment variable, daemon registration, MCP tool, CLI command, UI control, or README claim.

- [ ] **Step 10: Apply the changelog gate and commit**

Evaluate whether the optional offline adapter is a shipped developer-facing contract or only qualification infrastructure. Add one concise Unreleased entry only for the former; otherwise record the no-entry decision in the ledger. Run diff-level review, update the ledger, and commit with message `feat(experimental): add offline graph projection adapter`.

### Task 9: M5 graph-native value, retrieval, and performance probe

**Files:**
- Create: `scripts/bench_projection_backends.py`
- Create: `tests/projection/test_projection_backend_benchmark.py`
- Create: `tests/fixtures/projection_pqk/v1/retrieval-cases.json`
- Create: `tests/fixtures/projection_pqk/v1/deterministic-vectors.json`
- Create: `docs/quality/GRAPH_NATIVE_VALUE_PROBE_2026-08-23.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/quality/PROJECTION_QUALIFICATION_KIT.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: exact M3 SQLite and M4 Ladybug receipts plus repository-owned retrieval labels.
- Produces: separate structural, retrieval-quality, graph-traversal, vector, and performance observations; it does not alter the v1 projection port or runtime routing.

**Approval gate:** This task may begin with lexical and structural benchmark preparation, but graph-native traversal and vector-search execution are blocked until their capability slices are separately reviewed and explicitly approved. Approval of this implementation plan alone does not satisfy that gate.

- [ ] **Step 1: Freeze hypotheses and decision thresholds before running**

Record the candidate hypotheses and falsification criteria in the value-probe document:

1. graph-native reference and ancestry traversal preserves exact structural answers;
2. bounded graph traversal has a measurable benefit on multi-hop cases that is not explained by fixture error;
3. lexical retrieval remains within predeclared overlap and missed-relevant-item limits;
4. optional deterministic-vector retrieval adds value on labelled semantic cases without hidden inference;
5. startup, ingest, rebuild, warm-read, storage, and memory costs remain explicitly acceptable or are reported as blockers.

Set thresholds from the SQLite reference distribution and product constraints before seeing Ladybug results. Do not use post-hoc threshold adjustment.

- [ ] **Step 2: Create provenance-bound labelled cases**

Extend the synthetic corpus with exact expected UUID sets for lexical, empty-result, one-hop reference, multi-hop reference, ancestor, descendant, and negative queries. Add at least three deterministic seeds for generated scale cohorts. Store expected identities, normalized query text, query class, tokenizer/stemmer configuration, and known query-class limitations—but not cross-backend scores. Hash every case and vector artifact in the fixture manifest.

- [ ] **Step 3: Write benchmark-harness tests**

Tests must prove deterministic seed expansion, warmup separation, repeated-sample accounting, timeout enforcement, canonical UUID tie-breaking, score exclusion from cross-backend fingerprints, immutable source fixtures, and statistical output schemas. Test that one backend failure produces a retained negative result instead of deleting the campaign.

- [ ] **Step 4: Implement the benchmark harness**

Collect per backend and cohort:

```text
startup_seconds, ingest_seconds, rebuild_seconds, warm_read_seconds,
peak_rss_bytes, storage_bytes, result_overlap, reciprocal_rank,
rank_correlation, relevant_misses, false_positives, timeout_count
```

Use multiple measured repetitions after explicit warmup. Report raw samples, median, dispersion, exclusions, confidence intervals where justified, empty-result behavior, normalized query text, query-class limitations, and exact tokenizer/stemmer configuration for each backend. Never merge structural conformance and performance into one pass flag.

- [ ] **Step 5: Run lexical and graph-traversal comparisons**

Before running this step, verify that the ledger contains explicit approval for the graph-traversal capability slice. If approval is absent, record `not-authorized`, do not execute traversal queries, and continue only with already authorized lexical evidence. When approved, SQLite and Ladybug independently ingest the same normalized records. SQLite results come from its stable adapter and explicit recursive reference queries in the benchmark harness; Ladybug results come from graph relationships. Compare canonical identity sets and bounded ordering. Raw BM25 scores remain backend-local observations.

- [ ] **Step 6: Run the optional vector probe only with admitted artifacts**

Before running this step, verify that the ledger contains separate explicit approval for the vector-search capability slice. If approval is absent, record `not-authorized` and do not load the extension or execute vector queries. When approved, use committed deterministic vectors; do not call a model or extension-provided embedding function. Load only an exact locally admitted vector extension artifact. If provenance, platform compatibility, or offline loading fails, record `unsupported` and continue the non-vector campaign. Do not weaken the graph or lexical gates.

- [ ] **Step 7: Bind results to related programme authorities**

Classify retrieval-quality observations as evidence relevant to #448 and final-world-state questions as future inputs to #483. Do not claim those issues are satisfied by the PQK. State explicitly that #519's neutral TCK remains independent and database-agnostic.

- [ ] **Step 8: Review and commit retained evidence**

Run benchmark tests, two deterministic small-cohort dry runs, documentation gates, `git diff --check`, and diff-level review. Keep raw artifacts outside Git and publish only content-safe summaries plus receipt fingerprints. Update the ledger and commit with message `perf(quality): compare projection backend value`.

### Task 10: M5 ownership, interruption, recovery, and packaging qualification

**Files:**
- Create: `scripts/qualify_projection_operational.py`
- Create: `tests/projection/test_projection_operational_qualification.py`
- Create: `docs/quality/GRAPH_NATIVE_OPERATIONAL_QUALIFICATION_2026-08-23.md`
- Create: `.github/workflows/projection-pqk.yml`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/quality/PROJECTION_QUALIFICATION_KIT.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`

**Interfaces:**
- Consumes: exact optional-package lock, M4 adapter, M5 fixture manifest, and disposable qualification roots.
- Produces: retained local and hosted receipts for ownership, interruption, restart, checkpoint, cleanup, import, and package-platform behavior.

- [ ] **Step 1: Write the operational state machine and safety envelope**

Define `prepared`, `running`, `interrupted`, `recovered`, `closed`, and `failed_closed` states. Every run owns one disposable root, one database path, one immutable run manifest, one append-only event log, and one terminal receipt. The harness refuses source graphs, `shadow.sqlite`, non-empty unowned roots, unknown manifests, and concurrent ownership.

- [ ] **Step 2: Write failing operational tests**

Test single-owner acquisition, second-owner refusal, stale-owner diagnosis, explicit recovery, transaction interruption at each declared failpoint, prior-generation preservation, checkpoint idempotence, close idempotence, partial-output retention, and cleanup limited to the owned disposable root. Do not simulate success by relabelling an interrupted or skipped case.

- [ ] **Step 3: Implement subprocess-driven qualification**

Use deterministic child processes and explicit failpoints after database open, transaction begin, partial ingest, pre-commit, post-commit, checkpoint, and pre-close. Parent and child communicate only through the owned run directory. Kill only the exact child PID after verifying its manifest identity. No reboot, system service, real disk pressure, or user graph is required for this slice.

- [ ] **Step 4: Prove owner and lock behavior**

Run one read-write database owner and same-object connections permitted by the adapter. Attempt a second independent owner and any unsupported mixed read-write/read-only pattern; require deterministic refusal or record a blocker. No online owner service is implemented here.

- [ ] **Step 5: Prove restart and rollback behavior**

For every failpoint, reopen from a fresh process and verify either the prior committed generation or the complete new generation—never a mixed generation. Verify canonical Markdown and stable SQLite digests are unchanged. Verify deleting only the experimental database fully rolls back the experiment.

- [ ] **Step 6: Run guarded local resource qualification**

Use the current [Commit CI Preflight coordination runbook](https://github.com/MarcoPorcellato/commit-ci-preflight/blob/main/docs/COORDINATION_RUNBOOK.md) and record its exact source commit plus the installed resource-policy version in the ledger. Proceed only on explicit admit with no conflicting active or queued run. Preserve the admission receipt with the operational receipt. A denied, unknown, queued, interrupted, or historical run is not qualification evidence.

- [ ] **Step 7: Add a manual hosted workflow**

The workflow is `workflow_dispatch` only, least-privilege, concurrency-bounded, dependency-cached, and matrixed over supported Python and runner platforms that have an exact candidate wheel. It installs from the exact lock, runs import/package smoke and bounded PQK cases, uploads receipts, and never publishes packages or changes releases. Expected platform gaps are explicit `unsupported`, not green skips.

- [ ] **Step 8: Reconcile local and hosted receipts**

Require exact head SHA, fixture digest, dependency version, distribution digest, contract version, and case schema. Keep local macOS evidence, hosted platform evidence, and source-only checks separate. Stop on any mismatch, unexpected skip, unresolved failure, or missing artifact.

- [ ] **Step 9: Run repository gates and commit**

Run operational tests, bounded local campaign, workflow lint, packaging tests, default import smoke, docs gates, guarded `make ci`, and diff-level review. Update the ledger and commit with message `test(quality): qualify projection operations`.

### Task 11: M6 terminal promotion decision and programme reconciliation

**Files:**
- Create: `docs/decisions/2026-08-23-graph-native-projection-outcome.md`
- Modify: `docs/decisions/index.md`
- Modify: `docs/quality/EVIDENCE_INDEX.md`
- Modify: `docs/quality/GRAPH_NATIVE_PROJECTION_EXECUTION_STATUS_2026-08-23.md`
- Modify: `docs/roadmaps/ROADMAP_GRAPH_NATIVE_PROJECTION.md`
- Modify: `docs/knowledge/inventory.json`
- Modify: `docs/knowledge/inventory.md`
- Modify: `CHANGELOG.md` only if the terminal outcome changes a shipped public contract

**Interfaces:**
- Consumes: exact M1-M5 commits, receipts, raw-artifact digests, negative results, limitations, and hosted matrix status.
- Produces: one evidence-bound outcome. It cannot add runtime selection or change SQLite's default.

- [ ] **Step 1: Verify the evidence chain before interpretation**

Recompute every committed fixture, manifest, receipt, and raw-artifact digest. Verify exact commit ancestry, clean-tree status, backend/package identities, contract versions, platform labels, capability sets, case counts, expected skips, and external artifact retention. Reject evidence from another commit, changed fixture, incomplete run, stale index, running job, or undocumented exclusion.

- [ ] **Step 2: Build a facts/proposals/unknowns/limitations table**

Keep exact structural results, retrieval outcomes, performance observations, operational safety, packaging reach, and extension provenance in separate rows. State negative and unsupported cases directly. Do not infer product superiority, standard conformance, or end-to-end agent-memory value from backend qualification.

- [ ] **Step 3: Select exactly one terminal outcome**

Choose one and justify it against predeclared gates:

- `preferred_candidate`
- `supported_optional_candidate`
- `experimental_continue`
- `deferred_upstream_or_packaging`
- `rejected_with_evidence`

`preferred_candidate` and `supported_optional_candidate` still mean candidate status only. Neither permits online routing, a new environment variable, a daemon owner, a README availability claim, or a stable-default change.

- [ ] **Step 4: Define the smallest authorized follow-up**

For a positive outcome, draft—but do not implement—a separate online-owner/runtime-selection design with explicit user approval. For a deferred or rejected outcome, list the exact upstream, packaging, correctness, cost, or operational condition required for reconsideration. Preserve SQLite characterization and PQK assets regardless of outcome.

- [ ] **Step 5: Reconcile issue and documentation state**

Update the product epic and only the incremental child issue represented by completed public work, after explicit GitHub authorization. Link related evidence to #446, #448, #483, #519, and #520 without transferring authority or closing them. Keep README and release notes unchanged unless a separately shipped public contract warrants an update.

- [ ] **Step 6: Run final deterministic gates**

Run all focused suites, both backend PQK campaigns applicable to the selected capabilities, operational tests, default and optional packaging smoke, docs gates, architecture checks, typing, lint, guarded full CI, and hosted CI on the exact PR head. Verify no unexpected skip, unresolved review thread, scope concern, or evidence mismatch remains.

- [ ] **Step 7: Request independent review**

Have one bounded reviewer audit architecture and authority, one audit tests and negative cases, and one audit evidence/reproducibility. The primary orchestrator independently inspects every finding and exact diff. Resolve or explicitly reject each actionable finding with evidence.

- [ ] **Step 8: Commit the terminal decision**

Run final diff-level review, update the ledger to a terminal state, and commit with message `docs(architecture): record projection qualification outcome`. Push, PR, merge, announcement, release, and any external issue mutation remain separate authorization gates.

## Requirement-to-task coverage

| Approved requirement | Implemented or proven in |
| --- | --- |
| Markdown and governed evidence remain canonical | Tasks 1, 4, 5, 8, 10, 11 |
| SQLite remains stable default | Tasks 1, 3, 6, 8, 11 |
| No direct migration or second mutation authority | Tasks 1, 5, 8, 10 |
| Pure records and segregated ports | Tasks 4-6 |
| Existing public behavior and recall identity preserved | Tasks 3 and 6 |
| Deterministic PQK distinct from the neutral TCK | Tasks 2, 7, 9, 11 |
| Exact optional offline candidate | Task 8 |
| No runtime extension download or hidden inference | Tasks 8 and 9 |
| Structural, retrieval, quality, performance, and operational evidence separated | Tasks 7, 9, 10, 11 |
| Interruption, restart, ownership, checkpoint, packaging, and rollback proof | Task 10 |
| Negative, deferred, and rejected results are valid outcomes | Tasks 7, 9, 10, 11 |
| No runtime selector before a new approved design | Tasks 8 and 11 |
| Interruption-safe, cost-aware execution | Delivery topology and every task ledger update |

## Persistent execution goal

Qualify a backend-neutral, graph-native derived projection architecture for Matryca Plumber while preserving canonical Markdown authority, SQLite as the stable default, existing v2.0 behavior, and exact evidence boundaries. Execute M0-M6 in order from an isolated worktree; checkpoint every completed task in the durable ledger; use bounded lower-cost workers for independent evidence and mechanical slices; retain architecture, safety, public claims, integration, and terminal decisions with the primary orchestrator. Stop at every explicit approval, provenance mismatch, unsupported platform, unexpected skip, concurrency uncertainty, evidence-integrity failure, or scope expansion. Completion requires one reviewed M6 terminal outcome with exact receipts and no claim beyond evidence.

## Final completion gate

This plan is complete only when all of the following are true:

- every task checkbox is resolved as passed, explicitly unsupported, deferred with a named condition, or rejected with retained evidence;
- the execution ledger names the exact terminal commit, dirty state, fixtures, receipts, external artifact locations, limitations, and next authorized action;
- stable SQLite behavior, defaults, fallback, read-only compatibility, recall identity, and canonical Markdown authority are unchanged unless a separate approved design says otherwise;
- no runtime graph-backend selector, owner service, MCP/CLI/UI route, release, or marketing claim has entered through this plan;
- local and hosted evidence is bound to exact artifacts and commits, and skipped or running checks are not counted as qualification;
- exactly one M6 outcome is published in the repository after review.

At that point, stop. Any online runtime experiment is a new design and authorization cycle.
