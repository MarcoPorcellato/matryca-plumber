---
type: execution-plan
title: Matryca Plumber repository excellence study
description: Evidence-backed, gated programme for repository safety, performance, documentation, operations, and governance.
resource: docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
tags: [quality, roadmap, governance, okf]
timestamp: 2026-08-06T00:00:00Z
status: draft
decision_status: accepted
classification: active
last_verified: 2026-08-06
audience: [maintainer, contributor, agent]
owner: quality
authority: roadmap
execution_mode: gated
source_repository: MarcoPorcellato/matryca-plumber
source_ref: origin/main
source_commit: 1e8805ec99c6471549ecf36e4a261a31013a0f6f
official_okf_spec_version: "0.2"
official_okf_conformance: not_claimed
matryca_quality_profile: transitional
matryca_knowledge_baseline: 7a3ebd8966340f00aea0730ba14ee2d2fd8ba6c2
registry_projection: reviewed_only
---

# Matryca Plumber repository excellence study

**Date:** 2026-08-06

**Baseline:** `origin/main@1e8805ec99c6471549ecf36e4a261a31013a0f6f`

**Decision status:** accepted evidence-backed plan; no release authorization and no production implementation

**Scope:** codebase, architecture, safety, performance, resilience, tests, CI, packaging, documentation, contributor experience, and repository governance

## Executive conclusion

Matryca Plumber is already beyond the point where a broad rewrite would improve it. The repository has a strong automated baseline, a conservative Shadow DB design, explicit read-only policy, external cache containment, deterministic documentation checks, strict typing, and substantial test coverage. The path to a stellar repository is now selective: close a small number of safety and freshness gaps, make performance observable before changing concurrency, consolidate documentation authority, and convert the large historical backlog into a sequenced delivery system.

The highest-value direction is:

1. Protect the v2.0 release line: complete exact-artifact Gate B qualification and avoid unrelated runtime changes before the stable decision.
2. Fix four high-confidence correctness boundaries in small, independent slices:
   - read-only startup must not create graph-local log directories;
   - X-Ray must not hide a graph-local mutation behind a read contract;
   - Shadow `READY` must imply freshness or fail over to Markdown;
   - every Shadow synchronization failure must invalidate stale cache use without failing the authoritative Markdown write.
3. Instrument first, then optimize the serialized hot paths in generational caches, incremental graph indexing, Shadow synchronization, and watcher convergence.
4. Make one canonical operator path for v2 Shadow DB, read-only mode, health/fallback semantics, and release state.
5. Reconcile the open backlog and milestones so architecture, release, and contributor work have a single execution order.

This study deliberately keeps v2.0 stable-read-path work separate from v2.1 biological memory and Logseq DB Safe-Sync.

## Initial plan

The study began with five gates:

1. Establish an exact baseline and verify repository instructions, current documentation structure, code-intelligence freshness, and working-tree isolation.
2. Run four independent review tracks:
   - documentation architecture and operator/contributor usability;
   - CI, testing, packaging, developer experience, and repository hygiene;
   - Clean Architecture, persistence safety, concurrency, and security;
   - performance, scalability, resilience, Shadow DB, BM25, and soak representativeness.
3. Cross-check proposed findings against live source and deterministic repository checks.
4. Synthesize a prioritized roadmap with explicit evidence, acceptance gates, dependencies, non-goals, and existing-issue mappings.
5. Challenge the draft, reject poorly supported ideas, and leave one durable Markdown record.

## Method and evidence controls

- The source baseline was isolated from the maintainer's active soak-documentation branch.
- Four supporting review tracks were assigned according to boundedness and judgment required; the primary review retained integration, safety decisions, and final claim verification.
- Deterministic checks preceded recommendations.
- Local graph-based static analysis was used only for orientation because its index was eight commits behind the audited baseline. Every material finding in the final priority list was checked against current source.
- Symbolic Python analysis was unavailable in the supporting worktrees; line-numbered current-source inspection was used instead.
- GitHub was queried read-only to avoid duplicating open work. No issues, pull requests, tags, releases, or remote branches were changed.
- No production source was edited by this study.

## Matryca Knowledge alignment and authority

This plan adopts the federated documentation direction accepted in the private
Matryca Knowledge repository at
`main@7a3ebd8966340f00aea0730ba14ee2d2fd8ba6c2`. The authority boundary is
deliberate:

| Surface | Authority and role |
| --- | --- |
| Matryca Plumber source repository | Authoritative origin for this plan and all Plumber documentation |
| Matryca Knowledge `knowledge/matryca-plumber/` | Reviewed projection with immutable source provenance; never an editing origin |
| Plumber `docs/knowledge/` | Transitional maintained bundle and local quality profile |
| Historical reports and release evidence | Timestamped evidence; preserve rather than mass-normalize |

The accepted model contains two independent result streams:

1. **Official OKF v0.2 conformance** checks only the external format contract.
2. **Matryca quality** adds stricter ownership, navigation, freshness,
   classification, link, anchor, provenance, privacy, and canonical-role rules.

This document does **not** claim official OKF v0.2 conformance. The current
Matryca validator implements a transitional OKF-inspired flat-frontmatter
profile; the planned nested v0.2 parser and dual-layer conformance reporter are
not treated as shipped. `status` therefore uses the official lifecycle
vocabulary (`draft`, `stable`, `deprecated`), while plan acceptance and Matryca
classification remain separate extension fields.

Adoption rules for this programme:

- maintain stable Markdown paths as concept identities;
- keep ordinary Markdown links as explicit knowledge edges;
- bind findings and decisions to repository, commit, path, and verification date;
- require deterministic checks and stable evidence before any acceptance claim;
- preserve unknown extension fields and avoid destructive mass migration;
- refresh Matryca Knowledge only through a separately reviewed projection from
  authoritative Plumber bytes;
- report official conformance and Matryca quality separately, never infer one
  from the other.

## Verified baseline

### Repository scale

These values were captured from the clean pre-study baseline on 2026-08-06. Repository
file counts use `git ls-tree -r --name-only origin/main`; source/document line counts use
`rg --files <scope> -g <pattern> | xargs wc -l`. They intentionally exclude this dossier
and its generated inventory update.

| Measure | Verified value |
| --- | ---: |
| Repository-wide tracked Python files | 408 |
| Tracked Python test files under `tests/` | 162 |
| Repository-wide tracked Markdown files | 189 |
| GitHub workflow files | 5 |
| Python source lines under `src/` | 39,270 |
| Markdown lines under `docs/` | 14,300 |
| Open GitHub issues | 49 |
| Open issues without a milestone | 29 |
| Open pull requests | 5 |

