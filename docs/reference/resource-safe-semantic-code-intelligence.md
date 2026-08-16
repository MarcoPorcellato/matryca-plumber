---
type: Reference
title: Resource-safe semantic code intelligence
description: Maintainer policy for using language-server-backed code intelligence without competing with qualification and runtime workloads.
status: active
last_verified: 2026-08-16
---

# Resource-safe semantic code intelligence

Semantic code intelligence is valuable when a maintainer needs live declarations,
references, diagnostics, reference-aware renames, or symbol-scoped edits. Its language
servers can also retain project graphs, parsed syntax, dependency metadata, and document
symbol caches in memory. On a constrained development host, an always-on or broadly
configured semantic service can therefore compete with tests, containers, virtual machines,
and release qualification.

This guide defines the Matryca Plumber operating policy: semantic analysis is an admitted,
bounded capability, not a background indexer and not the default answer to every source
question.

## Evidence boundary

A local audit of a large mixed-language checkout found:

- approximately 2.9 GiB of retained semantic caches;
- one stale format-specific cache of approximately 2.1 GiB;
- Python and TypeScript caches of approximately 500 MiB and 213 MiB respectively;
- a historical session that started more than ten language servers for one checkout.

Those figures explain the observed risk but are not portable benchmarks. Cache files may
expand when deserialized, while resident memory depends on language-server implementation,
project shape, dependency graph, open documents, and query history. The audit did not run a
new live-RSS benchmark because the host resource-admission result was inconclusive. This
document therefore records a conservative policy and a reproducible measurement method,
not a universal memory claim.

## Admission contract

Start a semantic service only when every condition below is true:

1. The resource-admission gate explicitly allows optional analysis workloads. Unknown,
   inconclusive, or denied admission is a hard stop.
2. No resource-sensitive qualification, container, virtual-machine, or recovery workload is
   running or about to start.
3. The exact repository and worktree are known.
4. One language server is sufficient for the task, or the need for more than one is written
   down before startup.
5. Workspace folders and ignored paths are bounded before the service sees the checkout.
6. Existing caches have been inspected and are compatible with the current language and
   workspace selection.
7. The task materially benefits from semantic information that deterministic search and
   bounded file reads cannot supply safely.

Failure of any condition means: use deterministic repository tools and postpone semantic
activation.

## Cheapest suitable analysis first

Use the following order:

1. filename and text search;
2. bounded line or file reads;
3. parsers, formatters, linters, type checkers, and focused tests;
4. an existing repository graph, after checking its revision and worktree binding;
5. live language-server-backed symbol operations.

The final step is justified for operations such as:

- finding cross-file references before changing a shared symbol;
- locating declarations through imports or generated type information;
- performing a reference-aware rename;
- requesting diagnostics that require the active project graph;
- replacing a complete function, method, or class with symbol-bound boundaries.

It is normally unnecessary for Markdown, JSON, YAML, TOML, shell scripts, generated files,
small documentation changes, or an edit already bounded by an exact textual match.

## One worktree, one language lane

The default backend lane is Python source under `src/`. Frontend work should use a separate,
temporary TypeScript lane restricted to the frontend source directory. Both lanes may run
together only for an explicitly cross-stack task and only while admission remains positive.

Treat project policy as the following pseudoconfiguration, not as a drop-in configuration for
any particular client:

```yaml
semantic_analysis:
  languages: [python]
  workspace_folders: [src]
  ignore_gitignored_files: true
  ignored_paths:
    - "**/.venv/**"
    - "**/node_modules/**"
    - "**/.next/**"
    - "**/target/**"
    - "**/build/**"
    - "**/dist/**"
    - "**/coverage/**"
    - "**/htmlcov/**"
    - ".worktrees/**"
```

For a frontend-only task, replace `python` and `src` with `typescript` and the smallest
frontend source root. Do not add data formats merely because files of those formats exist in
the repository.

## Startup and response limits

