---
type: Specification
title: Graph-native derived projection qualification design
description: Architecture and evidence gates for preserving SQLite as the stable Shadow backend while qualifying LadybugDB as an optional graph-native derived projection.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: shadow-runtime
last_verified: 2026-08-22
stale_after: 2027-02-18
---

# Graph-native derived projection qualification design

## Executive decision

Matryca Plumber will evolve the stable v2.0 Shadow read architecture into a
backend-neutral projection architecture without changing canonical authority or
stable defaults.

- Logseq Markdown and governed evidence remain canonical, user-owned state.
- SQLite remains the stable, default, supported Shadow backend.
- LadybugDB enters only as an optional, experimental graph-native projection.
- The first Ladybug slice is an offline, single-process qualification adapter,
  not a live runtime route.
- Promotion requires predeclared semantic, safety, concurrency, recovery,
  packaging, quality, and performance gates.
- The database choice remains outside the normative agent-memory contract.

This design deliberately rejects a direct SQLite-to-Ladybug migration and a
single fat `MemoryProjectionBackend` interface.

## Verified starting point

The public design baseline is `main@505cfb0da805fce2dc2a7497b911846d857bbd39`.
The stable product baseline remains `v2.0.0@987446b8337f7abd308a9efe4abb834ce1acdc1b`.

The current implementation has these properties:

- `src/shadow/connection.py` owns SQLite connection creation and query-only
  opening.
- `src/shadow/schema.py` owns FTS5 tables, triggers, read-cache DDL, and
  schema-only future memory tables.
- `src/shadow/sync.py` parses one Markdown page and writes SQLite rows.
- `src/shadow/bootstrap.py` performs an atomic full rebuild and replays deferred
  sync work.
- `src/shadow/health.py` resolves `disabled`, `bootstrapping`, `ready`, `stale`,
  and `error` from SQLite metadata and runtime latches.
- `src/shadow/query.py` exposes SQLite FTS5 BM25 search and backend-specific
  rank values.
- `src/agent/shadow_graph_repository.py` routes bounded subtree reads through
  the Shadow cache when ready.
- `src/memory/recall.py` publishes `recall-bundle.v1` with
  `shadow-fts5/schema-1` as its exact index identity.

The current public documentation also contains a factual drift that must be
fixed before announcing a second backend: the maintained system overview still
describes the Shadow read cache as opt-in and says there is no auxiliary
database on the default read path, while the stable v2.0 contract is a
default-on external derived cache.

## Relationship to existing authorities

This work is a product architecture and qualification track under the v2.1
programme. It is not a standards project and does not move existing authority.

| Authority | Relationship |
| --- | --- |
| #178 | Programme umbrella for independently gated v2.1 memory and interoperability work. |
| #446 | Owns evidence-backed memory, retrieval, caching, clustering, and later memory semantics. |
| #448 | Owns reproducible retrieval and comparative benchmark evidence. |
| #449 | Owns append-only evidence and governed candidate provenance. |
| #452 | Owns the proposal queue and human-governed lifecycle. |
| #483 | Owns graph-outcome evaluation and final-world-state evidence. |
| #519 | Owns convergence-first standardization and the neutral TCK; database choice remains non-normative. |
| #520 | Owns prior-art and naming research; it may record Ladybug as adjacent implementation technology, not as a protocol. |

The product-level backend suite defined here is called the **Projection
Qualification Kit (PQK)**. It must never be described as the neutral TCK owned
by #519.

## Goals

1. Freeze the stable SQLite Shadow behavior as a characterization baseline.
2. Introduce narrow backend-neutral projection contracts without changing
   stable behavior.
3. Preserve existing public imports through compatibility facades while SQLite
   moves behind those contracts.
4. Build a deterministic PQK that separates exact structural conformance,
   retrieval quality, performance, and operational safety.
5. Qualify `ladybug==0.19.1` as an optional offline graph-native adapter on
   synthetic, disposable corpora.
6. Publish positive, negative, deferred, and rejected results with exact
   artifact and commit bindings.
