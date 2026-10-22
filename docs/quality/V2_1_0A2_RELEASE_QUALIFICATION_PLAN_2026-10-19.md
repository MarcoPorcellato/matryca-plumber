---
type: Roadmap
---
# Experimental 2.1.0a2 release qualification plan

Date: 2026-10-19. Status: **active preparation policy; no final candidate or
runtime qualification is selected by this document**.

## Preserved history and new candidate boundary

The [alpha.1 plan](V2_1_0A1_RELEASE_QUALIFICATION_PLAN_2026-10-16.md), its signed tag and
[failed publisher](../releases/v2.1.0-alpha.1-FAILED-PUBLICATION.md) remain
immutable historical evidence. The [recovery decision](ALPHA_RELEASE_RECOVERY_2026-10-18.md)
records the completed native bootstrap repair and this separately approved
migration. Earlier source diagnostics and failed publication do not qualify the
new alpha.2 source or public bytes.

The closed active policy is exactly `og-alpha2`, package version `2.1.0a2`,
prospective tag `v2.1.0-alpha.2`, and literal notes heading
`[2.1.0-alpha.2]`. Existing internal `alpha1_*` filenames and alpha
subcommands remain unchanged; stale alpha.1 and arbitrary future candidates are
not admitted by this tooling. Root-only version metadata causes only the
reviewed dependency-profile/manifest/descriptor digest cascade; the dependency
selections, native export, requirements, schemas, fixture/golden/TCK bytes and
producer policy remain frozen. Descriptor status stays `unqualified` and
matrix entries stay `planned` even when a separate exact-source campaign passes.

No final source is selected until the migration PR and normal main CI pass.
Then record actual signed source S/tree and one fresh first-attempt diagnostic
campaign D. All eight installed rows and mapped source/refusal/cleanup evidence
must be complete and independently reviewed. No tag or publication is authorized
by this preparation or diagnostic campaign. Later the maintainer must approve
that complete S/tree and explicitly acknowledge tag-triggered Releases/PyPI.

## 2026-10-20 dependency security amendment

