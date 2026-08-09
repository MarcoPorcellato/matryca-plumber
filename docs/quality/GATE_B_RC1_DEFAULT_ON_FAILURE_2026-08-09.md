# Gate B rc.1 default-on failure and rc.2 remediation

## Purpose

This record preserves the fail-closed disposition of the
`matryca-plumber==2.0.0rc1` default-on Gate B soak, the independently
successful Read Only profile, the diagnosed harness defect, and the mandatory
qualification boundary for `v2.0.0-rc.2`.

It is an incident and remediation record, not a stable-release approval.

## Decision summary

- The `read-only-external` rc.1 profile reached terminal `PASS`.
- The `default-on` rc.1 profile did not complete and must never be reported as
  `PASS`.
- The failing default-on LaunchAgent was stopped after the evidence was frozen.
- The stopped attempt is preserved under the private archive identifier
  `default-on-failed-20260809T084618Z`.
- The live Shadow SQLite database was not repaired or edited.
- No rc.1 elapsed time or attempt history may qualify rc.2.
- A fresh exact-artifact dual-profile soak is required for the published rc.2
  wheel.

## Exact rc.1 bindings

| Item | Binding |
|---|---|
| Candidate | `matryca-plumber==2.0.0rc1` |
| Public wheel SHA-256 | `f9c60cc89049b9524ca9f9346a053bac3c7aba6f2186d9a31a3993bd7a9253cd` |
| Runner commit | `1e8805ec99c6471549ecf36e4a261a31013a0f6f` |
| Qualifier SHA-256 | `b4cee6a2b6c8a8fbd8bb890cf583b7d126f2e40bda8b55cb7a0c499c8490dbe6` |
| Supervisor SHA-256 | `bfcae04483a5003df8e83fb52ece42c0c933d7c708c9e73d55733309736e7445` |
| Deployment manifest SHA-256 | `0d6ab04010707b0e40987f998b7fd01bba06cea460d0fb93634449abdd9c6b06` |

## Frozen profile outcomes

### Read Only external cache

The profile reached terminal `PASS` with:

- 412 completed cycles;
- 824 recorded phase attempts;
- 259,465.833 observed valid seconds;
- the duration target reached;
- unchanged source Markdown;
- the expected candidate provenance and wheel-binding digests.

### Default-on

The profile was stopped and archived with:

- status `RUNNING`, which remains non-terminal;
- 239 completed cycles;
- 149,454.297144625 valid seconds;
- 3,274 chained attempts;
- 478 `PASS` attempts followed by 2,796 `FAIL` attempts;
- last failure category `probe_flag_on_failed`;
- no `soak-result.json`, therefore no terminal result;
- frozen attempt cursor
  `c4599e53789ca5705e18070f6234429292cdd830dd03494779cf328a1229019a`.

The archive copy was checked byte-for-byte against the stopped source files.
Its attempt chain was loaded successfully by the exact archived runner.

## Root cause

At `2026-08-07T09:13:19Z`, the synthetic default-on fixture produced one
bounded `parse_timeout`. Shadow correctly quarantined that fixture rather than
serving an unproven page.

The probe then failed before renaming the fixture. Its `finally` block removed
both possible Markdown files but sent the Shadow deletion event only for the
renamed path. The original fixture's quarantine row therefore remained after
the file had disappeared.

The resulting database was internally readable and passed SQLite
`quick_check`, but its health accounting was inconsistent:

- source-page metadata: 1,014;
- indexed-page metadata and rows: 1,009;
- quarantine metadata: 5;
- actual quarantine rows: 6;
- orphaned synthetic fixture rows: 1.

The health invariant consequently evaluated as `STALE`. Every resumed
default-on probe failed before it could contribute another valid phase, while
the supervisor correctly credited neither failures nor downtime.

This was a qualification-harness cleanup defect triggered by a real bounded
timeout. It was not evidence of source-vault mutation or SQLite corruption.

