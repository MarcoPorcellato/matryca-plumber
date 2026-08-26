---
type: Specification
title: MLflow evaluation projection design
description: Architecture and privacy contract for a deterministic graph-outcome evidence projection and a separately gated optional MLflow publisher.
status: draft
classification: active
audience: [maintainer, contributor, operator, agent]
owner: quality
last_verified: 2026-08-26
stale_after: 2027-02-22
---

# MLflow Evaluation Projection Design

## Executive decision

Matryca Plumber will evaluate MLflow only as an optional maintainer laboratory
over a deterministic, content-free projection of already validated Matryca
evidence.

The work is split into two independent pull requests:

1. **PR A — pure evidence projection:** introduce a closed projection contract,
   deterministic JSON serializer, privacy guard, Git provenance binding, atomic
   file output, maintainer CLI, tests, and maintainer documentation. PR A has no
   MLflow dependency or import.
2. **PR B — optional MLflow publisher:** after PR A is reviewed and qualified,
   add a separately gated adapter that consumes only the PR A projection. PR B
   must not change canonical evidence or the default product runtime.

PR A is the only implementation scope authorized by this design. PR B remains
a future design and supply-chain gate rather than an implied follow-up merge.

## Outcome

A maintainer can run the existing synthetic graph-outcome scenarios and emit a
byte-deterministic, privacy-bounded projection to standard output or a new
explicit file. The projection is bound to the exact clean Matryca source
revision and can later be imported into a disposable experiment tracker without
changing any canonical task, report, receipt, validator, status, or digest.

The projection is useful even if PR B is never implemented. It establishes a
stable outer boundary for longitudinal evaluation tools while preserving the
repository's stronger evidence model.

## Verified starting point

This design is bound to public `main` at
`aa6acc92c41acc0764216187f39a6a50bb03ef6a`, verified in an isolated clean
worktree on 2026-08-26.

At this revision:

- `src/memory/graph_outcome_protocol.py` owns closed, provider-free task,
  report, receipt, canonical serialization, and validation contracts;
- `src/memory/graph_outcome_harness.py` owns deterministic synthetic scenarios
  and returns `EpisodeRun` only after temporary canonical and derived roots have
  been removed;
- `scripts/run_graph_outcome_harness.py` emits a deterministic content-free
  synthetic-suite report and accepts an operator-supplied 40-character source
  revision;
- `EpisodeRun` already binds its task, terminal report, receipt, canonical
  receipt bytes, validation result, source fingerprints, cleanup result,
  executed tool identifiers, and content-free failure codes;
- the default distribution includes only `src*` and `frontend`, so a new
  top-level `tools/` package remains outside the installed product package;
- the default and development dependencies contain no MLflow package.

The current report runner is evidence of a viable seam, not the new projection
contract. PR A may reuse its scenario orchestration, but it must not silently
change the existing report schema or its tests.

## Authority model

The design uses three explicit evidence classes:

| Class | Authority | Mutability | Role |
| --- | --- | --- | --- |
| Canonical Matryca evidence | Task bundles, reports, receipts, validators, and their canonical bytes | Contract-governed | Sole authority for what ran, what passed, and what was retained |
| Derived evaluation projection | PR A closed JSON document | Reconstructable | Content-free transport and comparison surface |
| MLflow state | Future PR B local tracking store | Disposable and mutable | Optional browsing, filtering, and visualization convenience |

Neither the derived projection nor MLflow can promote, reject, reinterpret, or
repair canonical evidence. Deleting them loses convenience only. Recreating
them from the same canonical input and source revision produces the same PR A
bytes.

MLflow-generated run IDs, experiment IDs, timestamps, URLs, database keys,
annotations, and server state are forbidden from canonical Matryca objects and
from the PR A projection identity.

## Goals

1. Define one closed, versioned projection schema for a validated synthetic
   graph-outcome `EpisodeRun`.
2. Preserve canonical Matryca evidence bytes and identities exactly.
3. Make the projection deterministic across input ordering and repeated runs.
4. Deny content, paths, credentials, runtime identity, and arbitrary metadata
   recursively before serialization.