GitHub counts were captured read-only at 2026-08-06 with `gh issue list --state open
--limit 200 --json number,milestone,labels` and `gh pr list --state open --limit 100`.
They are a timestamped remote snapshot, not immutable repository facts. The 29
unmilestoned issues conflict with the repository's own workflow rule that every
non-question/non-wontfix issue should have a milestone
(`.cursor/rules/08-github-workflow-standards.mdc`). This is a governance defect, not a
runtime defect.

### Automated health

The following checks passed on the exact baseline in an isolated worktree:

- `make ci`
  - 408 files formatted;
  - Ruff clean;
  - mypy strict clean across 372 source files;
  - graph sandbox read check clean;
  - version, agent-router, public-metrics, and generated-prompt checks clean;
  - full pytest suite passed with five skips and one macOS fork deprecation warning.
- `make docs-check`
  - knowledge inventory synchronized;
  - generated inventory view synchronized;
  - documentation knowledge bundle clean.
- `make agents-check`
- `make check-system-prompt`

This is a healthy baseline. The recommendations below are about raising assurance, operability, and maintainability rather than repairing a generally failing repository.

### Structural signals

Current local graph-based analysis reported five import cycles:

1. `src/agent/dispatch_mutate_handlers.py` ↔ `src/agent/graph_dispatch.py`
2. `src/agent/importers/tana/graph.py` ↔ `src/agent/importers/tana/load.py`
3. `src/agent/markdown_graph_repository.py` ↔ `src/agent/shadow_graph_repository.py`
4. `src/graph/alias_index.py` ↔ `src/graph/generational_cache.py`
5. `src/graph/page_path.py` ↔ `src/graph/path_sandbox.py`

Because the index was stale, these are refactoring candidates to reconfirm with a fresh index before implementation, not proof that all five cycles remain identical at the current commit. One boundary-test weakness was independently verified in current source: the test misses `from ...agent` imports and broadly exempts `generational_cache.py` from the graph-to-RAG rule (`tests/test_graph_layer_boundary.py:8-44`). Current production source contains both patterns (`src/graph/insights/prompts.py:8`, `src/graph/generational_cache.py:225-255`).

## What is already excellent

### Source-of-truth and fallback design

- Markdown remains authoritative; SQLite is a derived read cache.
- Shadow subtree reads fall back to Markdown when disabled, unhealthy, inconsistent, or when the backend raises (`src/agent/shadow_graph_repository.py:102-164`).
- Incremental Shadow synchronization is transactional and bounded-parses each page (`src/shadow/sync.py:163-309`).
- Rebuild failure rolls back instead of publishing a partial generation (`src/shadow/bootstrap.py:66-127`).
- Quarantine isolates pathological pages without making SQLite authoritative (`src/shadow/quarantine.py`, `src/shadow/health.py:45-65`).

### Read-only and cache isolation

- Graph-local writes pass through a central policy and atomic-write primitive.
- External Shadow locations are canonicalized, graph-identity hashed, containment checked, and symlink protected (`src/shadow/cache_location.py:101-164`).
- Cross-process writer locking protects Shadow mutations (`src/shadow/writer_lock.py:23-55`).
- The read-only daemon profile disables graph-local duties and observes through the external cache (`src/agent/maintenance_daemon.py:1030-1104`).

### Verification and release discipline

- Formatting, linting, typing, sandbox reads, generated prompts, version identity, and the full test suite are one `make ci` gate.
- Release artifacts are built from a clean tracked-source snapshot.
- The Gate B soak harness binds the exact artifact, hash-chains attempts, persists atomic checkpoints, probes restart/recovery, excludes downtime, and fails closed (`scripts/beta_evidence/soak.py`).
- Documentation already has a curated inventory and a gradual knowledge-bundle migration rather than an uncontrolled mass move.

## Priority register

### P0 — Release-line protection and mandatory pre-stable disposition

EX-02 and EX-03 are verified contract defects. EX-04 and EX-05 are verified control gaps
whose worst stale-read outcomes still require focused reproduction/fault injection.
Before stable authorization, the maintainer must disposition all four: either fix and
requalify the affected profile, or document with evidence why the stable product contract
does not include the scenario. `P0` means decision-blocking until disposition; it does not
claim that every item has already reproduced as a production incident.

#### EX-01 — Finish Gate B before stable authorization

**State:** in progress outside this document.

**Existing tracking:** #343, Epic #20.

**Why first:** stable v2.0 must be decided from the exact public RC artifact, not from source-tree tests or previous beta evidence.

Acceptance gate:

- both durable profiles reach terminal `PASS` for the required credited elapsed time;
- attempt chains, runner manifest, wheel and installed `RECORD`, heartbeats, stderr, restart continuity, cycle counts, and downtime exclusion validate;
- release preparation, stable tag, GitHub Release, and PyPI publication remain separate maintainer authority gates.

Non-goal: do not fold v2.1 Safe-Sync or biological memory into this gate.

#### EX-02 — Enforce read-only before startup directory creation

**Finding:** `prepare_matryca_runtime()` calls `ensure_plumber_log_directories()` before constructing `RuntimeWritePolicy` (`src/utils/runtime_bootstrap.py:123-145`). The log helper creates both parent directories immediately (`src/utils/config_paths.py:130-136`). A graph-local log configuration can therefore violate read-only startup immutability. This is configuration-dependent; the default/external log path is not claimed to mutate the graph.

**Smallest slice:** classify log destinations before `mkdir`; under strict read-only, reject graph-local log paths or route them to an external runtime/cache location.

Acceptance gate:

- parameterized MCP, CLI, UI, and daemon bootstrap tests for both graph-local and external log paths;
- graph-local ops and Loguru paths under read-only create no directory and leave a pre/post graph manifest identical;
- normal mode and external logs remain unchanged.

Non-goal: do not prohibit external logs or external Shadow writes.

#### EX-03 — Resolve the X-Ray read/write contract

**Verified contract mismatch:** `read_xray_page_markdown()` describes a read but generates and persists `.matryca_xray_state.json` (`src/agent/graph_tool_helpers.py:149-195`, `src/agent/alias_state.py:72-80`). Read-only mode blocks the write, making the API classification misleading.

**Decision needed:** either move ephemeral alias state outside the graph and preserve a read contract, or expose alias generation as an explicit mutation. External ephemeral state is the preferred reversible proposal, not an established requirement; it needs explicit ownership, graph identity, permissions, cleanup, and concurrency semantics.

Acceptance gate:

- read-only X-Ray works without graph changes, or returns a typed policy result before parsing if explicitly classified as mutation;
- the current read-only failure path is characterized, including whether it becomes a generic read error;
- normal-mode alias/UUID semantics remain identical;
- concurrent requests cannot corrupt or cross-contaminate alias state.

Non-goal: do not remove X-Ray aliases.

#### EX-04 — Make Shadow freshness explicit

