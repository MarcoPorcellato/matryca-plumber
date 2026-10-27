---
type: Document
title: Bounded MCP dashboard reads
description: Dashboard execution, cancellation, cleanup and platform boundaries.
status: draft
classification: active
owner: core-runtime
---

# Bounded MCP dashboard reads

## Scope

`read_graph_data(target_type="dashboard")` keeps its existing parameters and
successful Markdown counts. `query` is ignored: it cannot select a path, command,
transport, limit or bypass. Markdown remains authoritative; this operation does
not initialize Shadow, invoke a language model or start a service or watcher.

The bounded route applies to Linux and macOS. Windows retains the existing
thread-based route and has **no new whole-dashboard cancellation guarantee**.
Other platforms return `dashboard_platform_unsupported` before process creation.
An admitted POSIX failure never falls back to unbounded computation.

This document describes the implementation contract, not a release or deployment
qualification. Synthetic tests do not establish the cause or resolution of every
reported dashboard incident. Parser upgrades, installed-package qualification and
validation of an operator's deployment remain independent work.

## Execution and ownership

The asynchronous caller admits one job without queuing. A dedicated supervisor
owns its new process group, bounded input/output, cancellation polling and
finalization. Discovery, AST construction, parsing, queries, reference lint,
formatting and successful identity-context processing happen inside that group.
Its page-parser descendants are private; cancelling it does not terminate the
main process's shared AST cache or Parser worker.

| Boundary | Fixed production ceiling |
| --- | ---: |
| Execution, including startup and input | 1800 seconds (30 minutes) |
| Cleanup after the first terminal trigger | 5 seconds |
| Normal cancellation polling | 0.1 seconds |
| Request | 65,536 UTF-8 bytes |
| Worker stdout | 262,144 bytes |
| Worker stderr, aggregate | 4,096 bytes |
| Stage-entry records | Seven, at most 1,024 bytes each |
| Active dashboard jobs | One, without a queue |

The execution deadline starts before supervisor startup. The first success,
error, timeout or cancellation latches one cleanup deadline. Later cancellation
cannot renew it. A success must be fully validated and atomically admitted before
the execution deadline, with no earlier timeout or cancellation. Its subsequent
cleanup may cross that execution deadline but not its latched cleanup deadline.
A full pipe, EOF before child exit, blocked preparation or late
process creation does not grant more time. Capture limits are enforced while
reading, not after collecting an unbounded output.

The caller independently supervises its execution deadline. Python cannot
forcibly terminate a thread inside an uninterruptible kernel operation. If an
owner does not return within the original cleanup deadline, the caller stops
waiting, retains the owner and poisons dashboard admission. This is an
**unverified cleanup**, not proof that computation has stopped. A late owner
retains sole responsibility for its process handle and cannot reopen admission.

Cleanup succeeds only after the direct child is reaped, the owned group is
observed absent (`ESRCH`), every selector and stdin/stdout/stderr stream gate
passes, the supervisor returns and is joined, and no cleanup failure remains.
`EPERM` is an observation, never success. Other signal errors and uncertainty
remain failures. No unrelated process is terminated.

## Startup and protocol

The child uses a fixed current interpreter with `-I -S -B`, admitted source and
dependency roots, and source-origin verification. Neither the current directory
nor `PYTHONPATH`, executable `.pth` files, `sitecustomize` or `usercustomize`
selects its implementation. Parser spawn inherits the admitted import roots and
isolated interpreter flags. This is not an OS network sandbox or a general
security boundary against malicious installed dependencies.

The child forces the existing graph read-only policy and disables debug/default
logging privately, before internal imports. It binds identity reads to the
validated request root without changing the main process's environment.
Successful output preserves the previous order: cap the dashboard body, then
append identity once. The outer MCP wrapper does not read or append identity
again for this route. Error JSON contains no identity content. The non-Windows
dashboard branch does not await informational notifications outside the job.

Stage records mark entry into `discover`, `stat`, `load_ast`, `ids`, `refs` and
`format`; `complete` marks finished dashboard computation, not successful
identity processing or cleanup. An error may have only a valid prefix. Public
diagnostics contain fixed codes, the last phase, elapsed time and a cleanup
boolean, never raw exceptions, paths, note bodies or captured streams.

One correlated JSON terminal frame, successful exit, complete stage sequence,
EOF and all cleanup gates are required for success. A plausible Markdown frame
followed by a crash is a failure. The private Parser is shut down before the
terminal frame. No partial statistics are presented as a complete dashboard.

## Outcomes and recovery

Successful requests return the existing Markdown body and permitted identity
context. Failures return bounded JSON text containing `ok=false`, `code`,
`last_phase`, `elapsed_ms` and `cleanup_verified`.

| Code | Meaning |
| --- | --- |
| `dashboard_timeout` | Execution deadline reached; inspect cleanup independently. |
| `dashboard_busy` | Another admitted dashboard owns the permit; no queued job exists. |
| `dashboard_worker_failed` | Child startup, computation or exit failed. |
| `dashboard_protocol_error` | Request or captured response failed strict validation. |
| `dashboard_output_overflow` | A capture ceiling was exceeded. |
| `dashboard_cleanup_unverified` | Owned cleanup or supervisor return was not proven. |
| `dashboard_platform_unsupported` | Platform is neither admitted POSIX nor the legacy Windows route. |

After uncertain cleanup, subsequent dashboard requests remain rejected. There is
no reset endpoint or automatic retry. Preserve diagnostics and perform ordinary
operator diagnosis/restart; do not kill unrelated processes or infer cleanup
from an idle client. Other read targets remain independently usable.

An actual MCP cancellation notification propagates cancellation to the owned
job. The caller re-raises cancellation only after its bounded finalization wait;
a disconnected client is not promised a response. A client that merely stops
waiting without sending cancellation is a different case: the server's own
deadline remains the backstop. Transport delivery time is not bounded here.

## Qualification

`dashboard-read-qualification.yml` exercises small synthetic lifecycle fixtures
on Linux/macOS with Python 3.12/3.13. It does not replace existing required CI or
release gates and does not qualify large-graph completion or performance.

### Deferred 1,115-page completion control

One synthetic macOS run using CPython 3.12.13 and Parser 1.9.0 failed its
completion assertion at the former 120-second execution limit. The retained
outcome was `dashboard_timeout`, `last_phase=refs`, `elapsed_ms=120020` and
`cleanup_verified=true`. No partial dashboard was returned. This is evidence
of that observed timeout and cleanup, not completion or an isolated root cause.

The maintainer accepted separate lifecycle delivery and raised the production
execution limit to 1800 seconds. The consumed attempt is not reclassified or
retried by that policy change; completion at the new limit remains unqualified.
Raising a ceiling is not a performance improvement or a promise of completion.

The original completion assertions remain in a separately selected `slow` test.
Ordinary CI and local lifecycle runs do not execute it; the dedicated lifecycle
workflow excludes it explicitly, and other ordinary test runs report it as a
deferred skip. It is not an expected failure or a passed gate. A separately
authorized performance attempt must select it explicitly:

```bash
uv run --no-sync pytest --no-cov -q -m slow \
  tests/test_dashboard_worker.py::test_dashboard_synthetic_1115_pages_complete_without_partial_counts
```

That attempt needs its own execution allowance for the 1800-second production
limit and cleanup; this PR does not run it. Issue #656 remains open for the
performance investigation and deployment validation.

Direct synchronous dashboard functions retain their previous behavior, with an
optional synchronous stage callback. They acquire no timing guarantee; callback
exceptions propagate. Reads of files changing during the operation are not
claimed to be an atomic whole-vault snapshot.