7. Permit a later runtime experiment only after the offline qualification gates
   pass.

## Non-goals

- Replacing SQLite in the stable v2.0 runtime.
- Making LadybugDB part of a neutral memory standard or interoperability
  contract.
- Making Shadow or any derived database canonical.
- Porting the schema-only `memory_*` tables before their owning memory contracts
  are approved and implemented.
- Adding a second canonical graph mutation path.
- Claiming raw BM25 scores are numerically identical across engines.
- Enabling multiple Ladybug writer processes or mixed read-write/read-only
  database objects against the same database file.
- Installing Ladybug extensions from the network during normal runtime.
- Changing `recall-bundle.v1` or presenting Ladybug results as
  `shadow-fts5/schema-1` evidence.
- Adding hosted storage, mandatory cloud inference, or private graph evidence.
- Marketing Ladybug as the source of Matryca's memory semantics.

## Architecture

```text
Canonical Markdown and governed evidence
                 |
                 v
       pure projection records
                 |
     +-----------+-----------+
     |           |           |
     v           v           v
 ingest port   read port   state/capability port
     |           |           |
     +-----------+-----------+
                 |
       +---------+---------+
       |                   |
       v                   v
 SQLite Shadow adapter   Ladybug adapter
 stable and default      experimental and optional
```

Dependencies point inward. Pure records and protocols must not import
`sqlite3`, `ladybug`, agent surfaces, daemon code, FastMCP, FastAPI, or CLI
modules. Backend adapters depend on those contracts. Application orchestration
selects and operates an adapter; MCP, CLI, UI, and daemon entry points remain
thin consumers and never select storage independently.

The first refactor keeps `src/shadow/` as the SQLite implementation and public
compatibility facade. It does not perform a repository-wide module move. New
backend-neutral records and ports belong to the graph-domain boundary. The
Ladybug adapter remains infrastructure and is imported only when the optional
dependency and an explicit experimental execution mode are present.

## Projection contracts

The design uses interface segregation rather than one universal backend
object.

### Projection records

The canonical parser output is normalized into immutable records before a
backend sees it:

- `ProjectionPage`: stable title, graph-relative file path, source metadata,
  page properties, and ordered blocks.
- `ProjectionBlock`: stable block UUID, optional parent UUID, sort order,
  indent level, content, and properties.
- `ProjectionReference`: source block UUID, target identity, and reference kind.
- `ProjectionGeneration`: non-negative committed generation plus source,
  indexed, and quarantined counts.
- `ProjectionHit`: block UUID, content hash or bounded content required by the
  existing caller, page identity, stable order, and backend-local volatile
  score.
- `ProjectionHealth`: the established closed health state, reason code,
  generation, schema compatibility, and accounting status.
- `ProjectionCapabilities`: closed capability identifiers and backend contract
  version.

Absolute paths, credentials, prompts, private telemetry, or model secrets are
not valid projection-record fields.

### Narrow ports

`ProjectionIngestPort` owns:

- full replacement from normalized pages;
- one-page upsert;
- deletion by graph-relative source identity;
- transaction completion or rollback.

`ProjectionReadPort` owns:

- bounded lexical block search;
- bounded subtree reads;
- reference lookup required by current read behavior.

`ProjectionStatePort` owns:

- health resolution;
- generation and accounting metadata;
- content-free diagnostics;
- capability declaration.

No backend is required to fake an unsupported capability. Callers must check
the capability set and fail closed or use the existing Markdown/resident-BM25
fallback.

Graph-native traversal, vector search, hybrid retrieval, episodic memory, and
procedural memory are optional capabilities added only by separately approved
slices. They are not members of the initial stable port surface.

## Data and authority flow

1. The external parser reads canonical Markdown and yields Logseq page/block
   structures.
2. A pure normalizer creates projection records with deterministic ordering.
3. An application use case sends the records to one selected backend.
4. The backend commits a new generation or leaves the previous committed
   generation intact.
5. Health verifies schema, generation, source accounting, quarantine, and
   runtime failure latches.
6. Read routing uses the projection only when health and required capabilities
   are proven.