5. Bind maintainer CLI output to an exact clean Git source revision.
6. Make file output atomic, fail-closed, and non-destructive by default.
7. Keep MLflow absent from imports, dependencies, default runtime, and PR A
   tests.
8. Leave a narrow, testable boundary for a later optional publisher.

## Non-goals

PR A does not:

- add, install, import, start, configure, or contact MLflow;
- project `BenchmarkRunReport`, comparative cohorts, retrieval runs, real
  vaults, real Shadow databases, providers, models, prompts, answers, or user
  sessions;
- trace or autolog daemon, CLI, MCP, Logseq, model, or network activity;
- add artifacts, model registry, Review Queues, Assistant, MCP Server, MCP
  Registry, or human/LLM judgments;
- create a product observability subsystem or a public user-facing CLI;
- alter `src/memory/`, canonical protocol schemas, validation rules, report
  status, receipt identities, or release qualification;
- add a service, background process, network dependency, telemetry path, or
  hosted CI job;
- write to a Logseq graph, Shadow DB, Matryca evidence index, or canonical
  receipt location;
- publish a README claim about MLflow integration.

Real-vault and end-user tracking remain rejected unless a separate privacy and
product study establishes a justified user need.

## Architecture

```text
deterministic synthetic scenario
             |
             v
validated EpisodeRun
  task + report + receipt + cleanup evidence
             |
             v
closed allowlist projector --------------------+
             |                                 |
             v                                 v
recursive leakage guard              canonical Matryca objects
             |                       remain byte-identical
             v
canonical projection payload
             |
             +----> deterministic stdout JSON
             |
             +----> atomic explicit output file
             |
             `----> future optional publisher (PR B only)
```

Dependencies point outward. The projector may import the existing canonical
types and validators. No file under `src/` may import `tools`, and no canonical
module may import a tracking framework.

## Component boundaries

PR A uses focused modules under a maintainer-only outer adapter:

```text
tools/
  __init__.py
  evaluation_projection/
    __init__.py
    schema.py
    privacy.py
    provenance.py
    projector.py
    atomic_output.py
    cli.py
scripts/
  project_graph_outcome_evidence.py
tests/tools/evaluation_projection/
  test_schema.py
  test_privacy.py
  test_provenance.py
  test_projector.py
  test_atomic_output.py
  test_cli.py