Apply conservative defaults:

- disable dashboards, tray applications, onboarding, and session memories;
- keep logs at warning level unless diagnosing a specific failure;
- use a bounded tool timeout, initially 45 seconds;
- cap ordinary tool responses at approximately 30,000 characters;
- limit optional symbol metadata retrieval to approximately two seconds;
- do not pre-index the repository unless a measured task requires it;
- prefer a persistent dependency cache over repeated temporary downloads;
- expose only the read or edit operations required by the selected task profile.

Limiting the exposed tool set primarily reduces prompt and control-plane overhead. Limiting
languages, workspace folders, dependencies, and caches is what controls most host memory.

## Cache policy

Inspect cache size before activation. The repository's conservative review threshold is
250 MiB. Crossing the threshold is not automatically an error, but the cache must not be
loaded silently.

When a cache is unexpectedly large or was created under a broader project profile:

1. confirm that no semantic-service or language-server process is active;
2. record the cache path, size, languages, workspace scope, and modification time;
3. rename the cache directory to a timestamped quarantine path on the same filesystem;
4. start only after positive resource admission;
5. allow lazy reconstruction from the reduced project profile;
6. compare correctness and resource evidence before deleting the quarantined copy.

Renaming is preferred to immediate deletion because it is reversible and prevents a stale
cache from being deserialized. Quarantine consumes disk until explicitly retired; it is a
safety checkpoint, not the final cleanup step.

## Query discipline

Keep semantic queries narrow:

- request a symbol overview for one unfamiliar file;
- search for symbol names without bodies first;
- request bodies only for symbols required by the decision or patch;
- find references before changing a public or shared symbol;
- avoid whole-repository overviews and unbounded pattern searches;
- batch independent narrow queries when the service serializes them safely;
- validate the resulting patch with focused tests and repository gates.

A reference list is not runtime proof. Dynamic imports, generated code, configuration,
reflection, subprocesses, and integration behavior still require appropriate tests or direct
evidence.

## Shutdown and orphan handling

After semantic work, verify that no service or child language server remains before starting
a resource-sensitive workload. If cleanup is necessary:

1. inspect PID, parent PID, executable path, command line, elapsed time, and RSS;
2. distinguish service-owned children from editor, IDE, or operator processes;
3. terminate only exact owned processes or verified orphans;
4. never use a broad name-only process purge;
5. recheck the same exact process patterns after cleanup.

Lifecycle cleanup belongs at session end. Running cleanup hooks after every conversational
turn adds overhead and can interfere with a service that is intentionally active for the
session.

## Measurement protocol

When resource admission allows a controlled benchmark, capture:

1. exact repository revision and clean/dirty state;
2. exact project/worktree path;
3. selected language server and workspace folders;
4. cache state: absent, cold, warm, or quarantined;
5. baseline host memory and competing workloads;
6. service PID tree and per-process RSS after startup;
7. RSS after one overview, one symbol lookup, and one cross-file reference query;
8. elapsed startup and query times;
9. residual processes and memory after normal shutdown.

Repeat cold and warm runs. Do not compare results collected from different revisions,
language sets, or host workloads as if they were equivalent. A source inspection, cache size,
or successful smoke query must not be presented as measured resident-memory qualification.

## Maintainer checklist

Before use:

- [ ] Resource admission is explicitly positive.
- [ ] The exact worktree and revision are confirmed.
- [ ] One language lane and bounded workspace folders are selected.
- [ ] Generated, dependency, build, coverage, and nested-worktree paths are excluded.
- [ ] Cache size and provenance are acceptable.
- [ ] The semantic operation is materially safer than deterministic alternatives.

After use:

- [ ] Focused behavior or repository gates validate the change.
- [ ] No result is overstated beyond the language server's coverage.
- [ ] No service-owned process remains.
- [ ] Quarantined caches have an explicit retain-or-retire decision.
- [ ] Resource-sensitive qualification begins only after cleanup verification.

