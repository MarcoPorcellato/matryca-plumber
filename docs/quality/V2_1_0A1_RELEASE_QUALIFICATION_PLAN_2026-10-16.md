---
type: Roadmap
---
# Experimental 2.1.0a1 release qualification plan

Date: 2026-10-16. Status: **active preparation policy; no final candidate or
runtime qualification is selected by this document**.

## Publication failure and acquisition correction — 2026-10-18

The exact signed alpha.1 tag at source 09f8906e36abd0ec6d29e5d554377fb7b0ba57c5
is preserved. Publisher run 39118762754/1 stopped at acquisition-root preparation,
before build/publication; this is not an installed-package failure. The
[immutable failure record](../releases/v2.1.0-alpha.1-FAILED-PUBLICATION.md)
distinguishes observed results from the inferred failed builtin. Both workflow
families receive the same fresh, independently verified archive acquisition
boundary without reserved runner-variable overrides. The new native lane is
bootstrap-only; existing source/public qualification criteria are unchanged.

The [recovery record](ALPHA_RELEASE_RECOVERY_2026-10-18.md) recommends a separately
approved new alpha candidate. Version migration, fresh final-source qualification,
publication, public-byte verification and Trama admission remain separate. This
historical alpha.1 plan does not itself select or qualify that later candidate.


## Purpose and authority