## Parser 1.7.1 investigation

The same synthetic block shape was exercised with
`logseq-matryca-parser==1.7.1` through Matryca's bounded Stack-Machine worker:

- 500 deterministic randomized persistent-worker parses: 0 failures;
- maximum parser-reported duration: 0.39495 seconds;
- p95 parser-reported duration: 0.0036664 seconds;
- 50 fresh interpreter and worker lifecycles: 0 failures;
- maximum lifecycle duration: 4.454969 seconds;
- p95 lifecycle duration: 3.420434 seconds.

The one-off rc.1 timeout was not reproduced. Parser 1.7.1 remains required for
rc.2, but these synthetic results do not convert the historical rc.1 timeout
into a pass and do not replace a real-vault soak.

## Remediation

The rc.2 qualifier must:

1. unlink both the original and renamed fixture files;
2. send idempotent Shadow deletion events for both paths;
3. prove with regression coverage that a failure before rename clears the
   original quarantine row;
4. prove that Shadow health returns to `READY` once the synthetic fixture is
   gone;
5. preserve privacy-safe failure categories and exact attempt-chain behavior;
6. preserve the stopped rc.1 archive unchanged.

Manual deletion of the live quarantine row is explicitly prohibited because it
would alter the failed attempt and would not fix the reproducible harness
defect.

## Implementation and verification snapshot

The prepared correction adds the missing idempotent deletion event for the
original fixture path while preserving cleanup of the possible renamed path.
Its regression test forces a bounded failure before rename, confirms that the
original fixture enters quarantine and makes Shadow health `STALE`, executes
the exact embedded probe cleanup, and then proves all of the following:

- the original quarantine row is gone;
- neither synthetic fixture path remains on disk;
- quarantine metadata and rows are coherent;
- Shadow health has returned to `READY`.

The combined parser 1.7.1 and qualifier candidate was checked with:

- 16 focused Gate B and supervisor tests passing;
- the focused Shadow quarantine, bootstrap, bounded-parse, AST-cache, and graph
  suites passing;
- 1,709 full-suite tests passing and 5 skipped with four workers;
- the single process-inspection test blocked by the local sandbox passing when
  rerun with normal process-inspection access;
- formatting, lint, typing, graph-read sandbox, version consistency, agent
  coherence, documentation governance, generated-prompt integrity, and the
  project coverage threshold passing;
- graph-based change analysis reporting low risk against the current remote
  default-branch base.

The historical timeout investigation and these checks qualify the correction
for review. They do not qualify an unpublished artifact or close Gate B.

## Publication boundary

At the verification checkpoint on `2026-08-09`, the prepared correction had no
remote branch or pull request and no `v2.0.0-rc.2` GitHub Release existed.
Commit, push, pull-request creation, merge, tag creation, GitHub Release
publication, and package-index publication remain distinct maintainer actions.

The dual-profile rc.2 soak cannot start until a public wheel exists and its
digest and installed `RECORD` have been independently bound. No local build or
source checkout may substitute for that exact public artifact.

## rc.2 qualification contract

After the parser 1.7.1 integration and qualifier correction are merged:

1. freeze one rc.2 candidate commit;
2. build and publish `v2.0.0-rc.2`;
3. bind each profile to the exact public wheel digest and installed `RECORD`;
4. start fresh isolated `default-on` and `read-only-external` attempts;
5. count only measured successful probe time;
6. require terminal `PASS` from both profiles;
7. complete every remaining Gate B row before stable `v2.0.0`.

The rc.1 Read Only pass and partial default-on run remain supporting evidence
only. They are not transferable qualification credit.

## Related records

- [Gate B RC soak runbook](GATE_B_RC_SOAK_RUNBOOK.md)
- [v2.0.0 RC and stable readiness](issue-bodies/v2-rc-stable-readiness.md)
- [Shadow DB architecture](../knowledge/architecture/shadow-db.md)
