---
type: release-qualification-plan
title: v2.0.1-rc.4 release qualification plan
description: Proposed exact-artifact qualification envelope for the RC4 delta; no candidate, release, package, soak result, or stable decision is selected.
resource: docs/quality/V2_0_1_RC4_RELEASE_QUALIFICATION_PLAN_2026-09-06.md
tags: [release, qualification, parser, topology, contracts, v2]
last_verified: 2026-09-06
stale_after: 2027-03-06
status: proposed
classification: active
audience: [maintainer, contributor, operator]
owner: release
authority: release-qualification-plan
related:
  - V2_0_1_RC4_RELEASE_PREPARATION_2026-09-06.md
  - RELEASE_QUALIFICATION_GATE_MAP.md
  - RISK_BASED_RELEASE_QUALIFICATION_DECISION_2026-08-24.md
  - GATE_B_RC_SOAK_RUNBOOK.md
  - LOGSEQ_DB_CLI_ARTIFACT_EVIDENCE_2026-09-06.md
---

# v2.0.1-rc.4 release qualification plan

## Authority and non-selection boundary

This proposed plan is tracked by
[#582](https://github.com/MarcoPorcellato/matryca-plumber/issues/582). It is
separate from the implementation and package-preparation authority in
[#579](https://github.com/MarcoPorcellato/matryca-plumber/issues/579).

The planning anchor is `origin/main` commit
`118b265b5c6b29682c76453aad5fbde0de0c841f`. It is not an RC4 candidate.
The release authority must first select one exact, reachable, clean-source commit
after the implementation/preparation merge plan is complete. That selection must
record the full commit ID, tree ID, clean status, source provenance, and the
resulting wheel/sdist filenames and SHA-256 values. A later change requires a new
selection and invalidates candidate-bound evidence.

No candidate source, tag, public artifact, Gate B result, or stable decision is selected.
This document creates no tag, GitHub Release, PyPI upload, hosted workflow run,
or local qualification attempt. It does not authorize a heavy Gate B/CCP invocation.

Historical RC3 publication, RC2 failure, and earlier Gate B evidence remain bound to
their own artifacts. They do not qualify RC4 or a future stable `v2.0.1`.

## Complete RC4 delta classification

The delta is assessed against the last qualified public artifact, not against an
unpublished preparation commit. The following rows are a complete release-plan
classification, not evidence that any row has passed.

| Delta | Release-relevant behavior | Required control | Tier effect |
| --- | --- | --- | --- |
| Parser 1.9 snapshot | Plumber selects Parser 1.9 internally and calls `LogseqGraph.from_snapshot_pages()` for a bounded graph-wide snapshot. | Exact dependency resolution; parser-factory, bounded-snapshot, strict reference/title-collision, and source-provenance tests. | Parser/graph-I/O semantics: Tier 3. |
| Process timeout lifecycle | Pathological parser work is killed/recycled deterministically; no stale result crosses the process boundary. | Controlled seam/fake tests for timeout, terminate/recycle, result rejection, and later successful work. | Service lifecycle/recovery: Tier 3. |
| topology session | A Plumber-owned, session-bound read projection maps resolved wikilinks/block references into complete topology. | Complete-node/edge, closed-session, foreign-graph, incomplete-topology, strict-failure, and no-aggregated-page-ref tests. | Graph I/O/session semantics: Tier 3. |
| static contract/TCK resources | Three public, content-free contract families and their deterministic TCK scripts ship in wheel and sdist. | Archive membership/byte parity, installed-resource discovery, installed TCK, metadata, and `RECORD` checks. | Distribution change; included in the overall Tier 3 envelope. |
| Logseq DB policy | Capability discovery fixtures and protocol are test-only and unbound. | Negative protocol fixtures; inspect package/runtime imports to prove no DB adapter, transport, direct internal access, or capability claim. | No DB runtime support is introduced; it cannot lower the overall tier. |
| #580 external evidence | The first official bundled-CLI attempt is `upstream_blocked` at executable admission. | Preserve the artifact record as blocked; do not substitute it for runtime or DB compatibility evidence. | No executable/DB behavior was tested; no qualification credit. |

The release is **Tier 3** because the candidate delta changes Parser and graph-I/O
semantics and a process timeout lifecycle. The Tier 3 classification applies even
though the DB policy is test-only/unbound and the static resources are content-free.
No downgrade is available under this plan without a new reviewed decision.

## Candidate selection and source gates

After separate merge authority selects the candidate, record the following before
any publication action:

1. Exact commit/tree, ancestry from protected `main`, clean worktree, version
   agreement (`2.0.1rc4` / `v2.0.1-rc.4`), dependency lock, and no uncommitted
   generated-resource drift.
2. Terminal required hosted CI for that exact commit. Record workflow/run URLs,
   required-check names, conclusions, and any explicit non-blocking lane; a local
   pass is not a hosted-CI substitute.
3. Reproducible release build from the selected source. Record exactly one wheel
   and one sdist, each filename, size, SHA-256, build command, and archive manifest.
   Reject missing, additional, compiled-cache, version-drift, or resource-drift
   members.
4. Isolated installs of the selected wheel and sdist. Verify package metadata,
   `RECORD`, all 26 static contract/TCK resources, and byte-for-byte source/wheel/
   sdist parity. Run all three installed TCKs from the installed package context;
   source-checkout success alone is insufficient.

## Targeted runtime and package controls

The candidate must retain focused, deterministic evidence for:

- Parser 1.9’s public snapshot factory, bounded snapshot projection, unresolved
  block-reference and title-collision fail-closed behavior, and explicit reference
  origin handling. `LogseqNode.refs` and aggregated page-property references must
  not be inferred as topology edges without an explicit contract.
- Process timeout lifecycle: forced timeout, worker termination, recycle, no stale
  result, and a subsequent bounded parse. Fixture speed must not be used as an
  accidental timeout proxy.
- Topology session authority: Plumber composition only; no public Python adapter,
  `Path`-accepting consumer API, transport, CLI/MCP command, Trama/Brain import,
  UI, or LENS. Validate closed sessions, foreign graphs, incomplete topology, and
  all topology TCK fixtures fail or pass as declared.
- Package inclusions: `plumber.consumer.package/v1`, `plumber.graph.read/v1`, and
  `plumber.graph.topology/v1` schemas, profiles, fixtures, manifests, and TCKs;
  all stay static, content-free, and installable without a user graph.
- DB negative policy: the package contains no supported Logseq DB capability. The
  #580 `upstream_blocked` record is retained as evidence of a stopped external
  artifact admission, not as an operational test result.

## Platform and profile matrix

No platform result is recorded by this plan. Before RC4 publication, attach
candidate-bound evidence for each applicable row and disposition any unavailable
row explicitly; never mark an unrun row as covered by a different runner.

| Surface | Required evidence | Status now |
| --- | --- | --- |
| Hosted source CI, Python 3.12 | Exact candidate required checks, including docs, lint, types, security, and full tests. | Unselected. |
| Hosted source CI, Python 3.13 | Exact candidate matrix conclusion and compatibility disposition. | Unselected. |
| Installed wheel and sdist | Isolated install, metadata/`RECORD`, 26-resource parity, and all installed TCKs on every supported release platform implicated by the artifact. | Unselected. |
| macOS arm64 | Candidate-bound Parser/topology and timeout controls on the supported maintainer platform. | Unselected. |
| Linux hosted runner | Candidate-bound parser/topology, archive, and installed-package controls. | Unselected. |
| Windows | Candidate-bound installed-package/TCK and process-lifecycle disposition if the release support claim includes Windows. | Unselected. |
| `default-on` Gate B profile | Exact installed public RC4 artifact; independent attempt chain and terminal report. | Not started. |
| `read-only + external Shadow` Gate B profile | Exact installed public RC4 artifact; independent attempt chain and terminal report. | Not started. |

## Gate B and publication sequence

Tier 3 requires fresh exact-artifact Gate B. Each required profile must accumulate
at least **259,200 valid seconds per required profile**: `default-on` and
`read-only + external Shadow`. Setup, preflight, downtime, interruptions, prior
campaigns, and a different artifact contribute zero seconds. The campaign begins
only after a separately authorized public RC4 artifact and resource/admission check;
it must follow the Gate B runbook’s checkpoint, receipt, interruption, and
public-safe evidence rules.

This plan neither starts that campaign nor authorizes an exception. The local
coordinator/CCP is operational support, not release qualification; normal public
hosted CI must remain separate from the heavy soak decision.

RC4 pre-publication sequence is: select clean source; pass exact hosted CI; build and
hash artifacts; verify installed resources/TCK/parity and targeted controls; obtain
separate tag/publication authority; bind Gate B to the resulting exact public artifact;
then record a release-specific final disposition. A prerelease result does not promote
stable `v2.0.1`.

Any future stable `v2.0.1` needs its own exact source/artifact selection, delta
classification, publication authority, and final decision. It may cite RC4 only as
historical, artifact-bound evidence and must not transfer RC4’s source, package,
platform, or Gate B result to changed stable bytes.

## Stop conditions

Stop and return to release authority if source/tree/package identity is missing;
hosted CI is absent or non-terminal; an archive resource differs; an installed TCK
uses checkout bytes; Parser/topology controls fail; timeout handling returns stale
data; a DB policy is presented as runtime support; the public artifact differs from
the gated bytes; a Gate B profile lacks valid duration; or the stable decision is
attempted from RC4 inference.