```

Responsibilities are intentionally separated:

- `schema.py` owns the closed Pydantic projection models and schema identifier;
- `privacy.py` owns the recursive allowlist and denylist guard;
- `provenance.py` resolves and verifies the repository source binding;
- `projector.py` validates an `EpisodeRun` and maps allowlisted fields;
- `atomic_output.py` owns deterministic serialization and safe file install;
- `cli.py` owns argument parsing, scenario orchestration, exit codes, and
  content-free operator messages;
- the script is a thin, explicit maintainer entry point with no business logic.

This layout keeps experimental tooling out of the production package and makes
every policy independently testable. A later PR B publisher belongs in the
same outer adapter only after its own design is approved; it must consume the
closed PR A model rather than `EpisodeRun` or arbitrary dictionaries.

## Input contract

### Supported input

Projection schema v1 accepts exactly one terminal `EpisodeRun` produced by the
synthetic graph-outcome harness. It does not accept generic mappings,
unvalidated JSON, subclasses with extra fields, benchmark reports, retained
raw logs, or filesystem paths.

Before mapping, the projector must prove:

1. replaying `validate_episode_against_task(run.report, run.task)` reproduces
   the recorded canonical validation outcome exactly;
2. on validation success, the returned token equals `run.validation_token`,
   `run.validation_error` is absent, and `run.failure_codes` is empty;
3. on an expected validation rejection, the replayed
   `EvidenceContractError` code equals `run.validation_error`, the validation
   token is absent, and `run.failure_codes` contains exactly that code;
4. `run.receipt.report_id == run.report.report_id`;
5. `run.receipt.task_bundle_digest == run.task.task_bundle_id`;
6. `run.receipt_bytes == canonical_outcome_receipt_bytes(run.receipt)`;
7. `run.receipt.receipt_id` equals the SHA-256 of those canonical bytes;
8. roots were distinct and outside the repository;
9. cleanup was verified;
10. the source revision is lowercase hexadecimal with exactly 40 characters.

Any mismatch rejects the entire projection. A validation rejection is not
redacted into a partial success or reinterpreted as a projector failure. A
synthetically expected rejected scenario may be projected only when replay
reproduces the canonical report, receipt, and recorded failure code exactly.

### Source binding

The pure projection API requires an explicit source revision. It validates the
shape but performs no Git I/O.

The maintainer CLI resolves the worktree itself and applies a stricter policy:

- `HEAD` must be a full 40-character commit;
- the worktree must be clean, including untracked files;
- `HEAD` must belong to a named local branch;
- an optional `--source-revision` assertion must exactly equal `HEAD`;
- detached HEAD is rejected in schema v1;
- unavailable, ambiguous, dirty, or mismatched Git state is rejected before
  the harness runs.

Detached execution has no override in PR A. A future override would require a
separate provenance contract and explicit review.

## Projection schema v1

The top-level schema identifier is
`matryca-graph-outcome-evaluation-projection.v1`.

The closed output contains only:

- `schema_version`;
- `projection_id`;
- `source_revision`;
- `protocol_schema_version`;
- `scenario`;
- `policy_mode`;
- `task_bundle_digest`;
- `report_id`;
- `receipt_id`;
- `terminal_status`;
- `validation_status` as `passed` or `rejected`;
- sorted content-free `failure_codes`;
- sorted `executed_tool_ids`;
- closed outcome dimensions with dimension, status, and reason code;
- closed aggregate metrics already present in the canonical report;
- initial and final canonical and derived fingerprints;
- `roots_distinct`, `roots_outside_repository`, and `cleanup_verified`;
- receipt artifacts with kind, digest, and record count.

The maintainer CLI emits one closed suite envelope with schema identifier
`matryca-graph-outcome-evaluation-projection-suite.v1`. It contains only:

- `schema_version`;
- `suite_id`;
- the shared `source_revision` and `protocol_schema_version`;
- exactly one projection for each of the four fixed default scenarios, sorted
  lexicographically by scenario identifier.

The suite rejects duplicate, missing, unsupported, or mixed-provenance
projections. It does not introduce aggregate status, timing, metadata, or a
second interpretation of canonical results.

No wall-clock timing is projected in v1 because `EpisodeRun` does not currently
provide a canonical bounded timing field. No field may be added merely because
a tracking framework can display it.

All Pydantic models use `extra="forbid"`. Collections use closed element types,
bounded lengths, deterministic sorting, and existing identifier/digest
constraints. The projection cannot carry an open `tags`, `metadata`,
`properties`, `params`, or `extra` mapping.

## Deterministic identity

The canonical projection payload is the closed model without `projection_id`,
serialized as UTF-8 JSON with:

- ASCII escaping enabled;
- keys sorted recursively;
- separators `,` and `:` without insignificant whitespace;
- one trailing newline only for the emitted document;
- no timestamps, random values, process IDs, host values, or filesystem data.

`projection_id` is the lowercase SHA-256 of the canonical payload bytes without
the trailing newline. The final document adds that ID and is serialized with
the same canonical rules plus exactly one trailing newline.

`suite_id` follows the same construction: SHA-256 of the closed suite payload
without `suite_id` and without a trailing newline. Per-episode projection IDs
remain unchanged when placed in a suite.

Repeated projection of identical validated evidence at the same source
revision must produce byte-identical final documents. Reordered equivalent
input collections must also produce identical bytes. Any changed allowlisted
value, schema version, protocol version, or source revision must change the
projection identity.

## Privacy contract

### Closed allowlist

The schema is the primary privacy boundary. The projector constructs every
field explicitly from typed canonical values. It never recursively copies an
input model or calls unrestricted `model_dump()` into the output.

### Recursive leakage guard

After model validation and before identity calculation, a second guard walks
all keys and scalar values. It rejects the document if it detects a forbidden
field family or value class, including nested data.

Forbidden content includes:

- graph content, note titles, page names, block UUIDs, block text, and queries;
- prompts, answers, model outputs, raw events, raw logs, stack traces, and
  subprocess output;
- absolute paths, relative path fields, home-directory markers, URI-like file
  references, and platform-specific path forms;
- environment values, credentials, tokens, API keys, cookies, authorization
  material, usernames, hostnames, and email addresses;
- embeddings, tensors, binary blobs, model state, and arbitrary artifacts;
- framework-generated run IDs, timestamps, URLs, endpoints, database IDs, and
  annotations.

Digest-shaped values remain permitted only in explicitly allowlisted digest
fields. Identifier-shaped values remain permitted only in closed identifier
fields. A match in any nested value rejects the entire projection.

### Failure semantics

Privacy failures are not repaired by redaction. Redaction can collapse distinct
inputs into ambiguous evidence and may hide a projector defect. PR A therefore
fails closed, emits no projection document, and returns only a stable
content-free reason code.

The guard must not include forbidden source content in exceptions, logs, test
failure messages, or command output.

## CLI contract

The thin maintainer command is:

```text
python scripts/project_graph_outcome_evidence.py [--source-revision SHA] [--output FILE] [--overwrite]
```

Behavior:

- without `--output`, write the canonical projection document to standard
  output and no other standard-output content;
- with `--output`, write no projection to standard output;
- refuse an existing output unless `--overwrite` is explicit;
- resolve and validate Git provenance before running synthetic scenarios;
- run only the fixed synthetic graph-outcome scenario set;
- emit the closed suite envelope defined above;
- never read a graph path, `.env`, tracking URI, credentials, or network
  configuration.

The implementation plan must preserve and golden-test this exact suite
representation. It must not expose a generic input-file option in v1.

Stable process results are:

| Exit | Meaning |
| --- | --- |
| `0` | Projection completed and any requested output was installed |
| `2` | Argument parsing or usage failure |
| `3` | Git source binding unavailable, dirty, detached, or mismatched |
| `4` | Canonical evidence, schema, or privacy validation rejected |
| `5` | Output exists and overwrite was not authorized |
| `6` | Atomic output preparation or installation failed |

Standard error contains only a stable reason code and a short bounded
maintainer message. It never includes paths, input values, exceptions, Git
command output, environment values, or raw evidence.

## Atomic output contract

File output is installed only after the complete suite has been projected,
privacy-checked, identity-checked, and serialized in memory.

The writer must:

1. require an existing real parent directory;
2. reject a symlink destination and ambiguous destination types;
3. refuse an existing destination unless `--overwrite` is present;
4. create a private temporary file in the destination directory;
5. write the complete bytes, flush, and `fsync` the temporary file;
6. recheck the destination policy immediately before installation;
7. install with one same-filesystem atomic replacement;
8. `fsync` the parent directory where supported;
9. remove only its owned temporary file on any failure.

No partial projection may appear at the requested path. The writer must not
follow destination symlinks, create missing parent directories, delete unrelated
files, or broaden permissions. Overwrite replaces only the exact explicit
regular-file destination. A failure before atomic replacement preserves the
prior destination. If replacement succeeds but the following directory `fsync`
fails, the command reports an output failure and preserves the newly installed
complete file; it must not claim that the prior destination was restored.

## Testing strategy

PR A is implemented test-first and must include these independent gates:

1. **Golden identity:** fixed validated episodes and the fixed suite produce
   reviewed canonical bytes and expected projection and suite IDs.
2. **Reordered determinism:** equivalent reordered dimensions, artifacts,
   tool IDs, and failure codes produce the same bytes.
3. **Identity invalidation:** changing any allowlisted value, schema version,
   protocol version, or source revision changes the ID.
4. **Canonical preservation:** task, report, receipt bytes, IDs, and statuses are
   unchanged before and after projection.
5. **Adversarial privacy:** direct and recursively nested denied fields and
   values reject without echoing the secret or content.
6. **Closed schema:** unknown keys, generic mappings, unsupported model types,
   and benchmark reports reject.
7. **Git provenance:** clean named branch passes; dirty, untracked, detached,
   invalid SHA, and mismatched assertion states reject before harness execution.
8. **Atomic output:** new file, explicit overwrite, existing-file refusal,
   symlink refusal, missing parent, write failure, pre-install race, and
   replacement failure preserve the prior destination and remove owned
   temporary state. A post-replacement directory-sync failure preserves the
   complete new file and reports the durability failure without claiming
   rollback.
9. **CLI discipline:** stdout/stderr separation and every stable exit code are
   covered without leaking local data.
10. **Import boundary:** production `src` modules do not import `tools`; the
    projection package is absent from the built distribution.
11. **Dependency isolation:** PR A imports and tests pass when MLflow is neither
    installed nor importable; no dependency or lock entry is added.
12. **Graph-outcome regression:** existing protocol, harness, runner, and
    synthetic scenario tests remain green.

The full repository quality gates remain required in proportion to the exact
implementation diff. A projection PASS is not release, runtime, real-vault,
provider, model, or external-system qualification.

## Documentation contract

PR A adds:

- this architecture specification;
- an implementation plan after the written specification is approved;
- a concise maintainer runbook for deterministic projection generation,
  interpretation, reconstruction, and safe deletion;
- the generated documentation inventory updates;
- one concise Unreleased changelog entry if the implemented maintainer contract
  passes the repository changelog decision gate.

PR A does not add README marketing or claim that MLflow is integrated. A README
mention is permitted only after a separately qualified PR B and a measured
maintainer trial demonstrate material value.

Public documentation must describe canonical Matryca evidence, derived
projection evidence, and optional tracking state distinctly. It must never
present a local dashboard, imported row, or tracker run as canonical evidence.

## PR B entry gates

PR B may be designed only after PR A is merged and all of these facts are
reverified on its exact `main` commit:

1. projection identity and canonical-preservation gates are terminal green;
2. privacy tests cover the final closed schema and adversarial nested inputs;
3. dependency and import isolation are proven;
4. the publisher can consume only the validated PR A schema;
5. current MLflow version, license, dependency tree, vulnerabilities, Python
   3.12/3.13 support, Apple Silicon/Linux behavior, and offline behavior have
   been reviewed;
6. the design restricts publication to an explicit loopback endpoint and
   disables tracing, autologging, artifact capture, and experimental surfaces;
7. tracking failure cannot change canonical status or product behavior;
8. local retention, deletion, reconstruction, and storage measurements are
   specified;
9. no required hosted CI path becomes longer or network-dependent.

PR B must be optional, maintainer-only, and independently removable. The
default package, normal commands, tests, and releases must continue to work
without MLflow installed or reachable.

## Failure and rollback model

PR A has no migration and writes no persistent state unless the maintainer
names an output file. Rollback consists of removing the outer projection tools,
tests, wrapper, and documentation. Canonical Matryca evidence remains unchanged.

A failed projection produces no successful output and cannot downgrade or
upgrade the underlying result. A deleted projection can be reconstructed from
the same eligible `EpisodeRun` inputs and exact source revision. If canonical
evidence is unavailable, the projection is not reconstructable and must not be
treated as an archive substitute.

## Acceptance criteria for PR A

PR A is complete only when all of the following are proven on its exact commit:

- one closed schema v1 represents only the approved synthetic `EpisodeRun`
  evidence;
- canonical bytes, IDs, validation, and statuses remain unchanged;
- deterministic golden, reorder, and invalidation tests pass;
- recursive privacy tests fail closed without echoing denied values;
- source binding rejects dirty, untracked, detached, and mismatched worktrees;
- atomic output tests prove no partial or unintended overwrite;
- no MLflow import, dependency, process, endpoint, or network activity exists;
- no production module imports the outer tooling package;
- existing graph-outcome and repository quality gates are terminal green;
- the maintainer runbook, inventory, and changelog decision are current;
- exact-head diff and documentation review find no unsupported MLflow or product
  claim.

Completion of PR A authorizes neither PR B nor an MLflow trial. Those remain
separate decisions based on current evidence.
