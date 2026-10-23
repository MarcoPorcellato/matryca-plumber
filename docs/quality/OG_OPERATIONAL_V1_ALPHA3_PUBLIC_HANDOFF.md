---
type: Audit
title: Alpha.3 public OG producer handoff
description: Immutable producer bytes and independently reviewed experimental OG qualification evidence for owner evaluation.
resource: docs/quality/
tags: [graph, operational-profile, qualification, provenance]
audience: [maintainer, contributor, operator, agent]
last_verified: 2026-10-23
stale_after: 2027-04-21
status: stable
classification: active
owner: quality
---

# Alpha.3 public OG producer handoff

## Disposition and limits

**Accepted bounded experimental evidence, not Trama admission or stable support.**
The original public `2.1.0a3` wheel and source distribution passed eight installed
rows on Linux x86_64/macOS arm64 with CPython 3.12.14/3.13.15. The offered
capability is offline or quiescent OG graph identification and complete ordered,
content-free topology. Text and properties require a separate payload profile.

The packaged `plumber.og.operational/v1` descriptor remains **unqualified** and
its rows remain **planned**. This timestamped external evidence neither edits
those flags nor creates a runtime contract. Trama #2/ADR-0007 owns consumer
admission. No real Trama adapter or consumer run is admitted by this record.

The [machine-readable record](evidence/og-operational-v1-2.1.0a3-public.json)
binds all artifacts, reports, runtime rows, resources and evidence limits.

## Immutable producer and separate verifier

| Role | Exact binding |
| --- | --- |
| Original producer S | `8c30f70e217722e719c5aedc322219ebccb87e68` |
| Original producer tree T | `de80d0473aa281c52d0fed10b4561024dd12d76f` |
| Signed tag | `v2.1.0-alpha.3` |
| Tag object | `c093e9e8aa735b7c37a0c1a56a601a9c31cbdf24` |
| Original publisher R | [39887297548, attempt 1](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/39887297548) |
| Public-byte campaign Q | [39999081040, attempt 1](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/39999081040) |
| Recovery verifier V | `15a79076932491b588cedc43f5e6497edc87e16b` |
| Verifier tree | `055004897d5adbbec480ad8f5095f10a0f6368af` |