**Implemented in #389:** `READY` remains an aggregate cache-health state, while each
cached read now proves the source identity of the rows it is about to serve. Subtree
reads validate the requested page; FTS reads validate every unique returned page.
The check is bounded by the request (`1` page for subtree, at most the result limit for
FTS) and compares the sandboxed graph-relative path, nanosecond mtime, and byte size
with the persisted page row. It never performs a full graph scan.

Changed, missing, or untracked rows route to authoritative Markdown or generational
BM25. A zero-hit FTS result also routes to BM25 because an empty cached result cannot
prove that an unreconciled page has not gained the query term. Every such route adds
one closed, content-free reason: `page_untracked`, `source_missing`, `source_changed`,
or `empty_result_unproven`. A deleted subtree source returns an explicit unavailable
envelope rather than stale cached content or a raw file exception.

Watcher-disabled edit, delete, and rename fixtures pass. Fresh-hit tests reject any
attempted `Path.rglob`, proving the read-time check is request-bounded. On macOS
15.7.3 arm64 with Python 3.12.13, 500 warm synthetic iterations measured subtree
p95/p99 at 9.638/12.579 ms and FTS p95/p99 at 9.265/11.343 ms. CI retains deliberately
looser 250/500 ms p95/p99 soft ceilings to detect pathological regressions without
turning ordinary runner jitter into failures.

**Proof boundary:** non-empty FTS responses prove every cached row returned, not the
global absence of a newly matching unreconciled page elsewhere in the graph. Watcher
reconciliation remains the normal completeness mechanism; a future durable dirty
index or platform event-journal proof would be required to strengthen that global
negative guarantee without violating the no-scan constraint.

**Gate B impact:** the published `2.0.0rc1` probes execute FTS and subtree reads, so
their historical evidence cannot qualify these post-RC bytes. Preserve that evidence
as exact-RC history, but run focused watcher-disabled cases and both exact-candidate
Gate B profiles again before stable promotion.

#### EX-05 — Invalidate stale Shadow generations on every sync failure

**Implemented in #386:** every generic incremental or delete failure now latches the
current Shadow generation invalid before propagating to direct callers or being
contained by post-write/watchdog adapters. Reads report `ERROR` and use Markdown/BM25
fallback; the state API exposes the closed content-free reason
`incremental_sync_failed` under `not_ready_reason=sync_error`.

Invalidation has three fail-closed layers. The process-local latch works even when no
cache write is possible. A private `0600` `shadow.sync-invalid` marker in the external
per-graph cache survives process restart and SQLite writer contention. When SQLite is
writable, `last_sync_error` stores the same bounded reason. The marker rejects symlink
targets and contains no graph path, page title, block identifier, content, or raw
exception. Failure to persist either durable channel never clears the runtime latch or
masks the original sync exception.

Focused fault injection covers connection, schema, commit, disk-full-equivalent,
filesystem, post-write callback, and watchdog failures. The committed Markdown write
survives callback failure; the prior generation and generation number remain intact
but ineligible. A successful full rebuild increments the generation, clears metadata,
removes the durable marker, clears the runtime latch, and restores `READY`.

Unrelated successful incremental writes deliberately do not clear a global failure:
only full reconciliation proves that every source page has been reconsidered.

**Gate B impact:** the public RC's controlled recovery probe writes
`last_sync_error` directly; it does not inject these generic incremental branches.
Keep the multi-day RC result bound to the exact published wheel. The stable candidate
must run the focused exact-wheel failure/restart/rebuild matrix, but #386 alone does
not restart the historical RC soak clock.

### P1 — Security, operability, and architectural enforcement

#### EX-06 — Separate query-only cache connections from schema application

**Tranche manifest (frozen 2026-08-07):**

```yaml
tranche_id: EX-06-01
repository: MarcoPorcellato/matryca-plumber
base_commit: 791fbd8b8e1af0c7ff766f82c5ca694618deaaa8
objective: make every pure Shadow SQLite read physically query-only without changing writer ownership
authority: inspect | edit | commit | push | pr
tracking_issue: 413
allowlist:
  - src/shadow/connection.py
  - src/shadow/health.py
  - src/agent/shadow_graph_repository.py
  - src/shadow/fts_format.py
  - src/shadow/state_api.py
  - tests/test_shadow_connection.py
  - tests/test_shadow_hardening_axis6_security.py
  - docs/ARCHITECTURE.md
  - docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
  - CHANGELOG.md
non_goals:
  - change the external cache location, graph read-only policy, schema, or migration rules
  - change FTS, subtree, health, state, or fallback response contracts
  - modify Gate B evidence, services, artifacts, tags, releases, or publication state
deterministic_preflight:
  - uv run pytest --no-cov -q tests/test_shadow_connection.py
  - uv run pytest --no-cov -q tests/test_shadow_state_api.py tests/test_shadow_fts_routing.py tests/test_shadow_read_port.py
  - uv run pytest --no-cov -q tests/test_shadow_hardening_axis6_security.py
  - make ci
acceptance:
  - missing query targets create no cache directory, database, schema, WAL, or SHM
  - every pure reader uses mode=ro with PRAGMA query_only=ON
  - writer/bootstrap/sync schema ownership and existing fallback contracts remain unchanged
stop_conditions:
  - any required schema, cache-location, graph-write-policy, or public response change
rollback: revert the single stacked commit before merge
provenance:
  evidence_commit: 791fbd8b8e1af0c7ff766f82c5ca694618deaaa8
  gitnexus_open_writer_impact: CRITICAL
  gitnexus_health_impact: HIGH
  gitnexus_subtree_impact: LOW
  gitnexus_fts_impact: MEDIUM
```

**Priority:** P2 operational hygiene and defense in depth, not evidence of a graph-write bypass.

**Finding:** `open_shadow_db()` always creates/opens, applies DDL, and commits (`src/shadow/connection.py:34-65`). Health and subtree reads call it. External cache writes are allowed under graph read-only, but a nominal read path is still write-capable.

**Smallest slice:** add a query-only opener (`mode=ro`, `PRAGMA query_only=ON`) for health and read operations; retain the current writer/schema opener for bootstrap and sync. Graph read-only and SQLite filesystem read-only remain distinct policies, and external Shadow writes stay allowed.

Acceptance gate:

- health and subtree queries do not create a missing database, DDL, WAL, or SHM;
- missing/stale/corrupt databases fall back cleanly;
- writer paths retain schema migration behavior.

**Implemented in #413:** the schema-capable opener remains unchanged for bootstrap,
reconciliation, and sync. Health, state telemetry, FTS, and subtree reads now share a
separate opener that requires an existing database through SQLite URI `mode=ro` and
enables `PRAGMA query_only=ON`. The query path does not create the external cache
directory, apply pragmas that change persistent journal state, run DDL, or commit.
Missing and unreadable databases retain the existing stale/error and Markdown/BM25
fallback contracts.

