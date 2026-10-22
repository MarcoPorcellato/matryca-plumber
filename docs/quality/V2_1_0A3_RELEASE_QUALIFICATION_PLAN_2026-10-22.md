---
type: Roadmap
---
# Experimental 2.1.0a3 release qualification plan

Date: 2026-10-22. Status: **active preparation policy; no final source,
publication or consumer admission is selected by this document**.

## Authority and preserved history

This plan replaces the [alpha.2 plan](V2_1_0A2_RELEASE_QUALIFICATION_PLAN_2026-10-19.md)
only as the active preparation policy. That plan, the alpha.2 signed tag,
published assets and failed public-qualification evidence remain unchanged.
The [alpha.1 plan](V2_1_0A1_RELEASE_QUALIFICATION_PLAN_2026-10-16.md) and its
[failed publication](../releases/v2.1.0-alpha.1-FAILED-PUBLICATION.md) also remain
historical evidence. Do not rerun, replace, retag or manually repair either
older release as part of alpha.3.

The [release process](../RELEASE_PROCESS.md), the
[risk-based decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md),
[Plumber #582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582)
and the [RC4 supersession record](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md)
remain controlling. The complete delta is **Tier 3**. Experimental POSIX
qualification does not waive Windows, full three-platform Stage A, the separate
dual-profile Gate B or the later stable-support decision.
[Trama #2](https://github.com/MarcoPorcellato/matryca-trama/issues/2) owns
independent consumer admission.

The exact active policy is `og-alpha3`, package version `2.1.0a3`,
prospective signed tag `v2.1.0-alpha.3` and literal changelog heading
`[2.1.0-alpha.3]`. Historical internal `alpha1_*` filenames and alpha
subcommands remain unchanged. The policy rejects alpha.1, alpha.2, future
versions and caller-defined version expressions. Legacy RC4 defaults remain
unchanged.

## Recovery delta and evidence boundary

[PR #646](https://github.com/MarcoPorcellato/matryca-plumber/pull/646)
landed the macOS process-cleanup repair before this version preparation.
An EPERM group-signal result is an observation, never successful cleanup.
Success still requires the direct child to be reaped, group absence proved by
ESRCH within the existing deadline, and every selector, reader and stream gate
to pass. Exceptions, deadline failures and incomplete cleanup promote retained
observations to failure events. Non-EPERM failures, escalation timing, group
state mapping and negative controls remain fail-closed.

The repair's [source diagnostic run](https://github.com/MarcoPorcellato/matryca-plumber/actions/runs/39818389700)
passed all eight installed rows. Its native macOS stress reports contain 200
stdout-overflow and 200 stderr-overflow controls per runtime: CPython 3.12.14
observed one EPERM and CPython 3.13.15 observed three, with zero cleanup failures
in those 800 controls. This finite observation supports the repair; it does
not prove every race impossible, qualify alpha.3 or replace its later
actual-public-byte campaign. Earlier failed runs remain failures.

This preparation changes only active version/policy bindings, the root package
version and its derived resource digests, matching tests and release guidance.
Freeze all dependency selections, including exact Parser 1.9.0, and both
independent build/frontend locks. Native export and packaged requirements,
schemas, fixtures, topology golden, TCK cases, producer semantics, module
digests, finite bounds and qualification flags remain unchanged from the
merged repair source. Descriptor status stays `unqualified` and runtime
entries stay `planned`, even after a separate source campaign passes.

## Declared operational profile

- Profile: `plumber.og.operational/v1`; offline, quiescent `og_markdown`
  with an explicit synthetic root and no concurrent writer.
- One shell-free invocation through a dedicated, verified installed interpreter:

  ```text
  /absolute/operator-venv/bin/python -I -B -m matryca_plumber.graph_gateway snapshot --graph-root DIR --expect-descriptor-sha256 HEX
  ```

- One capture returns the unchanged `plumber.graph.read/v1` identity and
  `plumber.graph.topology/v1` complete, ordered, content-free topology.
  Authenticate the installed descriptor independently; a self-reported
  `describe` response or static catalog is not operational evidence.
- Provision the complete hash-locked Parser 1.9.0 runtime profile using
  `--require-hashes`, then install only the authenticated public wheel with
  `--no-deps`. Verify metadata, installed files, resources, import origins
  and both static and operational TCKs. The broad application Parser range,
  unconstrained installation and ordinary quick start do not qualify this
  exact operational profile.
- Preserve the producer's tested best-effort audit-event rejection and startup
  self-check. They are not an OS sandbox. Consumer process-group ownership,
  incremental output limits, unconditional finalization and separate primary
  and cleanup errors remain mandatory.
- No page/block text, typed properties, DB, direct SQLite, Shadow ingestion,
  writes, events, sync, UI, generic query, user graph or active-desktop
  coexistence claim. Trama is a consumer, never a second Parser gateway.
  Physical namespace-file qualification remains deferred.

## Fresh source, canonical build and installed matrix

After this preparation and all required main CI gates land, select one actual
clean protected-main commit `S` and tree. Record its signed source, complete
delta, descriptor, dependency/resource/fixture/golden/TCK chain and required
hosted checks. No earlier RC4, alpha.2 or repair-PR source is the alpha.3 final
candidate. A separately authorized first-attempt source campaign must use
that exact current-main SHA.

Build once with the canonical Node 22 frontend → normalized original sdist →
original wheel-from-sdist sequence. Use the independent locked CPython 3.12
build environment, record observed tools and source/frontend ledger, and
preserve the original distribution pair and canonical manifest. CPython 3.13
is a tested runtime, not an inferred build interpreter.

| Runtime platform | CPython | Original distribution paths |
| --- | --- | --- |
| Linux x86_64 | 3.12 | wheel and sdist |
| Linux x86_64 | 3.13 | wheel and sdist |
| macOS arm64 | 3.12 | wheel and sdist |
| macOS arm64 | 3.13 | wheel and sdist |

All eight installed rows are required. Each binds actual interpreter patch,
OS/architecture, source/tree, original name/size/SHA-256, resource and
dependency identities, run/attempt/job and cleanup outcomes. Each original-sdist
row authenticates that sdist and builds a temporary wheel in its own separate
locked CPython 3.12 build environment. Record that environment and temporary
wheel without substituting either for the original distribution identity.

Require complete metadata, RECORD, resources, import origins, static TCKs and
operational TCKs on both distribution paths. Run the existing source/JUnit
controls and native Windows refusal control; `unsupported_platform` before
graph access is not Windows installed-package qualification. Keep the bounded
hosted macOS CPU-load stress step: 200 executions of each overflow control per
CPython runtime, zero cleanup failures, exact retained counts and passive
diagnostics. Missing, skipped, failed, stale or incomplete required evidence
is NO-GO.

## Operational and negative controls

Use only provenance-recorded hand-authored synthetic fixtures, without
case-only filename collisions. Verify unique portable IDs, parentage,
depth-first order, contiguous sibling ordinals and complete ordered reference
edges under the existing finite bounds. The portable golden authenticates
`topology.result`, not the session-bearing response.

Verify bindings separately: repeated same-root invocation preserves graph ID,
revision and golden but changes session ID; relocation preserves revision and
golden but changes graph ID; an admitted source-byte change changes revision
and golden. Neither package self-report nor artifact identity replaces these
controls.

Retain invalid-root, symlink/FIFO, UTF-8, unresolved-reference, collision,
bounds, source-change, dependency/platform, descriptor, import-shadowing and
audit-hook negative controls. Prove no synthetic text/property canary leaks
and no graph, bytecode or environment mutation. Exercise timeout, overflow,
surviving descendants and finalization failures with bounded ownership and
retained diagnostics. EPERM with a live group, EACCES, EINTR and EINVAL must
not become successful cleanup.

Local source tests and preparation-PR diagnostics are not substitutes for a
separately selected source or actual-public-byte qualification. No private
observer/controller or new failure-time process probe is required by this
plan; retain the existing reviewed process owner and passive diagnostics.

## Signed publication and actual public bytes

Stop after preparation with a full `S`/tree and qualification handoff. A later
maintainer authorization must explicitly confirm those identities and
acknowledge that pushing `v2.1.0-alpha.3` triggers GitHub Releases and PyPI.
This document, a green PR and a conditional preparation merge authorize none
of those publication actions.

Preserve the reviewed publisher/acquisition graph. Authenticate each pinned
official tool archive and its safe extraction before use; do not override
reserved runner variables. Provision CPython 3.12 explicitly before
no-download consumption. The publisher builds its own canonical pair and
attests six public subjects: original wheel, original sdist, SHA256SUMS,
binding.json, content-ledger.json and canonical-build.json. Retain those six
Release assets and the Actions copy for at least 14 days. Stage only the two
original distributions for PyPI. Diagnostic artifact hashes never substitute
for publisher bytes.

After successful publication run `R`, a separately authorized first-attempt
manual public campaign `Q` must run from the same exact current-main `S`.
Require six exact GitHub assets and two non-yanked PyPI originals, bounded
allowlisted HTTPS acquisition and byte identity against the publisher binding.
Verify cryptographic attestations for all six subjects, including source and
signer digests, exact tag/workflow, hosted runner and the certificate's signed
`R/attempts/1` invocation. A self-declared predicate field is insufficient.

Before successful public admission, validate the source-derived build record,
locked tool/build identities and source/frontend ledger; repeat that validation
during aggregation. Run all eight full installed/operational rows on the
actual public pair, with four independent sdist build environments and complete
source, refusal and cleanup evidence. Retain exact-source stress evidence
separately; it never replaces installed overflow controls on public bytes. Bind actual `Q` jobs and
artifact IDs/digests without replacing them with diagnostic metadata. Any
failure, mismatch, uncertainty or incomplete result stops the campaign; do
not silently rerun or erase consumed attempts.

## Producer handoff and completion

Only a complete reviewed public-byte result may support a sanitized immutable
producer handoff. Bind `S`/tree, `R`, `Q`, public pair and evidence
hashes, attestations, complete supported matrix, exact dependency profile,
invocation/lifecycle limits, fixtures/TCK, negative outcomes and exclusions.
Exclude private paths, raw workstation logs, secrets and graph content.

Trama evaluates those exact bytes under its own #2/ADR-0007 gate. Acceptance
policy, fake-producer tests, static schemas, source CI and package availability
are not compatibility admission or an adapter result. Text/properties require
a separately qualified payload profile. Alpha.3 does not close #582, establish
stable support or complete the transferred Windows/full Stage A/Gate B work.