The documentary handoff uses V as its parent, not as a new producer source.
The [exact S-to-V comparison](https://github.com/MarcoPorcellato/matryca-plumber/compare/8c30f70e217722e719c5aedc322219ebccb87e68...15a79076932491b588cedc43f5e6497edc87e16b)
contains only ten verifier/workflow/test/release-guidance paths, enumerated in
the machine record. Runtime packages, contracts, packaged resources, frontend
inputs, project metadata, root/build/frontend locks and the canonical builder
did not change. Its retained response SHA-256 is
`532ffc23fba8c43c89362a8d392474d1121c995d6e61992be26e856ce3e327ae`.
Do not build from the handoff tree and relabel those bytes as the originals.

## Original public packages

The [original prerelease](https://github.com/MarcoPorcellato/matryca-plumber/releases/tag/v2.1.0-alpha.3)
contains exactly six assets. The machine record lists their IDs, sizes,
original release-download URLs and SHA-256 values, together with the two non-yanked,
byte-identical PyPI originals.

| Original distribution | Bytes | SHA-256 |
| --- | ---: | --- |
| `matryca_plumber-2.1.0a3-py3-none-any.whl` | 756,248 | `e5bc586a3da76d8e11760b39c9d7ac45b62b1240f085a8a96a573b9902bfea12` |
| `matryca_plumber-2.1.0a3.tar.gz` | 1,050,099 | `cbf6f47dece7266c0ec69820ca3ef84e6519ff5d12f5d057c851e5b9c453ed9c` |

All six public subjects passed hosted cryptographic attestation verification,
including original source, signer, tag, repository/owner, hosted runner,
push trigger and publisher invocation. The six subject checks share one
multi-subject attestation bundle; they are not six independent signatures.
Independent review inspected authenticated retained outputs, not a new local
signature-verification run. No package bytes were executed locally.

## Observed qualification

All eight Q jobs succeeded without skips. Eight report archives matched their
exact same-run IDs, sizes and SHA-256 values; all 51 member inventories and
cross-report bindings were checked independently of the workflow badge.

| Platform and interpreter | Original wheel | Original sdist |
| --- | --- | --- |
| Linux x86_64, CPython 3.12.14 | PASS | PASS |
| Linux x86_64, CPython 3.13.15 | PASS | PASS |
| macOS arm64, CPython 3.12.14 | PASS | PASS |
| macOS arm64, CPython 3.13.15 | PASS | PASS |

Each row contains full metadata/RECORD/resource/dependency verification,
non-editable installed-origin evidence, three static TCK outcomes, all thirteen
operational controls and verified cleanup. Parser compatibility is limited to
the exact hash-locked producer profile with `logseq-matryca-parser==1.9.0`;
this does not add a Parser dependency to Trama or qualify another version.

The four original-sdist rows used distinct, independently provisioned locked
CPython 3.12 builders, including the rows installed into Python 3.13 runtimes.
Complete before/after package inventories, requirement satisfiers, provisioning
records and temporary-wheel hashes are bound separately from public originals.

Q also passed 38 source/JUnit cases without failure, error or skip. Windows
proved refusal with exit 7 before any graph access; it is not installed Windows
support. The separate [source campaign D](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/39831820252)
contains 800 native macOS stress controls with zero cleanup failures. D is
source evidence and never substitutes for public-byte lifecycle controls.

Independent result review returned **PASS_WITH_NOTES**. The descriptor remains
unqualified; the result is bounded experimental evidence only. Raw report
archives have finite retention, recorded in the machine record. Preserve their
bytes for later auditing rather than assuming their download links last
indefinitely. Earlier failed campaigns remain preserved; Q is a distinct
successful campaign, not a rerun or reinterpretation of them.

## Invocation and lifecycle responsibility

A future, separately admitted consumer must use an explicitly selected producer
environment, not import Plumber or Parser into its own process. Authenticate
the descriptor independently and provision the complete exact hash-locked
profile, installing only the authenticated original package without dependency
resolution. The accepted producer-side invocation shape is:

```text
/absolute/operator-venv/bin/python -I -B -m matryca_plumber.graph_gateway snapshot --graph-root DIR --expect-descriptor-sha256 HEX
```

The exact descriptor SHA-256 is
`bcc6ac607706e934e5df4e044802aa74c7d7455e7711220df116080f1ab0cc70`.
DIR is an explicit canonical root, never ambient discovery. This is operator
interface documentation, not authorization to open a user graph.

The consumer owns incremental 4 MiB stdout/512-byte stderr limits, a 180-second
execution deadline and five-second total finalization. Cleanup requires the
direct child to be reaped, process-group absence observed as ESRCH within that
deadline, and every reader, stream and selector gate to pass. EPERM is a
retained observation, never cleanup success. Exceptions and deadline failures
must retain primary errors and cleanup observations. Exit 4,
`source_rejected`, is non-retryable. Audit hooks remain best-effort event
rejection, not an operating-system sandbox.

## Security and excluded claims

Two development-only frontend alerts, #103 and #104 for
`@vitest/mocker 5.0.1`, remained open. The maintainer's exception covered only
M6's Python-only OG qualification of these unchanged original packages and
provenance. That campaign did not execute frontend, development-server or
mock-server code. This handoff records the exception; it does not extend it or
claim repository-wide security clearance.

No payload/text/properties, native DB, user graph, physical namespace-file
qualification, writes, events, sync, UI, active-desktop coexistence, installed
Windows, stable-support or full RC4/Stage A/Gate B claim is included.
Trama profile admission and real adapter implementation remain separate owner
decisions. See [the prepared package boundary](OG_OPERATIONAL_PACKAGE.md),
[the alpha.3 qualification plan](V2_1_0A3_RELEASE_QUALIFICATION_PLAN_2026-10-22.md)
and [release authority](../RELEASE_PROCESS.md).