The 2026-10-20 exception to this plan's dependency freeze is `aiohttp 3.14.3 -> 3.14.4`
and its mandatory `yarl 1.24.2 -> 1.25.1` lower bound. The official advisories
[GHSA-2g87-pp6c-29x5](https://github.com/advisories/GHSA-2g87-pp6c-29x5),
[GHSA-5wr8-gcqf-gqf3](https://github.com/advisories/GHSA-5wr8-gcqf-gqf3) and
[GHSA-494j-54xm-rwp3](https://github.com/advisories/GHSA-494j-54xm-rwp3)
identify `3.14.4` as the first patched release. Its declared dependency requires
`yarl>=1.25.1,<2.0`; retaining the former `1.24.2` pin would not be valid.

Regenerate only the canonical runtime export and affected profile, manifest and
descriptor hashes. Preserve every other dependency selection, Parser `1.9.0`,
the independent build lock/recipe, package version, workflow and producer
semantics, schema/fixture/golden/TCK bytes, bounds and qualification flags.

This correction invalidates qualification and publication activation for the
earlier `b488a3dbfb328b05b5506773e33132eebf5c5d90` source. Select the new actual
main commit/tree only after the reviewed correction and normal hosted CI pass,
then require a fresh first-attempt eight-row source campaign and independent
review. Diagnostic hashes do not qualify public bytes. A later explicit
new-source acknowledgement of tag-triggered publication, actual-public-package
verification and independent Trama admission remain separate gates. No earlier
attempt or security finding is dismissed or silently reused.

## 2026-10-21 frontend security amendment

The second dated freeze exception pins the development build dependency Vite to
`8.3.3`, with its required Rolldown `1.2.11`, `@oxc-project/types 0.151.0` and
fifteen existing optional native-binding records at `1.2.11`. The official
advisories [GHSA-587h-7wmj-h5pm](https://github.com/advisories/GHSA-587h-7wmj-h5pm),
[GHSA-698v-4r3x-3vcv](https://github.com/advisories/GHSA-698v-4r3x-3vcv) and
[GHSA-r825-w8mm-5pxw](https://github.com/advisories/GHSA-r825-w8mm-5pxw)
identify `8.3.3` as the first patched release on this branch. Development-tool
classification does not waive the security gate or establish runtime exposure.

Preserve the other 229 non-root frontend package records, every Python
dependency/profile/descriptor byte, the earlier HTTP exception, package version,
workflows, producer behavior and all schema/fixture/golden/TCK semantics. Static
registry-identity and SRI consistency checks do not replace package provenance
verification or the hosted frontend installation/build.

The earlier `04ef56ce61355f4665d8798c8f00fd938116fe95` source and its diagnostic
campaign do not qualify the amended source. After the correction merges and
normal main CI/security gates pass, record the actual new signed commit/tree
and require a fresh first-attempt eight-row source campaign and independent
review. A later explicit source/tree acknowledgement must precede any signed
tag push that triggers GitHub Releases/PyPI. Actual-public-byte verification
and independent Trama admission remain separate gates; no prior failure or
attempt is erased or transferred.

## 2026-10-21 certificate trust-store security amendment

The third dated freeze exception updates only `certifi 2026.5.20 -> 2026.10.19`
in the runtime lock and exact OG dependency export. The official advisory
[GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2)
identifies `2026.10.19` as the first patched release. The selected release
declares no additional dependencies. Preserve the other 91 lock records and
72 export entries, earlier HTTP and frontend exceptions, Parser `1.9.0`,
package version, build environment, workflows and all producer semantics.

Regenerate only the canonical frozen export and its existing dependency-profile,
manifest and descriptor digest cascade. Preserve qualification flags, matrix
states, schemas, fixtures, golden topology, TCK cases and code-module hashes.
Do not edit the CA bundle manually or disable certificate verification.

This exception supersedes the earlier dependency-freeze wording only for
certifi and those derived hashes. The earlier
`f50e2a71b216777dc1e4339d04ca97183bba9960` source and older diagnostics do not
qualify the amended source. After normal integration and complete main CI/security
gates, record the actual new signed source/tree and require one fresh
first-attempt eight-row source campaign with independent review. A later explicit
source/tree and tag-trigger acknowledgement must precede publication. Actual
public-byte verification and Trama admission remain separate gates.

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

Require the shared standard-library-only acquisition helper to authenticate the
fixed official archive size/SHA-256, safe member identity and fresh non-symlink
repository-owned root before workflow-owned uv calls. Do not override reserved
runner variables or trust an editable record as the archive identity. Explicitly provision
CPython 3.12 before no-download consumption. Validate the source-derived
canonical-build record before successful public admission, and again during
aggregation; a later aggregate cannot repair premature package execution.

Once that bridge is merged, select a new clean final source `S` and run fresh
pre-publication qualification. Stop for the maintainer's explicit full
commit/tree confirmation and acknowledgement of tag-triggered publication
before creating or pushing `v2.1.0-alpha.2`.

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

## 2026-10-22 public verifier provenance amendment

Preserve the historical same-source procedure above and all consumed attempts.
Publication completed from source S
`82df37cdd4751e7cf0da9bf6372785567251c0ea`, tree T
`e5e43299b06f780905cc16920e3ebaca701f2d8e`, through publisher run
`39734945749`, attempt 1. The signed alpha.2 tag and exact published originals
remain fixed. Public run `39741677332`, attempt 1, failed at metadata command
construction before that fetch child; Windows refusal passed, but the source
and four installed jobs skipped. No public installed result is accepted.

The [dated release-process exception](../RELEASE_PROCESS.md#2026-10-22-separate-the-verifier-without-replacing-alpha2)
permits a separately reviewed qualification-only revision C whose sole parent
is S. It does not select or activate C by itself. Before a distinct new Q2,
the maintainer must separately bind C's complete commit/tree/workflow hash,
S/T, publisher R and the preserved public inventories. C must still be exact
protected main; any drift stops. There is no arbitrary verifier input, dirty S
overlay, server-side rerun, rebuilt original or publication fallback.

Use two clean disjoint checkouts: literal producer S and verifier C selected
from the actual event SHA. Run helpers from C, derive locks/resources,
canonical-build and ledger expectations from S, check source-child import
origins before collection and keep installed children isolated from both
checkouts. Public schema 2 adds explicit verifier commit/tree/workflow fields;
actual Q2/job/artifact metadata binds C while package, source and installed
records remain S-bound. Reject missing/schema-1/defaulted or conflated
identities. Producer attestations continue to bind S and signed publisher R;
diagnostic MatrixContext, RC schemas and default source qualification stay unchanged.

The argv correction changes only the metadata option encoding to
`--sha256=`; it does not allow an empty argv element or waive distribution
digest, source, signature, canonical-build, acquisition or cleanup controls.
Require the entire existing public matrix and all eight report roles before
accepting Q2. Corrected tooling, local synthetic tests and integration CI are
not actual-public-byte evidence.

The later documentary handoff H, if separately activated after accepted Q2,
has sole parent C rather than S and still covers only its four approved
documentary paths. It must preserve separate S/C/R/Q2 identities and cannot
become a source for either campaign. No Q2, H, tag, publication, Trama
admission, Windows-installed or stable support claim is authorized by this
amendment. Issue #582 and the independent full-soak programme remain open.

## Failed installed-control diagnostics

The first macOS arm64 / Python 3.12 wheel failure on the certifi correction
reported `native-stderr-overflow-cleanup`, uncertain cleanup and
`term_signal_failed`. It did not preserve the caught signal exception identity
or original child failure reason. The cause is not established; earlier passing
controls do not qualify that installed row or its unexecuted sdist counterpart.

Failure-only diagnostics retain fixed exception categories, allowlisted errno
identities and an allowlisted underlying child reason. They do not change the
original failure event, cleanup verdict, successful report shape, lifecycle
decisions, native fixtures, limits or dependencies. The authenticated descriptor
must bind the changed diagnostic code. New source requires fresh exact-head
hosted evidence; non-reproduction does not prove the historical cause repaired.
Publication, public-byte verification and independent consumer admission remain
separate gates.

## Ordered release and consumer handoff gates

1. **Preparation:** land version/policy, resource integration and workflow.
   Review one frozen candidate per milestone; require exact-head hosted CI.
   Keep dependency versions frozen through `v2.1.0-alpha.2`.
   At the workflow milestone's final handoff, move only the new acquisition note from
   `[Unreleased]` into the draft `[2.1.0-alpha.2]` section, add the migration note,
   preserve the complete alpha.1 section and carry its capabilities by reference,
   leave a fresh
   empty `[Unreleased]` heading, and verify the literal tag's extracted notes.
   The current draft is not final release notes. Select the final source only
   after that consolidation and its reviewed commit have landed.
2. **Pre-publication qualification:** select the final source only after those
   merges. Run and review the declared eight-row workflow and refusal control,
   with one canonical artifact pair and complete digest/receipt chain.
   The maintainer independently decides experimental GO/NO-GO.
3. **Maintainer publication:** only the maintainer creates the signed
   `v2.1.0-alpha.2` tag and authorizes GitHub Releases/PyPI. Metadata is
   `2.1.0a2`; curated notes use `[2.1.0-alpha.2]`. This document authorizes none
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

This experimental alpha does not close #582 or the full qualification track. The
transferred Windows/L/three-platform Stage A obligations and fresh exact-public-
artifact dual-profile Gate B remain explicit prerequisites of later full
qualification/stable decisions. Gate B was already separate from experimental
publication; no new claim of having passed or removed it is made.