Deliver the smallest experimentally qualified OG producer suitable for Trama's
independent evaluation: graph identification plus complete, ordered,
content-free topology in one offline process invocation. This plan selects the
experimental alpha gates under the
[release process](../RELEASE_PROCESS.md) and
[risk-based decision](RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md).
The [RC4 supersession record](RC4_TO_V2_1_0_SUPERSESSION_2026-10-16.md)
preserves the separate full qualification track. Work is tracked under
[Plumber #582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582);
consumer admission belongs to
[Trama #2](https://github.com/MarcoPorcellato/matryca-trama/issues/2).

The complete delta is **Tier 3**: parser/graph I/O and process-lifecycle
boundaries change. This limited experimental release does not lower that risk
classification, qualify Windows, waive the later dual-profile campaign or
establish stable support.

## Declared experimental profile

- Profile: `plumber.og.operational/v1`; source mode: offline, quiescent
  `og_markdown`, with an explicit synthetic root and no concurrent writer.
- Namespace: `matryca_plumber.graph_gateway`. The intended shell-free command
  uses a dedicated, verified installed interpreter:

  ```text
  /absolute/operator-venv/bin/python -I -B -m matryca_plumber.graph_gateway snapshot --graph-root DIR --expect-descriptor-sha256 HEX
  ```

- One capture supplies both existing `plumber.graph.read/v1` graph identity and
  `plumber.graph.topology/v1` complete topology. The contracts remain unchanged;
  a static catalog marked `static-only-unqualified` is not runtime evidence.
- The independently verified installed descriptor, not a self-reported
  `describe` response alone, supplies the expected digest. Operational resources,
  dependency locks, fixtures and the TCK must land before final selection.
- First exact Parser profile: `logseq-matryca-parser==1.9.0`. No range,
  intermediate version, later release or optional 1.11.0 profile is qualified.
- The application metadata's broader Parser range is not this operational
  profile. Provision a dedicated environment from the complete hash-locked
  dependency profile with `--require-hashes`, then install the verified public
  wheel with `--no-deps`; verify the installed profile and package before use.
  An ordinary `uvx` or unconstrained package installation is not the gateway
  bootstrap and must not be used as evidence for this exact profile.
- No page/block text, typed properties, DB objects, direct SQLite, Shadow
  ingestion, writes, events, sync, UI, generic query, user-graph or active-desktop
  coexistence claim. Trama remains a consumer, never a second Parser gateway.

The producer's tested audit-event rejection is best-effort protection, not an
OS sandbox. The consumer and installed TCK retain bounded process-group
ownership, incremental output reads, unconditional finalization and separate
primary/cleanup errors, including apparent-success paths with surviving
descendants. Accepted source bytes, bindings and complete results never excuse
an uncertain cleanup.

## Candidate, build and matrix

Land version/policy preparation, operational resources and the reviewed hosted
workflow in short PRs before choosing one clean, reachable, protected-main SHA
and tree. A prior RC4 selection or build is not the alpha candidate. Freeze the
descriptor, resource, dependency-profile, fixture and TCK digest chain from that
exact source and record its full identity and required hosted CI.

Use the canonical Node 22 frontend → normalized sdist → wheel-from-sdist
builder, with a separately locked CPython 3.12 build environment. Record exact
tool versions, artifacts and observed build-environment identities. CPython
3.13 is a runtime row, not an inferred build-environment qualification.

| Runtime platform | CPython | Original distribution paths |
| --- | --- | --- |
| Linux x86_64 | 3.12 | wheel and sdist |
| Linux x86_64 | 3.13 | wheel and sdist |
| macOS arm64 | 3.12 | wheel and sdist |
| macOS arm64 | 3.13 | wheel and sdist |

These are **eight required installed rows**, all initially unqualified. Bind
each exact interpreter patch, OS/architecture, source/tree, canonical artifact
name/size/SHA-256, profile/dependency/resource digests, run and job conclusion.
Windows has a separate refusal-only control (`unsupported_platform` before
graph access); it is not a ninth qualified row or Windows package evidence.

For every row run full installed verification: metadata, `RECORD`, packaged
resources, expected import origins, static contracts/TCKs, and the operational
TCK. An sdist row authenticates the original sdist, builds one temporary wheel
in a separate locked PEP 517 build environment, records the observed environment
and temporary wheel identity, then installs it in the separate runtime
environment. The temporary wheel never replaces the original distribution in
the canonical manifest or sdist verification.

## Required operational and negative evidence

Use only hand-authored synthetic fixtures with provenance and no case-only
filename collisions. Verify complete ordered topology: unique IDs, parentage,
depth-first order, contiguous sibling ordinals, valid unique ordered reference
edges and exact content-free schema encoding. The portable golden is the
canonical `topology.result` digest, not the whole session-bearing response.

Check graph/session/source-revision binding separately: repeated same-root
invocations retain graph ID, revision and golden but change session ID;
relocation retains revision and golden but changes graph ID; an admitted byte
change changes revision and golden. Neither artifact identity nor self-reported
versions substitutes for these controls.

Require negative controls for invalid roots, symlinks/FIFOs, invalid UTF-8,
unresolved references, collisions, each finite bound, observed source changes,
descriptor/dependency/platform refusal, import shadowing, declared audit events
and silent audit-hook refusal. Verify no synthetic text/property canary leaks,
graph mutation or bytecode/environment mutation. Exercise timeout, output
overflow, surviving descendants and finalization interruption/failure with
finite ownership and evidence retention.

No skipped, missing, mismatched, timed-out or incomplete required row counts as
PASS. Preserve terminal failures and exact run identities. Local diagnostics
are not a substitute for standard hosted CI or installed native runtime rows.

## Publication bridge prerequisite and public-byte campaign

Land the exact-alpha publisher/public-input bridge before final candidate
selection. It changes release tooling and policy only: the Parser 1.9.0
profile, contracts, descriptor/resource/TCK chain, application dependencies,
producer behavior and original diagnostic qualification workflow remain frozen.

The publisher must use the independently locked canonical builder and retain
its own original wheel/sdist, binding, source/frontend content ledger, actual
tool/build-environment record and canonical manifest. Attest all six public
subjects and attach them to the alpha Release; retain the Actions copy for at
least 14 days. Stage only the original two distributions for PyPI. Do not
substitute pre-publication bytes or reconstruct missing publisher evidence.

Require an independent official archive checksum, a fresh non-symlink action
tool cache and selected executable identity before workflow-owned uv calls.
The pinned action remains a trusted bootstrap component. Explicitly provision
CPython 3.12 before no-download consumption. Validate the source-derived
canonical-build record before successful public admission, and again during
aggregation; a later aggregate cannot repair premature package execution.

Once that bridge is merged, select a new clean final source `S` and run fresh
pre-publication qualification. Stop for the maintainer's explicit full
commit/tree confirmation and acknowledgement of tag-triggered publication
before creating or pushing `v2.1.0-alpha.1`.

After publication run `R` completes, the manual public-input workflow starts a
distinct run `Q`, from the same exact `S` on current `main`. Require first
attempts, six exact GitHub Release assets, two non-yanked PyPI originals,
bounded allowlisted HTTPS acquisition and cryptographic verification of all
six subjects. Source/signer digests and the certificate's signed publication
invocation must bind `R`; a self-declared statement field is not sufficient.
The public copies must be byte-identical to their publisher binding, and the
ledger must cover the selected Git tree and canonical frontend derivation.

Run the complete eight-row installed/operational matrix on those actual public
inputs, with four independent sdist build environments, source/JUnit evidence
and native Windows refusal only. Aggregate the actual `Q` jobs/artifacts
without replacing their names, source or run fields with diagnostic metadata.
Retain `R`, `Q`, source/tree, original pair, evidence digests and complete
row/cleanup outcomes separately. Failed, skipped, incomplete, mismatched or
uncertain evidence is NO-GO; a consumed failed publication or campaign is not
silently retried.

The release process's
[public-input bridge](../RELEASE_PROCESS.md#exact-alpha-publication-and-public-input-bridge)
defines the maintained entrypoints. This plan does not activate publication,
close #582, admit Trama or waive later full qualification and dual-profile Gate B.

## Ordered release and consumer handoff gates

1. **Preparation:** land version/policy, resource integration and workflow.
   Review one frozen candidate per milestone; require exact-head hosted CI.
   Keep dependency versions frozen through `v2.1.0-alpha.1`.
   At the workflow milestone's final handoff, consolidate every release-relevant
   `[Unreleased]` entry into the draft `[2.1.0-alpha.1]` section, leave a fresh
   empty `[Unreleased]` heading, and verify the literal tag's extracted notes.
   The current draft is not final release notes. Select the final source only
   after that consolidation and its reviewed commit have landed.
2. **Pre-publication qualification:** select the final source only after those
   merges. Run and review the declared eight-row workflow and refusal control,
   with one canonical artifact pair and complete digest/receipt chain.
   The maintainer independently decides experimental GO/NO-GO.
3. **Maintainer publication:** only the maintainer creates the signed
   `v2.1.0-alpha.1` tag and authorizes GitHub Releases/PyPI. Metadata is
   `2.1.0a1`; curated notes use `[2.1.0-alpha.1]`. This document authorizes none
   of those actions.
4. **Actual public-artifact binding:** after explicit publication confirmation,
   retrieve and verify public wheel/sdist identities, manifest and source-bound
   attestations, then repeat full installed and operational verification for
   all eight rows. Pre-publication hashes are diagnostic and need not equal the
   public workflow's newly built bytes. Do not substitute an earlier package.
5. **Producer handoff:** publish a sanitized immutable evidence bundle linking
   exact public artifacts, hashes, attestations, source/tree, supported matrix,
   dependency profile, invocation/lifecycle limits, fixtures/TCK and exclusions.
   No private paths, raw graph content or workstation logs belong in it.
6. **Independent consumer decision:** Trama evaluates those exact bytes under
   its own #2/ADR-0007 gate. Policy agreement, a fake-producer test or a public
   static schema is not compatibility admission or a real adapter result.

The first alpha does not close #582 or the full qualification track. The
transferred Windows/L/three-platform Stage A obligations and fresh exact-public-
artifact dual-profile Gate B remain explicit prerequisites of later full
qualification/stable decisions. Gate B was already separate from experimental
publication; no new claim of having passed or removed it is made.