The side-effect boundary is intentionally precise: when no database exists, the query
opener creates no directory, database, WAL, or SHM. For an existing live WAL database,
SQLite may create or reuse `-wal` and `-shm` sidecars to coordinate a current read. The
`immutable=1` URI option is rejected because reconciliation can update this derived
cache concurrently; asserting immutability could serve a stale snapshot. This follows
SQLite's documented [read-only WAL contract](https://www.sqlite.org/wal.html#read_only_databases).

**Validation:** the focused connection primitive suite passes `8/8`; health/state/FTS/
subtree routing and fallback suites pass `49/49`; the Axis-6 security suite passes
`24/24`; strict typing passes for all five changed source modules; and the documentation
bundle reports no drift. The complete macOS arm64 Python 3.12 gate passes with `1,649`
tests, `5` skips, and `83.33%` coverage. Its only warning is the pre-existing macOS
multi-threaded `fork()` deprecation probe. An initial sandboxed run also demonstrated
that the Windows-fallback process-lock test needs `ps`; that exact test passed separately
and the authoritative full gate passed outside the sandbox restriction.

**Gate B impact:** the public `2.0.0rc1` wheel used the schema-capable opener for these
reads, so its exact-artifact soak remains valid historical RC evidence but does not
qualify this post-RC implementation. The stable candidate requires focused exact-wheel
query-only/fallback probes and both candidate Gate B profiles; #413 does not rewrite or
restart the historical RC evidence chain.

#### EX-07 — Stop returning LLM secrets from `/api/config`

**Tranche manifest (frozen 2026-08-07):**

```yaml
tranche_id: EX-07-01
repository: MarcoPorcellato/matryca-plumber
base_commit: 34deb3bc02d82f3675c9e1dd50b61319e20ab9b2
objective: make the UI LLM API key write-only across backend and frontend configuration surfaces
authority: inspect | edit | commit | push | pr
allowlist:
  - src/cli/ui_server.py
  - tests/test_ui_server.py
  - frontend/src/types/daemon.ts
  - frontend/src/hooks/usePlumberPolling.ts
  - frontend/src/components/SettingsDrawer.tsx
  - frontend/src/components/MasterHeader.tsx
  - frontend/src/utils/plumberConfigDefaults.ts
  - frontend/src/utils/plumberConfigSecrets.ts
  - frontend/src/utils/plumberConfigSecrets.test.ts
  - docs/ARCHITECTURE.md
  - docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
  - CHANGELOG.md
non_goals:
  - change UI authentication, inference-provider behavior, or unrelated configuration fields
  - serialize dotenv writers or implement optimistic concurrency reserved for EX-08
  - modify Gate B evidence, release artifacts, tags, releases, or publication state
deterministic_preflight:
  - uv run pytest --no-cov -q tests/test_ui_server.py
  - npm run test -- src/utils/plumberConfigSecrets.test.ts
  - npm run build
  - npm run lint
acceptance:
  - GET and POST responses never serialize the configured key
  - omission preserves, a supplied string replaces, and explicit null clears the key
  - legacy readback is removed before any configuration payload reaches React state
  - frontend errors and operational logs never include the configured key
stop_conditions:
  - any required change to authentication, another secret, or dotenv concurrency
rollback: revert the single stacked commit before merge
provenance:
  evidence_commit: 34deb3bc02d82f3675c9e1dd50b61319e20ab9b2
  evidence_paths:
    - src/cli/ui_server.py
    - frontend/src/hooks/usePlumberPolling.ts
    - frontend/src/components/SettingsDrawer.tsx
documentation_impact: update
official_okf_conformance_impact: none
matryca_quality_impact: lifecycle | provenance
residual_risks:
  - a newly entered replacement exists transiently in the password control and request until submission settles
  - dotenv lost-update protection remains owned by EX-08
```

**Verified secret readback:** `PlumberConfigResponse` contains `llm_api_key` and the GET route returns the live model (`src/cli/ui_server.py:180-228`, `src/cli/ui_server.py:855-876`). Authentication reduces exposure but does not justify echoing a secret to browser state. This is a design-level exposure, not evidence that credentials have been compromised.

**Smallest slice:** return `llm_api_key_configured: bool`; accept key changes through a write-only nullable field and never echo the value.

Acceptance gate:

- serialized GET responses, frontend state, exception paths, and logs contain no configured key;
- update, preserve-without-resending, and explicit clear all work;
- frontend contract tests cover the new shape.

**Implemented in #390:** read and write schemas are now separate. `GET /api/config`
and every config response expose only `llm_api_key_configured`; `POST /api/config`
accepts an optional write-only `llm_api_key`, preserving it when omitted, replacing it
when supplied, and clearing it only when explicitly `null`. Response-model filtering
and frontend sanitization independently prevent legacy secret readback from entering
React configuration state.

The settings drawer keeps the password control empty, reports only configured/not
configured status, offers an explicit clear action, and removes a replacement from
component state after submission. Focused API tests assert that response bodies and
error details do not contain configured values, while frontend contract tests cover
legacy-response sanitization and all three write operations. Authentication, provider
behavior, dotenv concurrency, Gate B evidence, and release state remain unchanged.

Candidate validation passed 64 focused Python API/security tests and all 20 frontend
tests, plus the frontend TypeScript build and lint gates. The complete `make ci` gate
also passed (format, Ruff, strict mypy over 377 files, graph sandbox, version and agent
coherence, public-metrics policy, documentation inventory, generated prompt, and the
full parallel Python suite). The suite retained one pre-existing macOS `fork()`
deprecation warning in `test_fork_child_clears_flock_depth_state`; this tranche adds no
new warning.

#### EX-08 — Serialize `.env` read/merge/write updates

**Tranche manifest (frozen 2026-08-07):**

```yaml
tranche_id: EX-08-01
repository: MarcoPorcellato/matryca-plumber
base_commit: d05522e58072f7c85f329f70804e672b58183df4
objective: prevent lost and externally overwritten dotenv updates from concurrent UI routes
authority: inspect | edit | commit | push | pr
allowlist:
  - src/cli/ui_server.py
  - tests/test_ui_server.py
  - docs/ARCHITECTURE.md
  - docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
  - CHANGELOG.md
non_goals:
  - broaden the configuration schema or alter unrelated settings behavior
  - claim a portable filesystem compare-and-swap primitive that Python does not provide
  - modify Gate B evidence, services, artifacts, tags, releases, or publication state
deterministic_preflight:
  - uv run pytest --no-cov -q tests/test_ui_server.py -k "dotenv or post_config or post_graph_path"
  - uv run ruff check src/cli/ui_server.py tests/test_ui_server.py
  - uv run mypy --strict src/cli/ui_server.py tests/test_ui_server.py
acceptance:
  - concurrent cooperating writers serialize and preserve disjoint changes
  - device, inode, nanosecond mtime, size, and content hash bind each source snapshot
  - an intervening external edit returns HTTP 409 with code dotenv_conflict
  - comments, ordering, unknown keys, and crash-safe atomic replacement survive
stop_conditions:
  - cross-process mandatory locking or a platform-specific filesystem CAS becomes required
rollback: revert the single stacked commit before merge
provenance:
  evidence_commit: d05522e58072f7c85f329f70804e672b58183df4
  evidence_paths:
    - src/cli/ui_server.py
    - tests/test_ui_server.py
documentation_impact: update
official_okf_conformance_impact: none
matryca_quality_impact: lifecycle | provenance | safety
residual_risks:
  - an uncooperating writer can still race in the irreducible interval between the final identity check and os.replace
```

