---
type: Document
---
# Beta evidence reproducibility root-cause analysis — draft

**Status:** investigation draft, 2026-07-23. This is a sanitized quality artifact, not a release note, a beta decision, or a claim that the current candidate is releasable. The release decision remains [`issue-bodies/v2-beta-readiness.md`](issue-bodies/v2-beta-readiness.md); the historical experiment record remains [`V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md`](V2_ALPHA_BETA_EXPERIMENT_EVIDENCE.md).

## Decision and scope

The current candidate evidence is not sufficiently reproducible to close the installed-wheel or soak gates. The observed r4 run remains useful as a historical behavior observation, but it cannot prove that a future wheel built from the same revision has the same contents or that the long-running soak exercised that exact wheel.

This investigation is limited to artifact construction and private beta-evidence collection. It does not change the default-off Shadow contract, product page-parse timeout, vault authority, or runtime behavior.

## Confirmed evidence

### Non-hermetic artifact discovery

The packaging configuration includes package data from `frontend/dist` and uses setuptools package-data discovery. The source distribution manifest also grafts `src` and `frontend/dist`. At the same time, the worktree can contain ignored incremental artifacts: bytecode, `build/lib`, `*.egg-info` including `SOURCES.txt`, and `frontend/dist`.

Those inputs are outside version control but can still be discovered or reused by an incremental build path. Therefore, the same commit can yield different wheels when stale bytecode, a stale build tree, stale source-list metadata, or a locally generated frontend bundle differs. A clean Git status is not proof that the release artifact is reproducible.

### Soak harness evidence loss

The soak collector has five coupled defects.

| Finding | Observed behavior | Consequence |
| --- | --- | --- |
| Wrong OFF-path import | The flag-off probe imports `shadow_db_path` from the configuration module although the symbol belongs to the connection module. The resulting import error occurs before the probe assertions. | The intended flag-off no-op observation is not collected, and the generic failure path hides the deterministic cause. |
| Generic process failure | Any non-zero child exit becomes one generic `probe_failed` category. | The evidence loses phase, exit status, and a privacy-safe failure class needed to distinguish launch, import, assertion, and payload failures. |
| Terminal zero-cycle state | A failure before the first completed trend writes terminal `FAIL` state, re-raises, and does not emit the normal result/summary artifact. | The run is neither resumable nor reviewable as a completed failed attempt. |
| Lost phase evidence | OFF and ON payloads are merged into one cycle result; the trend and summary retain only aggregate fields. | A reviewer cannot tell which phase ran, which phase failed, or whether an OFF-only condition was observed. |
| No wheel-to-soak binding | The wheel collector records its wheel SHA-256, while the soak input identity is derived from the candidate interpreter and does not carry a wheel digest. | A passing soak cannot be shown to have executed the same artifact as the installed-wheel gate. |

## Root cause model

### Fault tree and 5 Whys

**Top event:** beta evidence can be accepted, rejected, or repeated without a reliable answer to “which artifact ran and what happened?”

- **Artifact branch:** ignored local build products remain eligible to influence discovery or incremental reuse.
  - Why? Version control ignores build outputs, but the build boundary does not independently construct and attest its complete input set.
  - Why does that matter? The wheel is treated as a release identity even when its contents are not proven to derive only from the tracked revision and declared generated inputs.
- **Observation branch:** the soak collapses phase and child-process detail into one boolean-shaped cycle result.
  - Why? The OFF phase can fail before its assertions because it imports `shadow_db_path` from the wrong module, while the runner uses a generic non-zero failure category and combines OFF/ON dictionaries before persistence.
  - Why does that matter? Evidence required to falsify a probe hypothesis is discarded before the state and summary are written.
- **Lifecycle branch:** an early failure is terminal but lacks a terminal failed-attempt record.
  - Why? The failure path only calls the normal finisher after at least one trend exists.
  - Why does that matter? A zero-cycle failure cannot be inspected, compared, or intentionally restarted under an explicit new-attempt identity.

### TRIZ analysis

**Contradictions.** The release process wants a convenient local build and a strictly reproducible artifact; it wants a compact, privacy-safe soak summary and enough diagnostic detail to falsify a failure; it wants resumability for a 24-hour soak and unambiguous terminal failure semantics. These are process contradictions, not Shadow-runtime contradictions.

**Ideal final result (IFR).** One declared source revision and build profile produce one attestable artifact identity. Every wheel, installed-wheel probe, and soak attempt carries that identity. Each phase emits a bounded, sanitized result, including zero-cycle failure. A release gate can only consume a complete evidence chain and never needs raw vault content or private paths.

**Separation principles.** Separate ignored developer convenience artifacts from release inputs by condition (only an isolated build directory is eligible) and in space (a declared frontend input snapshot is copied into the build context). Separate diagnostic detail from private data by condition (store phase, error class, exit status, bounded digest/length; never raw output or paths). Separate resumable work from a terminal decision in time (a heartbeat remains resumable only while `RUNNING`; a failed attempt is immutable and a retry receives a new attempt identity).