7. Missing, stale, incompatible, corrupt, or unsupported projection state uses
   the existing Markdown/resident-BM25 fallback.
8. Graph writes always continue through the existing parser-aware, sandboxed,
   OCC-protected, locked, atomic mutation plane.

SQLite and Ladybug are independently built from the same normalized source
records. Neither backend is built from the other as an authority. Ladybug's
SQLite attachment extension may be evaluated later as a migration convenience,
but it cannot supply conformance evidence for source equivalence.

## SQLite baseline and compatibility

SQLite remains selected when no experimental qualification mode is active.
Existing public functions continue to behave as compatibility facades during
the refactor:

- `open_shadow_db` and `open_shadow_db_query_only`;
- `rebuild_shadow_from_graph`;
- `sync_page_to_shadow` and `delete_shadow_page_by_file_path`;
- `resolve_shadow_health`;
- `search_blocks_fts`;
- `ShadowGraphRepository` read behavior.

The first abstraction PR must produce no operator-visible change, no new
environment variable, no schema migration, and no new fallback behavior. Its
acceptance evidence is the existing SQLite suite plus the new characterization
corpus.

## Ladybug qualification boundary

The initial adapter uses exactly `ladybug==0.19.1` as an optional development
and qualification dependency. The version is revalidated before an
implementation PR; a changed candidate requires an explicit design-record
update rather than an implicit dependency bump.

The first adapter is restricted to:

- synthetic or repository-owned disposable fixture graphs;
- one process with one read-write `Database` object;
- multiple connections only when created from that same object;
- an isolated database path that is never `shadow.sqlite`;
- explicit startup, transaction, checkpoint, close, and cleanup ownership;
- no MCP, CLI, UI, or daemon runtime routing;
- no normal-runtime extension download.

FTS, vector, SQLite-attach, and other Ladybug extensions are capabilities, not
assumptions. Qualification setup may acquire an exact extension artifact only
through an explicit network-enabled preparation step and must record version,
source, digest, platform, and cache location. Normal execution performs `LOAD`
only from an already admitted local artifact. Missing or mismatched extension
evidence produces `unsupported` or `no-serve`, never an automatic download.

## Future runtime selection

No runtime selector is added until offline PQK, packaging, crash recovery, and
concurrency gates pass.

If those gates pass, a later reviewed slice may introduce:

```text
MATRYCA_SHADOW_BACKEND=sqlite|ladybug
```

The default remains `sqlite`. An unknown value is a configuration error. An
explicit `ladybug` selection that cannot prove readiness falls back to the
existing Markdown/resident-BM25 path, not silently to SQLite. This preserves an
honest operator-visible backend decision.

Online Ladybug use additionally requires one durable database-owner process.
Other processes communicate with that owner through a bounded local adapter;
they do not open independent read-only objects while the owner is writing. The
owner service is a separate design and cannot be inferred from the offline
adapter.

## Semantic equivalence policy

Backend conformance has three different evidence classes.

### Exact structural conformance

These outputs must be byte- or value-equivalent after canonical ordering:

- normalized pages, blocks, parent relationships, and references;
- source/index/quarantine accounting;
- generation transitions;
- subtree membership and ordering;
- deletion, rename, rebuild, and replay postconditions;
- health, incompatibility, degraded, and no-serve classifications;
- content hashes and repository-owned fixture fingerprints.

### Retrieval contract conformance

The lexical contract requires bounded results, stable UUID tie-breaking,
content identity, explicit query normalization, and deterministic reporting for
the same backend/version. It does not require SQLite FTS5 and Ladybug BM25 to
emit identical raw scores.

The PQK records result overlap, rank correlation, missed relevant items, false
positives, empty-result behavior, query-class limitations, tokenizer/stemmer
configuration, and backend-local scores. Backend-local scores remain volatile
and do not enter reusable cross-backend fingerprints.

### Quality and outcome evaluation