**Finding:** at the frozen base, config routes run in worker threads and `_apply_dotenv_updates` performs read-merge-atomic-replace without a shared lock or OCC version. Concurrent full-config and graph-path updates can lose disjoint changes.

**Smallest slice:** use a lock for cooperating writers and source-identity OCC for uncooperating/external writers; define the identity contract (for example mtime/size plus content hash) and return a conflict instead of overwriting an intervening edit.

Acceptance gate:

- concurrent disjoint updates preserve both changes;
- an external edit yields a typed conflict;
- comments, ordering, and unknown keys survive;
- a failed atomic replacement leaves the source intact and removes its temporary file.

**Implemented for #387:** a process-wide lock now owns the complete dotenv
read/merge/write transaction for both UI configuration routes. The source snapshot is
bound to existence, device, inode, nanosecond mtime, size, and SHA-256. After the
candidate temporary file is flushed and synchronized, the writer captures that identity
again immediately before `os.replace`; a mismatch raises a private typed conflict that
both routes map to HTTP 409 with the stable, content-free code `dotenv_conflict`.
Process-environment mutation and dotenv reload occur only after replacement commits.

Deterministic concurrency coverage holds the first writer inside the snapshot boundary,
proves a second worker has started but cannot enter it, and then verifies that both
disjoint updates survive. External replacement, creation, and deletion are injected
before commit and all preserve the external result. Additional regressions retain
comments, established ordering, unknown keys, API conflict shape, original source
content on `os.replace` failure, and temporary-file cleanup.

Candidate validation passed 13 focused dotenv/config tests, all 56 UI and dotenv
serialization tests, focused Ruff and strict mypy, and the documentation bundle gate.
The complete `make ci` gate passed with 1,647 tests, 5 skips, 83.34% coverage, format,
Ruff, strict mypy over 377 source files, graph sandbox, version and agent coherence,
public-metrics policy, documentation inventory, and generated prompt checks. The suite
retained the pre-existing macOS `fork()` deprecation warning. An earlier restricted run
was blocked only when macOS process inspection was denied; the exact test and the full
gate both passed when run with standard process-inspection access. A later exact-tree
parallel repetition recorded one unrelated 30-second MCP handshake timeout after 1,646
passes; the isolated handshake then passed in 1.05 seconds, so no unrelated runtime
change was introduced.

#### EX-09 — Close first-run token ordering

**Tranche manifest (frozen 2026-08-07):**

```yaml
tranche_id: EX-09-01
repository: MarcoPorcellato/matryca-plumber
base_commit: bac65e6820002ffda65fd3fbbeb5e20ac7b6d36f
objective: enforce materialized UI token defaults before every network-bind decision
authority: inspect | edit | commit | push | pr
allowlist:
  - src/cli/ui_server.py::run_ui_server
  - tests/test_ui_server.py
  - CHANGELOG.md
  - docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
non_goals:
  - change token generation, LAN policy, API response shapes, or dotenv write concurrency
  - modify Gate B evidence, release artifacts, tags, releases, or publication state
deterministic_preflight:
  - uv run pytest --no-cov -q tests/test_ui_server.py tests/test_ui_explicit_token.py tests/test_ui_auth_lan.py tests/test_runtime_bootstrap.py
acceptance:
  - clean and existing dotenv states enforce explicit-token defaults before Uvicorn bind
  - loopback bootstrap and explicit LAN protection remain unchanged
  - failure remains typed and secret-free
stop_conditions:
  - any required change outside the composition-root allowlist or existing auth contract
rollback: revert the single stacked commit before merge
provenance:
  evidence_commit: bac65e6820002ffda65fd3fbbeb5e20ac7b6d36f
  evidence_paths:
    - src/cli/ui_server.py
    - src/cli/ui_auth.py
    - src/utils/runtime_bootstrap.py
documentation_impact: update
official_okf_conformance_impact: none
matryca_quality_impact: lifecycle | provenance
residual_risks:
  - startup policy remains process-environment driven after deterministic dotenv loading
```

**Implemented in #395:** `run_ui_server()` now materializes `.env` from the safe
template when needed and reloads it before evaluating either LAN binding or explicit
token policy. The same sequence applies when `.env` already exists, so startup no
longer depends on installation history. Policy failure remains a typed, secret-free
`ValueError` and occurs before browser scheduling, frontend preparation, or
`uvicorn.run()`.

Parameterized composition-root tests use isolated temporary repositories to exercise
both clean and existing dotenv states with the real copy-and-reload helpers. The
template's explicit-token requirement refuses both before bind, while the established
loopback bootstrap and explicit LAN tests remain green. No token generation, LAN
policy, endpoint shape, dotenv writer, or Gate B behavior changes in this tranche.

#### EX-10 — Replace string-based architecture tests with AST enforcement

**Tranche manifest (frozen 2026-08-07):**

```yaml
tranche_id: EX-10-01
repository: MarcoPorcellato/matryca-plumber
base_commit: 44fab70d358ecc6f5f40cdf33619a57d5b32ac91
objective: replace broad graph-layer string/file exemptions with exact AST-enforced import boundaries
authority: inspect | edit | commit | push | pr
tracking_issue: 394
allowlist:
  - tests/test_graph_layer_boundary.py
  - docs/quality/REPOSITORY_EXCELLENCE_STUDY_2026-08-06.md
non_goals:
  - move the CRITICAL shared tokenizer or prompt compiler in this tranche
  - change runtime imports, behavior, Gate B evidence, releases, tags, or publication state
deterministic_preflight:
  - uv run pytest --no-cov -q tests/test_graph_layer_boundary.py
  - make ci
acceptance:
  - absolute imports and every relative depth resolve through the Python AST
  - comments and strings cannot trigger false positives
  - exceptions identify the exact path, module, imported names, issue, and expiry criterion
  - stale exceptions fail the gate when their production import disappears
stop_conditions:
  - any production symbol move or new exception without an issue-bound expiry criterion
rollback: revert the single stacked commit before merge
provenance:
  evidence_commit: 44fab70d358ecc6f5f40cdf33619a57d5b32ac91
  tokenizer_impact: CRITICAL
  boundary_test_impacts: LOW
documentation_impact: update
official_okf_conformance_impact: none
matryca_quality_impact: lifecycle | provenance
residual_risks:
  - two exact production imports remain until later #394 tranches prove safe extraction
```

