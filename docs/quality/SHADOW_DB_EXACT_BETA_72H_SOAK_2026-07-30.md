# Shadow DB exact-beta 72-hour soak — terminal evidence record

**Status:** terminal `PASS`, recorded 2026-08-03 at 00:52:20 UTC. This is a
sanitized quality artifact, not a release note and not a release decision. It
records the exact-artifact re-qualification required before the Shadow read path
can become default-on. The fail-closed decision remains
[`issue-bodies/v2-rc-stable-readiness.md`](issue-bodies/v2-rc-stable-readiness.md),
tracked by [#343](https://github.com/MarcoPorcellato/matryca-plumber/issues/343).

The corpus is a copied daily-use vault. Page titles, graph paths, block
identifiers, raw logs, and private filesystem locations are deliberately absent.
Only aggregate counts and sanitized digests appear.

## Why this run exists

The beta gate accepted a documented evidence boundary: the previous installed
wheel and 24-hour soak proved the Shadow design and read path, but not the exact
bytes later published as `matryca-plumber==2.0.0b1`. That exception was safe for
an opt-in beta and does not carry forward to a default-on release candidate.

This run binds the public beta wheel to a fresh installed-wheel gate and a
minimum 72-hour real-vault soak at the product's 15-second page-parse deadline.
It does not test the future default-on configuration; that remains a separate RC
gate after this beta re-qualification passes.

## Artifact and installed-wheel gate

| Field | Value |
| --- | --- |
| Public release | `v2.0.0-beta.1` |
| Package version | `2.0.0b1` |
| Published tag commit | `85517e4` |
| Wheel SHA-256 | `c6d0223f6a4c04d781b97f9bfde8cf71a9546db8f3ca9e2adf55a0db4c4b0909` |
| Candidate provenance digest | `8654fb3261763228f52536f782291f3f01a4d944f65400e8ecafff257c5d4ffb` |
| Wheel binding digest | `0078c81282fc17270370262b23942732b871becac980663404bc22a4c8e96438` |
| Host profile | macOS arm64, CPython 3.12.13 |
| Source Markdown files | 3,378 |
| Page-parse deadline | 15 seconds |
| Preflight | `PASS` |
| Installed-wheel gate | `PASS` |
| Source Markdown unchanged | `true` |

The wheel digest matched the published PyPI artifact. The candidate imported
from its isolated virtual environment rather than the repository checkout. The
installed-wheel gate exercised a disposable vault copy through the supported
`2.0.0a5 → 2.0.0b1` upgrade path, Shadow readiness, FTS, bounded subtree reads,
quarantine behavior, recovery, and Markdown fingerprint preservation.

The same candidate provenance digest is verified again when the soak starts.
The collector refuses to run if it does not match the wheel gate, so a different
environment cannot silently inherit this evidence.

## Soak contract

| Parameter | Value |
| --- | --- |
| Target accumulated duration | 259,200 seconds (72 hours) |
| Maximum cycles | 1,000 |
| Interval | 600 seconds |
| Page-parse deadline | 15 seconds |
| Per-probe timeout | 900 seconds |
| Phases per completed cycle | `ON`, then `OFF` |
| Terminal results | `PASS` or `FAIL` |
| Terminal result | `PASS` |

Each ON phase asserts startup readiness, FTS, bounded subtree behavior,
watcher-driven create/rename/delete convergence, and count invariants. Every
twelfth cycle forces a sync error and verifies recovery through a full rebuild.
Each OFF phase verifies the disabled path. A cycle becomes complete only after
both phases pass.

The source copy is fingerprinted around the one-time working-copy operation.
Every resume re-verifies the working-copy fingerprint. The harness rejects any
changed input, candidate provenance, wheel binding, duration, interval, cycle
limit, or page-parse deadline as `soak_resume_mismatch`.

## Durable lifecycle and restart behavior

The earlier 24-hour run showed that the collector could resume from a
checkpoint, but its first interruption also showed that a session-scoped
background process was the wrong lifetime boundary. This run therefore uses a
user-scoped macOS service with four separated durable roots:

1. an immutable source-vault copy;
2. a mutable soak working copy;
3. sanitized evidence, heartbeat, result, and supervisor logs;
4. a frozen copy of the evidence runner, separate from both the repository and
   evidence output.

The service starts at user login. Its supervisor invokes the resumable
collector, retries non-terminal exits after a bounded delay, and stops only when
the collector writes terminal `PASS` or `FAIL` evidence. The service manager
restarts the supervisor after an unsuccessful exit. Because neither the
candidate environment nor the checkpoint lives in temporary storage, ordinary
process termination, logout, sleep, and host restart do not discard the run.

Host suspension and downtime do not receive unearned duration. The collector's
elapsed accumulator is restored from the last checkpoint and advances only
inside a live collector invocation.

### Restart proof already observed

After the initial state reached `RUNNING`, the service was deliberately
restarted during the first ON phase. The service manager replaced both the
supervisor and collector processes. The new collector reopened the existing
state with:

- status still `RUNNING`;
- zero completed cycles, because the interrupted ON/OFF pair was not promoted;
- the same 259,200-second target;
- the same 15-second parse deadline;
- the same durable working copy;
- no terminal failure and no input mismatch.

The supervisor log recorded a second “starting or resuming” event and the run
continued. This proves controlled process-stop recovery. The service is
configured to start after a host reboot, but a physical reboot is not claimed as
observed evidence until one actually occurs and the post-boot checkpoint is
verified.

## Setup corrections preserved as evidence

Two fail-closed setup corrections occurred before the durable run began.

First, the harness rejected an output directory whose inferred runner root also
contained the evidence directory (`output_unsafe`). No soak state was created.
The frozen runner was moved to a separate root while preserving the repository
layout expected by the harness.

Second, a provisional service rooted in a protected user-document directory was
blocked by macOS privacy controls before it could open its supervisor script.
The service, candidate environment, frozen runner, source copy, working copy,
and evidence were moved to durable user application-support storage. The final
service then reached `running` and launched the collector successfully without
requiring broad filesystem permissions.

Neither rejected setup contributed a cycle, a duration, or release evidence.

## Completion and publication rules

The machine-readable soak gate wrote terminal `PASS` after 259,225.349 observed
seconds (25.349 seconds beyond the 259,200-second target). The result records:

- 415 completed ON/OFF cycles and 831 recorded attempts;
- 415 passing subtree checks and 415 passing synthetic CRUD checks, with zero
  subtree checks skipped;
- unchanged source Markdown throughout the working-copy qualification;
- source count stable at 1,014 and indexed count between 1,005 and 1,010;
- RSS between 101,600 and 138,160 KiB; probe times between 2,622.379 and
  516,384.345 ms;
- the same candidate provenance and wheel-binding digests stated above.

The controlled process-restart proof described above remains valid evidence of
checkpoint recovery. No physical-reboot observation is claimed.

No RC default change, release tag, or stable-release claim follows
automatically from this run. Even a passing result closes only the exact-beta
real-vault qualification row in Gate A.