Retrieval quality belongs to #448 and graph/outcome effects belong to #483.
Latency or quality leadership cannot be inferred from structural conformance.
Comparative claims require version-pinned corpora, multiple deterministic
seeds, confidence intervals where applicable, raw results, exclusions, and
separate retrieval and end-to-end conclusions.

`recall-bundle.v1` remains SQLite-specific because it names
`shadow-fts5/schema-1`. A future backend-neutral recall envelope must use a new
version and migration decision; the Ladybug experiment must not reuse the v1
identity.

## Projection Qualification Kit

The PQK is deterministic, local, LLM-free, synthetic, content-safe, and
backend-aware. It reports conformance and observations without promoting a
backend.

Minimum families:

1. normalization and deterministic ordering;
2. initial ingest and full rebuild;
3. incremental upsert, delete, rename, and deferred replay;
4. duplicate UUID, malformed page, bounded parser, and quarantine behavior;
5. schema mismatch, stale state, corrupt state, and missing artifact;
6. subtree and reference parity;
7. lexical query classes, ordering, and score separation;
8. transaction interruption and restart;
9. checkpoint and close behavior;
10. process ownership and lock refusal;
11. extension provenance and offline admission;
12. packaging and import behavior on supported Python/platform combinations;
13. storage size, startup, ingest, rebuild, warm-read, and memory observations.

Every run records the exact Matryca commit, backend name/version, adapter
contract version, Python, OS, architecture, fixture manifest and digest,
extension artifacts and digests, selected capabilities, per-case result,
limitations, raw-artifact location, and receipt fingerprint.

The PQK may return `pass`, `partial`, `unsupported`, `no-serve`, `error`, or
`not-applicable` per case. An overall promotion decision is separate.

## Failure and rollback behavior

- A projection write failure never mutates canonical Markdown.
- Failed rebuilds preserve the prior committed generation when the backend can
  prove that property; otherwise the backend is not ready.
- Invalid accounting, schema, capability, or provenance fails closed.
- A Ladybug failure cannot corrupt or delete `shadow.sqlite`.
- Removing the optional dependency and deleting the experimental derived
  database fully rolls back the experiment.
- Stable SQLite routing remains available throughout offline qualification.
- No migration of user data is required because both projections are
  rebuildable from canonical source.

## Documentation and public GitHub structure

The first delivery slice reconciles current v2.0 documentation before adding a
future backend narrative.

Documentation authority remains:

- `docs/knowledge/architecture/shadow-db.md`: current stable SQLite Shadow
  runtime and operator contract;
- `docs/knowledge/architecture/system-overview.md`: corrected current system
  overview;
- this specification: approved design and invariants;
- `docs/roadmaps/ROADMAP_GRAPH_NATIVE_PROJECTION.md`: future execution sequence
  after specification approval;
- `docs/quality/`: timestamped PQK evidence and terminal decisions;
- `CHANGELOG.md`: only shipped user-visible contract changes;
- `README.md`: no graph-native runtime claim until implementation and evidence
  exist.

After the specification is approved, create one public product sub-epic under
#178:

`[Experiment] Qualify a graph-native derived projection backend`

Its children are created incrementally:

1. reconcile v2.0 projection documentation;
2. freeze the SQLite semantic baseline;
3. define projection records, ports, and capabilities;
4. adapt SQLite without behavior change;
5. build the Projection Qualification Kit;
6. implement the offline Ladybug adapter;
7. compare structural and retrieval behavior;
8. qualify packaging, concurrency, interruption, and recovery;
9. publish the terminal promotion decision.

The epic links #446, #448, #483, #519, and #520 but does not become their
authority. Every substantive child has one milestone, dependencies, files,
acceptance evidence, blockers, rollback, labels, and explicit non-goals.

## Delivery milestones and gates

### M0 — public truth and design

Deliver the approved specification, correct current v2.0 documentation drift,
publish the roadmap, and create the product epic. No runtime changes.

Exit evidence: documentation inventory synchronized; `make agents-check`,
`make docs-check`, and `git diff --check` pass on the exact commit.

### M1 — SQLite characterization

Create repository-owned fixtures and characterize current SQLite behavior
without changing routing or schema.