**Function model.** The key substances are the source revision, generated frontend input, build metadata, builder, wheel, installed environment, probe phases, and evidence store. The build/discovery field currently permits unintended local artifacts to affect the wheel. The subprocess-result field currently converts distinct OFF/ON outcomes into one generic failure. The corrective functions are: construct a sealed build input, attest a wheel identity, preserve per-phase sanitized events, and bind every downstream record to that identity.

**Trimming.** Remove stale build trees, bytecode, egg-info source lists, and undeclared frontend output from the release-input decision rather than attempting to validate every possible residue. Remove the aggregate-only cycle record as the sole source of truth; derive its summary from phase records. Remove implicit interpreter-only provenance from the soak gate; require the wheel identity that the interpreter installed.

**Contradiction matrix guidance.** For reliability versus build convenience, prioritize Principle 10 (preliminary action), Principle 11 (beforehand cushioning), and Principle 23 (feedback): prepare a clean staging area, fail on an incomplete input manifest, and record the resulting digest. For observability versus privacy, use Principle 2 (taking out), Principle 24 (intermediary), and Principle 35 (parameter change): extract non-sensitive failure metadata through a sanitizer with bounded fields. For continuity versus correct terminal state, use Principle 15 (dynamics), Principle 20 (continuity of useful action), and Principle 27 (short-lived disposable object): preserve immutable attempt events while allowing a new attempt rather than mutating a failed one into a resumed pass.

## Reusable protocol

1. **Prepare a sealed build input.** Start from a clean checkout or a generated staging directory. Declare every generated input, including the frontend bundle, and reject `build/`, bytecode, egg-info, cached source lists, and unaccounted generated output.
2. **Build twice under the declared profile.** Record revision, build profile, input-manifest digest, wheel SHA-256, and normalized package inventory. With deterministic build settings the wheel digests must match; otherwise the normalized package inventory must match and the discrepancy must fail investigation rather than be silently accepted.
3. **Install by exact artifact identity.** The wheel gate records the wheel SHA-256 and installed-package provenance. The soak accepts that same SHA-256 (and, if needed, the signed local artifact path) as required input and verifies it before the first probe.
4. **Persist phase events before aggregation.** Record OFF, ON, restart, recovery, and probe-launch events separately. Each event carries attempt ID, cycle, phase, status, bounded failure category, exit status when available, elapsed time, and the artifact identity; it carries no vault content, paths, titles, UUIDs, prompts, or raw process output.
5. **Make failures first-class terminal evidence.** On any failure, write a sanitized result and summary even at cycle zero. Mark that attempt terminal and require an explicit new attempt ID for retry; a heartbeat only resumes a matching `RUNNING` attempt.
6. **Consume the chain, not isolated green checks.** The release decision accepts an installed-wheel or soak result only when its artifact identity matches the sealed-build record and all required phase events are complete.

## Evidence falsification and acceptance checks

| Hypothesis to falsify | Required check | Passing result |
| --- | --- | --- |
| Ignored residue cannot alter the artifact | Seed stale bytecode, build output, egg-info source metadata, and a different local frontend bundle outside the declared build input; rebuild twice. | The sealed build either produces the same attested wheel/package inventory or rejects the undeclared input. |
| Flag-off proves no-op behavior and preserves its failure evidence | Run the OFF phase with `shadow_db_path` resolved from its connection boundary, then inject a deliberate OFF import failure against a prepared working copy. | The normal phase verifies that the rebuild call is a no-op while the flag is disabled and leaves the observed state unchanged; the injected failure records the OFF phase and its bounded import-failure class. |
| A child failure remains diagnosable without leaking private data | Force distinct OFF and ON import/assertion/timeout failures. | Each writes the correct phase, bounded class, exit status where available, and an immutable failed attempt result. |
| Zero-cycle failure is reviewable and retry-safe | Force the first phase to fail before any trend is recorded, then invoke the collector again. | A terminal failed result exists; retry requires a new attempt and cannot masquerade as a resume. |
| The soak ran the assessed wheel | Run the wheel gate and soak with mismatched wheel digests. | The soak refuses the mismatch; a matching run repeats the digest in every result and final summary. |

## Follow-up architecture

Implement the remediation as two narrow, testable boundaries.

- **Artifact identity boundary:** a clean build-input snapshot, normalized package inventory, wheel digest, and installer provenance record. The wheel gate becomes the producer of this immutable identity.
- **Evidence attempt boundary:** an immutable attempt record with per-phase events and explicit state transitions (`RUNNING`, `PASS`, `FAIL`, `ABORTED`). The soak is a consumer of the artifact identity and cannot begin without it.

The release decision should consume only these two records plus the existing sanitized gate checks. This keeps build determinism, private evidence handling, and Shadow runtime behavior separate, while making future release investigations repeatable.

## Follow-up order

1. Add focused contract tests for sealed artifact inputs, OFF-path isolation, phase-level failure records, zero-cycle terminal results, and wheel-to-soak mismatch rejection.
2. Implement the artifact identity and evidence-attempt boundaries without changing the product’s default-off runtime behavior.
3. Rebuild from the corrected sealed input, rerun the installed-wheel gate and the minimum sanitized soak, then update the beta-readiness decision with only the sanitized outcomes.