**EX-10-01 implemented:** the boundary gate now parses every Python import with the
standard-library AST, resolves absolute imports and arbitrary relative depth against the
source package, and ignores import-shaped text in comments and strings. The previous
whole-file exemptions are replaced by two exact records that bind path, resolved module,
imported names, issue #394, and a concrete expiry criterion. The gate fails both on any
new graph-to-agent/daemon/rag import and when a recorded exception becomes stale.

Focused validation passes `2/2`. The complete macOS arm64 Python 3.12 gate passes with
`1,648` tests, `5` skips, and `83.33%` coverage; format, Ruff, strict mypy over 377 source
files, graph sandbox, version and agent coherence, public-metrics policy, documentation
inventory, and generated prompt checks are all green. The only warning remains the
pre-existing macOS multi-threaded `fork()` deprecation probe. No changelog entry is
required because this tranche changes test enforcement and its evidence record only.

**Finding:** the current graph boundary test misses deeper relative imports and exempts an entire production file (`tests/test_graph_layer_boundary.py:8-44`). The live violations are visible at `src/graph/insights/prompts.py:8` and `src/graph/generational_cache.py:225-255`.

**Smallest slice:** first reconcile the absolute `graph`-must-not-import-`agent` rule with the documented Tier-1 prompt-core exception. Then parse imports with the standard-library AST, extract tokenization and prompt compilation behind domain-owned helpers/protocols where appropriate, and remove broad exemptions.

Acceptance gate:

- absolute and every relative-import depth are recognized;
- `src/graph/` has no imports from `agent`, `daemon`, or `rag` except narrowly documented permanent contract exceptions or temporary allowlist entries with issue IDs and expiry criteria;
- isolated module imports and full CI pass.

Non-goal: no repository-wide hexagonal rewrite.

### P2 — Scale and resilience after observability

#### EX-11 — Add operational diagnostics before concurrency refactors

Expose content-free metrics for:

- Shadow sync duration, writer-lock wait, generation, fallback reason, last successful incremental sync, parser timeout count, quarantine age and retry count;
- watcher pending count, overflow/coalescing count, oldest-event age, and convergence latency;
- BM25 hit/miss/invalidation/eviction counts, scoring latency, corpus size, query-cache rows, and current per-corpus memory estimate;
- daemon checkpoint recovery source and explicit state-reset events.

Acceptance gate: bounded-cardinality metrics, no graph content or local paths, deterministic tests, and zero behavior change when diagnostics are not consumed.

#### EX-12 — Benchmark and then narrow the generational-cache locks

**Finding:** `_lock` covers corpus scans, file reads, tokenization, cache patching, and publication (`src/graph/generational_cache.py:180-255`, `src/graph/generational_cache.py:396-417`). This can cause cross-graph head-of-line blocking. Query scoring has a per-corpus lock, which protects correctness but serializes same-corpus requests.

**Preferred design:** build immutable snapshots outside the global lock, publish with a short compare-and-swap-style critical section, and use per-graph build locks to suppress duplicate work.

Acceptance gate:

- output parity with the current implementation;
- no duplicate publication under concurrent cold starts;
- multi-graph p95/p99 latency improves without RSS or correctness regression;
- impact analysis is refreshed before implementation because this function has many production callers.

#### EX-13 — Keep BM25 at 8,192 until representative evidence says otherwise

The current limits are explicit and bounded: 8,192 entries and 65,536 result rows (`src/graph/generational_cache.py:29-39`). They should remain the product default. The next improvement is not another capacity increase but measurement of real query distributions, row pressure, multi-corpus memory, and invalidation churn.

Acceptance gate: complete the benchmark matrix below and record the decision. Any future limit change must demonstrate better hit rate and tail latency under a declared memory envelope.

#### EX-14 — Bound watcher and daemon state growth

**Findings:** watcher pending state has no explicit cardinality/backpressure policy (`src/daemon/file_watcher.py:78-126`). The daemon serializes the complete per-file state mapping while reads are bounded at 64 MB (`src/agent/daemon_state.py`, `src/utils/bounded_json.py:10-45`).

**Smallest slices:**

1. cap pending paths and coalesce overflow into one bounded rescan;
2. define a checkpoint size/cardinality envelope, deterministic compaction, and an explicit recovery/reset diagnostic.

Acceptance gate: 10,000-path event storms, near/over-cap checkpoints, restart recovery, bounded memory, and no silent dropped convergence.

#### EX-15 — Split large modules by behavior seams, not line count

Largest current modules include:

- `src/agent/maintenance_daemon.py`: 1,325 lines;
- `src/cli/ui_server.py`: 1,183 lines;
- `src/agent/llm_client.py`: 1,119 lines.

Existing issues #212–#214 already track these modules. Extract only stable seams with characterization tests—for example daemon lifecycle/state/phase orchestration, UI config/auth/control routes, and LLM transport/retry/repair—not a cosmetic file split.

Acceptance gate: unchanged public contracts, reduced dependency fan-in, focused module tests, and no new compatibility facade without an expiry plan.

### P3 — Documentation, CI depth, and repository governance

#### EX-16 — Create one v2 operator source of truth

Mutable Shadow/read-only/release behavior currently appears in README, CHANGELOG, roadmaps, architecture docs, release process, and evidence reports. Keep each surface, but give it one role:

| Surface | Authority |
| --- | --- |
| `README.md` | stable product overview and one link to operator documentation |
| `docs/knowledge/architecture/shadow-db.md` | maintained runtime architecture and operator contract |
| `docs/RELEASE_PROCESS.md` | release mechanics and authority gates |
| `CHANGELOG.md` | user-visible version deltas |
| `docs/roadmaps/*` | future work only |
| `docs/quality/*` | immutable or timestamped evidence and decisions |
| `docs/releases/*` | historical publication text |

Acceptance gate: each mutable claim has one canonical home; other surfaces link
rather than restate it; maintained concepts expose lifecycle, owner, authority,
verification date, and provenance; archived evidence remains unchanged. The
authoritative source is changed in Matryca Plumber first, and any Matryca
Knowledge refresh is a separate reviewed projection.

#### EX-17 — Make dual-layer documentation checks mandatory