Exit evidence: exact structural and lifecycle expectations pass against the
stable SQLite implementation; unsupported or backend-specific behavior is
explicit.

### M2 — projection contracts and SQLite adapter

Introduce pure records and segregated ports, then route existing SQLite use
cases through them while preserving compatibility facades.

Exit evidence: no graph-domain dependency inversion; all existing Shadow,
graph repository, routing, recall, read-only, and release-probe tests pass; no
operator-visible delta.

### M3 — Projection Qualification Kit

Publish deterministic runner, manifest, fixture digest, schemas, and SQLite
reference receipt.

Exit evidence: clean-checkout, network-free, LLM-free run with deterministic
machine-readable output and explicit evidence classes.

### M4 — offline Ladybug adapter

Implement the smallest graph-native adapter needed for current pages, blocks,
references, subtree, state, and bounded lexical qualification.

Exit evidence: one-process ownership, exact dependency and extension
provenance, structural PQK results, and no stable routing changes.

### M5 — comparative and operational qualification

Run structural parity, retrieval evaluation, performance observations,
interruption, restart, checkpoint, lock, and packaging matrices.

Exit evidence: retained raw artifacts and a reviewed decision record separating
facts, proposals, unknowns, limitations, and negative results.

### M6 — terminal decision

Publish exactly one outcome:

- `preferred_candidate`;
- `supported_optional_candidate`;
- `experimental_continue`;
- `deferred_upstream_or_packaging`;
- `rejected_with_evidence`.

Only a separately approved follow-up design may create an online owner service
or change runtime selection. No M6 result changes the v2.0 default by itself.

## Validation strategy

Use the narrowest deterministic gate first and expand with risk:

1. focused unit and characterization tests;
2. graph-layer boundary and typing checks;
3. existing Shadow/read/recall/read-only tests;
4. PQK exact fixtures;
5. guarded broader local CI under the current commit-ci-preflight admission
   contract;
6. hosted CI on the exact PR head;
7. platform/package matrices;
8. retained qualification campaign only after the exact public artifact exists.

Skipped, running, historical, source-only, or other-commit evidence is never a
pass for the current gate.

## Cost-aware execution policy

The primary orchestrator retains architecture, concurrency and safety rulings,
cross-task integration, public claims, final review, GitHub mutations, and
promotion decisions.

Cheaper workers may own bounded read-only inventories, documentation checks,
fixture generation, mechanical isolated implementation, deterministic test
execution, result distillation, and task-scoped review. Overlapping writers are
serialized. Workers receive one task brief and write a durable report; they do
not rediscover the whole programme or dispatch nested workers.

## Interruption and recovery

Execution uses an isolated worktree and a plan-owned progress ledger. Every
completed task ends in a recoverable local commit only after focused checks and
review. Before restart or handoff, record worktree, branch, base, exact HEAD,
dirty state, completed gates, running processes, unproven gates, and the next
task. Push, PR, merge, release, dependency publication, and external
announcement remain separate authorization gates.

## Acceptance checklist

- [ ] The maintained v2.0 documentation agrees on current Shadow defaults and
      authority.
- [ ] SQLite behavior is characterized before abstraction.
- [ ] Pure projection contracts have no infrastructure or agent-surface
      dependencies.
- [ ] SQLite remains the default and preserves all stable behavior.
- [ ] The PQK is visibly distinct from the #519 neutral TCK.
- [ ] Ladybug is optional, exact-versioned, offline-first, single-owner, and
      isolated from `shadow.sqlite`.
- [ ] No runtime extension download occurs.
- [ ] Structural parity, retrieval quality, performance, and outcomes are
      reported as separate evidence classes.
- [ ] `recall-bundle.v1` is not relabeled as backend-neutral.
- [ ] Concurrency, crash recovery, checkpoint, packaging, and rollback evidence
      exists before any online experiment.
- [ ] Negative and deferred results are publishable terminal evidence.
- [ ] No database or Matryca product is presented as the neutral standard.
- [ ] No README, release, or leadership claim exceeds exact public evidence.
