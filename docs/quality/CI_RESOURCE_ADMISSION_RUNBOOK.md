---
type: Guide
title: Local resource-admission coordinator runbook
description: Evidence-bound admission, interruption, ticket, workspace-lock, and journal handling for expensive local qualification work.
last_verified: 2026-08-19
stale_after: 2026-11-17
status: active
classification: active
owner: quality
authority: local-resource-admission
schema_version: "1.0"
receipt_schema_version: "1.0"
journal_schema_version: "1.0"
---

# Local resource-admission coordinator runbook

This runbook defines the public contract for the **local resource-admission
coordinator**. It is operational support for deciding whether an expensive
local check may start and how an interrupted attempt is handled. It is not a
Matryca release gate, artifact verifier, CI result, package qualification,
platform qualification, or external/identity qualification.

The coordinator may hold work, cancel it safely, or preserve recovery evidence.
It cannot turn a local pass into release evidence, and it cannot authorize a
publication or an external review outcome.

## Admission policy

The only enforced policy described here is the local macOS `macos-v4` profile.
All thresholds are evaluated from one bounded observation and recorded with the
decision.

| Signal or rule | `macos-v4` contract |
| --- | --- |
| Available memory | At least 20% |
| Reclaimable uncompressed memory | At least 3 GiB |
| Swap | At most `min(8 GiB, 30% of physical RAM)` |
| Compression | Advisory by itself; at least 70% denies only when another pressure signal is present |
| Unknown or denied state | Fail closed; do not start or resume the guarded run |
| Watchdog | 2 seconds |
| Soft cancellation | Two converging pressure signals across 15 samples, approximately 30 seconds |
| Critical pressure | Immediate cancellation and recovery handling |

Compression alone is not a denial. Missing, malformed, stale, or contradictory
measurements are `unknown`, not an implicit admission. A positive decision is
valid only for the bounded attempt and observation that produced it.

Linux and Windows are `unsupported_not_enforced`. They have no platform
qualification through this coordinator, and a local result on either platform
must not be represented as enforcement or support evidence.

## Admission and execution sequence

1. Identify the exact source commit, configuration, runtime, checks, output
   root, and redaction policy for the proposed attempt.
2. Acquire a ticket using the operating system's advisory lock semantics. The
   ticket is coordination metadata, not proof that the host is admitted.
3. Collect the bounded `macos-v4` observation. Record `admit`, `deny`, or
   `unknown`; treat `deny` and `unknown` as a hold.
4. Start only when the decision is `admit`. Keep memory-heavy work serialized or
   bounded and retain the attempt identity across checkpoints.
5. Run the 2-second watchdog. A soft cancellation requires the two converging
   signals and 15 samples; a critical signal cancels immediately.
6. On cancellation, interruption, reboot, or watchdog expiry, checkpoint the
   reason and classify the journal before any resume. Resume only from a
   validated checkpoint with a fresh admission decision.
7. Release the ticket and preserve the journal, receipt, and any quarantine
   records. Never rewrite an earlier attempt to make it appear continuous.

Setup, preflight, downtime, an interrupted attempt, and an unqualified local
pass do not count as release, artifact, CI, or platform qualification.

## Tickets and workspace locks

Tickets use operating-system-released advisory locks. Only a ticket that meets
the coordinator's explicit stale-ticket criteria may be reclaimed. A timeout,
reboot, or missing process record alone does not authorize arbitrary deletion.

An `active: true` status is a bounded snapshot that the platform-wide admission
slot was busy when sampled. It does not identify a process, command, repository,
user, or path, and it is not durable proof that a named process remains alive.
When the state is ambiguous, preserve the status record and hold the next heavy
run rather than deleting coordinator state or assuming the slot is free.

Workspace locks have no automatic stale deletion. If a workspace lock appears
stale, stop, preserve its state, and use the documented recovery or maintainer
decision path. Do not remove it merely to make a subsequent run start.

The coordinator must not claim mutual exclusion beyond these local advisory
locks. It does not establish a distributed lock, a CI reservation, or an
external-provider guarantee.

## Receipt and journal boundaries

Resource/admission records use schema `1.0`. Qualification receipts and
interruption journals use schema `1.0`.

Qualification receipts bind:

- source commit;
- configuration and runtime identity;
- the checks actually run and their terminal results; and
- the applied redaction policy.

Those receipts do **not** bind admission state or host telemetry. Admission and
host observations remain operational context and must not be presented as
source, artifact, CI, or release evidence. A receipt that lacks one of its
required bindings is incomplete and cannot qualify the associated claim.

An incomplete journal is classified as `incomplete`, then recovered or
quarantined according to the available checkpoint and integrity evidence. The
process must not delete evidence, truncate the journal, or silently convert an
incomplete attempt into a pass. If recovery cannot establish a valid
continuation point, quarantine the attempt and start a new attempt chain after
fresh admission.

## Decision and recovery checklist

- [ ] Exact source commit and attempt identity are recorded.
- [ ] Configuration, runtime, checks, and redaction policy are recorded.
- [ ] The platform is macOS and the `macos-v4` profile is selected.
- [ ] All required measurements are known and meet the thresholds.
- [ ] `unknown` or `deny` is held fail closed.
- [ ] Watchdog, soft-cancellation, and critical-signal handling are enabled.
- [ ] Ticket and workspace-lock state is preserved.
- [ ] Any interruption is journaled without deleting prior evidence.
- [ ] Resume uses a validated checkpoint and a fresh admission decision.
- [ ] The final claim remains bounded to the exact source, artifact, runner, and
      terminal evidence required by its owning release or CI gate.

## Limitations

This coordinator does not inspect or certify remote CI, package registries,
release publication, identity, external providers, or neutral ecosystem review.
It is a local operational aid whose `admit` result is necessary for selected
expensive work but never sufficient for a Matryca qualification decision.