`docs-check` currently passes but is not part of `make ci`. Add it to the
mandatory gate. Add a repository-aware internal-link checker that understands
relative paths, directory indexes, anchors, generated files, and an explicit
external-link policy.

Evolve validation in separately reviewable slices:

1. preserve the existing transitional Matryca quality gate;
2. add an official OKF v0.2 parser that accepts unknown types and extension
   fields and supports the reserved-file and lifecycle contract;
3. report official conformance and Matryca quality as separate top-level
   results;
4. version the specification baseline, Matryca profile, validator, and finding
   schema independently;
5. refresh only documents invalidated by changed bytes or policy versions.

Acceptance gate: zero false positives on the current baseline; broken
path/anchor and lifecycle fixtures fail the Matryca quality layer; official
format fixtures fail only the official layer; generated inventory drift fails
CI; identical source bytes and policy versions produce byte-identical results;
no LLM output participates in acceptance.

#### EX-18 — Expand CI where it buys independent evidence

Recommended order:

1. run frontend tests in CI, not only build/lint;
2. add Python 3.13 alongside 3.12 for the declared support contract;
3. keep focused macOS/Windows Shadow contract lanes on every PR;
4. run fuller cross-platform suites on a scheduled cadence before making all OSes mandatory for every PR;
5. add scheduled performance and mutation/property-test jobs for bounded allowlisted modules.

This is more cost-effective than immediately tripling every PR's full CI workload.

#### EX-19 — Reconcile the issue and milestone control plane

There are 49 open issues and 29 without milestones. Run a read-only duplicate/obsolescence audit, then classify every issue into:

- v2.0 release-blocking;
- v2.0 follow-up;
- v2.1 architecture/product;
- quality/tech-debt;
- contributor-ready;
- close with shipped evidence;
- superseded/duplicate.

Existing anchors include #17, #20, #25, #47–#49, #54, #63, #73, #178, #186, #204, #208, #212–#214, #219, #240, #271, #333, #334, #343, #346, and #351.

Acceptance gate: every actionable issue has one milestone, priority, dependencies, and acceptance criteria; no issue is closed without source/test evidence.

## Cross-cutting acceptance gates

These gates apply to every accepted slice in addition to its focused tests:

1. **Exact release identity:** any Gate B or post-Gate-B conclusion names the source commit, wheel hash, installed `RECORD`, and configuration profile. Source-tree CI is not exact-artifact qualification.
2. **Read-only manifest invariant:** immutability tests snapshot files, directories, symlinks, and relevant metadata—not only file contents.
3. **Fallback observability:** Shadow fallback has a bounded, content-free reason and a tested health transition.
4. **Failure-injection depth:** generic SQLite open/schema/commit, disk-full-equivalent, filesystem, and callback failures are distinct from parse-error tests.
5. **No security overclaim:** secret readback and startup-order findings are design-level defects; no remote exploit or credential compromise is claimed without evidence.
6. **Requalification rule:** a change to any Gate B runtime path or profile invalidates only the affected qualification evidence according to an explicit impact decision; credited evidence is never silently reused.
7. **Documentation authority:** Plumber bytes remain authoritative; registry
   projection bytes are never edited as their source.
8. **Conformance separation:** official OKF v0.2 and Matryca quality have
   independent versioned results; zero Matryca findings never implies official
   conformance.
9. **Provenance and freshness:** maintained documentation evidence records the
   source repository, exact commit, source path, policy version, and
   verification date.

## Tranche execution contract

Before any roadmap slice moves from planning to implementation, its issue or
working record must freeze the following manifest. Empty or inferred fields are
not sufficient authorization.

```yaml
tranche_id: EX-<number>-<sequence>
repository: MarcoPorcellato/matryca-plumber
base_commit: <exact-sha>
objective: <one-observable-outcome>
authority: inspect | edit | commit | push | pr
allowlist:
  - <path-or-symbol>
non_goals:
  - <explicit-exclusion>
deterministic_preflight:
  - <command>
acceptance:
  - <observable-check>
stop_conditions:
  - <scope-or-safety-boundary>
rollback: <reversible-path>
provenance:
  evidence_commit: <sha>
  evidence_paths:
    - <path>
documentation_impact: none | update | migrate
official_okf_conformance_impact: none | parser | profile | report
matryca_quality_impact: none | metadata | navigation | lifecycle | provenance
residual_risks:
  - <known-limit>
```

Authority is cumulative only when explicitly granted. `inspect` does not
authorize edits; `edit` does not authorize a commit; a local commit does not
authorize push or pull-request creation; and a pull request does not authorize
merge, release, publication, or repository-setting changes.

Completion evidence must include the changed-file allowlist, commands and
results, rollback status, documentation impact, residual risks, and the exact
accepted commit when one exists. A model-generated proposal may support the
work but is never acceptance evidence.

## Benchmark matrix

| Dimension | Required cases | Primary metrics |
| --- | --- | --- |
| Shadow cold build | 1k, 10k, 50k pages; shallow, deep, malformed/pathological | wall time, page p50/p95/p99, lock hold, current/peak RSS, indexed/quarantined counts |
| Shadow incremental | 1, 100, 1k edits/deletes/renames | convergence, transaction time, lock wait, generation, FTS/subtree parity |
| Shadow routing | ready, stale, absent, corrupt, disabled, generic sync failure | read p50/p95/p99, fallback reason/rate, cache files created, graph manifest |
| Read-only external cache | cold/warm cache, unavailable path, symlink, disk-full simulation | graph immutability, startup time, fallback, diagnostics, recovery |
| BM25 capacities | 512, 2,048, 8,192, 16,384 for evidence only | hit ratio, p50/p95/p99, current RSS, row-budget evictions, build cost |
| BM25 query distribution | hot 80/20, Zipf, uniform, duplicate tokens, empty/negative, limits 1/8/32/100 | scoring time, cache reuse, result parity, entries and row pressure |
| BM25 mutation storm | 1, 10, 100 edits during reads; one and multiple corpora | invalidation rate, lock wait, rebuild/patch cost, tail latency |
| Multi-graph concurrency | 2, 4, 8, 16 concurrent graphs | throughput, fairness, cross-graph blocking, per-corpus RSS |
| Watcher burst | 40, 1k, 10k clustered/scattered changes | pending depth, coalescing, oldest age, convergence, RSS |
| Daemon recovery | clean restart, SIGTERM during write, corrupt primary/backup, physical reboot | continuity, explicit reset event, restart duration, lost work, heartbeat gap |
| Exact-artifact soak | both required profiles, public wheel, representative sanitized corpus, 72h+ credited time | terminal state, chain integrity, RSS/latency/quarantine trends, artifact hashes |

Rules for benchmark credibility:

