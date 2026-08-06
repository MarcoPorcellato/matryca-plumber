# Matryca Plumber repository excellence study

**Date:** 2026-08-06

**Baseline:** `origin/main@1e8805ec99c6471549ecf36e4a261a31013a0f6f`

**Status:** evidence-backed plan; no release authorization and no production implementation

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

**Verified gap; plausible stale-read risk:** `resolve_shadow_health()` validates schema, sync-error metadata, completion, and aggregate counts but not current source mtimes (`src/shadow/health.py:68-106`). Shadow rows store `file_mtime_ns`, but subtree reads do not compare it before serving (`src/agent/shadow_graph_repository.py:110-153`). A page changed while the watcher is stopped or after a missed event can remain eligible for `READY` reads despite source changes that were not reconciled. This study did not observe that outcome in production.

**Smallest slice:** validate freshness for the requested page or maintain a bounded dirty/freshness index; if freshness cannot be proved, use Markdown.

Acceptance gate:

- edit, delete, and rename a page after a healthy rebuild with the watcher disabled, with explicit authoritative expected results for every case;
- every read returns current Markdown or an explicit stale/fallback result;
- healthy warm Shadow latency remains within an agreed regression budget.

Non-goal: do not scan the full graph on every read.

#### EX-05 — Invalidate stale Shadow generations on every sync failure

**Verified failure-handling gap; outcome hypothesis:** generic incremental failures roll back and propagate, but the post-write bridge catches and logs them (`src/shadow/sync.py:291-335`). Only selected parse failures persist error metadata. Some generic failures may leave old rows eligible for `READY`; others will make the next open/health operation return `ERROR`. Fault injection must establish the exact transition for each class.

**Smallest slice:** persist a content-free invalid-generation/sync-error marker after any failed transaction; route reads to Markdown until successful reconciliation clears it.

Acceptance gate:

- inject generic connection, schema, commit, disk-full-equivalent, filesystem, callback, and watchdog failures;
- authoritative Markdown writes still succeed;
- every class either already becomes non-`READY` or is made explicitly non-`READY`, with a bounded content-free reason;
- successful reconciliation clears the marker with defined generation semantics and restores `READY`.

Non-goal: do not make cache failure fail the authoritative write.

### P1 — Security, operability, and architectural enforcement

#### EX-06 — Separate query-only cache connections from schema application

**Priority:** P2 operational hygiene and defense in depth, not evidence of a graph-write bypass.

**Finding:** `open_shadow_db()` always creates/opens, applies DDL, and commits (`src/shadow/connection.py:34-65`). Health and subtree reads call it. External cache writes are allowed under graph read-only, but a nominal read path is still write-capable.

**Smallest slice:** add a query-only opener (`mode=ro`, `PRAGMA query_only=ON`) for health and read operations; retain the current writer/schema opener for bootstrap and sync. Graph read-only and SQLite filesystem read-only remain distinct policies, and external Shadow writes stay allowed.

Acceptance gate:

- health and subtree queries do not create a missing database, DDL, WAL, or SHM;
- missing/stale/corrupt databases fall back cleanly;
- writer paths retain schema migration behavior.

#### EX-07 — Stop returning LLM secrets from `/api/config`

**Verified secret readback:** `PlumberConfigResponse` contains `llm_api_key` and the GET route returns the live model (`src/cli/ui_server.py:180-228`, `src/cli/ui_server.py:855-876`). Authentication reduces exposure but does not justify echoing a secret to browser state. This is a design-level exposure, not evidence that credentials have been compromised.

**Smallest slice:** return `llm_api_key_configured: bool`; accept key changes through a write-only nullable field and never echo the value.

Acceptance gate:

- serialized GET responses, frontend state, exception paths, and logs contain no configured key;
- update, preserve-without-resending, and explicit clear all work;
- frontend contract tests cover the new shape.

#### EX-08 — Serialize `.env` read/merge/write updates

**Finding:** config routes run in worker threads and use read-merge-atomic-replace without a shared lock or OCC version (`src/cli/ui_server.py:542-576`, `src/cli/ui_server.py:902-918`). Concurrent full-config and graph-path updates can lose disjoint changes.

**Smallest slice:** use a lock for cooperating writers and source-identity OCC for uncooperating/external writers; define the identity contract (for example mtime/size plus content hash) and return a conflict instead of overwriting an intervening edit.

Acceptance gate:

- concurrent disjoint updates preserve both changes;
- an external edit yields a typed conflict;
- comments and unknown keys survive.

#### EX-09 — Close first-run token ordering

**Verified first-run policy-order defect:** token policy is checked before the UI lifespan may create `.env` from `.env.example` (`src/cli/ui_server.py:649-655`, `src/cli/ui_server.py:1126-1140`). On a clean first run, example defaults can therefore be applied after enforcement. This is not evidence of a remote authentication bypass; LAN binding still has a separate explicit-token requirement.

**Smallest slice:** materialize/load defaults before token policy evaluation and before binding.

Acceptance gate:

- clean first run with explicit-token-required defaults refuses startup before Uvicorn binds;
- loopback bootstrap and explicit LAN protection remain intact.

#### EX-10 — Replace string-based architecture tests with AST enforcement

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
| `docs/knowledge/architecture/shadow-db.md` | current runtime architecture and operator contract |
| `docs/RELEASE_PROCESS.md` | release mechanics and authority gates |
| `CHANGELOG.md` | user-visible version deltas |
| `docs/roadmaps/*` | future work only |
| `docs/quality/*` | immutable or timestamped evidence and decisions |
| `docs/releases/*` | historical publication text |

Acceptance gate: each mutable claim has one canonical home; other surfaces link rather than restate it; archived evidence remains unchanged.

#### EX-17 — Make docs checks mandatory and add a calibrated link checker

`docs-check` currently passes but is not part of `make ci`. Add it to the mandatory gate. Add a repository-aware internal-link checker that understands relative paths, directory indexes, anchors, generated files, and an explicit external-link policy.

Acceptance gate: zero false positives on the current baseline; broken path/anchor fixtures fail; generated inventory drift fails CI.

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
2. Reconcile documentation status language and establish the EX-16 authority matrix.
3. Execute EX-17 once: add `docs-check` to CI and calibrate link validation.
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
12. Definition of Done requiring `make ci` and the focused domain gates.

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