- publish machine, OS, Python, corpus generator/manifest, seed, warm-up, repetitions, and confidence interval;
- separate synthetic microbenchmarks, sanitized representative corpora, and exact public-artifact qualification;
- measure current RSS as well as high-water RSS;
- preserve correctness/parity assertions in every performance run;
- store raw machine-readable results and a short decision summary;
- reject any optimization that improves mean latency while materially worsening p99, memory, fallback correctness, or graph immutability.

## Sequenced roadmap

### Phase 0 — While Gate B is running

Low runtime risk, no release-line disturbance:

1. Keep monitoring Gate B without crediting downtime.
2. Reconcile documentation lifecycle language and establish the EX-16 authority matrix.
3. Execute EX-17 incrementally: first add the existing `docs-check` to CI,
   then introduce separately reported official OKF v0.2 and Matryca quality
   gates without a mass migration.
4. Triage milestones and map existing issues to this dossier.
5. Establish benchmark result schemas and capture a baseline without changing implementation.

### Phase 1 — After Gate B reaches terminal state, before the stable decision

Disposition and, where required, small safety/correctness PRs in this order:

1. EX-02 read-only bootstrap ordering.
2. EX-03 X-Ray contract.
3. EX-04 Shadow freshness.
4. EX-05 generic failure invalidation.
5. EX-06 query-only Shadow opener.
6. EX-07 to EX-09 UI config secrecy, concurrency, and first-run ordering.

Each is a separate issue/PR with focused tests and changelog decision. Do not combine them into a broad hardening PR. EX-02–EX-05 must be explicitly dispositioned before stable authorization; any fix that changes an affected Gate B profile requires declared requalification before publication.

### Phase 2 — Observability and bounded resilience

1. EX-11 operational metrics.
2. EX-14 watcher backpressure and checkpoint bounds.
3. Explicit quarantine rehabilitation/backoff and age diagnostics.
4. Scheduled benchmark and long-running resilience jobs.

### Phase 3 — Measured performance architecture

1. Run the complete BM25/Shadow/multi-graph matrix.
2. Narrow global locks using immutable snapshots and per-graph builders.
3. Replace full index replacement with page-level deltas or bounded batches where evidence supports it.
4. Re-run correctness, p99, memory, and edit-storm gates.

### Phase 4 — Maintainability and contributor excellence

1. AST-enforced boundaries and import-cycle slices.
2. Behavior-seam splits for the three largest modules.
3. Property tests for parsers, path normalization, and state machines.
4. Bounded mutation testing for safety-critical pure functions.
5. Complete the knowledge-bundle observation window and only then migrate/archive documentation paths.

### Phase 5 — v2.1 product evolution

Only after v2.0 stabilization:

- biological memory and recall;
- Logseq DB Safe-Sync write bridge;
- content-aware imports;
- context-aware MCP tool filtering;
- hardware-aware local model guidance.

These must not retroactively broaden the v2.0 stable-read-path claim.

## Ideas explicitly rejected

- **A repository-wide Clean Architecture rewrite.** It would increase release risk and obscure the small proven boundary defects.
- **Increasing BM25 above 8,192 by intuition.** The existing cap is generous and bounded; current evidence does not prove that a larger default improves real users within a known memory envelope.
- **Treating external-cache writes as incompatible with read-only.** Read-only protects the user graph; derived external Shadow state is an intentional and useful separate policy domain.
- **Making cache failures abort authoritative Markdown writes.** Shadow must remain disposable and fail back to Markdown.
- **Defining `READY` as aggregate database health only.** It must include freshness evidence or be renamed to a narrower structural-health state.
- **Using a global lock as the sole `.env` concurrency fix.** It cannot detect uncooperating external writers; OCC is also required.
- **Running the entire test suite on every OS for every PR immediately.** Targeted per-PR contracts plus scheduled full cross-platform runs provide better cost/evidence balance first.
- **Mass-moving documentation now.** The knowledge bundle is intentionally in an observation phase; authority labels and links are safer than path churn.
- **Treating the Matryca Knowledge projection as an editing origin.** Source
  repositories own imported documents; registry updates are reviewed
  projections bound to immutable source commits.
- **Calling a zero-finding Matryca quality report official OKF conformance.**
  The external format contract and the stricter internal quality profile are
  independent claims with independent versions and evidence.
- **Using a green CI run as performance or release proof.** CI, benchmarks, soak qualification, and release authorization are independent gates.
- **Combining v2.1 Safe-Sync with v2.0 stabilization.** It would change the product and risk profile during qualification.

## Issue-ready implementation template

Every accepted slice should be converted into one English issue with:

1. `## Problem Description`
2. `## Proposed Architectural Solution`
3. `## Estimated Impact`
4. `## Files Involved`
5. verified current behavior and reproduction;
6. exact scope and explicit non-goals;
7. impact/blast-radius evidence refreshed on the current branch;
8. deterministic unit, integration, concurrency, and immutability tests as applicable;
9. benchmark or observability acceptance threshold where applicable;
10. changelog decision;
11. dependency links and milestone;
12. the frozen tranche manifest: base commit, authority, allowlist, preflight,
    acceptance, stop conditions, rollback, provenance, documentation impact,
    conformance impact, and residual risks;
13. Definition of Done requiring `make ci`, the focused domain gates, and any
    affected documentation-quality layer.

## North-star repository scorecard

| Dimension | Current position | Stellar target |
| --- | --- | --- |
| Correctness | strong CI and fallback architecture | freshness and failure states are explicit and fail closed |
| Graph safety | central policy and atomic writes | zero graph mutation in every read-only startup/read surface |
| Performance | bounded caches and synthetic tests | representative p99/RSS/convergence baselines and regression budgets |
| Resilience | durable checkpoint and soak machinery | explicit degraded/recovery states under reboot, corruption, and storms |
| Architecture | documented inward rule | AST-enforced dependency direction with no unexplained exemptions |
| Security | path containment and UI auth | no secret readback, order-independent startup policy, serialized config |
| Documentation | rich inventory and evidence | one-click authority map with no mutable narrative duplication |
| CI | strict Linux gate plus focused cross-platform tests | declared Python matrix, frontend tests, scheduled deep gates |
| Governance | rich issue history | every actionable issue prioritized, milestoned, deduplicated, and testable |
| Release control | exact-artifact gates exist | qualification evidence, publication, and authorization remain independently auditable |

## Final recommendation

The repository should not chase more surface area immediately. Its most valuable next step is to turn the existing engineering strength into explicit contracts:

- `READY` means fresh;
- `read-only` means no graph mutation from startup or read APIs;
- a cache failure is observable and always falls back;
- performance claims include p99, current memory, realistic distributions, and exact artifacts;
- every document and issue has one authority role;
- every major change is small enough to verify and reverse.

If these slices are executed in the proposed order, Matryca Plumber can improve materially without destabilizing the v2.0 release line or accumulating another layer of speculative architecture.
